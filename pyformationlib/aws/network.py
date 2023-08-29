##
##

import attr
from typing import Optional, List, Sequence
from pyformationlib.network import NetworkDriver
from pyformationlib.aws.config.network import (AWSProvider, VPCResource, InternetGatewayResource, RouteEntry, RouteResource, SubnetResource, RTAssociationResource,
                                               SecurityGroupEntry, SGResource, Resources, VPCConfig)


@attr.s
class AWSNetworkConfig:
    project: Optional[str] = attr.ib(default=None)
    region: Optional[str] = attr.ib(default=None)


class AWSNetwork(object):

    def __init__(self, config: AWSNetworkConfig):
        pass

    def config_gen(self):
        cidr_util = NetworkDriver()

        for net in config.cloud_network().cidr_list:
            cidr_util.add_network(net)

        vpc_cidr = cidr_util.get_next_network()
        subnet_list = list(cidr_util.get_next_subnet())
        zone_list = config.cloud_base().zones()


    def create(self):
        pass
