##
##

import logging
from azure.core.exceptions import ResourceNotFoundError
from couchformation.azure.driver.base import CloudBase, AzureDriverError

logger = logging.getLogger('couchformation.azure.driver.dns')
logger.addHandler(logging.NullHandler())
logging.getLogger("azure").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class DNS(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def create(self, domain: str, resource_group: str, private: bool = False):
        visibility = 'Private' if private else 'Public'
        parameters = {
            'zone_type': visibility,
            'location': 'global'
        }

        try:
            result = self.dns_client.zones.create_or_update(resource_group, domain, parameters)
            return result.name
        except Exception as err:
            raise AzureDriverError(f"error creating zone: {err}")

    def details(self, domain: str):
        zones = self.list_zones()
        return next((zone for zone in zones if zone['name'].startswith(domain)), None)

    def list_zones(self):
        zone_list = []

        try:
            zones = self.dns_client.zones.list()
        except Exception as err:
            raise AzureDriverError(f"error getting zones: {err}")

        for group in list(zones):
            zone_data = {
                'id': group.id,
                'etag': group.etag,
                'resource_group': group.id.split('/')[4],
                'name': group.name,
                'location': group.location,
                'name_servers': group.name_servers,
                'zone_type': group.zone_type
            }
            zone_list.append(zone_data)

        return zone_list

    def record_sets(self, name: str, r_type: str, resource_group: str):
        record_data = []

        try:
            records = self.dns_client.record_sets.list_by_type(resource_group, name, r_type)
        except Exception as err:
            raise AzureDriverError(f"error getting resource records: {err}")

        def _list_iter(items):
            if items:
                return list(items)
            else:
                return []

        for group in list(records):
            record = {
                'id': group.id,
                'name': group.name,
                'a_records': [r.ipv4_address for r in _list_iter(group.a_records)],
                'aaaa_records': [r.ipv6_address for r in _list_iter(group.aaaa_records)],
                'mx_records': [r.exchange for r in _list_iter(group.mx_records)],
                'ns_records': [r.nsdname for r in _list_iter(group.ns_records)],
                'ptr_records': [r.ptrdname for r in _list_iter(group.ptr_records)],
                'srv_records': [f"{r.priority} {r.weight} {r.port} {r.target}" for r in _list_iter(group.srv_records)],
                'txt_records': [r.value for r in _list_iter(group.txt_records)],
                'cname_records': [r.cname for r in _list_iter(group.cname_record)],
                'soa_records': [f"{r.host} {r.email} {r.serial_number} {r.refresh_time} {r.retry_time} {r.expire_time} {r.minimum_ttl}" for r in _list_iter(group.soa_record)]
            }
            record_data.append(record)

        return record_data[0].get(f"{r_type.lower()}_records", [])

    def delete(self, name: str, resource_group: str):
        try:
            request = self.dns_client.zones.begin_delete(resource_group, name)
            request.wait()
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error deleting zone: {err}")

    @staticmethod
    def parameter_gen(values: list, record_type: str = 'A', ttl: int = 300):
        if record_type == 'A':
            return {"properties": {"ARecords": [{"ipv4Address": v} for v in values], "TTL": ttl}}
        elif record_type == 'AAAA':
            return {"properties": {"AAAARecords": [{"ipv6Address": v} for v in values], "TTL": ttl}}
        elif record_type == 'CNAME':
            return {"properties": {"CNAMERecord": {"cname": values[0]}, "TTL": ttl}}
        elif record_type == 'MX':
            return {"properties": {"MXRecords": [{"exchange": v, "preference": n} for n, v in enumerate(values)], "TTL": ttl}}
        elif record_type == 'NS':
            return {"properties": {"NSRecords": [{"nsdname": v} for v in values], "TTL": ttl}}
        elif record_type == 'PTR':
            return {"properties": {"PTRRecords": [{"ptrdname": v} for v in values], "TTL": ttl}}
        elif record_type == 'SRV':
            return {"properties": {"SRVRecords": [{"priority": v.split()[0], "weight": v.split()[1], "port": v.split()[2], "target": v.split()[3]} for v in values], "TTL": ttl}}
        elif record_type == 'TXT':
            return {"properties": {"TXTRecords": [{"value": values}], "TTL": ttl}}

    def add_record(self, zone_name: str, name: str, values: list, resource_group: str, record_type: str = 'A', ttl: int = 300):
        try:
            parameters = self.parameter_gen(values, record_type, ttl)
            response = self.dns_client.record_sets.create_or_update(resource_group_name=resource_group,
                                                                    zone_name=zone_name,
                                                                    relative_record_set_name=name,
                                                                    record_type=record_type,
                                                                    parameters=parameters)
            return response.id
        except Exception as err:
            raise AzureDriverError(f"error creating zone: {err}")

    def delete_record(self, zone_name: str, name: str, resource_group: str, record_type: str = 'A'):
        try:
            self.dns_client.record_sets.delete(resource_group, zone_name, name, record_type)
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error deleting record: {err}")
