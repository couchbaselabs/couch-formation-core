##
##

import re
import logging
from itertools import cycle
from typing import List
from couchformation.exec.process import TFRun
import couchformation.azure.driver.constants as C
from couchformation.azure.driver.image import Image
from couchformation.azure.driver.machine import MachineType
from couchformation.azure.driver.base import CloudBase
from couchformation.azure.network import GCPNetwork
from couchformation.config import NodeList, DeploymentConfig, NodeConfig
from couchformation.common.config.resources import NodeBuild, ResourceBlock, NodeMain, Output, OutputValue, ResourceBuild, DataResource
from couchformation.ssh import SSHUtil
from couchformation.exception import FatalError
from couchformation.provisioner.remote import RemoteProvisioner, ProvisionSet
from couchformation.azure.config.node import (NodeConfiguration, TerraformElement, RequiredProvider, AzureInstance, AzureTerraformProvider, AzureProviderBlock, NICConfiguration,
                                              NSGData, NICNSGConfiguration, AzureNetworkInterfaceNSG, AzureNetworkInterface, PublicIPConfiguration, DiskConfiguration,
                                              SubnetData, AzureManagedDisk, AzureDiskAttachment, AttachedDiskConfiguration, AzurePublicIP)

logger = logging.getLogger('couchformation.azure.node')
logger.addHandler(logging.NullHandler())


class AzureNodeError(FatalError):
    pass


class AzureDeployment(object):

    def __init__(self, deployment: DeploymentConfig):
        self.deployment = deployment
        self.core = self.deployment.core
        self.project = self.core.project
        self.region = self.core.region
        self.auth_mode = self.core.auth_mode
        self.profile = self.core.profile
        self.name = self.core.name
        self.ssh_key = self.core.ssh_key
        self.os_id = self.core.os_id
        self.os_version = self.core.os_version
        self.core.resource_mode()

        self._name_check(self.name)
        CloudBase(self.core).test_session()
        self.runner = TFRun(self.core)

        self.az_network = GCPNetwork(self.core)
        self.az_base = CloudBase(self.core)
        self.vpc_data = self.az_network.output()

    def deployment_config(self):
        rg_name = f"{self.project}-rg"
        vpc_name = f"{self.project}-vpc"
        nsg_name = f"{self.project}-nsg"

        try:
            ssh_pub_key_text = SSHUtil().get_ssh_public_key(self.ssh_key)
        except Exception as err:
            raise AzureNodeError(f"can not get SSH public key: {err}")

        header_block = TerraformElement.construct(RequiredProvider.construct(AzureTerraformProvider.construct("hashicorp/azurerm").as_dict).as_dict)
        provider_block = AzureProviderBlock.construct()

        data_block = DataResource.build().add(
            NSGData.construct(nsg_name, rg_name).as_dict
        ).add(
            SubnetData.construct(rg_name, vpc_name).as_dict
        )

        resource_block = ResourceBlock.build()
        output_block = Output.build()
        instance_block = AzureInstance.build()
        disk_block = AzureManagedDisk.build()
        disk_attach_block = AzureDiskAttachment.build()
        public_ip_block = AzurePublicIP.build()
        nic_block = AzureNetworkInterface.build()
        nic_nsg_block = AzureNetworkInterfaceNSG.build()

        for n, node_config in enumerate(self.deployment.config):
            instance_values, disk_values, disk_attach_values, public_ip_values, nic_values, nic_nsg_values, output_values = self.node_config(n, ssh_pub_key_text, node_config)
            for disk in disk_values:
                disk_block.add(disk)
            for disk_attach in disk_attach_values:
                disk_attach_block.add(disk_attach)
            for ip in public_ip_values:
                public_ip_block.add(ip)
            for nic in nic_values:
                nic_block.add(nic)
            for nic_nsg in nic_nsg_values:
                nic_nsg_block.add(nic_nsg)
            for instance in instance_values:
                instance_block.add(instance)
            for block in output_values:
                output_block.add(block)

        resource_block.add(instance_block.as_dict)
        resource_block.add(disk_block.as_dict)
        resource_block.add(disk_attach_block.as_dict)
        resource_block.add(public_ip_block.as_dict)
        resource_block.add(nic_block.as_dict)
        resource_block.add(nic_nsg_block.as_dict)

        main_config = NodeMain.build() \
            .add(header_block.as_dict) \
            .add(data_block.as_dict) \
            .add(provider_block.as_dict) \
            .add(resource_block.as_dict) \
            .add(output_block.as_dict).as_dict

        return main_config

    def node_config(self, group: int, ssh_key: str, config: NodeConfig):
        subnet_list = []
        output_values = []
        instance_values = []
        disk_values = []
        disk_attach_values = []
        public_ip_values = []
        nic_values = []
        nic_nsg_values = []
        quantity = config.quantity
        machine_type = config.machine_type
        volume_size = config.volume_size
        volume_type = config.volume_type
        root_size = config.root_size
        services = config.services
        rg_name = f"{self.project}-rg"

        if not self.vpc_data:
            raise AzureNodeError(f"project {self.project} is not configured")

        image = Image(self.core).list_standard(os_id=self.os_id, os_version=self.os_version)

        if not image:
            raise AzureNodeError(f"can not find image for os {self.os_id} version {self.os_version}")

        subnet_name = self.vpc_data.get('azurerm_virtual_network', {}).get('value', {}).get('subnet', [{}])[0].get('name')

        if not subnet_name:
            raise AzureNodeError("Can not get subnet name from network data, check deployment logs")

        for zone in self.az_base.azure_availability_zones:
            subnet_record = {}
            subnet_record.update({"subnet_name": subnet_name})
            subnet_record.update({"zone": zone})
            subnet_list.append(subnet_record)

        subnet_cycle = cycle(subnet_list)
        region = self.region

        machine = MachineType(self.core).get_machine(machine_type, region)
        machine_name = machine['name']
        machine_ram = str(int(machine['memory'] / 1024))

        root_tier = self.az_base.disk_size_to_tier(root_size)
        swap_tier = self.az_base.disk_size_to_tier(machine_ram)
        disk_tier = self.az_base.disk_size_to_tier(volume_size)

        for n in range(int(quantity)):
            subnet = next(subnet_cycle)
            node_name = f"node-{self.name}-{group + 1}-{n + 1}"
            node_swap_disk = f"{node_name}-swap-disk"
            node_data_disk = f"{node_name}-data-disk"
            node_nic = f"{node_name}-nic"
            node_ip = f"{node_name}-ip"
            node_nsg = f"{node_name}-nsg"

            disk_values.append(
                ResourceBuild.construct(
                    DiskConfiguration.construct(
                        node_swap_disk,
                        swap_tier['disk_size'],
                        region,
                        rg_name,
                        volume_type,
                        subnet['zone'],
                        swap_tier['disk_tier']
                    ).as_dict
                ).as_name(node_swap_disk)
            )

            disk_attach_values.append(
                ResourceBuild.construct(
                    AttachedDiskConfiguration.construct(
                        self.az_base.disk_caching(swap_tier['disk_size']),
                        "0",
                        node_swap_disk,
                        node_name
                    ).as_dict
                ).as_name(node_swap_disk)
            )

            disk_values.append(
                ResourceBuild.construct(
                    DiskConfiguration.construct(
                        node_data_disk,
                        disk_tier['disk_size'],
                        region,
                        rg_name,
                        volume_type,
                        subnet['zone'],
                        disk_tier['disk_tier']
                    ).as_dict
                ).as_name(node_data_disk)
            )

            disk_attach_values.append(
                ResourceBuild.construct(
                    AttachedDiskConfiguration.construct(
                        self.az_base.disk_caching(disk_tier['disk_size']),
                        "1",
                        node_data_disk,
                        node_name,
                    ).as_dict
                ).as_name(node_data_disk)
            )

            public_ip_values.append(
                ResourceBuild.construct(
                    PublicIPConfiguration.construct(
                        node_ip,
                        region,
                        rg_name,
                        subnet['zone']
                    ).as_dict
                ).as_name(node_ip)
            )

            nic_values.append(
                ResourceBuild.construct(
                    NICConfiguration.construct(
                        node_nic,
                        node_ip,
                        region,
                        rg_name
                    ).as_dict
                ).as_name(node_nic)
            )

            nic_nsg_values.append(
                ResourceBuild.construct(
                    NICNSGConfiguration.construct(
                        node_nic
                    ).as_dict
                ).as_name(node_nsg)
            )

            instance_values.append(
                NodeBuild.construct(
                    NodeConfiguration.construct(
                        node_name,
                        root_tier['disk_size'],
                        volume_type,
                        machine_name,
                        image['os_user'],
                        ssh_key,
                        region,
                        rg_name,
                        node_nic,
                        subnet['zone'],
                        services,
                        image['publisher'],
                        image['offer'],
                        image['sku']
                    ).as_dict
                ).as_name(node_name)
            )

        for n in range(int(quantity)):
            node_name = f"node-{self.name}-{group + 1}-{n + 1}"
            output_key = f"azurerm_linux_virtual_machine.{node_name}"
            output_values.append(
                OutputValue.build()
                .add(f"${{{output_key}}}")
                .as_name(output_key.split('.')[1])
            )

        return instance_values, disk_values, disk_attach_values, public_ip_values, nic_values, nic_nsg_values, output_values

    def deploy(self):
        if not self.vpc_data:
            self.az_network.create()
            self.vpc_data = self.az_network.output()
        nodes = self.deployment_config()
        logger.info(f"Creating cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.deploy(nodes)

    def destroy(self):
        logger.info(f"Removing cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.destroy()
        if self.vpc_data:
            self.az_network.destroy()
            self.vpc_data = self.az_network.output()

    def output(self):
        return self.runner.output()

    def list(self) -> NodeList:
        username = Image.image_user(self.os_id)
        if not username:
            raise AzureNodeError(f"can not get username for os type {self.os_id}")
        node_list = NodeList().create(username, self.ssh_key, self.core.working_dir, self.core.private_ip)
        node_data = self.output()
        for key, value in node_data.items():
            node_name = key
            node_private_ip = value.get('value', {}).get('private_ip_address')
            node_public_ip = value.get('value', {}).get('public_ip_address')
            availability_zone = value.get('value', {}).get('zone')
            services = value.get('value', {}).get('tags', {}).get('services')
            node_list.add(node_name, node_private_ip, node_public_ip, availability_zone, services)
        return node_list

    def provision(self, pre_commands: List[str], commands: List[str], post_commands: List[str]):
        nodes = self.list()
        ps = ProvisionSet()
        ps.add_pre_install(pre_commands)
        ps.add_install(commands)
        ps.add_post_install(post_commands)
        ps.add_nodes(nodes)
        rp = RemoteProvisioner(ps)
        rp.run()

    @staticmethod
    def _calc_iops(value: str):
        num = int(value)
        iops = num * 10
        return str(3000 if iops < 3000 else 16000 if iops > 16000 else iops)

    @staticmethod
    def _name_check(value):
        p = re.compile(r"^[a-z]([-_a-z0-9]*[a-z0-9])?$")
        if p.match(value):
            return value
        else:
            raise AzureNodeError("names must only contain letters, numbers, dashes and underscores")

    def validate(self):
        variables = [attr for attr in dir(self) if not callable(getattr(self, attr)) and not attr.startswith("__")]
        for variable in variables:
            if getattr(self, variable) is None:
                raise ValueError(f"setting \"{variable}\" is null")
