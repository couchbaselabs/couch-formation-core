##
##

import logging
from couchformation.network import NetworkDriver
from couchformation.azure.driver.network import Network
from couchformation.azure.driver.base import CloudBase
from couchformation.exec.process import TFRun
import couchformation.azure.driver.constants as C
from couchformation.common.config.resources import Output, OutputValue
from couchformation.config import BaseConfig
from couchformation.exception import FatalError
from couchformation.azure.config.network import (AzureProvider, RGResource, VNetResource, Resources, VPCConfig, NSGResource, NSGEntry, NSGElements)

logger = logging.getLogger('couchformation.azure.network')
logger.addHandler(logging.NullHandler())


class AzureNetworkError(FatalError):
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
            raise AzureNetworkError(err)

        self.az_network = Network(core)
        self.az_base = CloudBase(core)
        self.runner = TFRun(core)

    def config_gen(self):
        cidr_util = NetworkDriver()
        rg_name = f"{self.project}-rg"
        vpc_name = f"{self.project}-vpc"
        nsg_name = f"{self.project}-nsg"

        vpc_cidr = cidr_util.get_next_network()
        subnet_list = list(cidr_util.get_next_subnet())
        subnet_cidr = subnet_list[1]
        region = self.region

        if self.az_base.get_rg(rg_name, region):
            raise AzureNetworkError(f"Resource Group {rg_name} already exists")

        provider_block = AzureProvider.for_region()

        rg_block = RGResource.construct(region, rg_name)

        vnet_block = VNetResource.construct(vpc_cidr, vpc_name, subnet_cidr)

        nsg_block = NSGResource.construct(
            NSGEntry.construct(
                NSGElements.construct(nsg_name)
                .add("AllowSSH", ["22"], 100)
                .add("AllowCB", ["8091-8097", "9123", "9140", "11210", "11280", "11207", "18091-18097", "4984-4986"], 101)
                .as_dict)
            .as_dict)

        resource_block = Resources.build()
        resource_block.add(rg_block.as_dict)
        resource_block.add(vnet_block.as_dict)
        resource_block.add(nsg_block.as_dict)

        output_block = Output.build()
        output_block.add(
            OutputValue.build()
            .add("${azurerm_virtual_network.cf_vpc}")
            .as_name("azurerm_virtual_network")
        )
        output_block.add(
            OutputValue.build()
            .add("${azurerm_resource_group.cf_rg}")
            .as_name("azurerm_resource_group")
        )

        vpc_config = VPCConfig.build() \
            .add(provider_block.as_dict) \
            .add(resource_block.as_dict) \
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
