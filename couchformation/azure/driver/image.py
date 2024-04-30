##
##

import logging
import re
from typing import List, Union
from couchformation.azure.driver.base import CloudBase, AzureDriverError, EmptyResultSet
from couchformation.azure.driver.constants import AzureImagePublishers
import couchformation.constants as C

logger = logging.getLogger('couchformation.azure.driver.image')
logger.addHandler(logging.NullHandler())
logging.getLogger("azure").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class Image(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def list(self, filter_keys_exist: Union[List[str], None] = None, resource_group: Union[str, None] = None) -> List[dict]:
        image_list = []
        if not resource_group:
            resource_group = self.rg_switch()

        images = self.compute_client.images.list_by_resource_group(resource_group)

        for image in list(images):
            image_block = {'name': image.name,
                           'id': image.id,
                           'resource_group': resource_group,
                           'location': image.location}
            image_block.update(self.process_tags(image.tags))
            if filter_keys_exist:
                if not all(key in image_block for key in filter_keys_exist):
                    continue
            image_list.append(image_block)

        if len(image_list) == 0:
            raise EmptyResultSet(f"no images found")

        return image_list

    def public(self, location: str, publisher: str, architecture: str = 'x86_64'):
        offer_list = []
        image_list = []

        offers = self.compute_client.virtual_machine_images.list_offers(location, publisher)
        for group in list(offers):
            offer_block = {'name': group.name,
                           'skus': [],
                           'count': 0}
            offer_list.append(offer_block)

        for n, offer in enumerate(offer_list):
            offer_name = offer['name']
            skus = self.compute_client.virtual_machine_images.list_skus(location, publisher, offer_name)
            for sku in list(skus):
                sku_name = sku.name
                _image_is_arm = re.search('arm64', offer_name) or re.search('arm64', sku_name)
                if architecture == 'arm64' and not _image_is_arm:
                    continue
                elif _image_is_arm:
                    continue
                versions = self.compute_client.virtual_machine_images.list(location, publisher, offer_name, sku_name)
                for version in versions:
                    image_block = {
                        "publisher": publisher,
                        "offer": offer_name,
                        "sku": sku_name,
                        "version": version.name,
                        "location": location
                    }
                    image_list.append(image_block)

        if len(image_list) == 0:
            raise EmptyResultSet(f"no images found")

        return image_list

    def details(self, name: str, resource_group: Union[str, None] = None) -> dict:
        if not resource_group:
            resource_group = self.rg_switch()
        request = self.compute_client.images.get(resource_group, name)
        image = request.result()
        image_block = {'name': image.name,
                       'id': image.id,
                       'resource_group': resource_group,
                       'location': image.location}
        image_block.update(self.process_tags(image.tags))
        return image_block

    def delete(self, name: str, resource_group: Union[str, None] = None) -> None:
        if not resource_group:
            resource_group = self.rg_switch()
        try:
            request = self.compute_client.images.begin_delete(resource_group, name)
            request.result()
        except Exception as err:
            raise AzureDriverError(f"can not delete image: {err}")

    def list_standard(self, os_id: str = None, os_version: str = None, architecture: str = 'x86_64'):
        result_list = []
        for image_type in AzureImagePublishers.publishers:
            if os_id and image_type['os_id'] != os_id:
                continue
            image_list = self.public(location=self.region, publisher=image_type['name'], architecture=architecture)
            for version in C.OS_VERSION_LIST[image_type['os_id']]:
                if os_version and version != os_version:
                    continue
                filtered_images = []
                for image in image_list:
                    offer_match = re.search(image_type['offer_match'], image['offer'])
                    sku_match = re.search(image_type['sku_match'], image['sku'])
                    if offer_match:
                        if len(offer_match.groups()) > 0:
                            m = offer_match.group(1)
                            if m == version or m == version.replace('.', '_'):
                                filtered_images.append(image)
                        elif sku_match and len(sku_match.groups()) > 0:
                            m = sku_match.group(1)
                            if m == version or m == version.replace('.', '_'):
                                filtered_images.append(image)
                if len(filtered_images) > 0:
                    filtered_images.sort(key=lambda i: i['version'])
                    result_image = filtered_images[-1]
                    result_image.update(dict(
                        os_id=image_type['os_id'],
                        os_version=version,
                        os_user=image_type['user'],
                    ))
                    result_list.append(result_image)
                if len(result_list) > 0:
                    logger.debug(f"Selected image -> {result_list[-1]}")
                return result_list[-1]

    @staticmethod
    def image_user(os_id: str):
        return next((image_type['user'] for image_type in AzureImagePublishers.publishers if image_type['os_id'] == os_id), None)
