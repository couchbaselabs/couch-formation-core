##
##

import attr
import re
import logging
import time
from itertools import cycle
from typing import List
from couchformation.exec.process import TFRun
import couchformation.aws.driver.constants as C
from couchformation.aws.driver.image import Image
from couchformation.aws.driver.machine import MachineType
from couchformation.aws.driver.instance import Instance
from couchformation.aws.driver.base import CloudBase
from couchformation.aws.network import AWSNetwork
from couchformation.config import NodeList, DeploymentConfig
import couchformation.state as state
from couchformation.state import INSTANCES, AWSInstance
from couchformation.exception import FatalError
from couchformation.provisioner.remote import RemoteProvisioner, ProvisionSet

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

        state.core = self.core
        state.switch_cloud()

        self._name_check(self.name)
        CloudBase(self.core).test_session()
        self.runner = TFRun(self.core)

        self.aws_network = AWSNetwork(self.core)

    def create_nodes(self):
        subnet_list = []
        core = self.core
        offset = 1
        node_count = 0

        state.update(INSTANCES)

        ssh_key_name = state.infrastructure.ssh_key
        sg_id = state.infrastructure.security_group_id

        for n, zone_state in enumerate(state.infrastructure.zone_list):
            subnet_list.append(dict(
                subnet_id=zone_state['subnet_id'],
                zone=zone_state['zone'],
                cidr=zone_state['cidr'],
            ))

        if len(subnet_list) == 0:
            raise AWSNodeError(f"can not get subnet list, check project settings")

        subnet_cycle = cycle(subnet_list)

        image = Image(core).list_standard(os_id=core.os_id, os_version=core.os_version)
        if not image:
            raise AWSNodeError(f"can not find image for type {core.os_id} {core.os_version}")

        logger.info(f"Using image {image['name']} type {image['os_id']} version {image['os_version']}")

        state.instance_set.name = self.name
        state.instance_set.username = image['os_user']

        offset += node_count

        for n, config in enumerate(self.deployment.config):
            quantity = config.quantity
            machine_type = config.machine_type
            volume_iops = int(config.volume_iops)
            volume_size = int(config.volume_size)
            services = config.services

            logger.info(f"Deploying node group {n+1} with {quantity} nodes")

            machine = MachineType(core).get_machine(config.machine_type)
            if not machine:
                raise AWSNodeError(f"can not find machine for type {machine_type}")
            machine_name = machine['name']
            machine_ram = int(machine['memory'] / 1024)
            logger.info(f"Selecting machine type {machine_name}")

            for i in range(int(quantity)):
                node_count += 1
                instance_state = AWSInstance()
                subnet = next(subnet_cycle)
                node_num = i + offset
                node_name = f"{self.name}-node-{node_num:02d}"

                logger.info(f"Creating node {node_name}")
                instance_id = Instance(core).run(node_name,
                                                 image['name'],
                                                 ssh_key_name,
                                                 sg_id,
                                                 subnet['subnet_id'],
                                                 subnet['zone'],
                                                 swap_size=machine_ram,
                                                 data_size=volume_size,
                                                 data_iops=volume_iops,
                                                 instance_type=machine_name)

                instance_state.instance_id = instance_id
                instance_state.name = node_name
                instance_state.services = services
                instance_state.zone = subnet['zone']

                while True:
                    try:
                        instance_details = Instance(core).details(instance_id)
                        instance_state.public_ip = instance_details['PublicIpAddress']
                        instance_state.private_ip = instance_details['PrivateIpAddress']
                        break
                    except KeyError:
                        time.sleep(1)

                # noinspection PyTypeChecker
                state.instance_set.instance_list.append(attr.asdict(instance_state))
                logger.info(f"Created instance {instance_id}")

        state.save()

    def destroy_nodes(self):
        core = self.core

        state.update(INSTANCES)

        for n, instance in reversed(list(enumerate(state.instance_set.instance_list))):
            instance_id = instance['instance_id']
            Instance(core).terminate(instance_id)
            del state.instance_set.instance_list[n]
            logger.info(f"Removed instance {instance_id}")

        state.save()

    def deploy(self):
        self.aws_network.create()
        logger.info(f"Creating cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.create_nodes()

    def destroy(self):
        logger.info(f"Removing cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.destroy_nodes()
        self.aws_network.destroy()

    @staticmethod
    def output():
        state.instances_display()

    def list(self) -> NodeList:
        node_list = NodeList().create(state.instance_set.username, self.ssh_key, self.core.working_dir, self.core.private_ip)
        for n, instance_state in enumerate(state.instance_set.instance_list):
            node_name = instance_state['name']
            node_private_ip = instance_state['private_ip']
            node_public_ip = instance_state['public_ip']
            availability_zone = instance_state['zone']
            services = instance_state['services']
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
