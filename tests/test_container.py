#!/usr/bin/env python3

import sys
import os
import warnings

warnings.filterwarnings("ignore")
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
sys.path.append(current)

from couchformation.aws.driver.base import CloudBase
from tests.interactive import aws_base
from tests.common import start_container, copy_home_env_to_container


def setup_class():
    print("Starting Linux container")
    container_name = 'pytest'
    platform = f"linux/{os.uname().machine}"
    environment = CloudBase(aws_base).get_auth_config()
    container_id = start_container('cftest', container_name, platform=platform)
    copy_home_env_to_container(container_id, '/home/ubuntu', uid=1000, gid=1000)


if __name__ == '__main__':
    setup_class()
