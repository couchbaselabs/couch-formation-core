##
##

import logging
import base64
import time
import googleapiclient.errors
import datetime
import copy
import json
from typing import Union
from couchformation.gcp.driver.base import CloudBase, GCPDriverError
from couchformation.ssh import SSHUtil

logger = logging.getLogger('couchformation.gcp.driver.instance')
logger.addHandler(logging.NullHandler())
logging.getLogger("googleapiclient").setLevel(logging.ERROR)


class Instance(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def run(self,
            name: str,
            image_project: str,
            image_name: str,
            sa_email: Union[str, None],
            zone: str,
            vpc: str,
            subnet: str,
            username: str,
            ssh_key: str,
            swap_disk,
            data_disk,
            root_size="256",
            disk_type: str = "pd-ssd",
            machine_type="n2-standard-2",
            virtualization: bool = False):
        operation = {}
        instance_body = {
            "name": name,
            "zone": zone,
            "networkInterfaces": [
                {
                    "network": f"projects/{self.gcp_project}/global/networks/{vpc}",
                    "subnetwork": f"regions/{self.gcp_region}/subnetworks/{subnet}",
                    "accessConfigs": [
                        {
                            "name": "external-nat",
                            "type": "ONE_TO_ONE_NAT",
                            "networkTier": "PREMIUM"
                        }
                    ]
                }
            ],
            "metadata": {
                "items": [
                    {
                        "key": "ssh-keys",
                        "value": f"{username}:{ssh_key}"
                    }
                ]
            },
            "disks": [
                {
                    "boot": True,
                    "initializeParams": {
                        "sourceImage": f"projects/{image_project}/global/images/{image_name}",
                        "diskType": f"zones/{zone}/diskTypes/{disk_type}",
                        "diskSizeGb": str(round(float(root_size)))
                    },
                    "autoDelete": True
                },
                {
                    "source": f"zones/{zone}/disks/{swap_disk}"
                },
                {
                    "source": f"zones/{zone}/disks/{data_disk}"
                }
            ],
            "machineType": f"zones/{zone}/machineTypes/{machine_type}"
        }

        if virtualization:
            instance_body.update({
                "advancedMachineFeatures": {
                    "enableNestedVirtualization": True
                }
            })

        if sa_email:
            instance_body.update({
                "serviceAccounts": [
                    {
                        "email": sa_email,
                        "scopes": [
                            "https://www.googleapis.com/auth/cloud-platform"
                        ]
                    }
                ]
            })

        try:
            request = self.gcp_client.instances().insert(project=self.gcp_project, zone=zone, body=instance_body)
            operation = request.execute()
            self.wait_for_zone_operation(operation['name'], zone)
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "alreadyExists":
                raise GCPDriverError(f"can not create instance: {err}")
        except Exception as err:
            raise GCPDriverError(f"error creating instance: {err}")

        return operation.get('targetLink')

    def details(self, instance: str, zone: str) -> Union[dict, None]:
        try:
            request = self.gcp_client.instances().get(project=self.gcp_project, zone=zone, instance=instance)
            response = request.execute()
            return response
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "notFound":
                raise GCPDriverError(f"can not find instance: {err}")
            return None
        except Exception as err:
            raise GCPDriverError(f"error getting instance details: {err}")

    def find(self, instance: str) -> Union[dict, None]:
        for zone in self.gcp_zone_list:
            result = self.details(instance, zone)
            if result:
                return result
        return None

    def terminate(self, instance: str, zone: str) -> None:
        try:
            request = self.gcp_client.instances().delete(project=self.gcp_project, zone=zone, instance=instance)
            operation = request.execute()
            self.wait_for_zone_operation(operation['name'], zone)
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "notFound":
                raise GCPDriverError(f"can not terminate instance: {err}")
        except Exception as err:
            raise GCPDriverError(f"error terminating instance: {err}")

    def gen_password(self, user: str, instance: str, zone: str, sa_email: str, ssh_key: str):
        instance_ref = self.details(instance, zone)
        old_metadata = instance_ref['metadata']

        mod, exp = SSHUtil().get_mod_exp(ssh_key)
        modulus = base64.b64encode(mod)
        exponent = base64.b64encode(exp)

        utc_now = datetime.datetime.utcnow()
        expire_time = utc_now + datetime.timedelta(minutes=5)
        expire = expire_time.strftime('%Y-%m-%dT%H:%M:%SZ')

        metadata_entry = {'userName': user,
                          'modulus': modulus.decode('utf-8'),
                          'exponent': exponent.decode('utf-8'),
                          'email': sa_email,
                          'expireOn': expire}

        new_metadata = copy.deepcopy(old_metadata)
        new_metadata['items'] = [{
            'key': "windows-keys",
            'value': json.dumps(metadata_entry)
        }]

        request = self.gcp_client.instances().setMetadata(project=self.gcp_project,
                                                          zone=zone,
                                                          instance=instance,
                                                          body=new_metadata)
        operation = request.execute()
        self.wait_for_zone_operation(operation['name'], zone)

        logger.info(f"Waiting for instance {instance} password")
        while True:
            request = self.gcp_client.instances().getSerialPortOutput(project=self.gcp_project,
                                                                      zone=zone,
                                                                      instance=instance,
                                                                      port=4)
            operation = request.execute()
            serial_port_output = operation['contents']
            if len(serial_port_output) != 0:
                break
            else:
                time.sleep(2)

        output = serial_port_output.split('\n')
        for data in output:
            try:
                entry = json.loads(data)
                if modulus.decode('utf-8') == entry['modulus']:
                    enc_password = entry['encryptedPassword']
                    decoded_password = base64.b64decode(enc_password)
                    password = SSHUtil().decrypt_with_rsa(decoded_password, ssh_key)
                    return password.decode('utf-8')
            except ValueError:
                pass
