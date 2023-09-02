##
##

import re
import logging
from itertools import cycle
from typing import List
from pyformationlib.exec.process import TFRun
import pyformationlib.aws.driver.constants as C
from pyformationlib.aws.driver.image import Image
from pyformationlib.aws.driver.machine import MachineType
from pyformationlib.aws.driver.base import CloudBase
from pyformationlib.aws.network import AWSNetwork
from pyformationlib.aws.common import AWSConfig
from pyformationlib.config import NodeList
from pyformationlib.aws.config.network import AWSProvider
from pyformationlib.common.config.resources import NodeBuild, ResourceBlock, NodeMain, Output, OutputValue
from pyformationlib.ssh import SSHUtil
from pyformationlib.exception import FatalError
from pyformationlib.provisioner.remote import RemoteProvisioner, ProvisionSet
from pyformationlib.aws.config.node import (AWSInstance, BlockDevice, EbsElements, RootElements, NodeConfiguration, TerraformElement, RequiredProvider, AWSTerraformProvider,
                                            SSHResource)

logger = logging.getLogger('pyformationlib.aws.node')
logger.addHandler(logging.NullHandler())


class AWSNodeError(FatalError):
    pass


class AWSNode(object):

    def __init__(self, config: AWSConfig):
        self.config = config
        self.project = config.core.project
        self.region = config.region
        self.auth_mode = config.auth_mode
        self.profile = config.profile
        self.name = config.core.name
        self.quantity = config.quantity
        self.os_id = config.os_id
        self.os_version = config.os_version
        self.ssh_key = config.ssh_key
        self.machine_type = config.machine_type
        self.volume_iops = config.volume_iops
        self.volume_size = config.volume_size
        self.volume_type = config.volume_type
        self.root_size = config.root_size
        config.core.resource_mode()

        try:
            self.validate()
        except ValueError as err:
            raise AWSNodeError(err)

        self._name_check(self.name)
        CloudBase(config).test_session()
        self.runner = TFRun(config.core)

    def config_gen(self):
        instance_blocks = []
        subnet_list = []

        aws_network = AWSNetwork(self.config)
        vpc_data = aws_network.output()

        if not vpc_data:
            raise AWSNodeError(f"project {self.project} is not configured")

        try:
            ssh_pub_key_text = SSHUtil().get_ssh_public_key(self.ssh_key)
        except Exception as err:
            raise AWSNodeError(f"can not get SSH public key: {err}")

        image_list = Image(self.config).list_standard(os_id=self.os_id, os_version=self.os_version)

        if len(image_list) == 0:
            raise AWSNodeError(f"can not find image for os {self.os_id} version {self.os_version}")

        image = image_list[-1]
        machine = MachineType(self.config).get_machine(self.machine_type)
        machine_name = machine['name']
        machine_ram = str(int(machine['memory'] / 1024))

        if not machine:
            raise AWSNodeError(f"can not find machine for type {self.machine_type}")

        root_disk_device = image['root_disk']
        match = re.search(r"/dev/(.+?)a[0-9]*", root_disk_device)
        root_disk_prefix = f"/dev/{match.group(1)}"

        ssh_key_name = f"{self.name}-key"
        for key, value in vpc_data.items():
            if value.get('value', {}).get('map_public_ip_on_launch') is not None:
                subnet_list.append(dict(
                    subnet_id=value.get('value', {}).get('id'),
                    zone=value.get('value', {}).get('availability_zone'),
                    cidr=value.get('value', {}).get('cidr_block'),
                ))

        if len(subnet_list) == 0:
            raise AWSNodeError(f"can not get subnet list, check project settings")

        subnet_cycle = cycle(subnet_list)

        security_group_id = vpc_data.get('aws_security_group', {}).get('value', {}).get('id')

        if not security_group_id:
            raise AWSNodeError(f"can not get security group, check project settings")

        header_block = TerraformElement.construct(RequiredProvider.construct(AWSTerraformProvider.construct("hashicorp/aws").as_dict).as_dict)

        provider_block = AWSProvider.for_region(self.region)

        ssh_block = SSHResource.construct(ssh_key_name, ssh_pub_key_text)

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
                self.volume_iops,
                self.volume_size,
                self.volume_type
            ).as_dict
        )

        instance_block = AWSInstance.build()
        for n in range(int(self.quantity)):
            subnet = next(subnet_cycle)
            node_name = f"node-{self.name}-{n + 1}"
            instance_block.add(
                NodeBuild.construct(
                    NodeConfiguration.construct(
                        node_name,
                        image['name'],
                        subnet['zone'],
                        machine_name,
                        ssh_key_name,
                        RootElements.construct(
                            self._calc_iops(self.root_size),
                            self.root_size,
                            "gp3"
                        ).as_dict,
                        subnet['subnet_id'],
                        security_group_id,
                        disk_block.as_dict
                    ).as_dict
                ).as_name(node_name)
            )
            instance_blocks.append(instance_block.as_dict)

        resource_block = ResourceBlock.build()
        resource_block.add(instance_block.as_dict)
        resource_block.add(ssh_block.as_dict)

        output_block = Output.build()
        for n in range(int(self.quantity)):
            output_key = f"aws_instance.node-{self.name}-{n + 1}"
            output_block.add(
                OutputValue.build()
                .add(f"${{{output_key}}}")
                .as_name(output_key.split('.')[1])
            )

        main_config = NodeMain.build() \
            .add(header_block.as_dict) \
            .add(provider_block.as_dict)\
            .add(resource_block.as_dict)\
            .add(output_block.as_dict).as_dict

        return main_config

    def create(self):
        nodes = self.config_gen()
        logger.info(f"Creating cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.deploy(nodes)

    def destroy(self):
        logger.info(f"Removing cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.destroy()

    def output(self):
        return self.runner.output()

    def list(self) -> NodeList:
        username = Image.image_user(self.os_id)
        if not username:
            raise AWSNodeError(f"can not get username for os type {self.os_id}")
        node_list = NodeList().create(username, self.ssh_key, self.config.core.working_dir, self.config.core.private_ip)
        node_data = self.output()
        for key, value in node_data.items():
            node_name = key
            node_private_ip = value.get('value', {}).get('private_ip')
            node_public_ip = value.get('value', {}).get('public_ip')
            availability_zone = value.get('value', {}).get('availability_zone')
            node_list.add(node_name, node_private_ip, node_public_ip, availability_zone)
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
