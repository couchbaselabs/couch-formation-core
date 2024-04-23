##
##

import logging
import botocore.exceptions
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

    def create(self, name: str, description: str, vpc_id: str, tags: Union[dict, None] = None) -> str:
        sg_tag = AWSTagStruct.build("security-group")
        sg_tag.add(AWSTag("Name", name))
        if tags:
            for k, v in tags.items():
                sg_tag.add(AWSTag(k, str(v)))
        try:
            result = self.ec2_client.create_security_group(GroupName=name, Description=description, VpcId=vpc_id, TagSpecifications=[sg_tag.as_dict])
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
        sg = self.details(sg_id)
        if not sg:
            return
        try:
            self.ec2_client.delete_security_group(GroupId=sg_id)
        except Exception as err:
            raise AWSDriverError(f"error deleting security group: {err}")

    def get(self, name: str):
        get_filter = {
            'Name': "tag:Name",
            'Values': [
                name,
            ]
        }
        try:
            result = self.ec2_client.describe_security_groups(Filters=[get_filter])
            return result.get('SecurityGroups', [])[0]['GroupId']
        except IndexError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error getting security group details: {err}")

    def search(self, name: str):
        get_filter = {
            'Name': "tag:Name",
            'Values': [
                name,
            ]
        }
        try:
            result = self.ec2_client.describe_security_groups(Filters=[get_filter])
            return [dict({tag['Key']: tag['Value'] for tag in e.get('Tags', [])}, id=e.get('GroupId')) for e in result.get('SecurityGroups', [])]
        except IndexError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error getting security group details: {err}")

    def details(self, sg_id: str) -> Union[dict, None]:
        try:
            result = self.ec2_client.describe_security_groups(GroupIds=[sg_id])
            sg_entry = result['SecurityGroups'][0]
            sg_block = {'name': sg_entry['GroupName'],
                        'description': sg_entry['Description'],
                        'id': sg_entry['GroupId'],
                        'vpc': sg_entry['VpcId']}
            return sg_block
        except IndexError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error getting security group details: {err}")
