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
            "os_id": "ubuntu",
            "user": "ubuntu",
            "pattern": r"ubuntu/images/hvm-ssd/ubuntu-.*-server-.*",
            "version": r"ubuntu/images/hvm-ssd/ubuntu-.*-(.+?)-.*-server-.*"
        },
        {
            "owner_id": "125523088429",
            "description": "CentOS Linux",
            "os_id": "centos",
            "user": "centos",
            "pattern": r"CentOS Stream .* .* .*",
            "version": r"CentOS Stream (.+?) .* .*",
        },
        {
            "owner_id": "309956199498",
            "description": "RedHat Linux",
            "os_id": "rhel",
            "user": "ec2-user",
            "pattern": r"RHEL-[0-9].[0-9].[0-9]_HVM-[0-9]*-.*-.*",
            "version": r"RHEL-(.+?).[0-9].[0-9]_HVM-[0-9]*-.*-.*"
        },
        {
            "owner_id": "013907871322",
            "description": "Suse Linux",
            "os_id": "sles",
            "user": "ec2-user",
            "pattern": r"suse-sles-[0-9]*-sp[0-9]-v[0-9]*-hvm-ssd-.*",
            "version": r"suse-sles-(.+?)-sp[0-9]-v[0-9]*-hvm-ssd-.*"
        },
        {
            "owner_id": "679593333241",
            "description": "openSUSE Leap",
            "os_id": "opensuse-leap",
            "user": "ec2-user",
            "pattern": r"openSUSE-Leap-[0-9]*-[0-9]-v[0-9]*-hvm-ssd-.*-.*",
            "version": r"openSUSE-Leap-(.+?)-[0-9]-v[0-9]*-hvm-ssd-.*-.*"
        },
        {
            "owner_id": "379101102735",
            "description": "Debian 9 and earlier",
            "os_id": "debian",
            "user": "admin",
            "pattern": r"debian-[0-9]*-.*-[0-9]*-[0-9]*",
            "version": r"debian-(.+?)-.*-[0-9]*-[0-9]*"
        },
        {
            "owner_id": "136693071363",
            "description": "Debian 10 and later",
            "os_id": "debian",
            "user": "admin",
            "pattern": r"debian-[0-9]*-.*-[0-9]*-[0-9]*",
            "version": r"debian-(.+?)-.*-[0-9]*-[0-9]*"
        },
        {
            "owner_id": "131827586825",
            "description": "Oracle Linux",
            "os_id": "ol",
            "user": "ec2-user",
            "pattern": r"OL[0-9].[0-9]-.*-HVM-[0-9]*-[0-9]*-[0-9]*",
            "version": r"OL(.+?).[0-9]-.*-HVM-[0-9]*-[0-9]*-[0-9]*"
        },
        {
            "owner_id": "125523088429",
            "description": "Fedora CoreOS Linux",
            "os_id": "fedora",
            "user": "core",
            "pattern": r"fedora-coreos-[0-9]*.[0-9]*.[0-9].[0-9]-.*",
            "version": r"fedora-coreos-(.+?).[0-9]*.[0-9].[0-9]-.*"
        },
        {
            "owner_id": "137112412989",
            "description": "Amazon Linux",
            "os_id": "amzn",
            "user": "ec2-user",
            "pattern": r"[a-z]*[0-9]-ami-.*.[0-9]*.0-.*",
            "version": r"[a-z]*(.+?)-ami-.*.[0-9]*.0-.*"
        },
        {
            "owner_id": "647457786197",
            "description": "Arch Linux",
            "os_id": "arch",
            "user": "arch",
            "pattern": r"none",
            "version": r"none"
        },
        {
            "owner_id": "792107900819",
            "description": "Rocky Linux",
            "os_id": "rocky",
            "user": "rocky",
            "pattern": r"Rocky-[0-9]-EC2-[0-9].[0-9]-[0-9]*.0.*",
            "version": r"Rocky-(.+?)-EC2-[0-9].[0-9]-[0-9]*.0.*"
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
