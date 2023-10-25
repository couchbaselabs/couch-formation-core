##
##

from typing import List, Optional, Dict
import attr
import yaml
import argparse
import couchformation.constants as C


@attr.s
class Profile:
    driver: str = attr.ib()
    module: str = attr.ib()
    deploy: str = attr.ib()
    destroy: str = attr.ib()
    info: str = attr.ib()


@attr.s
class Parameters:
    options: List[str] = attr.ib()


@attr.s
class CloudProfile:
    name: str = attr.ib()
    network: Profile = attr.ib()
    node: Profile = attr.ib()
    parameters: Parameters = attr.ib()
    options: Optional[argparse.Namespace] = attr.ib(default=None)


@attr.s
class ProfileSet:
    profiles: List[CloudProfile] = attr.ib(default=[])

    def add(self, p: CloudProfile):
        self.profiles.append(p)

    def get(self, cloud):
        return next((p for p in self.profiles if p.name == cloud), None)


@attr.s
class BuildConfig:
    name: str = attr.ib()
    root: bool = attr.ib()
    commands: List[str] = attr.ib()


@attr.s
class BuildSet:
    profiles: List[BuildConfig] = attr.ib(default=[])

    def add(self, p: BuildConfig):
        self.profiles.append(p)

    def get(self, name):
        return next((p for p in self.profiles if p.name == name), None)


@attr.s
class Provisioner:
    name: str = attr.ib()
    driver: str = attr.ib()
    module: str = attr.ib()
    method: str = attr.ib()
    options: List[str] = attr.ib()
    parameters: Dict = attr.ib()


@attr.s
class ProvisionerSet:
    provisioners: List[Provisioner] = attr.ib(default=[])

    def add(self, p: Provisioner):
        self.provisioners.append(p)

    def get(self, name):
        return next((p for p in self.provisioners if p.name == name), None)


class TargetProfile(object):

    def __init__(self, options):
        self.cfg_file = C.TARGET_PROFILES
        self.options = options
        self.config = ProfileSet()
        self.load_config()

    def get(self, cloud) -> CloudProfile:
        profile = self.config.get(cloud)
        if not profile:
            raise ValueError(f"Cloud {cloud} is not supported")
        profile.options = self.initialize_args(self.options, profile.parameters.options)
        return profile

    def load_config(self):
        with open(self.cfg_file, "r") as f:
            try:
                for cloud, settings in yaml.safe_load(f).items():
                    network = Profile(*self.construct_profile(settings, 'network'))
                    node = Profile(*self.construct_profile(settings, 'node'))
                    # parameters = Parameters(*self.construct_profile(settings, 'parameters'))
                    profile = CloudProfile(cloud, network, node, Parameters(settings.get('parameters')))
                    self.config.add(profile)
            except yaml.YAMLError as err:
                RuntimeError(f"Can not open target config file {self.cfg_file}: {err}")

    @staticmethod
    def construct_profile(settings, key):
        config = settings.get(key)
        driver = list(config.keys())[0]
        elements = config.get(driver)
        module = elements.get('module')
        deploy = elements.get('deploy')
        destroy = elements.get('destroy')
        info = elements.get('info')
        return driver, module, deploy, destroy, info

    @staticmethod
    def initialize_args(args, parameters):
        parser = argparse.ArgumentParser(add_help=False)
        for attribute in parameters:
            parser.add_argument(f"--{attribute}", action='store')
        options, undefined = parser.parse_known_args(args)
        return options


class BuildProfile(object):

    def __init__(self):
        self.cfg_file = C.NODE_PROFILES
        self.config = BuildSet()
        self.load_config()

    def get(self, name) -> BuildConfig:
        profile = self.config.get(name)
        if not profile:
            raise ValueError(f"Build type {name} is not supported")
        return profile

    def load_config(self):
        with open(self.cfg_file, "r") as f:
            try:
                for name, settings in yaml.safe_load(f).items():
                    profile = BuildConfig(name, settings.get('root'), settings.get('commands'))
                    self.config.add(profile)
            except yaml.YAMLError as err:
                RuntimeError(f"Can not open node config file {self.cfg_file}: {err}")


class ProvisionerProfile(object):

    def __init__(self):
        self.cfg_file = C.PROVISIONER_PROFILES
        self.config = ProvisionerSet()
        self.load_config()

    def get(self, name, *args) -> Provisioner:
        profile = self.config.get(name)
        if not profile:
            raise ValueError(f"Provisioner type {name} is not supported")
        profile.parameters = self.initialize_parameters(profile.options, args)
        return profile

    def load_config(self):
        with open(self.cfg_file, "r") as f:
            try:
                for name, settings in yaml.safe_load(f).items():
                    provisioner = Provisioner(*self.construct_profile(name, settings))
                    self.config.add(provisioner)
            except yaml.YAMLError as err:
                RuntimeError(f"Can not open provisioner config file {self.cfg_file}: {err}")

    @staticmethod
    def construct_profile(name, settings):
        driver = settings.get('driver')
        module = settings.get('module')
        method = settings.get('method')
        options = settings.get('parameters')
        parameters = {}
        return name, driver, module, method, options, parameters

    @staticmethod
    def initialize_parameters(expected, args):
        p = {}
        for d in args:
            for attribute in expected:
                if p.get(attribute):
                    continue
                if d.get(attribute):
                    p[attribute] = d.get(attribute)
        return p
