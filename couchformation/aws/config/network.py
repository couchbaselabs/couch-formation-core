##

import attr
from attr.validators import instance_of as io


@attr.s
class AWSProvider(object):
    provider = attr.ib(validator=io(dict))

    @classmethod
    def for_region(cls, region: str):
        entry = {"region": region}
        return cls(
            {"aws": [entry]},
            )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class InternetGatewayResource(object):
    aws_internet_gateway = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, ig_name: str):
        return cls(
            InternetGateway.construct(ig_name).as_dict
            )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class InternetGateway(object):
    cf_gw = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, ig_name: str):
        return cls(
            [
                InternetGatewayEntry.construct(ig_name).as_dict
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class InternetGatewayEntry(object):
    depends_on = attr.ib(validator=io(list))
    tags = attr.ib(validator=io(dict))
    vpc_id = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, ig_name: str):
        return cls(
            [
                f"aws_vpc.cf_vpc"
            ],
            {
                "Name": ig_name
            },
            "${aws_vpc.cf_vpc.id}"
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class VPCResource(object):
    aws_vpc = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, cidr: str, vpc_name: str):
        return cls(
            VPC.construct(cidr, vpc_name).as_dict
            )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class VPC(object):
    cf_vpc = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, cidr: str, vpc_name: str):
        return cls(
            [
                VPCEntry.construct(cidr, vpc_name).as_dict
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class VPCEntry(object):
    cidr_block = attr.ib(validator=io(str))
    tags = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, cidr: str, vpc_name: str):
        return cls(
            cidr,
            {
                "Name": vpc_name
            }
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class RouteResource(object):
    aws_route_table = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, resource: dict):
        return cls(
            RouteTable.construct(resource).as_dict
            )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class RouteTable(object):
    cf_rt = attr.ib(validator=io(list))

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
class RouteEntry(object):
    depends_on = attr.ib(validator=io(list))
    route = attr.ib(validator=io(list))
    tags = attr.ib(validator=io(dict))
    vpc_id = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, rt_name: str):
        return cls(
                [
                    f"aws_internet_gateway.cf_gw",
                    f"aws_vpc.cf_vpc"
                ],
                [],
                {
                    "Name": rt_name
                },
                "${aws_vpc.cf_vpc.id}"
        )

    def add(self, cidr: str):
        resource = Route.construct(cidr).as_dict
        self.route.append(resource)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class Route(object):
    route = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, cidr: str):
        return cls(
            {
                "carrier_gateway_id": "",
                "cidr_block": cidr,
                "ipv6_cidr_block": None,
                "gateway_id": f"${{aws_internet_gateway.cf_gw.id}}",
                "core_network_arn": "",
                "destination_prefix_list_id": "",
                "egress_only_gateway_id": "",
                "instance_id": "",
                "local_gateway_id": "",
                "nat_gateway_id": "",
                "network_interface_id": "",
                "transit_gateway_id": "",
                "vpc_endpoint_id": "",
                "vpc_peering_connection_id": ""
            }
        )

    @property
    def as_dict(self):
        return self.__dict__['route']


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
class SubnetEntry(object):
    subnet = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, subnet_name: str, zone: str, cidr: str, pub_ip: bool):
        return cls(
            {subnet_name: [
               SubnetElements.construct(subnet_name, zone, cidr, pub_ip).as_dict
            ]}
        )

    @property
    def as_dict(self):
        return self.__dict__['subnet']


@attr.s
class SubnetElements(object):
    availability_zone = attr.ib(validator=io(str))
    cidr_block = attr.ib(validator=io(str))
    map_public_ip_on_launch = attr.ib(validator=io(bool))
    tags = attr.ib(validator=io(dict))
    vpc_id = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, subnet_name: str, zone: str, cidr: str, pub_ip: bool):
        return cls(
            zone,
            cidr,
            pub_ip,
            {
                "Name": subnet_name
            },
            "${aws_vpc.cf_vpc.id}"
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class SubnetResource(object):
    aws_subnet = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, subnet_name: str, zone: str, cidr: str, pub_ip: bool):
        subnet_item = SubnetEntry.construct(subnet_name, zone, cidr, pub_ip).as_dict
        self.aws_subnet.update(subnet_item)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class RTAssociationEntry(object):
    subnet = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, subnet_name: str):
        return cls(
            {subnet_name: [
               RTAssociationElements.construct(subnet_name).as_dict
            ]}
        )

    @property
    def as_dict(self):
        return self.__dict__['subnet']


@attr.s
class RTAssociationElements(object):
    route_table_id = attr.ib(validator=io(str))
    subnet_id = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, subnet_name: str):
        return cls(
            "${aws_route_table.cf_rt.id}",
            f"${{aws_subnet.{subnet_name}.id}}"
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class RTAssociationResource(object):
    aws_route_table_association = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, subnet_name: str):
        association = RTAssociationEntry.construct(subnet_name).as_dict
        self.aws_route_table_association.update(association)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class SGResource(object):
    aws_security_group = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, resource: dict):
        return cls(
            SecurityGroup.construct(resource).as_dict
            )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class SecurityGroup(object):
    cf_sg = attr.ib(validator=io(list))

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
class SecurityGroupEntry(object):
    depends_on = attr.ib(validator=io(list))
    description = attr.ib(validator=io(str))
    egress = attr.ib(validator=io(list))
    ingress = attr.ib(validator=io(list))
    name = attr.ib(validator=io(str))
    tags = attr.ib(validator=io(dict))
    vpc_id = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, sg_name: str):
        description_text = "Couchbase Default Security Group"
        return cls(
                [
                    f"aws_vpc.cf_vpc"
                ],
                description_text,
                [Egress.construct("0.0.0.0/0", "::/0").as_dict],
                [Ingress.construct("${aws_vpc.cf_vpc.cidr_block}", 0, "-1", 0).as_dict],
                sg_name,
                {
                    "Name": sg_name
                },
                "${aws_vpc.cf_vpc.id}"
        )

    def add_ingress(self, cidr_v4: str, from_port: int, protocol: str, to_port: int):
        resource = Ingress.construct(cidr_v4, from_port, protocol, to_port).as_dict
        self.ingress.append(resource)
        return self

    def add_egress(self, cidr_v4: str = "0.0.0.0/0", cidr_v6: str = "::/0"):
        resource = Egress.construct(cidr_v4, cidr_v6).as_dict
        self.egress.append(resource)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class Egress(object):
    egress = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, cidr_v4: str, cidr_v6: str):
        return cls(
            {
                "cidr_blocks": [
                    cidr_v4
                ],
                "description": "Cloud Formation Autogenerated",
                "from_port": 0,
                "ipv6_cidr_blocks": [
                    cidr_v6
                ],
                "prefix_list_ids": [],
                "security_groups": [],
                "self": False,
                "protocol": "-1",
                "to_port": 0
            }
        )

    @property
    def as_dict(self):
        return self.__dict__['egress']


@attr.s
class Ingress(object):
    ingress = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, cidr_v4: str, from_port: int, protocol: str, to_port: int):
        return cls(
            {
                "cidr_blocks": [
                    cidr_v4
                ],
                "from_port": from_port,
                "protocol": protocol,
                "to_port": to_port,
                "description": "Cloud Formation Autogenerated",
                "ipv6_cidr_blocks": [],
                "prefix_list_ids": [],
                "security_groups": [],
                "self": False
            }
        )

    @property
    def as_dict(self):
        return self.__dict__['ingress']


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
