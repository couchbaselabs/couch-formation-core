##
##

import logging
from couchformation.gcp.driver.base import CloudBase, GCPDriverError, EmptyResultSet
from couchformation.gcp.driver.constants import ComputeTypes
import couchformation.constants as C

logger = logging.getLogger('couchformation.gcp.driver.machine')
logger.addHandler(logging.NullHandler())
logging.getLogger("googleapiclient").setLevel(logging.ERROR)


class MachineType(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, zone: str, architecture: str = 'x86_64') -> list:
        machine_type_list = []
        if architecture == 'arm64':
            filter_string = "cpuPlatform = \"Ampere Altra\""
        else:
            filter_string = None

        try:
            request = self.gcp_client.machineTypes().list(project=self.gcp_project, zone=zone, filter=filter_string)
            while request is not None:
                response = request.execute()
                for machine_type in response['items']:
                    if not machine_type['name'].startswith(tuple(ComputeTypes().as_list())):
                        continue
                    config_block = {'name': machine_type['name'],
                                    'id': machine_type['id'],
                                    'cpu': int(machine_type['guestCpus']),
                                    'memory': int(machine_type['memoryMb']),
                                    'description': machine_type['description']}
                    machine_type_list.append(config_block)
                request = self.gcp_client.machineTypes().list_next(previous_request=request, previous_response=response)
        except Exception as err:
            raise GCPDriverError(f"error listing machine types: {err}")

        if len(machine_type_list) == 0:
            raise EmptyResultSet(f"no instance types found")

        return machine_type_list

    def get_machine_types(self, zone: str, architecture: str = 'x86_64'):
        result_list = []
        machine_list = self.list(zone, architecture)
        machine_list = sorted(machine_list, key=lambda m: m['name'])

        for machine_type in C.MACHINE_TYPES:
            machine = next((m for m in machine_list if m['cpu'] == machine_type['cpu'] and m['memory'] == machine_type['memory']), None)
            if not machine:
                continue
            machine.update(dict(machine_type=machine_type['name']))
            result_list.append(machine)

        return result_list

    def get_machine(self, name: str, zone: str, architecture: str = 'x86_64'):
        machine_list = self.get_machine_types(zone, architecture)
        return next((m for m in machine_list if m['machine_type'] == name), None)

    def details(self, machine_type: str) -> dict:
        try:
            request = self.gcp_client.machineTypes().get(project=self.gcp_project, zone=self.gcp_zone, machineType=machine_type)
            response = request.execute()
            return {'name': response['name'],
                    'id': response['id'],
                    'cpu': int(response['guestCpus']),
                    'memory': int(response['memoryMb']),
                    'description': response['description']}
        except Exception as err:
            GCPDriverError(f"error getting machine type details: {err}")
