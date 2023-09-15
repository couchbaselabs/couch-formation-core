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
from couchformation.exec.process import TFRun
import couchformation.aws.driver.constants as C
from couchformation.common.config.resources import Output, OutputValue
from couchformation.config import BaseConfig
from couchformation.ssh import SSHUtil
import couchformation.state as state
from couchformation.state import INFRASTRUCTURE, AWSZone
from couchformation.exception import FatalError
from couchformation.aws.config.network import (AWSProvider, VPCResource, InternetGatewayResource, RouteEntry, RouteResource, SubnetResource, RTAssociationResource,
                                               SecurityGroupEntry, SGResource, Resources, VPCConfig)

logger = logging.getLogger('couchformation.aws.network')
logger.addHandler(logging.NullHandler())


class AWSNetworkError(FatalError):
    pass


class AWSNetwork(object):

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
            raise AWSNetworkError(err)

        self.aws_network = Network(core)
        self.runner = TFRun(core)

    def create_vpc(self):
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
                vpc_id = Network(core).create(vpc_name, vpc_cidr)
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
                sg_id = SecurityGroup(core).create(sg_name, f"Couch Formation project {self.profile}", vpc_id)
                SecurityGroup(core).add_ingress(sg_id, "-1", 0, 0, vpc_cidr)
                SecurityGroup(core).add_ingress(sg_id, "tcp", 22, 22, "0.0.0.0/0")
                SecurityGroup(core).add_ingress(sg_id, "tcp", 8091, 8097, "0.0.0.0/0")
                SecurityGroup(core).add_ingress(sg_id, "tcp", 9123, 9123, "0.0.0.0/0")
                SecurityGroup(core).add_ingress(sg_id, "tcp", 9140, 9140, "0.0.0.0/0")
                SecurityGroup(core).add_ingress(sg_id, "tcp", 11210, 11210, "0.0.0.0/0")
                SecurityGroup(core).add_ingress(sg_id, "tcp", 11280, 11280, "0.0.0.0/0")
                SecurityGroup(core).add_ingress(sg_id, "tcp", 11207, 11207, "0.0.0.0/0")
                SecurityGroup(core).add_ingress(sg_id, "tcp", 18091, 18097, "0.0.0.0/0")
                SecurityGroup(core).add_ingress(sg_id, "tcp", 4984, 4986, "0.0.0.0/0")
                state.infrastructure.security_group_id = sg_id
                logger.info(f"Created security group {sg_id}")

            if not state.infrastructure.ssh_key:
                ssh_key_name = SSHKey(core).create(key_name, ssh_pub_key_text)
                state.infrastructure.ssh_key = ssh_key_name
                logger.info(f"Created SSH Key {ssh_key_name}")

            if not state.infrastructure.internet_gateway_id:
                ig_id = InternetGateway(core).create(ig_name, vpc_id)
                state.infrastructure.internet_gateway_id = ig_id
                logger.info(f"Created internet gateway {ig_id}")
            else:
                ig_id = state.infrastructure.internet_gateway_id

            if not state.infrastructure.route_table_id:
                rt_id = RouteTable(core).create(rt_name, vpc_id)
                state.infrastructure.route_table_id = rt_id
                RouteTable(core).add_route("0.0.0.0/0", ig_id, rt_id)
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
                subnet_id = Subnet(core).create(subnet_name, vpc_id, zone, network_cidr)
                RouteTable(core).associate(rt_id, subnet_id)
                zone_state.subnet_id = subnet_id
                zone_state.cidr = network_cidr
                # noinspection PyTypeChecker
                state.infrastructure.zone_list.append(attr.asdict(zone_state))
                logger.info(f"Created subnet {subnet_id} in zone {zone}")

        except Exception as err:
            raise AWSNetworkError(f"Error creating VPC: {err}")

        state.save()

    def destroy_vpc(self):
        core = self.core

        state.update(INFRASTRUCTURE)

        try:

            if state.infrastructure.route_table_id:
                rt_id = state.infrastructure.route_table_id
                RouteTable(core).delete(rt_id)
                state.infrastructure.route_table_id = None
                logger.info(f"Removed route table {rt_id}")

            if state.infrastructure.internet_gateway_id:
                ig_id = state.infrastructure.internet_gateway_id
                InternetGateway(core).delete(ig_id)
                state.infrastructure.internet_gateway_id = None
                logger.info(f"Removing internet gateway {ig_id}")

            if state.infrastructure.security_group_id:
                sg_id = state.infrastructure.security_group_id
                SecurityGroup(core).delete(sg_id)
                state.infrastructure.security_group_id = None
                logger.info(f"Removing security group {sg_id}")

            for n, zone_state in reversed(list(enumerate(state.infrastructure.zone_list))):
                subnet_id = zone_state['subnet_id']
                Subnet(core).delete(subnet_id)
                del state.infrastructure.zone_list[n]
                logger.info(f"Removed subnet {subnet_id}")

            if state.infrastructure.vpc_id:
                vpc_id = state.infrastructure.vpc_id
                Network(core).delete(vpc_id)
                state.infrastructure.vpc_id = None
                state.infrastructure.vpc_cidr = None
                logger.info(f"Removing VPC {vpc_id}")

            if state.infrastructure.ssh_key:
                ssh_key_name = state.infrastructure.ssh_key
                SSHKey(core).delete(ssh_key_name)
                state.infrastructure.ssh_key = None
                logger.info(f"Removing key pair {ssh_key_name}")

        except Exception as err:
            raise AWSNetworkError(f"Error removing VPC: {err}")

        state.save()

    def config_gen(self):
        cidr_util = NetworkDriver()
        vpc_name = f"{self.project}-vpc"
        ig_name = f"{self.project}-gw"
        rt_name = f"{self.project}-rt"
        sg_name = f"{self.project}-sg"
        subnet_names = []

        for net in self.aws_network.cidr_list:
            cidr_util.add_network(net)

        vpc_cidr = cidr_util.get_next_network()
        subnet_list = list(cidr_util.get_next_subnet())
        zone_list = self.aws_network.zones()

        provider_block = AWSProvider.for_region(self.region)

        cf_vpc = VPCResource.construct(vpc_cidr, vpc_name).as_dict

        cf_gw = InternetGatewayResource.construct(ig_name).as_dict

        route_entry = RouteEntry.construct(rt_name)
        route_entry.add("0.0.0.0/0")
        cf_rt = RouteResource.construct(route_entry.as_dict).as_dict

        subnet_struct = SubnetResource.build()
        association_struct = RTAssociationResource.build()
        for n, zone in enumerate(zone_list):
            subnet_name = f"{self.project}_subnet_{n+1}"
            subnet_names.append(subnet_name)
            subnet_struct.add(subnet_name, zone, subnet_list[n + 1], True)
            association_struct.add(subnet_name)
        subnet_resources = subnet_struct.as_dict
        rt_association_resources = association_struct.as_dict

        sg_entry = SecurityGroupEntry.construct(sg_name)
        sg_entry.add_ingress("0.0.0.0/0", 22, "tcp", 22)
        sg_entry.add_ingress("0.0.0.0/0", 8091, "tcp", 8097)
        sg_entry.add_ingress("0.0.0.0/0", 9123, "tcp", 9123)
        sg_entry.add_ingress("0.0.0.0/0", 9140, "tcp", 9140)
        sg_entry.add_ingress("0.0.0.0/0", 11210, "tcp", 11210)
        sg_entry.add_ingress("0.0.0.0/0", 11280, "tcp", 11280)
        sg_entry.add_ingress("0.0.0.0/0", 11207, "tcp", 11207)
        sg_entry.add_ingress("0.0.0.0/0", 18091, "tcp", 18097)
        sg_entry.add_ingress("0.0.0.0/0", 4984, "tcp", 4986)
        cf_sg = SGResource.construct(sg_entry.as_dict).as_dict

        resource_block = Resources.build()
        resource_block.add(cf_vpc)
        resource_block.add(subnet_resources)
        resource_block.add(rt_association_resources)
        resource_block.add(cf_gw)
        resource_block.add(cf_rt)
        resource_block.add(cf_sg)

        output_block = Output.build()

        for item in ['aws_vpc.cf_vpc', 'aws_security_group.cf_sg', 'aws_route_table.cf_rt', 'aws_internet_gateway.cf_gw']:
            output_block.add(
                OutputValue.build()
                .add(f"${{{item}}}")
                .as_name(item.split('.')[0])
            )

        for subnet in subnet_names:
            output_block.add(
                OutputValue.build()
                .add(f"${{aws_subnet.{subnet}}}")
                .as_name(subnet)
            )

        vpc_config = VPCConfig.build() \
            .add(provider_block.as_dict) \
            .add(resource_block.as_dict) \
            .add(output_block.as_dict).as_dict

        return vpc_config

    def create(self):
        logger.info(f"Creating cloud network for {self.project} in {C.CLOUD_KEY.upper()}")
        self.create_vpc()

    def destroy(self):
        logger.info(f"Removing cloud network for {self.project} in {C.CLOUD_KEY.upper()}")
        self.destroy_vpc()

    def output(self):
        return self.runner.output()

    def validate(self):
        variables = [attr for attr in dir(self) if not callable(getattr(self, attr)) and not attr.startswith("__")]
        for variable in variables:
            if getattr(self, variable) is None:
                raise ValueError(f"setting \"{variable}\" is null")
