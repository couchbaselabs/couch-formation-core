##
##

import time
import logging
import os
import configparser
from functools import wraps
from typing import Union, List, Callable
from azure.identity import AzureCliCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.privatedns import PrivateDnsManagementClient
from azure.mgmt.resource.resources import ResourceManagementClient
from azure.mgmt.resource.subscriptions import SubscriptionClient
from couchformation.config import AuthMode
from couchformation.exception import FatalError, NonFatalError
from couchformation.azure.driver.constants import get_auth_directory, get_config_default, get_config_main
from couchformation.azure.driver.constants import AzureDiskTiers
from couchformation.exec.process import cmd_exec

logger = logging.getLogger('couchformation.azure.driver.base')
logger.addHandler(logging.NullHandler())
logging.getLogger("azure").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


def auth_retry(retry_count=10,
               factor=0.01
               ) -> Callable:
    def retry_handler(func):
        @wraps(func)
        def f_wrapper(*args, **kwargs):
            for retry_number in range(retry_count + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as err:
                    if retry_number == retry_count:
                        logger.debug(f"{func.__name__} retry limit exceeded: {err}")
                        raise
                    login_cmd = ['az', 'login']
                    cmd_exec(login_cmd)
                    wait = factor
                    wait *= (2 ** (retry_number + 1))
                    time.sleep(wait)
        return f_wrapper
    return retry_handler


class AzureDriverError(FatalError):
    pass


class EmptyResultSet(NonFatalError):
    pass


class CloudBase(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.auth_directory = get_auth_directory()
        self.config_default = get_config_default()
        self.config_main = get_config_main()
        self.cloud_name = 'AzureCloud'
        self.local_context = None
        self.azure_subscription_id = None
        self.credential = None
        self.azure_resource_group = None
        self.azure_location = None
        self.azure_availability_zones = []
        self.azure_zone = None
        self.subscription_client = None

        if not parameters.get('auth_mode') or AuthMode[parameters.get('auth_mode')] == AuthMode.default:
            self.credential, self.azure_subscription_id, self.azure_tenant_id = self.default_auth()
        else:
            raise AzureDriverError(f"Unsupported auth mode {parameters.get('auth_mode')}")

        if not self.credential or not self.azure_subscription_id:
            raise AzureDriverError("unauthorized (use az login)")

        self.resource_client = ResourceManagementClient(self.credential, self.azure_subscription_id)
        self.compute_client = ComputeManagementClient(self.credential, self.azure_subscription_id)
        self.network_client = NetworkManagementClient(self.credential, self.azure_subscription_id)
        self.dns_client = DnsManagementClient(self.credential, self.azure_subscription_id)
        self.private_dns_client = PrivateDnsManagementClient(self.credential, self.azure_subscription_id)

        self.azure_location = parameters.get('region')

        self.zones()

    @auth_retry()
    def default_auth(self):
        try:
            credential = AzureCliCredential()
            subscription_client = SubscriptionClient(credential)
            subscriptions = subscription_client.subscriptions.list()
            azure_subscription_id = next((s.subscription_id for s in subscriptions), None)
            azure_tenant_id = credential.tenant_id
            return credential, azure_subscription_id, azure_tenant_id
        except Exception as err:
            raise AzureDriverError(f"Azure: unauthorized (use az login): {err}")

    def test_session(self):
        if len(self.azure_availability_zones) == 0:
            raise AzureDriverError(f"Unable to determine availability zones for location {self.azure_location}")

    @staticmethod
    def disk_size_to_tier(value: Union[int, str]):
        size = int(value)
        size_list = [int(i['disk_size']) for i in AzureDiskTiers.disk_tier_list]
        value = min([s for s in size_list if s >= size])
        return next(t for t in AzureDiskTiers.disk_tier_list if t['disk_size'] == str(value))

    @staticmethod
    def disk_caching(value: Union[int, str], ultra: bool = False):
        size = int(value)
        if size > 4095 or ultra:
            return "None"
        else:
            return "ReadWrite"

    def read_config(self):
        if os.path.exists(self.config_main):
            config = configparser.ConfigParser()
            try:
                config.read(self.config_main)
            except Exception as err:
                raise AzureDriverError(f"can not read config file {self.config_main}: {err}")

            if 'cloud' in config:
                if 'name' in config['cloud']:
                    self.cloud_name = config['cloud']['name']

            if 'local_context' in config:
                try:
                    self.local_context = list(config['local_context'].keys())[0]
                except IndexError:
                    pass

        if os.path.exists(self.config_default):
            config = configparser.ConfigParser()
            try:
                config.read(self.config_default)
            except Exception as err:
                raise AzureDriverError(f"can not read config file {self.config_default}: {err}")

            if self.cloud_name in config:
                self.azure_subscription_id = config[self.cloud_name].get('subscription', None)

    def zones(self) -> list:
        zone_list = self.compute_client.resource_skus.list(filter=f"location eq '{self.azure_location}'")
        for group in list(zone_list):
            if group.resource_type == 'virtualMachines':
                for resource_location in group.location_info:
                    for zone_number in resource_location.zones:
                        self.azure_availability_zones.append(zone_number)

        self.azure_availability_zones = sorted(set(self.azure_availability_zones))

        if len(self.azure_availability_zones) == 0:
            raise AzureDriverError("can not get Azure availability zones")

        self.azure_zone = self.azure_availability_zones[0]
        return self.azure_availability_zones

    def create_rg(self, name: str, location: str, tags: Union[dict, None] = None) -> dict:
        if not tags:
            tags = {}
        if not tags.get('type'):
            tags.update({"type": "couch-formation"})
        try:
            if self.resource_client.resource_groups.check_existence(name):
                return self.get_rg(name, location)
            else:
                result = self.resource_client.resource_groups.create_or_update(
                    name,
                    {
                        "location": location,
                        "tags": tags
                    }
                )
                return result.__dict__
        except Exception as err:
            raise AzureDriverError(f"error creating resource group: {err}")

    def get_rg(self, name: str, location: str) -> Union[dict, None]:
        try:
            if self.resource_client.resource_groups.check_existence(name):
                result = self.resource_client.resource_groups.get(name)
                if result.location == location:
                    return result.__dict__
        except Exception as err:
            raise AzureDriverError(f"error getting resource group: {err}")

        return None

    def list_rg(self, location: Union[str, None] = None, filter_keys_exist: Union[List[str], None] = None) -> List[dict]:
        rg_list = []

        try:
            resource_groups = self.resource_client.resource_groups.list()
        except Exception as err:
            raise AzureDriverError(f"error getting resource groups: {err}")

        for group in list(resource_groups):
            if location:
                if group.location != location:
                    continue
            rg_block = {'location': group.location,
                        'name': group.name,
                        'id': group.id}
            rg_block.update(self.process_tags(group.tags))
            if filter_keys_exist:
                if not all(key in rg_block for key in filter_keys_exist):
                    continue
            rg_list.append(rg_block)

        if len(rg_list) == 0:
            raise EmptyResultSet(f"no resource groups found")

        return rg_list

    def delete_rg(self, name: str):
        try:
            if self.resource_client.resource_groups.check_existence(name):
                request = self.resource_client.resource_groups.begin_delete(name)
                request.wait()
        except Exception as err:
            raise AzureDriverError(f"error deleting resource group: {err}")

    def list_locations(self) -> List[dict]:
        location_list = []
        locations = self.subscription_client.subscriptions.list_locations(self.azure_subscription_id)
        for group in list(locations):
            location_block = {
                'name': group.name,
                'display_name': group.display_name
            }
            location_list.append(location_block)
        return location_list

    @staticmethod
    def process_tags(struct: dict) -> dict:
        block = {}
        if struct:
            for tag in struct:
                block.update({tag.lower() + '_tag': struct[tag]})
        block = dict(sorted(block.items()))
        return block

    def rg_switch(self):
        image_rg = f"cf-image-{self.azure_location}-rg"
        if self.get_rg(image_rg, self.azure_location):
            resource_group = image_rg
        else:
            resource_group = self.azure_resource_group
        return resource_group

    @property
    def region(self):
        return self.azure_location
