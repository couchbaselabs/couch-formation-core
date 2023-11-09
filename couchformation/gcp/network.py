##
##

import logging
from itertools import cycle
from couchformation.network import NetworkDriver
from couchformation.gcp.driver.network import Network, Subnet
from couchformation.gcp.driver.firewall import Firewall
from couchformation.gcp.driver.base import CloudBase
import couchformation.gcp.driver.constants as C
from couchformation.config import get_state_file, get_state_dir
from couchformation.exception import FatalError
from couchformation.kvdb import KeyValueStore
from couchformation.util import FileManager


logger = logging.getLogger('couchformation.gcp.network')
logger.addHandler(logging.NullHandler())


class GCPNetworkError(FatalError):
    pass


class GCPNetwork(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.name = parameters.get('name')
        self.project = parameters.get('project')
        self.region = parameters.get('region')
        self.auth_mode = parameters.get('auth_mode')
        self.profile = parameters.get('profile')
        self.ssh_key = parameters.get('ssh_key')
        self.cloud = parameters.get('cloud')

        filename = get_state_file(self.project, 'common')

        try:
            state_dir = get_state_dir(self.project, 'common')
            FileManager().make_dir(state_dir)
        except Exception as err:
            raise GCPNetworkError(f"can not create state dir: {err}")

        document = f"network:{self.cloud}"
        self.state = KeyValueStore(filename, document)

        self.gcp_network = Network(self.parameters)
        self.gcp_base = CloudBase(self.parameters)

    def create_vpc(self):
        cidr_util = NetworkDriver()
        vpc_name = f"{self.project}-vpc"
        subnet_name = f"{self.project}-subnet-01"
        firewall_default = f"{vpc_name}-fw-default"
        firewall_cbs = f"{vpc_name}-fw-cbs"
        firewall_ssh = f"{vpc_name}-fw-ssh"

        for net in self.gcp_network.cidr_list:
            cidr_util.add_network(net)

        zone_list = self.gcp_network.zones()

        try:

            if not self.state.get('network'):
                vpc_cidr = cidr_util.get_next_network()
                Network(self.parameters).create(vpc_name)
                self.state['network'] = vpc_name
                self.state['network_cidr'] = vpc_cidr
                logger.info(f"Created network {vpc_name}")
            else:
                vpc_name = self.state['network']
                vpc_cidr = self.state['network_cidr']
                cidr_util.set_active_network(vpc_cidr)

            subnet_list = list(cidr_util.get_next_subnet())
            subnet_cycle = cycle(subnet_list[1:])

            if not self.state.get('subnet_cidr'):
                subnet_cidr = next(subnet_cycle)
                self.state['subnet_cidr'] = subnet_cidr
            else:
                subnet_cidr = self.state['subnet_cidr']

            if not self.state.get('subnet'):
                Subnet(self.parameters).create(subnet_name, vpc_name, subnet_cidr)
                self.state['subnet'] = subnet_name
                logger.info(f"Created subnet {subnet_name}")

            if not self.state.get('firewall_default'):
                Firewall(self.parameters).create_ingress(firewall_default, vpc_name, vpc_cidr, "all")
                self.state['firewall_default'] = firewall_default
                logger.info(f"Created firewall rule {firewall_default}")

            if not self.state.get('firewall_cbs'):
                Firewall(self.parameters).create_ingress(firewall_cbs, vpc_name, "0.0.0.0/0", "tcp", [
                    "8091-8097",
                    "9123",
                    "9140",
                    "11210",
                    "11280",
                    "11207",
                    "18091-18097",
                    "4984-4986"
                ])
                self.state['firewall_cbs'] = firewall_cbs
                logger.info(f"Created firewall rule {firewall_cbs}")

            if not self.state.get('firewall_ssh'):
                Firewall(self.parameters).create_ingress(firewall_ssh, vpc_name, "0.0.0.0/0", "tcp", ["22"])
                self.state['firewall_ssh'] = firewall_ssh
                logger.info(f"Created firewall rule {firewall_ssh}")

            for n, zone in enumerate(zone_list):
                if self.state.list_exists('zone', zone):
                    continue
                self.state.list_add('zone', zone, subnet_name)
                logger.info(f"Added zone {zone}")

        except Exception as err:
            raise GCPNetworkError(f"Error creating network: {err}")

    def destroy_vpc(self):
        if self.state.list_len('services') > 0:
            logger.info(f"Active services, leaving project network in place")
            return

        try:

            if self.state.get('firewall_ssh'):
                firewall_ssh = self.state.get('firewall_ssh')
                Firewall(self.parameters).delete(firewall_ssh)
                del self.state['firewall_ssh']
                logger.info(f"Removed firewall rule {firewall_ssh}")

            if self.state.get('firewall_cbs'):
                firewall_cbs = self.state.get('firewall_cbs')
                Firewall(self.parameters).delete(firewall_cbs)
                del self.state['firewall_cbs']
                logger.info(f"Removed firewall rule {firewall_cbs}")

            if self.state.get('firewall_default'):
                firewall_default = self.state.get('firewall_default')
                Firewall(self.parameters).delete(firewall_default)
                del self.state['firewall_default']
                logger.info(f"Removed firewall rule {firewall_default}")

            if self.state.get('subnet'):
                subnet_name = self.state.get('subnet')
                Subnet(self.parameters).delete(subnet_name)
                del self.state['subnet']
                logger.info(f"Removed subnet {subnet_name}")

            if self.state.get('subnet_cidr'):
                del self.state['subnet_cidr']

            for n, zone_state in reversed(list(enumerate(self.state.list_get('zone')))):
                self.state.list_remove('zone', zone_state[0])

            if self.state.get('network'):
                vpc_name = self.state.get('network')
                Network(self.parameters).delete(vpc_name)
                del self.state['network']
                del self.state['network_cidr']
                logger.info(f"Removed network {vpc_name}")

        except Exception as err:
            raise GCPNetworkError(f"Error removing network: {err}")

    def create(self):
        logger.info(f"Creating cloud network for {self.project} in {C.CLOUD_KEY.upper()}")
        self.create_vpc()

    def destroy(self):
        logger.info(f"Removing cloud network for {self.project} in {C.CLOUD_KEY.upper()}")
        self.destroy_vpc()

    def get(self, key):
        return self.state.get(key)

    @property
    def network(self):
        return self.state.get('network')

    @property
    def subnet(self):
        return self.state.get('subnet')

    @property
    def zones(self):
        return self.state.list_get('zone')

    def add_service(self, name):
        self.state.list_add('services', name)

    def remove_service(self, name):
        self.state.list_remove('services', name)
