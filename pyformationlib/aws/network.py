##
##

import attr
import logging
from typing import Optional
from pyformationlib.network import NetworkDriver
from pyformationlib.aws.driver.network import Network
from pyformationlib.aws.driver.base import AuthMode
from pyformationlib.exec.process import TFRun
import pyformationlib.aws.driver.constants as C
from pyformationlib.common.config.resources import Output, OutputValue
from pyformationlib.aws.config.network import (AWSProvider, VPCResource, InternetGatewayResource, RouteEntry, RouteResource, SubnetResource, RTAssociationResource,
                                               SecurityGroupEntry, SGResource, Resources, VPCConfig)

logger = logging.getLogger('pyformationlib.aws.network')
logger.addHandler(logging.NullHandler())


@attr.s
class AWSNetworkConfig:
    project: Optional[str] = attr.ib(default=None)
    region: Optional[str] = attr.ib(default=None)
    auth_mode: Optional[AuthMode] = attr.ib(default=AuthMode.default)
    profile: Optional[str] = attr.ib(default='default')
    location: Optional[str] = attr.ib(default=None)

    @classmethod
    def create(cls,
               project: str,
               region: str,
               auth_mode: AuthMode = AuthMode.default,
               profile: str = 'default',
               location: str = None):
        return cls(project,
                   region,
                   auth_mode,
                   profile,
                   location
                   )


class AWSNetwork(object):

    def __init__(self, config: AWSNetworkConfig):
        self.project = config.project
        self.region = config.region
        self.auth_mode = config.auth_mode
        self.profile = config.profile
        self.location = config.location
        self.name = 'network'

        self.aws_network = Network(self.region, self.auth_mode, self.profile)
        self.runner = TFRun(self.project, self.name, self.location)

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
        network = self.config_gen()
        logger.info(f"Creating cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.deploy(network)

    def destroy(self):
        logger.info(f"Removing cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.destroy()

    def output(self):
        return self.runner.output()
