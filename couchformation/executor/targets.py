##
##

from typing import List, Optional, Dict
from enum import Enum
import attr
import yaml
import argparse
import couchformation.constants as C


class DeployMode(Enum):
    node = 'node'
    saas = 'saas'


@attr.s
class Profile:
    driver: str = attr.ib()
    module: str = attr.ib()
    deploy: str = attr.ib()
    destroy: str = attr.ib()
    info: str = attr.ib()
    compose: str = attr.ib()


@attr.s
class Parameters:
    options: List[str] = attr.ib()
    required: Optional[List[str]] = attr.ib(default=[])
    boolean: Optional[List[str]] = attr.ib(default=[])


@attr.s
class CloudDriverBase:
    driver: str = attr.ib()
    module: str = attr.ib()
    test: str = attr.ib()


@attr.s
class CloudProfile:
    name: str = attr.ib()
    base: CloudDriverBase = attr.ib()
    network: Profile = attr.ib()
    node: Profile = attr.ib()
    parameters: Parameters = attr.ib()
    options: Optional[argparse.Namespace] = attr.ib(default=argparse.Namespace())
    undefined: Optional[List[str]] = attr.ib(default=[])
    parser: Optional[argparse.ArgumentParser] = attr.ib(default=argparse.ArgumentParser(add_help=False))

    def check_required_options(self):
        missing = []
        for opt in self.parameters.required:
            if opt not in self.options or getattr(self.options, opt) is None:
                missing.append(opt)
        return missing

    def check_undefined_options(self):
        return self.undefined

    def get_options(self):
        return self.options


@attr.s
class ProfileSet:
    profiles: List[CloudProfile] = attr.ib(default=[])

    def add(self, p: CloudProfile):
        self.profiles.append(p)

    def get(self, cloud):
        return next((p for p in self.profiles if p.name == cloud), None)


@attr.s
class BuildConfig:
    provisioner: str = attr.ib()
    root: bool = attr.ib()
    commands: List[str] = attr.ib()
    exclude: Optional[List[str]] = attr.ib(default=[])


@attr.s
class BuildConfigSequence:
    name: str = attr.ib()
    sequence: List[BuildConfig] = attr.ib(default=[])

    def add(self, b: BuildConfig):
        self.sequence.append(b)

    def get(self, provisioner) -> List[BuildConfig]:
        return list(s for s in self.sequence if s.provisioner == provisioner)


@attr.s
class BuildSet:
    profiles: List[BuildConfigSequence] = attr.ib(default=[])

    def add(self, p: BuildConfigSequence):
        self.profiles.append(p)

    def get(self, name):
        return next((p for p in self.profiles if p.name == name), None)


@attr.s
class Provisioner:
    name: str = attr.ib()
    driver: str = attr.ib()
    module: str = attr.ib()
    method: str = attr.ib()
    upload: str = attr.ib()
    when: str = attr.ib()
    options: List[str] = attr.ib()
    parameters: Dict = attr.ib()

    def parameter_gen(self, *args):
        parameters = self.initialize_parameters(self.options, args)
        return parameters

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


@attr.s
class ProvisionerSet:
    provisioners: List[Provisioner] = attr.ib(default=[])

    def add(self, p: Provisioner):
        self.provisioners.append(p)

    def get(self, name):
        return next((p for p in self.provisioners if p.name == name), None)


@attr.s
class Strategy:
    name: str = attr.ib()
    deployer: str = attr.ib()


@attr.s
class StrategySet:
    strategies: List[Strategy] = attr.ib(default=[])

    def add(self, s: Strategy):
        self.strategies.append(s)

    def get(self, name):
        return next((p for p in self.strategies if p.name == name), None)


##
@attr.s
class CloudType:
    cloud: str = attr.ib()
    provisioner: str = attr.ib()


@attr.s
class CloudTypeSet:
    clouds: List[CloudType] = attr.ib(default=[])

    def add(self, c: CloudType):
        self.clouds.append(c)

    def get(self, name):
        return next((c for c in self.clouds if c.cloud == name), None)


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
        profile.options, profile.undefined, profile.parser = self.initialize_args(self.options, profile.parameters.options)
        return profile

    def load_config(self):
        with open(self.cfg_file, "r") as f:
            try:
                for cloud, settings in yaml.safe_load(f).items():
                    base = CloudDriverBase(*self.construct_driver(settings, 'base'))
                    network = Profile(*self.construct_profile(settings, 'network'))
                    node = Profile(*self.construct_profile(settings, 'node'))
                    profile = CloudProfile(cloud, base, network, node, Parameters(settings.get('parameters'), settings.get('required', []), settings.get('boolean', [])))
                    self.config.add(profile)
            except yaml.YAMLError as err:
                raise RuntimeError(f"Can not open target config file {self.cfg_file}: {err}")

    @staticmethod
    def construct_profile(settings, key):
        config = settings.get(key)
        driver = list(config.keys())[0]
        elements = config.get(driver)
        module = elements.get('module')
        deploy = elements.get('deploy')
        destroy = elements.get('destroy')
        info = elements.get('info')
        compose = elements.get('compose')
        return driver, module, deploy, destroy, info, compose

    @staticmethod
    def construct_driver(settings, key):
        config = settings.get(key)
        driver = list(config.keys())[0]
        elements = config.get(driver)
        module = elements.get('module')
        test = elements.get('test')
        return driver, module, test

    @staticmethod
    def initialize_args(args, parameters):
        opt_struct = C.get_option_struct()
        parser = argparse.ArgumentParser(add_help=False)
        for attribute in parameters:
            opt_settings = opt_struct.get(attribute)
            if eval(opt_settings.type) is bool:
                parser.add_argument(f"--{attribute}", action='store_true', help=opt_settings.help)
            else:
                parser.add_argument(f"--{attribute}", action='store', type=eval(opt_settings.type), help=opt_settings.help)
        options, undefined = parser.parse_known_args(args)
        return options, undefined, parser


class BuildProfile(object):

    def __init__(self):
        self.cfg_file = C.NODE_PROFILES
        self.config = BuildSet()
        self.load_config()

    def get(self, name) -> BuildConfigSequence:
        sequence = self.config.get(name)
        if not sequence:
            return BuildConfigSequence(name, [])
        return sequence

    def load_config(self):
        with open(self.cfg_file, "r") as f:
            try:
                for name, settings in yaml.safe_load(f).items():
                    sequence = BuildConfigSequence(name, [])
                    for element in settings:
                        profile = BuildConfig(element.get('provisioner'), element.get('root'),
                                              element.get('commands'), element.get('exclude', []))
                        sequence.add(profile)
                    self.config.add(sequence)
            except yaml.YAMLError as err:
                raise RuntimeError(f"Can not open node config file {self.cfg_file}: {err}")


class ProvisionerProfile(object):

    def __init__(self):
        self.cfg_file = C.PROVISIONER_PROFILES
        self.config = ProvisionerSet()
        self.load_config()

    def get(self, name) -> Provisioner:
        profile = self.config.get(name)
        if not profile:
            raise ValueError(f"Provisioner type {name} is not supported")
        return profile

    @staticmethod
    def run(parameters, expression):
        for key, val in parameters.items():
            exec(key + '=val')
        try:
            return eval(expression)
        except NameError:
            return False

    def search(self, parameters):
        for provisioner in self.config.provisioners:
            expression = provisioner.when
            if self.run(parameters, expression):
                return provisioner.name
        return None

    def load_config(self):
        with open(self.cfg_file, "r") as f:
            try:
                for name, settings in yaml.safe_load(f).items():
                    provisioner = Provisioner(*self.construct_profile(name, settings))
                    self.config.add(provisioner)
            except yaml.YAMLError as err:
                raise RuntimeError(f"Can not open provisioner config file {self.cfg_file}: {err}")

    @staticmethod
    def construct_profile(name, settings):
        driver = settings.get('driver')
        module = settings.get('module')
        method = settings.get('method')
        upload = settings.get('upload')
        when = settings.get('when')
        options = settings.get('parameters')
        parameters = {}
        return name, driver, module, method, upload, when, options, parameters


class DeployStrategy(object):

    def __init__(self):
        self.cfg_file = C.STRATEGY_PROFILES
        self.config = StrategySet()
        self.load_config()

    def get(self, name) -> Strategy:
        strategy = self.config.get(name)
        if not strategy:
            raise ValueError(f"Strategy type {name} is not supported")
        return strategy

    def load_config(self):
        with open(self.cfg_file, "r") as f:
            try:
                for name, settings in yaml.safe_load(f).items():
                    strategy = Strategy(*self.construct_strategy(name, settings))
                    self.config.add(strategy)
            except yaml.YAMLError as err:
                raise RuntimeError(f"Can not open strategy config file {self.cfg_file}: {err}")

    @staticmethod
    def construct_strategy(name, settings):
        deployer = settings.get('deployer')
        return name, deployer


class CloudConfig(object):

    def __init__(self):
        self.cfg_file = C.CLOUD_PROFILES
        self.config = CloudTypeSet()
        self.load_config()

    def get(self, name) -> CloudType:
        cloud = self.config.get(name)
        if not cloud:
            raise ValueError(f"Cloud type {name} is not supported")
        return cloud

    def load_config(self):
        with open(self.cfg_file, "r") as f:
            try:
                for name, settings in yaml.safe_load(f).items():
                    cloud = CloudType(*self.construct_strategy(name, settings))
                    self.config.add(cloud)
            except yaml.YAMLError as err:
                raise RuntimeError(f"Can not open strategy config file {self.cfg_file}: {err}")

    @staticmethod
    def construct_strategy(name, settings):
        provisioner = settings.get('provisioner')
        return name, provisioner
