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


class Params(object):

    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--create", action="store_true")
        parser.add_argument("--destroy", action="store_true")
        parser.add_argument("--list", action="store_true")
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


def aws_destroy_1(config: AWSConfig):
    net = AWSNetwork(config)
    node = AWSNode(config)
    node.destroy()
    net.destroy()


def aws_list_1(config: AWSConfig):
    node = AWSNode(config)
    node.list()


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
