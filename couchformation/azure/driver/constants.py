##
##

import attr
import os
from pathlib import Path

CLOUD_KEY = "azure"


def get_auth_directory():
    return os.path.join(Path.home(), '.azure')


def get_config_default():
    return os.path.join(get_auth_directory(), 'clouds.config')


def get_config_main():
    return os.path.join(get_auth_directory(), 'config')


@attr.s
class AzureDiskTypes(object):
    disk_type_list = [
        {
            "type": 'Premium_LRS'
        },
        {
            "type": 'UltraSSD_LRS'
        }
    ]


@attr.s
class AzureDiskTiers(object):
    disk_tier_list = [
        {
            "disk_size": "4",
            "disk_tier": "P2",
            "disk_iops": "1200"
        },
        {
            "disk_size": "8",
            "disk_tier": "P3",
            "disk_iops": "2400"
        },
        {
            "disk_size": "16",
            "disk_tier": "P4",
            "disk_iops": "4800"
        },
        {
            "disk_size": "32",
            "disk_tier": "P6",
            "disk_iops": "9600"
        },
        {
            "disk_size": "64",
            "disk_tier": "P10",
            "disk_iops": "16000"
        },
        {
            "disk_size": "128",
            "disk_tier": "P15",
            "disk_iops": "16000"
        },
        {
            "disk_size": "256",
            "disk_tier": "P20",
            "disk_iops": "16000"
        },
        {
            "disk_size": "512",
            "disk_tier": "P30",
            "disk_iops": "16000"
        },
        {
            "disk_size": "1024",
            "disk_tier": "P40",
            "disk_iops": "16000"
        },
        {
            "disk_size": "2048",
            "disk_tier": "P50",
            "disk_iops": "16000"
        },
        {
            "disk_size": "4096",
            "disk_tier": "P50",
            "disk_iops": "16000"
        },
        {
            "disk_size": "8192",
            "disk_tier": "P80",
            "disk_iops": "16000"
        },
        {
            "disk_size": "16384",
            "disk_tier": "P80",
            "disk_iops": "16000"
        }
    ]


@attr.s
class AzureImagePublishers(object):
    publishers = [
        {
            "name": "Canonical",
            "offer_match": r"^0001-com-ubuntu-server-.*",
            "description": "Ubuntu Linux",
            "os_id": "ubuntu",
            "user": "ubuntu",
            "sku_match": "^(.+?)-lts-gen2$"
        },
        {
            "name": "OpenLogic",
            "offer_match": r"^CentOS$",
            "description": "CentOS Linux",
            "os_id": "centos",
            "user": "centos",
            "sku_match": r"^(.+?)_[0-9]-gen2$"
        },
        {
            "name": "RedHat",
            "offer_match": r"^RHEL$",
            "description": "RedHat Linux",
            "os_id": "rhel",
            "user": "rhel",
            "sku_match": r"^(.+?)[0-9]-gen2$"
        },
        {
            "name": "SUSE",
            "offer_match": r"^sles-(.+?)-sp[0-9]$",
            "description": "Suse Linux",
            "os_id": "sles",
            "user": "sles",
            "sku_match": "^gen2$"
        },
        {
            "name": "SUSE",
            "offer_match": r"^opensuse-leap-(.+?)-[0-9]$",
            "description": "Suse Linux",
            "os_id": "opensuse-leap",
            "user": "sles",
            "sku_match": "^gen2$"
        },
        {
            "name": "Debian",
            "offer_match": r"^debian-[0-9]*$",
            "description": "Debian 10 and later",
            "os_id": "debian",
            "user": "debian",
            "sku_match": "^(.+?)-gen2$"
        },
        {
            "name": "MicrosoftWindowsServer",
            "offer_match": r"^WindowsServer$",
            "description": "Windows Server",
            "os_id": "windows",
            "user": "adminuser",
            "sku_match": "^(.+?)-datacenter-g[2e].*$"
        },
    ]


@attr.s
class ComputeTypes(object):
    size_family = set('DEFL')
    size_features = set('tlmsa')
    vmp_features = set('tlms')
    size_storage = set('s')
    size_versions = set('2345')
    vmp_versions = set('345')


@attr.s
class StorageTierMap(object):
    size_in_gb = {
        "4": ["P2", "P3", "P4", "P6", "P10", "P15", "P20", "P30", "P40", "P50"],
        "8": ["P3", "P4", "P6", "P10", "P15", "P20", "P30", "P40", "P50"],
        "16": ["P4", "P6", "P10", "P15", "P20", "P30", "P40", "P50"],
        "32": ["P6", "P10", "P15", "P20", "P30", "P40", "P50"],
        "64": ["P10", "P15", "P20", "P30", "P40", "P50"],
        "128": ["P15", "P20", "P30", "P40", "P50"],
        "256": ["P20", "P30", "P40", "P50"],
        "512": ["P30", "P40", "P50"],
        "1024": ["P40", "P50"],
        "2048": ["P50"],
        "4096": ["P50"],
        "8192": ["P70", "P80"],
        "16384": ["P80"],
        "32768": ["P80"],
    }
