##
##

import logging
from couchformation.exception import FatalError
from couchformation.capella.driver.base import CloudBase
from couchformation.config import get_state_file, get_state_dir, State
from couchformation.kvdb import KeyValueStore
from couchformation.util import FileManager, Synchronize
from couchformation.util import PasswordUtility
from couchformation.deployment import MetadataManager
from couchformation.project import Project
from libcapella.columnar import CapellaColumnar
from libcapella.columnar_allowed_cidr import ColumnarAllowedCIDR
from libcapella.database import CapellaDatabase
from libcapella.database_allowed_cidr import CapellaAllowedCIDR
from libcapella.database_credentials import CapellaDatabaseCredentials
from libcapella.app_service import CapellaAppService
from libcapella.network_peers import CapellaNetworkPeers
from libcapella.logic.columnar import CapellaColumnarBuilder
from libcapella.logic.allowed_cidr import AllowedCIDRBuilder
from libcapella.logic.database import CapellaDatabaseBuilder
from libcapella.logic.credentials import DatabaseCredentialsBuilder
from libcapella.logic.app_service import CapellaAppServiceBuilder
from libcapella.logic.network_peers import NetworkPeerBuilder

logger = logging.getLogger('couchformation.capella.node')
logger.addHandler(logging.NullHandler())
logging.getLogger("restfull").setLevel(logging.ERROR)


class CapellaNodeError(FatalError):
    pass


class CapellaDeployment(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.name = parameters.get('name')
        self.deploy_type = parameters.get('type') if parameters.get('type') else "database"
        self.cluster_id = parameters.get('instance_id')
        self.cluster_name = parameters.get('instance_name')
        self.project_name = parameters.get('project')
        self.build = parameters.get('build')
        self.region = parameters.get('region') if parameters.get('region') else "us-east-1"
        self.cloud = parameters.get('cloud')
        self.machine_type = parameters.get('machine_type')
        self.quantity = parameters.get('quantity')
        self.provider = parameters.get('provider') if parameters.get('provider') else "aws"
        self.username = parameters.get('username') if parameters.get('username') else "Administrator"
        self.password = parameters.get('password')
        self.account_email = parameters.get('account_email')
        self.profile = parameters.get('profile') if parameters.get('profile') else 'default'
        self.sw_version = self.parameters.get('sw_version') if self.parameters.get('sw_version') else "latest"
        self.cidr = parameters.get('cidr')
        self.allow = parameters.get('allow') if parameters.get('allow') else "0.0.0.0/0"
        self.peer_project = parameters.get('peer_project')
        self.peer_region = parameters.get('peer_region')
        self.node_name = f"{self.name}-node-01"

        self.state_file = get_state_file(self.project_name, self.name)
        self.state_dir = get_state_dir(self.project_name, self.name)

        with Synchronize():
            try:
                FileManager().make_dir(self.state_dir)
            except Exception as err:
                raise CapellaNodeError(f"can not create state dir: {err}")

        document = self.node_name
        self.state = KeyValueStore(self.state_file, document)

        self.base = CloudBase(self.parameters)
        self.base.test_session()

        self.project_id = self.base.project_id
        self.org_id = self.base.organization_id
        self.project = self.base.project

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
        if self.build == "columnar":
            self.deploy_columnar()
        else:
            if self.deploy_type == "mobile":
                self.deploy_app_svc()
            else:
                self.deploy_database()
        if self.peer_project:
            self.peer_cluster()

    def deploy_app_svc(self):
        document = f"{self.name}-node-group-01"
        group = KeyValueStore(self.state_file, document)
        self.state['state'] = State.DEPLOYING.value

        self.state['project_id'] = self.project_id
        self.state['project'] = self.project_name
        self.state['type'] = self.deploy_type

        if not self.cluster_id:
            raise CapellaNodeError(f"Please connect the app service {self.name} to a Capella database")

        self.state['instance_id'] = self.cluster_id

        quantity = int(group.get('quantity'))
        machine = group.get('machine_type')

        try:
            database = CapellaDatabase(self.project, self.cluster_name)
            app_service = CapellaAppService(database)
            if not app_service.id:
                builder = CapellaAppServiceBuilder()
                builder.name(self.name)
                builder.compute(machine, quantity)
                config = builder.build()
                logger.info(f"Creating app service {self.name} with {quantity} {machine} nodes")
                app_service.create(config)
                logger.info("Waiting for app service creation to complete")
                if not app_service.wait("healthy", until=True):
                    raise CapellaNodeError("Timeout waiting for app service to deploy")
            else:
                logger.info(f"App service {self.name} already exists")
        except Exception as err:
            raise CapellaNodeError(f"Error creating app service: {err}")

        self.state['name'] = self.name
        self.state['cluster_name'] = self.cluster_name
        self.state['app_svc_id'] = app_service.id

        logger.info(f"App service ID: {app_service.id}")

        logger.info("Capella app service successfully created")

        self.state['state'] = State.DEPLOYED.value
        return self.state.as_dict

    def deploy_database(self):
        state_db = KeyValueStore(self.state_file)
        node_groups = state_db.doc_id_startswith(f"{self.name}-node-group")
        self.state['state'] = State.DEPLOYING.value

        if len(node_groups) == 0:
            raise CapellaNodeError("no node groups present")

        self.state['project'] = self.project_name
        self.state['type'] = self.deploy_type

        try:
            database = CapellaDatabase(self.project, self.name)
            if not database.id:
                logger.info(f"Creating cluster {self.name}")
                builder = CapellaDatabaseBuilder(self.provider)
                builder = builder.name(self.name)
                builder = builder.description("Pytest created cluster")
                builder = builder.region(self.region)
                if self.cidr:
                    builder = builder.cidr(self.cidr)
                for group in node_groups:
                    group_db = KeyValueStore(self.state_file, group)
                    machine_type = group_db.get('machine_type')
                    quantity = group_db.get('quantity')
                    volume_size = group_db.get('volume_size')
                    services = group_db.get('services').split(',')
                    builder = builder.service_group(machine_type, quantity, volume_size, services)
                config = builder.build()
                database.create(config)
                logger.info("Waiting for cluster creation to complete")
                if not database.wait("deploying"):
                    raise CapellaNodeError("Timeout waiting for cluster to deploy")
            else:
                logger.info(f"Database {self.name} already exists")

            database.refresh()
            self.state['instance_id'] = database.id
            self.state['provider'] = database.this.cloudProvider.type
            self.state['region'] = database.this.cloudProvider.region
            self.state['cidr'] = database.this.cloudProvider.cidr
            self.state['name'] = database.this.name
            self.state['cloud'] = self.cloud
            self.state['connect_string'] = database.this.connectionString

            logger.info(f"Cluster ID: {database.id}")
            logger.info(f"Cloud provider: {database.this.cloudProvider.type}")
            logger.info(f"Cloud region: {database.this.cloudProvider.region}")
            logger.info(f"Cluster CIDR: {database.this.cloudProvider.cidr}")
            logger.info(f"Connect string: {database.this.connectionString}")

            allowed_cidr = CapellaAllowedCIDR(database, self.allow)
            if not allowed_cidr.id:
                logger.info(f"Configuring allowed CIDR {self.allow}")
                builder = AllowedCIDRBuilder()
                builder.cidr(self.allow)
                config = builder.build()
                allowed_cidr.create(config)
            else:
                logger.info(f"Allow list already set to {self.state.get('allow')}")

            self.state['allow'] = self.allow

            if self.password:
                password = self.password
            else:
                password = PasswordUtility().generate(16)

            database_credential = CapellaDatabaseCredentials(database, self.username)
            if not database_credential.id:
                logger.info(f"Creating database user {self.username}")
                builder = DatabaseCredentialsBuilder(self.username, password)
                builder.data_read_write()
                config = builder.build()
                database_credential.create(config)
                self.state['password'] = password
            else:
                logger.info(f"Database user {self.state.get('username')} already exists")
        except Exception as err:
            raise CapellaNodeError(f"Error creating database: {err}")

        self.state['username'] = self.username

        logger.info("Capella database successfully created")

        self.state['state'] = State.DEPLOYED.value
        return self.state.as_dict

    def deploy_columnar(self):
        self.state['state'] = State.DEPLOYING.value
        self.state['project'] = self.project_name
        self.state['project_id'] = self.project_id

        try:
            cluster = CapellaColumnar(self.project, self.name)
            if not cluster.id:
                logger.info(f"Creating Columnar cluster {self.name}")
                builder = CapellaColumnarBuilder(self.provider)
                builder = builder.name(self.name)
                builder = builder.description("Pytest created cluster")
                builder = builder.region(self.region)
                builder = builder.compute(self.machine_type, self.quantity)
                config = builder.build()
                cluster.create(config)
                logger.info("Waiting for cluster creation to complete")
                if not cluster.wait("deploying"):
                    raise CapellaNodeError("Timeout waiting for cluster to deploy")
            else:
                logger.info(f"Columnar cluster {self.name} already exists")

            logger.info(f"Cluster ID: {cluster.id}")

            cluster.refresh()
            self.state['instance_id'] = cluster.id
            self.state['provider'] = cluster.this.cloudProvider
            self.state['region'] = cluster.this.region
            self.state['name'] = cluster.this.name
            self.state['cloud'] = self.cloud

            allowed_cidr = ColumnarAllowedCIDR(cluster, self.allow)
            if not allowed_cidr.id:
                logger.info(f"Configuring allowed CIDR {self.allow}")
                builder = AllowedCIDRBuilder()
                builder.cidr(self.allow)
                config = builder.build()
                allowed_cidr.create(config)
            else:
                logger.info(f"Allow list already set to {self.allow}")
        except Exception as err:
            raise CapellaNodeError(f"Error creating cluster: {err}")

        self.state['allow'] = self.allow

        logger.info("Columnar cluster successfully created")

        self.state['state'] = State.DEPLOYED.value
        return self.state.as_dict

    def peer_cluster(self):
        peer_project = self.peer_project
        if not MetadataManager(peer_project).exists:
            logger.warning(f"Can not peer with project {peer_project}: project does not exist")
            return

        try:
            peer_region = self.peer_region if self.peer_region else self.region
            database = CapellaDatabase(self.project, self.name)
            state_data = MetadataManager(peer_project).get_network_state(self.provider, peer_region)
            parameters = MetadataManager(peer_project).get_network_params(self.provider, peer_region)

            if state_data.get('state') != State.DEPLOYED.value:
                logger.warning(f"Project network is not deployed. Peering aborted.")
                return

            network_peer = CapellaNetworkPeers(database)
            if not network_peer.id:
                if self.provider == "aws":
                    account_id = state_data.get('account_id')
                    vpc_id = state_data.get('vpc_id')
                    vpc_cidr = state_data.get('vpc_cidr')
                    builder = NetworkPeerBuilder()
                    builder.account_id(account_id)
                    builder.vpc_id(vpc_id)
                    builder.region(self.region)
                    builder.cidr(vpc_cidr)
                    config = builder.build()
                    network_peer.create(config)
                elif self.provider == "gcp":
                    gcp_project_name = state_data.get('project_name')
                    network_name = state_data.get('network')
                    network_cidr = state_data.get('network_cidr')
                    service_account = state_data.get('default_service_account')
                    builder = NetworkPeerBuilder()
                    builder.provider_type("gcp")
                    builder.network_name(network_name)
                    builder.cidr(network_cidr)
                    builder.project_id(gcp_project_name)
                    builder.service_account(service_account)
                    config = builder.build()
                    network_peer.create(config)
                elif self.provider == "azure":
                    raise CapellaNodeError(f"Can not peer with project {self.provider}: Azure is currently not supported")
                else:
                    raise CapellaNodeError(f"Can not peer with project {self.provider}: unsupported cloud provider {self.provider}")

            network_peer.refresh()

            self.state['provider_id'] = network_peer.provider_id
            parameters['provider_id'] = self.state['provider_id']
            logger.info(f"Capella peer provider ID: {self.state['provider_id']}")

            if network_peer.hosted_zone_id:
                self.state['aws_hosted_zone'] = network_peer.hosted_zone_id
                parameters['hosted_zone'] = self.state['aws_hosted_zone']
                logger.info(f"Capella AWS hosted zone ID: {self.state['aws_hosted_zone']}")

            if network_peer.peer_project:
                self.state['gcp_peer_project'] = network_peer.peer_project
                parameters['peer_gcp_project'] = self.state['gcp_peer_project']
                logger.info(f"Capella GCP project: {self.state['gcp_peer_project']}")

            if network_peer.peer_network:
                self.state['gcp_peer_network'] = network_peer.peer_network
                parameters['peer_gcp_network'] = self.state['gcp_peer_network']
                logger.info(f"Capella GCP network: {self.state['gcp_peer_network']}")

            if network_peer.managed_zone:
                self.state['gcp_managed_zone'] = network_peer.managed_zone
                parameters['managed_gcp_zone'] = self.state['gcp_managed_zone']
                logger.info(f"Capella GCP managed zone: {self.state['gcp_managed_zone']}")

        except Exception as err:
            raise CapellaNodeError(f"Error peering network: {err}")

        self.state['network_peer_id'] = network_peer.id

        logger.info(f"Network Peer ID: {network_peer.id}")

        logger.info(f"Invoking peer acceptance module for cloud {self.provider}")
        Project.peer_network(self.provider, parameters)
        database.wait("peering")
        logger.info(f"Peering complete")

    def unpeer_project(self):
        peer_project = self.peer_project
        if not MetadataManager(peer_project).exists:
            logger.warning(f"Can not unpeer with project {peer_project}: project does not exist")
            return

        try:
            peer_region = self.peer_region if self.peer_region else self.region
            database = CapellaDatabase(self.project, self.name)
            state_data = MetadataManager(peer_project).get_network_state(self.provider, peer_region)
            parameters = MetadataManager(peer_project).get_network_params(self.provider, peer_region)

            if state_data.get('state') != State.DEPLOYED.value:
                logger.warning(f"Project network is not deployed. Peering removal aborted.")
                return

            network_peer = CapellaNetworkPeers(database)
            if network_peer.id:
                network_peer.refresh()
                logger.info(f"Removing Capella peering {network_peer.name}")
                network_peer.delete()

            if self.state.get('provider_id'):
                parameters['provider_id'] = self.state['provider_id']

            if self.state.get('aws_hosted_zone'):
                parameters['hosted_zone'] = self.state['aws_hosted_zone']

            if self.state.get('gcp_peer_project'):
                parameters['peer_gcp_project'] = self.state['gcp_peer_project']

            if self.state.get('gcp_peer_network'):
                parameters['peer_gcp_network'] = self.state['gcp_peer_network']

            if self.state.get('gcp_managed_zone'):
                parameters['managed_gcp_zone'] = self.state['gcp_managed_zone']

        except Exception as err:
            raise CapellaNodeError(f"Error unpeering network: {err}")

        logger.info(f"Invoking peer removal module for cloud {self.provider}")
        Project.unpeer_network(self.provider, parameters)
        database.wait("peering")
        logger.info(f"Peer removal complete")

    def destroy(self):
        if self.peer_project:
            self.unpeer_project()
        if self.build == "columnar":
            self.destroy_columnar()
        else:
            if self.state.get('type') == "mobile":
                self.destroy_app_svc()
            else:
                self.destroy_database()

    def destroy_app_svc(self):
        try:
            self.state['state'] = State.DESTROYING.value
            app_svc_name = self.state['name']
            cluster_name = self.state['cluster_name']
            database = CapellaDatabase(self.project, cluster_name)
            app_service = CapellaAppService(database)

            if app_service.id:
                logger.info(f"Destroying app service {app_svc_name}")
                app_service.delete()
                if not app_service.wait("destroying"):
                    raise CapellaNodeError("Timeout waiting for app service deletion to complete")
            else:
                logger.info(f"Cluster {cluster_name} does not have associated app services")

            self.state.clear()
            self.state['state'] = State.IDLE.value
        except Exception as err:
            raise CapellaNodeError(f"Error destroying app service: {err}")

    def destroy_database(self):
        try:
            self.state['state'] = State.DESTROYING.value
            cluster_name = self.state['name'] = self.name
            database = CapellaDatabase(self.project, cluster_name)

            if database.id:
                logger.info(f"Destroying cluster {cluster_name}")
                database.delete()
                if not database.wait("destroying"):
                    raise CapellaNodeError("Timeout waiting for cluster deletion to complete")
            else:
                logger.info(f"Database {cluster_name} does not exist")

            self.state.clear()
            self.state['state'] = State.IDLE.value
        except Exception as err:
            raise CapellaNodeError(f"Error destroying database: {err}")

    def destroy_columnar(self):
        try:
            self.state['state'] = State.DESTROYING.value
            cluster = CapellaColumnar(self.project, self.name)

            if cluster.id:
                logger.info(f"Destroying Columnar cluster {self.name}")
                cluster.delete()
                logger.info("Waiting for cluster removal to complete")
                if not cluster.wait("destroying"):
                    raise CapellaNodeError("Timeout waiting for cluster deletion to complete")
            else:
                logger.info(f"Columnar cluster {self.name} does not exist")

            logger.info("Columnar cluster successfully removed")

            self.state.clear()
            self.state['state'] = State.IDLE.value
        except Exception as err:
            raise CapellaNodeError(f"Error destroying cluster: {err}")

    def info(self):
        return self.state.as_dict
