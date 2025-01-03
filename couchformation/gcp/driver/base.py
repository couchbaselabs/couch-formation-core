##
##

import os.path
import socket
import logging
import json
import time
import base64
import sqlite3
import googleapiclient.discovery
import googleapiclient.errors
import google.auth
import google.auth.transport.requests
from pathlib import Path
from google.cloud import storage
from google.oauth2 import service_account
from google.cloud import resourcemanager_v3
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
    cache = {}

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.auth_directory = get_auth_directory()
        self.gcp_account = None
        self.gcp_project = None
        self.gcp_region = None
        self.gcp_account_file = None
        self._service_account_email = None
        self._user_account_email = None
        self.gcp_zone_list = []
        self.gcp_zone = None

        socket.setdefaulttimeout(120)

        if not parameters.get('auth_mode') or AuthMode[parameters.get('auth_mode')] == AuthMode.default:
            if not CloudBase.cache.get('credentials') or not CloudBase.cache.get('gcp_project'):
                self.credentials, self.gcp_project = self.default_auth()
                CloudBase.cache['credentials'] = self.credentials
                CloudBase.cache['gcp_project'] = self.gcp_project
            else:
                self.credentials = CloudBase.cache.get('credentials')
                self.gcp_project = CloudBase.cache.get('gcp_project')

            if not CloudBase.cache.get('service_account_email') or not CloudBase.cache.get('user_account_email'):
                self._service_account_email, self._user_account_email = self.get_account_email()
                CloudBase.cache['service_account_email'] = self._service_account_email
                CloudBase.cache['user_account_email'] = self._user_account_email
            else:
                self._service_account_email = CloudBase.cache.get('service_account_email')
                self._user_account_email = CloudBase.cache.get('user_account_email')
        elif AuthMode[parameters.get('auth_mode')] == AuthMode.file:
            self.credentials, self.gcp_project, self._service_account_email = self.file_auth()
        else:
            raise GCPDriverError(f"Unsupported auth mode {parameters.get('auth_mode')}")

        self.gcp_client = googleapiclient.discovery.build('compute', 'v1', credentials=self.credentials)
        self.dns_client = googleapiclient.discovery.build('dns', 'v1', credentials=self.credentials)

        if not self.gcp_project:
            raise GCPDriverError(f"can not determine GCP project")

        self.gcp_region = parameters.get('region')

        if not self.gcp_region:
            raise GCPDriverError("region not specified")

        try:
            self.zones()
        except GCPDriverTransientError:
            raise GCPDriverError(f"There is likely an auth config or firewall problem - make sure you can access the GCP API and use \"gcloud auth\" to configure access")
        except Exception as err:
            raise GCPDriverError(f"error getting availability zones: {err}")

    def test_session(self):
        try:
            storage_client = storage.Client(project=self.gcp_project, credentials=self.credentials)
            storage_client.list_buckets()
        except Exception as err:
            raise GCPDriverError(f"not authorized: {err}")

    @staticmethod
    def default_auth():
        try:
            credentials, project_id = google.auth.default()
            return credentials, project_id
        except Exception as err:
            raise GCPDriverError(f"error connecting to GCP: {err}")

    def get_account_email(self):
        try:
            if hasattr(self.credentials, "service_account_email"):
                service_account_email = self.credentials.service_account_email
                account_email = None
            elif hasattr(self.credentials, "signer_email"):
                service_account_email = self.credentials.signer_email
                account_email = None
            else:
                service_account_email = None
                request = google.auth.transport.requests.Request()
                self.credentials.refresh(request=request)
                token_payload = self.credentials.id_token.split('.')[1]
                input_bytes = token_payload.encode('utf-8')
                rem = len(input_bytes) % 4
                if rem > 0:
                    input_bytes += b"=" * (4 - rem)
                json_data = base64.urlsafe_b64decode(input_bytes).decode('utf-8')
                token_data = json.loads(json_data)
                account_email = token_data.get('email')
            return service_account_email, account_email
        except Exception as err:
            raise GCPDriverError(f"error getting GCP account email: {err}")

    @staticmethod
    def get_config_dir():
        if 'CLOUDSDK_CONFIG' in os.environ:
            return os.environ['CLOUDSDK_CONFIG']
        if os.name != 'nt':
            return os.path.join(Path.home(), '.config', 'gcloud')
        if 'APPDATA' in os.environ:
            return os.path.join(os.environ['APPDATA'], 'gcloud')
        drive = os.environ.get('SystemDrive', 'C:')
        return os.path.join(drive, os.path.sep, 'gcloud')

    def get_account(self, account: str):
        account_db = os.path.join(self.get_config_dir(), 'credentials.db')
        connection = sqlite3.connect(
            account_db,
            detect_types=sqlite3.PARSE_DECLTYPES,
            isolation_level=None,
            check_same_thread=True
        )

        cursor = connection.cursor()
        table = cursor.execute('SELECT account_id, value FROM credentials').fetchall()
        for row in table:
            account_id, cred_json = row[0], row[1]
            if account_id == account:
                return json.loads(cred_json)

        return None

    def sa_auth(self, service_account_email):
        auth_data = self.get_account(service_account_email)
        if not auth_data:
            raise GCPDriverError(f"Account {service_account_email} is not configured. Use gcloud auth to add the account.")
        credentials, _ = google.auth.load_credentials_from_dict(auth_data)
        return credentials

    @property
    def project_number(self):
        rm = resourcemanager_v3.ProjectsClient()
        req = resourcemanager_v3.GetProjectRequest(dict(name=f"projects/{self.gcp_project}"))
        res = rm.get_project(request=req)
        project_number = res.name.split('/')[1]
        return project_number

    @property
    def default_sa(self):
        return f"{self.project_number}-compute@developer.gserviceaccount.com"

    def file_auth(self):
        auth_file = get_default_credentials()
        if os.path.exists(auth_file):
            credentials = service_account.Credentials.from_service_account_file(auth_file)
            auth_data = self.read_auth_file(auth_file)
            project_id = auth_data.get('project_id')
            account_email = auth_data.get('client_email')
            return credentials, project_id, account_email
        else:
            raise GCPDriverError(f"file auth selected: can not find application_default_credentials.json")

    @staticmethod
    def read_auth_file(auth_file: str):
        file_handle = open(auth_file, 'r')
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

    @property
    def service_account_email(self):
        return self._service_account_email

    @property
    def login_account_email(self):
        return self._user_account_email

    @property
    def account_email(self):
        return self._service_account_email if self._service_account_email else self._user_account_email

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
