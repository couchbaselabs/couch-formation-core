##
##

import logging
from couchformation.aws.driver.base import CloudBase, AWSDriverError, EmptyResultSet
from couchformation.aws.driver.constants import ComputeTypes
import couchformation.constants as C

logger = logging.getLogger('couchformation.aws.driver.machine')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class MachineType(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, architecture: str = 'x86_64') -> list:
        type_list = []
        types = []
        filters = []
        prefix_list = []
        extra_args = {}

        for prefix in ComputeTypes().as_list():
            prefix_list.append(f"{prefix}.*")

        filters.append(
            {
                'Name': 'instance-type',
                'Values': prefix_list
            }
        )
        filters.append(
            {
                'Name': 'processor-info.supported-architecture',
                'Values': [architecture]
            }
        )

        try:
            while True:
                result = self.ec2_client.describe_instance_types(Filters=filters, **extra_args)
                types.extend(result['InstanceTypes'])
                if 'NextToken' not in result:
                    break
                extra_args['NextToken'] = result['NextToken']
        except Exception as err:
            raise AWSDriverError(f"error getting instance types: {err}")

        for machine in types:
            key_block = {'name': machine['InstanceType'],
                         'cpu': int(machine['VCpuInfo']['DefaultVCpus']),
                         'memory': int(machine['MemoryInfo']['SizeInMiB']),
                         'arch': machine.get('ProcessorInfo', {}).get('SupportedArchitectures'),
                         'clock': machine.get('ProcessorInfo', {}).get('SustainedClockSpeedInGhz'),
                         'network': machine.get('NetworkInfo', {}).get('NetworkPerformance'),
                         'nvme': machine.get('EbsInfo', {}).get('NvmeSupport'),
                         'hypervisor': machine.get('Hypervisor')}
            type_list.append(key_block)

        if len(type_list) == 0:
            raise EmptyResultSet(f"no instance types found")

        return type_list

    def get_machine_zones(self, instance_type: str):
        machine_filter = [
            {
                'Name': 'instance-type',
                'Values': [
                    instance_type,
                ]
            }
        ]
        try:
            result = self.ec2_client.describe_instance_type_offerings(LocationType='availability-zone', Filters=machine_filter)
            return list(loc['Location'] for loc in result.get('InstanceTypeOfferings', []))
        except Exception as err:
            raise AWSDriverError(f"error getting instance type details: {err}")

    def get_machine_types(self, architecture: str = 'x86_64'):
        result_list = []
        machine_list = self.list(architecture)
        machine_list = sorted(machine_list, key=lambda m: m['name'])

        for machine_type in C.MACHINE_TYPES:
            machine = next((m for m in machine_list if m['cpu'] == machine_type['cpu'] and m['memory'] == machine_type['memory']), None)
            if not machine:
                continue
            machine.update(dict(machine_type=machine_type['name']))
            result_list.append(machine)

        return result_list

    def get_machine(self, name: str, architecture: str = 'x86_64'):
        machine_list = self.get_machine_types(architecture)
        return next((m for m in machine_list if m['machine_type'] == name), None)

    def get_next_machine(self, name: str, architecture: str = 'x86_64'):
        machine_list = self.get_machine_types(architecture)
        index = next((i for (i, d) in enumerate(machine_list) if d['name'] == name), 0)
        return machine_list[index + 1]

    def details(self, instance_type: str) -> dict:
        try:
            result = self.ec2_client.describe_instance_types(InstanceTypes=[instance_type])
        except Exception as err:
            raise AWSDriverError(f"error getting instance type details: {err}")

        if len(result['InstanceTypes']) == 0:
            raise EmptyResultSet(f"can not find instance type {instance_type}")

        machine = result['InstanceTypes'][0]

        return {'name': machine['InstanceType'],
                'cpu': int(machine['VCpuInfo']['DefaultVCpus']),
                'memory': int(machine['MemoryInfo']['SizeInMiB']),
                'arch': machine.get('ProcessorInfo', {}).get('SupportedArchitectures'),
                'clock': machine.get('ProcessorInfo', {}).get('SustainedClockSpeedInGhz'),
                'network': machine.get('NetworkInfo', {}).get('NetworkPerformance'),
                'hypervisor': machine.get('Hypervisor')}
