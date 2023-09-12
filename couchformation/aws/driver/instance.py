##
##

import logging
from couchformation.aws.driver.base import CloudBase, AWSDriverError
from couchformation.aws.driver.constants import AWSEbsDisk, AWSTagStruct, EbsVolume, AWSTag

logger = logging.getLogger('couchformation.aws.driver.instance')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class Instance(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, name: str, ami: str, ssh_key: str, sg_id: str, subnet: str, root_type="gp3", root_size=100, instance_type="t2.micro"):
        try:
            ami_details = self.image_details(ami)
        except Exception as err:
            raise AWSDriverError(f"error getting AMI {ami} details: {err}")
        if 'BlockDeviceMappings' not in ami_details:
            raise AWSDriverError(f"can not get details for AMI {ami}")

        root_dev = ami_details['BlockDeviceMappings'][0]['DeviceName']
        root_disk = [AWSEbsDisk.build(root_dev, EbsVolume(root_type, root_size)).as_dict]
        instance_tag = [AWSTagStruct.build("instance").add(AWSTag("Name", name)).as_dict]

        try:
            result = self.ec2_client.run_instances(BlockDeviceMappings=root_disk,
                                                   ImageId=ami,
                                                   InstanceType=instance_type,
                                                   KeyName=ssh_key,
                                                   MaxCount=1,
                                                   MinCount=1,
                                                   SecurityGroupIds=[sg_id],
                                                   SubnetId=subnet,
                                                   TagSpecifications=instance_tag)
        except Exception as err:
            raise AWSDriverError(f"error running instance: {err}")

        instance_id = result['Instances'][0]['InstanceId']
        waiter = self.ec2_client.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id])

        return instance_id

    def details(self, instance_id: str) -> dict:
        try:
            result = self.ec2_client.describe_instances(InstanceIds=[instance_id])
        except Exception as err:
            raise AWSDriverError(f"error getting instance details: {err}")

        return result['Reservations'][0]['Instances'][0]

    def terminate(self, instance_id: str) -> None:
        try:
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
        except Exception as err:
            raise AWSDriverError(f"error terminating instance: {err}")

        waiter = self.ec2_client.get_waiter('instance_terminated')
        waiter.wait(InstanceIds=[instance_id])

    def image_details(self, ami_id: str) -> dict:
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