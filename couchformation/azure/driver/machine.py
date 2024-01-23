##
##

import re
import logging
from typing import Union, List
from couchformation.azure.driver.base import CloudBase, AzureDriverError
from couchformation.azure.driver.constants import ComputeTypes
import couchformation.constants as C

logger = logging.getLogger('couchformation.azure.driver.machine')
logger.addHandler(logging.NullHandler())
logging.getLogger("azure").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class MachineType(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, location: str, virtualization: bool = False) -> list:
        machine_type_list = []

        try:
            machine_list = self.compute_client.virtual_machine_sizes.list(location=location)
        except Exception as err:
            raise AzureDriverError(f"error listing machine types: {err}")

        for machine in list(machine_list):
            match = re.search(r"Standard_([A-Z])([0-9]*)([a-z]*)_v([0-9])", machine.name)
            if not match:
                continue
            if len(match.groups()) != 4:
                continue
            if not set(match.group(1)).issubset(ComputeTypes.size_family):
                continue
            if not set(match.group(3)).issubset(ComputeTypes.size_features):
                continue
            if not set(match.group(3)).issuperset(ComputeTypes.size_storage):
                continue
            if not set(match.group(4)).issubset(ComputeTypes.size_versions):
                continue
            if virtualization and not set(match.group(3)).issubset(ComputeTypes.vmp_features):
                continue
            if virtualization and not set(match.group(4)).issubset(ComputeTypes.vmp_versions):
                continue
            config_block = {'name': machine.name,
                            'cpu': machine.number_of_cores,
                            'memory': machine.memory_in_mb}
            machine_type_list.append(config_block)

        if len(machine_type_list) == 0:
            raise AzureDriverError(f"no machine types in location {location}")

        return machine_type_list

    def get_resources(self, location: str):
        result_list = self.compute_client.resource_skus.list()
        resource_list = [r for r in result_list if location in r.locations]
        return resource_list

    def get_machine_types(self, location: str, virtualization: bool = False):
        result_list = []
        machine_list = self.list(location, virtualization)
        machine_list = sorted(machine_list, key=lambda m: m['name'][-1], reverse=True)

        for machine_type in C.MACHINE_TYPES:
            machine = next((m for m in machine_list if m['cpu'] == machine_type['cpu'] and m['memory'] == machine_type['memory']), None)
            if not machine:
                continue
            machine.update(dict(machine_type=machine_type['name']))
            result_list.append(machine)

        return result_list

    def get_machine(self, name: str, location: str, virtualization: bool = False):
        machine_list = self.get_machine_types(location, virtualization)
        return next((m for m in machine_list if m['machine_type'] == name), None)

    def check_capacity(self, resource_list: List, machine_size: str, location: str):
        for resource in resource_list:
            if machine_size != resource.name:
                continue
            zone_list = next((i.zones for i in resource.location_info if i.location == location), [])
            if set(zone_list) != set(self.azure_availability_zones):
                return False
            restriction = next((r.reason_code for r in resource.restrictions if location in r.values), None)
            if restriction and restriction == "NotAvailableForSubscription":
                return False
            return True

    def details(self, machine_type: str) -> Union[dict, None]:
        try:
            sizes = self.compute_client.virtual_machine_sizes.list(self.azure_location)
        except Exception as err:
            raise AzureDriverError(f"error getting machine type {machine_type}: {err}")

        for group in list(sizes):
            if group.name == machine_type:
                return {'name': group.name,
                        'cpu': int(group.number_of_cores),
                        'memory': int(group.memory_in_mb),
                        'disk': int(group.resource_disk_size_in_mb)}
        return None
