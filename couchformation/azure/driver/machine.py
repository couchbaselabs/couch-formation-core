##
##

import logging
from typing import Union
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

    def list(self, location: str) -> list:
        machine_type_list = []

        try:
            resource_list = self.compute_client.resource_skus.list()
        except Exception as err:
            raise AzureDriverError(f"error listing machine types: {err}")

        for group in list(resource_list):
            if location not in group.locations:
                continue
            if not group.name.endswith(tuple(ComputeTypes().as_list())):
                continue
            if group.restrictions:
                if len(list(group.restrictions)) != 0:
                    continue
            if not group.capabilities:
                continue
            if group.tier != 'Standard':
                continue
            if not next((c for c in group.capabilities if c.name == 'PremiumIO' and bool(c.value) is True), None):
                continue
            vm_cpu = next((float(c.value) for c in group.capabilities if c.name == 'vCPUs'), 0)
            vm_mem = next((float(c.value) * 1024 for c in group.capabilities if c.name == 'MemoryGB'), 0)
            if vm_cpu == 0 or vm_mem == 0:
                continue
            config_block = {'name': group.name,
                            'cpu': int(vm_cpu),
                            'memory': int(vm_mem)}
            machine_type_list.append(config_block)

        if len(machine_type_list) == 0:
            raise AzureDriverError(f"no machine types in location {location}")

        return machine_type_list

    def get_machine_types(self, location: str):
        result_list = []
        machine_list = self.list(location)
        machine_list = sorted(machine_list, key=lambda m: m['name'])

        for machine_type in C.MACHINE_TYPES:
            machine = next((m for m in machine_list if m['cpu'] == machine_type['cpu'] and m['memory'] == machine_type['memory']), None)
            if not machine:
                continue
            machine.update(dict(machine_type=machine_type['name']))
            result_list.append(machine)

        return result_list

    def get_machine(self, name: str, location: str):
        machine_list = self.get_machine_types(location)
        return next((m for m in machine_list if m['machine_type'] == name), None)

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
