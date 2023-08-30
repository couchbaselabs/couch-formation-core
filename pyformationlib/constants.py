##
##
import os

STATE_DIRECTORY = os.path.join(os.environ.get('HOME'), '.config', 'couch-formation', 'state')

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
