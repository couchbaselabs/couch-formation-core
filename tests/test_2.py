#!/usr/bin/env python3

import os
import sys
import logging
import warnings
import requests
import base64
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


pre_provision_cmds = [
    'curl -sfL https://raw.githubusercontent.com/mminichino/host-prep-lib/main/bin/setup.sh | sudo -E bash -s - -s -g https://github.com/mminichino/host-prep-lib',
]

provision_cmds = [
    'sudo bundlemgr -b CBS',
    'sudo swmgr cluster create -n testdb -s {{ SERVICES }} -g {{ NODE_ZONE }} -l {{ PRIVATE_IP_LIST }}',
]
post_provision_cmds = [
    'sudo swmgr cluster rebalance -l {{ PRIVATE_IP_LIST }}',
]


def test_1():
    args = ["--type", "cbs", "--cloud", "gcp", "--project", "pytest-gcp", "--name", "test-cluster",
            "--region", "us-central1", "--quantity", "3", "--os_id", "ubuntu", "--os_version", "22.04",
            "--ssh_key", "/Users/michael/.ssh/mminichino-default-key-pair.pem", "--machine_type", "4x16"]
    project = Project(args)
    project.create()
    project.save()


def test_2():
    args = ["--type", "cbs", "--cloud", "gcp", "--project", "pytest-gcp", "--name", "test-cluster",
            "--region", "us-central1", "--quantity", "2", "--os_id", "ubuntu", "--os_version", "22.04",
            "--ssh_key", "/Users/michael/.ssh/mminichino-default-key-pair.pem", "--machine_type", "4x16", "--services", "analytics"]
    project = Project(args)
    project.add()
    project.save()


def test_3():
    args = ["--type", "cbs", "--project", "pytest-gcp", "--name", "test-cluster"]
    project = Project(args)
    project.deploy()
    project.provision(pre_provision_cmds, provision_cmds, post_provision_cmds)


def test_4():
    args = ["--type", "cbs", "--project", "pytest-gcp", "--name", "test-cluster"]
    username = "Administrator"
    password = "password"
    project = Project(args)
    nodes = project.list()
    connect_ip = nodes.provision_list()[0]

    session = requests.Session()
    retries = Retry(total=60,
                    backoff_factor=0.1,
                    status_forcelist=[500, 501, 503])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))

    response = requests.get(f"http://{connect_ip}:8091/pools/default", verify=False, timeout=15, auth=BasicAuth(username, password))

    assert response.status_code == 200


def test_5():
    args = ["--type", "cbs", "--project", "pytest-gcp", "--name", "test-cluster"]
    project = Project(args)
    project.destroy()
