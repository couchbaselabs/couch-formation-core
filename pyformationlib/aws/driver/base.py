##
##

import logging
import boto3
import botocore.exceptions
import botocore.session
from botocore.config import Config
import os
import attr
import webbrowser
import time
import configparser
from datetime import datetime
from Crypto.PublicKey import RSA
from attr.validators import instance_of as io
from typing import Iterable, Union
from itertools import cycle
from pyformationlib.aws.driver.constants import AuthMode, AWSDriverError

logger = logging.getLogger('pyformationlib.aws.driver.base')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class CloudBase(object):

    def __init__(self, region: str = None, auth_type: AuthMode = AuthMode.default, profile: str = 'default'):
        self.config_directory = os.path.join(os.environ['HOME'], '.aws')
        self.config_file = os.path.join(self.config_directory, 'config')
        self.credential_file = os.path.join(self.config_directory, 'credentials')
        self.config_data = configparser.ConfigParser()
        self.credential_data = configparser.ConfigParser()
        self.profile = profile
        self.sso_session = None
        self.sso_account_id = None
        self.sso_role_name = None
        self.sso_start_url = None
        self.sso_region = None
        self.sso_registration_scopes = None
        self.profile_region = None
        self.aws_region = None
        self.zone_list = []
        self.access_key = None
        self.secret_key = None
        self.token = None
        self.token_expiration = None
        self.timeouts = Config(
            connect_timeout=1,
            read_timeout=1,
            retries={'max_attempts': 2}
        )

        self.read_config()

        if auth_type == AuthMode.default:
            self.default_auth()
        else:
            self.sso_auth()

        if region:
            os.environ['AWS_DEFAULT_REGION'] = region
        elif self.profile_region:
            os.environ['AWS_DEFAULT_REGION'] = self.profile_region

        if self.access_key:
            os.environ['AWS_ACCESS_KEY_ID'] = self.access_key
        if self.secret_key:
            os.environ['AWS_SECRET_ACCESS_KEY'] = self.secret_key
        if self.token:
            os.environ['AWS_SESSION_TOKEN'] = self.token

        try:
            self.ec2_client = boto3.client('ec2', region_name=self.aws_region)
        except Exception as err:
            raise AWSDriverError(f"can not initialize AWS driver: {err}")

        # self.set_zone()

    def read_config(self):
        if os.path.exists(self.config_file):
            try:
                self.config_data.read(self.config_file)
            except Exception as err:
                raise AWSDriverError(f"can not read config file {self.config_file}: {err}")

        if os.path.exists(self.credential_file):
            try:
                self.credential_data.read(self.credential_file)
            except Exception as err:
                raise AWSDriverError(f"can not read config file {self.credential_file}: {err}")

    def read_sso_config(self):
        for section, contents in self.config_data.items():
            if section.startswith('profile'):
                profile_name = section.split()[1]
                if self.profile != 'default':
                    if profile_name != self.profile:
                        continue
                else:
                    self.profile = profile_name
                logger.debug(f"SSO: using profile {self.profile}")
                self.sso_session = contents.get('sso_session')
                self.sso_account_id = contents.get('sso_account_id')
                self.sso_role_name = contents.get('sso_role_name')
                self.profile_region = contents.get('region')

        for section, contents in self.config_data.items():
            if section.startswith('sso-session'):
                session_name = section.split()[1]
                if session_name == self.sso_session:
                    self.sso_start_url = contents.get('sso_start_url')
                    self.sso_region = contents.get('sso_region')
                    self.sso_registration_scopes = contents.get('sso_registration_scopes')

    @staticmethod
    def auth_expired(timestamp):
        if timestamp:
            _timestamp = timestamp / 1000
            expires = datetime.fromtimestamp(_timestamp)
            if datetime.now() < expires:
                return False
        return True

    def default_auth(self):
        session = boto3.Session(profile_name=self.profile)
        credentials = session.get_credentials()
        self.access_key = credentials.access_key
        self.secret_key = credentials.secret_key

    def save_auth(self):
        dt = datetime.fromtimestamp(self.token_expiration / 1000)
        token_expiration = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
        self.credential_data[self.profile] = {
            'aws_access_key_id': self.access_key,
            'aws_secret_access_key': self.secret_key,
            'aws_session_token': self.token,
            'x_security_token_expires': token_expiration
        }
        with open(self.credential_file, 'w') as config_file:
            self.credential_data.write(config_file)

    def sso_auth(self):
        token = {}

        self.read_sso_config()

        session = botocore.session.Session()
        profiles_config = session.full_config.get('profiles', {})
        default_config = profiles_config.get(self.profile, {})

        self.access_key = default_config.get("aws_access_key_id")
        self.secret_key = default_config.get("aws_secret_access_key")
        self.token = default_config.get("aws_session_token")
        token_expiration_str = default_config.get("x_security_token_expires")
        if token_expiration_str:
            dt = datetime.strptime(token_expiration_str, '%Y-%m-%dT%H:%M:%S.%f')
            self.token_expiration = dt.timestamp() * 1000

        if not self.auth_expired(self.token_expiration):
            return

        if not self.sso_account_id or not self.sso_start_url or not self.sso_region:
            AWSDriverError("Please run aws configure sso to setup SSO")

        session = boto3.Session()
        account_id = self.sso_account_id
        start_url = self.sso_start_url
        region = self.sso_region
        sso_oidc = session.client('sso-oidc', region_name=region)
        client_creds = sso_oidc.register_client(
            clientName='couch-formation',
            clientType='public',
        )
        device_authorization = sso_oidc.start_device_authorization(
            clientId=client_creds['clientId'],
            clientSecret=client_creds['clientSecret'],
            startUrl=start_url,
        )
        url = device_authorization['verificationUriComplete']
        device_code = device_authorization['deviceCode']
        expires_in = device_authorization['expiresIn']
        interval = device_authorization['interval']
        webbrowser.open(url, autoraise=True)
        for n in range(1, expires_in // interval + 1):
            time.sleep(interval)
            try:
                token = sso_oidc.create_token(
                    grantType='urn:ietf:params:oauth:grant-type:device_code',
                    deviceCode=device_code,
                    clientId=client_creds['clientId'],
                    clientSecret=client_creds['clientSecret'],
                )
                break
            except sso_oidc.exceptions.AuthorizationPendingException:
                pass

        access_token = token['accessToken']
        sso = session.client('sso', region_name=region)
        account_roles = sso.list_account_roles(
            accessToken=access_token,
            accountId=account_id,
        )
        roles = account_roles['roleList']
        role = roles[0]
        role_creds = sso.get_role_credentials(
            roleName=role['roleName'],
            accountId=account_id,
            accessToken=access_token,
        )

        session_creds = role_creds['roleCredentials']

        self.access_key = session_creds['accessKeyId']
        self.secret_key = session_creds['secretAccessKey']
        self.token = session_creds['sessionToken']
        self.token_expiration = session_creds['expiration']
        self.save_auth()

    # def init(self):
    #     logger.info(f"importing region and zone information")
    #     regions = config.cloud_base().get_all_regions()
    #     count = 1
    #     for region in regions:
    #         try:
    #             logger.info(f" ... importing {region}")
    #             zones = config.cloud_base(region=region).zones()
    #             row = {
    #                 "id": count,
    #                 "name": region,
    #                 "zones": ','.join(zones),
    #                 "cloud": CLOUD_KEY
    #             }
    #             self.db.update_cloud(CloudTable.REGION, row)
    #             count += 1
    #         except (botocore.exceptions.ClientError, botocore.exceptions.ConnectTimeoutError):
    #             continue
    #
    #     logger.info(f"importing compute information")
    #     count = 1
    #     for region in regions:
    #         logger.info(f" ... generating compute for {region}")
    #         compute_list = config.cloud_machine_type(region=region).list()
    #         compute_list = sorted(compute_list, key=lambda c: c['name'])
    #         subset = set()
    #         compute_list = [x for x in compute_list if [(x['cpu'], x['memory']) not in subset, subset.add((x['cpu'], x['memory']))][0]]
    #         for compute in compute_list:
    #             config_str = f"{compute['cpu']}x{int(compute['memory'] / 1024)}"
    #             row = {
    #                 "id": count,
    #                 "name": compute['name'],
    #                 "config": config_str,
    #                 "cpu": compute['cpu'],
    #                 "memory": compute['memory'],
    #                 "architecture": compute['arch'][0],
    #                 "cloud": CLOUD_KEY,
    #                 "region": region
    #             }
    #             self.db.update_cloud(CloudTable.COMPUTE, row)
    #             count += 1
