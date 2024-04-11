#!/usr/bin/env python3

import os
import sys
import argparse
import logging
import warnings

warnings.filterwarnings("ignore")
logger = logging.getLogger()
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
sys.path.append(current)

from couchformation.project import Project
from couchformation.network import NetworkDriver
from couchformation.azure.driver.base import CloudBase
from couchformation.azure.driver.network import Network, Subnet, SecurityGroup
from couchformation.azure.driver.instance import Instance
from couchformation.azure.driver.machine import MachineType
from couchformation.azure.driver.disk import Disk
from couchformation.azure.driver.image import Image
from couchformation.ssh import SSHUtil
from couchformation.config import BaseConfig, NodeConfig


pre_provision_cmds = [
    'curl -sfL https://raw.githubusercontent.com/mminichino/host-prep-lib/main/bin/setup.sh | sudo -E bash -s - -s -g https://github.com/mminichino/host-prep-lib',
]

provision_cmds = [
    'sudo bundlemgr -b CBS',
    'sudo swmgr cluster create -n testdb -s {{ SERVICES }} -g {{ NODE_ZONE }} -l {{ PRIVATE_IP_LIST }}',
]
post_provision_cmds = [
    'sudo swmgr cluster rebalance -l {{ PRIVATE_IP_LIST }}',
]


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    green = "\x1b[32;20m"
    reset = "\x1b[0m"
    format_level = "%(levelname)s"
    format_name = "%(name)s"
    format_message = "%(message)s"
    format_line = "(%(filename)s:%(lineno)d)"
    format_extra = " [%(name)s](%(filename)s:%(lineno)d)"
    FORMATS = {
        logging.DEBUG: f"{grey}{format_level}{reset} - {format_message}",
        logging.INFO: f"{green}{format_level}{reset} - {format_message}",
        logging.WARNING: f"{yellow}{format_level}{reset} - {format_message}",
        logging.ERROR: f"{red}{format_level}{reset} - {format_message}",
        logging.CRITICAL: f"{red}{format_level}{reset} - {format_message}"
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        if logging.DEBUG >= logging.root.level:
            log_fmt += self.format_extra
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class Params(object):

    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--add", action="store_true")
        parser.add_argument("--create", action="store_true")
        parser.add_argument("--deploy", action="store_true")
        parser.add_argument("--destroy", action="store_true")
        parser.add_argument("--list", action="store_true")
        parser.add_argument("--driver", action="store_true")
        self.options, self.remainder = parser.parse_known_args()

    @property
    def parameters(self):
        return self.options, self.remainder


def azure_create_1(args):
    project = Project(args)
    project.create()
    project.save()


def azure_add_1(args):
    project = Project(args)
    project.add()
    project.save()


def azure_deploy_1(args):
    project = Project(args)
    project.deploy()
    project.provision(pre_provision_cmds, provision_cmds, post_provision_cmds)


def azure_destroy_1(args):
    project = Project(args)
    project.destroy()


def azure_list_1(args):
    project = Project(args)
    nodes = project.list()
    for ip in nodes.provision_list():
        print(ip)
    print(nodes.ip_csv_list())


def azure_driver_1(args):
    warnings.filterwarnings("ignore")
    cidr_util = NetworkDriver()
    core = BaseConfig().create(args)
    base = CloudBase(core)
    config = NodeConfig().create(args)
    rg_name = f"{core.project}-rg"
    vpc_name = f"{core.project}-vpc"
    nsg_name = f"{core.project}-nsg"
    subnet_name = f"{core.project}-subnet-01"
    node_name = f"{core.project}-node-01"
    boot_disk = f"{core.project}-boot-01"
    swap_disk = f"{core.project}-swap-01"
    data_disk = f"{core.project}-data-01"
    node_pub_ip = f"{core.project}-ip-01"
    node_nic = f"{core.project}-nic-01"

    for net in Network(core).cidr_list:
        cidr_util.add_network(net)

    vpc_cidr = cidr_util.get_next_network()
    subnet_list = list(cidr_util.get_next_subnet())
    zone_list = base.zones()
    azure_location = base.region

    ssh_pub_key_text = SSHUtil().get_ssh_public_key(core.ssh_key)

    print(f"Network: {vpc_cidr}")
    print(f"Subnet : {subnet_list[1]}")
    print(f"Zone   : {zone_list[0]}")

    print("Creating resource group")
    azure_rg_struct = base.create_rg(rg_name, azure_location)

    if not azure_rg_struct.get('name'):
        raise Exception(f"resource group creation failed")

    print("Creating network")
    Network(core).create(vpc_name, vpc_cidr, rg_name)

    print("Creating network security group")
    nsg_resource = SecurityGroup(core).create(nsg_name, rg_name)
    SecurityGroup(core).add_rule("AllowSSH", nsg_name, ["22"], 100, rg_name)
    SecurityGroup(core).add_rule("AllowCB", nsg_name, [
        "8091-8097",
        "9123",
        "9140",
        "11210",
        "11280",
        "11207",
        "18091-18097",
        "4984-4986"
    ], 101, rg_name)

    print("Creating subnet")
    subnet_resource = Subnet(core).create(subnet_name, vpc_name, subnet_list[1], nsg_resource.id, rg_name)

    image = Image(core).list_standard(os_id=core.os_id, os_version=core.os_version)
    assert image is not None
    machine = MachineType(core).get_machine(config.machine_type, azure_location)
    assert machine is not None

    machine_name = machine['name']
    machine_ram = int(machine['memory'] / 1024)

    print("Creating disks")
    swap_resource = Disk(core).create(rg_name, azure_location, zone_list[0], machine_ram, swap_disk)
    data_resource = Disk(core).create(rg_name, azure_location, zone_list[0], 256, data_disk)

    print("Creating IP and NIC")
    pub_ip_resource = Network(core).create_pub_ip(node_pub_ip, rg_name)
    nic_resource = Network(core).create_nic(node_nic, subnet_resource.id, zone_list[0], pub_ip_resource.id, rg_name)

    print("Creating instance")
    Instance(core).run(node_name,
                       image['publisher'],
                       image['offer'],
                       image['sku'],
                       zone_list[0],
                       nic_resource.id,
                       image['os_user'],
                       ssh_pub_key_text,
                       rg_name,
                       boot_disk,
                       base.disk_caching(machine_ram),
                       swap_resource.id,
                       base.disk_caching(256),
                       data_resource.id,
                       machine_type=machine_name)

    nsg_list = SecurityGroup(core).list(rg_name)
    network_list = Network(core).list(rg_name)

    assert any(i['name'] == vpc_name for i in network_list) is True
    assert any(i['name'] == nsg_name for i in nsg_list) is True

    print("Cleanup")
    Instance(core).terminate(node_name, rg_name)
    Network(core).delete_nic(node_nic, rg_name)
    Network(core).delete_pub_ip(node_pub_ip, rg_name)
    Disk(core).delete(boot_disk, rg_name)
    Disk(core).delete(swap_disk, rg_name)
    Disk(core).delete(data_disk, rg_name)
    Subnet(core).delete(vpc_name, subnet_name, rg_name)
    SecurityGroup(core).delete(nsg_name, rg_name)
    Network(core).delete(vpc_name, rg_name)
    base.delete_rg(rg_name)


p = Params()
options, remainder = p.parameters

try:
    debug_level = int(os.environ['DEBUG_LEVEL'])
except (ValueError, KeyError):
    debug_level = 2

if debug_level == 0:
    logger.setLevel(logging.DEBUG)
elif debug_level == 1:
    logger.setLevel(logging.ERROR)
elif debug_level == 2:
    logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.CRITICAL)

screen_handler = logging.StreamHandler()
screen_handler.setFormatter(CustomFormatter())
logger.addHandler(screen_handler)

if options.create:
    azure_create_1(remainder)

if options.add:
    azure_add_1(remainder)

if options.deploy:
    azure_deploy_1(remainder)

if options.destroy:
    azure_destroy_1(remainder)

if options.list:
    azure_list_1(remainder)

if options.driver:
    remainder = ["--type", "cbs", "--cloud", "azure", "--project", "pytest-manual", "--name", "test-cluster",
                 "--region", "eastus", "--quantity", "3", "--os_id", "ubuntu", "--os_version", "22.04",
                 "--ssh_key", "/Users/michael/.ssh/mminichino-default-key-pair.pem", "--machine_type", "4x16"]
    azure_driver_1(remainder)
