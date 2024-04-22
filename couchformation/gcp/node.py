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
from couchformation.gcp.driver.dns import DNS
from couchformation.gcp.network import GCPNetwork
from couchformation.deployment import MetadataManager
from couchformation.config import get_state_file, get_state_dir, PortSettingSet
from couchformation.ssh import SSHUtil
from couchformation.exception import FatalError
from couchformation.kvdb import KeyValueStore
from couchformation.util import FileManager, Synchronize, UUIDGen

logger = logging.getLogger('couchformation.gcp.node')
logger.addHandler(logging.NullHandler())


class GCPNodeError(FatalError):
    pass


class GCPDeployment(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.name = parameters.get('name')
        self.project = parameters.get('project')
        self.build = parameters.get('build')
        self.region = parameters.get('region')
        self.zone = parameters.get('zone')
        self.auth_mode = parameters.get('auth_mode')
        self.profile = parameters.get('profile')
        self.ssh_key = parameters.get('ssh_key')
        self.os_id = parameters.get('os_id')
        self.os_version = parameters.get('os_version')
        self.feature = parameters.get('feature')
        self.cloud = parameters.get('cloud')
        self.group = parameters.get('group')
        self.number = parameters.get('number')
        self.machine_type = parameters.get('machine_type')
        self.ports = parameters.get('ports')
        self.volume_size = parameters.get('volume_size') if parameters.get('volume_size') else "256"
        self.services = parameters.get('services') if parameters.get('services') else "default"

        project_uid = MetadataManager(self.project).project_uid
        self.asset_prefix = f"cf-{project_uid}"
        self.node_name = f"{self.name}-node-{self.number:02d}"
        self.swap_disk = f"{self.name}-swap-{self.number:02d}"
        self.data_disk = f"{self.name}-data-{self.number:02d}"
        node_code = UUIDGen().text_hash(self.node_name)
        self.node_encoded = f"{self.asset_prefix}-{node_code}-node"
        self.swap_encoded = f"{self.asset_prefix}-{node_code}-swap"
        self.data_encoded = f"{self.asset_prefix}-{node_code}-data"

        filename = get_state_file(self.project, self.name)

        with Synchronize():
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
        self.service_account_email = self.gcp_base.service_account_email
        self.account_email = self.gcp_base.account_email

    def check_state(self):
        if self.state.get('instance_id'):
            result = Instance(self.parameters).find(self.state['instance_id'])
            if result is None:
                logger.warning(f"Removing stale state entry for instance {self.state['instance_id']}")
                del self.state['instance_id']
        if self.state.get('swap_disk'):
            result = Disk(self.parameters).find(self.state['swap_disk'])
            if result is None:
                logger.warning(f"Removing stale state entry for disk {self.state['swap_disk']}")
                del self.state['swap_disk']
        if self.state.get('data_disk'):
            result = Disk(self.parameters).find(self.state['data_disk'])
            if result is None:
                logger.warning(f"Removing stale state entry for disk {self.state['data_disk']}")
                del self.state['data_disk']

    def deploy(self):
        self.check_state()
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

        if not self.zone:
            subnet_cycle = cycle(subnet_list)
            subnet = next(islice(subnet_cycle, self.number - 1, None))
        else:
            subnet = next((z for z in subnet_list if z['zone'] == self.zone), None)

        if not subnet:
            raise GCPNodeError(f"Can not determine availability zone (check project settings)")

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

        if self.feature == "vmp":
            logger.info(f"Enabling nested virtualization")
            virtualization = True
        else:
            virtualization = False

        if self.ports:
            self.gcp_network.create_node_group_sg(self.name, self.group, self.ports.split(','))
            logger.info("Requesting service group firewall rule")

        build_ports = PortSettingSet().create().get(self.build)
        if build_ports:
            self.gcp_network.create_build_sg(self.build)
            logger.info(f"Requesting build {self.build} firewall rule")

        if image['os_id'] == 'windows':
            self.gcp_network.create_win_sg()
            logger.info("Requesting windows firewall rule")

        logger.info(f"Creating disk {self.swap_encoded} ({self.swap_disk})")
        Disk(self.parameters).create(self.swap_encoded, subnet['zone'], machine_ram)
        self.state['swap_disk'] = self.swap_encoded

        logger.info(f"Creating disk {self.data_encoded} ({self.data_disk})")
        Disk(self.parameters).create(self.data_encoded, subnet['zone'], volume_size)
        self.state['data_disk'] = self.data_encoded

        logger.info(f"Creating node {self.node_encoded} ({self.node_name})")
        Instance(self.parameters).run(self.node_encoded,
                                      image['image_project'],
                                      image['name'],
                                      self.service_account_email,
                                      subnet['zone'],
                                      vpc_name,
                                      subnet_name,
                                      image['os_user'],
                                      ssh_pub_key_text,
                                      self.swap_encoded,
                                      self.data_encoded,
                                      machine_type=machine_name,
                                      virtualization=virtualization)

        self.state['instance_id'] = self.node_encoded
        self.state['name'] = self.node_encoded
        self.state['services'] = services
        self.state['zone'] = subnet['zone']
        self.gcp_network.add_service(self.node_name)

        while True:
            try:
                instance_details = Instance(self.parameters).details(self.node_encoded, subnet['zone'])
                self.state['public_ip'] = instance_details['networkInterfaces'][0]['accessConfigs'][0]['natIP']
                self.state['private_ip'] = instance_details['networkInterfaces'][0]['networkIP']
                break
            except KeyError:
                time.sleep(1)
            except TypeError:
                raise GCPNodeError(f"Failed to properly start node {self.node_encoded} - try removing and recreating service")

        if self.gcp_network.public_zone and self.gcp_network.domain_name and not self.state.get('public_hostname'):
            host_name = f"{self.node_name}.{self.gcp_network.domain_name}"
            DNS(self.parameters).add_record(self.gcp_network.public_zone, host_name, [self.state['public_ip']])
            self.state['public_zone_id'] = self.gcp_network.public_zone
            self.state['public_hostname'] = host_name

        if self.gcp_network.private_zone and self.gcp_network.domain_name and not self.state.get('private_hostname'):
            host_name = f"{self.node_name}.{self.gcp_network.domain_name}"
            DNS(self.parameters).add_record(self.gcp_network.private_zone, host_name, [self.state['private_ip']])
            self.state['private_zone_id'] = self.gcp_network.private_zone
            self.state['private_hostname'] = host_name

        if image['os_id'] == 'windows':
            password = Instance(self.parameters).gen_password(image['os_user'],
                                                              self.node_encoded,
                                                              subnet['zone'],
                                                              self.account_email,
                                                              self.ssh_key)
            self.state['host_password'] = password

        logger.info(f"Created instance {self.node_encoded}")
        return self.state.as_dict

    def destroy(self):
        if self.state.get('public_hostname'):
            domain_id = self.state['public_zone_id']
            name = self.state['public_hostname']
            ip = self.state['public_ip']
            DNS(self.parameters).delete_record(domain_id, name)
            logger.info(f"Deleted DNS record for {ip}")
        if self.state.get('private_hostname'):
            domain_id = self.state['private_zone_id']
            name = self.state['private_hostname']
            ip = self.state['private_ip']
            DNS(self.parameters).delete_record(domain_id, name)
            logger.info(f"Deleted DNS record for {ip}")
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
