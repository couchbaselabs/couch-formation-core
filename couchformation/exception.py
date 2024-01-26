##
##

import sys
import os
import inspect
import logging
import logging.handlers
import traceback
import couchformation.constants as C
from datetime import datetime
from couchformation.config import get_log_dir

logger = logging.getLogger('couchformation.error')
logger.addHandler(logging.NullHandler())


class CustomCrashFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG: f"{C.FORMAT_MESSAGE}",
        logging.INFO: f"{C.FORMAT_MESSAGE}",
        logging.WARNING: f"{C.FORMAT_MESSAGE}",
        logging.ERROR: f"{C.FORMAT_MESSAGE}",
        logging.CRITICAL: f"{C.FORMAT_MESSAGE}"
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        if logging.DEBUG >= logging.root.level:
            log_fmt += C.FORMAT_EXTRA
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class FatalError(Exception):

    def __init__(self, message):
        frame = inspect.currentframe().f_back
        (filename, line, function, lines, index) = inspect.getframeinfo(frame)
        filename = os.path.basename(filename)
        logging.debug(f"Error: {type(self).__name__} in {filename} {function} at line {line}: {message}")
        logging.error(f"{message} [{filename}:{line}]")

        crash_log_file = os.path.join(get_log_dir(), "crash.log")
        logging.debug(f"See {crash_log_file} for stack trace")

        crash_handler = logging.handlers.RotatingFileHandler(crash_log_file, maxBytes=10485760, backupCount=5)
        crash_handler.setFormatter(CustomCrashFormatter())
        crash_handler.setLevel(logging.DEBUG)
        crash_logger = logging.getLogger('exception')
        crash_logger.propagate = False
        crash_logger.addHandler(crash_handler)

        now = datetime.now()
        time_string = now.strftime("%D %I:%M:%S %p")
        crash_logger.debug(f"---- {time_string} ----")
        crash_logger.debug(traceback.extract_stack(self.__traceback__.tb_frame))
        if self.__context__:
            crash_logger.debug("The above exception was raised while handling this exception:")
            crash_logger.debug(traceback.extract_stack(self.__context__.__traceback__.tb_frame))

        sys.exit(1)


class NonFatalLogError(Exception):

    def __init__(self, message):
        frame = inspect.currentframe().f_back
        (filename, line, function, lines, index) = inspect.getframeinfo(frame)
        filename = os.path.basename(filename)
        logging.debug(f"Error: {type(self).__name__} in {filename} {function} at line {line}: {message}")
        logging.debug(''.join(traceback.format_stack(frame)))
        logging.error(f"{message} [{filename}:{line}]")


class NonFatalError(Exception):

    def __init__(self, message):
        frame = inspect.currentframe().f_back
        (filename, line, function, lines, index) = inspect.getframeinfo(frame)
        filename = os.path.basename(filename)
        self.message = f"Error: {type(self).__name__} in {filename} {function} at line {line}: {message}"
        super().__init__(self.message)
