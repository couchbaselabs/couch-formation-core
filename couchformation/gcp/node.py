##
##

import re
import logging
from itertools import cycle
from typing import List
from couchformation.exec.process import TFRun
import couchformation.gcp.driver.constants as C
from couchformation.gcp.driver.image import Image
from couchformation.gcp.driver.machine import MachineType
from couchformation.gcp.driver.base import CloudBase
from couchformation.gcp.network import GCPNetwork
from couchformation.config import NodeList, DeploymentConfig, NodeConfig
from couchformation.common.config.resources import NodeBuild, ResourceBlock, NodeMain, Output, OutputValue
from couchformation.ssh import SSHUtil
from couchformation.exception import FatalError
from couchformation.provisioner.remote import RemoteProvisioner, ProvisionSet
from couchformation.gcp.config.node import (GCPInstance, AttachedDisk, NodeConfiguration, TerraformElement, RequiredProvider, GCPTerraformProvider,
                                            GCPProviderBlock, GCPDisk, GCPDiskBuild, GCPDiskConfiguration)

logger = logging.getLogger('couchformation.aws.node')
logger.addHandler(logging.NullHandler())


class GCPNodeError(FatalError):
    pass


class GCPDeployment(object):

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

        self.gcp_network = GCPNetwork(self.core)
        self.gcp_base = CloudBase(self.core)
        self.vpc_data = self.gcp_network.output()

        self.gcp_project = self.gcp_base.gcp_project
        self.gcp_account_email = self.gcp_base.gcp_account_email
        self.gcp_auth_file = self.gcp_base.auth_file

    def deployment_config(self):
        try:
            ssh_pub_key_text = SSHUtil().get_ssh_public_key(self.ssh_key)
        except Exception as err:
            raise GCPNodeError(f"can not get SSH public key: {err}")

        header_block = TerraformElement.construct(RequiredProvider.construct(GCPTerraformProvider.construct("hashicorp/google").as_dict).as_dict)

        provider_block = GCPProviderBlock.construct(self.gcp_auth_file, self.gcp_project, self.region)

        resource_block = ResourceBlock.build()

        output_block = Output.build()
        instance_block = GCPInstance.build()
        disk_block = GCPDisk.build()

        for n, node_config in enumerate(self.deployment.config):
            instance_values, disk_values, output_values = self.node_config(n, ssh_pub_key_text, node_config)
            for disk in disk_values:
                disk_block.add(disk)
            for instance in instance_values:
                instance_block.add(instance)
            for block in output_values:
                output_block.add(block)

        resource_block.add(instance_block.as_dict)
        resource_block.add(disk_block.as_dict)

        main_config = NodeMain.build() \
            .add(header_block.as_dict) \
            .add(provider_block.as_dict) \
            .add(resource_block.as_dict) \
            .add(output_block.as_dict).as_dict

        return main_config

    def node_config(self, group: int, ssh_key: str, config: NodeConfig):
        subnet_list = []
        output_values = []
        instance_values = []
        disk_values = []
        quantity = config.quantity
        machine_type = config.machine_type
        volume_size = config.volume_size
        volume_type = config.volume_type
        root_size = config.root_size
        services = config.services

        if not self.vpc_data:
            raise GCPNodeError(f"project {self.project} is not configured")

        image_list = Image(self.core).list_standard(os_id=self.os_id, os_version=self.os_version)

        if len(image_list) == 0:
            raise GCPNodeError(f"can not find image for os {self.os_id} version {self.os_version}")

        image = image_list[-1]

        subnet_name = self.vpc_data.get('google_compute_subnetwork', {}).get('value', {}).get('name')

        for zone in self.gcp_base.gcp_zone_list:
            subnet_record = {}
            subnet_record.update({"subnet_name": subnet_name})
            subnet_record.update({"zone": zone})
            subnet_list.append(subnet_record)

        subnet_cycle = cycle(subnet_list)

        for n in range(int(quantity)):
            subnet = next(subnet_cycle)
            node_name = f"node-{self.name}-{group + 1}-{n + 1}"
            node_swap_disk = f"{node_name}-swap-disk"
            node_data_disk = f"{node_name}-data-disk"

            machine = MachineType(self.core).get_machine(machine_type, subnet['zone'])
            machine_name = machine['name']
            machine_ram = str(int(machine['memory'] / 1024))

            disk_values.append(
                GCPDiskBuild.construct(
                    GCPDiskConfiguration.construct(
                        node_name,
                        "swap",
                        self.gcp_project,
                        machine_ram,
                        volume_type,
                        subnet['zone']
                    ).as_dict
                ).as_name(node_swap_disk)
            )

            disk_values.append(
                GCPDiskBuild.construct(
                    GCPDiskConfiguration.construct(
                        node_name,
                        "data",
                        self.gcp_project,
                        volume_size,
                        volume_type,
                        subnet['zone']
                    ).as_dict
                ).as_name(node_data_disk)
            )

            attached_disk_block = AttachedDisk.build()
            attached_disk_block.add(node_swap_disk)
            attached_disk_block.add(node_data_disk)

            instance_values.append(
                NodeBuild.construct(
                    NodeConfiguration.construct(
                        node_name,
                        image['image_project'],
                        image['name'],
                        root_size,
                        volume_type,
                        machine_name,
                        image['os_user'],
                        ssh_key,
                        subnet['subnet_name'],
                        self.gcp_project,
                        self.gcp_account_email,
                        subnet['zone'],
                        services,
                        attached_disk_block.as_dict
                    ).as_dict
                ).as_name(node_name)
            )

        for n in range(int(quantity)):
            output_key = f"google_compute_instance.node-{self.name}-{group + 1}-{n + 1}"
            output_values.append(
                OutputValue.build()
                .add(f"${{{output_key}}}")
                .as_name(output_key.split('.')[1])
            )

        return instance_values, disk_values, output_values

    def deploy(self):
        if not self.vpc_data:
            self.gcp_network.create()
            self.vpc_data = self.gcp_network.output()
        nodes = self.deployment_config()
        logger.info(f"Creating cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.deploy(nodes)

    def destroy(self):
        logger.info(f"Removing cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.destroy()
        if self.vpc_data:
            self.gcp_network.destroy()
            self.vpc_data = self.gcp_network.output()

    def output(self):
        return self.runner.output()

    def list(self) -> NodeList:
        username = Image.image_user(self.os_id)
        if not username:
            raise GCPNodeError(f"can not get username for os type {self.os_id}")
        node_list = NodeList().create(username, self.ssh_key, self.core.working_dir, self.core.private_ip)
        node_data = self.output()
        for key, value in node_data.items():
            node_name = key
            node_private_ip = value.get('value', {}).get('network_interface')[0].get('network_ip')
            node_public_ip = value.get('value', {}).get('network_interface')[0].get('access_config')[0].get('nat_ip')
            availability_zone = value.get('value', {}).get('zone')
            services = value.get('value', {}).get('metadata', {}).get('services')
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
            raise GCPNodeError("names must only contain letters, numbers, dashes and underscores")

    def validate(self):
        variables = [attr for attr in dir(self) if not callable(getattr(self, attr)) and not attr.startswith("__")]
        for variable in variables:
            if getattr(self, variable) is None:
                raise ValueError(f"setting \"{variable}\" is null")
