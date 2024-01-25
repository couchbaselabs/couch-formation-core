##
##

import os
import logging
from itertools import cycle
from couchformation.network import NetworkDriver
from couchformation.azure.driver.network import Network, Subnet, SecurityGroup
from couchformation.azure.driver.base import CloudBase
import couchformation.azure.driver.constants as C
from couchformation.config import get_state_file, get_state_dir
from couchformation.exception import FatalError
from couchformation.kvdb import KeyValueStore
from couchformation.util import FileManager


logger = logging.getLogger('couchformation.azure.network')
logger.addHandler(logging.NullHandler())


class AzureNetworkError(FatalError):
    pass


class AzureNetwork(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.name = parameters.get('name')
        self.project = parameters.get('project')
        self.region = parameters.get('region')
        self.auth_mode = parameters.get('auth_mode')
        self.profile = parameters.get('profile')
        self.ssh_key = parameters.get('ssh_key')
        self.cloud = parameters.get('cloud')

        filename = get_state_file(self.project, f"network-{self.region}")

        try:
            state_dir = get_state_dir(self.project, f"network-{self.region}")
            if not os.path.exists(state_dir):
                FileManager().make_dir(state_dir)
        except Exception as err:
            raise AzureNetworkError(f"can not create state dir: {err}")

        document = f"network:{self.cloud}"
        self.state = KeyValueStore(filename, document)

        self.az_network = Network(self.parameters)
        self.az_base = CloudBase(self.parameters)

        self.rg_name = f"{self.project}-rg"
        self.vpc_name = f"{self.project}-vpc"
        self.nsg_name = f"{self.project}-nsg"
        self.subnet_name = f"{self.project}-subnet-01"

    def check_state(self):
        if self.state.get('resource_group'):
            rg_name = self.state.get('resource_group')
        else:
            rg_name = self.rg_name

        if self.state.get('network'):
            vpc_name = self.state.get('network')
        else:
            vpc_name = self.vpc_name

        if self.state.get('subnet'):
            result = Subnet(self.parameters).details(vpc_name, self.state['subnet'], rg_name)
            if result is None:
                logger.warning(f"Removing stale state entry for subnet {self.state['subnet']}")
                del self.state['subnet']
                del self.state['subnet_id']
                del self.state['subnet_cidr']
        if self.state.get('network_security_group'):
            result = SecurityGroup(self.parameters).details(self.state['network_security_group'], rg_name)
            if result is None:
                logger.warning(f"Removing stale state entry for security group {self.state['network_security_group']}")
                del self.state['network_security_group']
                del self.state['network_security_group_id']
        if self.state.get('network'):
            result = Network(self.parameters).details(self.state['network'], rg_name)
            if result is None:
                logger.warning(f"Removing stale state entry for network {self.state['network']}")
                del self.state['network']
                del self.state['network_cidr']
                del self.state['network_id']
        if self.state.get('resource_group'):
            result = self.az_base.get_rg(self.state['resource_group'], self.az_base.region)
            if result is None:
                logger.warning(f"Removing stale state entry for resource group {self.state['resource_group']}")
                del self.state['resource_group']
                del self.state['zone']

    def create_vpc(self):
        self.check_state()
        cidr_util = NetworkDriver()

        for net in self.az_network.cidr_list:
            cidr_util.add_network(net)

        zone_list = self.az_network.zones()
        azure_location = self.az_base.region

        try:

            if not self.state.get('resource_group'):
                self.az_base.create_rg(self.rg_name, azure_location)
                self.state['resource_group'] = self.rg_name
                logger.info(f"Created resource group {self.rg_name}")
            else:
                self.rg_name = self.state['resource_group']

            if not self.state.get('network'):
                vpc_cidr = cidr_util.get_next_network()
                net_resource = Network(self.parameters).create(self.vpc_name, vpc_cidr, self.rg_name)
                net_resource_id = net_resource.id
                self.state['network'] = self.vpc_name
                self.state['network_cidr'] = vpc_cidr
                self.state['network_id'] = net_resource_id
                logger.info(f"Created network {self.vpc_name}")
            else:
                self.vpc_name = self.state['network']
                vpc_cidr = self.state['network_cidr']
                cidr_util.set_active_network(vpc_cidr)

            if not self.state.get('network_security_group'):
                nsg_resource = SecurityGroup(self.parameters).create(self.nsg_name, self.rg_name)
                nsg_resource_id = nsg_resource.id
                SecurityGroup(self.parameters).add_rule("AllowSSH", self.nsg_name, ["22"], 100, self.rg_name)
                SecurityGroup(self.parameters).add_rule("AllowRDP", self.nsg_name, ["3389"], 101, self.rg_name)
                SecurityGroup(self.parameters).add_rule("AllowCB", self.nsg_name, [
                    "8091-8097",
                    "9123",
                    "9140",
                    "11210",
                    "11280",
                    "11207",
                    "18091-18097",
                    "4984-4986"
                ], 102, self.rg_name)
                self.state['network_security_group'] = self.nsg_name
                self.state['network_security_group_id'] = nsg_resource_id
            else:
                nsg_resource_id = self.state['network_security_group_id']

            subnet_list = list(cidr_util.get_next_subnet())
            subnet_cycle = cycle(subnet_list[1:])

            if not self.state.get('subnet_cidr'):
                subnet_cidr = next(subnet_cycle)
                self.state['subnet_cidr'] = subnet_cidr
            else:
                subnet_cidr = self.state['subnet_cidr']

            if not self.state.get('subnet'):
                subnet_resource = Subnet(self.parameters).create(self.subnet_name, self.vpc_name, subnet_cidr, nsg_resource_id, self.rg_name)
                subnet_id = subnet_resource.id
                self.state['subnet'] = self.subnet_name
                self.state['subnet_id'] = subnet_id
            else:
                subnet_id = self.state['subnet_id']
                self.subnet_name = self.state['subnet']

            for n, zone in enumerate(zone_list):
                if self.state.list_exists('zone', zone):
                    continue
                self.state.list_add('zone', zone, self.subnet_name, subnet_id)
                logger.info(f"Added zone {zone}")

        except Exception as err:
            raise AzureNetworkError(f"Error creating network: {err}")

    def destroy_vpc(self):
        if self.state.list_len('services') > 0:
            logger.info(f"Active services, leaving project network in place")
            return

        try:

            if self.state.get('resource_group'):
                rg_name = self.state.get('resource_group')
            else:
                logger.warning("No saved resource group")
                return

            if self.state.get('network'):
                vpc_name = self.state.get('network')
            else:
                logger.warning("No saved network")
                return

            if self.state.get('subnet'):
                subnet_name = self.state.get('subnet')
                Subnet(self.parameters).delete(vpc_name, subnet_name, rg_name)
                del self.state['subnet']
                del self.state['subnet_id']
                logger.info(f"Removed subnet {subnet_name}")

            if self.state.get('subnet_cidr'):
                del self.state['subnet_cidr']

            if self.state.get('network_security_group'):
                nsg_name = self.state.get('network_security_group')
                SecurityGroup(self.parameters).delete(nsg_name, rg_name)
                del self.state['network_security_group']
                del self.state['network_security_group_id']
                logger.info(f"Removed network security group {nsg_name}")

            for n, zone_state in reversed(list(enumerate(self.state.list_get('zone')))):
                self.state.list_remove('zone', zone_state[0])

            if self.state.get('network'):
                vpc_name = self.state.get('network')
                Network(self.parameters).delete(vpc_name, rg_name)
                del self.state['network']
                del self.state['network_cidr']
                del self.state['network_id']
                logger.info(f"Removed network {vpc_name}")

            if self.state.get('resource_group'):
                rg_name = self.state.get('resource_group')
                self.az_base.delete_rg(rg_name)
                del self.state['resource_group']
                logger.info(f"Removed resource group {rg_name}")

        except Exception as err:
            raise AzureNetworkError(f"Error removing network: {err}")

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
    def resource_group(self):
        return self.state.get('resource_group')

    @property
    def zones(self):
        return self.state.list_get('zone')

    def add_service(self, name):
        self.state.list_add('services', name)

    def remove_service(self, name):
        self.state.list_remove('services', name)
