##
##

import re
import logging
import time
from itertools import cycle, islice
from couchformation.gcp.driver.base import CloudBase
from couchformation.gcp.driver.instance import Instance
from couchformation.gcp.driver.machine import MachineType
from couchformation.gcp.driver.disk import Disk
from couchformation.gcp.driver.image import Image
from couchformation.gcp.network import GCPNetwork
from couchformation.config import get_state_file, get_state_dir
from couchformation.ssh import SSHUtil
from couchformation.exception import FatalError
from couchformation.kvdb import KeyValueStore
from couchformation.util import FileManager


logger = logging.getLogger('couchformation.gcp.node')
logger.addHandler(logging.NullHandler())


class GCPNodeError(FatalError):
    pass


class GCPDeployment(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.name = parameters.get('name')
        self.project = parameters.get('project')
        self.region = parameters.get('region')
        self.auth_mode = parameters.get('auth_mode')
        self.profile = parameters.get('profile')
        self.ssh_key = parameters.get('ssh_key')
        self.os_id = parameters.get('os_id')
        self.os_version = parameters.get('os_version')
        self.cloud = parameters.get('cloud')
        self.number = parameters.get('number')
        self.machine_type = parameters.get('machine_type')
        self.volume_size = parameters.get('volume_size') if parameters.get('volume_size') else "256"
        self.services = parameters.get('services') if parameters.get('services') else "default"
        self.node_name = f"{self.name}-node-{self.number:02d}"
        self.swap_disk = f"{self.name}-swap-{self.number:02d}"
        self.data_disk = f"{self.name}-data-{self.number:02d}"

        filename = get_state_file(self.project, self.name)

        try:
            state_dir = get_state_dir(self.project, self.name)
            FileManager().make_dir(state_dir)
        except Exception as err:
            raise GCPNodeError(f"can not create state dir: {err}")

        document = self.node_name
        self.state = KeyValueStore(filename, document)

        self.gcp_network = GCPNetwork(self.parameters)
        self.gcp_base = CloudBase(self.parameters)

        self.gcp_project = self.gcp_base.gcp_project
        self.gcp_account_email = self.gcp_base.gcp_account_email
        self.gcp_auth_file = self.gcp_base.auth_file

    def deploy(self):
        subnet_list = []

        if self.state.get('instance_id'):
            logger.info(f"Node {self.node_name} already exists")
            return self.state.as_dict

        ssh_pub_key_text = SSHUtil().get_ssh_public_key(self.ssh_key)
        vpc_name = self.gcp_network.network
        subnet_name = self.gcp_network.subnet

        for n, zone_state in enumerate(self.gcp_network.zones):
            subnet_list.append(dict(
                subnet_id=zone_state[1],
                zone=zone_state[0],
            ))

        if len(subnet_list) == 0:
            raise GCPNodeError(f"can not get subnet list, check project settings")

        subnet_cycle = cycle(subnet_list)
        subnet = next(islice(subnet_cycle, self.number - 1, None))

        image = Image(self.parameters).list_standard(os_id=self.os_id, os_version=self.os_version)
        if not image:
            raise GCPNodeError(f"can not find image for type {self.os_id} {self.os_version}")

        logger.info(f"Using image {image['name']} type {image['os_id']} version {image['os_version']}")

        self.state['service'] = self.name
        self.state['username'] = image['os_user']

        machine_type = self.machine_type
        volume_size = self.volume_size
        services = self.services

        machine = MachineType(self.parameters).get_machine(self.machine_type, subnet['zone'])
        if not machine:
            raise GCPNodeError(f"can not find machine for type {machine_type}")
        machine_name = machine['name']
        machine_ram = str(machine['memory'] / 1024)
        logger.info(f"Selecting machine type {machine_name}")

        Disk(self.parameters).create(self.swap_disk, subnet['zone'], machine_ram)
        self.state['swap_disk'] = self.swap_disk
        Disk(self.parameters).create(self.data_disk, subnet['zone'], volume_size)
        self.state['data_disk'] = self.data_disk

        logger.info(f"Creating node {self.node_name}")
        Instance(self.parameters).run(self.node_name,
                                      image['image_project'],
                                      image['name'],
                                      self.gcp_base.gcp_account_email,
                                      subnet['zone'],
                                      vpc_name,
                                      subnet_name,
                                      image['os_user'],
                                      ssh_pub_key_text,
                                      self.swap_disk,
                                      self.data_disk,
                                      machine_type=machine_name)

        self.state['instance_id'] = self.node_name
        self.state['name'] = self.node_name
        self.state['services'] = services
        self.state['zone'] = subnet['zone']
        self.gcp_network.add_service(self.node_name)

        while True:
            try:
                instance_details = Instance(self.parameters).details(self.node_name, subnet['zone'])
                self.state['public_ip'] = instance_details['networkInterfaces'][0]['accessConfigs'][0]['natIP']
                self.state['private_ip'] = instance_details['networkInterfaces'][0]['networkIP']
                break
            except KeyError:
                time.sleep(1)

        logger.info(f"Created instance {self.node_name}")
        return self.state.as_dict

    def destroy(self):
        if self.state.get('instance_id'):
            instance_name = self.state['instance_id']
            zone = self.state['zone']
            Instance(self.parameters).terminate(instance_name, zone)
            logger.info(f"Removed instance {instance_name}")
            Disk(self.parameters).delete(self.state['swap_disk'], zone)
            logger.info(f"Removed disk {self.state['swap_disk']}")
            Disk(self.parameters).delete(self.state['data_disk'], zone)
            logger.info(f"Removed disk {self.state['data_disk']}")
            self.state.clear()
            self.gcp_network.remove_service(self.node_name)
            logger.info(f"Removed instance {instance_name}")

    def info(self):
        return self.state.as_dict

    @staticmethod
    def _name_check(value):
        p = re.compile(r"^[a-z]([-_a-z0-9]*[a-z0-9])?$")
        if p.match(value):
            return value
        else:
            raise GCPNodeError("names must only contain letters, numbers, dashes and underscores")
