##
##

import logging
from couchformation.exception import FatalError
from couchformation.aws.node import AWSDeployment
from couchformation.gcp.node import GCPDeployment
from couchformation.azure.node import AzureDeployment
from couchformation.config import Parameters
from couchformation.deployment import Deployment
import couchformation.constants as C
import couchformation.state as state

logger = logging.getLogger('couchformation.exec.process')
logger.addHandler(logging.NullHandler())


class ProjectError(FatalError):
    pass


class Project(object):

    def __init__(self, args):
        self.parameters = Parameters().create(args)
        try:
            self.dpmt = Deployment(self.parameters)
        except Exception as err:
            raise ProjectError(f"{err}")

    @staticmethod
    def deployer(cloud: str):
        if cloud == 'aws':
            return AWSDeployment
        elif cloud == 'gcp':
            return GCPDeployment
        elif cloud == 'azure':
            return AzureDeployment
        else:
            raise ValueError(f"cloud {cloud} is not supported")

    def create(self):
        logger.info(f"Creating new service")
        self.dpmt.store_config(overwrite=True)

    def add(self):
        logger.info(f"Adding node group to service")
        self.dpmt.store_config()

    def save(self):
        logger.info(f"Saving deployment")
        self.dpmt.to_file()

    def deploy(self):
        for name, core, service in self.dpmt.services:
            if self.parameters.name and self.parameters.name != name:
                continue
            logger.info(f"Deploying service {name}")
            deployer = self.deployer(service.cloud)
            env = deployer(name, core, service)
            env.deploy()

    def destroy(self):
        for name, core, service in self.dpmt.services:
            if self.parameters.name and self.parameters.name != name:
                continue
            logger.info(f"Removing service {name}")
            deployer = self.deployer(service.cloud)
            env = deployer(name, core, service)
            env.destroy()

    def list(self):
        ip_list = {}
        for name, core, service in self.dpmt.services:
            deployer = self.deployer(service.cloud)
            env = deployer(name, core, service)
            ip_list.update({name: env.list()})
        return ip_list

    def provision(self):
        state.services.import_list(self.list())
        for name, core, service in self.dpmt.services:
            if self.parameters.name and self.parameters.name != name:
                continue
            deployer = self.deployer(service.cloud)
            env = deployer(name, core, service)
            provision_cmds = C.provisioners.get(service.model)
            if provision_cmds:
                env.provision(provision_cmds.get('pre_provision', []), provision_cmds.get('provision', []), provision_cmds.get('post_provision', []))

    @property
    def deployment(self) -> Deployment:
        return self.dpmt
