##
##

import logging
import boto3
import botocore.exceptions
from botocore.config import Config
import os
import attr
import webbrowser
import time
from datetime import datetime
from Crypto.PublicKey import RSA
from attr.validators import instance_of as io
from typing import Iterable, Union
from itertools import cycle
from lib.exceptions import AWSDriverError, EmptyResultSet
from lib.util.filemgr import FileManager
from lib.util.db_mgr import LocalDB
from lib.config_values import CloudTable
import lib.config as config

logger = logging.getLogger('pyformationlib.aws.driver.auth')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class Network(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def list(self, filter_keys_exist: Union[list[str], None] = None) -> list[dict]:
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
            vpc_block.update(self.process_tags(vpc_entry))
            if filter_keys_exist:
                if not all(key in vpc_block for key in filter_keys_exist):
                    continue
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
            vpc_block.update(self.process_tags(vpc_entry))
            return vpc_block
        except (KeyError, IndexError):
            return None
        except Exception as err:
            raise AWSDriverError(f"error getting VPC details: {err}")
