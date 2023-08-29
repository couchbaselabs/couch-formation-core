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
from pyformationlib.aws.network import AWSNetwork, AWSNetworkConfig
from pyformationlib.ssh import SSHUtil
from pyformationlib.common.config.resources import Output, OutputValue
from pyformationlib.aws.config.node import (AWSInstance, BlockDevice, EbsElements, RootElements, NodeConfiguration, TerraformElement, RequiredProvider, AWSTerraformProvider)

logger = logging.getLogger('pyformationlib.aws.node')
logger.addHandler(logging.NullHandler())


@attr.s
class AWSNodeConfig:
    project: Optional[str] = attr.ib(default=None)
    name: Optional[str] = attr.ib(default=None)
    region: Optional[str] = attr.ib(default=None)
    ami_id: Optional[str] = attr.ib(default=None)
    ssh_user: Optional[str] = attr.ib(default=None)
    ssh_key: Optional[str] = attr.ib(default=None)
    machine_type: Optional[str] = attr.ib(default=None)
    volume_iops: Optional[str] = attr.ib(default=None)
    volume_size: Optional[str] = attr.ib(default=None)
    volume_type: Optional[str] = attr.ib(default=None)
    auth_mode: Optional[AuthMode] = attr.ib(default=AuthMode.default)
    profile: Optional[str] = attr.ib(default='default')

    @classmethod
    def create(cls,
               project: str,
               name: str,
               region: str,
               ami_id: str,
               ssh_user: str,
               ssh_key: str,
               machine_type: str,
               volume_iops: str,
               volume_size: str,
               volume_type: str,
               auth_mode: AuthMode = AuthMode.default,
               profile: str = 'default'):
        return cls(project,
                   name,
                   region,
                   ami_id,
                   ssh_user,
                   ssh_key,
                   machine_type,
                   volume_iops,
                   volume_size,
                   volume_type,
                   auth_mode,
                   profile
                   )


class AWSNode(object):

    def __init__(self, config: AWSNodeConfig):
        self.project = config.project
        self.region = config.region
        self.auth_mode = config.auth_mode
        self.profile = config.profile
        self.name = config.name
        self.ami_id = config.ami_id
        self.ssh_user = config.ssh_user
        self.ssh_key = config.ssh_key

        net_config = AWSNetworkConfig().create(
            self.project,
            self.region,
            self.auth_mode
        )
        self.aws_network = AWSNetwork(net_config)

    def config_gen(self):
        ssh_pub_key_text = SSHUtil().get_ssh_public_key(self.ssh_key)
        vpc_data = self.aws_network.output()
        return {}

    def create(self, location: str = None):
        runner = TFRun(self.project, 'network', location)
        nodes = self.config_gen()
        logger.info(f"Creating cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        runner.deploy(nodes)

    def destroy(self, location: str = None):
        runner = TFRun(self.project, 'network', location)
        logger.info(f"Removing cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        runner.destroy()

    def output(self, location: str = None):
        runner = TFRun(self.project, 'network', location)
        return runner.output()
