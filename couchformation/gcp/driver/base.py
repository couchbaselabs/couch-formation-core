##
##

import socket
import logging
import json
import time
import googleapiclient.discovery
import googleapiclient.errors
from google.cloud import storage
from google.oauth2 import service_account
from couchformation.config import AuthMode
from couchformation.exception import FatalError, NonFatalError
from couchformation.retry import retry
from couchformation.gcp.driver.constants import get_auth_directory, get_default_credentials

logger = logging.getLogger('couchformation.gcp.driver.base')
logger.addHandler(logging.NullHandler())
logging.getLogger("googleapiclient").setLevel(logging.ERROR)


class GCPDriverError(FatalError):
    pass


class GCPDriverTransientError(NonFatalError):
    pass


class EmptyResultSet(NonFatalError):
    pass


class CloudBase(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.auth_directory = get_auth_directory()
        self.gcp_account = None
        self.gcp_project = None
        self.gcp_region = None
        self.gcp_account_file = None
        self.gcp_account_email = None
        self.gcp_zone_list = []
        self.gcp_zone = None
        self.auth_file = get_default_credentials()

        socket.setdefaulttimeout(120)

        if not parameters.get('auth_mode') or AuthMode[parameters.get('auth_mode')] == AuthMode.default:
            self.gcp_client = self.default_auth()
        else:
            raise GCPDriverError(f"Unsupported auth mode {parameters.get('auth_mode')}")

        self.auth_data = self.read_auth_file()

        self.gcp_project = self.auth_data.get('project_id')
        self.gcp_account_email = self.auth_data.get('client_email')

        if not self.gcp_account_email:
            raise GCPDriverError(f"can not get account email from auth file {self.gcp_account_file}")

        if not self.gcp_project:
            raise GCPDriverError(f"can not get GCP project from auth file {self.gcp_account_file}")

        self.gcp_region = parameters.get('region')

        if not self.gcp_region:
            raise GCPDriverError("region not specified")

        self.zones()

    def test_session(self):
        try:
            credentials = service_account.Credentials.from_service_account_file(self.auth_file)
            storage_client = storage.Client(project=self.gcp_project, credentials=credentials)
            storage_client.list_buckets()
        except Exception as err:
            raise GCPDriverError(f"not authorized: {err}")

    def default_auth(self):
        try:
            credentials = service_account.Credentials.from_service_account_file(self.auth_file)
            return googleapiclient.discovery.build('compute', 'v1', credentials=credentials)
        except Exception as err:
            raise GCPDriverError(f"error connecting to GCP: {err}")

    def read_auth_file(self):
        file_handle = open(self.auth_file, 'r')
        auth_data = json.load(file_handle)
        file_handle.close()
        return auth_data

    @retry()
    def zones(self) -> list:
        try:
            request = self.gcp_client.zones().list(project=self.gcp_project)
            while request is not None:
                response = request.execute()
                for zone in response['items']:
                    if not zone['name'].startswith(self.gcp_region):
                        continue
                    self.gcp_zone_list.append(zone['name'])
                request = self.gcp_client.zones().list_next(previous_request=request, previous_response=response)
        except Exception as err:
            raise GCPDriverTransientError(f"error getting zones: {err}")

        self.gcp_zone_list = sorted(set(self.gcp_zone_list))

        if len(self.gcp_zone_list) == 0:
            raise GCPDriverError("can not get GCP availability zones")

        self.gcp_zone = self.gcp_zone_list[0]
        return self.gcp_zone_list

    @property
    def region(self):
        return self.gcp_region

    @property
    def account_file(self):
        return self.gcp_account_file

    @property
    def project(self):
        return self.gcp_project

    @staticmethod
    def process_labels(struct: dict) -> dict:
        block = {}
        if 'labels' in struct:
            for tag in struct['labels']:
                block.update({tag.lower() + '_tag': struct['labels'][tag]})
        block = dict(sorted(block.items()))
        return block

    def wait_for_global_operation(self, operation):
        while True:
            result = self.gcp_client.globalOperations().get(
                project=self.gcp_project,
                operation=operation).execute()

            if result['status'] == 'DONE':
                if 'error' in result:
                    raise GCPDriverError(result['error'])
                return result

            time.sleep(1)

    def wait_for_regional_operation(self, operation):
        while True:
            result = self.gcp_client.regionOperations().get(
                project=self.gcp_project,
                region=self.gcp_region,
                operation=operation).execute()

            if result['status'] == 'DONE':
                if 'error' in result:
                    raise GCPDriverError(result['error'])
                return result

            time.sleep(1)

    def wait_for_zone_operation(self, operation, zone):
        while True:
            result = self.gcp_client.zoneOperations().get(
                project=self.gcp_project,
                zone=zone,
                operation=operation).execute()

            if result['status'] == 'DONE':
                if 'error' in result:
                    raise GCPDriverError(result['error'])
                return result

            time.sleep(1)
