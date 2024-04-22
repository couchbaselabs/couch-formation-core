#!/usr/bin/env python3

import os
import sys
import unittest
import logging
import warnings
import pytest
import time

warnings.filterwarnings("ignore")
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
sys.path.append(current)

from couchformation.network import NetworkDriver
from couchformation.gcp.driver.base import CloudBase
from couchformation.gcp.driver.network import Network, Subnet
from couchformation.gcp.driver.instance import Instance
from couchformation.gcp.driver.machine import MachineType
from couchformation.gcp.driver.firewall import Firewall
from couchformation.gcp.driver.disk import Disk
from couchformation.gcp.driver.image import Image
from couchformation.ssh import SSHUtil
from tests.common import ssh_key_path


@pytest.mark.serial
class TestMainGCP(unittest.TestCase):

    def setUp(self):
        warnings.filterwarnings("ignore")
        self.parameters = {
              "debug": 0,
              "verbose": 0,
              "command": "create",
              "build": "cbs",
              "cloud": "gcp",
              "project": "pytest-gcp",
              "name": "test-cluster",
              "connect": None,
              "group": 1,
              "provisioner": "remote",
              "region": "us-central1",
              "auth_mode": None,
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
        subnet_name = f"{self.project}-subnet-01"
        firewall_default = f"{vpc_name}-fw-default"
        firewall_cbs = f"{vpc_name}-fw-cbs"
        firewall_ssh = f"{vpc_name}-fw-ssh"
        firewall_rdp = f"{vpc_name}-fw-rdp"
        node_name = f"{self.project}-node-01"
        swap_disk = f"{self.project}-swap-01"
        data_disk = f"{self.project}-data-01"

        vpc_cidr = cidr_util.get_next_network()
        subnet_list = list(cidr_util.get_next_subnet())
        zone_list = base.zones()

        print(f"Network: {vpc_cidr}")
        print(f"Subnet : {subnet_list[1]}")
        print(f"Zone   : {zone_list[0]}")

        print("Creating network")
        Network(self.parameters).create(vpc_name)
        ssh_pub_key_text = SSHUtil().get_ssh_public_key(self.ssh_key)
        print("Creating subnet")
        Subnet(self.parameters).create(subnet_name, vpc_name, subnet_list[1])
        print("Creating firewall rules")
        Firewall(self.parameters).create_ingress(firewall_default, vpc_name, vpc_cidr, "all")
        Firewall(self.parameters).create_ingress(firewall_cbs, vpc_name, "0.0.0.0/0", "tcp", [
                    "8091-8097",
                    "9123",
                    "9140",
                    "11210",
                    "11280",
                    "11207",
                    "18091-18097",
                    "4984-4986"
                  ])
        Firewall(self.parameters).create_ingress(firewall_ssh, vpc_name, "0.0.0.0/0", "tcp", ["22"])
        Firewall(self.parameters).create_ingress(firewall_rdp, vpc_name, "0.0.0.0/0", "tcp", ["3389"])

        image = Image(self.parameters).list_standard(os_id=self.os_id, os_version=self.os_version)
        assert image is not None
        machine = MachineType(self.parameters).get_machine(self.machine_type, zone_list[0])
        assert machine is not None

        machine_name = machine['name']
        machine_ram = str(machine['memory'] / 1024)

        print("Creating disks")
        Disk(self.parameters).create(swap_disk, zone_list[0], machine_ram)
        Disk(self.parameters).create(data_disk, zone_list[0], "256")
        print("Creating instance")
        instance_link = Instance(self.parameters).run(node_name,
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
        network_list = Network(self.parameters).list()
        firewall_list = Firewall(self.parameters).list()
        disk_list = Disk(self.parameters).list(zone_list[0])

        assert any(i['name'] == vpc_name for i in network_list) is True
        assert any(i['name'] == firewall_default for i in firewall_list) is True
        assert any(i['name'] == data_disk for i in disk_list) is True

        print("Cleanup")
        assert Instance(self.parameters).find(node_name) is not None
        Instance(self.parameters).terminate(node_name, zone_list[0])

        assert Disk(self.parameters).find(swap_disk) is not None
        Disk(self.parameters).delete(swap_disk, zone_list[0])

        assert Disk(self.parameters).find(data_disk) is not None
        Disk(self.parameters).delete(data_disk, zone_list[0])

        assert Firewall(self.parameters).details(firewall_rdp) is not None
        Firewall(self.parameters).delete(firewall_rdp)

        assert Firewall(self.parameters).details(firewall_ssh) is not None
        Firewall(self.parameters).delete(firewall_ssh)

        assert Firewall(self.parameters).details(firewall_cbs) is not None
        Firewall(self.parameters).delete(firewall_cbs)

        assert Firewall(self.parameters).details(firewall_default) is not None
        Firewall(self.parameters).delete(firewall_default)

        assert Subnet(self.parameters).details(subnet_name) is not None
        Subnet(self.parameters).delete(subnet_name)

        assert Network(self.parameters).details(vpc_name) is not None
        Network(self.parameters).delete(vpc_name)
