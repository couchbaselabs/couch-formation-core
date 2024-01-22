#
#

import logging
import warnings
import os
from pathlib import Path

warnings.filterwarnings("ignore")
logger = logging.getLogger()

ROOT_DIRECTORY = os.path.join(Path.home(), '.config', 'couch-formation')
STATE_DIRECTORY = os.path.join(ROOT_DIRECTORY, 'state')
LOG_DIRECTORY = os.path.join(ROOT_DIRECTORY, 'log')


class CustomLogFormatter(logging.Formatter):
    format_timestamp = "%(asctime)s"
    format_level = "%(levelname)s"
    format_message = "%(message)s"
    format_extra = " [%(name)s](%(filename)s:%(lineno)d)"
    FORMATS = {
        logging.DEBUG: f"{format_timestamp} [{format_level}] {format_message}",
        logging.INFO: f"{format_timestamp} [{format_level}] {format_message}",
        logging.WARNING: f"{format_timestamp} [{format_level}] {format_message}",
        logging.ERROR: f"{format_timestamp} [{format_level}] {format_message}",
        logging.CRITICAL: f"{format_timestamp} [{format_level}] {format_message}"
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        if logging.DEBUG >= logging.root.level:
            log_fmt += CustomLogFormatter.format_extra
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    green = "\x1b[32;20m"
    reset = "\x1b[0m"
    format_level = "%(levelname)s"
    format_name = "%(name)s"
    format_message = "%(message)s"
    format_line = "(%(filename)s:%(lineno)d)"
    format_extra = " [%(name)s](%(filename)s:%(lineno)d)"
    FORMATS = {
        logging.DEBUG: f"{grey}{format_level}{reset} - {format_message}",
        logging.INFO: f"{green}{format_level}{reset} - {format_message}",
        logging.WARNING: f"{yellow}{format_level}{reset} - {format_message}",
        logging.ERROR: f"{red}{format_level}{reset} - {format_message}",
        logging.CRITICAL: f"{red}{format_level}{reset} - {format_message}"
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        if logging.DEBUG >= logging.root.level:
            log_fmt += self.format_extra
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def pytest_configure():
    pass


def pytest_sessionstart():
    log_dir = LOG_DIRECTORY
    default_debug_file = os.path.join(log_dir, "pytest.log")
    debug_file = os.environ.get("COUCH_FORMATION_DEBUG_FILE", default_debug_file)

    screen_handler = logging.StreamHandler()
    screen_handler.setFormatter(CustomFormatter())
    logger.addHandler(screen_handler)

    file_handler = logging.FileHandler(debug_file, 'w')
    file_handler.setFormatter(CustomLogFormatter())
    logger.addHandler(file_handler)

    logger.setLevel(logging.INFO)


def pytest_sessionfinish():
    pass


def pytest_unconfigure():
    pass
