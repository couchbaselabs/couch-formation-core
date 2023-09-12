##
##

import re
import logging
from itertools import cycle
from typing import List
from couchformation.exec.process import TFRun
import couchformation.aws.driver.constants as C
from couchformation.aws.driver.image import Image
from couchformation.aws.driver.machine import MachineType
from couchformation.aws.driver.base import CloudBase
from couchformation.aws.network import AWSNetwork
from couchformation.config import NodeList, DeploymentConfig, NodeConfig
from couchformation.aws.config.network import AWSProvider
from couchformation.common.config.resources import NodeBuild, ResourceBlock, NodeMain, Output, OutputValue
from couchformation.ssh import SSHUtil
from couchformation.exception import FatalError
from couchformation.provisioner.remote import RemoteProvisioner, ProvisionSet
from couchformation.aws.config.node import (AWSInstance, BlockDevice, EbsElements, RootElements, NodeConfiguration, TerraformElement, RequiredProvider, AWSTerraformProvider,
                                            SSHResource)

logger = logging.getLogger('couchformation.aws.node')
logger.addHandler(logging.NullHandler())


class AWSNodeError(FatalError):
    pass


class AWSDeployment(object):

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

        # try:
        #     self.validate()
        # except ValueError as err:
        #     raise AWSNodeError(err)

        self._name_check(self.name)
        CloudBase(self.core).test_session()
        self.runner = TFRun(self.core)

        self.aws_network = AWSNetwork(self.core)
        self.vpc_data = self.aws_network.output()

    def deployment_config(self):
        ssh_key_name = f"{self.name}-key"

        try:
            ssh_pub_key_text = SSHUtil().get_ssh_public_key(self.ssh_key)
        except Exception as err:
            raise AWSNodeError(f"can not get SSH public key: {err}")

        header_block = TerraformElement.construct(RequiredProvider.construct(AWSTerraformProvider.construct("hashicorp/aws").as_dict).as_dict)
        provider_block = AWSProvider.for_region(self.region)
        ssh_block = SSHResource.construct(ssh_key_name, ssh_pub_key_text)

        resource_block = ResourceBlock.build()
        resource_block.add(ssh_block.as_dict)

        output_block = Output.build()
        instance_block = AWSInstance.build()

        for n, node_config in enumerate(self.deployment.config):
            instance_values, output_values = self.node_config(n, ssh_key_name, node_config)
            for instance in instance_values:
                instance_block.add(instance)
            for block in output_values:
                output_block.add(block)

        resource_block.add(instance_block.as_dict)

        main_config = NodeMain.build() \
            .add(header_block.as_dict) \
            .add(provider_block.as_dict)\
            .add(resource_block.as_dict)\
            .add(output_block.as_dict).as_dict

        return main_config

    def node_config(self, group: int, ssh_key_name: str, config: NodeConfig):
        subnet_list = []
        output_values = []
        instance_values = []
        quantity = config.quantity
        machine_type = config.machine_type
        volume_iops = config.volume_iops
        volume_size = config.volume_size
        volume_type = config.volume_type
        root_size = config.root_size
        services = config.services

        if not self.vpc_data:
            raise AWSNodeError(f"project {self.project} is not configured")

        image_list = Image(self.core).list_standard(os_id=self.os_id, os_version=self.os_version)

        if len(image_list) == 0:
            raise AWSNodeError(f"can not find image for os {self.os_id} version {self.os_version}")

        image = image_list[-1]
        machine = MachineType(self.core).get_machine(machine_type)
        machine_name = machine['name']
        machine_ram = str(int(machine['memory'] / 1024))

        if not machine:
            raise AWSNodeError(f"can not find machine for type {machine_type}")

        root_disk_device = image['root_disk']
        match = re.search(r"/dev/(.+?)a[0-9]*", root_disk_device)
        root_disk_prefix = f"/dev/{match.group(1)}"

        for key, value in self.vpc_data.items():
            if value.get('value', {}).get('map_public_ip_on_launch') is not None:
                subnet_list.append(dict(
                    subnet_id=value.get('value', {}).get('id'),
                    zone=value.get('value', {}).get('availability_zone'),
                    cidr=value.get('value', {}).get('cidr_block'),
                ))

        if len(subnet_list) == 0:
            raise AWSNodeError(f"can not get subnet list, check project settings")

        subnet_cycle = cycle(subnet_list)

        security_group_id = self.vpc_data.get('aws_security_group', {}).get('value', {}).get('id')

        if not security_group_id:
            raise AWSNodeError(f"can not get security group, check project settings")

        disk_block = BlockDevice.build()
        disk_block.add(
            EbsElements.construct(
                f"{root_disk_prefix}b",
                self._calc_iops(machine_ram),
                machine_ram,
                "gp3"
            ).as_dict
        )

        disk_block.add(
            EbsElements.construct(
                f"{root_disk_prefix}c",
                volume_iops,
                volume_size,
                volume_type
            ).as_dict
        )

        for n in range(int(quantity)):
            subnet = next(subnet_cycle)
            node_name = f"node-{self.name}-{group + 1}-{n + 1}"
            instance_values.append(
                NodeBuild.construct(
                    NodeConfiguration.construct(
                        node_name,
                        image['name'],
                        subnet['zone'],
                        machine_name,
                        ssh_key_name,
                        RootElements.construct(
                            self._calc_iops(root_size),
                            root_size,
                            "gp3"
                        ).as_dict,
                        subnet['subnet_id'],
                        security_group_id,
                        services,
                        disk_block.as_dict
                    ).as_dict
                ).as_name(node_name)
            )

        for n in range(int(quantity)):
            output_key = f"aws_instance.node-{self.name}-{group + 1}-{n + 1}"
            output_values.append(
                OutputValue.build()
                .add(f"${{{output_key}}}")
                .as_name(output_key.split('.')[1])
            )

        return instance_values, output_values

    def deploy(self):
        if not self.vpc_data:
            self.aws_network.create()
            self.vpc_data = self.aws_network.output()
        nodes = self.deployment_config()
        logger.info(f"Creating cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.deploy(nodes)

    def destroy(self):
        logger.info(f"Removing cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.destroy()
        if self.vpc_data:
            self.aws_network.destroy()
            self.vpc_data = self.aws_network.output()

    def output(self):
        return self.runner.output()

    def list(self) -> NodeList:
        username = Image.image_user(self.os_id)
        if not username:
            raise AWSNodeError(f"can not get username for os type {self.os_id}")
        node_list = NodeList().create(username, self.ssh_key, self.core.working_dir, self.core.private_ip)
        node_data = self.output()
        for key, value in node_data.items():
            node_name = key
            node_private_ip = value.get('value', {}).get('private_ip')
            node_public_ip = value.get('value', {}).get('public_ip')
            availability_zone = value.get('value', {}).get('availability_zone')
            services = value.get('value', {}).get('tags', {}).get('Services')
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
            raise AWSNodeError("names must only contain letters, numbers, dashes and underscores")

    def validate(self):
        variables = [attr for attr in dir(self) if not callable(getattr(self, attr)) and not attr.startswith("__")]
        for variable in variables:
            if getattr(self, variable) is None:
                raise ValueError(f"setting \"{variable}\" is null")
