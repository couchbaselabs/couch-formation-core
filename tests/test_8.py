#!/usr/bin/env python3

import os
import sys
import logging
import warnings
import unittest
import pytest
import time
import base64
from requests.auth import AuthBase

warnings.filterwarnings("ignore")
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


@pytest.mark.cf_columnar
@pytest.mark.cf_windows
@pytest.mark.cf_posix
@pytest.mark.order(8)
class TestMainColumnar(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        time.sleep(1)
        loggers = [logging.getLogger()] + list(logging.Logger.manager.loggerDict.values())
        for logger in loggers:
            handlers = getattr(logger, 'handlers', [])
            for handler in handlers:
                logger.removeHandler(handler)

    def test_1(self):
        args = ["create", "--build", "columnar", "--cloud", "capella", "--project", "pytest-columnar", "--name", "columnardb",
                "--region", "us-east-1", "--quantity", "1", "--provider", "aws", "--machine_type", "4x32", "--profile", "pytest"]
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        project.create()

    def test_2(self):
        args = ["deploy", "--project", "pytest-columnar"]
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        project.deploy()

    def test_3(self):
        args = ["destroy", "--project", "pytest-columnar"]
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        project.destroy()
