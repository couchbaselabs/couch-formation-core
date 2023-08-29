##
##
import attr
from enum import Enum
from attr.validators import instance_of as io
from typing import Iterable

CLOUD_KEY = "aws"


class AuthMode(Enum):
    default = 0
    sso = 1


@attr.s
class AWSTag(object):
    Key = attr.ib(validator=io(str))
    Value = attr.ib(validator=io(str))

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AWSTagStruct(object):
    ResourceType = attr.ib(validator=io(str))
    Tags = attr.ib(validator=io(Iterable))

    @classmethod
    def build(cls, resource: str):
        return cls(
            resource,
            []
        )

    def add(self, obj: AWSTag):
        self.Tags.append(obj.as_dict)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class EbsVolume(object):
    VolumeType = attr.ib(validator=io(str))
    VolumeSize = attr.ib(validator=io(int))

    @classmethod
    def build(cls, vol_type: str, vol_size: int):
        return cls(
            vol_type,
            vol_size
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AWSEbsDisk(object):
    DeviceName = attr.ib(validator=io(str))
    Ebs = attr.ib(validator=io(dict))

    @classmethod
    def build(cls, device: str, obj: EbsVolume):
        return cls(
            device,
            obj.as_dict
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AWSEbsDiskTypes(object):
    ebs_type_list = [
        {
            "type": "standard",
            "iops": None,
            "max": None
        },
        {
            "type": "io1",
            "iops": 3000,
            "max": 64000
        },
        {
            "type": "io2",
            "iops": 3000,
            "max": 64000
        },
        {
            "type": "gp2",
            "iops": None,
            "max": None
        },
        {
            "type": "sc1",
            "iops": None,
            "max": None
        },
        {
            "type": "st1",
            "iops": None,
            "max": None
        },
        {
            "type": "gp3",
            "iops": 3000,
            "max": 16000
        }
    ]


@attr.s
class AWSImageOwners(object):
    image_owner_list = [
        {
            "owner_id": "099720109477",
            "description": "Ubuntu Linux",
            "user": "ubuntu"
        },
        {
            "owner_id": "125523088429",
            "description": "CentOS Linux",
            "user": "centos"
        },
        {
            "owner_id": "309956199498",
            "description": "RedHat Linux",
            "user": "ec2-user"
        },
        {
            "owner_id": "013907871322",
            "description": "Suse Linux",
            "user": "ec2-user"
        },
        {
            "owner_id": "379101102735",
            "description": "Debian 9 and earlier",
            "user": "admin"
        },
        {
            "owner_id": "136693071363",
            "description": "Debian 10 and later",
            "user": "admin"
        },
        {
            "owner_id": "131827586825",
            "description": "Oracle Linux",
            "user": "ec2-user"
        },
        {
            "owner_id": "125523088429",
            "description": "Fedora CoreOS Linux",
            "user": "core"
        },
        {
            "owner_id": "137112412989",
            "description": "Amazon Linux",
            "user": "ec2-user"
        },
        {
            "owner_id": "647457786197",
            "description": "Arch Linux",
            "user": "arch"
        },
        {
            "owner_id": "792107900819",
            "description": "Rocky Linux",
            "user": "rocky"
        },
    ]


@attr.s
class ComputeTypes(object):
    general_purpose = ['m5', 'm5a', 'm7g']
    compute_optimized = ['c5', 'c5a', 'c7g']
    memory_optimized = ['r5', 'r5a', 'r7g']

    def as_list(self) -> list:
        flat_list = []
        for element in [self.general_purpose, self.compute_optimized, self.memory_optimized]:
            flat_list.extend(element)
        return flat_list


@attr.s
class ArchitectureTypes(object):
    list = ['x86_64', 'arm64']
