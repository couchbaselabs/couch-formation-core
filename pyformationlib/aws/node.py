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

        image = Image(self.region, self.auth_mode, self.profile).list_standard(os_id=self.os_id, os_version=self.os_version)

        if len(image) == 0:
            raise AWSNodeError(f"can not find image for os {self.os_id} version {self.os_version}")

        machine = MachineType(self.region, self.auth_mode, self.profile).get_machine(self.machine_type)

        if not machine:
            raise AWSNodeError(f"can not find machine for type {self.machine_type}")

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
