##
##

import re
import attr
import logging
from itertools import cycle
from typing import List
import couchformation.azure.driver.constants as C
from couchformation.azure.driver.base import CloudBase
from couchformation.azure.driver.network import Network
from couchformation.azure.driver.instance import Instance
from couchformation.azure.driver.machine import MachineType
from couchformation.azure.driver.disk import Disk
from couchformation.azure.driver.image import Image
from couchformation.azure.network import AzureNetwork
from couchformation.config import NodeList, DeploymentConfig
from couchformation.ssh import SSHUtil
from couchformation.exception import FatalError
from couchformation.provisioner.remote import RemoteProvisioner, ProvisionSet
import couchformation.state as state
from couchformation.state import INSTANCES, AzureInstance, AzureDisk

logger = logging.getLogger('couchformation.azure.node')
logger.addHandler(logging.NullHandler())


class AzureNodeError(FatalError):
    pass


class AzureDeployment(object):

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

        self.az_network = AzureNetwork(self.core)
        self.az_base = CloudBase(self.core)

    def create_nodes(self):
        subnet_list = []
        core = self.core
        offset = 1
        node_count = 0

        state.update(INSTANCES)

        ssh_pub_key_text = SSHUtil().get_ssh_public_key(core.ssh_key)
        rg_name = state.infrastructure.resource_group
        azure_location = self.az_base.region

        for n, zone_state in enumerate(state.infrastructure.zone_list):
            subnet_list.append(dict(
                subnet_id=zone_state['subnet_id'],
                zone=zone_state['zone'],
                subnet=zone_state['subnet'],
            ))

        if len(subnet_list) == 0:
            raise AzureNodeError(f"can not get subnet list, check project settings")

        subnet_cycle = cycle(subnet_list)

        image = Image(core).list_standard(os_id=core.os_id, os_version=core.os_version)
        if not image:
            raise AzureNodeError(f"can not find image for type {core.os_id} {core.os_version}")

        logger.info(f"Using image {image['publisher']}/{image['offer']}/{image['sku']} type {image['os_id']} version {image['os_version']}")

        state.instance_set.name = self.name
        state.instance_set.username = image['os_user']

        offset += node_count

        for n, config in enumerate(self.deployment.config):
            quantity = config.quantity
            machine_type = config.machine_type
            volume_size = config.volume_size
            services = config.services

            machine = MachineType(core).get_machine(config.machine_type, azure_location)
            if not machine:
                raise AzureNodeError(f"can not find machine for type {machine_type}")
            machine_name = machine['name']
            machine_ram = int(machine['memory'] / 1024)
            logger.info(f"Selecting machine type {machine_name}")

            logger.info(f"Deploying node group {n+1} with {quantity} nodes")

            for i in range(int(quantity)):
                node_count += 1
                instance_state = AzureInstance()
                subnet = next(subnet_cycle)
                node_num = i + offset
                node_name = f"{self.name}-node-{node_num:02d}"
                boot_disk = f"{self.name}-boot-{node_num:02d}"
                swap_disk = f"{self.name}-swap-{node_num:02d}"
                data_disk = f"{self.name}-data-{node_num:02d}"
                node_pub_ip = f"{self.name}-node-{node_num:02d}-pub-ip"
                node_nic = f"{self.name}-node-{node_num:02d}-nic"

                swap_tier = self.az_base.disk_size_to_tier(machine_ram)
                disk_tier = self.az_base.disk_size_to_tier(volume_size)

                instance_state.disk_list.clear()
                logger.info(f"Creating disk {swap_disk}")
                swap_resource = Disk(core).create(rg_name, azure_location, subnet['zone'], swap_tier['disk_size'], swap_tier['disk_tier'], swap_disk)
                # noinspection PyTypeChecker
                instance_state.disk_list.append(attr.asdict(AzureDisk(swap_disk, subnet['zone'])))
                logger.info(f"Creating disk {data_disk}")
                data_resource = Disk(core).create(rg_name, azure_location, subnet['zone'], disk_tier['disk_size'], disk_tier['disk_tier'], data_disk)
                # noinspection PyTypeChecker
                instance_state.disk_list.append(attr.asdict(AzureDisk(data_disk, subnet['zone'])))

                logger.info(f"Creating public IP {node_pub_ip}")
                pub_ip_resource = Network(core).create_pub_ip(node_pub_ip, rg_name)
                logger.info(f"Creating NIC {node_nic}")
                nic_resource = Network(core).create_nic(node_nic, subnet['subnet_id'], subnet['zone'], pub_ip_resource.id, rg_name)

                logger.info(f"Creating node {node_name}")
                Instance(core).run(node_name,
                                   image['publisher'],
                                   image['offer'],
                                   image['sku'],
                                   subnet['zone'],
                                   nic_resource.id,
                                   image['os_user'],
                                   ssh_pub_key_text,
                                   rg_name,
                                   boot_disk,
                                   self.az_base.disk_caching(swap_tier['disk_size']),
                                   swap_resource.id,
                                   self.az_base.disk_caching(disk_tier['disk_size']),
                                   data_resource.id,
                                   machine_type=machine_name)

                # noinspection PyTypeChecker
                instance_state.disk_list.append(attr.asdict(AzureDisk(boot_disk, subnet['zone'])))
                instance_state.name = node_name
                instance_state.services = services
                instance_state.zone = subnet['zone']
                instance_state.resource_group = rg_name
                instance_state.node_nic = node_nic
                instance_state.node_pub_ip = node_pub_ip

                nic_details = Network(core).describe_nic(node_nic, rg_name)
                pub_ip_details = Network(core).describe_pub_ip(node_pub_ip, rg_name)
                instance_state.public_ip = pub_ip_details.ip_address
                instance_state.private_ip = nic_details.ip_configurations[0].private_ip_address

                # noinspection PyTypeChecker
                state.instance_set.instance_list.append(attr.asdict(instance_state))
                logger.info(f"Created instance {node_name}")

        state.save()

    def destroy_nodes(self):
        core = self.core

        state.update(INSTANCES)

        for n, instance in reversed(list(enumerate(state.instance_set.instance_list))):
            instance_name = instance['name']
            rg_name = instance['resource_group']
            node_nic = instance['node_nic']
            node_pub_ip = instance['node_pub_ip']
            Instance(core).terminate(instance_name, rg_name)
            logger.info(f"Removed instance {instance_name}")
            Network(core).delete_nic(node_nic, rg_name)
            logger.info(f"Removed NIC {node_nic}")
            Network(core).delete_pub_ip(node_pub_ip, rg_name)
            logger.info(f"Removed public IP {node_pub_ip}")
            for d, disk in reversed(list(enumerate(instance['disk_list']))):
                Disk(core).delete(disk['name'], rg_name)
                logger.info(f"Removed disk {disk['name']}")
            del state.instance_set.instance_list[n]

        state.save()

    def deploy(self):
        self.az_network.create()
        logger.info(f"Creating cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.create_nodes()

    def destroy(self):
        logger.info(f"Removing cloud infrastructure for {self.project} in {C.CLOUD_KEY.upper()}")
        self.destroy_nodes()
        self.az_network.destroy()

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
            raise AzureNodeError("names must only contain letters, numbers, dashes and underscores")

    def validate(self):
        variables = [a for a in dir(self) if not callable(getattr(self, a)) and not a.startswith("__")]
        for variable in variables:
            if getattr(self, variable) is None:
                raise ValueError(f"setting \"{variable}\" is null")
