##
##

from typing import List
import attr
import yaml
import couchformation.constants as C


@attr.s
class Profile:
    driver: str = attr.ib()
    module: str = attr.ib()
    deploy: str = attr.ib()
    destroy: str = attr.ib()
    parameters: List[str] = attr.ib()


@attr.s
class CloudProfile:
    name: str = attr.ib()
    network: Profile = attr.ib()
    node: Profile = attr.ib()


@attr.s
class ProfileSet:
    profiles: List[CloudProfile] = attr.ib(default=[])

    def add(self, p: CloudProfile):
        self.profiles.append(p)

    def get(self, cloud):
        return next((p for p in self.profiles if p.name == cloud), None)


class TargetProfile(object):

    def __init__(self):
        self.cfg_file = C.TARGET_PROFILES
        self.config = ProfileSet()
        self.load_config()

    def load_config(self):
        with open(self.cfg_file, "r") as f:
            try:
                for cloud, settings in yaml.safe_load(f).items():
                    network = Profile(*self.construct_profile(settings, 'network'))
                    node = Profile(*self.construct_profile(settings, 'node'))
                    profile = CloudProfile(cloud, network, node)
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
        parameters = elements.get('parameters')
        return driver, module, deploy, destroy, parameters
