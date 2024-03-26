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

        with open(crash_log_file, 'a') as log:
            now = datetime.now()
            time_string = now.strftime("%D %I:%M:%S %p")
            log.write(f"---- BEGIN {time_string} ----\n")
            log.write(f"== <ERROR> ==\n")
            log.write(f"{message} [{filename}:{line}]\n")
            trace_output = traceback.format_exc()
            if trace_output:
                log.write(f"== <TRACE> ==\n")
                log.write(trace_output)
            log.write(f"---- END ----\n")
            log.flush()

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
