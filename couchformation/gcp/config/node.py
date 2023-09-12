##
##

import attr
from attr.validators import instance_of as io


@attr.s
class TerraformElement(object):
    terraform = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, element: dict):
        return cls(
            [
                element
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class RequiredProvider(object):
    required_providers = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, element: dict):
        return cls(
           [
                element
           ]
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class GCPTerraformProvider(object):
    google = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, source: str):
        return cls(
            {"source": source}
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class GCPInstance(object):
    google_compute_instance = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, resource: dict):
        self.google_compute_instance.update(resource)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AttachedDisk(object):
    attached_disk = attr.ib(validator=io(list))

    @classmethod
    def build(cls):
        return cls(
            []
        )

    def add(self, name: str):
        self.attached_disk.append({"source": f"${{google_compute_disk.{name}.self_link}}"})
        return self

    @property
    def as_dict(self):
        return self.__dict__['attached_disk']


@attr.s
class BootDisk(object):
    boot_disk = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, params: dict):
        return cls(
            [
                params
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__['boot_disk']


@attr.s
class InitParams(object):
    initialize_params = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, image_project: str, image_name: str, size: str, vol_type: str):
        return cls(
           [
               {
                   "image": f"{image_project}/{image_name}",
                   "size": size,
                   "type": vol_type
               }
           ]
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class Metadata(object):
    metadata = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, user: str, ssh_key: str, services: str):
        return cls(
            {
                "ssh-keys": f"{user}:{ssh_key}",
                "services": services
            }
        )

    @property
    def as_dict(self):
        return self.__dict__['metadata']


@attr.s
class NetworkInterface(object):
    network_interface = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, subnet: str, project: str):
        return cls(
            [
                {
                    "access_config": [
                        {}
                    ],
                    "subnetwork": subnet,
                    "subnetwork_project": project
                }
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__['network_interface']


@attr.s
class ServiceAccount(object):
    service_account = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, email: str):
        return cls(
            [
                {
                    "email": email,
                    "scopes": [
                        "cloud-platform"
                    ]
                }
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__['service_account']


@attr.s
class ImageData(object):
    google_compute_image = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, image: str, project: str):
        return cls(
            {"cb_image": [
                {
                    "name": image,
                    "project": project
                }
            ]}
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class GCPProviderBlock(object):
    provider = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, auth_file: str, gcp_project: str, region: str):
        return cls(
            {"google": [
                {
                    "credentials": auth_file,
                    "project": gcp_project,
                    "region": region
                }
            ]}
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class GCPDiskBuild(object):
    disk_block = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, entry: dict):
        return cls(
            [
                entry
            ]
        )

    def as_name(self, name: str):
        response = {name: self.__dict__['disk_block']}
        return response


@attr.s
class GCPDiskConfiguration(object):
    name = attr.ib(validator=io(str))
    project = attr.ib(validator=io(str))
    size = attr.ib(validator=io(str))
    type = attr.ib(validator=io(str))
    zone = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, name: str, description: str, project: str, size: str, vol_type: str, zone: str):
        return cls(
            f"{name}-{description}",
            project,
            size,
            vol_type,
            zone
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class GCPDisk(object):
    google_compute_disk = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, resource: dict):
        self.google_compute_disk.update(resource)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class NodeConfiguration(object):
    boot_disk = attr.ib(validator=io(list))
    machine_type = attr.ib(validator=io(str))
    metadata = attr.ib(validator=io(dict))
    name = attr.ib(validator=io(str))
    network_interface = attr.ib(validator=io(list))
    project = attr.ib(validator=io(str))
    service_account = attr.ib(validator=io(list))
    zone = attr.ib(validator=io(str))
    attached_disk = attr.ib(validator=io(list))

    @classmethod
    def construct(cls,
                  name: str,
                  image_project: str,
                  image_name: str,
                  root_size: str,
                  root_type: str,
                  machine_type: str,
                  user: str,
                  ssh_key: str,
                  subnet: str,
                  gcp_project: str,
                  email: str,
                  zone: str,
                  services: str,
                  attached_disk: list):
        return cls(
            BootDisk.construct(InitParams.construct(image_project, image_name, root_size, root_type).as_dict).as_dict,
            machine_type,
            Metadata.construct(user, ssh_key, services).as_dict,
            name,
            NetworkInterface.construct(subnet, gcp_project).as_dict,
            gcp_project,
            ServiceAccount.construct(email).as_dict,
            zone,
            attached_disk
        )

    @property
    def as_dict(self):
        block = {k: v for k, v in self.__dict__.items() if v is not None}
        return block
