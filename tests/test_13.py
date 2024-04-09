#!/usr/bin/env python3

import os
import warnings
import pytest
import time
import requests
import base64
from requests.auth import AuthBase
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from couchformation.aws.driver.base import CloudBase
from couchformation.project import Project
from couchformation.cli.cloudmgr import CloudMgrCLI
from tests.interactive import aws_base
from tests.common import start_container, stop_container, run_in_container, copy_to_container, copy_home_env_to_container, linux_image_name, ssh_key_path

warnings.filterwarnings("ignore")
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)


class BasicAuth(AuthBase):

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def __call__(self, r):
        auth_hash = f"{self.username}:{self.password}"
        auth_bytes = auth_hash.encode('ascii')
        auth_encoded = base64.b64encode(auth_bytes)
        request_headers = {
            "Authorization": f"Basic {auth_encoded.decode('ascii')}",
        }
        r.headers.update(request_headers)
        return r


@pytest.mark.serial
class TestInstallAWS(object):
    container_id = None
    aws_auth = {}
    container_name = 'pytest'

    @classmethod
    def setup_class(cls):
        print("Starting Linux container")
        platform = f"linux/{os.uname().machine}"
        script = os.path.join(parent, 'tests', 'install_pkg.sh')
        cls.aws_auth = CloudBase(aws_base).get_auth_config()
        cls.container_id = start_container(linux_image_name, cls.container_name, platform=platform)
        copy_home_env_to_container(cls.container_id, '/root')
        copy_to_container(cls.container_id, script, '/root')
        command = ['/bin/bash', '/root/install_pkg.sh']
        run_in_container(cls.container_id, command)
        time.sleep(1)

    @classmethod
    def teardown_class(cls):
        print("Stopping test container")
        stop_container(cls.container_name)
        time.sleep(1)

    def test_1(self):
        command = ["cloudmgr", "create", "--build", "cbs", "--cloud", "aws", "--project", "pytest-aws", "--name", "test-cluster", "--auth_mode", "sso",
                   "--region", "us-east-2", "--quantity", "3", "--os_id", "ubuntu", "--os_version", "22.04",
                   "--ssh_key", ssh_key_path, "--machine_type", "4x16"]
        run_in_container(self.container_id, command, environment=self.aws_auth)

    def test_2(self):
        command = ["cloudmgr", "deploy", "--project", "pytest-aws"]
        run_in_container(self.container_id, command, environment=self.aws_auth)

    def test_3(self):
        args = ["list", "--project", "pytest-aws"]
        username = "Administrator"
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        nodes = list(project.list(api=True))
        connect_ip = nodes[0].get('public_ip')
        password = project.credential()

        time.sleep(1)
        session = requests.Session()
        retries = Retry(total=10,
                        backoff_factor=0.01,
                        status_forcelist=[500, 501, 503])
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))

        response = requests.get(f"http://{connect_ip}:8091/pools/default", verify=False, timeout=15, auth=BasicAuth(username, password))

        assert response.status_code == 200

    def test_4(self):
        command = ["cloudmgr", "destroy", "--project", "pytest-aws"]
        run_in_container(self.container_id, command, environment=self.aws_auth)
