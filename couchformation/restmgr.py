##
##

import os
import logging
import math
import json
import requests
import warnings
import base64
import asyncio
import ssl
from typing import Union, List
from requests.adapters import HTTPAdapter, Retry
from requests.auth import AuthBase
from aiohttp import ClientSession, TCPConnector
from couchformation.retry import retry
from couchformation.exception import NonFatalError
from couchformation.capella.driver.cb_capella_config import CapellaConfigFile
if os.name == 'nt':
    import certifi_win32
    certifi_where = certifi_win32.wincerts.where()
else:
    import certifi
    certifi_where = certifi.where()

logger = logging.getLogger('couchformation.restmgr')
logger.addHandler(logging.NullHandler())
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)


class RetryableError(NonFatalError):
    pass


class CapellaAuth(AuthBase):

    def __init__(self, key_id: str, token: str):
        self.profile_key_id = key_id
        self.profile_token = token

        self.request_headers = {
            "Authorization": f"Bearer {self.profile_token}",
        }

    def __call__(self, r):
        r.headers.update(self.request_headers)
        return r

    def get_header(self):
        return self.request_headers


class BasicAuth(AuthBase):

    def __init__(self, username, password):
        self.username = username
        self.password = password
        auth_hash = f"{self.username}:{self.password}"
        auth_bytes = auth_hash.encode('ascii')
        auth_encoded = base64.b64encode(auth_bytes)

        self.request_headers = {
            "Authorization": f"Basic {auth_encoded.decode('ascii')}",
        }

    def __call__(self, r):
        r.headers.update(self.request_headers)
        return r

    def get_header(self):
        return self.request_headers


class RESTManager(object):

    def __init__(self,
                 hostname: Union[str, None] = None,
                 username: Union[str, None] = None,
                 password: Union[str, None] = None,
                 token: Union[str, None] = None,
                 use_ssl: bool = True,
                 verify: bool = True,
                 port: Union[int, None] = None,
                 profile: Union[str, None] = None):
        warnings.filterwarnings("ignore")
        self.hostname = hostname
        self.username = username
        self.password = password
        self.token = token
        self.ssl = use_ssl
        self.verify = verify
        self.port = port
        self.scheme = 'https' if self.ssl else 'http'
        self.response_text = None
        self.response_list = []
        self.response_dict = {}
        self.response_code = 200
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.ssl_context = ssl.create_default_context()
        self.ssl_context.load_verify_locations(certifi_where)

        if self.username is not None and self.password is not None:
            self.auth_class = BasicAuth(self.username, self.password)
        else:
            cf = CapellaConfigFile(profile)
            cf.read_token()
            logger.debug(f"Using Capella auth: key ID: {cf.key_id}")
            self.hostname = cf.api_host
            self.auth_class = CapellaAuth(cf.key_id, cf.token)

        if not self.hostname:
            self.hostname = '127.0.0.1'

        self.request_headers = self.auth_class.get_header()
        self.session = requests.Session()
        retries = Retry(total=10,
                        backoff_factor=0.01)
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

        if not port:
            if use_ssl:
                self.port = 443
            else:
                self.port = 80

        self.url_prefix = f"{self.scheme}://{self.hostname}:{self.port}"

    def get(self, url: str):
        response = self.session.get(url, auth=self.auth_class, verify=self.verify)
        self.response_text = response.text
        self.response_code = response.status_code
        return self

    def post(self, url: str, body: dict):
        response = self.session.post(url, auth=self.auth_class, json=body, verify=self.verify)
        self.response_text = response.text
        self.response_code = response.status_code
        return self

    def patch(self, url: str, body: dict):
        response = self.session.patch(url, auth=self.auth_class, json=body, verify=self.verify)
        self.response_text = response.text
        self.response_code = response.status_code
        return self

    def put(self, url: str, body: dict):
        response = self.session.put(url, auth=self.auth_class, json=body, verify=self.verify)
        self.response_text = response.text
        self.response_code = response.status_code
        return self

    def delete(self, url: str):
        response = self.session.delete(url, auth=self.auth_class, verify=self.verify)
        self.response_text = response.text
        self.response_code = response.status_code
        return self

    def validate(self):
        if self.response_code >= 300:
            try:
                response_json = json.loads(self.response_text)
                message = f"Can not access Capella API: Response Code: {self.response_code}"
                if 'message' in response_json:
                    message += f" Message: {response_json['message']}"
                if 'hint' in response_json:
                    message += f" Hint: {response_json['hint']}"
                if self.response_code == 412:
                    raise RetryableError(message)
                else:
                    raise RuntimeError(message)
            except json.decoder.JSONDecodeError:
                raise RuntimeError(f"Invalid response from API endpoint: response code: {self.response_code}")
        return self

    def json(self):
        try:
            return json.loads(self.response_text)
        except json.decoder.JSONDecodeError:
            return {}

    def as_json(self):
        try:
            self.response_dict = json.loads(self.response_text)
        except json.decoder.JSONDecodeError:
            self.response_dict = {}
        return self

    def list(self):
        return self.response_list

    def filter(self, key: str, value: str):
        self.response_list = [item for item in self.response_list if item.get(key) == value]
        return self

    def default(self):
        try:
            self.response_dict = self.response_list[0]
        except IndexError:
            self.response_dict = {}
        return self

    def item(self, index: int):
        try:
            self.response_dict = self.response_list[index]
        except IndexError:
            self.response_dict = {}
        return self

    def key(self, key: str):
        return self.response_dict.get(key)

    def record(self):
        if self.response_dict:
            return self.response_dict
        else:
            return None

    def by_name(self, name: str):
        self.response_list = [item for item in self.response_list if item.get('name') == name]
        return self

    def by_id(self, item_id: str):
        self.response_list = [item for item in self.response_list if item.get('id') == item_id]
        return self

    def name(self):
        try:
            return self.response_dict['name']
        except KeyError:
            return None

    def id(self):
        try:
            return self.response_dict['id']
        except KeyError:
            return None

    def unique(self):
        if len(self.response_list) > 1:
            raise ValueError("More than one object matches search criteria")
        return self.default()

    def page_url(self, endpoint: str, page: int, per_page: int) -> str:
        return f"{self.url_prefix}{endpoint}?page={page}&perPage={per_page}"

    def build_url(self, endpoint: str) -> str:
        return f"{self.url_prefix}{endpoint}"

    @retry()
    async def get_async(self, url: str):
        conn = TCPConnector(ssl_context=self.ssl_context)
        async with ClientSession(headers=self.request_headers, connector=conn) as session:
            async with session.get(url, verify_ssl=self.verify) as response:
                response = await response.json()
                return response.get('data', [])

    @retry()
    async def get_kv_async(self, url: str, key: str, value: str):
        conn = TCPConnector(ssl_context=self.ssl_context)
        async with ClientSession(headers=self.request_headers, connector=conn) as session:
            async with session.get(url, verify_ssl=self.verify) as response:
                response = await response.json()
                return [item for item in response.get('data', []) if item.get(key) == value]

    async def get_capella_a(self, endpoint: str):
        data = []
        url = self.page_url(endpoint, 1, 1)
        logger.debug(f"Capella get {url}")
        cursor = self.get(url).validate().json()

        total_items = cursor.get('cursor', {}).get('pages', {}).get('totalItems', 1)
        pages = math.ceil(total_items / 10)

        for result in asyncio.as_completed([self.get_async(self.page_url(endpoint, page, 10)) for page in range(1, pages + 1)]):
            block = await result
            data.extend(block)

        self.response_list = data

    @retry()
    async def get_capella_kv_a(self, endpoint: str, key: str, value: str):
        data = []
        url = self.page_url(endpoint, 1, 1)
        cursor = self.get(url).validate().json()

        total_items = cursor.get('cursor', {}).get('pages', {}).get('totalItems', 1)
        pages = math.ceil(total_items / 10)

        for result in asyncio.as_completed([self.get_kv_async(self.page_url(endpoint, page, 10), key, value) for page in range(1, pages + 1)]):
            block = await result
            data.extend(block)

        if len(data) == 0:
            raise ValueError('No match')
        self.response_list = data

    def get_capella(self, endpoint: str):
        self.response_list = []
        self.response_dict = {}
        self.loop.run_until_complete(self.get_capella_a(endpoint))
        return self

    def get_capella_kv(self, endpoint: str, key: str, value: str):
        self.response_list = []
        self.response_dict = {}
        self.loop.run_until_complete(self.get_capella_kv_a(endpoint, key, value))
        return self

    def post_capella(self, endpoint: str, body: dict):
        self.response_list = []
        self.response_dict = {}
        url = self.build_url(endpoint)
        self.response_dict = self.post(url, body).validate().json()
        return self

    def patch_capella(self, endpoint: str, body: Union[dict, List[dict]]):
        self.response_list = []
        self.response_dict = {}
        url = self.build_url(endpoint)
        self.response_dict = self.patch(url, body).validate().json()
        return self

    def put_capella(self, endpoint: str, body: Union[dict, List[dict]]):
        self.response_list = []
        self.response_dict = {}
        url = self.build_url(endpoint)
        self.response_dict = self.put(url, body).validate().json()
        return self

    def delete_capella(self, endpoint: str):
        self.response_list = []
        self.response_dict = {}
        url = self.build_url(endpoint)
        self.response_dict = self.delete(url).validate().json()
        return self
