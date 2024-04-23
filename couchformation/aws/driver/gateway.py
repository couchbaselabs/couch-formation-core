##
##

import logging
import botocore.exceptions
from typing import Union, List
from couchformation.aws.driver.base import CloudBase, AWSDriverError, EmptyResultSet
from couchformation.aws.driver.constants import AWSTagStruct, AWSTag

logger = logging.getLogger('couchformation.aws.driver.gateway')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class InternetGateway(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self) -> List[dict]:
        ig_list = []
        igs = []
        extra_args = {}

        try:
            while True:
                result = self.ec2_client.describe_internet_gateways(**extra_args)
                igs.extend(result['InternetGateways'])
                if 'NextToken' not in result:
                    break
                extra_args['NextToken'] = result['NextToken']
        except Exception as err:
            raise AWSDriverError(f"error getting Internet Gateway list: {err}")

        for ig_entry in igs:
            ig_block = {'owner': ig_entry['OwnerId'],
                        'attachments': [a['VpcId'] for a in ig_entry['Attachments']],
                        'id': ig_entry['InternetGatewayId']}
            ig_list.append(ig_block)

        if len(ig_list) == 0:
            raise EmptyResultSet(f"no Internet Gateways found")
        else:
            return ig_list

    def create(self, name: str, vpc_id: str) -> str:
        ig_tag = [AWSTagStruct.build("internet-gateway").add(AWSTag("Name", name)).as_dict]
        try:
            result = self.ec2_client.create_internet_gateway(TagSpecifications=ig_tag)
            ig_id = result['InternetGateway']['InternetGatewayId']
            self.ec2_client.attach_internet_gateway(InternetGatewayId=ig_id, VpcId=vpc_id)
        except Exception as err:
            raise AWSDriverError(f"error creating Internet Gateway: {err}")

        return ig_id

    def delete(self, ig_id: str) -> None:
        try:
            ig_data = self.details(ig_id)
            if not ig_data:
                return
            for vpc_id in ig_data.get('attachments', []):
                self.ec2_client.detach_internet_gateway(InternetGatewayId=ig_id, VpcId=vpc_id)
            self.ec2_client.delete_internet_gateway(InternetGatewayId=ig_id)
        except Exception as err:
            raise AWSDriverError(f"error deleting Internet Gateway: {err}")

    def get(self, name: str):
        get_filter = {
            'Name': "tag:Name",
            'Values': [
                name,
            ]
        }
        try:
            result = self.ec2_client.describe_internet_gateways(Filters=[get_filter])
            return result.get('InternetGateways', [])[0]['InternetGatewayId']
        except IndexError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error getting Internet Gateway details: {err}")

    def details(self, ig_id: str) -> Union[dict, None]:
        try:
            result = self.ec2_client.describe_internet_gateways(InternetGatewayIds=[ig_id])
            ig_entry = result['InternetGateways'][0]
            ig_block = {'owner': ig_entry['OwnerId'],
                        'attachments': [a['VpcId'] for a in ig_entry['Attachments']],
                        'id': ig_entry['InternetGatewayId']}
            return ig_block
        except IndexError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error getting Internet Gateway details: {err}")
