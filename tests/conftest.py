#
#

import logging
import warnings
import os
import pytest
from pathlib import Path
from io import TextIOWrapper

warnings.filterwarnings("ignore")
logger = logging.getLogger()

ROOT_DIRECTORY = os.path.join(Path.home(), '.config', 'couch-formation')
STATE_DIRECTORY = os.path.join(ROOT_DIRECTORY, 'state')
LOG_DIRECTORY = os.path.join(ROOT_DIRECTORY, 'log')
FAILURE_LOG = 'failure.log'
RESULTS_FILE: TextIOWrapper


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


def make_dir(name: str):
    if not os.path.exists(name):
        path_dir = os.path.dirname(name)
        if not os.path.exists(path_dir):
            make_dir(path_dir)
        try:
            os.mkdir(name)
        except OSError:
            raise


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport():
    outcome = yield
    rep = outcome.get_result()

    if rep.when == 'call' and rep.failed:
        with open(FAILURE_LOG, 'a') as f:
            f.write(f"{rep.head_line}\n")
            f.write(f"{rep.longreprtext}\n")


def pytest_configure():
    pass


def pytest_sessionstart():
    global RESULTS_FILE
    RESULTS_FILE = open("results.log", "w")
    make_dir(LOG_DIRECTORY)
    if os.path.exists(FAILURE_LOG):
        open(FAILURE_LOG, 'w').close()


def pytest_sessionfinish():
    global RESULTS_FILE
    if RESULTS_FILE:
        RESULTS_FILE.close()
        RESULTS_FILE = None


def pytest_unconfigure():
    pass


def pytest_runtest_logreport(report):
    RESULTS_FILE.write(f"{report.nodeid} {report.when} {report.outcome} {report.duration}\n")
