##
##

import logging
import attr
import os
import json
import argparse
import yaml
import couchformation.constants as C
from typing import Optional, List, Tuple, Union, Any
from enum import Enum
from couchformation.exception import FatalError
from couchformation.config import BaseConfig, NodeConfig, Parameters, AuthMode, get_project_dir
from couchformation.util import FileManager, dict_merge, dict_merge_not_none
from couchformation.kvdb import KeyValueStore
from couchformation.util import PasswordUtility, UUIDGen

DEPLOYMENT = "deployment.db"
logger = logging.getLogger('couchformation.deployment')
logger.addHandler(logging.NullHandler())


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


@attr.s
class BuildParameter:
    name: Optional[str] = attr.ib()
    type: Optional[str] = attr.ib(default="string")
    allowed_values: Optional[List[str]] = attr.ib(default=[])
    required_values: Optional[List[str]] = attr.ib(default=[])


@attr.s
class Build:
    name: Optional[str] = attr.ib()
    parameters: Optional[List[BuildParameter]] = attr.ib(default=[])
    supports: Optional[List[str]] = attr.ib(default=[])


@attr.s
class BuildList:
    build_list: List[Build] = attr.ib(default=[])

    def add(self, build: Build):
        self.build_list.append(build)

    def get(self, name: str) -> Union[Build, None]:
        for build in self.build_list:
            if build.name == name:
                return build
        return None


class MetadataManager(object):

    def __init__(self, project: str):
        self.project = project
        self.project_dir = get_project_dir(project)
        self.metadata = os.path.join(self.project_dir, C.METADATA)
        self.network = os.path.join(self.project_dir, C.NETWORK)

    @property
    def project_uid(self):
        meta = KeyValueStore(self.metadata)
        meta.document('config')
        return meta.get('project_uid')

    @property
    def exists(self):
        return os.path.exists(self.metadata)

    def list_services(self):
        if not self.exists:
            return ()
        meta = KeyValueStore(self.metadata)
        meta.document('resources')
        for resource in meta.keys():
            if not resource:
                continue
            yield resource, meta[resource]

    def get_service_groups(self, service: str) -> List[KeyValueStore]:
        filename = os.path.join(self.project_dir, f"{service}.db")
        db = KeyValueStore(filename)
        doc_list = db.doc_id_startswith(service)
        return [KeyValueStore(filename, doc) for doc in doc_list]

    def copy_project(self, target: str):
        target_dir = get_project_dir(target)

        if not self.exists:
            raise DeploymentError(f"Project {self.project} does not exist")

        target_metadata = os.path.join(target_dir, C.METADATA)
        target_network = os.path.join(target_dir, C.NETWORK)
        try:
            FileManager().make_dir(target_dir)
            FileManager().copy_file(self.metadata, target_metadata)
            FileManager().copy_file(self.network, target_network)
            db = KeyValueStore(target_network)
            doc_list = db.doc_id_startswith('network')
            for doc in doc_list:
                net = KeyValueStore(db.file_name, doc)
                net['project'] = target
        except Exception as err:
            raise DeploymentError(f"can not create target project dir: {err}")

        for service, cloud in self.list_services():
            filename = f"{service}.db"
            source_filename = os.path.join(self.project_dir, filename)
            target_filename = os.path.join(target_dir, filename)
            FileManager().copy_file(source_filename, target_filename)
            db = KeyValueStore(target_filename)
            doc_list = db.doc_id_startswith(service)
            for doc in doc_list:
                resource = KeyValueStore(db.file_name, doc)
                resource['project'] = target

    def print_services(self):
        log = logging.getLogger('minimum_output')
        cloud_map = {}
        log.info(f"\n<{self.project}>")
        for service, cloud in self.list_services():
            cloud_map.setdefault(cloud, []).append(service)
        for cloud in cloud_map.keys():
            log.info(f"[{cloud}]")
            for service in cloud_map[cloud]:
                log.info(f"+- [{service}]")
                for n, group in enumerate(self.get_service_groups(service)):
                    build = group['build'] if 'build' in group and group['build'] is not None else ''
                    region = group['region'] if 'region' in group and group['region'] is not None else ''
                    os_id = group['os_id'] if 'os_id' in group and group['os_id'] is not None else ''
                    machine_type = group['machine_type'] if 'machine_type' in group and group['machine_type'] is not None else ''
                    quantity = group['quantity'] if 'quantity' in group and group['quantity'] is not None else 1
                    log.info(f"| +- [{n+1}] ({build}) {quantity}x {os_id} {machine_type} {region}")

    def print_cli(self, options: argparse.Namespace):
        log = logging.getLogger('minimum_output')
        cloud_map = {}
        for service, cloud in self.list_services():
            cloud_map.setdefault(cloud, []).append(service)
        for cloud in cloud_map.keys():
            for service in cloud_map[cloud]:
                log.info(f"[{service}]")
                for n, group in enumerate(self.get_service_groups(service)):
                    command = "create" if n == 0 else "add"
                    out_line = f"cloudmgr {command} "
                    for attribute in vars(options):
                        if attribute == 'command' or attribute == 'group' or attribute == 'provisioner':
                            continue
                        if group.get(attribute):
                            out_line += f"--{attribute} {group[attribute]} "
                    for parameter in group:
                        if parameter not in vars(options) and group[parameter] is not None:
                            out_line += f"--{parameter} {group[parameter]} "
                    log.info(out_line)

    def print_project(self, options: argparse.Namespace, name: str = None):
        log = logging.getLogger('minimum_output')
        cloud_map = {}
        for service, cloud in self.list_services():
            cloud_map.setdefault(cloud, []).append(service)
        for cloud in cloud_map.keys():
            for service in cloud_map[cloud]:
                if name and service != name:
                    continue
                log.info(f"\n<Service: {service}>")
                for n, group in enumerate(self.get_service_groups(service)):
                    if n == 0:
                        log.info(f"Cloud: {group.get('cloud')}")
                        log.info(f"Build: {group.get('build')}")
                    log.info(f"[{service}] Group: {n+1}")
                    for key, value in group.items():
                        if key not in vars(options):
                            continue
                        if value is not None:
                            log.info(f"{key:<14}: {value}")

    def edit_service(self, name: str, group: int, options: argparse.Namespace):
        if len([attribute for attribute in vars(options) if getattr(options, attribute) is not None]) == 0:
            raise DeploymentError(f"No parameters to edit for service {name}")
        cloud_map = {}
        for service, cloud in self.list_services():
            cloud_map.setdefault(cloud, []).append(service)
        for cloud in cloud_map.keys():
            for service in cloud_map[cloud]:
                if service != name:
                    continue
                filename = f"{service}.db"
                service_filename = os.path.join(self.project_dir, filename)
                db = KeyValueStore(service_filename)
                document = f"{service}:{group:04d}"
                db.document(document)
                for attribute in vars(options):
                    if getattr(options, attribute) is None:
                        continue
                    logger.info(f"Setting parameter {attribute} to \"{getattr(options, attribute)}\"")
                    db[attribute] = getattr(options, attribute)
        self.print_project(options, name)


class BuildManager(object):

    def __init__(self, options: argparse.Namespace, parameters: List[str]):
        self.cfg_file = C.BUILD_PROFILES
        self.options = options
        self.parameters = parameters
        self.create_mode = self.options.command == "create"
        self.build_list = BuildList()
        self.load_config()

    def load_config(self):
        with open(self.cfg_file, "r") as f:
            try:
                for build, settings in yaml.safe_load(f).items():
                    p_list = []
                    for parameter in settings.get('parameters', []):
                        for key, value in parameter.items():
                            p_list.append(BuildParameter(key, value.get('type'), value.get('allowed_values'), value.get('required_values')))
                    build = Build(build, p_list, settings.get('supports', []))
                    self.build_list.add(build)
            except yaml.YAMLError as err:
                raise RuntimeError(f"Can not open build config file {self.cfg_file}: {err}")

    def validate(self):
        build = self.build_list.get(self.options.build)
        if not build:
            return None
        self.validate_base()
        self.validate_command(build)
        self.validate_parameters(build)

    def validate_base(self):
        project = self.options.project
        name = self.options.name
        services = [service for service, cloud in MetadataManager(project).list_services()]
        if name in services and self.create_mode:
            logger.warning(f"Overwriting previously configured service {name}")

    def validate_command(self, build: Build):
        command = self.options.command
        if command not in build.supports:
            raise DeploymentError(f"Command {command} not allowed with build type {build.name}")

    def validate_parameters(self, build: Build):
        for parameter in build.parameters:
            if not self.parameter_check(parameter):
                raise DeploymentError(f"--{parameter.name} value is not valid")

    def parameter_check(self, parameter: BuildParameter):
        parser = argparse.ArgumentParser(add_help=False)
        if parameter.type == "boolean":
            parser.add_argument(f"--{parameter.name}", action='store_true')
        else:
            parser.add_argument(f"--{parameter.name}", action='store')
        options, undefined = parser.parse_known_args(self.parameters)
        result = getattr(options, parameter.name)
        if result:
            return self.value_check(parameter.type, result, parameter.allowed_values, parameter.required_values)
        return True

    def value_check(self, v_type: str, v_value: Any, v_allowed: List[str], v_required: List[str]):
        if v_type == "boolean":
            return isinstance(v_value, bool)
        elif v_type == "integer":
            try:
                int(v_value)
            except ValueError:
                return False
        elif v_type == "float":
            try:
                float(v_value)
            except ValueError:
                return False
        elif v_type == "string":
            pass
        elif v_type == "csv":
            if not isinstance(v_value, str) or not all(val in v_allowed for val in v_value.split(',')):
                logger.warning(f"Invalid comma separated list: allowed values: {','.join(v_allowed)}")
                return False
            if self.create_mode and not any(val in v_required for val in v_value.split(',')):
                logger.warning(f"Invalid comma separated list: required values: {','.join(v_required)}")
                return False
        elif v_type == "path":
            if not os.path.exists(v_value):
                logger.warning(f"Path does not exist: {v_value}")
                return False
        return True


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
        credentials = os.path.join(self.project_dir, C.CREDENTIALS)
        self.db = KeyValueStore(filename)
        self.net = KeyValueStore(network)
        self.meta = KeyValueStore(metadata)
        self.credentials = KeyValueStore(credentials)

        self.meta.document('config')
        if not self.meta['project_uid']:
            self.project_uid = UUIDGen().get_project_uid(self.project)
            self.meta['project_uid'] = self.project_uid
        else:
            self.project_uid = self.meta['project_uid']

    def create_network(self, parameters: argparse.Namespace, region, group=1):
        document = f"network:{self.cloud}:{region}"
        self.net.document(document)

        opt_dict = vars(self.options)
        parm_dict = vars(parameters)
        opt_merge = dict_merge(opt_dict, parm_dict)
        combined = dict_merge_not_none(self.net.as_dict, opt_merge)

        if group == 1:
            self.meta.document('network')
            self.net.update(combined)
            self.meta[self.cloud] = True

    def create_credentials(self):
        document = f"credentials:{self.project}"

        self.credentials.document(document)
        if not self.credentials.get('password'):
            password = PasswordUtility().generate(16)
            self.credentials['password'] = password

        return self.credentials.get('password')

    def remove_credentials(self):
        document = f"credentials:{self.project}"
        self.credentials.remove(document)

    def create_node_group(self, parameters: argparse.Namespace, group=1):
        document = f"{self.name}:{group:04d}"
        region = parameters.region if 'region' in parameters else "local"

        if not self.name:
            raise DeploymentError(f"name is required")

        opt_dict = vars(self.options)
        parm_dict = vars(parameters)
        combined = dict_merge(opt_dict, parm_dict)

        if group == 1:
            self.db.clean()
        self.db.document(document)
        self.meta.document('resources')
        self.db.update(combined)
        self.meta[self.name] = self.cloud

        self.create_network(parameters, region, group)

    def get_credentials(self):
        document = f"credentials:{self.project}"
        self.credentials.document(document)
        return self.credentials.get('password')

    def add_to_node_group(self, parameters: argparse.Namespace):
        count = len(self.db.doc_id_startswith(self.name))
        if count == 0:
            raise ValueError(f"attempting to add to empty node group")
        self.create_node_group(parameters, count + 1)

    def get_node_groups(self) -> List[KeyValueStore]:
        self.meta.document('resources')
        for resource in self.meta.keys():
            if not resource:
                continue
            filename = os.path.join(get_project_dir(self.project), f"{resource}.db")
            db = KeyValueStore(filename)
            doc_list = db.doc_id_startswith(resource)
            yield [KeyValueStore(filename, doc) for doc in doc_list]

    def remove_node_groups(self, name=None):
        self.meta.document('resources')
        for resource in self.meta.keys():
            if name and resource != name:
                continue
            if not resource:
                continue
            filename = os.path.join(get_project_dir(self.project), f"{resource}.db")
            db = KeyValueStore(filename)
            doc_list = db.doc_id_startswith(resource)
            for doc in doc_list:
                db.remove(doc)
            del self.meta[resource]

    def clean_node_groups(self, name=None):
        self.meta.document('resources')
        for resource in self.meta.keys():
            if name and resource != name:
                continue
            filename = os.path.join(get_project_dir(self.project), f"{resource}.db")
            logger.info(f"Removing {resource} database")
            os.remove(filename)

    def clean_base(self):
        logger.info("Removing project core databases")
        network = os.path.join(self.project_dir, C.NETWORK)
        os.remove(network)
        metadata = os.path.join(self.project_dir, C.METADATA)
        os.remove(metadata)

    def get_networks(self) -> List[KeyValueStore]:
        doc_list = self.net.doc_id_startswith('network')
        return [KeyValueStore(self.net.file_name, doc) for doc in doc_list]

    def get_network(self, cloud, region):
        doc_list = self.net.doc_id_startswith('network')
        return next((KeyValueStore(self.net.file_name, doc) for doc in doc_list if doc.endswith(f"{cloud}:{region}")), None)


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
