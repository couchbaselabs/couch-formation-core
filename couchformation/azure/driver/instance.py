##
##

import logging
from typing import Union
from azure.core.exceptions import ResourceNotFoundError
from couchformation.azure.driver.base import CloudBase, AzureDriverError

logger = logging.getLogger('couchformation.azure.driver.instance')
logger.addHandler(logging.NullHandler())
logging.getLogger("azure").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class Instance(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def run(self,
            name: str,
            image_publisher: str,
            image_offer: str,
            image_sku: str,
            zone: str,
            nic_id: str,
            username: str,
            public_key: str,
            resource_group: str,
            root_disk_name: str,
            swap_caching: str,
            swap_disk_id: str,
            data_caching: str,
            data_disk_id: str,
            root_type="Premium_LRS",
            root_size=256,
            machine_type="Standard_D4_v3"):
        if not resource_group:
            resource_group = self.azure_resource_group

        try:
            instance_info = self.details(name, resource_group)
            return instance_info
        except ResourceNotFoundError:
            pass

        image_block = {
            'publisher': image_publisher,
            'offer': image_offer,
            'sku': image_sku,
            'version': 'latest'
        }

        parameters = {
            'location': self.azure_location,
            'zones': [zone],
            'os_profile': {
                'computer_name': name,
                'admin_username': username,
                'linux_configuration': {
                    'ssh': {
                        'public_keys': [
                            {
                                'path': f"/home/{username}/.ssh/authorized_keys",
                                'key_data': public_key
                            }
                        ]
                    }
                }
            },
            'hardware_profile': {
                'vm_size': machine_type
            },
            'storage_profile': {
                'image_reference': image_block,
                'os_disk': {
                    'name': root_disk_name,
                    'disk_size_gb': root_size,
                    'create_option': 'FromImage',
                    'managed_disk': {
                        'storage_account_type': root_type
                    }
                },
                'data_disks': [
                    {
                        'caching': swap_caching,
                        'lun': '0',
                        'create_option': 'Attach',
                        'managed_disk': {
                            'id': swap_disk_id
                        }
                    },
                    {
                        'caching': data_caching,
                        'lun': '1',
                        'create_option': 'Attach',
                        'managed_disk': {
                            'id': data_disk_id
                        }
                    }
                ]
            },
            'network_profile': {
                'network_interfaces': [{
                    'id': nic_id,
                }]
            },
        }

        try:
            request = self.compute_client.virtual_machines.begin_create_or_update(resource_group, name, parameters)
            request.wait()
        except Exception as err:
            raise AzureDriverError(f"error creating instance: {err}")

        return name

    def details(self, instance: str, resource_group: str):
        try:
            machine = self.compute_client.virtual_machines.get(resource_group, instance)
            return machine
        except ResourceNotFoundError:
            raise
        except Exception as err:
            raise AzureDriverError(f"error getting instance {instance}: {err}")

    def terminate(self, instance: str, resource_group: str) -> None:
        try:
            request = self.compute_client.virtual_machines.begin_delete(resource_group, instance)
            request.wait()
        except Exception as err:
            raise AzureDriverError(f"error deleting instance: {err}")
