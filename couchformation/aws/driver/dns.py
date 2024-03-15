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

    def delete(self, hosted_zone: str):
        try:
            result = self.dns_client.delete_hosted_zone(Id=hosted_zone)
            return result.get('ChangeInfo', {}).get('Status')
        except Exception as err:
            raise AWSDriverError(f"error deleting hosted domain: {err}")

    def add_record(self, hosted_zone: str, name: str, value: str, record_type: str, ttl: int = 300):
        try:
            result = self.dns_client.change_resource_record_sets(
                HostedZoneId=hosted_zone,
                ChangeBatch={
                    'Changes': [
                        {
                            'Action': 'CREATE',
                            'ResourceRecordSet': {
                                'Name': name,
                                'Type': record_type,
                                'TTL': ttl,
                                'ResourceRecords': [
                                    {
                                        'Value': value
                                    }
                                ]
                            }
                        }]
                })
            return result.get('ChangeInfo', {}).get('Status')
        except Exception as err:
            raise AWSDriverError(f"error adding record to domain: {err}")

    def delete_record(self, hosted_zone: str, name: str, value: str, record_type: str, ttl: int = 300):
        try:
            result = self.dns_client.change_resource_record_sets(
                HostedZoneId=hosted_zone,
                ChangeBatch={
                    'Changes': [
                        {
                            'Action': 'DELETE',
                            'ResourceRecordSet': {
                                'Name': name,
                                'Type': record_type,
                                'TTL': ttl,
                                'ResourceRecords': [
                                    {
                                        'Value': value
                                    }
                                ]
                            }
                        }]
                })
            return result.get('ChangeInfo', {}).get('Status')
        except Exception as err:
            raise AWSDriverError(f"error deleting record from domain: {err}")
