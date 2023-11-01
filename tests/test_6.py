#!/usr/bin/env python3

import os
import sys
import logging
import warnings
import requests
import base64
import unittest
from requests.auth import AuthBase
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

warnings.filterwarnings("ignore")
logger = logging.getLogger()
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
sys.path.append(current)

from couchformation.project import Project
from couchformation.cli.cloudmgr import CloudMgrCLI


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


class TestMainAzure(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_1(self):
        args = ["create", "--build", "cbs", "--cloud", "azure", "--project", "pytest-azure", "--name", "test-cluster",
                "--region", "eastus", "--quantity", "3", "--os_id", "ubuntu", "--os_version", "22.04",
                "--ssh_key", "/Users/michael/.ssh/mminichino-default-key-pair.pem", "--machine_type", "4x16"]
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        project.create()

    def test_2(self):
        args = ["add", "--build", "cbs", "--cloud", "azure", "--project", "pytest-azure", "--name", "test-cluster",
                "--region", "eastus", "--quantity", "2", "--os_id", "ubuntu", "--os_version", "22.04",
                "--ssh_key", "/Users/michael/.ssh/mminichino-default-key-pair.pem", "--machine_type", "4x16", "--services", "analytics"]
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        project.add()

    def test_3(self):
        args = ["deploy", "--project", "pytest-azure"]
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        project.deploy()

    def test_4(self):
        args = ["list", "--project", "pytest-azure"]
        username = "Administrator"
        password = "password"
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        nodes = list(project.list(api=True))
        connect_ip = nodes[0].get('public_ip')

        session = requests.Session()
        retries = Retry(total=60,
                        backoff_factor=0.1,
                        status_forcelist=[500, 501, 503])
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))

        response = requests.get(f"http://{connect_ip}:8091/pools/default", verify=False, timeout=15, auth=BasicAuth(username, password))

        assert response.status_code == 200

    def test_5(self):
        args = ["destroy", "--project", "pytest-azure"]
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        project.destroy()
