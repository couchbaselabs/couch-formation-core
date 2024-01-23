##
##

import logging
import re
from datetime import datetime
from typing import Union, List
from couchformation.aws.driver.base import CloudBase, AWSDriverError, EmptyResultSet
from couchformation.aws.driver.constants import AWSEbsDisk, AWSTagStruct, EbsVolume, AWSTag, AWSImageOwners
import couchformation.constants as C

logger = logging.getLogger('couchformation.aws.driver.image')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class Image(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, filter_keys_exist: Union[List[str], None] = None, is_public: bool = False, owner_id: str = None, name: str = None) -> List[dict]:
        image_list = []
        if owner_id:
            owner_filter = [owner_id]
        else:
            owner_filter = []
        if is_public:
            ami_filter = [
                {
                    'Name': 'architecture',
                    'Values': [
                        "x86_64",
                        "arm64",
                        "arm64_mac"
                    ]
                },
                {
                    'Name': 'root-device-type',
                    'Values': [
                        "ebs",
                    ]
                }
            ]
            if name:
                ami_filter.append(
                    {
                        'Name': 'name',
                        'Values': [
                            name
                        ]
                    }
                )
        else:
            ami_filter = [
                {
                    'Name': 'is-public',
                    'Values': [
                        'false',
                    ]
                }
            ]

        logger.debug(f"Searching images by owner {owner_id} and name {name}")

        try:
            images = self.ec2_client.describe_images(Filters=ami_filter, Owners=owner_filter)
        except Exception as err:
            raise AWSDriverError(f"error getting AMIs: {err}")

        for image in images['Images']:
            image_block = {'name': image['ImageId'],
                           'description': image['Name'],
                           'date': image['CreationDate'],
                           'details': image['PlatformDetails'],
                           'root_disk': image.get('BlockDeviceMappings')[0].get('DeviceName'),
                           'arch': image['Architecture']}
            if is_public:
                image_block.update({'owner': image['OwnerId']})

            if filter_keys_exist:
                if not all(key in image_block for key in filter_keys_exist):
                    continue
            image_list.append(image_block)

        if len(image_list) == 0:
            raise EmptyResultSet(f"no AMIs found")

        return image_list

    def list_standard(self, architecture: str = 'x86_64', os_id: str = None, os_version: str = None, feature: str = None):
        result_list = []
        for image_type in AWSImageOwners.image_owner_list:
            if os_id and (image_type['os_id'] != os_id or image_type['feature'] != feature):
                continue
            image_list = self.list(is_public=True, owner_id=image_type['owner_id'], name=image_type['pattern'])
            for version in C.OS_VERSION_LIST[image_type['os_id']]:
                logger.debug(f"Checking image {version}")
                if os_version and version != os_version:
                    continue
                filtered_images = []
                for image in image_list:
                    logger.debug(f"Found image {image}")
                    if image['arch'] != architecture:
                        continue
                    match = re.search(image_type['version'], image['description'])
                    if match and match.group(1) == version:
                        filtered_images.append(image)
                if len(filtered_images) > 0:
                    filtered_images.sort(key=lambda i: datetime.strptime(i['date'], '%Y-%m-%dT%H:%M:%S.%fZ'))
                    result_image = filtered_images[-1]
                    result_image.update(dict(
                        os_id=image_type['os_id'],
                        os_version=version,
                        os_user=image_type['user']
                    ))
                    result_list.append(result_image)
        if len(result_list) > 0:
            logger.debug(f"Selected image -> {result_list[-1]}")
        return result_list[-1]

    @staticmethod
    def image_user(os_id: str):
        return next((image_type['user'] for image_type in AWSImageOwners.image_owner_list if image_type['os_id'] == os_id), None)

    def details(self, ami_id: str) -> dict:
        ami_filter = {
            'Name': 'image-id',
            'Values': [
                ami_id,
            ]
        }
        try:
            result = self.ec2_client.describe_images(Filters=[ami_filter])
        except Exception as err:
            raise AWSDriverError(f"error getting AMI details: {err}")

        return result['Images'][0]

    def create(self, name: str, instance: str, description=None, root_type="gp3", root_size=100, root_iops=3000) -> str:
        try:
            instance_details = self.instance_details(instance)
        except Exception as err:
            raise AWSDriverError(f"error getting instance {instance} details: {err}")
        if 'BlockDeviceMappings' not in instance_details:
            raise AWSDriverError(f"can not get details for instance {instance}")

        root_dev = instance_details['BlockDeviceMappings'][0]['DeviceName']
        root_disk = [AWSEbsDisk.build(root_dev, EbsVolume(root_type, root_size, root_iops)).as_dict]
        ami_tag = [AWSTagStruct.build("image").add(AWSTag("Name", name)).as_dict]

        if not description:
            description = "couch-formation-image"

        try:
            result = self.ec2_client.create_image(BlockDeviceMappings=root_disk,
                                                  Description=description,
                                                  InstanceId=instance,
                                                  Name=name,
                                                  TagSpecifications=ami_tag)
        except Exception as err:
            raise AWSDriverError(f"error creating AMI: {err}")

        ami_id = result['ImageId']
        waiter = self.ec2_client.get_waiter('image_available')
        waiter.wait(ImageIds=[ami_id])

        return ami_id

    def delete(self, ami: str) -> None:
        try:
            self.ec2_client.deregister_image(ImageId=ami)
        except Exception as err:
            raise AWSDriverError(f"error deleting AMI: {err}")

    def instance_details(self, instance_id: str) -> dict:
        try:
            result = self.ec2_client.describe_instances(InstanceIds=[instance_id])
        except Exception as err:
            raise AWSDriverError(f"error getting instance details: {err}")

        return result['Reservations'][0]['Instances'][0]
