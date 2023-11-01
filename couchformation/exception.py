##
##

import sys
import os
import inspect
import logging
import traceback

logger = logging.getLogger('couchformation.error')
logger.addHandler(logging.NullHandler())


class FatalError(Exception):

    def __init__(self, message):
        frame = inspect.currentframe().f_back
        (filename, line, function, lines, index) = inspect.getframeinfo(frame)
        filename = os.path.basename(filename)
        logging.debug(f"Error: {type(self).__name__} in {filename} {function} at line {line}: {message}")
        logging.debug(''.join(traceback.format_stack(frame)))
        logging.error(f"{message} [{filename}:{line}]")
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
