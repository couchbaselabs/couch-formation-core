##
##

import logging
from couchformation.exception import FatalError
from libcapella.config import CapellaConfig
from libcapella.organization import CapellaOrganization
from libcapella.project import CapellaProject
from libcapella.user import CapellaUser
from libcapella.logic.project import CapellaProjectBuilder

logger = logging.getLogger('couchformation.capella.driver.base')
logger.addHandler(logging.NullHandler())


class CapellaDriverError(FatalError):
    pass


class CloudBase(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.profile = parameters.get('profile') if parameters.get('profile') else 'default'
        self._project_name = parameters.get('project')
        self._account_email = parameters.get('account_email')

        logger.debug(f"Capella credential profile: {self.profile}")
        try:
            config = CapellaConfig(profile=self.profile)

            if not self._account_email:
                self._account_email = config.account_email

            if not self._account_email:
                raise CapellaDriverError("Capella account email not set")

            if not config.token:
                raise CapellaDriverError("Capella v4 API token not set")

            self.org = CapellaOrganization(config)
            self._project = CapellaProject(self.org, self._project_name, self._account_email)
            if not self._project.id:
                logger.info(f"Creating project {self._project_name}")
                builder = CapellaProjectBuilder()
                builder = builder.name(self._project_name)
                config = builder.build()
                self._project.create(config)

                user = CapellaUser(self.org, self._account_email)
                user.set_project_owner(self._project.id)
        except Exception as err:
            raise CapellaDriverError(f"can not access Capella project {self._project_name}: {err}")

    def test_session(self):
        try:
            self.org.list()
        except Exception as err:
            raise CapellaDriverError(f"not authorized: {err}")

    @property
    def project_id(self):
        return self._project.id

    @property
    def organization_id(self):
        return self.org.id

    @property
    def project_name(self):
        return self.project_name

    @property
    def project(self):
        return self._project
