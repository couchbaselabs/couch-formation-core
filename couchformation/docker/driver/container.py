##
##

import logging
import docker
from docker.errors import APIError
from docker.models.containers import Container as ContainerClass
from typing import Union, List
from couchformation.docker.driver.base import CloudBase, DockerDriverError

logger = logging.getLogger('couchformation.docker.driver.network')
logger.addHandler(logging.NullHandler())
logging.getLogger("docker").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


class Container(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, name: str = None) -> Union[List[dict], None]:
        container_list = []

        try:
            containers = self.client.containers.list()
        except Exception as err:
            raise DockerDriverError(f"error getting container list: {err}")

        for container in containers:
            if name and container.name != name:
                continue
            container_block = {'name': container.name,
                               'short_id': container.short_id,
                               'status': container.status,
                               'id': container.id}
            container_list.append(container_block)

        if len(container_list) == 0:
            return None
        else:
            return container_list

    @staticmethod
    def expand_ranges(text):
        range_list = []
        for i in text.split(','):
            if '-' not in i:
                range_list.append(int(i))
            else:
                l, h = map(int, i.split('-'))
                range_list += range(l, h + 1)
        return range_list

    @staticmethod
    def create_port_dict(port_list: List[int]):
        result = {}
        for port in port_list:
            key = f"{port}/tcp"
            result.update({key: port})
        return result

    def run(self,
            image: str,
            name: str,
            volume_mount: Union[str, None] = None,
            volume_size: int = 2048,
            dir_mount: Union[str, None] = None,
            platform: Union[str, None] = None,
            ports: Union[str, None] = None,
            network: Union[str, None] = None,
            command: Union[str, list, None] = None) -> ContainerClass:
        if not platform:
            platform = self.arch
        if not ports:
            ports = "80,443"
        volume_map = None

        port_struct = self.create_port_dict(self.expand_ranges(ports))

        try:
            if volume_mount and not dir_mount:
                volume = self.client.volumes.create(name=f"{name}-vol", driver="local", driver_opts={"type": "tmpfs", "device": "tmpfs", "o": f"size={volume_size}m"})
                volume_map = [f"{volume.name}:{volume_mount}"]
            elif dir_mount:
                if not volume_mount:
                    volume_mount = dir_mount
                volume_map = [f"{dir_mount}:{volume_mount}"]
            container_id = self.client.containers.run(image,
                                                      tty=True,
                                                      detach=True,
                                                      platform=platform,
                                                      name=name,
                                                      ports=port_struct,
                                                      network=network,
                                                      volumes=volume_map,
                                                      command=command
                                                      )
        except docker.errors.APIError as e:
            if e.status_code == 409:
                container_id = self.client.containers.get(name)
            else:
                raise

        print("Container started")
        return container_id

    @staticmethod
    def get_container_id(name: str) -> Union[ContainerClass, None]:
        client = docker.from_env()
        try:
            return client.containers.get(name)
        except docker.errors.NotFound:
            return None

    def get_container_ip(self, name: str):
        container_id = self.get_container_id(name)
        try:
            return container_id.attrs['NetworkSettings']['IPAddress']
        except KeyError:
            return None

    def terminate(self, name: str) -> None:
        container_id = self.get_container_id(name)
        if not container_id:
            return
        client = docker.from_env()
        container_id.stop()
        container_id.remove()
        try:
            volume = client.volumes.get(f"{name}-vol")
            volume.remove()
        except docker.errors.NotFound:
            pass
