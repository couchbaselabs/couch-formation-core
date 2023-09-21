##
##

from __future__ import annotations
import os
import attr
import json
from pwd import getpwnam
from grp import getgrnam
from typing import Optional, List, Union

INFRASTRUCTURE = 0x01
INSTANCES = 0x02


class StateError(Exception):
    pass


@attr.s
class AWSInstance:
    name: Optional[str] = attr.ib(default=None)
    instance_id: Optional[str] = attr.ib(default=None)
    machine_type: Optional[str] = attr.ib(default=None)
    volume_iops: Optional[str] = attr.ib(default="3000")
    volume_size: Optional[str] = attr.ib(default="256")
    volume_type: Optional[str] = attr.ib(default="gp3")
    root_iops: Optional[str] = attr.ib(default="3000")
    root_size: Optional[str] = attr.ib(default="256")
    root_type: Optional[str] = attr.ib(default="gp3")
    public_ip: Optional[str] = attr.ib(default=None)
    private_ip: Optional[str] = attr.ib(default=None)
    services: Optional[str] = attr.ib(default=None)
    zone: Optional[str] = attr.ib(default=None)
    subnet_id: Optional[str] = attr.ib(default=None)


@attr.s
class AWSInstanceSet:
    cloud: Optional[str] = attr.ib(default="aws")
    name: Optional[str] = attr.ib(default=None)
    username: Optional[str] = attr.ib(default=None)
    instance_list: Optional[List[dict]] = attr.ib(default=[])


@attr.s
class AWSZone:
    zone: Optional[str] = attr.ib(default=None)
    subnet_id: Optional[str] = attr.ib(default=None)
    cidr: Optional[str] = attr.ib(default=None)


@attr.s
class AWSState:
    cloud: Optional[str] = attr.ib(default="aws")
    region: Optional[str] = attr.ib(default=None)
    vpc_id: Optional[str] = attr.ib(default=None)
    vpc_cidr: Optional[str] = attr.ib(default=None)
    security_group_id: Optional[str] = attr.ib(default=None)
    ssh_key: Optional[str] = attr.ib(default=None)
    internet_gateway_id: Optional[str] = attr.ib(default=None)
    route_table_id: Optional[str] = attr.ib(default=None)
    zone_list: Optional[List[dict]] = attr.ib(default=[])


@attr.s
class GCPDisk:
    name: Optional[str] = attr.ib(default=None)
    zone: Optional[str] = attr.ib(default=None)


@attr.s
class GCPInstance:
    name: Optional[str] = attr.ib(default=None)
    machine_type: Optional[str] = attr.ib(default=None)
    volume_size: Optional[str] = attr.ib(default="256")
    volume_type: Optional[str] = attr.ib(default="pd-ssd")
    root_size: Optional[str] = attr.ib(default="256")
    root_type: Optional[str] = attr.ib(default="pd-ssd")
    public_ip: Optional[str] = attr.ib(default=None)
    private_ip: Optional[str] = attr.ib(default=None)
    services: Optional[str] = attr.ib(default=None)
    zone: Optional[str] = attr.ib(default=None)
    disk_list: Optional[List[dict]] = attr.ib(default=[])


@attr.s
class GCPInstanceSet:
    cloud: Optional[str] = attr.ib(default="gcp")
    name: Optional[str] = attr.ib(default=None)
    username: Optional[str] = attr.ib(default=None)
    instance_list: Optional[List[dict]] = attr.ib(default=[])


@attr.s
class GCPZone:
    zone: Optional[str] = attr.ib(default=None)
    subnet: Optional[str] = attr.ib(default=None)


@attr.s
class GCPState:
    cloud: Optional[str] = attr.ib(default="gcp")
    region: Optional[str] = attr.ib(default=None)
    network: Optional[str] = attr.ib(default=None)
    network_cidr: Optional[str] = attr.ib(default=None)
    subnet: Optional[str] = attr.ib(default=None)
    subnet_cidr: Optional[str] = attr.ib(default=None)
    ssh_key: Optional[str] = attr.ib(default=None)
    firewall_default: Optional[str] = attr.ib(default=None)
    firewall_cbs: Optional[str] = attr.ib(default=None)
    firewall_ssh: Optional[str] = attr.ib(default=None)
    gcp_project: Optional[str] = attr.ib(default=None)
    credentials: Optional[str] = attr.ib(default=None)
    zone_list: Optional[List[dict]] = attr.ib(default=[])


@attr.s
class AzureDisk:
    name: Optional[str] = attr.ib(default=None)
    zone: Optional[str] = attr.ib(default=None)
    disk_attachment:  Optional[str] = attr.ib(default=None)


@attr.s
class AzureInstance:
    name: Optional[str] = attr.ib(default=None)
    node_nic: Optional[str] = attr.ib(default=None)
    node_pub_ip: Optional[str] = attr.ib(default=None)
    resource_group: Optional[str] = attr.ib(default=None)
    machine_type: Optional[str] = attr.ib(default=None)
    volume_tier: Optional[str] = attr.ib(default="P20")
    volume_size: Optional[str] = attr.ib(default="256")
    volume_type: Optional[str] = attr.ib(default="Premium_LRS")
    root_tier: Optional[str] = attr.ib(default="P20")
    root_size: Optional[str] = attr.ib(default="256")
    root_type: Optional[str] = attr.ib(default="Premium_LRS")
    public_ip: Optional[str] = attr.ib(default=None)
    private_ip: Optional[str] = attr.ib(default=None)
    services: Optional[str] = attr.ib(default=None)
    zone: Optional[str] = attr.ib(default=None)
    vm_public_ip: Optional[str] = attr.ib(default=None)
    vm_nic: Optional[str] = attr.ib(default=None)
    vm_nsg_association: Optional[str] = attr.ib(default=None)
    disk_list: Optional[List[dict]] = attr.ib(default=[])


@attr.s
class AzureInstanceSet:
    cloud: Optional[str] = attr.ib(default="azure")
    name: Optional[str] = attr.ib(default=None)
    username: Optional[str] = attr.ib(default=None)
    instance_list: Optional[List[dict]] = attr.ib(default=[])


@attr.s
class AzureZone:
    zone: Optional[str] = attr.ib(default=None)
    subnet: Optional[str] = attr.ib(default=None)
    subnet_id: Optional[str] = attr.ib(default=None)


@attr.s
class AzureState:
    cloud: Optional[str] = attr.ib(default="azure")
    location: Optional[str] = attr.ib(default=None)
    resource_group: Optional[str] = attr.ib(default=None)
    network: Optional[str] = attr.ib(default=None)
    network_id: Optional[str] = attr.ib(default=None)
    network_cidr: Optional[str] = attr.ib(default=None)
    subnet: Optional[str] = attr.ib(default=None)
    subnet_id: Optional[str] = attr.ib(default=None)
    subnet_cidr: Optional[str] = attr.ib(default=None)
    ssh_key: Optional[str] = attr.ib(default=None)
    network_security_group: Optional[str] = attr.ib(default=None)
    network_security_group_id: Optional[str] = attr.ib(default=None)
    zone_list: Optional[List[dict]] = attr.ib(default=[])


@attr.s
class ServiceSet:
    services: Optional[dict] = attr.ib(default={})

    def import_list(self, services: dict):
        for name, node_list in services.items():
            private_ip_list = [ip for ip in node_list.list_private_ip()]
            public_ip_list = [ip for ip in node_list.list_public_ip()]
            self.services.update({
                name: {
                    'private': private_ip_list,
                    'public': public_ip_list
                }
            })


@attr.s
class StateConfig:
    name: Optional[str] = attr.ib(default=None)
    cloud: Optional[str] = attr.ib(default=None)
    project_dir: Optional[str] = attr.ib(default=None)

    def set(self, name, cloud, project_dir):
        self.name = name
        self.cloud = cloud
        self.project_dir = project_dir


config = StateConfig()
services = ServiceSet()

infrastructure: Union[AWSState, GCPState, AzureState] = AWSState()
_infrastructure_update = False
instance_set: Union[AWSInstanceSet, GCPInstanceSet, AzureInstanceSet] = AWSInstanceSet()
_instance_update = False


def read_file(name: str):
    try:
        with open(name, 'r') as cfg_file_h:
            data = json.load(cfg_file_h)
            return data
    except FileNotFoundError:
        return None
    except Exception as err:
        raise StateError(f"can not read from config file {name}: {err}")


def write_file(data: dict, name: str):
    try:
        with open(name, 'w') as cfg_file_h:
            json.dump(data, cfg_file_h, indent=2)
            cfg_file_h.write('\n')
    except Exception as err:
        raise StateError(f"can not write to config file {name}: {err}")


def make_dir(name: str, owner: str = None, group: str = None, mode: int = 0o775):
    owner_id = getpwnam(owner).pw_uid if owner else None
    group_id = getgrnam(group).gr_gid if group else None
    if not os.path.exists(name):
        path_dir = os.path.dirname(name)
        if not os.path.exists(path_dir):
            make_dir(path_dir)
        try:
            uid = os.stat(path_dir).st_uid if not owner_id else owner_id
            gid = os.stat(path_dir).st_gid if not group_id else group_id
            os.mkdir(name)
            os.chown(name, uid, gid)
            os.chmod(name, mode)
        except OSError:
            raise


def service_dir():
    return os.path.join(config.project_dir, config.name)


def switch_cloud() -> None:
    global infrastructure, instance_set
    common_state_data = {}
    resource_state_data = {}
    common_state_file = os.path.join(config.project_dir, 'state.json')
    resource_state_file = os.path.join(service_dir(), 'state.json')

    if os.path.exists(common_state_file):
        common_state_data = read_file(common_state_file)
        if common_state_data['cloud'] != config.cloud:
            raise StateError(f"Cloud mismatch: state: {common_state_data['cloud']} requested: {config.cloud}")
    if os.path.exists(resource_state_file):
        resource_state_data = read_file(resource_state_file)
        if resource_state_data['cloud'] != config.cloud:
            raise StateError(f"Cloud mismatch: state: {resource_state_data['cloud']} requested: {config.cloud}")

    if config.cloud == 'aws':
        infrastructure = AWSState(**common_state_data)
        instance_set = AWSInstanceSet(**resource_state_data)
    elif config.cloud == 'gcp':
        infrastructure = GCPState(**common_state_data)
        instance_set = GCPInstanceSet(**resource_state_data)
    elif config.cloud == 'azure':
        infrastructure = AzureState(**common_state_data)
        instance_set = AzureInstanceSet(**resource_state_data)


def update(mask):
    global _infrastructure_update, _instance_update
    if 0x01 & mask > 0:
        _infrastructure_update = True
    if 0x02 & mask > 0:
        _instance_update = True


def save():
    if _infrastructure_update:
        make_dir(config.project_dir)
        # noinspection PyTypeChecker
        write_file(attr.asdict(infrastructure), os.path.join(config.project_dir, 'state.json'))
    if _instance_update:
        make_dir(service_dir())
        # noinspection PyTypeChecker
        write_file(attr.asdict(instance_set), os.path.join(service_dir(), 'state.json'))


def instance_count():
    return len(instance_set.instance_list)


def services_active():
    deployment_file = os.path.join(config.project_dir, "deployment.cfg")
    if os.path.exists(deployment_file):
        with open(deployment_file, 'r') as cfg_file:
            deployment_data = json.load(cfg_file)
            for name, service in deployment_data.items():
                if name == 'core':
                    continue
                state_path = os.path.join(config.project_dir, name, 'state.json')
                if os.path.exists(state_path):
                    with open(state_path, 'r') as state_file:
                        state_data = json.load(state_file)
                        if state_data.get('instance_list') and len(state_data.get('instance_list')) > 0:
                            return True
    return False


def infrastructure_display():
    json.dumps(infrastructure, indent=2)


def instances_display():
    json.dumps(instance_set, indent=2)
