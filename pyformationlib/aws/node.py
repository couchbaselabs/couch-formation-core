##
##

import attr
import re
import logging
from typing import Optional
from pyformationlib.network import NetworkDriver
from pyformationlib.aws.driver.network import Network
from pyformationlib.aws.driver.base import AuthMode
from pyformationlib.exec.process import TFRun
import pyformationlib.aws.driver.constants as C
from pyformationlib.aws.driver.image import Image
from pyformationlib.aws.driver.machine import MachineType
from pyformationlib.aws.network import AWSNetwork, AWSNetworkConfig
from pyformationlib.aws.config.network import AWSProvider
from pyformationlib.common.config.resources import NodeBuild, TimeSleep, ResourceBlock, NodeMain
from pyformationlib.ssh import SSHUtil
from pyformationlib.exception import FatalError
from pyformationlib.common.config.resources import Output, OutputValue
from pyformationlib.aws.config.node import (AWSInstance, BlockDevice, EbsElements, RootElements, NodeConfiguration, TerraformElement, RequiredProvider, AWSTerraformProvider)

logger = logging.getLogger('pyformationlib.aws.node')
logger.addHandler(logging.NullHandler())


class AWSNodeError(FatalError):
    pass


@attr.s
class AWSNodeConfig:
    project: Optional[str] = attr.ib(default=None)
    name: Optional[str] = attr.ib(default=None)
    quantity: Optional[int] = attr.ib(default=None)
    region: Optional[str] = attr.ib(default=None)
    os_id: Optional[str] = attr.ib(default=None)
    os_version: Optional[str] = attr.ib(default=None)
    ssh_key: Optional[str] = attr.ib(default=None)
    machine_type: Optional[str] = attr.ib(default=None)
    volume_iops: Optional[str] = attr.ib(default=None)
    volume_size: Optional[str] = attr.ib(default=None)
    volume_type: Optional[str] = attr.ib(default=None)
    auth_mode: Optional[AuthMode] = attr.ib(default=AuthMode.default)
    profile: Optional[str] = attr.ib(default='default')
    location: Optional[str] = attr.ib(default=None)

    @classmethod
    def create(cls,
               project: str,
               name: str,
               quantity: int,
               region: str,
               os_id: str,
               os_version: str,
               ssh_key: str,
               machine_type: str,
               volume_iops: str,
               volume_size: str,
               volume_type: str,
               auth_mode: AuthMode = AuthMode.default,
               profile: str = 'default',
               location: str = None):
        return cls(project,
                   name,
                   quantity,
                   region,
                   os_id,
                   os_version,
                   ssh_key,
                   machine_type,
                   volume_iops,
                   volume_size,
                   volume_type,
                   auth_mode,
                   profile,
                   location
                   )


class AWSNode(object):

    def __init__(self, config: AWSNodeConfig):
        self.project = config.project
        self.region = config.region
        self.auth_mode = config.auth_mode
        self.profile = config.profile
        self.name = config.name
        self.quantity = config.quantity
        self.os_id = config.os_id
        self.os_version = config.os_version
        self.ssh_key = config.ssh_key
        self.machine_type = config.machine_type
        self.volume_iops = config.volume_iops
        self.volume_size = config.volume_size
        self.volume_type = config.volume_type
        self.location = config.location

        self._name_check(self.name)

        self.runner = TFRun(self.project, self.name, self.location)

    def config_gen(self):
        net_config = AWSNetworkConfig().create(
            self.project,
            self.region,
            self.auth_mode,
            self.profile,
            self.location
        )
        aws_network = AWSNetwork(net_config)
        vpc_data = aws_network.output()

        if not vpc_data:
            raise AWSNodeError(f"project {self.project} is not configured")

        try:
            ssh_pub_key_text = SSHUtil().get_ssh_public_key(self.ssh_key)
        except Exception as err:
            raise AWSNodeError(f"can not get SSH public key: {err}")

        image_list = Image(self.region, self.auth_mode, self.profile).list_standard(os_id=self.os_id, os_version=self.os_version)

        if len(image_list) == 0:
            raise AWSNodeError(f"can not find image for os {self.os_id} version {self.os_version}")

        image = image_list[-1]
        machine = MachineType(self.region, self.auth_mode, self.profile).get_machine(self.machine_type)

        if not machine:
            raise AWSNodeError(f"can not find machine for type {self.machine_type}")

        root_disk_device = image['root_disk']
        match = re.search(r"/dev/(.+?)a[0-9]*", root_disk_device)
        root_disk_prefix = f"/dev/{match.group(1)}"

        header_block = TerraformElement.construct(RequiredProvider.construct(AWSTerraformProvider.construct("hashicorp/aws").as_dict).as_dict)

        provider_block = AWSProvider.for_region("region_name")

        output_block = Output.build().add(
            OutputValue.build()
            .add("${[for instance in aws_instance.couchbase_nodes: instance.private_ip]}")
            .as_name("node-private")
        ).add(
            OutputValue.build()
            .add("${var.use_public_ip ? [for instance in aws_instance.couchbase_nodes: instance.public_ip] : null}")
            .as_name("node-public")
        )

        disk_block = BlockDevice.build()
        disk_block.add(
            EbsElements.construct(
                f"{root_disk_prefix}b",
                "root_volume_iops",
                "node_ram",
                "root_volume_type"
            ).as_dict
        )

        disk_block.add(
            EbsElements.construct(
                f"{root_disk_prefix}c",
                "root_volume_iops",
                "node_ram",
                "root_volume_type"
            ).as_dict
        )

        instance_block = AWSInstance.build().add(
            NodeBuild.construct(
                NodeConfiguration.construct(
                    "cf_env_name",
                    "ami_id",
                    "node_zone",
                    "instance_type",
                    "ssh_key",
                    RootElements.construct(
                        "root_volume_iops",
                        "root_volume_size",
                        "root_volume_type"
                    ).as_dict,
                    "node_subnet",
                    "security_group_ids",
                    disk_block.as_dict
                ).as_dict
            ).as_name("couchbase_nodes")
        )

        resource_block = ResourceBlock.build()
        resource_block.add(instance_block.as_dict)

        main_config = NodeMain.build() \
            .add(header_block.as_dict) \
            .add(provider_block.as_dict)\
            .add(resource_block.as_dict)\
            .add(output_block.as_dict)

        import json
        print(json.dumps(main_config.as_dict, indent=2))
        return {}

    def create(self):
        nodes = self.config_gen()
        logger.info(f"Creating cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.deploy(nodes)

    def destroy(self):
        logger.info(f"Removing cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.runner.destroy()

    def output(self):
        return self.runner.output()

    @staticmethod
    def _name_check(value):
        p = re.compile(r"^[a-z]([-a-z0-9]*[a-z0-9])?$")
        if p.match(value):
            return value
        else:
            raise AWSNodeError("name must comply with RFC1035")
