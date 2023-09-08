##
##

import logging
from typing import Union
from pyformationlib.exception import FatalError
from pyformationlib.aws.node import AWSDeployment
from pyformationlib.config import BaseConfig, DeploymentConfig, NodeConfig
from pyformationlib.exec.process import TFRun

logger = logging.getLogger('pyformationlib.exec.process')
logger.addHandler(logging.NullHandler())


class ProjectError(FatalError):
    pass


class Project(object):

    def __init__(self, args: Union[list, dict]):
        self.args = args
        try:
            self._core = BaseConfig().create(args)
            self._deployment = DeploymentConfig.new(self._core)
            self.runner = TFRun(self._core)
            self.saved_deployment = self.runner.get_deployment_cfg()
            if self.saved_deployment and self.saved_deployment.get('core'):
                self._deployment.core.from_dict(self.saved_deployment.get('core'))
            if self.saved_deployment and self.saved_deployment.get('config'):
                for saved_config in self.saved_deployment.get('config'):
                    config = NodeConfig().create(saved_config)
                    self._deployment.add_config(self._deployment.length + 1, config)
        except Exception as err:
            raise ProjectError(f"{err}")

        if self._core.cloud == 'aws':
            self.deployer = AWSDeployment
        else:
            raise ValueError(f"cloud {self._core.cloud} is not supported")

    def create(self):
        self._deployment.reset()
        self.add()

    def add(self):
        logger.info(f"Adding node group to deployment {self._deployment.core.name}")
        config = NodeConfig().create(self.args)
        self._deployment.add_config(self._deployment.length + 1, config)

    def save(self):
        logger.info(f"Saving project {self._deployment.core.project} deployment {self._deployment.core.name}")
        self.runner.store_deployment_cfg(self._deployment)

    def deploy(self):
        logger.info(f"Deploying project {self._deployment.core.project} deployment {self._deployment.core.name}")
        env = self.deployer(self.deployment)
        env.deploy()

    def destroy(self):
        logger.info(f"Removing project {self._deployment.core.project} deployment {self._deployment.core.name}")
        env = self.deployer(self.deployment)
        env.destroy()

    def list(self):
        env = self.deployer(self.deployment)
        return env.list()

    def provision(self, pre_provision_cmds, provision_cmds, post_provision_cmds):
        env = self.deployer(self.deployment)
        env.provision(pre_provision_cmds, provision_cmds, post_provision_cmds)

    @property
    def deployment(self) -> DeploymentConfig:
        return self._deployment
