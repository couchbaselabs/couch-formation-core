##
##

import logging
from typing import List, Union
import googleapiclient.errors
from couchformation.gcp.driver.base import CloudBase, GCPDriverError, EmptyResultSet

logger = logging.getLogger('couchformation.gcp.driver.network')
logger.addHandler(logging.NullHandler())
logging.getLogger("googleapiclient").setLevel(logging.ERROR)


class Network(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self) -> List[dict]:
        network_list = []

        try:
            request = self.gcp_client.networks().list(project=self.gcp_project)
            while request is not None:
                response = request.execute()

                for network in response['items']:
                    subnet_list = []
                    for subnet in network.get('subnetworks', []):
                        subnet_name = subnet.rsplit('/', 4)[-1]
                        region_name = subnet.rsplit('/', 4)[-3]
                        if region_name != self.region:
                            continue
                        result = Subnet(self.parameters).details(subnet_name)
                        subnet_list.append(result)
                    network_block = {'cidr': network.get('IPv4Range', None),
                                     'name': network['name'],
                                     'description': network.get('description', None),
                                     'subnets': subnet_list,
                                     'id': network['id']}
                    network_list.append(network_block)
                request = self.gcp_client.networks().list_next(previous_request=request, previous_response=response)
        except Exception as err:
            raise GCPDriverError(f"error listing networks: {err}")

        if len(network_list) == 0:
            raise EmptyResultSet(f"no networks found")
        else:
            return network_list

    @property
    def cidr_list(self):
        try:
            for network in self.list():
                for item in Subnet(self.parameters).list(network['name']):
                    yield item['cidr']
        except EmptyResultSet:
            return iter(())

    def create(self, name: str) -> str:
        operation = {}
        network_body = {
            "name": name,
            "autoCreateSubnetworks": False
        }
        try:
            request = self.gcp_client.networks().insert(project=self.gcp_project, body=network_body)
            operation = request.execute()
            self.wait_for_global_operation(operation['name'])
            return operation.get('targetLink')
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "alreadyExists":
                raise GCPDriverError(f"can not create network: {err}")
        except Exception as err:
            raise GCPDriverError(f"error creating network: {err}")

        return operation.get('targetLink')

    def delete(self, network: str) -> None:
        try:
            request = self.gcp_client.networks().delete(project=self.gcp_project, network=network)
            operation = request.execute()
            self.wait_for_global_operation(operation['name'])
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "notFound":
                raise GCPDriverError(f"can not delete network: {err}")
        except Exception as err:
            raise GCPDriverError(f"error deleting network: {err}")

    def details(self, network: str) -> Union[dict, None]:
        try:
            request = self.gcp_client.networks().get(project=self.gcp_project, network=network)
            result = request.execute()
            return result
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "notFound":
                raise GCPDriverError(f"can not find network: {err}")
            return None
        except Exception as err:
            raise GCPDriverError(f"error getting network: {err}")


class Subnet(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, network: str, region: Union[str, None] = None) -> List[dict]:
        subnet_list = []

        try:
            request = self.gcp_client.subnetworks().list(project=self.gcp_project, region=self.gcp_region)
            while request is not None:
                response = request.execute()
                for subnet in response['items']:
                    network_name = subnet['network'].rsplit('/', 1)[-1]
                    region_name = subnet['region'].rsplit('/', 1)[-1]
                    if region:
                        if region != region_name:
                            continue
                    if network != network_name:
                        continue
                    subnet_block = {'cidr': subnet['ipCidrRange'],
                                    'name': subnet['name'],
                                    'description': subnet.get('description', None),
                                    'gateway': subnet['gatewayAddress'],
                                    'network': network_name,
                                    'region': region_name,
                                    'id': subnet['id']}
                    subnet_list.append(subnet_block)
                request = self.gcp_client.subnetworks().list_next(previous_request=request, previous_response=response)
        except Exception as err:
            raise GCPDriverError(f"error listing subnets: {err}")

        if len(subnet_list) == 0:
            raise EmptyResultSet(f"no subnets found")
        else:
            return subnet_list

    def create(self, name: str, network: str, cidr: str) -> str:
        operation = {}
        network_info = Network(self.parameters).details(network)
        subnetwork_body = {
            "name": name,
            "network": network_info['selfLink'],
            "ipCidrRange": cidr,
            "region": self.gcp_region
        }
        try:
            request = self.gcp_client.subnetworks().insert(project=self.gcp_project, region=self.gcp_region, body=subnetwork_body)
            operation = request.execute()
            self.wait_for_regional_operation(operation['name'])
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "alreadyExists":
                raise GCPDriverError(f"can not create subnet: {err}")
        except Exception as err:
            raise GCPDriverError(f"error creating subnet: {err}")

        return operation.get('targetLink')

    def delete(self, subnet: str) -> None:
        try:
            request = self.gcp_client.subnetworks().delete(project=self.gcp_project, region=self.gcp_region, subnetwork=subnet)
            operation = request.execute()
            self.wait_for_regional_operation(operation['name'])
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "notFound":
                raise GCPDriverError(f"can not delete subnet: {err}")
        except Exception as err:
            raise GCPDriverError(f"error deleting subnet: {err}")

    def details(self, subnet: str) -> Union[dict, None]:
        try:
            request = self.gcp_client.subnetworks().get(project=self.gcp_project, region=self.gcp_region, subnetwork=subnet)
            result = request.execute()
            network_name = result['network'].rsplit('/', 1)[-1]
            region_name = result['region'].rsplit('/', 1)[-1]
            subnet_block = {'cidr': result['ipCidrRange'],
                            'name': result['name'],
                            'description': result.get('description', None),
                            'gateway': result['gatewayAddress'],
                            'network': network_name,
                            'region': region_name,
                            'id': result['id']}
            return subnet_block
        except googleapiclient.errors.HttpError as err:
            error_details = err.error_details[0].get('reason')
            if error_details != "notFound":
                raise GCPDriverError(f"can not find subnet: {err}")
            return None
        except Exception as err:
            raise GCPDriverError(f"error getting subnet: {err}")
