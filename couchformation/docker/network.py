##
##

import logging
from itertools import cycle
from couchformation.network import NetworkDriver
from couchformation.config import get_state_file, get_state_dir
from couchformation.exception import FatalError
from couchformation.util import FileManager
from couchformation.kvdb import KeyValueStore
from couchformation.docker.driver.network import Network

logger = logging.getLogger('couchformation.docker.network')
logger.addHandler(logging.NullHandler())
logging.getLogger("docker").setLevel(logging.WARNING)


class DockerNetworkError(FatalError):
    pass


class DockerNetwork(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.name = parameters.get('name')
        self.project = parameters.get('project')
        self.cloud = parameters.get('cloud')

        filename = get_state_file(self.project, 'common')

        try:
            state_dir = get_state_dir(self.project, 'common')
            FileManager().make_dir(state_dir)
        except Exception as err:
            raise DockerNetworkError(f"can not create state dir: {err}")

        document = f"network:{self.cloud}"
        self.state = KeyValueStore(filename, document)

        self.docker_network = Network(self.parameters)

    def check_state(self):
        if self.state.get('network'):
            network = Network(self.parameters).get_network(self.state.get('network'))
            if network is None:
                logger.warning(f"Removing stale state entry for network {self.state.get('network')}")
                del self.state['network']

    def create_vpc(self):
        self.check_state()
        cidr_util = NetworkDriver()
        net_name = f"{self.project}-net"

        for net in self.docker_network.cidr_list:
            cidr_util.add_network(net)

        try:

            if not self.state.get('network'):
                cidr_util.get_next_network()
                subnet_list = list(cidr_util.get_next_subnet())
                subnet_cycle = cycle(subnet_list[1:])
                subnet_cidr = next(subnet_cycle)
                Network(self.parameters).create(net_name, subnet_cidr)
                self.state['network'] = net_name
                self.state['network_cidr'] = subnet_cidr
                logger.info(f"Created network {net_name}")

        except Exception as err:
            raise DockerNetworkError(f"Error creating network: {err}")

    def destroy_vpc(self):
        if self.state.list_len('services') > 0:
            logger.info(f"Active services, leaving project network in place")
            return

        try:
            if self.state.get('network'):
                net_name = self.state.get('network')
                Network(self.parameters).delete(net_name)
                del self.state['network']
                del self.state['network_cidr']
                logger.info(f"Removed network {net_name}")

        except Exception as err:
            raise DockerNetworkError(f"Error removing network: {err}")

    def create(self):
        logger.info(f"Creating docker network for {self.project}")
        self.create_vpc()

    def destroy(self):
        logger.info(f"Removing docker network for {self.project}")
        self.destroy_vpc()

    def get(self, key):
        return self.state.get(key)

    @property
    def network(self):
        return self.state.get('network')

    def add_service(self, name):
        self.state.list_add('services', name)

    def remove_service(self, name):
        self.state.list_remove('services', name)
