##
##

import re
import logging
import time
from itertools import cycle, islice
from couchformation.aws.driver.image import Image
from couchformation.aws.driver.machine import MachineType
from couchformation.aws.driver.instance import Instance
from couchformation.aws.driver.base import CloudBase
from couchformation.aws.network import AWSNetwork
from couchformation.config import get_state_file, get_state_dir
from couchformation.exception import FatalError
from couchformation.kvdb import KeyValueStore
from couchformation.util import FileManager

logger = logging.getLogger('couchformation.aws.node')
logger.addHandler(logging.NullHandler())


class AWSNodeError(FatalError):
    pass


class AWSDeployment(object):

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
        self.volume_iops = parameters.get('volume_iops') if parameters.get('volume_iops') else "3000"
        self.volume_size = parameters.get('volume_size') if parameters.get('volume_size') else "256"
        self.services = parameters.get('services') if parameters.get('services') else "default"
        self.node_name = f"{self.name}-node-{self.number:02d}"

        filename = get_state_file(self.project, self.name)

        try:
            state_dir = get_state_dir(self.project, self.name)
            FileManager().make_dir(state_dir)
        except Exception as err:
            raise AWSNodeError(f"can not create state dir: {err}")

        document = self.node_name
        self.state = KeyValueStore(filename, document)

        CloudBase(self.parameters).test_session()

        self.aws_network = AWSNetwork(self.parameters)

    def deploy(self):
        subnet_list = []

        if self.state.get('instance_id'):
            logger.info(f"Node {self.node_name} already exists")
            return self.state.as_dict

        ssh_key_name = self.aws_network.ssh_key_id
        sg_id = self.aws_network.security_group_id

        for n, zone_state in enumerate(self.aws_network.zones):
            subnet_list.append(dict(
                subnet_id=zone_state[2],
                zone=zone_state[0],
                cidr=zone_state[1],
            ))

        if len(subnet_list) == 0:
            raise AWSNodeError(f"can not get subnet list, check project settings")

        subnet_cycle = cycle(subnet_list)
        subnet = next(islice(subnet_cycle, self.number - 1, None))

        image = Image(self.parameters).list_standard(os_id=self.os_id, os_version=self.os_version)
        if not image:
            raise AWSNodeError(f"can not find image for type {self.os_id} {self.os_version}")

        logger.info(f"Using image {image['name']} type {image['os_id']} version {image['os_version']}")

        self.state['service'] = self.name
        self.state['username'] = image['os_user']

        machine_type = self.machine_type
        volume_iops = int(self.volume_iops)
        volume_size = int(self.volume_size)
        services = self.services

        machine = MachineType(self.parameters).get_machine(self.machine_type)
        if not machine:
            raise AWSNodeError(f"can not find machine for type {machine_type}")
        machine_name = machine['name']
        machine_ram = int(machine['memory'] / 1024)
        logger.info(f"Selecting machine type {machine_name}")

        logger.info(f"Creating node {self.node_name}")
        instance_id = Instance(self.parameters).run(self.node_name,
                                                    image['name'],
                                                    ssh_key_name,
                                                    sg_id,
                                                    subnet['subnet_id'],
                                                    subnet['zone'],
                                                    swap_size=machine_ram,
                                                    data_size=volume_size,
                                                    data_iops=volume_iops,
                                                    instance_type=machine_name)

        self.state['instance_id'] = instance_id
        self.state['name'] = self.node_name
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

        logger.info(f"Created instance {instance_id}")
        return self.state.as_dict

    def destroy(self):
        if self.state.get('instance_id'):
            instance_id = self.state['instance_id']
            Instance(self.parameters).terminate(instance_id)
            self.state.clear()
            self.aws_network.remove_service(self.node_name)
            logger.info(f"Removed instance {instance_id}")

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
