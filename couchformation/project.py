##
##

import logging
from couchformation.exception import FatalError
from couchformation.aws.node import AWSDeployment
from couchformation.gcp.node import GCPDeployment
from couchformation.azure.node import AzureDeployment
from couchformation.config import get_project_dir
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
            if len(result_list) != number:
                raise ProjectError(f"Partial deployment: deployed {len(result_list)} expected {number}")
            result_list = sorted(result_list, key=lambda d: d['name'])
            private_ip_list = [d['private_ip'] for d in result_list]
            public_ip_list = [d['public_ip'] for d in result_list]
            result_list = [dict(item, private_ip_list=private_ip_list, public_ip_list=public_ip_list) for item in result_list]

            if groups[0].get('connect'):
                connect_list = self.list(api=True, service=groups[0].get('connect'))
                connect_list = sorted(connect_list, key=lambda d: d['name'])
                if len(connect_list) == 0:
                    raise ProjectError(f"Connect: No nodes in service {groups[0].get('connect')}")
                logger.info(f"Connecting service {groups[0].get('name')} to {groups[0].get('connect')}")
                private_connect_list = [d['private_ip'] for d in connect_list]
                result_list = [dict(item, connect=private_connect_list) for item in result_list]

            provisioner = ProvisionerProfile().get(self.provisioner)
            p_module = provisioner.driver
            p_instance = provisioner.module
            p_method = provisioner.method

            p_list = [provisioner.parameter_gen(result, groups[0].as_dict) for result in result_list]

            default = BuildProfile().get('default')

            for step, command in enumerate(default.commands):
                for p_set in p_list:
                    logger.info(f"Provisioning node {p_set.get('name')} - default step #{step + 1}")
                    self.runner.dispatch(p_module, p_instance, p_method, p_set, command, default.root)
                exit_codes = list(self.runner.join())
                if any(n != 0 for n in exit_codes):
                    raise ProjectError(f"Provisioning step failed")

            build = BuildProfile().get(groups[0].get('build'))

            for step, command in enumerate(build.commands):
                for p_set in p_list:
                    logger.info(f"Provisioning node {p_set.get('name')} - build step #{step + 1}")
                    self.runner.dispatch(p_module, p_instance, p_method, p_set, command, build.root)
                exit_codes = list(self.runner.join())
                if any(n != 0 for n in exit_codes):
                    raise ProjectError(f"Provisioning step failed")

    def destroy(self, service=None):
        for groups in reversed(list(NodeGroup(self.options).get_node_groups())):
            if service and groups[0].get('name') != service:
                continue
            number = 0
            for db in groups:
                cloud = db.get('cloud')
                profile = TargetProfile(self.remainder).get(cloud)
                module = profile.node.driver
                instance = profile.node.module
                method = profile.node.destroy
                self.runner.foreground(profile.base.driver, profile.base.module, profile.base.test, db.as_dict)
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

    def remove(self):
        if self.options.name:
            service = self.options.name
        else:
            service = None
        logger.info("Removing All Services" if not service else f"Removing {service}")
        self.destroy(service=service)
        NodeGroup(self.options).remove_node_groups(service)

    def list(self, api=False, service=None):
        return_list = []
        for groups in NodeGroup(self.options).get_node_groups():
            if service and groups[0].get('name') != service:
                continue
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
            if any(d.get('name') is None for d in result_list):
                continue
            result_list = sorted(result_list, key=lambda d: d['name'])
            if not api:
                logger.info(f"Service: {groups[0].get('name')}")
            for result in result_list:
                if not api:
                    logger.info(f"Node: {result.get('name')} "
                                f"Private IP: {result.get('private_ip'):<15} "
                                f"Public IP: {result.get('public_ip'):<15} "
                                f"Services: {result.get('services')}")
                return_list.append(result)
        return return_list

    @property
    def location(self):
        return get_project_dir(self.options.project)
