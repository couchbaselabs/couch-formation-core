##
##

import attr
import os

CLOUD_KEY = "azure"


def get_auth_directory():
    return os.path.join(os.environ['HOME'], '.azure')


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
            "disk_size": "64",
            "disk_tier": "P50",
            "disk_iops": "16000"
        },
        {
            "disk_size": "128",
            "disk_tier": "P50",
            "disk_iops": "16000"
        },
        {
            "disk_size": "256",
            "disk_tier": "P50",
            "disk_iops": "16000"
        },
        {
            "disk_size": "512",
            "disk_tier": "P50",
            "disk_iops": "16000"
        },
        {
            "disk_size": "1024",
            "disk_tier": "P50",
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
    ]


@attr.s
class ComputeTypes(object):
    size_family = set('DEFL')
    size_features = set('tlmsa')
    size_storage = set('s')
    size_versions = set('2345')
