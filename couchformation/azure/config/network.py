##

import attr
from attr.validators import instance_of as io


@attr.s
class AzureProvider(object):
    provider = attr.ib(validator=io(dict))

    @classmethod
    def for_region(cls):
        entry = {
            "features": [{}]
        }
        return cls(
            {"azurerm": [entry]},
            )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class Resources(object):
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
class Variable(object):
    variable = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, name: str, value: str, description: str, v_type: str):
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
class VPCConfig(object):
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
class RGElements(object):
    location = attr.ib(validator=io(str))
    name = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, region: str, name: str):
        return cls(
            region,
            name
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class ResourceGroup(object):
    cf_rg = attr.ib(validator=io(list))

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
class RGResource(object):
    azurerm_resource_group = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, region: str, name: str):
        return cls(
            ResourceGroup.construct(RGElements.construct(region, name).as_dict).as_dict
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class VNetEntry(object):
    cf_vpc = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, cidr: str, name: str, subnet_cidr: str):
        return cls(
            [
               VNetElements.construct(cidr, name, subnet_cidr).as_dict
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class Subnet(object):
    id = attr.ib(validator=io(type(None)))
    address_prefix = attr.ib(validator=io(str))
    name = attr.ib(validator=io(str))
    security_group = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, subnet_cidr: str, vpc_name: str):
        return cls(
            None,
            subnet_cidr,
            f"{vpc_name}-subnet-1",
            "${azurerm_network_security_group.cf_nsg.id}"
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class VNetElements(object):
    address_space = attr.ib(validator=io(list))
    location = attr.ib(validator=io(str))
    name = attr.ib(validator=io(str))
    resource_group_name = attr.ib(validator=io(str))
    subnet = attr.ib(validator=io(list))
    tags = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, cidr: str, name: str, subnet_cidr: str):
        return cls(
            [cidr],
            "${azurerm_resource_group.cf_rg.location}",
            name,
            "${azurerm_resource_group.cf_rg.name}",
            [Subnet.construct(subnet_cidr, name).as_dict],
            {"name": name}
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class VNetResource(object):
    azurerm_virtual_network = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, cidr: str, name: str, subnet_cidr: str):
        return cls(
            VNetEntry.construct(cidr, name, subnet_cidr).as_dict
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class NSGEntry(object):
    cf_nsg = attr.ib(validator=io(list))

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
class SecurityRule(object):
    entry = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, name: str, port_list: list, priority: int, src: str = "*", dst: str = "*", protocol: str = "Tcp"):
        return cls(
            {
                "description": "Cloud Formation Managed",
                "access": "Allow",
                "destination_address_prefix": dst,
                "destination_port_ranges": port_list,
                "direction": "Inbound",
                "name": name,
                "priority": priority,
                "protocol": protocol,
                "source_address_prefix": src,
                "source_port_range": "*",
                "destination_application_security_group_ids": None,
                "source_application_security_group_ids": None,
                "destination_address_prefixes": None,
                "destination_port_range": None,
                "source_address_prefixes": None,
                "source_port_ranges": None
            }
        )

    @property
    def as_dict(self):
        return self.__dict__['entry']


@attr.s
class NSGElements(object):
    location = attr.ib(validator=io(str))
    name = attr.ib(validator=io(str))
    resource_group_name = attr.ib(validator=io(str))
    security_rule = attr.ib(validator=io(list))
    tags = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, name: str):
        return cls(
            "${azurerm_resource_group.cf_rg.location}",
            name,
            "${azurerm_resource_group.cf_rg.name}",
            [],
            {"name": name}
        )

    def add(self, name: str, port_list: list, priority: int, src: str = "*", dst: str = "*", protocol: str = "Tcp"):
        security_rule = SecurityRule.construct(name, port_list, priority, src, dst, protocol).as_dict
        self.security_rule.append(security_rule)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class NSGResource(object):
    azurerm_network_security_group = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, entry: dict):
        return cls(
            entry
        )

    @property
    def as_dict(self):
        return self.__dict__
