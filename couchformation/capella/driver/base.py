##
##

import logging
from couchformation.capella.driver.cb_capella import Capella
from couchformation.exception import FatalError

logger = logging.getLogger('couchformation.capella.driver.base')
logger.addHandler(logging.NullHandler())


class CapellaDriverError(FatalError):
    pass


class CloudBase(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.profile = parameters.get('profile') if parameters.get('profile') else 'default'

        logger.debug(f"Capella credential profile: {self.profile}")
        try:
            self.cm = Capella(profile=self.profile)
            self._organization_id = self.cm.organization_id
            self._project_id = self.cm.project_id
        except Exception as err:
            raise CapellaDriverError(f"can not get Capella organization ID: {err}")

    def test_session(self):
        try:
            self.cm.list_organizations()
        except Exception as err:
            raise CapellaDriverError(f"not authorized: {err}")

    @property
    def project_id(self):
        return self._project_id

    @property
    def organization_id(self):
        return self._organization_id
