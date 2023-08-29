##
##

import logging
from typing import Union, List
from pyformationlib.aws.driver.base import CloudBase, AWSDriverError, EmptyResultSet
from pyformationlib.aws.driver.constants import AWSTagStruct, AWSTag

logger = logging.getLogger('pyformationlib.aws.driver.network')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class Network(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self) -> List[dict]:
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
            vpc_block = {'cidr': vpc_entry['CidrBlock'],
                         'default': vpc_entry['IsDefault'],
                         'id': vpc_entry['VpcId']}
            vpc_list.append(vpc_block)

        if len(vpc_list) == 0:
            raise EmptyResultSet(f"no VPCs found")
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

    def delete(self, vpc_id: str) -> None:
        try:
            self.ec2_client.delete_vpc(VpcId=vpc_id)
        except Exception as err:
            raise AWSDriverError(f"error deleting VPC: {err}")

    def details(self, vpc_id: str) -> Union[dict, None]:
        try:
            result = self.ec2_client.describe_vpcs(VpcId=[vpc_id])
            vpc_entry = result['Vpcs'][0]
            vpc_block = {'cidr': vpc_entry['CidrBlock'],
                         'default': vpc_entry['IsDefault'],
                         'id': vpc_entry['VpcId']}
            return vpc_block
        except (KeyError, IndexError):
            return None
        except Exception as err:
            raise AWSDriverError(f"error getting VPC details: {err}")
