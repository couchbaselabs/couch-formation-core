##
##

import logging
import googleapiclient.errors
from couchformation.gcp.driver.base import CloudBase, GCPDriverError

logger = logging.getLogger('couchformation.gcp.driver.dns')
logger.addHandler(logging.NullHandler())
logging.getLogger("googleapiclient").setLevel(logging.ERROR)


class DNS(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def fqdn(domain: str):
        if domain[-1] not in ['.']:
            domain = domain + '.'
        return domain

    def create(self, domain: str, network_link: str = None, private: bool = False):
        name_part = domain.replace('.', '-')
        name = f"{name_part}-public" if not private else f"{name_part}-private"
        visibility = 'private' if private else 'public'
        dns_body = {
            'kind': 'dns#managedZone',
            'name': name,
            'dnsName': self.fqdn(domain),
            'description': 'Couch Formation Managed Zone',
            'visibility': visibility
        }
        if private and network_link:
            dns_body['privateVisibilityConfig'] = {
                "kind": "dns#managedZonePrivateVisibilityConfig",
                "networks": [
                    {
                        "kind": "dns#managedZonePrivateVisibilityConfigNetwork",
                        "networkUrl": network_link
                    }
                ]
            }

        try:
            request = self.dns_client.managedZones().create(project=self.gcp_project, body=dns_body)
            result = request.execute()
            return result.get('name')
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "alreadyExists":
                raise GCPDriverError(f"can not create managed zone: {err}")
        except Exception as err:
            raise GCPDriverError(f"error creating managed zone: {err}")

    def details(self, name: str):
        try:
            request = self.dns_client.managedZones().get(project=self.gcp_project, managedZone=name)
            result = request.execute()
            return result
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "notFound":
                raise GCPDriverError(f"can not find managed zone: {err}")
            return None
        except Exception as err:
            raise GCPDriverError(f"error getting managed zone: {err}")

    def list_zones(self):
        zone_list = []
        try:
            request = self.dns_client.managedZones().list(project=self.gcp_project)
            while request is not None:
                response = request.execute()
                for managed_zone in response['managedZones']:
                    zone_list.append(managed_zone)
                request = self.dns_client.managedZones().list_next(previous_request=request, previous_response=response)
            return zone_list
        except Exception as err:
            raise GCPDriverError(f"error listing managed zones: {err}")

    def zone_name(self, domain: str):
        zones = self.list_zones()
        return next((zone['name'] for zone in zones if zone['dnsName'].startswith(domain)), None)

    def record_sets(self, name: str, r_type: str):
        record_list = []
        try:
            request = self.dns_client.resourceRecordSets().list(project=self.gcp_project, managedZone=name)
            while request is not None:
                response = request.execute()
                for resource_record_set in response['rrsets']:
                    if resource_record_set['type'] != r_type:
                        continue
                    record_list.extend(resource_record_set['rrdatas'])
                request = self.dns_client.managedZones().list_next(previous_request=request, previous_response=response)
            return record_list
        except Exception as err:
            raise GCPDriverError(f"error listing managed zones: {err}")

    def delete(self, name: str):
        try:
            request = self.dns_client.managedZones().delete(project=self.gcp_project, managedZone=name)
            request.execute()
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "notFound":
                raise GCPDriverError(f"can not delete managed zone: {err}")
        except Exception as err:
            raise GCPDriverError(f"error deleting managed zone: {err}")

    def add_record(self, managed_zone: str, name: str, values: list, record_type: str = 'A', ttl: int = 300):
        dns_record_body = {
            'kind': 'dns#resourceRecordSet',
            'name': self.fqdn(name),
            'rrdatas': values,
            'ttl': ttl,
            'type': record_type
        }

        try:
            request = self.dns_client.resourceRecordSets().create(project=self.gcp_project, managedZone=managed_zone, body=dns_record_body)
            request.execute()
        except Exception as err:
            raise GCPDriverError(f"error creating DNS records: {err}")

    def delete_record(self, managed_zone: str, name: str, record_type: str = 'A'):
        try:
            request = self.dns_client.resourceRecordSets().delete(project=self.gcp_project, managedZone=managed_zone, name=self.fqdn(name), type=record_type)
            request.execute()
        except Exception as err:
            raise GCPDriverError(f"error deleting DNS records: {err}")
