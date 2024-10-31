##
##

import logging
from couchformation.exception import FatalError
from couchformation.resources.config_manager import ConfigurationManager
from libcapella.config import CapellaConfig
from libcapella.organization import CapellaOrganization
from libcapella.project import CapellaProject
from libcapella.logic.project import CapellaProjectBuilder

logger = logging.getLogger('couchformation.capella.driver.base')
logger.addHandler(logging.NullHandler())
logging.getLogger("restfull").setLevel(logging.ERROR)


class CapellaDriverError(FatalError):
    pass


class CloudBase(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self._token = None
        self._account_email = None
        self._account_id = None
        self._project_name = None

        cm = ConfigurationManager()
        if cm.get('capella.token'):
            self._token = cm.get('capella.token')
        if cm.get('capella.user'):
            self._account_email = cm.get('capella.user')
        if cm.get('capella.user.id'):
            self._account_id = cm.get('capella.user.id')
        if cm.get('capella.project'):
            self._project_name = cm.get('capella.project')
        else:
            self._project_name = parameters.get('project')

        try:
            if self._token and (self._account_email or self._account_id):
                config_dict = {
                    "token": self._token,
                    "account_email": self._account_email,
                    "project_name": self._project_name,
                    "account_id": self._account_id,
                }
                logger.debug(f"Capella config parameters: {config_dict}")
                config = CapellaConfig(config_dict=config_dict)
            else:
                profile = parameters.get('profile')
                logger.debug(f"Capella credential profile: {profile}")
                config = CapellaConfig(profile=profile)

            self._account_email = config.config.account_email

            if not self._account_email:
                raise CapellaDriverError("Capella account email not set")

            if not config.config.token:
                raise CapellaDriverError("Capella v4 API token not set")

            self.org = CapellaOrganization(config)
            self._project = CapellaProject(self.org, self._project_name, self._account_email)
            if not self._project.id:
                logger.info(f"Creating project {self._project_name}")
                builder = CapellaProjectBuilder()
                builder = builder.name(self._project_name)
                config = builder.build()
                self._project.create(config)
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
