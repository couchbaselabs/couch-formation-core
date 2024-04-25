##
##

import re
import logging
from typing import List, Union
import googleapiclient.errors
from couchformation.gcp.driver.base import CloudBase, GCPDriverError, EmptyResultSet

logger = logging.getLogger('couchformation.gcp.driver.firewall')
logger.addHandler(logging.NullHandler())
logging.getLogger("googleapiclient").setLevel(logging.ERROR)


class Firewall(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self) -> List[dict]:
        firewall_list = []

        try:
            request = self.gcp_client.firewalls().list(project=self.gcp_project)
            while request is not None:
                response = request.execute()

                for firewall in response['items']:
                    firewall_list.append(firewall)
                request = self.gcp_client.firewalls().list_next(previous_request=request, previous_response=response)
        except Exception as err:
            raise GCPDriverError(f"error listing firewall rules: {err}")

        if len(firewall_list) == 0:
            raise EmptyResultSet(f"no firewalls found")
        else:
            return firewall_list

    def search(self, pattern: str) -> List[dict]:
        firewall_list = []
        for entry in self.list():
            if re.search(pattern, entry['name']):
                firewall_list.append(entry)
        return firewall_list

    def create_ingress(self, name: str, network: str, cidr: str, protocol: str = "tcp", ports: Union[List[str], None] = None, udp_ports: Union[List[str], None] = None) -> str:
        operation = {}
        firewall_body = {
            "sourceRanges": [
                cidr,
            ],
            "description": "Couch Formation generated firewall rule",
            "allowed": [
                {
                    "IPProtocol": protocol,
                },
            ],
            "network": f"global/networks/{network}",
            "name": name,
        }
        if ports:
            firewall_body['allowed'][0]['ports'] = []
            firewall_body['allowed'][0]['ports'].extend(ports)
        if udp_ports:
            firewall_body['allowed'].append(dict(
                IPProtocol="udp",
                ports=udp_ports
            ))
        try:
            request = self.gcp_client.firewalls().insert(project=self.gcp_project, body=firewall_body)
            operation = request.execute()
            self.wait_for_global_operation(operation['name'])
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "alreadyExists":
                raise GCPDriverError(f"can not create firewall rule: {err}")
        except Exception as err:
            raise GCPDriverError(f"error creating firewall rule: {err}")

        return operation.get('targetLink')

    def delete(self, firewall: str) -> None:
        try:
            request = self.gcp_client.firewalls().delete(project=self.gcp_project, firewall=firewall)
            operation = request.execute()
            self.wait_for_global_operation(operation['name'])
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "notFound":
                raise GCPDriverError(f"can not delete firewall rule: {err}")
        except Exception as err:
            raise GCPDriverError(f"error deleting firewall rule: {err}")

    def details(self, firewall: str) -> Union[dict, None]:
        try:
            request = self.gcp_client.firewalls().get(project=self.gcp_project, firewall=firewall)
            result = request.execute()
            return result
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "notFound":
                raise GCPDriverError(f"can not find firewall entry: {err}")
            return None
        except Exception as err:
            raise GCPDriverError(f"error getting firewall rule: {err}")
