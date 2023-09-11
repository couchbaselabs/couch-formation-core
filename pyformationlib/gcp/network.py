##
##

import logging
from pyformationlib.network import NetworkDriver
from pyformationlib.gcp.driver.network import Network
from pyformationlib.gcp.driver.base import CloudBase
from pyformationlib.exec.process import TFRun
import pyformationlib.gcp.driver.constants as C
from pyformationlib.common.config.resources import Output, OutputValue
from pyformationlib.config import BaseConfig
from pyformationlib.exception import FatalError
from pyformationlib.gcp.config.network import (GCPProvider, SubnetResource, NetworkResource, Resources, VPCConfig, FirewallResource)

logger = logging.getLogger('pyformationlib.aws.network')
logger.addHandler(logging.NullHandler())


class GCPNetworkError(FatalError):
    pass


class GCPNetwork(object):

    def __init__(self, core: BaseConfig):
        self.project = core.project
        self.region = core.region
        self.auth_mode = core.auth
        self.profile = core.profile
        core.common_mode()

        try:
            self.validate()
        except ValueError as err:
            raise GCPNetworkError(err)

        self.gcp_network = Network(core)
        self.gcp_base = CloudBase(core)
        self.runner = TFRun(core)

    def config_gen(self):
        cidr_util = NetworkDriver()
        vpc_name = f"{self.project}-vpc"
        subnet_name = f"{self.project}-subnet-1"

        for net in self.gcp_network.cidr_list:
            cidr_util.add_network(net)

        vpc_cidr = cidr_util.get_next_network()
        subnet_list = list(cidr_util.get_next_subnet())
        gcp_project = self.gcp_base.project
        account_file = self.gcp_base.account_file

        provider_block = GCPProvider.for_region(account_file, gcp_project, self.region)

        network_block = NetworkResource.construct(vpc_name)

        subnet_block = SubnetResource.construct(subnet_list[1], subnet_name, self.region)

        firewall_block = FirewallResource.build(self.project, vpc_cidr)
        firewall_block.add(self.project, "cbs",
                           ["8091-8097", "9123", "9140", "11210", "11280", "11207", "18091-18097", "4984-4986"],
                           "tcp",
                           ["0.0.0.0/0"])
        firewall_block.add(self.project, "ssh", ["22"], "tcp", ["0.0.0.0/0"])

        resource_block = Resources.build()
        resource_block.add(network_block.as_dict)
        resource_block.add(subnet_block.as_dict)
        resource_block.add(firewall_block.as_dict)

        output_block = Output.build()
        output_block.add(
            OutputValue.build()
            .add("${google_compute_network.cf_vpc}")
            .as_name("google_compute_network")
        )
        output_block.add(
            OutputValue.build()
            .add("${google_compute_subnetwork.cf_subnet_1}")
            .as_name("google_compute_subnetwork")
        )

        vpc_config = VPCConfig.build()\
            .add(provider_block.as_dict)\
            .add(resource_block.as_dict)\
            .add(output_block.as_dict).as_dict

        return vpc_config

    def create(self):
        vpc_data = self.output()
        if vpc_data:
            return
        network = self.config_gen()
        logger.info(f"Creating cloud network for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.deploy(network)

    def destroy(self):
        logger.info(f"Removing cloud network for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.destroy()

    def output(self):
        return self.runner.output()

    def validate(self):
        variables = [attr for attr in dir(self) if not callable(getattr(self, attr)) and not attr.startswith("__")]
        for variable in variables:
            if getattr(self, variable) is None:
                raise ValueError(f"setting \"{variable}\" is null")
