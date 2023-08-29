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
