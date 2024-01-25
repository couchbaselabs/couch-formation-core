##
##

import logging
from typing import List, Union
import googleapiclient.errors
from couchformation.gcp.driver.base import CloudBase, GCPDriverError, EmptyResultSet

logger = logging.getLogger('couchformation.gcp.driver.disk')
logger.addHandler(logging.NullHandler())
logging.getLogger("googleapiclient").setLevel(logging.ERROR)


class Disk(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, zone: str) -> List[dict]:
        disk_list = []

        try:
            request = self.gcp_client.disks().list(project=self.gcp_project, zone=zone)
            while request is not None:
                response = request.execute()

                for disk in response['items']:
                    disk_list.append(disk)
                request = self.gcp_client.disks().list_next(previous_request=request, previous_response=response)
        except Exception as err:
            raise GCPDriverError(f"error listing disks: {err}")

        if len(disk_list) == 0:
            raise EmptyResultSet(f"no disks found")
        else:
            return disk_list

    def create(self, name: str, zone: str, size: str, disk_type: str = "pd-ssd") -> str:
        operation = {}
        disk_body = {
            "sizeGb": str(round(float(size))),
            "name": name,
            "type": f"zones/{zone}/diskTypes/{disk_type}"
        }
        try:
            request = self.gcp_client.disks().insert(project=self.gcp_project, zone=zone, body=disk_body)
            operation = request.execute()
            self.wait_for_zone_operation(operation['name'], zone)
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "alreadyExists":
                raise GCPDriverError(f"can not create disk: {err}")
        except Exception as err:
            raise GCPDriverError(f"error creating disk: {err}")

        return operation.get('targetLink')

    def delete(self, disk: str, zone: str) -> None:
        try:
            request = self.gcp_client.disks().delete(project=self.gcp_project, zone=zone, disk=disk)
            operation = request.execute()
            self.wait_for_zone_operation(operation['name'], zone)
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "notFound":
                raise GCPDriverError(f"can not delete disk: {err}")
        except Exception as err:
            raise GCPDriverError(f"error deleting disk: {err}")

    def details(self, disk: str, zone: str) -> Union[dict, None]:
        try:
            request = self.gcp_client.disks().get(project=self.gcp_project, zone=zone, disk=disk)
            result = request.execute()
            return result
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "notFound":
                raise GCPDriverError(f"can not find disk: {err}")
            return None
        except Exception as err:
            raise GCPDriverError(f"error getting disk: {err}")

    def find(self, disk: str) -> Union[dict, None]:
        for zone in self.gcp_zone_list:
            result = self.details(disk, zone)
            if result:
                return result
        return None
