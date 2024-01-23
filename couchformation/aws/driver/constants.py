##
##

import attr
from attr.validators import instance_of as io
from typing import Iterable
from enum import Enum

CLOUD_KEY = "aws"

aws_storage_matrix = {
    99: "3000",
    199: "5000",
    299: "6000",
    399: "8000",
    499: "9000",
    599: "10000",
    699: "12000",
    799: "13000",
    899: "14000",
    999: "16000",
    16384: "16000"
}


aws_arch_matrix = {
    'x86_64': 'zone',
    'arm64': 'zone',
    'arm64_mac': 'host'
}


class PlacementType(Enum):
    ZONE = "zone"
    HOST = "host"


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
    Iops = attr.ib(validator=io(int))

    @classmethod
    def build(cls, vol_type: str, vol_size: int, vol_iops: int):
        return cls(
            vol_type,
            vol_size,
            vol_iops
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
            "feature": None,
            "pattern": r"ubuntu/images/hvm-ssd/ubuntu-*-server-*",
            "version": r"ubuntu/images/hvm-ssd/ubuntu-.*-(.+?)-.*-server-.*"
        },
        {
            "owner_id": "125523088429",
            "description": "CentOS Linux",
            "os_id": "centos",
            "user": "centos",
            "feature": None,
            "pattern": r"CentOS Stream * * *",
            "version": r"CentOS Stream (.+?) .* .*",
        },
        {
            "owner_id": "309956199498",
            "description": "RedHat Linux",
            "os_id": "rhel",
            "user": "ec2-user",
            "feature": None,
            "pattern": r"RHEL-?.?.?_HVM-*-*-*",
            "version": r"RHEL-(.+?).[0-9].[0-9]_HVM-[0-9]*-.*-.*"
        },
        {
            "owner_id": "013907871322",
            "description": "Suse Linux",
            "os_id": "sles",
            "user": "ec2-user",
            "feature": None,
            "pattern": r"suse-sles-*-sp?-v*-hvm-ssd-*",
            "version": r"suse-sles-(.+?)-sp[0-9]-v[0-9]*-hvm-ssd-.*"
        },
        {
            "owner_id": "679593333241",
            "description": "openSUSE Leap",
            "os_id": "opensuse-leap",
            "user": "ec2-user",
            "feature": None,
            "pattern": r"openSUSE-Leap-*-?-v*-hvm-ssd-*-*",
            "version": r"openSUSE-Leap-(.+?)-[0-9]-v[0-9]*-hvm-ssd-.*-.*"
        },
        {
            "owner_id": "379101102735",
            "description": "Debian 9 and earlier",
            "os_id": "debian",
            "user": "admin",
            "feature": None,
            "pattern": r"debian-*-*-*-*",
            "version": r"debian-(.+?)-.*-[0-9]*-[0-9]*"
        },
        {
            "owner_id": "136693071363",
            "description": "Debian 10 and later",
            "os_id": "debian",
            "user": "admin",
            "feature": None,
            "pattern": r"debian-*-*-*-*",
            "version": r"debian-(.+?)-.*-[0-9]*-[0-9]*"
        },
        {
            "owner_id": "131827586825",
            "description": "Oracle Linux",
            "os_id": "ol",
            "user": "ec2-user",
            "feature": None,
            "pattern": r"OL?.?-*-HVM-*-*-*",
            "version": r"OL(.+?).[0-9]-.*-HVM-[0-9]*-[0-9]*-[0-9]*"
        },
        {
            "owner_id": "125523088429",
            "description": "Fedora CoreOS Linux",
            "os_id": "fedora",
            "user": "core",
            "feature": None,
            "pattern": r"fedora-coreos-*.*.?.?-*",
            "version": r"fedora-coreos-(.+?).[0-9]*.[0-9].[0-9]-.*"
        },
        {
            "owner_id": "137112412989",
            "description": "Amazon Linux",
            "os_id": "amzn",
            "user": "ec2-user",
            "feature": None,
            "pattern": r"*-ami-*.*.0-*",
            "version": r"[a-z]*(.+?)-ami-.*.[0-9]*.0-.*"
        },
        {
            "owner_id": "647457786197",
            "description": "Arch Linux",
            "os_id": "arch",
            "user": "arch",
            "feature": None,
            "pattern": r"arch-linux-*-hvm-*.*.*.*-*",
            "version": r"none"
        },
        {
            "owner_id": "792107900819",
            "description": "Rocky Linux",
            "os_id": "rocky",
            "user": "rocky",
            "feature": None,
            "pattern": r"Rocky-?-EC2-?.?-*.0*",
            "version": r"Rocky-(.+?)-EC2-[0-9].[0-9]-[0-9]*.0.*"
        },
        {
            "owner_id": "801119661308",
            "description": "Windows",
            "os_id": "windows",
            "user": "Administrator",
            "feature": None,
            "pattern": r"Windows_Server-*-English-Full-Base-*.*.*",
            "version": r"Windows_Server-(.+?)-English-Full-Base-[0-9]*.[0-9]*.[0-9]*"
        },
        {
            "owner_id": "801119661308",
            "description": "Windows",
            "os_id": "windows",
            "user": "Administrator",
            "feature": "vmp",
            "pattern": r"Windows_Server-*-English-Full-HyperV-*.*.*",
            "version": r"Windows_Server-(.+?)-English-Full-HyperV-[0-9]*.[0-9]*.[0-9]*"
        },
        {
            "owner_id": "634519214787",
            "description": "macOS",
            "os_id": "macos",
            "user": "ec2-user",
            "feature": None,
            "pattern": r"amzn-ec2-macos-*.*.*-*-*-arm64",
            "version": r"amzn-ec2-macos-(.+?).[0-9]*.[0-9]*-[0-9]*-[0-9]*-arm64"
        },
    ]


@attr.s
class ComputeTypes(object):
    general_purpose = ['m5', 'm5a', 'm7g', "mac2", "mac2-m2", "mac2-m2pro"]
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
