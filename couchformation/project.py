##
##

import logging
from couchformation.exception import FatalError
from couchformation.aws.node import AWSDeployment
from couchformation.gcp.node import GCPDeployment
from couchformation.azure.node import AzureDeployment
from couchformation.config import get_project_dir
from couchformation.util import dict_merge_list
from couchformation.deployment import NodeGroup
from couchformation.executor.targets import TargetProfile, ProvisionerProfile, BuildProfile
from couchformation.executor.dispatch import JobDispatch

logger = logging.getLogger('couchformation.exec.process')
logger.addHandler(logging.NullHandler())


class ProjectError(FatalError):
    pass


class Project(object):

    def __init__(self, args, remainder):
        self.options = args
        self.remainder = remainder
        self.cloud = self.options.cloud
        self.provisioner = self.options.provisioner
        self.runner = JobDispatch()

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
        profile = TargetProfile(self.remainder).get(self.cloud)
        NodeGroup(self.options).create_node_group(profile.options)

    def add(self):
        logger.info(f"Adding node group to service")
        profile = TargetProfile(self.remainder).get(self.cloud)
        NodeGroup(self.options).add_to_node_group(profile.options)

    def deploy(self):
        for net in NodeGroup(self.options).get_networks():
            logger.info(f"Deploying network for cloud {net.get('cloud')}")
            cloud = net.get('cloud')
            profile = TargetProfile(self.remainder).get(cloud)
            module = profile.network.driver
            instance = profile.network.module
            method = profile.network.deploy
            self.runner.foreground(profile.base.driver, profile.base.module, profile.base.test, net.as_dict)
            self.runner.dispatch(module, instance, method, net.as_dict)
        list(self.runner.join())
        for groups in NodeGroup(self.options).get_node_groups():
            number = 0
            for db in groups:
                cloud = db.get('cloud')
                profile = TargetProfile(self.remainder).get(cloud)
                module = profile.node.driver
                instance = profile.node.module
                method = profile.node.deploy
                for n in range(int(db['quantity'])):
                    number += 1
                    logger.info(f"Deploying service {db.get('name')} node group {db.get('group')} node {number}")
                    parameters = db.as_dict
                    parameters['number'] = number
                    self.runner.dispatch(module, instance, method, parameters)
            result_list = list(self.runner.join())
            combined = dict_merge_list(*result_list)
            for result in result_list:
                provisioner = ProvisionerProfile().get(self.provisioner, result, combined, groups[0].as_dict)
                default = BuildProfile().get('default')
                build = BuildProfile().get(self.options.build)
                module = provisioner.driver
                instance = provisioner.module
                method = provisioner.method
                self.runner.dispatch(module, instance, method, provisioner, default, build)
            list(self.runner.join())

    def destroy(self):
        for groups in NodeGroup(self.options).get_node_groups():
            number = 0
            for db in groups:
                cloud = db.get('cloud')
                profile = TargetProfile(self.remainder).get(cloud)
                module = profile.node.driver
                instance = profile.node.module
                method = profile.node.destroy
                for n in range(int(db['quantity'])):
                    number += 1
                    logger.info(f"Removing service {db.get('name')} node group {db.get('group')} node {number}")
                    parameters = db.as_dict
                    parameters['number'] = number
                    self.runner.dispatch(module, instance, method, parameters)
            list(self.runner.join())
        for net in NodeGroup(self.options).get_networks():
            logger.info(f"Removing network for cloud {net.get('cloud')}")
            cloud = net.get('cloud')
            profile = TargetProfile(self.remainder).get(cloud)
            module = profile.network.driver
            instance = profile.network.module
            method = profile.network.destroy
            self.runner.dispatch(module, instance, method, net.as_dict)
        list(self.runner.join())

    def list(self, api=False):
        for groups in NodeGroup(self.options).get_node_groups():
            number = 0
            for db in groups:
                cloud = db.get('cloud')
                profile = TargetProfile(self.remainder).get(cloud)
                module = profile.node.driver
                instance = profile.node.module
                method = profile.node.info
                for n in range(int(db['quantity'])):
                    number += 1
                    parameters = db.as_dict
                    parameters['number'] = number
                    self.runner.dispatch(module, instance, method, parameters)
            result_list = list(self.runner.join())
            for result in result_list:
                if not api:
                    logger.info(f"Node: {result.get('name')} Private IP: {result.get('private_ip')} Public IP: {result.get('public_ip')}")
                else:
                    yield result

    @property
    def location(self):
        return get_project_dir(self.options.project)
