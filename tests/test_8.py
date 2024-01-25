#!/usr/bin/env python3

import os
import sys
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
from couchformation.docker.driver.network import Network
from couchformation.docker.driver.container import Container


@pytest.mark.serial
class TestMainDocker(object):
    parameters = {}
    project = None
    image = None

    @classmethod
    def setup_class(cls):
        warnings.filterwarnings("ignore")
        cls.parameters = {
              "debug": 0,
              "verbose": 0,
              "command": "create",
              "build": "cbs",
              "cloud": "docker",
              "project": "pytest-docker",
              "name": "test-cluster",
              "connect": None,
              "group": 1,
              "provisioner": "remote",
              "region": "us-east-2",
              "auth_mode": "sso",
              "profile": None,
              "ssh_key": "/Users/michael/.ssh/mminichino-default-key-pair.pem",
              "cidr": None,
              "image": "couchbase/server",
              "quantity": "3",
              "services": None,
              "volume_iops": None,
              "volume_size": None
            }
        cls.project = cls.parameters.get('project')
        cls.image = cls.parameters.get('image')

    @classmethod
    def teardown_class(cls):
        time.sleep(1)
        loggers = [logging.getLogger()] + list(logging.Logger.manager.loggerDict.values())
        for logger in loggers:
            handlers = getattr(logger, 'handlers', [])
            for handler in handlers:
                logger.removeHandler(handler)

    def test_1(self):
        cidr_util = NetworkDriver()

        Network(self.parameters).list()

        for net in Network(self.parameters).cidr_list:
            cidr_util.add_network(net)

        net_name = f"{self.project}-net"
        cbs_node_name = f"{self.project}-node-01"
        sgw_node_name = f"{self.project}-node-02"

        cidr_util.get_next_network()
        subnet_list = list(cidr_util.get_next_subnet())

        print(f"Network: {subnet_list[1]}")

        net_id = Network(self.parameters).create(net_name, subnet_list[1])

        print("Creating CBS container")
        Container(self.parameters).run("cbs", cbs_node_name, network=net_id.name)

        print("Configuring CBS container")
        run_cmd = 'curl -sfL https://raw.githubusercontent.com/mminichino/host-prep-lib/main/bin/setup.sh | bash -s - -s -g https://github.com/mminichino/host-prep-lib'
        exit_code, output = Container(self.parameters).run_in_container(cbs_node_name, run_cmd)
        assert exit_code == 0

        run_cmd = 'swmgr cluster create -n testdb'
        exit_code, output = Container(self.parameters).run_in_container(cbs_node_name, run_cmd)
        assert exit_code == 0

        print("Creating SGW container")
        Container(self.parameters).run("sgw", sgw_node_name, network=net_id.name)

        print("Removing containers")
        Container(self.parameters).terminate(sgw_node_name)
        Container(self.parameters).terminate(cbs_node_name)

        print("Removing network")
        Network(self.parameters).delete(net_name)
