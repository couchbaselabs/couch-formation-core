##
##

import os
from typing import Optional, Union, List
from enum import Enum
import attr
import argparse
import pyformationlib.constants as C


def get_base_dir():
    if 'COUCH_FORMATION_CONFIG_DIR' in os.environ:
        return os.environ['COUCH_FORMATION_CONFIG_DIR']
    else:
        return C.STATE_DIRECTORY


def get_resource_dir(name: str, tag: str):
    return os.path.join(get_base_dir(), name, tag)


class PathMode(Enum):
    resource = 0
    common = 1


@attr.s
class BaseConfig:
    project: Optional[str] = attr.ib(default=None)
    name: Optional[str] = attr.ib(default=None)
    base_dir: Optional[str] = attr.ib(default=get_base_dir())
    path_mode: Optional[PathMode] = attr.ib(default=PathMode.resource)

    @classmethod
    def create(cls, data: Union[list, dict]):
        if type(data) == list:
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
    def working_dir(self):
        if self.path_mode == PathMode.resource:
            return get_resource_dir(self.project, self.name)
        else:
            return get_resource_dir(self.project, 'common')

    def common_mode(self):
        self.path_mode = PathMode.common

    def resource_mode(self):
        self.path_mode = PathMode.resource

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
class NodeEntry:
    name: Optional[str] = attr.ib(default=None)
    username: Optional[str] = attr.ib(default=None)
    private_ip: Optional[str] = attr.ib(default=None)
    public_ip: Optional[str] = attr.ib(default=None)

    @classmethod
    def create(cls,
               name,
               username,
               private_ip,
               public_ip):
        return cls(
            name,
            username,
            private_ip,
            public_ip
        )


@attr.s
class NodeList:
    username: Optional[str] = attr.ib(default=None)
    ssh_key: Optional[str] = attr.ib(default=None)
    nodes: Optional[List[NodeEntry]] = attr.ib(default=[])

    @classmethod
    def create(cls, username: str, ssh_key: str):
        return cls(
            username,
            ssh_key,
            []
        )

    def add(self, name: str, private_ip: str, public_ip: str):
        self.nodes.append(
            NodeEntry.create(
                name,
                self.username,
                private_ip,
                public_ip
            )
        )

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
