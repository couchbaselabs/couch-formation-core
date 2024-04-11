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
from couchformation.azure.driver.base import CloudBase
from couchformation.azure.driver.network import Network, Subnet, SecurityGroup
from couchformation.azure.driver.instance import Instance
from couchformation.azure.driver.machine import MachineType
from couchformation.azure.driver.disk import Disk
from couchformation.azure.driver.image import Image
from couchformation.ssh import SSHUtil
from tests.common import ssh_key_path


@pytest.mark.serial
class TestMainAzure(unittest.TestCase):

    def setUp(self):
        warnings.filterwarnings("ignore")
        self.parameters = {
              "debug": 0,
              "verbose": 0,
              "command": "create",
              "build": "cbs",
              "cloud": "azure",
              "project": "pytest-azure",
              "name": "test-cluster",
              "connect": None,
              "group": 1,
              "provisioner": "remote",
              "region": "eastus",
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

        rg_name = f"{self.project}-rg"
        vpc_name = f"{self.project}-vpc"
        nsg_name = f"{self.project}-nsg"
        subnet_name = f"{self.project}-subnet-01"
        node_name = f"{self.project}-node-01"
        boot_disk = f"{self.project}-boot-01"
        swap_disk = f"{self.project}-swap-01"
        data_disk = f"{self.project}-data-01"
        node_pub_ip = f"{self.project}-ip-01"
        node_nic = f"{self.project}-nic-01"

        vpc_cidr = cidr_util.get_next_network()
        subnet_list = list(cidr_util.get_next_subnet())
        zone_list = base.zones()
        azure_location = base.region
        ssh_pub_key_text = SSHUtil().get_ssh_public_key(self.ssh_key)

        print(f"Network: {vpc_cidr}")
        print(f"Subnet : {subnet_list[1]}")
        print(f"Zone   : {zone_list[0]}")

        print("Creating resource group")
        azure_rg_struct = base.create_rg(rg_name, azure_location)

        if not azure_rg_struct.get('name'):
            raise Exception(f"resource group creation failed")

        print("Creating network")
        Network(self.parameters).create(vpc_name, vpc_cidr, rg_name)

        print("Creating network security group")
        nsg_resource = SecurityGroup(self.parameters).create(nsg_name, rg_name)
        SecurityGroup(self.parameters).add_rule("AllowSSH", nsg_name, ["22"], 100, rg_name)
        SecurityGroup(self.parameters).add_rule("AllowCB", nsg_name, [
            "8091-8097",
            "9123",
            "9140",
            "11210",
            "11280",
            "11207",
            "18091-18097",
            "4984-4986"
        ], 101, rg_name)

        print("Creating subnet")
        subnet_resource = Subnet(self.parameters).create(subnet_name, vpc_name, subnet_list[1], nsg_resource.id, rg_name)

        image = Image(self.parameters).list_standard(os_id=self.os_id, os_version=self.os_version)
        assert image is not None
        machine = MachineType(self.parameters).get_machine(self.machine_type, azure_location)
        assert machine is not None

        machine_name = machine['name']
        machine_ram = int(machine['memory'] / 1024)

        print("Creating disks")
        swap_resource = Disk(self.parameters).create(rg_name, azure_location, zone_list[0], machine_ram, swap_disk)
        data_resource = Disk(self.parameters).create(rg_name, azure_location, zone_list[0], 256, data_disk)

        print("Creating IP and NIC")
        pub_ip_resource = Network(self.parameters).create_pub_ip(node_pub_ip, rg_name)
        nic_resource = Network(self.parameters).create_nic(node_nic, subnet_resource.id, zone_list[0], pub_ip_resource.id, rg_name)

        print("Creating instance")
        Instance(self.parameters).run(node_name,
                                      image['publisher'],
                                      image['offer'],
                                      image['sku'],
                                      zone_list[0],
                                      nic_resource.id,
                                      image['os_user'],
                                      ssh_pub_key_text,
                                      rg_name,
                                      boot_disk,
                                      machine_type=machine_name)

        print(f"Attaching disk {swap_disk}")
        Instance(self.parameters).attach_disk(node_name, base.disk_caching(machine_ram), "1", swap_resource.id, rg_name)
        print(f"Attaching disk {data_disk}")
        Instance(self.parameters).attach_disk(node_name, base.disk_caching(256), "2", data_resource.id, rg_name)

        nsg_list = SecurityGroup(self.parameters).list(rg_name)
        network_list = Network(self.parameters).list(rg_name)

        assert any(i['name'] == vpc_name for i in network_list) is True
        assert any(i['name'] == nsg_name for i in nsg_list) is True

        print("Cleanup")
        assert Instance(self.parameters).details(node_name, rg_name) is not None
        Instance(self.parameters).terminate(node_name, rg_name)

        assert Network(self.parameters).describe_nic(node_nic, rg_name) is not None
        Network(self.parameters).delete_nic(node_nic, rg_name)

        assert Network(self.parameters).describe_pub_ip(node_pub_ip, rg_name) is not None
        Network(self.parameters).delete_pub_ip(node_pub_ip, rg_name)

        assert Disk(self.parameters).details(boot_disk, rg_name) is not None
        Disk(self.parameters).delete(boot_disk, rg_name)

        assert Disk(self.parameters).details(swap_disk, rg_name) is not None
        Disk(self.parameters).delete(swap_disk, rg_name)

        assert Disk(self.parameters).details(data_disk, rg_name) is not None
        Disk(self.parameters).delete(data_disk, rg_name)

        assert Subnet(self.parameters).details(vpc_name, subnet_name, rg_name) is not None
        Subnet(self.parameters).delete(vpc_name, subnet_name, rg_name)

        assert SecurityGroup(self.parameters).details(nsg_name, rg_name) is not None
        SecurityGroup(self.parameters).delete(nsg_name, rg_name)

        assert Network(self.parameters).details(vpc_name, rg_name) is not None
        Network(self.parameters).delete(vpc_name, rg_name)

        assert base.get_rg(rg_name, base.region) is not None
        base.delete_rg(rg_name)
