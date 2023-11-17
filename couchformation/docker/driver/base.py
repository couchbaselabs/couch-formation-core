##
##

import logging
import docker
from docker import APIClient
from couchformation.exception import FatalError, NonFatalError

logger = logging.getLogger('couchformation.docker.driver.base')
logger.addHandler(logging.NullHandler())
logging.getLogger("docker").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


class DockerDriverError(FatalError):
    pass


class EmptyResultSet(NonFatalError):
    pass


class CloudBase(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.project = parameters.get('project')
        self.name = parameters.get('name')

        self.client = docker.from_env()
        self.docker_api = APIClient(base_url='unix://var/run/docker.sock')
        stats = self.docker_api.version()
        eng = next((c for c in stats.get('Components', [{}]) if c.get('Name') == 'Engine'), None)

        self.arch = eng.get('Details', {}).get('Arch')

    @staticmethod
    def test_session():
        try:
            docker_api = APIClient(base_url='unix://var/run/docker.sock')
            docker_api.version()
            client = docker.from_env()
            client.info()
        except Exception as err:
            raise DockerDriverError(f"not authorized: {err}")

    @property
    def architecture(self):
        return self.arch
