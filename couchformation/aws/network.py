##
##

import os
import logging
import random
import string
from itertools import cycle
from couchformation.network import NetworkDriver
from couchformation.aws.driver.network import Network, Subnet
from couchformation.aws.driver.sshkey import SSHKey
from couchformation.aws.driver.gateway import InternetGateway
from couchformation.aws.driver.nsg import SecurityGroup
from couchformation.aws.driver.route import RouteTable
from couchformation.aws.driver.dns import DNS
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
        self.domain = parameters.get('domain')

        filename = get_state_file(self.project, f"network-{self.region}")

        try:
            state_dir = get_state_dir(self.project, f"network-{self.region}")
            if not os.path.exists(state_dir):
                FileManager().make_dir(state_dir)
        except Exception as err:
            raise AWSNetworkError(f"can not create state dir: {err}")

        document = f"network:{self.cloud}"
        self.state = KeyValueStore(filename, document)

        self.aws_network = Network(self.parameters)

        self.vpc_name = f"{self.project}-vpc"
        self.ig_name = f"{self.project}-gw"
        self.rt_name = f"{self.project}-rt"
        self.sg_name = f"{self.project}-sg"
        self.key_name = f"{self.project}-key"

    def check_state(self):
        for n, zone_state in reversed(list(enumerate(self.state.list_get('zone')))):
            subnet_id = zone_state[2]
            result = Subnet(self.parameters).details(subnet_id)
            if result is None:
                logger.warning(f"Removing stale state entry for subnet {subnet_id}")
                self.state.list_remove('zone', zone_state[0])
        if self.state.get('route_table_id'):
            result = RouteTable(self.parameters).details(self.state['route_table_id'])
            if result is None:
                logger.warning(f"Removing stale state entry for route table {self.state['route_table_id']}")
                del self.state['route_table_id']
        if self.state.get('internet_gateway_id'):
            result = InternetGateway(self.parameters).details(self.state['internet_gateway_id'])
            if result is None:
                logger.warning(f"Removing stale state entry for gateway {self.state['internet_gateway_id']}")
                del self.state['internet_gateway_id']
        if self.state.get('security_group_id'):
            result = SecurityGroup(self.parameters).details(self.state['security_group_id'])
            if result is None:
                logger.warning(f"Removing stale state entry for security group {self.state['security_group_id']}")
                del self.state['security_group_id']
        if self.state.get('vpc_id'):
            result = Network(self.parameters).details(self.state['vpc_id'])
            if result is None:
                logger.warning(f"Removing stale state entry for network {self.state['vpc_id']}")
                del self.state['vpc_id']
                del self.state['vpc_cidr']
                del self.state['zone']
        if self.state.get('ssh_key'):
            result = SSHKey(self.parameters).details(self.state['ssh_key'])
            if result is None:
                logger.warning(f"Removing stale state entry for SSH key {self.state['ssh_key']}")
                del self.state['ssh_key']
        if self.state.get('public_hosted_zone'):
            result = DNS(self.parameters).details(self.state['public_hosted_zone'])
            if result is None:
                logger.warning(f"Removing stale state entry for public hosted domain {self.state['public_hosted_zone']}")
                del self.state['public_hosted_zone']
        if self.state.get('private_hosted_zone'):
            result = DNS(self.parameters).details(self.state['private_hosted_zone'])
            if result is None:
                logger.warning(f"Removing stale state entry for private hosted domain {self.state['private_hosted_zone']}")
                del self.state['private_hosted_zone']

    def create_vpc(self):
        self.check_state()
        cidr_util = NetworkDriver()

        for net in self.aws_network.cidr_list:
            cidr_util.add_network(net)

        zone_list = self.aws_network.zones()

        ssh_pub_key_text = SSHUtil().get_ssh_public_key(self.ssh_key)

        try:

            if not self.state.get('vpc_id'):
                vpc_cidr = cidr_util.get_next_network()
                vpc_id = Network(self.parameters).create(self.vpc_name, vpc_cidr)
                Network(self.parameters).enable_dns_hostnames(vpc_id)
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
                sg_id = SecurityGroup(self.parameters).create(self.sg_name, f"Couch Formation project {self.project}", vpc_id)
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
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 3389, 3389, "0.0.0.0/0")
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 5985, 5985, "0.0.0.0/0")
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 5986, 5986, "0.0.0.0/0")
                self.state['security_group_id'] = sg_id
                logger.info(f"Created security group {sg_id}")

            if not self.state.get('ssh_key'):
                ssh_key_name = SSHKey(self.parameters).create(self.key_name, ssh_pub_key_text)
                self.state['ssh_key'] = ssh_key_name
                logger.info(f"Created SSH Key {ssh_key_name}")

            if not self.state.get('internet_gateway_id'):
                ig_id = InternetGateway(self.parameters).create(self.ig_name, vpc_id)
                self.state['internet_gateway_id'] = ig_id
                logger.info(f"Created internet gateway {ig_id}")
            else:
                ig_id = self.state.get('internet_gateway_id')

            if not self.state.get('route_table_id'):
                rt_id = RouteTable(self.parameters).create(self.rt_name, vpc_id)
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

            if self.domain and not self.state.get('domain'):
                domain_prefix = ''.join(random.choice(string.ascii_lowercase) for _ in range(7))
                domain_name = f"{domain_prefix}.{self.domain}"
                self.state['domain'] = domain_name
                logger.info(f"Generated project domain {domain_name}")
            elif self.state.get('domain'):
                domain_name = self.state.get('domain')
                logger.info(f"Using existing domain {domain_name}")
            else:
                domain_name = None

            if domain_name and not self.state.get('public_hosted_zone'):
                domain_id = DNS(self.parameters).create(domain_name)
                self.state['public_hosted_zone'] = domain_id
                logger.info(f"Created public hosted zone {domain_id} for domain {domain_name}")

            if domain_name and not self.state.get('private_hosted_zone'):
                domain_id = DNS(self.parameters).create(domain_name, vpc_id, self.region)
                self.state['private_hosted_zone'] = domain_id
                logger.info(f"Created private hosted zone {domain_id} for domain {domain_name}")

            if self.state.get('public_hosted_zone') and not self.state['parent_hosted_zone']:
                parent_domain = '.'.join(domain_name.split('.')[1:])
                parent_id = DNS(self.parameters).zone_id(parent_domain)
                if parent_id:
                    ns_names = DNS(self.parameters).record_sets(self.state['public_hosted_zone'], 'NS')
                    DNS(self.parameters).add_record(parent_id, domain_name, ns_names, 'NS')
                    self.state['parent_hosted_zone'] = parent_id
                    self.state['parent_zone_ns_records'] = ','.join(ns_names)
                    logger.info(f"Added {len(ns_names)} NS record(s) to domain {parent_domain}")

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

            if self.state.get('parent_hosted_zone') and self.state.get('domain'):
                ns_names = self.state['parent_zone_ns_records'].split(',')
                DNS(self.parameters).delete_record(self.state['parent_hosted_zone'], self.state['domain'], ns_names, 'NS')
                del self.state['parent_hosted_zone']
                del self.state['parent_zone_ns_records']
                logger.info(f"Removing NS records for domain {self.state['domain']}")

            if self.state.get('public_hosted_zone'):
                domain_id = self.state.get('public_hosted_zone')
                DNS(self.parameters).delete(domain_id)
                del self.state['public_hosted_zone']
                logger.info(f"Removing public hosted zone {domain_id}")

            if self.state.get('private_hosted_zone'):
                domain_id = self.state.get('private_hosted_zone')
                DNS(self.parameters).delete(domain_id)
                del self.state['private_hosted_zone']
                logger.info(f"Removing private hosted zone {domain_id}")

            if self.state.get('domain'):
                domain_name = self.state.get('domain')
                del self.state['domain']
                logger.info(f"Removing project domain {domain_name}")

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

    @property
    def domain_name(self):
        return self.state.get('domain')

    @property
    def public_zone(self):
        return self.state.get('public_hosted_zone')

    @property
    def private_zone(self):
        return self.state.get('private_hosted_zone')

    def add_service(self, name):
        self.state.list_add('services', name)

    def remove_service(self, name):
        self.state.list_remove('services', name)
