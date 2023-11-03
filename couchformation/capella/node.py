##
##

import logging
from couchformation.exception import FatalError
from couchformation.capella.driver.base import CloudBase
from couchformation.config import get_state_file
from couchformation.kvdb import KeyValueStore


logger = logging.getLogger('couchformation.aws.node')
logger.addHandler(logging.NullHandler())


class AWSNodeError(FatalError):
    pass


class CapellaDeployment(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.name = parameters.get('name')
        self.project = parameters.get('project')
        self.region = parameters.get('region')
        self.number = parameters.get('number')
        self.cloud = parameters.get('cloud')
        self.provider = parameters.get('provider')
        self.machine_type = parameters.get('machine_type')
        self.username = parameters.get('username')
        self.password = parameters.get('password')
        self.cidr = parameters.get('cidr') if parameters.get('cidr') else "10.0.0.0/23"
        self.allow = parameters.get('allow') if parameters.get('allow') else "0.0.0.0/0"
        self.quantity = parameters.get('quantity') if parameters.get('quantity') else 3
        self.volume_size = parameters.get('volume_size') if parameters.get('volume_size') else "256"
        self.services = parameters.get('services') if parameters.get('services') else "data,index,query"
        self.node_name = f"{self.name}-group-{self.number:02d}"

        filename = get_state_file(self.project, self.name)
        document = self.node_name
        self.state = KeyValueStore(filename, document)

        CloudBase(self.parameters).test_session()

        self.project_id = CloudBase(self.parameters).project_id

    def deploy(self):
        if self.state.get('instance_id'):
            logger.info(f"Node {self.node_name} already exists")
            return self.state.as_dict

        self.state['cluster_name'] = self.name
        self.state['cluster_cloud'] = self.cloud
        self.state['cluster_provider'] = self.provider
        self.state['cluster_region'] = self.region
        self.state['cluster_cidr'] = self.cidr
        self.state['cluster_machine'] = self.machine_type
        self.state['cluster_storage'] = self.volume_size
        self.state['cluster_size'] = self.quantity
        self.state['cluster_services'] = self.services.split(',')
        self.state['allow_cidr'] = self.allow
        self.state['username'] = self.username
        self.state['password'] = self.password

        return self.state.as_dict

    def destroy(self):
        pass

    def info(self):
        return self.state.as_dict
