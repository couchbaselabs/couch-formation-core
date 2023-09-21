##
##

import logging
from itertools import cycle
import attr
from couchformation.network import NetworkDriver
from couchformation.aws.driver.network import Network, Subnet
from couchformation.aws.driver.sshkey import SSHKey
from couchformation.aws.driver.gateway import InternetGateway
from couchformation.aws.driver.nsg import SecurityGroup
from couchformation.aws.driver.route import RouteTable
import couchformation.aws.driver.constants as C
from couchformation.config import BaseConfig
from couchformation.ssh import SSHUtil
import couchformation.state as state
from couchformation.state import INFRASTRUCTURE, AWSZone
from couchformation.exception import FatalError
from couchformation.deployment import Service

logger = logging.getLogger('couchformation.aws.network')
logger.addHandler(logging.NullHandler())


class AWSNetworkError(FatalError):
    pass


class AWSNetwork(object):

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
            raise AWSNetworkError(err)

        self.aws_network = Network(service)

    def create_vpc(self):
        service = self.service
        core = self.core
        cidr_util = NetworkDriver()
        vpc_name = f"{self.project}-vpc"
        ig_name = f"{self.project}-gw"
        rt_name = f"{self.project}-rt"
        sg_name = f"{self.project}-sg"
        key_name = f"{self.project}-key"

        for net in self.aws_network.cidr_list:
            cidr_util.add_network(net)

        zone_list = self.aws_network.zones()

        state.update(INFRASTRUCTURE)

        ssh_pub_key_text = SSHUtil().get_ssh_public_key(core.ssh_key)

        try:

            if not state.infrastructure.vpc_id:
                vpc_cidr = cidr_util.get_next_network()
                vpc_id = Network(service).create(vpc_name, vpc_cidr)
                state.infrastructure.vpc_id = vpc_id
                state.infrastructure.vpc_cidr = vpc_cidr
                logger.info(f"Created VPC {vpc_id}")
            else:
                vpc_id = state.infrastructure.vpc_id
                vpc_cidr = state.infrastructure.vpc_cidr
                cidr_util.set_active_network(vpc_cidr)

            subnet_list = list(cidr_util.get_next_subnet())
            subnet_cycle = cycle(subnet_list[1:])

            if not state.infrastructure.security_group_id:
                sg_id = SecurityGroup(service).create(sg_name, f"Couch Formation project {self.profile}", vpc_id)
                SecurityGroup(service).add_ingress(sg_id, "-1", 0, 0, vpc_cidr)
                SecurityGroup(service).add_ingress(sg_id, "tcp", 22, 22, "0.0.0.0/0")
                SecurityGroup(service).add_ingress(sg_id, "tcp", 8091, 8097, "0.0.0.0/0")
                SecurityGroup(service).add_ingress(sg_id, "tcp", 9123, 9123, "0.0.0.0/0")
                SecurityGroup(service).add_ingress(sg_id, "tcp", 9140, 9140, "0.0.0.0/0")
                SecurityGroup(service).add_ingress(sg_id, "tcp", 11210, 11210, "0.0.0.0/0")
                SecurityGroup(service).add_ingress(sg_id, "tcp", 11280, 11280, "0.0.0.0/0")
                SecurityGroup(service).add_ingress(sg_id, "tcp", 11207, 11207, "0.0.0.0/0")
                SecurityGroup(service).add_ingress(sg_id, "tcp", 18091, 18097, "0.0.0.0/0")
                SecurityGroup(service).add_ingress(sg_id, "tcp", 4984, 4986, "0.0.0.0/0")
                state.infrastructure.security_group_id = sg_id
                logger.info(f"Created security group {sg_id}")

            if not state.infrastructure.ssh_key:
                ssh_key_name = SSHKey(service).create(key_name, ssh_pub_key_text)
                state.infrastructure.ssh_key = ssh_key_name
                logger.info(f"Created SSH Key {ssh_key_name}")

            if not state.infrastructure.internet_gateway_id:
                ig_id = InternetGateway(service).create(ig_name, vpc_id)
                state.infrastructure.internet_gateway_id = ig_id
                logger.info(f"Created internet gateway {ig_id}")
            else:
                ig_id = state.infrastructure.internet_gateway_id

            if not state.infrastructure.route_table_id:
                rt_id = RouteTable(service).create(rt_name, vpc_id)
                state.infrastructure.route_table_id = rt_id
                RouteTable(service).add_route("0.0.0.0/0", ig_id, rt_id)
                logger.info(f"Created route table {rt_id}")
            else:
                rt_id = state.infrastructure.route_table_id

            for n, zone in enumerate(zone_list):
                if next((z for z in state.infrastructure.zone_list if z['zone'] == zone), None):
                    continue
                while True:
                    network_cidr = next(subnet_cycle)
                    if not next((z for z in state.infrastructure.zone_list if z['cidr'] == network_cidr), None):
                        break
                zone_state = AWSZone()
                zone_state.zone = zone
                subnet_name = f"{self.project}-subnet-{n+1:02d}"
                subnet_id = Subnet(service).create(subnet_name, vpc_id, zone, network_cidr)
                RouteTable(service).associate(rt_id, subnet_id)
                zone_state.subnet_id = subnet_id
                zone_state.cidr = network_cidr
                # noinspection PyTypeChecker
                state.infrastructure.zone_list.append(attr.asdict(zone_state))
                logger.info(f"Created subnet {subnet_id} in zone {zone}")

        except Exception as err:
            raise AWSNetworkError(f"Error creating VPC: {err}")

        state.save()

    def destroy_vpc(self):
        service = self.service

        state.update(INFRASTRUCTURE)

        try:

            for n, zone_state in reversed(list(enumerate(state.infrastructure.zone_list))):
                subnet_id = zone_state['subnet_id']
                Subnet(service).delete(subnet_id)
                del state.infrastructure.zone_list[n]
                logger.info(f"Removed subnet {subnet_id}")

            if state.infrastructure.route_table_id:
                rt_id = state.infrastructure.route_table_id
                RouteTable(service).delete(rt_id)
                state.infrastructure.route_table_id = None
                logger.info(f"Removed route table {rt_id}")

            if state.infrastructure.internet_gateway_id:
                ig_id = state.infrastructure.internet_gateway_id
                InternetGateway(service).delete(ig_id)
                state.infrastructure.internet_gateway_id = None
                logger.info(f"Removing internet gateway {ig_id}")

            if state.infrastructure.security_group_id:
                sg_id = state.infrastructure.security_group_id
                SecurityGroup(service).delete(sg_id)
                state.infrastructure.security_group_id = None
                logger.info(f"Removing security group {sg_id}")

            if state.infrastructure.vpc_id:
                vpc_id = state.infrastructure.vpc_id
                Network(service).delete(vpc_id)
                state.infrastructure.vpc_id = None
                state.infrastructure.vpc_cidr = None
                logger.info(f"Removing VPC {vpc_id}")

            if state.infrastructure.ssh_key:
                ssh_key_name = state.infrastructure.ssh_key
                SSHKey(service).delete(ssh_key_name)
                state.infrastructure.ssh_key = None
                logger.info(f"Removing key pair {ssh_key_name}")

        except Exception as err:
            raise AWSNetworkError(f"Error removing VPC: {err}")

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
