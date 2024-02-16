##
##

import logging
from couchformation.azure.driver.base import CloudBase, AzureDriverError


class KeyVault(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def create(self, name: str, location: str, resource_group: str):
        parameters = {
            'location': location,
            'properties': {
                'sku': {
                    'name': 'standard'
                },
                'tenant_id': '6c3f1c39-b84c-4188-b49f-xxxxxxxxx',
                'access_policies': [{
                    'tenant_id': '6c3f1c39-b84c-4188-b49f-xxxxxxxx',
                    'object_id': OBJECT_ID,
                    'permissions': {
                        'keys': ['all'],
                        'secrets': ['all']
                    }
                }]
            }
        }