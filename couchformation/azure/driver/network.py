##
##

import logging
from typing import Union, List
from azure.core.exceptions import ResourceNotFoundError
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

    def create(self, name: str, cidr: str, resource_group: Union[str, None] = None) -> str:
        if not resource_group:
            resource_group = self.azure_resource_group

        try:
            net_info = self.details(name, resource_group)
            return net_info['name']
        except ResourceNotFoundError:
            pass

        try:
            request = self.network_client.virtual_networks.begin_create_or_update(
                resource_group,
                name,
                {
                    'location': self.azure_location,
                    'address_space': {
                        'address_prefixes': [cidr]
                    }
                }
            )
            request.wait()
        except Exception as err:
            raise AzureDriverError(f"error creating network: {err}")
        return name

    def delete(self, network: str, resource_group: Union[str, None] = None) -> None:
        if not resource_group:
            resource_group = self.azure_resource_group
        try:
            request = self.network_client.virtual_networks.begin_delete(resource_group, network)
            request.wait()
        except Exception as err:
            raise AzureDriverError(f"error getting vnet: {err}")

    def details(self, network: str, resource_group: Union[str, None] = None) -> dict:
        if not resource_group:
            resource_group = self.azure_resource_group
        try:
            info = self.network_client.virtual_networks.get(resource_group, network)
        except ResourceNotFoundError:
            raise
        except Exception as err:
            raise AzureDriverError(f"error getting vnet: {err}")

        network_block = {'cidr': info.address_space.address_prefixes,
                         'name': info.name,
                         'subnets': [s.name for s in info.subnets],
                         'id': info.id}
        network_block.update(self.process_tags(info.tags))

        return network_block

    def create_pub_ip(self, name: str, resource_group: Union[str, None] = None) -> dict:
        public_ip = {
            'location': self.azure_location,
            'public_ip_allocation_method': 'Static',
            'sku': {
                'name': 'Standard'
            }
        }

        try:
            request = self.network_client.public_ip_addresses.begin_create_or_update(resource_group, name, public_ip)
            result = request.result()
        except Exception as err:
            raise AzureDriverError(f"can not create public IP: {err}")

        return result.__dict__

    def create_nic(self, name: str, network: str, subnet: str, zone: str, resource_group: Union[str, None] = None) -> dict:
        if not resource_group:
            resource_group = self.azure_resource_group

        try:
            subnet_info = Subnet(self.config).details(network, subnet, resource_group)
        except Exception as err:
            raise AzureDriverError(f"can not get subnet {subnet} info: {err}")

        pub_ip = self.create_pub_ip(f"{name}-pub-ip", resource_group)

        parameters = {
            'location': self.azure_location,
            'ip_configurations': [
                {
                    'name': f"{name}-int",
                    'subnet': {
                        'id': subnet_info['id'],
                    },
                    'private_ip_allocation_method': 'Dynamic',
                    'zones': [zone],
                    'public_ip_address': {
                        'id': pub_ip['id']
                    }
                }
            ]
        }

        try:
            request = self.network_client.network_interfaces.begin_create_or_update(resource_group, name, parameters)
            result = request.result()
        except Exception as err:
            raise AzureDriverError(f"error creating nic: {err}")

        return result.__dict__

    def delete_pub_ip(self, name: str, resource_group: Union[str, None] = None):
        if not resource_group:
            resource_group = self.azure_resource_group
        try:
            request = self.network_client.public_ip_addresses.begin_delete(resource_group, name)
            request.wait()
        except Exception as err:
            raise AzureDriverError(f"error deleting public IP: {err}")

    def delete_nic(self, name: str, resource_group: Union[str, None] = None) -> None:
        if not resource_group:
            resource_group = self.azure_resource_group
        try:
            request = self.network_client.network_interfaces.begin_delete(resource_group, name)
            request.wait()
            self.delete_pub_ip(f"{name}-pub-ip", resource_group)
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

    def create(self, name: str, network: str, cidr: str, nsg: str, resource_group: Union[str, None] = None) -> str:
        if not resource_group:
            resource_group = self.azure_resource_group

        nsg_data = SecurityGroup(self.config).details(nsg, resource_group)
        if not nsg_data.get('id'):
            raise AzureDriverError(f"can not lookup nsg {nsg}")

        request = self.network_client.subnets.begin_create_or_update(
            resource_group,
            network,
            name,
            {
                'address_prefix': cidr,
                'network_security_group': {
                    'id': nsg_data['id']
                }
            }
        )
        subnet_info = request.result()

        return subnet_info.name

    def delete(self, network: str, subnet: str, resource_group: Union[str, None] = None) -> None:
        if not resource_group:
            resource_group = self.azure_resource_group
        try:
            request = self.network_client.subnets.begin_delete(resource_group, network, subnet)
            request.wait()
        except Exception as err:
            raise AzureDriverError(f"error deleting subnet: {err}")

    def details(self, network: str, subnet: str, resource_group: Union[str, None] = None) -> dict:
        if not resource_group:
            resource_group = self.azure_resource_group
        try:
            info = self.network_client.subnets.get(resource_group, network, subnet)
        except Exception as err:
            raise AzureDriverError(f"error getting subnet: {err}")

        subnet_block = {'cidr': info.address_prefix,
                        'name': info.name,
                        'routes': info.route_table.routes if info.route_table else None,
                        'nsg': info.network_security_group.id.rsplit('/', 1)[-1] if info.network_security_group else None,
                        'id': info.id}

        return subnet_block


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

    def create(self, name: str, resource_group: Union[str, None] = None) -> str:
        if not resource_group:
            resource_group = self.azure_resource_group
        try:
            request = self.network_client.network_security_groups.begin_create_or_update(
                resource_group,
                name,
                {
                    'location': self.azure_location
                }
            )
            request.wait()
        except Exception as err:
            raise AzureDriverError(f"error creating network security group: {err}")
        return name

    def add_rule(self,
                 name: str,
                 nsg: str,
                 ports: list,
                 priority: int,
                 source: Union[list, None] = None,
                 resource_group: Union[str, None] = None) -> None:
        if not resource_group:
            resource_group = self.azure_resource_group
        if source:
            default_source = None
        else:
            default_source = "*"
        try:
            request = self.network_client.security_rules.create_or_update(
                resource_group,
                nsg,
                name,
                {
                    "description": "Cloud Formation Managed",
                    "access": "Allow",
                    "destination_address_prefix": "*",
                    "destination_port_ranges": ports,
                    "direction": "Inbound",
                    "priority": priority,
                    "protocol": "Tcp",
                    "source_address_prefix": default_source,
                    "source_address_prefixes": source,
                    "source_port_range": "*",
                }
            )
            request.wait()
        except Exception as err:
            raise AzureDriverError(f"error creating network security group rule: {err}")

    def delete(self, name: str, resource_group: Union[str, None] = None) -> None:
        if not resource_group:
            resource_group = self.azure_resource_group
        try:
            request = self.network_client.network_security_groups.begin_delete(resource_group, name)
            request.wait()
        except Exception as err:
            raise AzureDriverError(f"error getting network security group: {err}")

    def details(self, name: str, resource_group: Union[str, None] = None) -> dict:
        if not resource_group:
            resource_group = self.azure_resource_group
        try:
            info = self.network_client.network_security_groups.get(resource_group, name)
        except Exception as err:
            raise AzureDriverError(f"error getting network security group: {err}")

        nsg_block = {'location': info.location,
                     'name': info.name,
                     'rules': [r.__dict__ for r in info.security_rules] if info.security_rules else [],
                     'subnets': [s.__dict__ for s in info.subnets] if info.subnets else [],
                     'id': info.id}
        nsg_block.update(self.process_tags(info.tags))

        return nsg_block
