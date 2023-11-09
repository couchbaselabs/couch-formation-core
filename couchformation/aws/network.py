##
##

import logging
from itertools import cycle
from couchformation.network import NetworkDriver
from couchformation.aws.driver.network import Network, Subnet
from couchformation.aws.driver.sshkey import SSHKey
from couchformation.aws.driver.gateway import InternetGateway
from couchformation.aws.driver.nsg import SecurityGroup
from couchformation.aws.driver.route import RouteTable
import couchformation.aws.driver.constants as C
from couchformation.config import get_state_file, get_state_dir
from couchformation.ssh import SSHUtil
from couchformation.exception import FatalError
from couchformation.kvdb import KeyValueStore
from couchformation.util import FileManager

logger = logging.getLogger('couchformation.aws.network')
logger.addHandler(logging.NullHandler())


class AWSNetworkError(FatalError):
    pass


class AWSNetwork(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.name = parameters.get('name')
        self.project = parameters.get('project')
        self.region = parameters.get('region')
        self.auth_mode = parameters.get('auth_mode')
        self.profile = parameters.get('profile')
        self.ssh_key = parameters.get('ssh_key')
        self.cloud = parameters.get('cloud')

        filename = get_state_file(self.project, 'common')

        try:
            state_dir = get_state_dir(self.project, 'common')
            FileManager().make_dir(state_dir)
        except Exception as err:
            raise AWSNetworkError(f"can not create state dir: {err}")

        document = f"network:{self.cloud}"
        self.state = KeyValueStore(filename, document)

        self.aws_network = Network(self.parameters)

    def create_vpc(self):
        cidr_util = NetworkDriver()
        vpc_name = f"{self.project}-vpc"
        ig_name = f"{self.project}-gw"
        rt_name = f"{self.project}-rt"
        sg_name = f"{self.project}-sg"
        key_name = f"{self.project}-key"

        for net in self.aws_network.cidr_list:
            cidr_util.add_network(net)

        zone_list = self.aws_network.zones()

        ssh_pub_key_text = SSHUtil().get_ssh_public_key(self.ssh_key)

        try:

            if not self.state.get('vpc_id'):
                vpc_cidr = cidr_util.get_next_network()
                vpc_id = Network(self.parameters).create(vpc_name, vpc_cidr)
                self.state['vpc_id'] = vpc_id
                self.state['vpc_cidr'] = vpc_cidr
                logger.info(f"Created VPC {vpc_id}")
            else:
                vpc_id = self.state.get('vpc_id')
                vpc_cidr = self.state.get('vpc_cidr')
                cidr_util.set_active_network(vpc_cidr)

            subnet_list = list(cidr_util.get_next_subnet())
            subnet_cycle = cycle(subnet_list[1:])

            if not self.state.get('security_group_id'):
                sg_id = SecurityGroup(self.parameters).create(sg_name, f"Couch Formation project {self.profile}", vpc_id)
                SecurityGroup(self.parameters).add_ingress(sg_id, "-1", 0, 0, vpc_cidr)
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 22, 22, "0.0.0.0/0")
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 8091, 8097, "0.0.0.0/0")
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 9123, 9123, "0.0.0.0/0")
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 9140, 9140, "0.0.0.0/0")
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 11210, 11210, "0.0.0.0/0")
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 11280, 11280, "0.0.0.0/0")
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 11207, 11207, "0.0.0.0/0")
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 18091, 18097, "0.0.0.0/0")
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 4984, 4986, "0.0.0.0/0")
                self.state['security_group_id'] = sg_id
                logger.info(f"Created security group {sg_id}")

            if not self.state.get('ssh_key'):
                ssh_key_name = SSHKey(self.parameters).create(key_name, ssh_pub_key_text)
                self.state['ssh_key'] = ssh_key_name
                logger.info(f"Created SSH Key {ssh_key_name}")

            if not self.state.get('internet_gateway_id'):
                ig_id = InternetGateway(self.parameters).create(ig_name, vpc_id)
                self.state['internet_gateway_id'] = ig_id
                logger.info(f"Created internet gateway {ig_id}")
            else:
                ig_id = self.state.get('internet_gateway_id')

            if not self.state.get('route_table_id'):
                rt_id = RouteTable(self.parameters).create(rt_name, vpc_id)
                self.state['route_table_id'] = rt_id
                RouteTable(self.parameters).add_route("0.0.0.0/0", ig_id, rt_id)
                logger.info(f"Created route table {rt_id}")
            else:
                rt_id = self.state.get('route_table_id')

            for n, zone in enumerate(zone_list):
                if self.state.list_exists('zone', zone):
                    continue
                while True:
                    network_cidr = next(subnet_cycle)
                    if not self.state.list_exists('zone', network_cidr):
                        break
                subnet_name = f"{self.project}-subnet-{n+1:02d}"
                subnet_id = Subnet(self.parameters).create(subnet_name, vpc_id, zone, network_cidr)
                RouteTable(self.parameters).associate(rt_id, subnet_id)
                self.state.list_add('zone', zone, network_cidr, subnet_id)
                logger.info(f"Created subnet {subnet_id} in zone {zone}")

        except Exception as err:
            raise AWSNetworkError(f"Error creating VPC: {err}")

    def destroy_vpc(self):
        if self.state.list_len('services') > 0:
            logger.info(f"Active services, leaving project network in place")
            return

        try:

            for n, zone_state in reversed(list(enumerate(self.state.list_get('zone')))):
                subnet_id = zone_state[2]
                Subnet(self.parameters).delete(subnet_id)
                self.state.list_remove('zone', zone_state[0])
                logger.info(f"Removed subnet {subnet_id}")

            if self.state.get('route_table_id'):
                rt_id = self.state.get('route_table_id')
                RouteTable(self.parameters).delete(rt_id)
                del self.state['route_table_id']
                logger.info(f"Removed route table {rt_id}")

            if self.state.get('internet_gateway_id'):
                ig_id = self.state.get('internet_gateway_id')
                InternetGateway(self.parameters).delete(ig_id)
                del self.state['internet_gateway_id']
                logger.info(f"Removing internet gateway {ig_id}")

            if self.state.get('security_group_id'):
                sg_id = self.state.get('security_group_id')
                SecurityGroup(self.parameters).delete(sg_id)
                del self.state['security_group_id']
                logger.info(f"Removing security group {sg_id}")

            if self.state.get('vpc_id'):
                vpc_id = self.state.get('vpc_id')
                Network(self.parameters).delete(vpc_id)
                del self.state['vpc_id']
                del self.state['vpc_cidr']
                logger.info(f"Removing VPC {vpc_id}")

            if self.state.get('ssh_key'):
                ssh_key_name = self.state.get('ssh_key')
                SSHKey(self.parameters).delete(ssh_key_name)
                del self.state['ssh_key']
                logger.info(f"Removing key pair {ssh_key_name}")

        except Exception as err:
            raise AWSNetworkError(f"Error removing VPC: {err}")

    def create(self):
        logger.info(f"Creating cloud network for {self.project} in {C.CLOUD_KEY.upper()}")
        self.create_vpc()

    def destroy(self):
        logger.info(f"Removing cloud network for {self.project} in {C.CLOUD_KEY.upper()}")
        self.destroy_vpc()

    def get(self, key):
        return self.state.get(key)

    @property
    def ssh_key_id(self):
        return self.state.get('ssh_key')

    @property
    def security_group_id(self):
        return self.state.get('security_group_id')

    @property
    def zones(self):
        return self.state.list_get('zone')

    def add_service(self, name):
        self.state.list_add('services', name)

    def remove_service(self, name):
        self.state.list_remove('services', name)
