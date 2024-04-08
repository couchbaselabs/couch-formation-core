##
##

import logging
import botocore.exceptions
from typing import Union, List
from botocore.exceptions import ClientError
from couchformation.aws.driver.base import CloudBase, AWSDriverError, EmptyResultSet
from couchformation.aws.driver.constants import AWSTagStruct, AWSTag

logger = logging.getLogger('couchformation.aws.driver.sshkey')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class SSHKey(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def list(self, filter_keys_exist: Union[List[str], None] = None) -> List[dict]:
        key_list = []

        try:
            key_pairs = self.ec2_client.describe_key_pairs()
        except Exception as err:
            raise AWSDriverError(f"error getting key pairs: {err}")

        for key in key_pairs['KeyPairs']:
            key_block = {'name': key['KeyName'],
                         'id': key['KeyPairId'],
                         'fingerprint': key['KeyFingerprint'],
                         'pubkey': key.get('PublicKey')}
            if filter_keys_exist:
                if not all(key in key_block for key in filter_keys_exist):
                    continue
            key_list.append(key_block)

        if len(key_list) == 0:
            raise EmptyResultSet(f"no SSH keys found")

        return key_list

    def create(self, name: str, ssh_key: str, tags: Union[dict, None] = None) -> str:
        key_block = {}
        tag_build = AWSTagStruct.build("key-pair")
        tag_build.add(AWSTag("Name", name))

        if tags:
            for key, value in tags.items():
                tag_build.add(AWSTag(key, value))

        key_tag = [tag_build.as_dict]

        try:
            result = self.ec2_client.import_key_pair(KeyName=name,
                                                     PublicKeyMaterial=ssh_key.encode('utf-8'),
                                                     TagSpecifications=key_tag)
            key_block = {'name': result['KeyName'],
                         'id': result['KeyPairId'],
                         'fingerprint': result['KeyFingerprint']}
        except ClientError as err:
            if err.response['Error']['Code'] == 'InvalidKeyPair.Duplicate':
                key_block = self.details(name)
            else:
                raise
        except Exception as err:
            AWSDriverError(f"error importing key pair: {err}")

        return key_block['name']

    def create_native(self, name: str) -> dict:
        key_block = {}
        try:
            result = self.ec2_client.create_key_pair(KeyName=name)
            key_block = {'name': result['KeyName'],
                         'id': result['KeyPairId'],
                         'fingerprint': result['KeyFingerprint'],
                         'key': result['KeyMaterial']}
        except Exception as err:
            AWSDriverError(f"error creating key pair: {err}")

        return key_block

    def details(self, key_name: str) -> Union[dict, None]:
        try:
            result = self.ec2_client.describe_key_pairs(KeyNames=[key_name])
            key_result = result['KeyPairs'][0]
            key_block = {'name': key_result['KeyName'],
                         'id': key_result['KeyPairId'],
                         'fingerprint': key_result['KeyFingerprint']}
            return key_block
        except IndexError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error deleting key pair: {err}")

    def delete(self, name: str) -> None:
        key = self.details(name)
        if not key:
            return
        try:
            self.ec2_client.delete_key_pair(KeyName=name)
        except Exception as err:
            raise AWSDriverError(f"error deleting key pair: {err}")

    def instances_by_key(self, name: str):
        instances = []
        extra_args = {}
        key_filter = [
            {
                'Name': 'key-name',
                'Values': [
                    name,
                ]
            },
            {
                'Name': 'instance-state-name',
                'Values': [
                    'running',
                    'pending'
                ]
            }
        ]

        try:
            while True:
                result = self.ec2_client.describe_instances(**extra_args, Filters=key_filter)
                for reservation in result.get('Reservations', []):
                    instances.extend(reservation.get('Instances', []))
                if 'NextToken' not in result:
                    break
                extra_args['NextToken'] = result['NextToken']
        except Exception as err:
            raise AWSDriverError(f"error getting instance list: {err}")

        return instances
