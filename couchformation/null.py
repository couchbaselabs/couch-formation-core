##
##

import logging

logger = logging.getLogger('couchformation.null')
logger.addHandler(logging.NullHandler())


class NullClass(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters

    def null_f(self):
        logger.debug(f"Null call for name {self.parameters.get('name')}")
        pass
