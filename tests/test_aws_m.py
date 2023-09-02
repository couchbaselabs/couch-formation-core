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

from pyformationlib.aws.common import AWSConfig
from pyformationlib.aws.network import AWSNetwork
from pyformationlib.aws.node import AWSNode
from pyformationlib.provisioner.remote import RemoteProvisioner, ProvisionSet
from pyformationlib.config import NodeList

pre_provision_cmds = [
    'curl -sfL https://raw.githubusercontent.com/mminichino/host-prep-lib/main/bin/setup.sh | sudo -E bash -s - -s -g https://github.com/mminichino/host-prep-lib',
]

provision_cmds = [
    'sudo bundlemgr -b CBS',
    'sudo swmgr cluster create -n testdb -g {{ NODE_ZONE }} -l {{ PRIVATE_IP_LIST }}',
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
        parser.add_argument("--create", action="store_true")
        parser.add_argument("--destroy", action="store_true")
        parser.add_argument("--list", action="store_true")
        parser.add_argument("--provision", action="store_true")
        self.options, self.remainder = parser.parse_known_args()

    @property
    def parameters(self):
        return self.options, self.remainder


def aws_create_1(config: AWSConfig):
    net = AWSNetwork(config)
    node = AWSNode(config)
    print("Creating network")
    net.create()
    print("Creating nodes")
    node.create()
    print("Provisioning nodes")
    node.provision(pre_provision_cmds, provision_cmds, post_provision_cmds)


def aws_destroy_1(config: AWSConfig):
    net = AWSNetwork(config)
    node = AWSNode(config)
    node.destroy()
    net.destroy()


def aws_list_1(config: AWSConfig):
    node = AWSNode(config)
    nodes = node.list()
    for ip in nodes.provision_list():
        print(ip)
    print(nodes.ip_csv_list())


def aws_provision_1(username, ssh_key, ip_list):
    cmd = [
        'uname -a',
        'id -a'
    ]
    ps = ProvisionSet()
    ps.add_install(cmd)
    nodes = NodeList().create(username, ssh_key)
    for ip in ip_list:
        nodes.add('node-test-cluster-1', ip, ip)
    ps.add_nodes(nodes)
    rp = RemoteProvisioner(ps)
    rp.run()


p = Params()
options, remainder = p.parameters

aws_config = AWSConfig.create(remainder)

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
    aws_create_1(aws_config)

if options.destroy:
    aws_destroy_1(aws_config)

if options.list:
    aws_list_1(aws_config)

if options.provision:
    _username = os.environ['TEST_USERNAME']
    _ssh_key = os.environ['TEST_SSH_KEY']
    _ip_list = os.environ['TEST_IP_LIST'].split(',')
    aws_provision_1(_username, _ssh_key, _ip_list)
