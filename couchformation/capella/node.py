##
##

import logging
from couchformation.exception import FatalError
from couchformation.capella.driver.base import CloudBase
from couchformation.config import get_state_file
from couchformation.kvdb import KeyValueStore


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
        self.username = parameters.get('username')
        self.password = parameters.get('password')
        self.cidr = parameters.get('cidr') if parameters.get('cidr') else "10.0.0.0/23"
        self.allow = parameters.get('allow') if parameters.get('allow') else "0.0.0.0/0"
        self.db_name = f"{self.name}-database"

        self.state_file = get_state_file(self.project, self.name)
        document = self.db_name
        self.state = KeyValueStore(self.state_file, document)

        CloudBase(self.parameters).test_session()

        self.project_id = CloudBase(self.parameters).project_id

    def compose(self, parameters: dict):
        number = parameters.get('number') if parameters.get('number') else 1
        document = f"{self.name}-node-group-{number:02d}"
        group = KeyValueStore(self.state_file, document)

        group['cloud'] = parameters.get('cloud')
        group['machine_type'] = parameters.get('machine_type')
        group['volume_size'] = parameters.get('volume_size') if parameters.get('volume_size') else "256"
        group['quantity'] = parameters.get('quantity') if parameters.get('quantity') else 3
        group['services'] = parameters.get('services') if parameters.get('services') else "data,index,query"

    def deploy(self):
        if self.state.get('instance_id'):
            logger.info(f"Database {self.db_name} already exists")
            return self.state.as_dict

        # self.state['instance_id'] = self.name
        # self.state['cloud'] = self.cloud
        # self.state['provider'] = self.provider
        # self.state['region'] = self.region
        # self.state['cidr'] = self.cidr
        # self.state['allow'] = self.allow
        # self.state['username'] = self.username
        # self.state['password'] = self.password

        return self.state.as_dict

    def destroy(self):
        pass

    def info(self):
        return self.state.as_dict
