import os
from pkg_resources import parse_version

_ROOT = os.path.abspath(os.path.dirname(__file__))
__version__ = "0.1.2"
VERSION = parse_version(__version__)
