##
##

import logging
from couchformation.exception import FatalError
from couchformation.capella.driver.base import CloudBase
from couchformation.config import get_state_file, get_state_dir
from couchformation.kvdb import KeyValueStore
from couchformation.util import FileManager, Synchronize
from cbcmgr.cb_capella import Capella, CapellaCluster, AllowedCIDR, Credentials
import couchformation.constants as C


logger = logging.getLogger('couchformation.capella.node')
logger.addHandler(logging.NullHandler())


class CapellaNodeError(FatalError):
    pass


class CapellaDeployment(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.name = parameters.get('name')
        self.project = parameters.get('project')
        self.region = parameters.get('region')
        self.cloud = parameters.get('cloud')
        self.provider = parameters.get('provider')
        self.username = parameters.get('username') if parameters.get('username') else "Administrator"
        self.password = parameters.get('password')
        self.account_email = parameters.get('account_email')
        self.cidr = parameters.get('cidr') if parameters.get('cidr') else "10.0.0.0/23"
        self.allow = parameters.get('allow') if parameters.get('allow') else "0.0.0.0/0"
        self.db_name = f"{self.name}-database"

        self.state_file = get_state_file(self.project, self.name)
        self.state_dir = get_state_dir(self.project, self.name)

        with Synchronize(C.GLOBAL_LOCK):
            try:
                FileManager().make_dir(self.state_dir)
            except Exception as err:
                raise CapellaNodeError(f"can not create state dir: {err}")

        document = self.db_name
        self.state = KeyValueStore(self.state_file, document)

        CloudBase(self.parameters).test_session()

    def compose(self):
        number = self.parameters.get('number') if self.parameters.get('number') else 1
        document = f"{self.name}-node-group-{number:02d}"
        group = KeyValueStore(self.state_file, document)

        group['cloud'] = self.parameters.get('provider')
        group['machine_type'] = self.parameters.get('machine_type')
        group['volume_size'] = self.parameters.get('volume_size') if self.parameters.get('volume_size') else "256"
        group['quantity'] = self.parameters.get('quantity') if self.parameters.get('quantity') else 3
        group['services'] = self.parameters.get('services') if self.parameters.get('services') else "data,index,query"

    def deploy(self):
        state_db = KeyValueStore(self.state_file)
        node_groups = state_db.doc_id_startswith(f"{self.name}-node-group")

        if len(node_groups) == 0:
            raise CapellaNodeError("no node groups present")

        cluster = CapellaCluster().create(self.name, "CouchFormation managed cluster", self.provider, self.region, self.cidr)

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
            project_data = Capella().get_project(self.project)
            if not project_data:
                logger.info(f"Creating project {self.project}")
                project_id = Capella().create_project(self.project, self.account_email)
                self.state['project_id'] = project_id
            else:
                project_id = project_data.get('id')

        self.state['project'] = self.project

        if self.state.get('instance_id'):
            logger.info(f"Database {self.db_name} already exists")
            cluster_id = self.state['instance_id']
        else:
            logger.info(f"Creating cluster {self.name}")
            cluster_id = Capella(project_id=project_id).create_cluster(cluster)
            self.state['instance_id'] = cluster_id
            self.state['provider'] = self.provider
            self.state['region'] = self.region
            self.state['cidr'] = self.cidr
            self.state['name'] = self.name
            self.state['cloud'] = self.cloud
            logger.info("Waiting for cluster creation to complete")
            Capella(project_id=project_id).wait_for_cluster(self.name)

        logger.info(f"Cluster ID: {cluster_id}")

        if self.state.get('allow'):
            logger.info(f"Allow list already set to {self.state.get('allow')}")
        else:
            allow_cidr = AllowedCIDR().create(self.allow)
            logger.info(f"Configuring allowed CIDR {self.allow}")
            Capella(project_id=project_id).allow_cidr(cluster_id, allow_cidr)
            self.state['allow'] = self.allow

        if self.state.get('username'):
            logger.info(f"Database user {self.state.get('username')} already exists")
        else:
            if self.password:
                password = self.password
            else:
                password = Capella().generate_password()
                logger.info(f"Password: {password}")
            credentials = Credentials().create(self.username, password)
            logger.info(f"Creating database user {self.username}")
            Capella(project_id=project_id).add_db_user(cluster_id, credentials)
            self.state['username'] = self.username

        logger.info("Capella database successfully created")

        return self.state.as_dict

    def destroy(self):
        project = self.state.get('project')
        project_data = Capella().get_project(project)
        project_id = project_data.get('id')
        logger.info(f"Project {project} ID {project_id}")

        cluster_name = self.state['name'] = self.name
        logger.info(f"Destroying cluster {cluster_name}")
        Capella(project_id=project_id).delete_cluster(cluster_name)
        logger.info("Waiting for cluster deletion to complete")
        Capella(project_id=project_id).wait_for_cluster_delete(cluster_name)

        if self.state.get('project_id'):
            cluster_list = Capella(project_id=project_id).list_clusters()
            if len(cluster_list) == 0:
                logger.info(f"Removing project {project}")
                Capella().delete_project(project)
            else:
                logger.warning(f"Project {project} has active clusters, it will not be removed")

        self.state.clear()

    def info(self):
        return self.state.as_dict
