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


class Params(object):

    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--cloud", action="store", help="Cloud", default="aws")
        parser.add_argument("--network", action="store_true")
        parser.add_argument("--nodes", action="store_true")
        parser.add_argument("--create", action="store_true")
        parser.add_argument("--destroy", action="store_true")
        parser.add_argument("--list", action="store_true")
        self.args = parser.parse_args()

    @property
    def parameters(self):
        return self.args


def aws_network_create_1():
    from pyformationlib.aws.network import AWSNetwork, AWSNetworkConfig, AuthMode

    config = AWSNetworkConfig().create(
        'pytest_m',
        'us-east-2',
        AuthMode.sso
    )

    net = AWSNetwork(config)

    net.create()


def aws_network_destroy_1():
    from pyformationlib.aws.network import AWSNetwork, AWSNetworkConfig, AuthMode

    config = AWSNetworkConfig().create(
        'pytest_m',
        'us-east-2',
        AuthMode.sso
    )

    net = AWSNetwork(config)

    net.destroy()


def aws_node_create_1():
    from pyformationlib.aws.node import AWSNode, AWSNodeConfig, AuthMode

    config = AWSNodeConfig().create(
        'pytest_m',
        'test-cluster',
        3,
        'us-east-2',
        'ubuntu',
        '22.04',
        '/Users/michael/.ssh/mminichino-default-key-pair.pem',
        '4x16',
        '250',
        auth_mode=AuthMode.sso
    )

    node = AWSNode(config)

    node.create()


def aws_node_destroy_1():
    from pyformationlib.aws.node import AWSNode, AWSNodeConfig, AuthMode

    config = AWSNodeConfig().create(
        'pytest_m',
        'test-cluster',
        3,
        'us-east-2',
        'ubuntu',
        '22.04',
        '/Users/michael/.ssh/mminichino-default-key-pair.pem',
        '4x16',
        '250',
        auth_mode=AuthMode.sso
    )

    node = AWSNode(config)

    node.destroy()


def aws_node_list_1():
    from pyformationlib.aws.node import AWSNode, AWSNodeConfig, AuthMode

    config = AWSNodeConfig().create(
        'pytest_m',
        'test-cluster',
        3,
        'us-east-2',
        'ubuntu',
        '22.04',
        '/Users/michael/.ssh/mminichino-default-key-pair.pem',
        '4x16',
        '250',
        auth_mode=AuthMode.sso
    )

    node = AWSNode(config)

    node.list()


p = Params()
options = p.parameters

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

if options.network:
    if options.cloud == 'aws':
        if options.create:
            aws_network_create_1()
        elif options.destroy:
            aws_network_destroy_1()

if options.nodes:
    if options.cloud == 'aws':
        if options.create:
            aws_node_create_1()
        elif options.destroy:
            aws_node_destroy_1()
        elif options.list:
            aws_node_list_1()
