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
class AWSTerraformProvider(object):
    aws = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, source: str):
        return cls(
            {"source": source}
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AWSInstance(object):
    aws_instance = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, resource: dict):
        self.aws_instance.update(resource)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class BlockDevice(object):
    elements = attr.ib(validator=io(list))

    @classmethod
    def build(cls):
        return cls(
            []
        )

    def add(self, element: dict):
        self.elements.append(element)
        return self

    @property
    def as_dict(self):
        response = self.__dict__['elements']
        return response


@attr.s
class EbsElements(object):
    device_name = attr.ib(validator=io(str))
    iops = attr.ib(validator=io(str))
    volume_size = attr.ib(validator=io(str))
    volume_type = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, device: str, iops: str, size: str, vol_type: str):
        return cls(
            device,
            iops,
            size,
            vol_type
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class RootElements(object):
    iops = attr.ib(validator=io(str))
    volume_size = attr.ib(validator=io(str))
    volume_type = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, iops: str, size: str, vol_type: str):
        return cls(
            iops,
            size,
            vol_type
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class NodeConfiguration(object):
    ami = attr.ib(validator=io(str))
    availability_zone = attr.ib(validator=io(str))
    instance_type = attr.ib(validator=io(str))
    key_name = attr.ib(validator=io(str))
    root_block_device = attr.ib(validator=io(list))
    subnet_id = attr.ib(validator=io(str))
    vpc_security_group_ids = attr.ib(validator=io(list))
    tags = attr.ib(validator=io(dict))
    ebs_block_device = attr.ib(validator=attr.validators.optional(io(list)), default=None)

    @classmethod
    def construct(cls,
                  name: str,
                  ami_id: str,
                  zone: str,
                  machine_type: str,
                  key_pair: str,
                  root: dict,
                  subnet: str,
                  sec_group: str,
                  services,
                  disks: list):
        return cls(
            ami_id,
            zone,
            machine_type,
            key_pair,
            [root],
            subnet,
            [sec_group],
            {
                "Name": name,
                "Services": services
            },
            disks
        )

    @property
    def as_dict(self):
        block = {k: v for k, v in self.__dict__.items() if v is not None}
        return block


@attr.s
class SSHResource(object):
    aws_key_pair = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, key_name: str, public_key: str):
        return cls(
            SSH.construct(key_name, public_key).as_dict
            )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class SSH(object):
    cf_ssh_key = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, key_name: str, public_key: str):
        return cls(
            [
                SSHEntry.construct(key_name, public_key).as_dict
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class SSHEntry(object):
    key_name = attr.ib(validator=io(str))
    public_key = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, key_name: str, public_key: str):
        return cls(
            key_name,
            public_key
        )

    @property
    def as_dict(self):
        return self.__dict__
