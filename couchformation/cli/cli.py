##
##

import logging
import warnings
import argparse
import sys
import os
import re
import signal
import inspect
import traceback
import datetime
import psutil
import logging.handlers
from datetime import datetime
from couchformation.config import get_log_dir
import couchformation.constants as C
from couchformation.util import FileManager
from couchformation.exception import FatalError

warnings.filterwarnings("ignore")
logger = logging.getLogger()


def break_signal_handler(signum, frame):
    signal_name = signal.Signals(signum).name
    (filename, line, function, lines, index) = inspect.getframeinfo(frame)
    logger.info(f"received signal {signal_name} in {filename} {function} at line {line}")
    tb = ''.join(traceback.format_stack(frame))
    logger.info(tb)
    print("")
    print("Break received, aborting.")
    sys.exit(1)


class CloudMgrError(FatalError):
    pass


class CustomDisplayFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG: f"[{C.GREY_COLOR}{C.FORMAT_LEVEL}{C.SCREEN_RESET}] {C.FORMAT_MESSAGE}",
        logging.INFO: f"[{C.GREEN_COLOR}{C.FORMAT_LEVEL}{C.SCREEN_RESET}] {C.FORMAT_MESSAGE}",
        logging.WARNING: f"[{C.YELLOW_COLOR}{C.FORMAT_LEVEL}{C.SCREEN_RESET}] {C.FORMAT_MESSAGE}",
        logging.ERROR: f"[{C.RED_COLOR}{C.FORMAT_LEVEL}{C.SCREEN_RESET}] {C.FORMAT_MESSAGE}",
        logging.CRITICAL: f"[{C.BOLD_RED_COLOR}{C.FORMAT_LEVEL}{C.SCREEN_RESET}] {C.FORMAT_MESSAGE}"
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class CustomMinimalDisplayFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG: f"{C.FORMAT_MESSAGE}",
        logging.INFO: f"{C.FORMAT_MESSAGE}",
        logging.WARNING: f"{C.FORMAT_MESSAGE}",
        logging.ERROR: f"{C.FORMAT_MESSAGE}",
        logging.CRITICAL: f"{C.FORMAT_MESSAGE}"
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class CustomLogFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG: f"{C.FORMAT_TIMESTAMP} [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}",
        logging.INFO: f"{C.FORMAT_TIMESTAMP} [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}",
        logging.WARNING: f"{C.FORMAT_TIMESTAMP} [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}",
        logging.ERROR: f"{C.FORMAT_TIMESTAMP} [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}",
        logging.CRITICAL: f"{C.FORMAT_TIMESTAMP} [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}"
    }

    @staticmethod
    def _filter(s):
        return re.sub(r'(\".*password\"\s*:\s*\").+?(\")', r'\1********\2', s)

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        if logging.DEBUG >= logging.root.level:
            log_fmt += C.FORMAT_EXTRA
        formatter = logging.Formatter(log_fmt)
        original = formatter.format(record)
        return self._filter(original)


class StreamOutputLogger(object):
    def __init__(self, _logger, _level, _file=None):
        self.logger = _logger
        self.level = _level
        if not _file:
            self.file = sys.stdout
        else:
            self.file = _file
        self.buffer = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def __getattr__(self, name):
        return getattr(self.file, name)

    def flush(self):
        pass


class CLI(object):

    def __init__(self, args):
        self.log_dir = get_log_dir()
        signal.signal(signal.SIGINT, break_signal_handler)
        default_debug_file = os.path.join(self.log_dir, "formation.log")
        debug_file = os.environ.get("COUCH_FORMATION_DEBUG_FILE", default_debug_file)
        self.args = args
        self.parser = None
        self.options = None
        self.remainder = None

        if os.name == 'nt':
            from ctypes import windll
            k = windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)

        if self.args is None:
            self.args = sys.argv[1:]

        self.init_parser()

        try:
            FileManager().make_dir(self.log_dir)
        except Exception as err:
            raise CloudMgrError(f"can not create log dir: {err}")

        screen_handler = logging.StreamHandler()
        screen_handler.setFormatter(CustomDisplayFormatter())
        screen_handler.setLevel(logging.INFO)
        logger.addHandler(screen_handler)

        min_log = logging.getLogger('minimum_output')
        min_screen_handler = logging.StreamHandler()
        min_screen_handler.setFormatter(CustomMinimalDisplayFormatter())
        min_screen_handler.setLevel(logging.INFO)
        min_log.addHandler(min_screen_handler)
        min_log.propagate = False

        file_handler = logging.handlers.RotatingFileHandler(debug_file, maxBytes=10485760, backupCount=5)
        file_handler.setFormatter(CustomLogFormatter())
        logger.addHandler(file_handler)

        logger.setLevel(logging.DEBUG)

        process = psutil.Process(os.getpid())
        logger.debug(f"---- CLI Start: {self.get_timestamp()} PID: {process.pid}----")
        logger.debug(f"---- CLI: {process.name()} {' '.join(sys.argv)} ----")

        self.process_args()

    @staticmethod
    def get_timestamp():
        return datetime.utcnow().strftime("%b %d %H:%M:%S")

    def init_parser(self):
        self.parser = argparse.ArgumentParser(add_help=False)
        self.parser.add_argument('-d', '--debug', action='store_true', help="Debug output")
        self.parser.add_argument('-v', '--verbose', action='store_true', help="Verbose output")

    def local_args(self):
        pass

    def process_args(self):
        self.local_args()
        self.options, self.remainder = self.parser.parse_known_args(self.args)
        if self.options.debug:
            logger.setLevel(logging.DEBUG)
