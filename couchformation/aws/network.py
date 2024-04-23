##
##

import os
import logging
import random
import string
from itertools import cycle
from typing import List
from couchformation.network import NetworkDriver
from couchformation.aws.driver.network import Network, Subnet
from couchformation.aws.driver.sshkey import SSHKey
from couchformation.aws.driver.gateway import InternetGateway
from couchformation.aws.driver.nsg import SecurityGroup
from couchformation.aws.driver.route import RouteTable
from couchformation.aws.driver.dns import DNS
import couchformation.aws.driver.constants as C
from couchformation.config import get_state_file, get_state_dir, PortSettingSet, PortSettings
from couchformation.deployment import MetadataManager
from couchformation.ssh import SSHUtil
from couchformation.exception import FatalError
from couchformation.kvdb import KeyValueStore
from couchformation.util import FileManager, synchronize, UUIDGen

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
        self.allow = parameters.get('allow') if parameters.get('allow') else "0.0.0.0/0"
        self.build_ports = PortSettingSet().create().items()

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

        project_uid = MetadataManager(self.project).project_uid
        self.asset_prefix = f"cf-{project_uid}"
        self.vpc_name = f"{self.asset_prefix}-vpc"
        self.ig_name = f"{self.asset_prefix}-gw"
        self.rt_name = f"{self.asset_prefix}-rt"
        self.sg_name = f"{self.asset_prefix}-sg"
        self.key_name = f"{self.asset_prefix}-key"

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
        else:
            result = RouteTable(self.parameters).get(self.rt_name)
            if result:
                logger.warning(f"Importing orphaned entry for route table {result}")
                self.state['route_table_id'] = result

        if self.state.get('internet_gateway_id'):
            result = InternetGateway(self.parameters).details(self.state['internet_gateway_id'])
            if result is None:
                logger.warning(f"Removing stale state entry for gateway {self.state['internet_gateway_id']}")
                del self.state['internet_gateway_id']
        else:
            result = InternetGateway(self.parameters).get(self.ig_name)
            if result:
                logger.warning(f"Importing orphaned entry for internet gateway {result}")
                self.state['internet_gateway_id'] = result

        if self.state.get('security_group_id'):
            result = SecurityGroup(self.parameters).details(self.state['security_group_id'])
            if result is None:
                logger.warning(f"Removing stale state entry for security group {self.state['security_group_id']}")
                del self.state['security_group_id']
        else:
            result = SecurityGroup(self.parameters).get(self.sg_name)
            if result:
                logger.warning(f"Importing orphaned entry for security group {result}")
                self.state['security_group_id'] = result

        for build_port_cfg in self.build_ports:
            build_name = build_port_cfg.build
            state_key_name = f"{build_name}_security_group_id"
            build_sg_name = f"{self.asset_prefix}-{build_name}-sg"
            if self.state.get(state_key_name):
                result = SecurityGroup(self.parameters).details(self.state[state_key_name])
                if result is None:
                    logger.warning(f"Removing stale state entry for security group {self.state[state_key_name]}")
                    del self.state[state_key_name]
            else:
                result = SecurityGroup(self.parameters).get(build_sg_name)
                if result:
                    logger.warning(f"Importing orphaned entry for security group {result}")
                    self.state[state_key_name] = result

        if self.state.get('win_security_group_id'):
            result = SecurityGroup(self.parameters).details(self.state['win_security_group_id'])
            if result is None:
                logger.warning(f"Removing stale state entry for security group {self.state['win_security_group_id']}")
                del self.state['win_security_group_id']
        else:
            win_sg_name = f"{self.asset_prefix}-win-sg"
            result = SecurityGroup(self.parameters).get(win_sg_name)
            if result:
                logger.warning(f"Importing orphaned entry for security group {result}")
                self.state['win_security_group_id'] = result

        for group_sg_key in self.state.key_match('.*_group_.*_sg_id'):
            if self.state.get(group_sg_key):
                result = SecurityGroup(self.parameters).details(self.state[group_sg_key])
                if result is None:
                    logger.warning(f"Removing stale state entry for security group {self.state[group_sg_key]}")
                    del self.state[group_sg_key]

        for n, sg_group in enumerate(SecurityGroup(self.parameters).search(f"{self.asset_prefix}-*-sg")):
            sg_group_id = sg_group.get('id')
            service = sg_group.get('Service', 'import')
            group = sg_group.get('Group', n)
            state_key_name = f"{service}_group_{group}_sg_id"
            if not self.state.value_match(sg_group_id):
                logger.warning(f"Importing orphaned entry for security group {sg_group_id}")
                self.state[state_key_name] = sg_group_id

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

    @synchronize()
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
                SecurityGroup(self.parameters).add_ingress(sg_id, "tcp", 22, 22, self.allow)
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
                subnet_name = f"{self.asset_prefix}-subnet-{n+1:02d}"
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

    @synchronize()
    def create_build_sg(self, build_name: str):
        vpc_id = self.vpc_id
        for build_port_cfg in self.build_ports:
            if build_port_cfg.build != build_name:
                continue
            state_key_name = f"{build_name}_security_group_id"
            build_sg_name = f"{self.asset_prefix}-{build_name}-sg"
            if not self.state.get(state_key_name):
                build_sg_id = SecurityGroup(self.parameters).create(build_sg_name, f"Couch Formation build type {build_name}", vpc_id)
                for begin, end in build_port_cfg.tcp_as_tuple():
                    SecurityGroup(self.parameters).add_ingress(build_sg_id, "tcp", begin, end, self.allow)
                for begin, end in build_port_cfg.udp_as_tuple():
                    SecurityGroup(self.parameters).add_ingress(build_sg_id, "udp", begin, end, self.allow)
                self.state[state_key_name] = build_sg_id
                logger.info(f"Created {build_name} build security group {build_sg_id}")
            else:
                build_sg_id = self.state.get(state_key_name)
            return build_sg_id

    @synchronize()
    def create_win_sg(self):
        vpc_id = self.vpc_id
        if not self.state.get('win_security_group_id'):
            win_sg_name = f"{self.asset_prefix}-win-sg"
            win_sg_id = SecurityGroup(self.parameters).create(win_sg_name, "Couch Formation Windows OS ports", vpc_id)
            SecurityGroup(self.parameters).add_ingress(win_sg_id, "tcp", 3389, 3389, self.allow)
            SecurityGroup(self.parameters).add_ingress(win_sg_id, "tcp", 5985, 5986, self.allow)
            self.state['win_security_group_id'] = win_sg_id
            logger.info(f"Created win security group {win_sg_id}")
        else:
            win_sg_id = self.state.get('win_security_group_id')
        return win_sg_id

    @synchronize()
    def create_node_group_sg(self, service: str, group: int, ports: List[str]):
        vpc_id = self.vpc_id
        state_key_name = f"{service}_group_{group}_sg_id"
        service_code = UUIDGen().text_hash(f"{service}-group-{group}")
        build_sg_name = f"{self.asset_prefix}-{service_code}-sg"
        if not self.state.get(state_key_name):
            port_cfg = PortSettings().create(self.name, ports)
            tags = {'Service': service, 'Group': group}
            port_sg_id = SecurityGroup(self.parameters).create(build_sg_name, f"Couch Formation service {service} group {group}", vpc_id, tags=tags)
            for begin, end in port_cfg.tcp_as_tuple():
                SecurityGroup(self.parameters).add_ingress(port_sg_id, "tcp", begin, end, self.allow)
            for begin, end in port_cfg.udp_as_tuple():
                SecurityGroup(self.parameters).add_ingress(port_sg_id, "udp", begin, end, self.allow)
            self.state[state_key_name] = port_sg_id
            logger.info(f"Created service group security group {port_sg_id}")
        else:
            port_sg_id = self.state.get(state_key_name)
        return port_sg_id

    @synchronize()
    def destroy_vpc(self):
        if self.state.list_len('services') > 0:
            logger.info(f"Active services, leaving project network in place")
            return

        self.check_state()
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

            for build_port_cfg in self.build_ports:
                build_name = build_port_cfg.build
                state_key_name = f"{build_name}_security_group_id"
                if self.state.get(state_key_name):
                    sg_id = self.state.get(state_key_name)
                    SecurityGroup(self.parameters).delete(sg_id)
                    del self.state[state_key_name]
                    logger.info(f"Removing security group {sg_id}")

            if self.state.get('win_security_group_id'):
                sg_id = self.state.get('win_security_group_id')
                SecurityGroup(self.parameters).delete(sg_id)
                del self.state['win_security_group_id']
                logger.info(f"Removing security group {sg_id}")

            for group_sg_key in self.state.key_match('.*_group_.*_sg_id'):
                if self.state.get(group_sg_key):
                    sg_id = self.state.get(group_sg_key)
                    SecurityGroup(self.parameters).delete(sg_id)
                    del self.state[group_sg_key]
                    logger.info(f"Removing security group {sg_id}")

            if self.state.get('vpc_id'):
                vpc_id = self.state.get('vpc_id')
                Network(self.parameters).delete(vpc_id)
                del self.state['vpc_id']
                del self.state['vpc_cidr']
                logger.info(f"Removing VPC {vpc_id}")

            if self.state.get('ssh_key'):
                ssh_key_name = self.state.get('ssh_key')
                instances = SSHKey(self.parameters).instances_by_key(ssh_key_name)
                if len(instances) > 0:
                    logger.warning(f"SSH key {ssh_key_name} in use, key will not be deleted from AWS")
                else:
                    logger.info(f"Deleting SSH key pair {ssh_key_name}")
                    SSHKey(self.parameters).delete(ssh_key_name)
                del self.state['ssh_key']
                logger.info(f"Removing key pair {ssh_key_name} from project")

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

    def build_security_group_id(self, build_name: str):
        state_key_name = f"{build_name}_security_group_id"
        return self.state.get(state_key_name)

    @property
    def win_security_group_id(self):
        return self.state.get('win_security_group_id')

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

    @property
    def vpc_id(self):
        return self.state.get('vpc_id')

    def add_service(self, name):
        self.state.list_add('services', name)

    def remove_service(self, name):
        self.state.list_remove('services', name)
