##
##

import attr
import logging
from itertools import cycle
from couchformation.network import NetworkDriver
from couchformation.gcp.driver.network import Network, Subnet
from couchformation.gcp.driver.firewall import Firewall
from couchformation.gcp.driver.base import CloudBase
import couchformation.gcp.driver.constants as C
from couchformation.config import BaseConfig
from couchformation.exception import FatalError
import couchformation.state as state
from couchformation.state import INFRASTRUCTURE, GCPZone

logger = logging.getLogger('couchformation.gcp.network')
logger.addHandler(logging.NullHandler())


class GCPNetworkError(FatalError):
    pass


class GCPNetwork(object):

    def __init__(self, core: BaseConfig):
        self.core = core
        self.project = core.project
        self.region = core.region
        self.auth_mode = core.auth
        self.profile = core.profile
        core.common_mode()

        state.core = self.core
        state.switch_cloud()

        try:
            self.validate()
        except ValueError as err:
            raise GCPNetworkError(err)

        self.gcp_network = Network(core)
        self.gcp_base = CloudBase(core)

    def create_vpc(self):
        core = self.core
        cidr_util = NetworkDriver()
        vpc_name = f"{core.project}-vpc"
        subnet_name = f"{core.project}-subnet-01"
        firewall_default = f"{vpc_name}-fw-default"
        firewall_cbs = f"{vpc_name}-fw-cbs"
        firewall_ssh = f"{vpc_name}-fw-ssh"

        for net in self.gcp_network.cidr_list:
            cidr_util.add_network(net)

        zone_list = self.gcp_network.zones()

        state.update(INFRASTRUCTURE)

        try:

            if not state.infrastructure.network:
                vpc_cidr = cidr_util.get_next_network()
                Network(core).create(vpc_name)
                state.infrastructure.network = vpc_name
                state.infrastructure.network_cidr = vpc_cidr
                logger.info(f"Created network {vpc_name}")
            else:
                vpc_name = state.infrastructure.network
                vpc_cidr = state.infrastructure.network_cidr
                cidr_util.set_active_network(vpc_cidr)

            subnet_list = list(cidr_util.get_next_subnet())
            subnet_cycle = cycle(subnet_list[1:])

            if not state.infrastructure.subnet_cidr:
                subnet_cidr = next(subnet_cycle)
            else:
                subnet_cidr = state.infrastructure.subnet_cidr

            if not state.infrastructure.subnet:
                Subnet(core).create(subnet_name, vpc_name, subnet_cidr)
                state.infrastructure.subnet = subnet_name
                logger.info(f"Created subnet {subnet_name}")

            if not state.infrastructure.firewall_default:
                Firewall(core).create_ingress(firewall_default, vpc_name, vpc_cidr, "all")
                state.infrastructure.firewall_default = firewall_default
                logger.info(f"Created firewall rule {firewall_default}")

            if not state.infrastructure.firewall_cbs:
                Firewall(core).create_ingress(firewall_cbs, vpc_name, "0.0.0.0/0", "tcp", [
                    "8091-8097",
                    "9123",
                    "9140",
                    "11210",
                    "11280",
                    "11207",
                    "18091-18097",
                    "4984-4986"
                ])
                state.infrastructure.firewall_cbs = firewall_cbs
                logger.info(f"Created firewall rule {firewall_cbs}")

            if not state.infrastructure.firewall_ssh:
                Firewall(core).create_ingress(firewall_ssh, vpc_name, "0.0.0.0/0", "tcp", ["22"])
                state.infrastructure.firewall_ssh = firewall_ssh
                logger.info(f"Created firewall rule {firewall_ssh}")

            for n, zone in enumerate(zone_list):
                if next((z for z in state.infrastructure.zone_list if z['zone'] == zone), None):
                    continue
                zone_state = GCPZone()
                zone_state.zone = zone
                zone_state.subnet = subnet_name
                # noinspection PyTypeChecker
                state.infrastructure.zone_list.append(attr.asdict(zone_state))
                logger.info(f"Added zone {zone}")

        except Exception as err:
            raise GCPNetworkError(f"Error creating network: {err}")

        state.save()

    def destroy_vpc(self):
        core = self.core

        state.update(INFRASTRUCTURE)

        try:

            if state.infrastructure.firewall_ssh:
                firewall_ssh = state.infrastructure.firewall_ssh
                Firewall(core).delete(firewall_ssh)
                state.infrastructure.firewall_ssh = None
                logger.info(f"Removed firewall rule {firewall_ssh}")

            if state.infrastructure.firewall_cbs:
                firewall_cbs = state.infrastructure.firewall_cbs
                Firewall(core).delete(firewall_cbs)
                state.infrastructure.firewall_cbs = None
                logger.info(f"Removed firewall rule {firewall_cbs}")

            if state.infrastructure.firewall_default:
                firewall_default = state.infrastructure.firewall_default
                Firewall(core).delete(firewall_default)
                state.infrastructure.firewall_default = None
                logger.info(f"Removed firewall rule {firewall_default}")

            if state.infrastructure.subnet:
                subnet_name = state.infrastructure.subnet
                Subnet(core).delete(subnet_name)
                state.infrastructure.subnet = None
                logger.info(f"Removed subnet {subnet_name}")

            if state.infrastructure.subnet_cidr:
                state.infrastructure.subnet_cidr = None

            for n, zone_state in reversed(list(enumerate(state.infrastructure.zone_list))):
                del state.infrastructure.zone_list[n]

            if state.infrastructure.network:
                vpc_name = state.infrastructure.network
                Network(core).delete(vpc_name)
                state.infrastructure.network = None
                state.infrastructure.network_cidr = None
                logger.info(f"Removed network {vpc_name}")

        except Exception as err:
            raise GCPNetworkError(f"Error removing network: {err}")

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
