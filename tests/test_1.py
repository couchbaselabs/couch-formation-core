#!/usr/bin/env python3

import os
import sys
import logging
import warnings
import unittest
import pytest
import time

warnings.filterwarnings("ignore")
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
from tests.common import ssh_key_path


@pytest.mark.serial
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
              "ssh_key": ssh_key_path,
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
        time.sleep(1)
        loggers = [logging.getLogger()] + list(logging.Logger.manager.loggerDict.values())
        for logger in loggers:
            handlers = getattr(logger, 'handlers', [])
            for handler in handlers:
                logger.removeHandler(handler)

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
        assert Instance(self.parameters).details(instance_id) is not None
        Instance(self.parameters).terminate(instance_id)

        assert RouteTable(self.parameters).details(rt_id) is not None
        RouteTable(self.parameters).delete(rt_id)

        assert InternetGateway(self.parameters).details(ig_id) is not None
        InternetGateway(self.parameters).delete(ig_id)

        assert SecurityGroup(self.parameters).details(sg_id) is not None
        SecurityGroup(self.parameters).delete(sg_id)

        assert Subnet(self.parameters).details(subnet_id) is not None
        Subnet(self.parameters).delete(subnet_id)

        assert Network(self.parameters).details(vpc_id) is not None
        Network(self.parameters).delete(vpc_id)

        assert SSHKey(self.parameters).details(ssh_key_name) is not None
        SSHKey(self.parameters).delete(ssh_key_name)
