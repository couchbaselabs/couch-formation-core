##
##

import logging
from typing import Union, List
from couchformation.aws.driver.base import CloudBase, AWSDriverError, EmptyResultSet
from couchformation.aws.driver.constants import AWSTagStruct, AWSTag

logger = logging.getLogger('couchformation.aws.driver.nsg')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class SecurityGroup(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def list(self, vpc_id: str, filter_keys_exist: Union[List[str], None] = None) -> List[dict]:
        sg_list = []
        sgs = []
        extra_args = {}
        vpc_filter = {
            'Name': 'vpc-id',
            'Values': [
                vpc_id,
            ]
        }

        try:
            while True:
                result = self.ec2_client.describe_security_groups(**extra_args, Filters=[vpc_filter])
                sgs.extend(result['SecurityGroups'])
                if 'NextToken' not in result:
                    break
                extra_args['NextToken'] = result['NextToken']
        except Exception as err:
            raise AWSDriverError(f"error getting security groups: {err}")

        for sg_entry in sgs:
            sg_block = {'name': sg_entry['GroupName'],
                        'description': sg_entry['Description'],
                        'id': sg_entry['GroupId'],
                        'vpc': sg_entry['VpcId']}
            if filter_keys_exist:
                if not all(key in sg_block for key in filter_keys_exist):
                    continue
            sg_list.append(sg_block)

        if len(sg_list) == 0:
            raise EmptyResultSet(f"no security groups found")
        else:
            return sg_list

    def create(self, name: str, description: str, vpc_id: str) -> str:
        sg_tag = [AWSTagStruct.build("security-group").add(AWSTag("Name", name)).as_dict]
        try:
            result = self.ec2_client.create_security_group(GroupName=name, Description=description, VpcId=vpc_id, TagSpecifications=sg_tag)
        except Exception as err:
            raise AWSDriverError(f"error creating security group: {err}")

        return result['GroupId']

    def add_egress(self, sg_id: str, protocol: str, from_port: int, to_port: int, cidr: str):
        try:
            result = self.ec2_client.authorize_security_group_egress(
                GroupId=sg_id,
                IpPermissions=[{
                    'IpProtocol': protocol,
                    'FromPort': from_port,
                    'ToPort': to_port,
                    'IpRanges': [{
                        'CidrIp': cidr
                    }],
                }]
            )
        except Exception as err:
            raise AWSDriverError(f"error adding egress to security group: {err}")

        return result['Return']

    def add_ingress(self, sg_id: str, protocol: str, from_port: int, to_port: int, cidr: str):
        try:
            result = self.ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[{
                    'IpProtocol': protocol,
                    'FromPort': from_port,
                    'ToPort': to_port,
                    'IpRanges': [{
                        'CidrIp': cidr
                    }],
                }]
            )
        except Exception as err:
            raise AWSDriverError(f"error adding egress to security group: {err}")

        return result['Return']

    def delete(self, sg_id: str) -> None:
        try:
            self.ec2_client.delete_security_group(GroupId=sg_id)
        except Exception as err:
            raise AWSDriverError(f"error deleting security group: {err}")
