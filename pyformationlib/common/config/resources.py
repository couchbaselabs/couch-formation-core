##
##

import attr
from typing import Union
from attr.validators import instance_of as io
from typing import Iterable


@attr.s
class Build(object):
    build = attr.ib(validator=io(dict))

    @classmethod
    def from_config(cls, json_data: dict):
        return cls(
            json_data.get("build"),
            )


@attr.s
class Entry(object):
    versions = attr.ib(validator=io(Iterable))

    @classmethod
    def from_config(cls, distro: str, json_data: dict):
        return cls(
            json_data.get(distro),
            )


@attr.s
class Variable(object):
    variable = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, name: str, value: Union[str, list, dict], description: str):
        if type(value) == list:
            v_type: str = "list(string)"
        elif type(value) == dict:
            v_type: str = "map"
        elif type(value) == bool:
            v_type: str = "bool"
        else:
            v_type: str = "string"
        return cls(
            {name: [
                {
                    "default": value,
                    "description": description,
                    "type": v_type
                }
            ]}
        )

    @property
    def as_dict(self):
        return self.__dict__['variable']


@attr.s
class VariableMap(object):
    variable_block = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, name: str, element: dict):
        entry = {name: element}
        self.variable_block.update(entry)
        return self

    @property
    def as_dict(self):
        return self.__dict__['variable_block']


@attr.s
class ClusterMapElement(object):
    install_mode = attr.ib(validator=io(str))
    node_env = attr.ib(validator=io(str))
    node_number = attr.ib(validator=io(int))
    node_services = attr.ib(validator=io(str))
    node_subnet = attr.ib(validator=io(str))
    node_zone = attr.ib(validator=io(str))
    node_ram = attr.ib(validator=io(str))
    node_swap = attr.ib(validator=io(bool))
    instance_type = attr.ib(validator=io(str))
    root_volume_iops = attr.ib(validator=io(str))
    root_volume_size = attr.ib(validator=io(str))
    root_volume_type = attr.ib(validator=io(str))
    root_volume_tier = attr.ib(validator=attr.validators.optional(io(str)), default=None)
    data_volume_iops = attr.ib(validator=attr.validators.optional(io(str)), default=None)
    data_volume_size = attr.ib(validator=attr.validators.optional(io(str)), default=None)
    data_volume_type = attr.ib(validator=attr.validators.optional(io(str)), default=None)
    data_volume_tier = attr.ib(validator=attr.validators.optional(io(str)), default=None)
    node_gateway = attr.ib(validator=attr.validators.optional(io(str)), default=None)
    node_ip_address = attr.ib(validator=attr.validators.optional(io(str)), default=None)
    node_netmask = attr.ib(validator=attr.validators.optional(io(str)), default=None)

    @classmethod
    def construct(cls,
                  mode: str,
                  env_name: str,
                  number: int,
                  services: str,
                  subnet: str,
                  zone: str,
                  ram_gb: str,
                  node_swap: bool,
                  instance_type: str,
                  root_volume_iops: str,
                  root_volume_size: str,
                  root_volume_type: str,
                  root_volume_tier: Union[str, None] = None,
                  data_volume_iops: Union[str, None] = None,
                  data_volume_size: Union[str, None] = None,
                  data_volume_type: Union[str, None] = None,
                  data_volume_tier: Union[str, None] = None,
                  gateway: Union[str, None] = None,
                  ip_address: Union[str, None] = None,
                  netmask: Union[str, None] = None):
        return cls(
            mode,
            env_name,
            number,
            services,
            subnet,
            zone,
            ram_gb,
            node_swap,
            instance_type,
            root_volume_iops,
            root_volume_size,
            root_volume_type,
            root_volume_tier,
            data_volume_iops,
            data_volume_size,
            data_volume_type,
            data_volume_tier,
            gateway,
            ip_address,
            netmask
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class Variables(object):
    variable = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, variable: dict):
        self.variable.update(variable)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class ResourceBlock(object):
    resource = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, resource: dict):
        self.resource.update(resource)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class NodeBuild(object):
    node_block = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, entry: dict):
        return cls(
            [
                entry
            ]
        )

    def as_name(self, name: str):
        response = {name: self.__dict__['node_block']}
        return response


@attr.s
class ResourceBuild(object):
    resource_block = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, entry: dict):
        return cls(
            [
                entry
            ]
        )

    def as_name(self, name: str):
        response = {name: self.__dict__['resource_block']}
        return response


@attr.s
class Locals(object):
    locals = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, entry: dict):
        return cls(
            [
                entry
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class LocalVar(object):
    local = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, var_name: str, var_value: str):
        self.local.update({var_name: var_value})
        return self

    @property
    def as_dict(self):
        return self.__dict__['local']


@attr.s
class NodeMain(object):
    elements = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, item: dict):
        self.elements.update(item)
        return self

    @property
    def as_dict(self):
        return self.__dict__['elements']


@attr.s
class NullResource(object):
    null_resource = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, element: dict):
        self.null_resource.update(element)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class NullResourceBlock(object):
    resource_block = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, entry: dict):
        return cls(
            [
                entry
            ]
        )

    def as_name(self, name: str):
        response = {name: self.__dict__['resource_block']}
        return response


@attr.s
class NullResourceBody(object):
    elements = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, element: dict):
        self.elements.update(element)
        return self

    @property
    def as_dict(self):
        return self.__dict__['elements']


@attr.s
class Connection(object):
    elements = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, element: dict):
        self.elements.update(element)
        return self

    @property
    def as_dict(self):
        response = {"connection": [self.__dict__['elements']]}
        return response


@attr.s
class ConnectionElements(object):
    host = attr.ib(validator=io(str))
    private_key = attr.ib(validator=io(str))
    type = attr.ib(validator=io(str))
    user = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, host: str, private_key_file: str, user: str):
        return cls(
            f"${{{host}}}",
            f"${{file(var.{private_key_file})}}",
            "ssh",
            f"${{var.{user}}}"
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class DependsOn(object):
    depends_on = attr.ib(validator=io(list))

    @classmethod
    def build(cls):
        return cls(
            []
        )

    def add(self, element: str):
        self.depends_on.append(element)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class ForEach(object):
    for_each = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, element: str):
        return cls(
            element
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class Provisioner(object):
    provisioner = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, element: dict):
        self.provisioner.update(element)
        return self

    @property
    def as_dict(self):
        return self.__dict__

    @property
    def as_contents(self):
        return self.__dict__['provisioner']


@attr.s
class RemoteExec(object):
    elements = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, element: dict):
        self.elements.update(element)
        return self

    @property
    def as_dict(self):
        response = {"remote-exec": [self.__dict__['elements']]}
        return response


@attr.s
class InLine(object):
    inline = attr.ib(validator=io(list))

    @classmethod
    def build(cls):
        return cls(
            []
        )

    def add(self, element: str):
        self.inline.append(element)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class Triggers(object):
    triggers = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, name: str, value: str):
        self.triggers.update({name: value})
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class Output(object):
    output = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, element: dict):
        self.output.update(element)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class OutputValue(object):
    value = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, element: str):
        self.value.update({
            "value": element,
            "sensitive": True
        })
        return self

    def as_name(self, name: str):
        response = {name: [self.__dict__['value']]}
        return response


@attr.s
class TimeSleep(object):
    time_sleep = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, resource_type: str, resource_name: str):
        return cls(
            TimeSleepPause.construct(resource_type, resource_name).as_dict
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class TimeSleepPause(object):
    pause = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, resource_type: str, resource_name: str):
        return cls(
            [
                {
                    "create_duration": "5s",
                    "depends_on": [
                        f"{resource_type}.{resource_name}"
                    ]
                }
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class DataResource(object):
    data = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, element: dict):
        self.data.update(element)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class CapellaServerGroupList(object):
    server_groups = attr.ib(validator=io(list))

    @classmethod
    def build(cls):
        return cls(
            []
        )

    def add(self, element: dict):
        self.server_groups.append(element)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class CapellaServerGroup(object):
    compute = attr.ib(validator=io(str))
    services = attr.ib(validator=io(list))
    size = attr.ib(validator=io(str))
    root_volume_size = attr.ib(validator=io(str))
    root_volume_type = attr.ib(validator=io(str))
    root_volume_iops = attr.ib(validator=attr.validators.optional(io(str)), default=None)

    @classmethod
    def construct(cls,
                  compute: str,
                  services: list,
                  size: int,
                  root_volume_size: str,
                  root_volume_type: str,
                  root_volume_iops: Union[str, None] = None):
        return cls(
            compute,
            services,
            str(size),
            root_volume_size,
            root_volume_type,
            root_volume_iops
        )

    @property
    def as_dict(self):
        return self.__dict__
