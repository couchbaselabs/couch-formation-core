#!/usr/bin/env python3

import os
import sys
import logging
import warnings
import unittest

warnings.filterwarnings("ignore")
logger = logging.getLogger()
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
sys.path.append(current)

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


class TestMainAWS(unittest.TestCase):

    def setUp(self):
        warnings.filterwarnings("ignore")
        self.parameters = {
              "debug": 0,
              "verbose": 0,
              "command": "create",
              "build": "cbs",
              "cloud": "aws",
              "project": "pytest-aws",
              "name": "test-cluster",
              "connect": None,
              "group": 1,
              "provisioner": "remote",
              "region": "us-east-2",
              "auth_mode": "sso",
              "profile": None,
              "ssh_key": "/Users/michael/.ssh/mminichino-default-key-pair.pem",
              "cidr": None,
              "os_id": "ubuntu",
              "os_version": "22.04",
              "machine_type": "4x16",
              "quantity": "3",
              "services": None,
              "volume_iops": None,
              "volume_size": None
            }
        self.project = self.parameters.get('project')
        self.ssh_key = self.parameters.get('ssh_key')
        self.os_id = self.parameters.get('os_id')
        self.os_version = self.parameters.get('os_version')
        self.machine_type = self.parameters.get('machine_type')

    def tearDown(self):
        pass

    def test_1(self):
        cidr_util = NetworkDriver()
        base = CloudBase(self.parameters)

        for net in Network(self.parameters).cidr_list:
            cidr_util.add_network(net)

        vpc_name = f"{self.project}-vpc"
        ig_name = f"{self.project}-gw"
        rt_name = f"{self.project}-rt"
        sg_name = f"{self.project}-sg"
        key_name = f"{self.project}-key"
        subnet_name = f"{self.project}-subnet-01"
        node_name = f"{self.project}-node-01"

        vpc_cidr = cidr_util.get_next_network()
        subnet_list = list(cidr_util.get_next_subnet())
        zone_list = base.zones()

        print(f"Network: {vpc_cidr}")
        print(f"Subnet : {subnet_list[1]}")
        print(f"Zone   : {zone_list[0]}")

        ssh_pub_key_text = SSHUtil().get_ssh_public_key(self.ssh_key)
        vpc_id = Network(self.parameters).create(vpc_name, vpc_cidr)
        sg_id = SecurityGroup(self.parameters).create(sg_name, "TestSG", vpc_id)
        ssh_key_name = SSHKey(self.parameters).create(key_name, ssh_pub_key_text, {"Environment": "pytest"})
        subnet_id = Subnet(self.parameters).create(subnet_name, vpc_id, zone_list[0], subnet_list[1])

        ig_id = InternetGateway(self.parameters).create(ig_name, vpc_id)
        rt_id = RouteTable(self.parameters).create(rt_name, vpc_id)
        RouteTable(self.parameters).add_route("0.0.0.0/0", ig_id, rt_id)

        image = Image(self.parameters).list_standard(os_id=self.os_id, os_version=self.os_version)
        assert image is not None
        machine = MachineType(self.parameters).get_machine(self.machine_type)
        assert machine is not None

        print("Creating instance")
        instance_id = Instance(self.parameters).run(node_name,
                                                    image['name'],
                                                    ssh_key_name,
                                                    sg_id, subnet_id,
                                                    zone_list[0],
                                                    instance_type=machine['name'])

        sg_list = SecurityGroup(self.parameters).list(vpc_id)
        new_vpc_list = Network(self.parameters).list()

        assert any(i['id'] == vpc_id for i in new_vpc_list) is True
        assert any(i['id'] == sg_id for i in sg_list) is True

        print("Removing instance")
        Instance(self.parameters).terminate(instance_id)
        RouteTable(self.parameters).delete(rt_id)
        InternetGateway(self.parameters).delete(ig_id)
        SecurityGroup(self.parameters).delete(sg_id)
        Subnet(self.parameters).delete(subnet_id)
        Network(self.parameters).delete(vpc_id)
        SSHKey(self.parameters).delete(ssh_key_name)
