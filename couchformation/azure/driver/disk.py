##
##

import logging
from typing import Union
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.compute.models import DiskCreateOption
from couchformation.azure.driver.base import CloudBase, AzureDriverError

logger = logging.getLogger('couchformation.azure.driver.disk')
logger.addHandler(logging.NullHandler())
logging.getLogger("azure").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class Disk(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def create(self, resource_group: str, location: str, zone: str, size: int, tier: str, name: str):
        parameters = {
            'location': location,
            'sku': {
                'name': 'Premium_LRS',
                'tier': tier
            },
            'zones': [zone],
            'disk_size_gb': size,
            'creation_data': {
                'create_option': DiskCreateOption.empty
            }
        }
        try:
            request = self.compute_client.disks.begin_create_or_update(resource_group, name, parameters)
            request.wait()
            return request.result()
        except Exception as err:
            raise AzureDriverError(f"error creating disk: {err}")

    def details(self, name: str, resource_group: str) -> Union[dict, None]:
        try:
            disk = self.compute_client.disks.get(resource_group, name)
            disk_info = {'name': disk.name,
                         'id': disk.id,
                         'zones': disk.zones,
                         'disk_size_gb': disk.disk_size_gb,
                         'sku': disk.sku.__dict__}
            return disk_info
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error getting disk {name}: {err}")

    def delete(self, name: str, resource_group: str) -> None:
        try:
            request = self.compute_client.disks.begin_delete(resource_group, name)
            request.wait()
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error deleting instance: {err}")
