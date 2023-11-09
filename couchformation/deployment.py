##
##

import attr
import os
import json
import argparse
import couchformation.constants as C
from typing import Optional, List, Tuple
from enum import Enum
from couchformation.exception import FatalError
from couchformation.config import BaseConfig, NodeConfig, Parameters, AuthMode, get_project_dir
from couchformation.util import FileManager, dict_merge
from couchformation.kvdb import KeyValueStore

DEPLOYMENT = "deployment.db"


class DeploymentError(FatalError):
    pass


class ServiceModel(str, Enum):
    cbs = 'cbs'
    sgw = 'sgw'
    sdk = 'sdk'
    generic = 'generic'


@attr.s
class Service:
    cloud: Optional[str] = attr.ib(default="aws")
    name: Optional[str] = attr.ib(default="nodes")
    model: Optional[str] = attr.ib(default=ServiceModel.generic)
    region: Optional[str] = attr.ib(default=None)
    os_id: Optional[str] = attr.ib(default=None)
    os_version: Optional[str] = attr.ib(default=None)
    auth_mode: Optional[str] = attr.ib(default="default")
    profile: Optional[str] = attr.ib(default='default')
    connect_svc: Optional[str] = attr.ib(default=None)
    connect_ip: Optional[str] = attr.ib(default=None)
    config: Optional[List[NodeConfig]] = attr.ib(default=[])

    def from_dict(self, options: dict):
        for attribute in self.__annotations__:
            if attribute == 'config':
                continue
            if options.get(attribute):
                setattr(self, attribute, options.get(attribute))

    @property
    def auth(self) -> AuthMode:
        return AuthMode[self.auth_mode]


class NodeGroup(object):

    def __init__(self, options: argparse.Namespace):
        self.options = options
        self.project = self.options.project
        self.name = self.options.name
        self.cloud = self.options.cloud
        self.project_dir = get_project_dir(self.project)

        try:
            FileManager().make_dir(self.project_dir)
        except Exception as err:
            raise DeploymentError(f"can not create project dir: {err}")

        filename = os.path.join(self.project_dir, f"{self.name}.db")
        network = os.path.join(self.project_dir, C.NETWORK)
        metadata = os.path.join(self.project_dir, C.METADATA)
        self.db = KeyValueStore(filename)
        self.net = KeyValueStore(network)
        self.meta = KeyValueStore(metadata)

    def create_network(self, parameters: argparse.Namespace, group=1):
        document = f"network:{self.cloud}"

        opt_dict = vars(self.options)
        parm_dict = vars(parameters)
        combined = dict_merge(opt_dict, parm_dict)

        if group == 1:
            self.net.remove(document)
            self.net.document(document)
            self.meta.document('network')
            self.net.update(combined)
            self.meta[self.cloud] = True

    def create_node_group(self, parameters: argparse.Namespace, group=1):
        document = f"{self.name}:{group:04d}"

        opt_dict = vars(self.options)
        parm_dict = vars(parameters)
        combined = dict_merge(opt_dict, parm_dict)

        if group == 1:
            self.db.clean()
        self.db.document(document)
        self.meta.document('resources')
        self.db.update(combined)
        self.meta[self.name] = self.cloud

        self.create_network(parameters, group)

    def add_to_node_group(self, parameters: argparse.Namespace):
        count = len(self.db.doc_id_startswith(self.name))
        if count == 0:
            raise ValueError(f"attempting to add to empty node group")
        self.create_node_group(parameters, count + 1)

    def get_node_groups(self) -> List[KeyValueStore]:
        self.meta.document('resources')
        for resource in self.meta.keys():
            filename = os.path.join(get_project_dir(self.project), f"{resource}.db")
            db = KeyValueStore(filename)
            doc_list = db.doc_id_startswith(resource)
            yield [KeyValueStore(filename, doc) for doc in doc_list]

    def remove_node_groups(self, name=None):
        self.meta.document('resources')
        for resource in self.meta.keys():
            if name and resource != name:
                continue
            filename = os.path.join(get_project_dir(self.project), f"{resource}.db")
            db = KeyValueStore(filename)
            doc_list = db.doc_id_startswith(resource)
            for doc in doc_list:
                db.remove(doc)
            del self.meta[resource]

    def get_networks(self) -> List[KeyValueStore]:
        doc_list = self.net.doc_id_startswith('network')
        return [KeyValueStore(self.net.file_name, doc) for doc in doc_list]

    def get_network(self, cloud):
        doc_list = self.net.doc_id_startswith('network')
        return next((KeyValueStore(self.net.file_name, doc) for doc in doc_list if doc.endswith(cloud)), None)


class Deployment(object):

    def __init__(self, parameters: Parameters):
        self.parameters = parameters
        self.core, self.deploy_set = self.from_file()

        try:
            FileManager().make_dir(self.parameters.project_dir)
        except Exception as err:
            raise DeploymentError(f"can not create working dir: {err}")

    @property
    def services(self) -> Tuple[str, BaseConfig, Service]:
        for name, service in self.deploy_set.items():
            yield name, self.core, service

    def store_config(self, overwrite: bool = False):
        service = self.parameters.name
        if not self.deploy_set.get(service) or overwrite:
            new_svc = Service(config=[])
            new_svc.from_dict(self.parameters.as_dict)
            self.deploy_set.update({service: new_svc})
        config = NodeConfig().create(self.parameters.as_dict)
        self.deploy_set.get(service).config.append(config)

    def from_file(self):
        deploy_set = {}
        core = BaseConfig()
        config_data = self.read_file("deployment.cfg")

        if config_data.get('core'):
            core.from_dict(config_data.get('core'))

        core.from_dict(self.parameters.as_dict)

        for name, service in config_data.items():
            if name == 'core':
                continue
            new_svc = Service(config=[])
            new_svc.from_dict(service)
            for saved_config in service.get('config'):
                config = NodeConfig().create(saved_config)
                new_svc.config.append(config)
            deploy_set.update({name: new_svc})

        return core, deploy_set

    def to_file(self):
        config_data = {
            'core': self.core.as_dict
        }
        for name, service in self.deploy_set.items():
            # noinspection PyTypeChecker
            config_data.update({name: attr.asdict(service)})
        self.write_file(config_data, "deployment.cfg")

    def read_file(self, name: str):
        cfg_file = os.path.join(self.parameters.project_dir, name)
        try:
            with open(cfg_file, 'r') as cfg_file_h:
                data = json.load(cfg_file_h)
                return data
        except FileNotFoundError:
            return {}
        except Exception as err:
            raise DeploymentError(f"can not read from config file {cfg_file}: {err}")

    def write_file(self, data: dict, name: str):
        cfg_file = os.path.join(self.parameters.project_dir, name)
        try:
            with open(cfg_file, 'w') as cfg_file_h:
                json.dump(data, cfg_file_h, indent=2)
                cfg_file_h.write('\n')
        except Exception as err:
            raise DeploymentError(f"can not write to config file {cfg_file}: {err}")
