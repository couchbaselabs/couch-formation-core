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
from couchformation.gcp.driver.base import CloudBase
from couchformation.gcp.driver.network import Network, Subnet
from couchformation.gcp.driver.instance import Instance
from couchformation.gcp.driver.machine import MachineType
from couchformation.gcp.driver.firewall import Firewall
from couchformation.gcp.driver.disk import Disk
from couchformation.gcp.driver.image import Image
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


def gcp_create_1(args):
    project = Project(args)
    project.create()
    project.save()


def gcp_add_1(args):
    project = Project(args)
    project.add()
    project.save()


def gcp_deploy_1(args):
    project = Project(args)
    project.deploy()
    project.provision(pre_provision_cmds, provision_cmds, post_provision_cmds)


def gcp_destroy_1(args):
    project = Project(args)
    project.destroy()


def gcp_list_1(args):
    project = Project(args)
    nodes = project.list()
    for ip in nodes.provision_list():
        print(ip)
    print(nodes.ip_csv_list())


def gcp_driver_1(args):
    warnings.filterwarnings("ignore")
    cidr_util = NetworkDriver()
    core = BaseConfig().create(args)
    base = CloudBase(core)
    config = NodeConfig().create(args)
    vpc_name = f"{core.project}-vpc"
    subnet_name = f"{core.project}-subnet-01"
    firewall_default = f"{vpc_name}-fw-default"
    firewall_cbs = f"{vpc_name}-fw-cbs"
    firewall_ssh = f"{vpc_name}-fw-ssh"
    node_name = f"{core.project}-node-01"
    swap_disk = f"{core.project}-swap-01"
    data_disk = f"{core.project}-data-01"

    for net in Network(core).cidr_list:
        cidr_util.add_network(net)

    vpc_cidr = cidr_util.get_next_network()
    subnet_list = list(cidr_util.get_next_subnet())
    zone_list = base.zones()

    print(f"Network: {vpc_cidr}")
    print(f"Subnet : {subnet_list[1]}")
    print(f"Zone   : {zone_list[0]}")

    print("Creating network")
    Network(core).create(vpc_name)
    ssh_pub_key_text = SSHUtil().get_ssh_public_key(core.ssh_key)
    print("Creating subnet")
    Subnet(core).create(subnet_name, vpc_name, subnet_list[1])
    print("Creating firewall rules")
    Firewall(core).create_ingress(firewall_default, vpc_name, vpc_cidr, "all")
    Firewall(core).create_ingress(firewall_cbs, vpc_name, "0.0.0.0/0", "tcp", [
                "8091-8097",
                "9123",
                "9140",
                "11210",
                "11280",
                "11207",
                "18091-18097",
                "4984-4986"
              ])
    Firewall(core).create_ingress(firewall_ssh, vpc_name, "0.0.0.0/0", "tcp", ["22"])

    image = Image(core).list_standard(os_id=core.os_id, os_version=core.os_version)
    assert image is not None
    machine = MachineType(core).get_machine(config.machine_type, zone_list[0])
    assert machine is not None

    machine_name = machine['name']
    machine_ram = str(machine['memory'] / 1024)

    print("Creating disks")
    Disk(core).create(swap_disk, zone_list[0], machine_ram)
    Disk(core).create(data_disk, zone_list[0], "256")
    print("Creating instance")
    instance_link = Instance(core).run(node_name,
                                       image['image_project'],
                                       image['name'],
                                       base.service_account_email,
                                       zone_list[0],
                                       vpc_name,
                                       subnet_name,
                                       image['os_user'],
                                       ssh_pub_key_text,
                                       swap_disk,
                                       data_disk,
                                       machine_type=machine_name)

    print(f"Created {instance_link}")
    network_list = Network(core).list()
    firewall_list = Firewall(core).list()
    disk_list = Disk(core).list(zone_list[0])

    assert any(i['name'] == vpc_name for i in network_list) is True
    assert any(i['name'] == firewall_default for i in firewall_list) is True
    assert any(i['name'] == data_disk for i in disk_list) is True

    print("Cleanup")
    Instance(core).terminate(node_name, zone_list[0])
    Disk(core).delete(swap_disk, zone_list[0])
    Disk(core).delete(data_disk, zone_list[0])
    Firewall(core).delete(firewall_ssh)
    Firewall(core).delete(firewall_cbs)
    Firewall(core).delete(firewall_default)
    Subnet(core).delete(subnet_name)
    Network(core).delete(vpc_name)


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
    gcp_create_1(remainder)

if options.add:
    gcp_add_1(remainder)

if options.deploy:
    gcp_deploy_1(remainder)

if options.destroy:
    gcp_destroy_1(remainder)

if options.list:
    gcp_list_1(remainder)

if options.driver:
    remainder = ["--type", "cbs", "--cloud", "gcp", "--project", "pytest-manual", "--name", "test-cluster",
                 "--region", "us-central1", "--quantity", "3", "--os_id", "ubuntu", "--os_version", "22.04",
                 "--ssh_key", "/Users/michael/.ssh/mminichino-default-key-pair.pem", "--machine_type", "4x16"]
    gcp_driver_1(remainder)
