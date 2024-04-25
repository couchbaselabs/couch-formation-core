##
##

import logging
import re
from typing import Union, List
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.network.models import VirtualNetwork
from couchformation.azure.driver.base import CloudBase, AzureDriverError, EmptyResultSet

logger = logging.getLogger('couchformation.azure.driver.network')
logger.addHandler(logging.NullHandler())
logging.getLogger("azure").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class Network(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def list(self, resource_group: Union[str, None] = None, filter_keys_exist: Union[List[str], None] = None) -> List[dict]:
        if not resource_group:
            if not self.azure_resource_group:
                return []
            resource_group = self.azure_resource_group
        vnet_list = []

        try:
            vnetworks = self.network_client.virtual_networks.list(resource_group)
        except Exception as err:
            raise AzureDriverError(f"error getting vnet: {err}")

        for group in list(vnetworks):
            if group.location != self.azure_location:
                continue
            network_block = {'cidr': group.address_space.address_prefixes,
                             'name': group.name,
                             'subnets': [s.name for s in group.subnets],
                             'id': group.id}
            network_block.update(self.process_tags(group.tags))
            if filter_keys_exist:
                if not all(key in network_block for key in filter_keys_exist):
                    continue
            vnet_list.append(network_block)

        if len(vnet_list) == 0:
            raise EmptyResultSet(f"no suitable virtual network in location {self.azure_location}")

        return vnet_list

    @property
    def cidr_list(self):
        try:
            for item in self.list():
                for net in item['cidr']:
                    yield net
        except EmptyResultSet:
            return iter(())

    def create(self, name: str, cidr: str, resource_group: str):
        parameters = {
            'location': self.azure_location,
            'address_space': {
                'address_prefixes': [cidr]
            }
        }

        net_info = self.details(name, resource_group)
        if net_info:
            return net_info

        try:
            request = self.network_client.virtual_networks.begin_create_or_update(resource_group, name, parameters)
            request.wait()
            return request.result()
        except Exception as err:
            raise AzureDriverError(f"error creating network: {err}")

    def delete(self, network: str, resource_group: str) -> None:
        try:
            request = self.network_client.virtual_networks.begin_delete(resource_group, network)
            request.wait()
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error getting vnet: {err}")

    def details(self, network: str, resource_group: str) -> Union[VirtualNetwork, None]:
        try:
            info = self.network_client.virtual_networks.get(resource_group, network)
            return info
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error getting vnet: {err}")

    def create_pub_ip(self, name: str, resource_group: str):
        parameters = {
            'location': self.azure_location,
            'public_ip_allocation_method': 'Static',
            'sku': {
                'name': 'Standard'
            }
        }

        try:
            request = self.network_client.public_ip_addresses.begin_create_or_update(resource_group, name, parameters)
            request.wait()
            return request.result()
        except Exception as err:
            raise AzureDriverError(f"can not create public IP: {err}")

    def create_nic(self, name: str, subnet_id: str, zone: str, pub_ip_id: str, resource_group: str):
        parameters = {
            'location': self.azure_location,
            'ip_configurations': [
                {
                    'name': name,
                    'subnet': {
                        'id': subnet_id,
                    },
                    'private_ip_allocation_method': 'Dynamic',
                    'zones': [zone],
                    'public_ip_address': {
                        'id': pub_ip_id
                    }
                }
            ]
        }

        try:
            request = self.network_client.network_interfaces.begin_create_or_update(resource_group, name, parameters)
            request.wait()
            return request.result()
        except Exception as err:
            raise AzureDriverError(f"error creating nic: {err}")

    def describe_nic(self, name: str, resource_group: str):
        try:
            nic = self.network_client.network_interfaces.get(resource_group, name)
            return nic
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error getting nic details: {err}")

    def describe_pub_ip(self, name: str, resource_group: str):
        try:
            ip = self.network_client.public_ip_addresses.get(resource_group, name)
            return ip
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error getting public IP: {err}")

    def delete_pub_ip(self, name: str, resource_group: str):
        try:
            request = self.network_client.public_ip_addresses.begin_delete(resource_group, name)
            request.wait()
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error deleting public IP: {err}")

    def delete_nic(self, name: str, resource_group: str) -> None:
        try:
            request = self.network_client.network_interfaces.begin_delete(resource_group, name)
            request.wait()
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error deleting nic: {err}")


class Subnet(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def list(self, vnet: str, resource_group: Union[str, None] = None) -> List[dict]:
        if not resource_group:
            resource_group = self.azure_resource_group
        subnet_list = []

        try:
            subnets = self.network_client.subnets.list(resource_group, vnet)
        except Exception as err:
            raise AzureDriverError(f"error getting subnets: {err}")

        for group in list(subnets):
            subnet_block = {'cidr': group.address_prefix,
                            'name': group.name,
                            'routes': group.route_table.routes if group.route_table else None,
                            'nsg': group.network_security_group.id.rsplit('/', 1)[-1] if group.network_security_group else None,
                            'id': group.id}
            subnet_list.append(subnet_block)

        if len(subnet_list) == 0:
            raise EmptyResultSet(f"no subnets in vnet {vnet}")

        return subnet_list

    def create(self, name: str, network: str, cidr: str, nsg_id: str, resource_group: str):
        parameters = {
            'address_prefix': cidr,
            'network_security_group': {
                'id': nsg_id
            }
        }
        try:
            request = self.network_client.subnets.begin_create_or_update(resource_group, network, name, parameters)
            request.wait()
            return request.result()
        except Exception as err:
            raise AzureDriverError(f"error creating subnet: {err}")

    def delete(self, network: str, subnet: str, resource_group: str) -> None:
        try:
            subnet_info = self.details(network, subnet, resource_group)
            if subnet_info:
                request = self.network_client.subnets.begin_delete(resource_group, network, subnet)
                request.wait()
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error deleting subnet: {err}")

    def details(self, network: str, subnet: str, resource_group: str) -> Union[dict, None]:
        try:
            info = self.network_client.subnets.get(resource_group, network, subnet)
            subnet_block = {'cidr': info.address_prefix,
                            'name': info.name,
                            'routes': info.route_table.routes if info.route_table else None,
                            'nsg': info.network_security_group.id.rsplit('/', 1)[-1] if info.network_security_group else None,
                            'id': info.id}

            return subnet_block
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error getting subnet: {err}")


class SecurityGroup(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def list(self, resource_group: Union[str, None] = None, filter_keys_exist: Union[List[str], None] = None) -> List[dict]:
        if not resource_group:
            resource_group = self.azure_resource_group
        nsg_list = []

        try:
            result = self.network_client.network_security_groups.list(resource_group)
        except Exception as err:
            raise AzureDriverError(f"error getting vnet: {err}")

        for group in list(result):
            if group.location != self.azure_location:
                continue
            nsg_block = {'location': group.location,
                         'name': group.name,
                         'rules': [r.__dict__ for r in group.security_rules] if group.security_rules else [],
                         'subnets': [s.__dict__ for s in group.subnets] if group.subnets else [],
                         'id': group.id}
            nsg_block.update(self.process_tags(group.tags))
            if filter_keys_exist:
                if not all(key in nsg_block for key in filter_keys_exist):
                    continue
            nsg_list.append(nsg_block)

        if len(nsg_list) == 0:
            raise EmptyResultSet(f"no suitable network security group in group {resource_group}")

        return nsg_list

    def create(self, name: str, resource_group: str):
        parameters = {
            'location': self.azure_location
        }
        try:
            request = self.network_client.network_security_groups.begin_create_or_update(resource_group, name, parameters)
            request.wait()
            return request.result()
        except Exception as err:
            raise AzureDriverError(f"error creating network security group: {err}")

    def add_rule(self,
                 name: str,
                 nsg_name: str,
                 ports: list,
                 priority: int,
                 resource_group: str,
                 protocol: str = "Tcp",
                 source: Union[list, None] = None) -> None:
        nsg_info = self.details(nsg_name, resource_group)
        if not nsg_info:
            raise AzureDriverError(f"can not find NSG {nsg_name} in {resource_group}")
        if source:
            default_source = None
        else:
            default_source = "*"
        protocol = protocol.lower().capitalize()
        if priority == 0:
            count = len(nsg_info.get('rules', []))
            priority = (count + 101)
        parameters = {
            "description": "Cloud Formation Managed",
            "access": "Allow",
            "destination_address_prefix": "*",
            "destination_port_ranges": ports,
            "direction": "Inbound",
            "priority": priority,
            "protocol": protocol,
            "source_address_prefix": default_source,
            "source_address_prefixes": source,
            "source_port_range": "*",
        }
        try:
            request = self.network_client.security_rules.begin_create_or_update(resource_group, nsg_name, name, parameters)
            request.wait()
            return request.result()
        except Exception as err:
            raise AzureDriverError(f"error creating network security group rule: {err}")

    def delete(self, name: str, resource_group: str) -> None:
        try:
            request = self.network_client.network_security_groups.begin_delete(resource_group, name)
            request.wait()
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error getting network security group: {err}")

    def search_rules(self, name: str, resource_group: str, pattern: str) -> List[dict]:
        rules = []
        nsg_info = self.details(name, resource_group)
        if not nsg_info:
            raise AzureDriverError(f"can not find NSG {name} in {resource_group}")
        for rule in nsg_info.get('rules', []):
            if re.search(pattern, rule['name']):
                rules.append(rule)
        return rules

    def details(self, name: str, resource_group: str) -> Union[dict, None]:
        try:
            info = self.network_client.network_security_groups.get(resource_group, name)
            nsg_block = {'location': info.location,
                         'name': info.name,
                         'rules': [r.__dict__ for r in info.security_rules] if info.security_rules else [],
                         'subnets': [s.__dict__ for s in info.subnets] if info.subnets else [],
                         'id': info.id}
            nsg_block.update(self.process_tags(info.tags))
            return nsg_block
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error getting network security group: {err}")
