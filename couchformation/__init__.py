import os
from pkg_resources import parse_version

_ROOT = os.path.abspath(os.path.dirname(__file__))
__version__ = "4.0.0a320"
VERSION = parse_version(__version__)


def get_data_dir():
    return os.path.join(_ROOT, 'data')
