##
##

import os.path
import re
import logging
import time
from itertools import cycle, islice
from couchformation.aws.driver.image import Image
from couchformation.aws.driver.machine import MachineType
from couchformation.aws.driver.instance import Instance
from couchformation.aws.driver.base import CloudBase
from couchformation.aws.driver.constants import aws_storage_matrix, aws_arch_matrix, PlacementType
from couchformation.aws.driver.dns import DNS
from couchformation.aws.driver.nsg import SecurityGroup
from couchformation.aws.network import AWSNetwork
from couchformation.deployment import MetadataManager
from couchformation.config import get_state_file, get_state_dir, PortSettingSet
from couchformation.exception import FatalError
from couchformation.kvdb import KeyValueStore
from couchformation.util import FileManager, Synchronize, UUIDGen

logger = logging.getLogger('couchformation.aws.node')
logger.addHandler(logging.NullHandler())


class AWSNodeError(FatalError):
    pass


class AWSDeployment(object):

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
        self.os_arch = parameters.get('os_arch') if parameters.get('os_arch') else 'x86_64'
        self.feature = parameters.get('feature')
        self.cloud = parameters.get('cloud')
        self.group = parameters.get('group')
        self.number = parameters.get('number')
        self.machine_type = parameters.get('machine_type')
        self.ports = parameters.get('ports')
        self.allow = parameters.get('allow') if parameters.get('allow') else "0.0.0.0/0"
        self.volume_size = parameters.get('volume_size') if parameters.get('volume_size') else "256"
        self.volume_iops = parameters.get('volume_iops') if parameters.get('volume_iops') \
            else next((aws_storage_matrix[s] for s in aws_storage_matrix if s >= int(self.volume_size)), "3000")
        self.services = parameters.get('services') if parameters.get('services') else "default"

        project_uid = MetadataManager(self.project).project_uid
        self.asset_prefix = f"cf-{project_uid}"
        self.node_name = f"{self.name}-node-{self.number:02d}"
        node_code = UUIDGen().text_hash(self.node_name)
        self.node_encoded = f"{self.asset_prefix}-{node_code}-node"

        filename = get_state_file(self.project, self.name)

        with Synchronize():
            try:
                state_dir = get_state_dir(self.project, self.name)
                if not os.path.exists(state_dir):
                    FileManager().make_dir(state_dir)
            except Exception as err:
                raise AWSNodeError(f"can not create state dir: {err}")

        document = self.node_name
        self.state = KeyValueStore(filename, document)

        CloudBase(self.parameters).test_session()

        self.aws_network = AWSNetwork(self.parameters)

    def check_state(self):
        if self.state.get('instance_id'):
            result = Instance(self.parameters).details(self.state['instance_id'])
            if result is None:
                logger.warning(f"Removing stale state entry for instance {self.state['instance_id']}")
                del self.state['instance_id']
        if self.state.get('node_security_group_id'):
            result = SecurityGroup(self.parameters).details(self.state['node_security_group_id'])
            if result is None:
                logger.warning(f"Removing stale state entry for security group {self.state['node_security_group_id']}")
                del self.state['node_security_group_id']

    def deploy(self):
        self.check_state()
        subnet_list = []
        nsg_list = []

        if self.state.get('instance_id'):
            logger.info(f"Node {self.node_name} already exists")
            return self.state.as_dict

        ssh_key_name = self.aws_network.ssh_key_id
        sg_id = self.aws_network.security_group_id
        nsg_list.append(sg_id)

        for n, zone_state in enumerate(self.aws_network.zones):
            subnet_list.append(dict(
                subnet_id=zone_state[2],
                zone=zone_state[0],
                cidr=zone_state[1],
            ))

        if len(subnet_list) == 0:
            raise AWSNodeError(f"can not get subnet list, check project settings")

        if not self.zone:
            subnet_cycle = cycle(subnet_list)
            subnet = next(islice(subnet_cycle, self.number - 1, None))
        else:
            subnet = next((z for z in subnet_list if z['zone'] == self.zone), None)

        if not subnet:
            raise AWSNodeError(f"Can not determine availability zone (check project settings)")

        image = Image(self.parameters).list_standard(os_id=self.os_id, os_version=self.os_version, architecture=self.os_arch, feature=self.feature)
        if not image:
            raise AWSNodeError(f"can not find image for type {self.os_id} {self.os_version}")

        logger.info(f"Using image {image['name']} type {image['os_id']} version {image['os_version']}")

        self.state['service'] = self.name
        self.state['username'] = image['os_user']

        machine_type = self.machine_type
        volume_iops = int(self.volume_iops)
        volume_size = int(self.volume_size)
        services = self.services

        machine = MachineType(self.parameters).get_machine(self.machine_type, self.os_arch)
        if not machine:
            raise AWSNodeError(f"can not find machine for type {machine_type}")
        machine_name = machine['name']
        machine_ram = int(machine['memory'] / 1024)
        logger.info(f"Selecting machine type {machine_name}")

        placement = PlacementType(aws_arch_matrix[self.os_arch])

        if placement == PlacementType.HOST:
            if not self.state.get('host_id'):
                host_list = Instance(self.parameters).list_hosts(machine_name)
                host_id = next((h['id'] for h in host_list if h['capacity'] == machine['cpu']), None)
                if host_id:
                    logger.info(f"Using dedicated host {host_id}")
                else:
                    host_name = f"{self.project}-host"
                    logger.info(f"Allocating dedicated host for machine type {machine_name}")
                    host_id = Instance(self.parameters).allocate_host(host_name, subnet['zone'], machine_name)
                    logger.info(f"Allocated host {host_id}")
                self.state['host_id'] = host_id
            else:
                host_id = self.state.get('host_id')
        else:
            host_id = None

        if self.ports:
            port_sg_id = self.aws_network.create_node_group_sg(self.name, self.group, self.ports.split(','))
            logger.info(f"Assigning service group security group {port_sg_id}")
            nsg_list.append(port_sg_id)

        build_ports = PortSettingSet().create().get(self.build)
        if build_ports:
            build_sg_id = self.aws_network.create_build_sg(self.build)
            logger.info(f"Assigning build security group {build_sg_id}")
            nsg_list.append(build_sg_id)

        if image['os_id'] == 'windows':
            win_sg_id = self.aws_network.create_win_sg()
            logger.info(f"Assigning windows security group {win_sg_id}")
            nsg_list.append(win_sg_id)
            enable_winrm = True
        else:
            enable_winrm = False

        logger.info(f"Creating node {self.node_name}")
        instance_id = Instance(self.parameters).run(self.node_encoded,
                                                    image['name'],
                                                    ssh_key_name,
                                                    nsg_list,
                                                    subnet['subnet_id'],
                                                    subnet['zone'],
                                                    swap_size=machine_ram,
                                                    data_size=volume_size,
                                                    data_iops=volume_iops,
                                                    instance_type=machine_name,
                                                    placement=placement,
                                                    host_id=host_id,
                                                    enable_winrm=enable_winrm)

        self.state['instance_id'] = instance_id
        self.state['name'] = self.node_encoded
        self.state['services'] = services
        self.state['zone'] = subnet['zone']
        self.aws_network.add_service(self.node_name)

        while True:
            try:
                instance_details = Instance(self.parameters).details(instance_id)
                self.state['public_ip'] = instance_details['PublicIpAddress']
                self.state['private_ip'] = instance_details['PrivateIpAddress']
                break
            except KeyError:
                time.sleep(1)

        if self.aws_network.public_zone and self.aws_network.domain_name and not self.state.get('public_hostname'):
            host_name = f"{self.node_name}.{self.aws_network.domain_name}"
            DNS(self.parameters).add_record(self.aws_network.public_zone, host_name, [self.state['public_ip']])
            self.state['public_zone_id'] = self.aws_network.public_zone
            self.state['public_hostname'] = host_name

        if self.aws_network.private_zone and self.aws_network.domain_name and not self.state.get('private_hostname'):
            host_name = f"{self.node_name}.{self.aws_network.domain_name}"
            DNS(self.parameters).add_record(self.aws_network.private_zone, host_name, [self.state['private_ip']])
            self.state['private_zone_id'] = self.aws_network.private_zone
            self.state['private_hostname'] = host_name

        if image['os_id'] == 'windows':
            password = Instance(self.parameters).get_password(instance_id, self.ssh_key)
            self.state['host_password'] = password

        logger.info(f"Created instance {instance_id}")
        return self.state.as_dict

    def destroy(self):
        if self.state.get('public_hostname'):
            domain_id = self.state['public_zone_id']
            name = self.state['public_hostname']
            ip = self.state['public_ip']
            DNS(self.parameters).delete_record(domain_id, name, [ip])
            logger.info(f"Deleted DNS record for {ip}")
        if self.state.get('private_hostname'):
            domain_id = self.state['private_zone_id']
            name = self.state['private_hostname']
            ip = self.state['private_ip']
            DNS(self.parameters).delete_record(domain_id, name, [ip])
            logger.info(f"Deleted DNS record for {ip}")
        if self.state.get('instance_id'):
            instance_id = self.state['instance_id']
            Instance(self.parameters).terminate(instance_id)
            logger.info(f"Removed instance {instance_id}")
        if self.state.get('host_id'):
            host_id = self.state.get('host_id')
            host = Instance(self.parameters).get_host_by_id(host_id)
            if host['age'] >= 24:
                Instance(self.parameters).release_host(host_id)
                del self.state['host_id']
                logger.info(f"Released host {host_id}")
            else:
                logger.warning(f"Can not remove dedicated host {host_id} age {host['age']} hrs is less than 24")
        if self.state.get('node_security_group_id'):
            sg_id = self.state.get('node_security_group_id')
            SecurityGroup(self.parameters).delete(sg_id)
            del self.state['node_security_group_id']
            logger.info(f"Removing security group {sg_id}")
        self.state.clear()
        self.aws_network.remove_service(self.node_name)

    def info(self):
        return self.state.as_dict

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
