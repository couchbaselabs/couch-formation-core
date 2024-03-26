##
##

import logging
import botocore.exceptions
from typing import Union, List
from couchformation.aws.driver.base import CloudBase, AWSDriverError, EmptyResultSet
from couchformation.aws.driver.constants import AWSTagStruct, AWSTag

logger = logging.getLogger('couchformation.aws.driver.network')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class Network(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, name: str = None) -> Union[List[dict], None]:
        vpc_list = []
        vpcs = []
        extra_args = {}

        try:
            while True:
                result = self.ec2_client.describe_vpcs(**extra_args)
                vpcs.extend(result['Vpcs'])
                if 'NextToken' not in result:
                    break
                extra_args['NextToken'] = result['NextToken']
        except Exception as err:
            raise AWSDriverError(f"error getting VPC list: {err}")

        for vpc_entry in vpcs:
            if name:
                vpc_name = self.get_tag("Name", vpc_entry['Tags'])
                if vpc_name != name:
                    continue
            vpc_block = {'cidr': vpc_entry['CidrBlock'],
                         'default': vpc_entry['IsDefault'],
                         'id': vpc_entry['VpcId']}
            vpc_list.append(vpc_block)

        if len(vpc_list) == 0:
            return None
        else:
            return vpc_list

    @property
    def cidr_list(self):
        try:
            for item in self.list():
                yield item['cidr']
        except EmptyResultSet:
            return iter(())

    def create(self, name: str, cidr: str) -> str:
        vpc_tag = [AWSTagStruct.build("vpc").add(AWSTag("Name", name)).as_dict]
        try:
            result = self.ec2_client.create_vpc(CidrBlock=cidr, TagSpecifications=vpc_tag)
        except Exception as err:
            raise AWSDriverError(f"error creating VPC: {err}")

        return result['Vpc']['VpcId']

    def enable_dns_hostnames(self, vpc_id: str):
        try:
            self.ec2_client.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={'Value': True})
        except Exception as err:
            raise AWSDriverError(f"error setting VPC DNS hostname option: {err}")

    def delete(self, vpc_id: str) -> None:
        try:
            self.ec2_client.delete_vpc(VpcId=vpc_id)
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error deleting VPC: {err}")

    def details(self, vpc_id: str) -> Union[dict, None]:
        try:
            result = self.ec2_client.describe_vpcs(VpcIds=[vpc_id])
            vpc_entry = result['Vpcs'][0]
            vpc_block = {'cidr': vpc_entry['CidrBlock'],
                         'default': vpc_entry['IsDefault'],
                         'id': vpc_entry['VpcId']}
            return vpc_block
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error getting VPC details: {err}")


class Subnet(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def list(self, vpc_id: str, zone: Union[str, None] = None, filter_keys_exist: Union[List[str], None] = None) -> List[dict]:
        subnet_list = []
        subnets = []
        extra_args = {}
        subnet_filter = [
            {
                'Name': 'vpc-id',
                'Values': [
                    vpc_id,
                ]
            }
        ]

        if zone:
            subnet_filter.append(
                {
                    'Name': 'availability-zone',
                    'Values': [
                        zone,
                    ]
                }
            )

        try:
            while True:
                result = self.ec2_client.describe_subnets(**extra_args, Filters=subnet_filter)
                subnets.extend(result['Subnets'])
                if 'NextToken' not in result:
                    break
                extra_args['NextToken'] = result['NextToken']
        except Exception as err:
            raise AWSDriverError(f"error getting subnets: {err}")

        for subnet in subnets:
            net_block = {'cidr': subnet['CidrBlock'],
                         'name': subnet['SubnetId'],
                         'vpc': subnet['VpcId'],
                         'zone': subnet['AvailabilityZone'],
                         'default': subnet['DefaultForAz'],
                         'public': subnet['MapPublicIpOnLaunch']}
            if filter_keys_exist:
                if not all(key in net_block for key in filter_keys_exist):
                    continue
            subnet_list.append(net_block)

        if len(subnet_list) == 0:
            raise EmptyResultSet(f"no subnets found")

        return subnet_list

    def create(self, name: str, vpc_id: str, zone: str, cidr: str) -> str:
        subnet_tag = [AWSTagStruct.build("subnet").add(AWSTag("Name", name)).as_dict]
        try:
            result = self.ec2_client.create_subnet(VpcId=vpc_id, AvailabilityZone=zone, CidrBlock=cidr, TagSpecifications=subnet_tag)
            subnet_id = result['Subnet']['SubnetId']
            self.ec2_client.modify_subnet_attribute(SubnetId=subnet_id, MapPublicIpOnLaunch={'Value': True})
            return subnet_id
        except Exception as err:
            AWSDriverError(f"error creating subnet: {err}")

    def details(self, subnet_id: str) -> Union[dict, None]:
        try:
            result = self.ec2_client.describe_subnets(SubnetIds=[subnet_id])
            subnet = result['Subnets'][0]
            net_block = {'cidr': subnet['CidrBlock'],
                         'name': subnet['SubnetId'],
                         'vpc': subnet['VpcId'],
                         'zone': subnet['AvailabilityZone'],
                         'default': subnet['DefaultForAz'],
                         'public': subnet['MapPublicIpOnLaunch']}
            return net_block
        except IndexError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error getting VPC details: {err}")

    def delete(self, subnet_id: str) -> None:
        try:
            self.ec2_client.delete_subnet(SubnetId=subnet_id)
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error deleting subnet: {err}")
