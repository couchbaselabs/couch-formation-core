##
##

import os
from couchformation import get_data_dir

ROOT_DIRECTORY = os.path.join(os.environ.get('HOME'), '.config', 'couch-formation')
STATE_DIRECTORY = os.path.join(ROOT_DIRECTORY, 'state')
LOG_DIRECTORY = os.path.join(ROOT_DIRECTORY, 'log')
DATA_DIRECTORY = get_data_dir()
NODE_PROFILES = os.path.join(DATA_DIRECTORY, "node_profiles.yaml")
TARGET_PROFILES = os.path.join(DATA_DIRECTORY, "target_profiles.yaml")
PROVISIONER_PROFILES = os.path.join(DATA_DIRECTORY, "provisioner_profiles.yaml")
PLAYBOOK_DIR = os.path.join(DATA_DIRECTORY, "playbooks")

METADATA = "metadata.db"
NETWORK = "network.db"
STATE = "state.db"

GREY_COLOR = "\x1b[38;20m"
YELLOW_COLOR = "\x1b[33;20m"
RED_COLOR = "\x1b[31;20m"
BOLD_RED_COLOR = "\x1b[31;1m"
GREEN_COLOR = "\x1b[32;20m"
SCREEN_RESET = "\x1b[0m"
FORMAT_LEVEL = "%(levelname)s"
FORMAT_NAME = "%(name)s"
FORMAT_MESSAGE = "%(message)s"
FORMAT_LINE = "(%(filename)s:%(lineno)d)"
FORMAT_EXTRA = " [%(name)s](%(filename)s:%(lineno)d)"
FORMAT_TIMESTAMP = "%(asctime)s"

OS_VERSION_LIST = {
    'amzn': ['2', '2023'],
    'rhel': ['8', '9'],
    'centos': ['8'],
    'ol': ['8', '9'],
    'rocky': ['8', '9'],
    'fedora': ['34'],
    'sles': ['12', '15'],
    'opensuse-leap': ['15'],
    'ubuntu': ['20.04', '22.04'],
    'debian': ['10', '11'],
    'arch': []
}

MACHINE_TYPES = [
        {
            "name": "2x4",
            "cpu": 2,
            "memory": 4096
        },
        {
            "name": "2x8",
            "cpu": 2,
            "memory": 8192
        },
        {
            "name": "4x8",
            "cpu": 4,
            "memory": 8192
        },
        {
            "name": "4x16",
            "cpu": 4,
            "memory": 16384
        },
        {
            "name": "8x16",
            "cpu": 8,
            "memory": 16384
        },
        {
            "name": "8x32",
            "cpu": 8,
            "memory": 32768
        },
        {
            "name": "16x32",
            "cpu": 16,
            "memory": 32768
        },
        {
            "name": "16x64",
            "cpu": 16,
            "memory": 65536
        },
        {
            "name": "32x64",
            "cpu": 32,
            "memory": 65536
        },
        {
            "name": "32x128",
            "cpu": 32,
            "memory": 131072
        },
        {
            "name": "48x192",
            "cpu": 48,
            "memory": 196608
        },
        {
            "name": "64x128",
            "cpu": 64,
            "memory": 131072
        },
        {
            "name": "64x256",
            "cpu": 64,
            "memory": 262144
        },
        {
            "name": "80x320",
            "cpu": 80,
            "memory": 327680
        },
        {
            "name": "2x16",
            "cpu": 2,
            "memory": 16384
        },
        {
            "name": "4x32",
            "cpu": 4,
            "memory": 32768
        },
        {
            "name": "8x64",
            "cpu": 8,
            "memory": 65536
        },
        {
            "name": "16x128",
            "cpu": 16,
            "memory": 131072
        },
        {
            "name": "32x256",
            "cpu": 32,
            "memory": 262144
        },
        {
            "name": "48x384",
            "cpu": 48,
            "memory": 393216
        },
        {
            "name": "64x512",
            "cpu": 64,
            "memory": 524288
        },
        {
            "name": "80x640",
            "cpu": 80,
            "memory": 655360
        },
        {
            "name": "2x2",
            "cpu": 2,
            "memory": 2048
        },
        {
            "name": "4x4",
            "cpu": 4,
            "memory": 4096
        },
        {
            "name": "8x8",
            "cpu": 8,
            "memory": 8192
        },
        {
            "name": "16x16",
            "cpu": 16,
            "memory": 16384
        },
        {
            "name": "32x32",
            "cpu": 32,
            "memory": 32768
        },
        {
            "name": "48x48",
            "cpu": 48,
            "memory": 49152
        },
        {
            "name": "64x64",
            "cpu": 64,
            "memory": 65536
        },
        {
            "name": "80x80",
            "cpu": 80,
            "memory": 81920
        }
    ]

provisioners = {
    "cbs": {
        "pre_provision": [
            'curl -sfL https://raw.githubusercontent.com/mminichino/host-prep-lib/main/bin/setup.sh | sudo -E bash -s - -s -g https://github.com/mminichino/host-prep-lib',
        ],
        "provision": [
            'sudo bundlemgr -b CBS',
            'sudo swmgr cluster create -n testdb -s {{ SERVICES }} -g {{ NODE_ZONE }} -D /cbdata -l {{ PRIVATE_IP_LIST }}',
        ],
        "post_provision": [
            'sudo swmgr cluster rebalance -l {{ PRIVATE_IP_LIST }}',
        ]
    },
    "sgw": {
        "pre_provision": [
            'curl -sfL https://raw.githubusercontent.com/mminichino/host-prep-lib/main/bin/setup.sh | sudo -E bash -s - -s -g https://github.com/mminichino/host-prep-lib',
        ],
        "provision": [
            'sudo bundlemgr -b InstallSGW',
            'sudo swmgr gateway configure -l {{ CONNECT_LIST }}',
            'sudo bundlemgr -b EnableSGW'
        ],
        "post_provision": []
    }
}
