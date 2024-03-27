##
##

import os
import shutil
import configparser
from configparser import SectionProxy
from pathlib import Path
from typing import Union


class CapellaConfigFile(object):

    def __init__(self, profile: Union[str, None] = None):
        self.home_dir = Path.home()
        self.config_directory = os.path.join(self.home_dir, '.capella')
        self.config_file = os.path.join(self.config_directory, 'credentials')
        self.profile = profile if profile else 'default'
        self.config_data = configparser.ConfigParser()

        self._api_host = None
        self._token_file = None
        self._token_file_path = os.path.join(self.config_directory, 'default-api-key-token.txt')
        self._organization = None
        self._project = None
        self._account_email = None
        self._profile_key_id = None
        self._profile_token = None

        self.read_config('default')
        if self.profile != 'default':
            self.read_config(self.profile)

    def read_config(self, profile: str):
        if not os.path.exists(self.config_file):
            self.write_default_config()

        profile_config = self.read_config_file(profile)
        self._api_host = profile_config.get('api_host', self._api_host)
        self._token_file = profile_config.get('token_file', self._token_file)
        self._token_file_path = os.path.join(self.config_directory, self._token_file)
        self._organization = profile_config.get('organization', self._organization)
        self._project = profile_config.get('project', self._project)
        self._account_email = profile_config.get('account_email', self._account_email)

    def read_config_file(self, profile: str) -> SectionProxy:
        try:
            self.config_data.read(self.config_file)
            return self.config_data[profile]
        except KeyError:
            raise RuntimeError(f"profile {self.profile} does not exist in config file {self.config_file}")
        except Exception as err:
            raise RuntimeError(f"can not read config file {self.config_file}: {err}")

    def write_default_config(self):
        self.config_data['default'] = {
            'api_host': 'cloudapi.cloud.couchbase.com',
            'token_file': 'default-api-key-token.txt'
        }
        try:
            if not os.path.exists(self.config_directory):
                os.mkdir(self.config_directory)
            with open(self.config_file, 'w') as configfile:
                self.config_data.write(configfile)
        except Exception as err:
            raise RuntimeError(f"can not write config file {self.config_file}: {err}")

    def read_token(self):
        if not os.path.exists(self._token_file_path):
            self.find_token_file()
        self.read_token_file()

    def read_token_file(self):
        if os.path.exists(self._token_file_path):
            try:
                credential_data = dict(line.split(':', 1) for line in open(self._token_file_path))
                self._profile_token = credential_data.get('APIKeyToken').strip()
                self._profile_key_id = credential_data.get('APIKeyId').strip()
            except AttributeError:
                raise RuntimeError(f"token file {self._token_file} does not contain an API key and token")
            except Exception as err:
                raise RuntimeError(f"can not read credential file {self._token_file}: {err}")
        else:
            raise RuntimeError("Please create Capella token file (i.e. $HOME/.capella/default-api-key-token.txt)")

    def find_token_file(self):
        download_dir = os.path.join(Path.home(), 'Downloads')

        if os.path.exists(os.path.join(download_dir, self.token_file)):
            shutil.copy(os.path.join(download_dir, self.token_file), self._token_file_path)
        elif os.path.exists(os.path.join(self.home_dir, self.token_file)):
            shutil.copy(os.path.join(self.home_dir, self.token_file), self._token_file_path)

    @property
    def api_host(self):
        return self._api_host

    @property
    def token_file(self):
        return self._token_file

    @property
    def organization(self):
        return self._organization

    @property
    def project(self):
        return self._project

    @property
    def account_email(self):
        return self._account_email

    @property
    def token(self):
        return self._profile_token

    @property
    def key_id(self):
        return self._profile_key_id
