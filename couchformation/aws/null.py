##
##

import logging

logger = logging.getLogger('couchformation.aws.null')
logger.addHandler(logging.NullHandler())


class AWSDeployment(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters

    def deploy(self):
        logger.info(f"Null call to deploy name {self.parameters.get('name')}")
