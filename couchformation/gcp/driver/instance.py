##
##

import logging
import googleapiclient.errors
from couchformation.gcp.driver.base import CloudBase, GCPDriverError

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
            sa_email,
            zone: str,
            vpc: str,
            subnet: str,
            username: str,
            ssh_key: str,
            swap_disk,
            data_disk,
            root_size="256",
            disk_type: str = "pd-ssd",
            machine_type="n2-standard-2"):
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
            "serviceAccounts": [
                {
                    "email": sa_email,
                    "scopes": [
                        "https://www.googleapis.com/auth/cloud-platform"
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

    def details(self, instance: str, zone: str) -> dict:
        try:
            request = self.gcp_client.instances().get(project=self.gcp_project, zone=zone, instance=instance)
            response = request.execute()
            return response
        except Exception as err:
            raise GCPDriverError(f"error getting instance details: {err}")

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
