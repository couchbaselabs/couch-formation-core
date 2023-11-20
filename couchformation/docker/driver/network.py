##
##

import logging
import ipaddress
from docker.types import IPAMPool, IPAMConfig
from docker.models.networks import Network as NetworkClass
from typing import Union, List
from couchformation.docker.driver.base import CloudBase, DockerDriverError

logger = logging.getLogger('couchformation.docker.driver.network')
logger.addHandler(logging.NullHandler())
logging.getLogger("docker").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


class Network(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, name: str = None) -> Union[List[dict], None]:
        network_list = []

        try:
            networks = self.client.networks.list()
        except Exception as err:
            raise DockerDriverError(f"error getting network list: {err}")

        for network_entry in list(n.attrs for n in networks):
            if name and network_entry.get('Name') != name:
                continue
            if network_entry.get('Driver') != 'bridge':
                continue
            net_block = {'cidr': network_entry.get('IPAM').get('Config')[0].get('Subnet'),
                         'gateway': network_entry.get('IPAM').get('Config')[0].get('Gateway'),
                         'id': network_entry.get('Id')}
            network_list.append(net_block)

        if len(network_list) == 0:
            return None
        else:
            return network_list

    @property
    def cidr_list(self):
        try:
            for item in self.list():
                yield item['cidr']
        except TypeError:
            return iter(())

    def get_network(self, name: str):
        return next((n for n in self.client.networks.list() if n.name == name), None)

    def create(self, name: str, cidr: str) -> NetworkClass:
        if self.get_network(name):
            return self.get_network(name)
        try:
            net = ipaddress.IPv4Network(cidr)
            ipam_pool = IPAMPool(
                subnet=cidr,
                gateway=str(net[1])
            )
            ipam_config = IPAMConfig(
                pool_configs=[ipam_pool]
            )
            result = self.client.networks.create(name, driver="bridge", ipam=ipam_config)
            return result
        except Exception as err:
            raise DockerDriverError(f"error creating network: {err}")

    def delete(self, name: str) -> None:
        try:
            network_id = self.get_network(name)
            if network_id:
                network_id.remove()
        except Exception as err:
            raise DockerDriverError(f"error deleting network: {err}")
