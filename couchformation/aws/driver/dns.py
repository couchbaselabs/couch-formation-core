##
##

import logging
import botocore.exceptions
from couchformation.aws.driver.base import CloudBase, AWSDriverError

logger = logging.getLogger('couchformation.aws.driver.dns')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class DNS(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def create(self, domain: str, vpc_id: str = None, region: str = None):
        private = vpc_id is not None
        zone_region = region if region is not None else self.aws_region
        kwargs = {
            'HostedZoneConfig': {
                'PrivateZone': private
            },
            'CallerReference': str(hash(domain + '_private_' + str(private)))
        }
        if private:
            kwargs['VPC'] = {
                'VPCRegion': zone_region,
                'VPCId': vpc_id
            }
        try:
            result = self.dns_client.create_hosted_zone(Name=domain, **kwargs)
            return result.get('HostedZone', {}).get('Id')
        except Exception as err:
            raise AWSDriverError(f"error creating hosted domain: {err}")

    def details(self, hosted_zone: str):
        try:
            result = self.dns_client.get_hosted_zone(Id=hosted_zone)
            return result.get('HostedZone', {})
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'] == 'NoSuchHostedZone':
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error: {err}")

    def zone_id(self, domain: str):
        try:
            result = self.dns_client.list_hosted_zones()
            r_set = next((item for item in result.get('HostedZones', [])
                          if item.get('Name').startswith(domain) and item.get('Config', {}).get('PrivateZone', False) is False), None)
            return r_set.get('Id') if r_set else None
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'] == 'NoSuchHostedZone':
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error: {err}")

    def record_sets(self, hosted_zone: str, r_type: str):
        try:
            result = self.dns_client.list_resource_record_sets(HostedZoneId=hosted_zone)
            r_set = next((item for item in result.get('ResourceRecordSets', {}) if item.get('Type') == r_type), None)
            return [item.get('Value') for item in r_set.get('ResourceRecords', [])]
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'] == 'NoSuchHostedZone':
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error: {err}")

    def delete(self, hosted_zone: str):
        try:
            result = self.dns_client.delete_hosted_zone(Id=hosted_zone)
            return result.get('ChangeInfo', {}).get('Status')
        except Exception as err:
            raise AWSDriverError(f"error deleting hosted domain: {err}")

    def add_record(self, hosted_zone: str, name: str, values: list, record_type: str = 'A', ttl: int = 300):
        change_batch = {
            'Changes': [
                {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': name,
                        'Type': record_type,
                        'TTL': ttl,
                        'ResourceRecords': []
                    }
                }
            ]
        }
        for item in values:
            change_batch['Changes'][0]['ResourceRecordSet']['ResourceRecords'].append({'Value': item})
        try:
            result = self.dns_client.change_resource_record_sets(HostedZoneId=hosted_zone, ChangeBatch=change_batch)
            return result.get('ChangeInfo', {}).get('Status')
        except Exception as err:
            raise AWSDriverError(f"error adding record to domain: {err}")

    def delete_record(self, hosted_zone: str, name: str, values: list, record_type: str = 'A', ttl: int = 300):
        change_batch = {
            'Changes': [
                {
                    'Action': 'DELETE',
                    'ResourceRecordSet': {
                        'Name': name,
                        'Type': record_type,
                        'TTL': ttl,
                        'ResourceRecords': []
                    }
                }
            ]
        }
        for item in values:
            change_batch['Changes'][0]['ResourceRecordSet']['ResourceRecords'].append({'Value': item})
        try:
            result = self.dns_client.change_resource_record_sets(HostedZoneId=hosted_zone, ChangeBatch=change_batch)
            return result.get('ChangeInfo', {}).get('Status')
        except Exception as err:
            raise AWSDriverError(f"error deleting record from domain: {err}")
