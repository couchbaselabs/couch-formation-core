#!/usr/bin/env python3

import os
import sys
import logging
import warnings
import unittest

warnings.filterwarnings("ignore")
logger = logging.getLogger()
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
sys.path.append(current)

from couchformation.project import Project
from couchformation.cli.cloudmgr import CloudMgrCLI


class TestMainCapella(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_1(self):
        args = ["create", "--build", "capella", "--cloud", "capella", "--project", "pytest-project", "--name", "test-cluster",
                "--region", "us-east-2", "--quantity", "3", "--provider", "aws", "--machine_type", "4x16"]
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        project.create()

    def test_2(self):
        args = ["add", "--build", "capella", "--cloud", "capella", "--project", "pytest-project", "--name", "test-cluster",
                "--region", "us-east-2", "--quantity", "2", "--provider", "aws", "--machine_type", "4x16", "--services", "analytics"]
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        project.add()

    def test_3(self):
        args = ["deploy", "--project", "pytest-project"]
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        project.deploy()

    def test_4(self):
        args = ["destroy", "--project", "pytest-project"]
        cm = CloudMgrCLI(args)
        project = Project(cm.options, cm.remainder)
        project.destroy()
