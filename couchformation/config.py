##
##

import os
from typing import Optional, Union, List
from enum import Enum
from pathlib import Path
import attr
import argparse
import yaml
import itertools
import couchformation.constants as C


def get_base_dir():
    if 'COUCH_FORMATION_CONFIG_DIR' in os.environ:
        return os.environ['COUCH_FORMATION_CONFIG_DIR']
    else:
        return C.STATE_DIRECTORY


def get_log_dir():
    if 'COUCH_FORMATION_LOG_DIR' in os.environ:
        return os.environ['COUCH_FORMATION_LOG_DIR']
    else:
        return C.LOG_DIRECTORY


def get_root_dir():
    return C.ROOT_DIRECTORY


def get_resource_dir(name: str, tag: str):
    return os.path.join(get_base_dir(), name, tag)


def get_project_dir(name: str):
    return os.path.join(get_base_dir(), name)


def get_state_file(project: str, name: str):
    return os.path.join(get_project_dir(project), name, C.STATE)


def get_state_dir(project: str, name: str):
    return os.path.join(get_project_dir(project), name)


def str_to_int(value: Union[str, int]) -> int:
    return int(value)


class AuthMode(Enum):
    default = 0
    sso = 1
    file = 2


class PathMode(Enum):
    resource = 0
    common = 1


class ProvisionMode(Enum):
    public = 0
    private = 1


@attr.s
class Parameters:
    project: Optional[str] = attr.ib(default=None)
    cloud: Optional[str] = attr.ib(default=None)
    name: Optional[str] = attr.ib(default=None)
    model: Optional[str] = attr.ib(default=None)
    region: Optional[str] = attr.ib(default=None)
    ssh_key: Optional[str] = attr.ib(default=None)
    os_id: Optional[str] = attr.ib(default=None)
    os_version: Optional[str] = attr.ib(default=None)
    auth_mode: Optional[str] = attr.ib(default=None)
    profile: Optional[str] = attr.ib(default=None)
    base_dir: Optional[str] = attr.ib(default=None)
    private_ip: Optional[bool] = attr.ib(default=None)
    path_mode: Optional[PathMode] = attr.ib(default=None)
    machine_type: Optional[str] = attr.ib(default=None)
    quantity: Optional[int] = attr.ib(default=None)
    services: Optional[str] = attr.ib(default=None)
    volume_iops: Optional[str] = attr.ib(default=None)
    volume_size: Optional[str] = attr.ib(default=None)
    volume_type: Optional[str] = attr.ib(default=None)
    volume_tier: Optional[str] = attr.ib(default=None)
    root_size: Optional[str] = attr.ib(default=None)
    connect_svc: Optional[str] = attr.ib(default=None)
    connect_ip: Optional[str] = attr.ib(default=None)

    @classmethod
    def create(cls, args):
        c = cls()
        c.initialize_args(args)
        return c

    def initialize_args(self, args):
        parser = argparse.ArgumentParser(add_help=False)
        for attribute in self.__annotations__:
            parser.add_argument(f"--{attribute}", action='store')
        parameters, remainder = parser.parse_known_args(args)
        self.from_namespace(parameters)

    def from_namespace(self, namespace: argparse.Namespace):
        args = vars(namespace)
        for attribute in self.__annotations__:
            if args.get(attribute):
                setattr(self, attribute, args.get(attribute))

    def from_dict(self, options: dict):
        for attribute in self.__annotations__:
            if options.get(attribute):
                setattr(self, attribute, options.get(attribute))

    @property
    def project_dir(self):
        return get_project_dir(self.project)

    @property
    def as_dict(self):
        return {k: self.__dict__[k] for k in self.__dict__ if self.__dict__[k] is not None}


@attr.s
class BaseConfig:
    project: Optional[str] = attr.ib(default="resources")
    ssh_key: Optional[str] = attr.ib(default=os.path.join(Path.home(), '.ssh', 'couch-formation-key.pem'))
    base_dir: Optional[str] = attr.ib(default=get_base_dir())
    private_ip: Optional[bool] = attr.ib(default=False)

    @classmethod
    def create(cls, data: Union[list, dict]):
        if type(data) is list:
            c = cls()
            c.initialize_args(data)
        else:
            c = cls()
            c.initialize_dict(data)
        return c

    def initialize_args(self, args):
        parser = argparse.ArgumentParser(add_help=False)
        for attribute in self.__annotations__:
            parser.add_argument(f"--{attribute}", action='store')
        parameters, remainder = parser.parse_known_args(args)
        self.from_namespace(parameters)

    def initialize_dict(self, options):
        self.from_dict(options)

    @property
    def project_dir(self):
        return get_project_dir(self.project)

    def from_namespace(self, namespace: argparse.Namespace):
        args = vars(namespace)
        for attribute in self.__annotations__:
            if args.get(attribute):
                setattr(self, attribute, args.get(attribute))

    def from_dict(self, options: dict):
        for attribute in self.__annotations__:
            if options.get(attribute):
                setattr(self, attribute, options.get(attribute))

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class NodeConfig:
    machine_type: Optional[str] = attr.ib(default=None)
    quantity: Optional[int] = attr.ib(default=1, converter=str_to_int)
    services: Optional[str] = attr.ib(default="default")
    volume_iops: Optional[str] = attr.ib(default="3000")
    volume_size: Optional[str] = attr.ib(default="256")
    volume_type: Optional[str] = attr.ib(default=None)
    root_size: Optional[str] = attr.ib(default="256")

    @classmethod
    def create(cls, data: Union[list, dict]):
        if type(data) is list:
            c = cls()
            c.initialize_args(data)
        else:
            c = cls()
            c.initialize_dict(data)
        return c

    def initialize_args(self, args):
        parser = argparse.ArgumentParser(add_help=False)
        for attribute in self.__annotations__:
            parser.add_argument(f"--{attribute}", action='store')
        parameters, undefined = parser.parse_known_args(args)
        self.from_namespace(parameters)

    def initialize_dict(self, options):
        self.from_dict(options)

    def from_namespace(self, namespace: argparse.Namespace):
        args = vars(namespace)
        for attribute in self.__annotations__:
            if args.get(attribute):
                setattr(self, attribute, args.get(attribute))

    def from_dict(self, options: dict):
        for attribute in self.__annotations__:
            if options.get(attribute):
                setattr(self, attribute, options.get(attribute))

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class DeploymentConfig:
    core: Optional[BaseConfig] = attr.ib(default=BaseConfig())
    config: Optional[List[NodeConfig]] = attr.ib(default=[])

    def add_config(self, index: Union[str, int], config: NodeConfig):
        index = int(index)
        config.group = str(index)
        if index > len(self.config) + 1:
            raise ValueError(f"config index {index} out of range")
        elif index == len(self.config) + 1:
            self.config.append(config)
        else:
            self.config[index - 1] = config

    @classmethod
    def new(cls, core: BaseConfig):
        return cls(
            core,
            []
        )

    def reset(self, args):
        self.config.clear()
        self.core = BaseConfig().create(args)

    @property
    def length(self):
        return len(self.config)

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class NodeEntry:
    name: Optional[str] = attr.ib(default=None)
    username: Optional[str] = attr.ib(default=None)
    private_ip: Optional[str] = attr.ib(default=None)
    public_ip: Optional[str] = attr.ib(default=None)
    use_private_ip: Optional[bool] = attr.ib(default=False)
    availability_zone: Optional[str] = attr.ib(default=None)
    services: Optional[str] = attr.ib(default=None)
    connect_svc: Optional[str] = attr.ib(default=None)
    connect_ip: Optional[str] = attr.ib(default=None)

    @classmethod
    def create(cls,
               name: str,
               username: str,
               private_ip: str,
               public_ip: str = None,
               use_private_ip: bool = False,
               zone: str = None,
               services: str = "default",
               connect_svc: str = None,
               connect_ip: str = None
               ):
        return cls(
            name,
            username,
            private_ip,
            public_ip,
            use_private_ip,
            zone,
            services,
            connect_svc,
            connect_ip
        )


@attr.s
class NodeList:
    username: Optional[str] = attr.ib(default=None)
    ssh_key: Optional[str] = attr.ib(default=None)
    nodes: Optional[List[NodeEntry]] = attr.ib(default=[])
    working_dir: Optional[str] = attr.ib(default=None)
    provision_ip: Optional[ProvisionMode] = attr.ib(default=ProvisionMode.public)

    @classmethod
    def create(cls, username: str, ssh_key: str, working_dir: str = None, use_private_ip: bool = False):
        return cls(
            username,
            ssh_key,
            [],
            working_dir,
            ProvisionMode(use_private_ip)
        )

    def add(self, name: str, private_ip: str, public_ip: str = None, zone: str = None, services: str = "default", connect_svc: str = None, connect_ip: str = None):
        self.nodes.append(
            NodeEntry.create(
                name,
                self.username,
                private_ip,
                public_ip,
                bool(self.provision_ip.value),
                zone,
                services,
                connect_svc,
                connect_ip
            )
        )

    @property
    def node_list(self) -> List[NodeEntry]:
        return self.nodes

    def list_public_ip(self):
        address_list = []
        for entry in self.nodes:
            address_list.append(entry.public_ip)
        return address_list

    def list_private_ip(self):
        address_list = []
        for entry in self.nodes:
            address_list.append(entry.private_ip)
        return address_list

    def provision_list(self):
        if self.provision_ip == ProvisionMode.public:
            return self.list_public_ip()
        else:
            return self.list_private_ip()

    def ip_csv_list(self):
        return ','.join(self.list_private_ip())


@attr.s
class PortSettings:
    build: Optional[str] = attr.ib(default=None)
    tcp_ports: Optional[List[int]] = attr.ib(default=[])
    udp_ports: Optional[List[int]] = attr.ib(default=[])

    @classmethod
    def create(cls, name: str, port_config: List[str]):
        tcp_list = []
        udp_list = []
        tcp_ports = []
        udp_ports = []
        for spec in port_config:
            port_spec = spec.split('/')
            port_nums = port_spec[0]
            if len(port_spec) > 1:
                port_proto = port_spec[1]
            else:
                port_proto = 'tcp'
            if port_proto == 'tcp':
                tcp_list.append(port_nums)
            else:
                udp_list.append(port_nums)
        for ports in tcp_list:
            port_split = ports.split('-')
            if len(port_split) > 1:
                tcp_ports.extend(list(range(int(port_split[0]), int(port_split[1])+1)))
            else:
                tcp_ports.append(int(port_split[0]))
        for ports in udp_list:
            port_split = ports.split('-')
            if len(port_split) > 1:
                udp_ports.extend(list(range(int(port_split[0]), int(port_split[1])+1)))
            else:
                udp_ports.append(int(port_split[0]))
        tcp_ports.sort()
        udp_ports.sort()

        return cls(
            name,
            tcp_ports,
            udp_ports
        )

    @property
    def has_tcp_ports(self):
        return len(self.tcp_ports) > 0

    @property
    def has_udp_ports(self):
        return len(self.udp_ports) > 0

    @staticmethod
    def ranges(ports: List[int]):
        for a, b in itertools.groupby(enumerate(ports), lambda pair: pair[1] - pair[0]):
            b = list(b)
            yield b[0][1], b[-1][1]

    def tcp_as_tuple(self):
        for begin, end in self.ranges(self.tcp_ports):
            yield begin, end

    def udp_as_tuple(self):
        for begin, end in self.ranges(self.udp_ports):
            yield begin, end

    def tcp_as_ranges(self):
        for begin, end in self.ranges(self.tcp_ports):
            if begin < end:
                yield f"{begin}-{end}"
            else:
                yield str(begin)

    def udp_as_ranges(self):
        for begin, end in self.ranges(self.udp_ports):
            if begin < end:
                yield f"{begin}-{end}"
            else:
                yield str(begin)


@attr.s
class PortSettingSet:
    config: Optional[List[PortSettings]] = attr.ib(default=[])

    @classmethod
    def create(cls):
        profile = []
        with open(C.NODE_PORT_PROFILE, "r") as f:
            try:
                for build, settings in yaml.safe_load(f).items():
                    port_settings = PortSettings.create(build, settings.get('ports', []))
                    profile.append(port_settings)
                return cls(
                    profile
                )
            except yaml.YAMLError as err:
                raise RuntimeError(f"Can not open port config file {C.NODE_PORT_PROFILE}: {err}")

    def get(self, name: str):
        return next((o for o in self.config if o.build == name), None)

    def items(self):
        return self.config
