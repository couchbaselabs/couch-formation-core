#!/usr/bin/env python3

import os
import warnings
import pytest
import time
from tests.common import start_container, stop_container, run_in_container, copy_to_container, copy_home_env_to_container, linux_image_name, ssh_key_path

warnings.filterwarnings("ignore")
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)


@pytest.mark.serial
class TestInstallLinux(object):
    container_id = None

    @classmethod
    def setup_class(cls):
        print("Starting Linux container")
        platform = f"linux/{os.uname().machine}"
        script = os.path.join(parent, 'tests', 'install_pkg.sh')
        cls.container_id = start_container(linux_image_name, platform)
        copy_home_env_to_container(cls.container_id, '/root')
        copy_to_container(cls.container_id, script, '/root')
        command = ['/bin/bash', '/root/install_pkg.sh']
        run_in_container(cls.container_id, command)
        time.sleep(1)

    @classmethod
    def teardown_class(cls):
        print("Stopping test container")
        stop_container(cls.container_id)
        time.sleep(1)

    def test_1(self):
        command = ["cloudmgr", "create", "--build", "cbs", "--cloud", "gcp", "--project", "pytest-gcp", "--name", "test-cluster",
                   "--region", "us-central1", "--quantity", "3", "--os_id", "ubuntu", "--os_version", "22.04",
                   "--ssh_key", ssh_key_path, "--machine_type", "4x16"]
        run_in_container(self.container_id, command)

    def test_2(self):
        command = ["cloudmgr", "deploy", "--project", "pytest-gcp"]
        run_in_container(self.container_id, command)
