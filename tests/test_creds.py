#!/usr/bin/env python3

import os
import sys
from pathlib import Path

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
sys.path.append(current)

from common import create_cred_package


def main():
    create_cred_package(os.path.join(Path.home(), 'pytest-creds.tgz'))


if __name__ == '__main__':
    main()
