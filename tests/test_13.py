#!/usr/bin/env python3

import os
import warnings
import pytest
import time
import requests
import base64
import logging
import json
from requests.auth import AuthBase
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from couchformation.aws.driver.base import CloudBase
from tests.interactive import aws_base
from tests.common import start_container, stop_container, run_in_container, copy_home_env_to_container, ssh_key_relative_path, get_cmd_output

warnings.filterwarnings("ignore")
logger = logging.getLogger('couchformation.aws.driver.base')
logger.addHandler(logging.NullHandler())
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
    environment = {}
    container_name = 'pytest'
    ssh_key_path = os.path.join('/home/ubuntu', ssh_key_relative_path)

    @classmethod
    def setup_class(cls):
        logger.info("Starting Linux container")
        platform = f"linux/{os.uname().machine}"
        cls.environment = CloudBase(aws_base).get_auth_config()
        cls.container_id = start_container('cftest', cls.container_name, platform=platform)
        copy_home_env_to_container(cls.container_id,'/home/ubuntu', uid=1000, gid=1000)
        command = ['pip3', 'install', '--user', 'git+https://github.com/mminichino/couch-formation-core']
        result = run_in_container(cls.container_id, command)
        assert result is True
        time.sleep(1)

    @classmethod
    def teardown_class(cls):
        logger.info("Stopping test container")
        stop_container(cls.container_name)
        time.sleep(1)

    def test_1(self):
        command = ["cloudmgr", "create", "--build", "cbs", "--cloud", "aws", "--project", "pytest-aws", "--name", "test-cluster",
                   "--region", "us-east-2", "--quantity", "3", "--os_id", "ubuntu", "--os_version", "22.04",
                   "--ssh_key", self.ssh_key_path, "--machine_type", "4x16"]
        result = run_in_container(self.container_id, command, environment=self.environment)
        assert result is True

    def test_2(self):
        command = ["cloudmgr", "deploy", "--project", "pytest-aws"]
        result = run_in_container(self.container_id, command, environment=self.environment)
        assert result is True

    def test_3(self):
        command = ["cloudmgr", "list", "--project", "pytest-aws", "--json"]
        exit_code, output = get_cmd_output(self.container_id, command, environment=self.environment)
        assert exit_code == 0
        nodes = json.loads(output)
        username = "Administrator"
        connect_ip = nodes[0].get('public_ip')
        password = nodes[0].get('project_password')

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
        result = run_in_container(self.container_id, command, environment=self.environment)
        assert result is True
