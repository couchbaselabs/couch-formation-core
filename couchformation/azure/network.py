##
##

import logging
import attr
from itertools import cycle
from couchformation.network import NetworkDriver
from couchformation.azure.driver.network import Network, Subnet, SecurityGroup
from couchformation.azure.driver.base import CloudBase
import couchformation.azure.driver.constants as C
from couchformation.config import BaseConfig
from couchformation.exception import FatalError
import couchformation.state as state
from couchformation.state import INFRASTRUCTURE, AzureZone
from couchformation.deployment import Service

logger = logging.getLogger('couchformation.azure.network')
logger.addHandler(logging.NullHandler())


class AzureNetworkError(FatalError):
    pass


class AzureNetwork(object):

    def __init__(self, name: str, core: BaseConfig, service: Service):
        self.name = name
        self.service = service
        self.core = core
        self.project = core.project
        self.region = service.region
        self.auth_mode = service.auth
        self.profile = service.profile

        state.config.set(name, service.cloud, core.project_dir)
        state.switch_cloud()

        try:
            self.validate()
        except ValueError as err:
            raise AzureNetworkError(err)

        self.az_network = Network(service)
        self.az_base = CloudBase(service)

    def create_vpc(self):
        service = self.service
        core = self.core
        cidr_util = NetworkDriver()
        rg_name = f"{core.project}-rg"
        vpc_name = f"{core.project}-vpc"
        nsg_name = f"{core.project}-nsg"
        subnet_name = f"{core.project}-subnet-01"

        for net in self.az_network.cidr_list:
            cidr_util.add_network(net)

        zone_list = self.az_network.zones()
        azure_location = self.az_base.region

        state.update(INFRASTRUCTURE)

        try:

            if not state.infrastructure.resource_group:
                self.az_base.create_rg(rg_name, azure_location)
                state.infrastructure.resource_group = rg_name
                logger.info(f"Created resource group {rg_name}")
            else:
                rg_name = state.infrastructure.resource_group

            if not state.infrastructure.network:
                vpc_cidr = cidr_util.get_next_network()
                net_resource = Network(service).create(vpc_name, vpc_cidr, rg_name)
                net_resource_id = net_resource.id
                state.infrastructure.network = vpc_name
                state.infrastructure.network_cidr = vpc_cidr
                state.infrastructure.network_id = net_resource_id
                logger.info(f"Created network {vpc_name}")
            else:
                vpc_name = state.infrastructure.network
                vpc_cidr = state.infrastructure.network_cidr
                cidr_util.set_active_network(vpc_cidr)

            if not state.infrastructure.network_security_group:
                nsg_resource = SecurityGroup(service).create(nsg_name, rg_name)
                nsg_resource_id = nsg_resource.id
                SecurityGroup(service).add_rule("AllowSSH", nsg_name, ["22"], 100, rg_name)
                SecurityGroup(service).add_rule("AllowCB", nsg_name, [
                    "8091-8097",
                    "9123",
                    "9140",
                    "11210",
                    "11280",
                    "11207",
                    "18091-18097",
                    "4984-4986"
                ], 101, rg_name)
                state.infrastructure.network_security_group = nsg_name
                state.infrastructure.network_security_group_id = nsg_resource_id
            else:
                nsg_resource_id = state.infrastructure.network_security_group_id

            subnet_list = list(cidr_util.get_next_subnet())
            subnet_cycle = cycle(subnet_list[1:])

            if not state.infrastructure.subnet_cidr:
                subnet_cidr = next(subnet_cycle)
                state.infrastructure.subnet_cidr = subnet_cidr
            else:
                subnet_cidr = state.infrastructure.subnet_cidr

            if not state.infrastructure.subnet:
                subnet_resource = Subnet(service).create(subnet_name, vpc_name, subnet_cidr, nsg_resource_id, rg_name)
                subnet_id = subnet_resource.id
                state.infrastructure.subnet = subnet_name
                state.infrastructure.subnet_id = subnet_id
            else:
                subnet_id = state.infrastructure.subnet_id
                subnet_name = state.infrastructure.subnet

            for n, zone in enumerate(zone_list):
                if next((z for z in state.infrastructure.zone_list if z['zone'] == zone), None):
                    continue
                zone_state = AzureZone()
                zone_state.zone = zone
                zone_state.subnet = subnet_name
                zone_state.subnet_id = subnet_id
                # noinspection PyTypeChecker
                state.infrastructure.zone_list.append(attr.asdict(zone_state))
                logger.info(f"Added zone {zone}")

        except Exception as err:
            raise AzureNetworkError(f"Error creating network: {err}")

        state.save()

    def destroy_vpc(self):
        service = self.service

        state.update(INFRASTRUCTURE)

        try:

            if state.infrastructure.resource_group:
                rg_name = state.infrastructure.resource_group
            else:
                logger.warning("No saved resource group")
                return

            if state.infrastructure.network:
                vpc_name = state.infrastructure.network
            else:
                logger.warning("No saved network")
                return

            if state.infrastructure.subnet:
                subnet_name = state.infrastructure.subnet
                Subnet(service).delete(vpc_name, subnet_name, rg_name)
                state.infrastructure.subnet = None
                state.infrastructure.subnet_id = None
                logger.info(f"Removed subnet {subnet_name}")

            if state.infrastructure.subnet_cidr:
                state.infrastructure.subnet_cidr = None

            if state.infrastructure.network_security_group:
                nsg_name = state.infrastructure.network_security_group
                SecurityGroup(service).delete(nsg_name, rg_name)
                state.infrastructure.network_security_group = None
                state.infrastructure.network_security_group_id = None
                logger.info(f"Removed network security group {nsg_name}")

            for n, zone_state in reversed(list(enumerate(state.infrastructure.zone_list))):
                del state.infrastructure.zone_list[n]

            if state.infrastructure.network:
                vpc_name = state.infrastructure.network
                Network(service).delete(vpc_name, rg_name)
                state.infrastructure.network = None
                state.infrastructure.network_cidr = None
                state.infrastructure.network_id = None
                logger.info(f"Removed network {vpc_name}")

            if state.infrastructure.resource_group:
                rg_name = state.infrastructure.resource_group
                self.az_base.delete_rg(rg_name)
                state.infrastructure.resource_group = None
                logger.info(f"Removed resource group {rg_name}")

        except Exception as err:
            raise AzureNetworkError(f"Error removing network: {err}")

        state.save()

    def create(self):
        logger.info(f"Creating cloud network for {self.project} in {C.CLOUD_KEY.upper()}")
        self.create_vpc()

    def destroy(self):
        logger.info(f"Removing cloud network for {self.project} in {C.CLOUD_KEY.upper()}")
        self.destroy_vpc()

    @staticmethod
    def output():
        state.infrastructure_display()

    def validate(self):
        variables = [a for a in dir(self) if not callable(getattr(self, a)) and not a.startswith("__")]
        for variable in variables:
            if getattr(self, variable) is None:
                raise ValueError(f"setting \"{variable}\" is null")
