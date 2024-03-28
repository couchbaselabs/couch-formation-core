##
##

import io
import os
import logging
import docker
import jinja2
from jinja2.meta import find_undeclared_variables
from docker.errors import APIError
from docker.models.containers import Container as ContainerClass
from typing import Union, List, Set
from couchformation.docker.driver.base import CloudBase, DockerDriverError
from couchformation.docker.util import ContainerProfile, ContainerSpec
from couchformation.docker.driver.constants import ContainerBuildMap
from couchformation.util import FileManager
from couchformation.config import get_project_dir

logger = logging.getLogger('couchformation.docker.driver.container')
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
                               'ports': self.get_container_ports(container.name),
                               'ip_address': self.get_container_ip(container.name),
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
        if self.map(image):
            image = self.map(image)
        cp = ContainerProfile()
        ip = cp.get(image)
        volume_map = None

        if not platform:
            platform = self.arch
        if not ports:
            if ip.ports:
                ports = ip.ports
            else:
                ports = "80,443"
        if not volume_mount and ip.volume:
            volume_mount = ip.volume.directory
            if ip.volume.size:
                volume_size = ip.volume.size
        if not dir_mount and ip.volume.run:
            host_path = os.path.join(get_project_dir(self.project), self.name, 'mounts', name)
            dir_mount = host_path
            if ip.volume.run:
                run_cmd = self.process_command_vars(ip)
            else:
                run_cmd = None
            FileManager().dir_populate(str(host_path), run_cmd)
        if not command and ip.volume.command:
            command = ip.volume.command

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

        logger.debug("Container started")
        return container_id

    @staticmethod
    def map(name: str):
        return ContainerBuildMap().image(name)

    def get_container(self, container_id: str):
        return self.get_container_id(container_id)

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
            ip_address = container_id.attrs['NetworkSettings']['IPAddress']
            if len(ip_address) == 0:
                networks = container_id.attrs.get('NetworkSettings', {}).get('Networks', {})
                for network, settings in networks.items():
                    ip_address = settings.get('IPAddress')
                    if len(ip_address) > 0:
                        break
            return ip_address
        except KeyError:
            return None

    def get_container_ports(self, name: str):
        container_id = self.get_container_id(name)
        ports = list(p.split('/')[0] for p in container_id.attrs.get('Config', {}).get('ExposedPorts', {}).keys())
        return ports

    @staticmethod
    def get_file_parameters(input_text) -> Set[str]:
        env = jinja2.Environment(undefined=jinja2.DebugUndefined)
        template = env.from_string(input_text)
        rendered = template.render()
        ast = env.parse(rendered)
        return find_undeclared_variables(ast)

    def process_command_vars(self, profile: ContainerSpec) -> str:
        tags = []
        variables = self.get_file_parameters(profile.volume.run)
        for variable in variables:
            if variable.startswith('port'):
                ip_list = []
                try:
                    check_port = variable.split('_')[1]
                except IndexError:
                    check_port = "0"
                for container in self.list():
                    if check_port in container.get('ports'):
                        ip_list.append(container.get('ip_address'))
                ip_list_str = ','.join(ip_list)
                tags.append((variable, ip_list_str))
            elif variable == 'dir_name' and profile.volume.directory:
                tags.append((variable, profile.volume.directory))
        parameters = dict((a, b) for a, b in tags)
        raw_template = jinja2.Template(profile.volume.run)
        return raw_template.render(parameters)

    def run_in_container(self, name: str, command: Union[str, List[str]], directory: Union[str, None] = None):
        buffer = io.BytesIO()
        cmd_prefix = ['sh', '-c']
        container_id = self.get_container_id(name)
        if type(command) is str:
            command = [command]
        cmd_prefix.extend(command)
        exit_code, output = container_id.exec_run(cmd_prefix, workdir=directory)
        buffer.write(output)
        buffer.seek(0)
        return exit_code, buffer

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
