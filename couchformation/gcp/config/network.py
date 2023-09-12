##

import attr
from attr.validators import instance_of as io


@attr.s
class GCPProvider(object):
    provider = attr.ib(validator=io(dict))

    @classmethod
    def for_region(cls, auth_file: str, gcp_project: str, region: str):
        entry = {
            "credentials": auth_file,
            "project": gcp_project,
            "region": region
        }
        return cls(
            {"google": [entry]},
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
class NetworkElements(object):
    auto_create_subnetworks = attr.ib(validator=io(bool))
    name = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, name: str):
        return cls(
            False,
            name
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class Network(object):
    cf_vpc = attr.ib(validator=io(list))

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
class NetworkResource(object):
    google_compute_network = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, name: str):
        return cls(
            Network.construct(NetworkElements.construct(name).as_dict).as_dict
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class SubnetElements(object):
    ip_cidr_range = attr.ib(validator=io(str))
    name = attr.ib(validator=io(str))
    network = attr.ib(validator=io(str))
    region = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, cidr: str, name: str, region: str):
        return cls(
            cidr,
            name,
            f"${{google_compute_network.cf_vpc.id}}",
            region
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class Subnet(object):
    cf_subnet_1 = attr.ib(validator=io(list))

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
class SubnetResource(object):
    google_compute_subnetwork = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, cidr: str, name: str, region: str):
        return cls(
            Subnet.construct(SubnetElements.construct(cidr, name, region).as_dict).as_dict
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class FirewallEntry(object):
    rule = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, name: str, description: str, ports: list, protocol: str, cidr: list):
        return cls(
            {f"{name}-fw-{description}": [
               FireElements.construct(name, description, ports, protocol, cidr).as_dict
            ]}
        )

    @property
    def as_dict(self):
        return self.__dict__['rule']


@attr.s
class DefaultFirewallEntry(object):
    rule = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, name: str, cidr: str):
        return cls(
            {f"{name}-fw-default": [
                {
                    "allow": [{"protocol": "all"}],
                    "name": f"{name}-fw-default",
                    "network": f"${{google_compute_network.cf_vpc.name}}",
                    "source_ranges": [cidr]
                }
            ]}
        )

    @property
    def as_dict(self):
        return self.__dict__['rule']


@attr.s
class AllowList(object):
    ports = attr.ib(validator=io(list))
    protocol = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, ports: list, protocol: str):
        return cls(
            ports,
            protocol
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class FireElements(object):
    allow = attr.ib(validator=io(list))
    name = attr.ib(validator=io(str))
    network = attr.ib(validator=io(str))
    source_ranges = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, name: str, description: str, ports: list, protocol: str, cidr: list):
        return cls(
            [AllowList.construct(ports, protocol).as_dict],
            f"{name}-fw-{description}",
            f"${{google_compute_network.cf_vpc.name}}",
            cidr
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class FirewallResource(object):
    google_compute_firewall = attr.ib(validator=io(dict))

    @classmethod
    def build(cls, name: str, cidr: str):
        return cls(
            DefaultFirewallEntry.construct(name, cidr).as_dict
        )

    def add(self, name: str, description: str, ports: list, protocol: str, cidr: list):
        firewall_item = FirewallEntry.construct(name, description, ports, protocol, cidr).as_dict
        self.google_compute_firewall.update(firewall_item)
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
