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
from couchformation.aws.driver.base import CloudBase
from couchformation.aws.driver.network import Network, Subnet
from couchformation.aws.driver.gateway import InternetGateway
from couchformation.aws.driver.instance import Instance
from couchformation.aws.driver.machine import MachineType
from couchformation.aws.driver.nsg import SecurityGroup
from couchformation.aws.driver.route import RouteTable
from couchformation.aws.driver.sshkey import SSHKey
from couchformation.aws.driver.image import Image
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


def aws_create_1(args):
    project = Project(args)
    project.create()
    project.save()


def aws_add_1(args):
    project = Project(args)
    project.add()
    project.save()


def aws_deploy_1(args):
    project = Project(args)
    project.deploy()
    project.provision(pre_provision_cmds, provision_cmds, post_provision_cmds)


def aws_destroy_1(args):
    project = Project(args)
    project.destroy()


def aws_list_1(args):
    project = Project(args)
    nodes = project.list()
    for ip in nodes.provision_list():
        print(ip)
    print(nodes.ip_csv_list())


def aws_driver_1(args):
    warnings.filterwarnings("ignore")
    cidr_util = NetworkDriver()
    core = BaseConfig().create(args)
    base = CloudBase(core)
    config = NodeConfig().create(args)

    for net in Network(core).cidr_list:
        cidr_util.add_network(net)

    vpc_cidr = cidr_util.get_next_network()
    subnet_list = list(cidr_util.get_next_subnet())
    zone_list = base.zones()

    print(f"Network: {vpc_cidr}")
    print(f"Subnet : {subnet_list[1]}")
    print(f"Zone   : {zone_list[0]}")

    ssh_pub_key_text = SSHUtil().get_ssh_public_key(core.ssh_key)
    vpc_id = Network(core).create("pytest-vpc", vpc_cidr)
    sg_id = SecurityGroup(core).create("pytest-sg", "TestSG", vpc_id)
    ssh_key_name = SSHKey(core).create("pytest-key", ssh_pub_key_text, {"Environment": "pytest"})
    subnet_id = Subnet(core).create("pytest-subnet-01", vpc_id, zone_list[0], subnet_list[1])

    ig_id = InternetGateway(core).create("pytest-vpc-ig", vpc_id)
    rt_id = RouteTable(core).create("pytest-vpc-rt", vpc_id)
    RouteTable(core).add_route("0.0.0.0/0", ig_id, rt_id)

    image = Image(core).list_standard(os_id=core.os_id, os_version=core.os_version)
    assert image is not None
    machine = MachineType(core).get_machine(config.machine_type)
    assert machine is not None

    print("Creating instance")
    instance_id = Instance(core).run("pytest-instance", image['name'], ssh_key_name, sg_id, subnet_id, instance_type=machine['name'])

    sg_list = SecurityGroup(core).list(vpc_id)
    new_vpc_list = Network(core).list()

    assert any(i['id'] == vpc_id for i in new_vpc_list) is True
    assert any(i['id'] == sg_id for i in sg_list) is True

    print("Removing instance")
    Instance(core).terminate(instance_id)
    RouteTable(core).delete(rt_id)
    InternetGateway(core).delete(ig_id)
    SecurityGroup(core).delete(sg_id)
    Subnet(core).delete(subnet_id)
    Network(core).delete(vpc_id)
    SSHKey(core).delete(ssh_key_name)


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
    aws_create_1(remainder)

if options.add:
    aws_add_1(remainder)

if options.deploy:
    aws_deploy_1(remainder)

if options.destroy:
    aws_destroy_1(remainder)

if options.list:
    aws_list_1(remainder)

if options.driver:
    aws_driver_1(remainder)
