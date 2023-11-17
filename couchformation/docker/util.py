##
##

from typing import List, Optional, Union
import attr
import yaml
import couchformation.constants as C


@attr.s
class VolumeSpec:
    v_type: str = attr.ib()
    directory: str = attr.ib()
    size: Optional[int] = attr.ib()
    run: Optional[str] = attr.ib()
    command: Optional[str] = attr.ib()


@attr.s
class ContainerSpec:
    name: str = attr.ib()
    volume: Optional[VolumeSpec] = attr.ib(default=None)
    ports: Optional[str] = attr.ib(default="80,443")

    def add_volume(self, v_type: str, directory: str, size: Union[int, None] = None, run: Union[str, None] = None, command: Union[str, None] = None):
        self.volume = VolumeSpec(v_type, directory, size, run, command)

    def add_ports(self, ports: str):
        self.ports = ports


@attr.s
class ContainerSet:
    profiles: List[ContainerSpec] = attr.ib(default=[])

    def add(self, p: ContainerSpec):
        self.profiles.append(p)

    def get(self, image):
        return next((p for p in self.profiles if p.name == image), None)


class ContainerProfile(object):

    def __init__(self):
        self.cfg_file = C.CONTAINER_PROFILES
        self.config = ContainerSet()
        self.load_config()

    def get(self, image) -> Union[ContainerSpec, None]:
        profile = self.config.get(image)
        if not profile:
            return None
        return profile

    def load_config(self):
        with open(self.cfg_file, "r") as f:
            try:
                for image, settings in yaml.safe_load(f).items():
                    profile = ContainerSpec(image)
                    if settings.get('ports'):
                        profile.add_ports(settings.get('ports'))
                    if settings.get('volume'):
                        vol_spec = settings.get('volume')
                        profile.add_volume(vol_spec.get('type'), vol_spec.get('directory'), vol_spec.get('size'), vol_spec.get('run'), vol_spec.get('command'))
                    self.config.add(profile)
            except yaml.YAMLError as err:
                RuntimeError(f"Can not open target config file {self.cfg_file}: {err}")
