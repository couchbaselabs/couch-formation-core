##
##

import attr
import re
import logging
import time
from itertools import cycle
from typing import List
import couchformation.aws.driver.constants as C
from couchformation.aws.driver.image import Image
from couchformation.aws.driver.machine import MachineType
from couchformation.aws.driver.instance import Instance
from couchformation.aws.driver.base import CloudBase
from couchformation.aws.network import AWSNetwork
from couchformation.config import NodeList, BaseConfig
import couchformation.state as state
from couchformation.state import INSTANCES, AWSInstance
from couchformation.exception import FatalError
from couchformation.deployment import Service
from couchformation.provisioner.remote import RemoteProvisioner, ProvisionSet

logger = logging.getLogger('couchformation.aws.node')
logger.addHandler(logging.NullHandler())


class AWSNodeError(FatalError):
    pass


class AWSDeployment(object):

    def __init__(self, name: str, core: BaseConfig, service: Service):
        self.name = name
        self.service = service
        self.core = core
        self.project = self.core.project
        self.region = self.service.region
        self.auth_mode = self.service.auth_mode
        self.profile = self.service.profile
        self.ssh_key = self.core.ssh_key
        self.os_id = self.service.os_id
        self.os_version = self.service.os_version

        state.config.set(name, service.cloud, core.project_dir)
        state.switch_cloud()

        self._name_check(self.name)
        CloudBase(service).test_session()

        self.aws_network = AWSNetwork(name, core, service)

    def create_nodes(self):
        subnet_list = []
        service = self.service
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

        image = Image(service).list_standard(os_id=service.os_id, os_version=service.os_version)
        if not image:
            raise AWSNodeError(f"can not find image for type {service.os_id} {service.os_version}")

        logger.info(f"Using image {image['name']} type {image['os_id']} version {image['os_version']}")

        state.instance_set.name = self.name
        state.instance_set.username = image['os_user']

        offset += node_count

        for n, config in enumerate(self.service.config):
            quantity = config.quantity
            machine_type = config.machine_type
            volume_iops = int(config.volume_iops)
            volume_size = int(config.volume_size)
            services = config.services

            logger.info(f"Deploying node group {n+1} with {quantity} nodes")

            machine = MachineType(service).get_machine(config.machine_type)
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

                if next((instance for instance in state.instance_set.instance_list if instance['name'] == node_name), None):
                    continue

                logger.info(f"Creating node {node_name}")
                instance_id = Instance(service).run(node_name,
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
                        instance_details = Instance(service).details(instance_id)
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
        service = self.service

        state.update(INSTANCES)

        for n, instance in reversed(list(enumerate(state.instance_set.instance_list))):
            instance_id = instance['instance_id']
            Instance(service).terminate(instance_id)
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
        node_list = NodeList().create(state.instance_set.username, self.ssh_key, state.service_dir(), self.core.private_ip)
        for n, instance_state in enumerate(state.instance_set.instance_list):
            node_name = instance_state['name']
            node_private_ip = instance_state['private_ip']
            node_public_ip = instance_state['public_ip']
            availability_zone = instance_state['zone']
            services = instance_state['services']
            node_list.add(node_name, node_private_ip, node_public_ip, availability_zone, services, self.service.connect_svc, self.service.connect_ip)
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
        variables = [a for a in dir(self) if not callable(getattr(self, a)) and not a.startswith("__")]
        for variable in variables:
            if getattr(self, variable) is None:
                raise ValueError(f"setting \"{variable}\" is null")
