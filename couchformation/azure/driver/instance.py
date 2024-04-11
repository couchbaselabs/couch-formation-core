##
##

import logging
import json
from azure.core.exceptions import ResourceNotFoundError
from couchformation.azure.driver.base import CloudBase, AzureDriverError
from couchformation.azure.driver.constants import AzureImagePublishers

logger = logging.getLogger('couchformation.azure.driver.instance')
logger.addHandler(logging.NullHandler())
logging.getLogger("azure").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

WIN_INIT_SCRIPT = """winrm quickconfig -q -force
winrm set winrm/config/service/auth '@{Basic="true"}'
$hostname = $env:computername
$certificateThumbprint = (New-SelfSignedCertificate -DnsName "${hostname}" -CertStoreLocation Cert:\LocalMachine\My).Thumbprint
winrm create winrm/config/Listener?Address=*+Transport=HTTPS "@{Hostname=`"${hostname}`"; CertificateThumbprint=`"${certificateThumbprint}`"}"
netsh advfirewall firewall add rule name="Windows Remote Management (HTTPS-In)" dir=in action=allow protocol=TCP localport=5986
"""


class Instance(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def run(self,
            name: str,
            image_publisher: str,
            image_offer: str,
            image_sku: str,
            zone: str,
            nic_id: str,
            username: str,
            public_key: str,
            resource_group: str,
            root_disk_name: str,
            root_type="Premium_LRS",
            root_size=256,
            machine_type="Standard_D4_v3",
            password="Passw0rd!",
            ultra=False):
        if not resource_group:
            resource_group = self.azure_resource_group

        instance_info = self.details(name, resource_group)
        if instance_info:
            return instance_info

        image_os = next((o['os_id'] for o in AzureImagePublishers.publishers if o['name'] == image_publisher), None)

        image_block = {
            'publisher': image_publisher,
            'offer': image_offer,
            'sku': image_sku,
            'version': 'latest'
        }

        parameters = {
            'location': self.azure_location,
            'zones': [zone],
            'os_profile': {
                'computer_name': name,
                'admin_username': username
            },
            'hardware_profile': {
                'vm_size': machine_type
            },
            'storage_profile': {
                'image_reference': image_block,
                'os_disk': {
                    'name': root_disk_name,
                    'disk_size_gb': root_size,
                    'create_option': 'FromImage',
                    'managed_disk': {
                        'storage_account_type': root_type
                    }
                }
            },
            'network_profile': {
                'network_interfaces': [{
                    'id': nic_id,
                }]
            },
        }

        if image_os == 'windows':
            os_config_block = {
                'admin_password': password,
                'windows_configuration': {
                    'enable_automatic_updates': False
                }
            }
        else:
            os_config_block = {
                'linux_configuration': {
                    'ssh': {
                        'public_keys': [
                            {
                                'path': f"/home/{username}/.ssh/authorized_keys",
                                'key_data': public_key
                            }
                        ]
                    }
                }
            }

        parameters['os_profile'].update(os_config_block)
        if ultra:
            parameters['additional_capabilities'] = {}
            parameters['additional_capabilities']['ultra_ssd_enabled'] = True

        logger.debug(f"Creating instance {name} with parameters:\n{json.dumps(parameters, indent=2)}")
        try:
            request = self.compute_client.virtual_machines.begin_create_or_update(resource_group, name, parameters)
            request.wait()
            if image_os == 'windows':
                result = self.run_command(WIN_INIT_SCRIPT, name, resource_group)
                if result.exit_code != 0:
                    raise AzureDriverError(f"error running instance config script: {result.error}")
            return request.result()
        except Exception as err:
            raise AzureDriverError(f"error creating instance: {err}")

    def attach_disk(self, instance: str, caching: str, lun: str, disk_id: str, resource_group: str):
        parameters = {
            'caching': caching,
            'lun': lun,
            'create_option': 'Attach',
            'managed_disk': {
                'id': disk_id
            }
        }

        try:
            vm = self.compute_client.virtual_machines.get(resource_group, instance)
            vm.storage_profile.data_disks.append(parameters)
            request = self.compute_client.virtual_machines.begin_create_or_update(resource_group, instance, vm)
            request.wait()
            return request.result()
        except Exception as err:
            raise AzureDriverError(f"error attaching disk: {err}")

    def details(self, instance: str, resource_group: str):
        try:
            machine = self.compute_client.virtual_machines.get(resource_group, instance)
            return machine
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error getting instance {instance}: {err}")

    def terminate(self, instance: str, resource_group: str) -> None:
        try:
            request = self.compute_client.virtual_machines.begin_delete(resource_group, instance)
            request.wait()
        except ResourceNotFoundError:
            return None
        except Exception as err:
            raise AzureDriverError(f"error deleting instance: {err}")

    def run_command(self, command: str, vm_name: str, resource_group: str):
        run_command_name = "RunPowerShellScript"

        run_command = {
            'command_id': 'RunPowerShellScript',
            'location': self.azure_location,
            'source': {
                'script': command
            }
        }

        request = self.compute_client.virtual_machine_run_commands.begin_create_or_update(resource_group, vm_name, run_command_name, run_command)
        request.wait()
        result = self.compute_client.virtual_machine_run_commands.get_by_virtual_machine(resource_group, vm_name, run_command_name, expand="instanceView")
        iw = result.instance_view
        return iw
