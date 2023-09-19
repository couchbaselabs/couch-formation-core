##
##

import re
import logging
import time
import attr
from itertools import cycle
from typing import List
import couchformation.gcp.driver.constants as C
from couchformation.gcp.driver.base import CloudBase
from couchformation.gcp.driver.instance import Instance
from couchformation.gcp.driver.machine import MachineType
from couchformation.gcp.driver.disk import Disk
from couchformation.gcp.driver.image import Image
from couchformation.gcp.network import GCPNetwork
from couchformation.config import NodeList, DeploymentConfig
from couchformation.ssh import SSHUtil
from couchformation.exception import FatalError
import couchformation.state as state
from couchformation.state import INSTANCES, GCPInstance, GCPDisk
from couchformation.provisioner.remote import RemoteProvisioner, ProvisionSet

logger = logging.getLogger('couchformation.gcp.node')
logger.addHandler(logging.NullHandler())


class GCPNodeError(FatalError):
    pass


class GCPDeployment(object):

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

        self._name_check(self.name)
        CloudBase(self.core).test_session()

        state.core = self.core
        state.switch_cloud()

        self.gcp_network = GCPNetwork(self.core)
        self.gcp_base = CloudBase(self.core)

        self.gcp_project = self.gcp_base.gcp_project
        self.gcp_account_email = self.gcp_base.gcp_account_email
        self.gcp_auth_file = self.gcp_base.auth_file

    def create_nodes(self):
        subnet_list = []
        core = self.core
        offset = 1
        node_count = 0

        state.update(INSTANCES)

        ssh_pub_key_text = SSHUtil().get_ssh_public_key(core.ssh_key)
        vpc_name = state.infrastructure.network
        subnet_name = state.infrastructure.subnet

        for n, zone_state in enumerate(state.infrastructure.zone_list):
            subnet_list.append(dict(
                subnet_id=zone_state['subnet'],
                zone=zone_state['zone'],
            ))

        if len(subnet_list) == 0:
            raise GCPNodeError(f"can not get subnet list, check project settings")

        subnet_cycle = cycle(subnet_list)

        image = Image(core).list_standard(os_id=core.os_id, os_version=core.os_version)
        if not image:
            raise GCPNodeError(f"can not find image for type {core.os_id} {core.os_version}")

        logger.info(f"Using image {image['name']} type {image['os_id']} version {image['os_version']}")

        state.instance_set.name = self.name
        state.instance_set.username = image['os_user']

        offset += node_count

        for n, config in enumerate(self.deployment.config):
            quantity = config.quantity
            machine_type = config.machine_type
            volume_size = config.volume_size
            services = config.services

            logger.info(f"Deploying node group {n+1} with {quantity} nodes")

            for i in range(int(quantity)):
                node_count += 1
                instance_state = GCPInstance()
                subnet = next(subnet_cycle)
                node_num = i + offset
                node_name = f"{self.name}-node-{node_num:02d}"
                swap_disk = f"{self.name}-swap-{node_num:02d}"
                data_disk = f"{self.name}-data-{node_num:02d}"

                machine = MachineType(core).get_machine(config.machine_type, subnet['zone'])
                if not machine:
                    raise GCPNodeError(f"can not find machine for type {machine_type}")
                machine_name = machine['name']
                machine_ram = str(machine['memory'] / 1024)
                logger.info(f"Selecting machine type {machine_name}")

                instance_state.disk_list.clear()
                logger.info(f"Creating disk {swap_disk}")
                Disk(core).create(swap_disk, subnet['zone'], machine_ram)
                # noinspection PyTypeChecker
                instance_state.disk_list.append(attr.asdict(GCPDisk(swap_disk, subnet['zone'])))
                logger.info(f"Creating disk {data_disk}")
                Disk(core).create(data_disk, subnet['zone'], volume_size)
                # noinspection PyTypeChecker
                instance_state.disk_list.append(attr.asdict(GCPDisk(data_disk, subnet['zone'])))

                logger.info(f"Creating node {node_name}")
                Instance(core).run(node_name,
                                   image['image_project'],
                                   image['name'],
                                   self.gcp_base.gcp_account_email,
                                   subnet['zone'],
                                   vpc_name,
                                   subnet_name,
                                   image['os_user'],
                                   ssh_pub_key_text,
                                   swap_disk,
                                   data_disk,
                                   machine_type=machine_name)

                instance_state.name = node_name
                instance_state.services = services
                instance_state.zone = subnet['zone']

                while True:
                    try:
                        instance_details = Instance(core).details(node_name, subnet['zone'])
                        instance_state.public_ip = instance_details['networkInterfaces'][0]['accessConfigs'][0]['natIP']
                        instance_state.private_ip = instance_details['networkInterfaces'][0]['networkIP']
                        break
                    except KeyError:
                        time.sleep(1)

                # noinspection PyTypeChecker
                state.instance_set.instance_list.append(attr.asdict(instance_state))
                logger.info(f"Created instance {node_name}")

        state.save()

    def destroy_nodes(self):
        core = self.core

        state.update(INSTANCES)

        for n, instance in reversed(list(enumerate(state.instance_set.instance_list))):
            instance_name = instance['name']
            zone = instance['zone']
            Instance(core).terminate(instance_name, zone)
            logger.info(f"Removed instance {instance_name}")
            for d, disk in reversed(list(enumerate(instance['disk_list']))):
                Disk(core).delete(disk['name'], disk['zone'])
                logger.info(f"Removed disk {disk['name']}")
            del state.instance_set.instance_list[n]

        state.save()

    def deploy(self):
        self.gcp_network.create()
        logger.info(f"Creating cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.create_nodes()

    def destroy(self):
        logger.info(f"Removing cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.destroy_nodes()
        self.gcp_network.destroy()

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
    def _name_check(value):
        p = re.compile(r"^[a-z]([-_a-z0-9]*[a-z0-9])?$")
        if p.match(value):
            return value
        else:
            raise GCPNodeError("names must only contain letters, numbers, dashes and underscores")

    def validate(self):
        variables = [a for a in dir(self) if not callable(getattr(self, a)) and not a.startswith("__")]
        for variable in variables:
            if getattr(self, variable) is None:
                raise ValueError(f"setting \"{variable}\" is null")
