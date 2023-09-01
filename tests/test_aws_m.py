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

provision_cmds = [
    'curl -sfL https://raw.githubusercontent.com/mminichino/host-prep-lib/main/bin/setup.sh | sudo -E bash -s - -s -g https://github.com/mminichino/host-prep-lib'
]


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
    node.provision(provision_cmds)


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


def aws_provision_1(username, ssh_key, ip_list):
    ps = ProvisionSet()
    ps.add_cmd('uname -a')
    ps.add_cmd('id -a')
    nodes = NodeList().create(username, ssh_key)
    for ip in ip_list:
        nodes.add('node-test-cluster-1', ip, ip)
    ps.add_nodes(nodes)
    rp = RemoteProvisioner(ps)
    rp.exec()
    rp.join()


p = Params()
options, remainder = p.parameters

aws_config = AWSConfig.create(remainder)

try:
    debug_level = int(os.environ['DEBUG_LEVEL'])
except (ValueError, KeyError):
    debug_level = 3

if debug_level == 0:
    logger.setLevel(logging.DEBUG)
elif debug_level == 1:
    logger.setLevel(logging.ERROR)
elif debug_level == 2:
    logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.CRITICAL)

logging.basicConfig()

if options.create:
    aws_create_1(aws_config)

if options.destroy:
    aws_destroy_1(aws_config)

if options.list:
    aws_list_1(aws_config)

if options.provision:
    aws_provision_1()
