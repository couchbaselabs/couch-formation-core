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
        parser.add_argument("--create", action="store_true")
        parser.add_argument("--destroy", action="store_true")
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
