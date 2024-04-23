##
##

import logging
import botocore.exceptions
from typing import Union, List
from couchformation.aws.driver.base import CloudBase, AWSDriverError, EmptyResultSet
from couchformation.aws.driver.constants import AWSTagStruct, AWSTag

logger = logging.getLogger('couchformation.aws.driver.route')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class RouteTable(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self) -> List[dict]:
        table_list = []
        tables = []
        extra_args = {}

        try:
            while True:
                result = self.ec2_client.describe_route_tables(**extra_args)
                tables.extend(result['InternetGateways'])
                if 'NextToken' not in result:
                    break
                extra_args['NextToken'] = result['NextToken']
        except Exception as err:
            raise AWSDriverError(f"error getting Internet Gateway list: {err}")

        for table_entry in tables:
            table_block = {'owner': table_entry['OwnerId'],
                           'associations': [a for a in table_entry['Associations']],
                           'routes': [r for r in table_entry['Routes']],
                           'vpc': table_entry['VpcId'],
                           'id': table_entry['RouteTableId']}
            table_list.append(table_block)

        if len(table_list) == 0:
            raise EmptyResultSet(f"no Route Table found")
        else:
            return table_list

    def create(self, name: str, vpc_id: str) -> str:
        table_tag = [AWSTagStruct.build("route-table").add(AWSTag("Name", name)).as_dict]
        try:
            result = self.ec2_client.create_route_table(VpcId=vpc_id, TagSpecifications=table_tag)
        except Exception as err:
            raise AWSDriverError(f"error creating Route Table: {err}")

        return result['RouteTable']['RouteTableId']

    def delete(self, rt_id: str) -> None:
        rt = self.details(rt_id)
        if not rt:
            return
        try:
            self.ec2_client.delete_route_table(RouteTableId=rt_id)
        except Exception as err:
            raise AWSDriverError(f"error deleting Route Table: {err}")

    def get(self, name: str):
        get_filter = {
            'Name': "tag:Name",
            'Values': [
                name,
            ]
        }
        try:
            result = self.ec2_client.describe_route_tables(Filters=[get_filter])
            return result.get('RouteTables', [])[0]['RouteTableId']
        except IndexError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error getting Route Table details: {err}")

    def details(self, rt_id: str) -> Union[dict, None]:
        try:
            result = self.ec2_client.describe_route_tables(RouteTableIds=[rt_id])
            table_entry = result['RouteTables'][0]
            table_block = {'owner': table_entry['OwnerId'],
                           'associations': [a for a in table_entry['Associations']],
                           'routes': [r for r in table_entry['Routes']],
                           'vpc': table_entry['VpcId'],
                           'id': table_entry['RouteTableId']}
            return table_block
        except IndexError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error getting Route Table details: {err}")

    def associate(self, rt_id: str, subnet_id: str):
        try:
            response = self.ec2_client.associate_route_table(RouteTableId=rt_id, SubnetId=subnet_id)
            return response['AssociationId']
        except Exception as err:
            raise AWSDriverError(f"error creating Route Table: {err}")

    def add_route(self, cidr: str, ig_id: str, rt_id: str):
        try:
            response = self.ec2_client.create_route(DestinationCidrBlock=cidr, GatewayId=ig_id, RouteTableId=rt_id)
            return response['Return']
        except Exception as err:
            raise AWSDriverError(f"error creating Route Table: {err}")
