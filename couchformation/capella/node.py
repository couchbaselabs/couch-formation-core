##
##

import logging
from couchformation.exception import FatalError
from couchformation.capella.driver.base import CloudBase
from couchformation.config import get_state_file, get_state_dir
from couchformation.kvdb import KeyValueStore
from couchformation.util import FileManager, Synchronize
from couchformation.capella.driver.cb_capella import Capella, CapellaCluster, AllowedCIDR, Credentials, AppService
from couchformation.util import PasswordUtility

logger = logging.getLogger('couchformation.capella.node')
logger.addHandler(logging.NullHandler())


class CapellaNodeError(FatalError):
    pass


class CapellaDeployment(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.name = parameters.get('name')
        self.deploy_type = parameters.get('type') if parameters.get('type') else "database"
        self.cluster_id = parameters.get('instance_id')
        self.project = parameters.get('project')
        self.region = parameters.get('region') if parameters.get('region') else "us-east-1"
        self.cloud = parameters.get('cloud')
        self.provider = parameters.get('provider') if parameters.get('provider') else "aws"
        self.username = parameters.get('username') if parameters.get('username') else "Administrator"
        self.password = parameters.get('password')
        self.account_email = parameters.get('account_email')
        self.profile = parameters.get('profile') if parameters.get('profile') else 'default'
        self.sw_version = self.parameters.get('sw_version') if self.parameters.get('sw_version') else "latest"
        self.cidr = parameters.get('cidr') if parameters.get('cidr') else "10.0.0.0/23"
        self.allow = parameters.get('allow') if parameters.get('allow') else "0.0.0.0/0"
        self.db_name = f"{self.name}-database"

        self.state_file = get_state_file(self.project, self.name)
        self.state_dir = get_state_dir(self.project, self.name)

        with Synchronize():
            try:
                FileManager().make_dir(self.state_dir)
            except Exception as err:
                raise CapellaNodeError(f"can not create state dir: {err}")

        document = self.db_name
        self.state = KeyValueStore(self.state_file, document)

        CloudBase(self.parameters).test_session()

    def compose(self):
        if self.deploy_type == "mobile":
            self.compose_app_svc()
        else:
            self.compose_database()

    def compose_app_svc(self):
        number = self.parameters.get('number') if self.parameters.get('number') else 1
        document = f"{self.name}-node-group-{number:02d}"
        group = KeyValueStore(self.state_file, document)

        group['machine_type'] = self.parameters.get('machine_type')
        group['quantity'] = self.parameters.get('quantity') if self.parameters.get('quantity') else 2

    def compose_database(self):
        number = self.parameters.get('number') if self.parameters.get('number') else 1
        document = f"{self.name}-node-group-{number:02d}"
        group = KeyValueStore(self.state_file, document)

        group['cloud'] = self.parameters.get('provider')
        group['machine_type'] = self.parameters.get('machine_type')
        group['volume_size'] = self.parameters.get('volume_size') if self.parameters.get('volume_size') else "256"
        group['quantity'] = self.parameters.get('quantity') if self.parameters.get('quantity') else 3
        group['services'] = self.parameters.get('services') if self.parameters.get('services') else "data,index,query"

    def deploy(self):
        if self.deploy_type == "mobile":
            self.deploy_app_svc()
        else:
            self.deploy_database()

    def deploy_app_svc(self):
        state_db = KeyValueStore(self.state_file)
        node_groups = state_db.doc_id_startswith(f"{self.name}-node-group")

        if len(node_groups) == 0:
            raise CapellaNodeError("no node groups present")

        if self.state.get('project_id'):
            project_id = self.state.get('project_id')
        else:
            project_data = Capella(profile=self.profile).get_project(self.project)
            if not project_data:
                raise CapellaNodeError(f"Project {self.project} does not exist, please create a database for app service {self.name}")
            else:
                project_id = project_data.get('id')

        self.state['project'] = self.project
        self.state['type'] = self.deploy_type

        if not self.cluster_id:
            raise CapellaNodeError(f"Please connect the app service {self.name} to a Capella database")

        self.state['instance_id'] = self.cluster_id

        for group in node_groups:
            group_db = KeyValueStore(self.state_file, group)

            if self.state.get('app_svc_id'):
                logger.info(f"App service {self.name} already exists")
                app_svc_id = self.state['app_svc_id']
            else:
                quantity = int(group_db.get('quantity'))
                machine = group_db.get('machine_type')
                logger.info(f"Creating app service {self.name} with {quantity} {machine} nodes")
                app_svc = AppService.create(self.name, "CouchFormation managed app service", quantity, machine, self.sw_version)

                app_svc_id = Capella(project_id=project_id, profile=self.profile).create_app_svc(self.cluster_id, app_svc)
                self.state['name'] = self.name
                self.state['app_svc_id'] = app_svc_id
                logger.info("Waiting for app service creation to complete")
                if not Capella(project_id=project_id, profile=self.profile).wait_for_app_svc(self.cluster_id):
                    raise CapellaNodeError("Timeout waiting for app service to deploy")

            logger.info(f"App service ID: {app_svc_id}")

        logger.info("Capella app service successfully created")

        return self.state.as_dict

    def deploy_database(self):
        state_db = KeyValueStore(self.state_file)
        node_groups = state_db.doc_id_startswith(f"{self.name}-node-group")

        if len(node_groups) == 0:
            raise CapellaNodeError("no node groups present")

        cluster = CapellaCluster().create(self.name, "CouchFormation managed cluster", self.provider, self.region, self.cidr, version=self.sw_version)

        for group in node_groups:
            group_db = KeyValueStore(self.state_file, group)
            cluster.add_service_group(group_db.get('cloud'),
                                      group_db.get('machine_type'),
                                      int(group_db.get('volume_size')),
                                      int(group_db.get('quantity')),
                                      group_db.get('services').split(','))

        if self.state.get('project_id'):
            project_id = self.state.get('project_id')
        else:
            project_data = Capella(profile=self.profile).get_project(self.project)
            if not project_data:
                logger.info(f"Creating project {self.project}")
                project_id = Capella(profile=self.profile).create_project(self.project, self.account_email)
                self.state['project_id'] = project_id
            else:
                project_id = project_data.get('id')

        self.state['project'] = self.project
        self.state['type'] = self.deploy_type

        if self.state.get('instance_id'):
            logger.info(f"Database {self.db_name} already exists")
            cluster_id = self.state['instance_id']
        else:
            logger.info(f"Creating cluster {self.name}")
            cluster_id = Capella(project_id=project_id, profile=self.profile).create_cluster(cluster)
            self.state['instance_id'] = cluster_id
            self.state['provider'] = self.provider
            self.state['region'] = self.region
            self.state['cidr'] = self.cidr
            self.state['name'] = self.name
            self.state['cloud'] = self.cloud
            logger.info("Waiting for cluster creation to complete")
            if not Capella(project_id=project_id, profile=self.profile).wait_for_cluster(self.name):
                raise CapellaNodeError("Timeout waiting for cluster to deploy")

        logger.info(f"Cluster ID: {cluster_id}")

        cluster_info = Capella(project_id=project_id, profile=self.profile).get_cluster_by_id(cluster_id)
        connect_string = cluster_info.get('connectionString')
        self.state['connect_string'] = connect_string
        logger.info(f"Connect string: {connect_string}")

        if self.state.get('allow'):
            logger.info(f"Allow list already set to {self.state.get('allow')}")
        else:
            allow_cidr = AllowedCIDR().create(self.allow)
            logger.info(f"Configuring allowed CIDR {self.allow}")
            Capella(project_id=project_id, profile=self.profile).allow_cidr(cluster_id, allow_cidr)
            self.state['allow'] = self.allow

        if self.state.get('username'):
            logger.info(f"Database user {self.state.get('username')} already exists")
        else:
            if self.password:
                password = self.password
            else:
                password = PasswordUtility().generate(16)
                self.state['password'] = password
                logger.info(f"Password: {password}")
            credentials = Credentials().create(self.username, password)
            logger.info(f"Creating database user {self.username}")
            Capella(project_id=project_id, profile=self.profile).add_db_user(cluster_id, credentials)
            self.state['username'] = self.username

        logger.info("Capella database successfully created")

        return self.state.as_dict

    def destroy(self):
        project = self.state.get('project')
        if not project:
            return
        project_data = Capella(profile=self.profile).get_project(project)
        project_id = project_data.get('id')
        logger.info(f"Project {project} ID {project_id}")

        if self.state.get('type') == "mobile":
            self.destroy_app_svc(project_id)
        else:
            self.destroy_database(project, project_id)

    def destroy_app_svc(self, project_id):
        app_svc_name = self.state['name']
        cluster_id = self.state['instance_id']

        logger.info(f"Destroying app service {app_svc_name}")
        Capella(project_id=project_id, profile=self.profile).delete_app_svc(cluster_id)
        logger.info("Waiting for app service deletion to complete")
        if not Capella(project_id=project_id, profile=self.profile).wait_for_app_svc_delete(cluster_id):
            raise CapellaNodeError("Timeout waiting for app service deletion to complete")

        self.state.clear()

    def destroy_database(self, project, project_id):
        cluster_name = self.state['name'] = self.name
        logger.info(f"Destroying cluster {cluster_name}")
        Capella(project_id=project_id, profile=self.profile).delete_cluster(cluster_name)
        logger.info("Waiting for cluster deletion to complete")
        if not Capella(project_id=project_id, profile=self.profile).wait_for_cluster_delete(cluster_name):
            raise CapellaNodeError("Timeout waiting for cluster deletion to complete")

        if self.state.get('project_id'):
            cluster_list = Capella(project_id=project_id, profile=self.profile).list_clusters()
            if len(cluster_list) == 0:
                logger.info(f"Removing project {project}")
                Capella(profile=self.profile).delete_project(project)
            else:
                logger.warning(f"Project {project} has active clusters, it will not be removed")

        self.state.clear()

    def info(self):
        return self.state.as_dict
