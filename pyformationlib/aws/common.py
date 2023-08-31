##
##

from enum import Enum
import attr
import argparse
from typing import Optional, Union
from pyformationlib.config import BaseConfig


def str_to_int(value: Union[str, int]) -> int:
    return int(value)


class AuthMode(Enum):
    default = 0
    sso = 1


@attr.s
class AWSConfig:
    core: Optional[BaseConfig] = attr.ib(default=None)
    region: Optional[str] = attr.ib(default=None)
    os_id: Optional[str] = attr.ib(default=None)
    os_version: Optional[str] = attr.ib(default=None)
    ssh_key: Optional[str] = attr.ib(default=None)
    machine_type: Optional[str] = attr.ib(default=None)
    quantity: Optional[int] = attr.ib(default=1, converter=str_to_int)
    volume_iops: Optional[str] = attr.ib(default="3000")
    volume_size: Optional[str] = attr.ib(default="256")
    volume_type: Optional[str] = attr.ib(default="gp3")
    root_size: Optional[str] = attr.ib(default="256")
    auth_mode: Optional[str] = attr.ib(default="default")
    profile: Optional[str] = attr.ib(default='default')

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
        self.core = BaseConfig().create(args)
        parser = argparse.ArgumentParser(add_help=False)
        for attribute in self.__annotations__:
            parser.add_argument(f"--{attribute}", action='store')
        parameters, undefined = parser.parse_known_args(args)
        self.from_namespace(parameters)

    def initialize_dict(self, options):
        self.core = BaseConfig().create(options)
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
    def auth(self) -> AuthMode:
        return AuthMode[self.auth_mode]

    @property
    def as_dict(self):
        return self.__dict__
