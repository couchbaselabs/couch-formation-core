##
##

import json
import logging
import attr
import re
import time
from typing import Optional, List, Union
from enum import Enum
import attrs
import ipaddress
import string
import random
from itertools import cycle
from ipaddress import IPv4Network
from couchformation.exception import FatalError
from couchformation.capella.driver.cb_bucket import Bucket
from couchformation.capella.driver.cb_capella_config import CapellaConfigFile
from couchformation.restmgr import RESTManager

logger = logging.getLogger('couchformation.capella.driver.capella')
logger.addHandler(logging.NullHandler())


class CapellaError(FatalError):
    pass


aws_storage_matrix = {
    99: 3000,
    199: 5000,
    299: 6000,
    399: 8000,
    499: 9000,
    599: 10000,
    699: 12000,
    799: 13000,
    899: 14000,
    999: 16000,
    16384: 16000
}


azure_storage_matrix = {
    64: "P6",
    128: "P10",
    256: "P15",
    512: "P20",
    1024: "P30",
    2048: "P40",
    4096: "P50",
    8192: "P60"
}


class Role(object):

    def __init__(self, name=None, bucket=None, scope=None, collection=None):
        if not name:
            raise RuntimeError('A role must have a name')
        self._name = name
        self._bucket = bucket
        self._scope = scope
        self._collection = collection

    @property
    def name(self) -> str:
        return self._name

    @property
    def bucket(self) -> str:
        return self._bucket

    @property
    def scope(self) -> str:
        return self._scope

    @property
    def collection(self) -> str:
        return self._collection

    def as_dict(self):
        return {
            'name': self._name,
            'bucket': self._bucket,
            'scope': self._scope,
            'collection': self._collection
        }

    def __eq__(self, other):
        if not isinstance(other, Role):
            return False
        return (self.name == other.name
                and self.bucket == other.bucket
                and self.scope == other.scope
                and self.collection == other.collection)

    def __hash__(self):
        return hash((self.name, self.bucket, self.scope, self.collection))

    @classmethod
    def create_role(cls, raw_data):
        return cls(
            name=raw_data.get("name", None),
            bucket=raw_data.get("bucket_name", None),
            scope=raw_data.get("scope_name", None),
            collection=raw_data.get("collection_name", None)
        )


class NodeAvailability(str, Enum):
    single = 'single'
    multi = 'multi'


class SupportPlan(str, Enum):
    basic = 'basic'
    devpro = 'developer pro'
    enterprise = 'enterprise'


class SupportTZ(str, Enum):
    eastern_us = 'ET'
    emea = 'GMT'
    asia = 'IST'
    western_us = 'PT'


class CapellaBucketType(str, Enum):
    couchbase = 'membase'
    ephemeral = 'ephemeral'


class CapellaDurabilityLevel(int, Enum):
    none = 0
    majority = 1
    majorityAndPersistActive = 2
    persistToMajority = 3


class BucketBackend(str, Enum):
    couchstore = 'couchstore'
    magma = 'magma'


class BucketResolution(str, Enum):
    seqno = 'seqno'
    lww = 'lww'


class BucketDurability(str, Enum):
    none = 'none'
    majority = 'majority'
    majorityAndPersistActive = 'majorityAndPersistActive'
    persistToMajority = 'persistToMajority'


class BucketEviction(str, Enum):
    fullEviction = 'fullEviction'
    noEviction = 'noEviction'
    nruEviction = 'nruEviction'


@attr.s
class CloudProvider:
    type: Optional[str] = attr.ib(default=None)
    region: Optional[str] = attr.ib(default=None)
    cidr: Optional[str] = attr.ib(default='10.0.0.0/23')


@attr.s
class ComputeConfig:
    cpu: Optional[int] = attr.ib(default=None)
    ram: Optional[int] = attr.ib(default=None)


@attr.s
class StorageConfig:
    storage: Optional[int] = attr.ib(default=None)
    type: Optional[str] = attr.ib(default=None)
    iops: Optional[int] = attr.ib(default=None)


@attr.s
class NodeConfig:
    compute: Optional[ComputeConfig] = attr.ib(default=None)
    disk: Optional[StorageConfig] = attr.ib(default=None)


@attr.s
class ServiceGroup:
    node: Optional[NodeConfig] = attr.ib(default=None)
    numOfNodes: Optional[int] = attr.ib(default=None)
    services: Optional[List[str]] = attr.ib(default=None)


@attr.s
class Availability:
    type: Optional[NodeAvailability] = attr.ib(default=NodeAvailability.multi)


@attr.s
class Support:
    plan: Optional[SupportPlan] = attr.ib(default=SupportPlan.devpro)
    timezone: Optional[SupportTZ] = attr.ib(default=SupportTZ.western_us)


@attr.s
class CouchbaseServer:
    version: Optional[str] = attr.ib(default=None)


@attr.s
class CapellaCluster:
    name: Optional[str] = attr.ib(default=None)
    description: Optional[str] = attr.ib(default=None)
    cloudProvider: Optional[CloudProvider] = attr.ib(default=None)
    couchbaseServer: Optional[CouchbaseServer] = attr.ib(default=None)
    serviceGroups: Optional[List[ServiceGroup]] = attr.ib(default=[])
    availability: Optional[Availability] = attr.ib(default=None)
    support: Optional[Support] = attr.ib(default=None)

    @classmethod
    def create(cls,
               name,
               description,
               cloud,
               region,
               cidr='10.0.0.0/23',
               availability=NodeAvailability.multi,
               plan=SupportPlan.devpro,
               timezone=SupportTZ.western_us,
               version="latest"):
        return cls(
            name,
            description,
            CloudProvider(
                cloud,
                region,
                cidr
            ),
            CouchbaseServer(version),
            [],
            Availability(availability),
            Support(plan, timezone)
        )

    def add_service_group(self, cloud, machine_type, storage=256, quantity=3, services=None):
        if not services:
            services = ["data", "index", "query"]
        cpu, memory = machine_type.split('x')
        if cloud == "aws":
            size = storage
            iops = next((aws_storage_matrix[s] for s in aws_storage_matrix if s >= storage), None)
            s_type = "gp3"
        elif cloud == "azure":
            size, s_type = next(((s, azure_storage_matrix[s]) for s in azure_storage_matrix if s >= storage), None)
            iops = None
        else:
            size = storage
            s_type = None
            iops = None
        self.serviceGroups.append(
            ServiceGroup(
                NodeConfig(
                    ComputeConfig(int(cpu), int(memory)),
                    StorageConfig(size, s_type, iops)
                ),
                quantity,
                services
            )
        )


@attr.s
class CapellaClusterUpdate:
    name: Optional[str] = attr.ib(default=None)
    description: Optional[str] = attr.ib(default=None)
    support: Optional[Support] = attr.ib(default=None)
    serviceGroups: Optional[List[ServiceGroup]] = attr.ib(default=[])

    @classmethod
    def create(cls, name, description, plan=SupportPlan.devpro, timezone=SupportTZ.western_us):
        return cls(
            name,
            description,
            Support(plan, timezone),
            [],
        )

    def add_service_group(self, cloud, machine_type, storage=256, quantity=3, services=None):
        if not services:
            services = ["data", "index", "query"]
        cpu, memory = machine_type.split('x')
        if cloud == "aws":
            size = storage
            iops = next((aws_storage_matrix[s] for s in aws_storage_matrix if s >= storage), None)
            s_type = "gp3"
        elif cloud == "azure":
            size, s_type = next(((s, azure_storage_matrix[s]) for s in azure_storage_matrix if s >= storage), None)
            iops = None
        else:
            size = storage
            s_type = None
            iops = None
        self.serviceGroups.append(
            ServiceGroup(
                NodeConfig(
                    ComputeConfig(int(cpu), int(memory)),
                    StorageConfig(size, s_type, iops)
                ),
                quantity,
                services
            )
        )


@attr.s
class AllowedCIDR:
    cidr: Optional[str] = attr.ib(default='0.0.0.0/0')

    @classmethod
    def create(cls, cidr='0.0.0.0/0'):
        return cls(
            cidr
        )


@attr.s
class UserAccess:
    privileges: Optional[List[str]] = attr.ib(default=[
        "read",
        "write",
    ]
    )


@attr.s
class Credentials:
    name: Optional[str] = attr.ib(default='sysdba')
    password: Optional[str] = attr.ib(default=None)
    access: Optional[List[UserAccess]] = attr.ib(default=None)

    @classmethod
    def create(cls, username, password):
        return cls(
            username,
            password,
            [
                UserAccess()
            ]
        )

    @classmethod
    def from_cbs(cls, username: str, password: str, roles: List[Role]):
        access = UserAccess()
        access.privileges.append("read")
        if any(r for r in roles if r.name == 'data_writer') or any(r for r in roles if r.name == 'query_insert') or any(r for r in roles if r.name == 'query_delete'):
            access.privileges.append("write")
        return cls(
            username,
            password,
            [
                UserAccess()
            ]
        )


@attr.s
class UserOpValue:
    id: Optional[str] = attr.ib(default=None)
    type: Optional[str] = attr.ib(default=None)
    roles: Optional[List[str]] = attr.ib(default=None)


@attr.s
class UserOp:
    op: Optional[str] = attr.ib(default=None)
    path: Optional[str] = attr.ib(default=None)
    value: Optional[UserOpValue] = attr.ib(default=None)


@attr.s
class UserOpList:
    user_op_list: Optional[List[UserOp]] = attr.ib(default=[])

    def add(self, project_id: str, role: str):
        opo = UserOp()
        opo.op = "add"
        opo.path = f"/resources/{project_id}"
        opo.value = UserOpValue(id=project_id, type="project", roles=[role])
        self.user_op_list.append(opo)

    @property
    def as_dict(self):
        return list(attrs.asdict(o) for o in self.__dict__["user_op_list"])


@attr.s
class AppService:
    name: Optional[str] = attr.ib(default="AppService")
    description: Optional[str] = attr.ib(default="Automation Generated App Service")
    nodes: Optional[int] = attr.ib(default=2)
    compute: Optional[ComputeConfig] = attr.ib(default=ComputeConfig(2, 4))
    version: Optional[str] = attr.ib(default="latest")

    @classmethod
    def create(cls, name: str, description: str, nodes: int, machine_type: str, version: str):
        cpu, memory = machine_type.split('x')
        return cls(
            name,
            description,
            nodes,
            ComputeConfig(int(cpu), int(memory)),
            version
        )


class NetworkDriver(object):

    def __init__(self):
        self.ip_space = []
        self.active_network: IPv4Network = ipaddress.ip_network("10.1.0.0/16")
        self.super_net: IPv4Network = ipaddress.ip_network("10.0.0.0/8")

    def set_active_network(self, cidr: str):
        self.active_network: IPv4Network = ipaddress.ip_network(cidr)

    def add_network(self, cidr: str) -> None:
        cidr_net = ipaddress.ip_network(cidr)
        self.ip_space.append(cidr_net)

    def get_next_subnet(self, prefix=24) -> str:
        for subnet in self.active_network.subnets(new_prefix=prefix):
            yield subnet.exploded

    def get_next_network(self) -> Union[str, None]:
        candidates = list(self.super_net.subnets(new_prefix=16))

        for network in self.ip_space:
            available = []
            for n, candidate in enumerate(candidates):
                try:
                    if network.prefixlen < 16:
                        list(network.address_exclude(candidate))
                    else:
                        list(candidate.address_exclude(network))
                except ValueError:
                    available.append(candidate)
            candidates = available

        if len(candidates) == 0:
            return None

        self.active_network = candidates[0]
        self.ip_space.append(self.active_network)
        return self.active_network.exploded


class Capella(object):

    def __init__(self, organization_id=None, project_id=None, profile='default'):
        self.rest = RESTManager(profile=profile)
        self.cf = CapellaConfigFile(profile)

        self._cluster_id = None
        self._cluster_name = None

        self.organization_id = organization_id
        self.project_id = project_id

        if not self.organization_id:
            if self.cf.organization:
                self.organization_id = self.rest.get_capella('/v4/organizations').by_name(self.cf.organization).unique().id()
            else:
                self.organization_id = self.rest.get_capella('/v4/organizations').item(0).id()

        if not self.project_id and self.cf.project:
            self.project_id = self.rest.get_capella(f"/v4/organizations/{self.organization_id}/projects").by_name(self.cf.project).unique().id()

    @staticmethod
    def valid_password(password: str):
        lower = 0
        upper = 0
        digit = 0
        if len(password) >= 8:
            for i in password:
                if i.islower():
                    lower += 1
                if i.isupper():
                    upper += 1
                if i.isdigit():
                    digit += 1

        if lower >= 1 and upper >= 1 and digit >= 1:
            return True
        else:
            return False

    def generate_password(self):
        while True:
            text = ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k=7))
            password = f"{str(text)}#"
            if self.valid_password(password):
                return password

    def list_organizations(self):
        return self.rest.get_capella('/v4/organizations').list()

    def get_organization(self, name: str):
        return self.rest.get_capella('/v4/organizations').by_name(name).unique().record()

    def list_users(self):
        return self.rest.get_capella(f"/v4/organizations/{self.organization_id}/users").list()

    def get_user(self, email: str):
        return self.rest.get_capella_kv(f"/v4/organizations/{self.organization_id}/users", "email", email).item(0).record()

    def list_projects(self):
        return self.rest.get_capella(f"/v4/organizations/{self.organization_id}/projects").list()

    def get_project(self, name: str):
        return self.rest.get_capella(f"/v4/organizations/{self.organization_id}/projects").by_name(name).unique().record()

    def create_project(self, name: str, email: str = None):
        account_email = email if email else self.cf.account_email if self.cf.account_email else None
        parameters = {"name": name}
        try:
            project_id = self.rest.post_capella(f"/v4/organizations/{self.organization_id}/projects", parameters).id()
            if account_email is not None:
                self.set_project_owner(project_id, account_email)
            return project_id
        except Exception as err:
            raise CapellaError(f"Can not create project: {err}")

    def set_project_owner(self, project_id: str, email: str = None):
        user = self.get_user(email)
        if not user:
            raise CapellaError("User does not exist")

        user_id = user.get('id')
        user_op = UserOpList()
        user_op.add(project_id, "projectOwner")
        parameters = user_op.as_dict

        try:
            self.rest.patch_capella(f"/v4/organizations/{self.organization_id}/users/{user_id}", parameters)
        except Exception as err:
            raise CapellaError(f"Can not set project ownership: {err}")

    def delete_project(self, name: str):
        project = self.get_project(name)
        if project:
            project_id = project.get('id')
            try:
                self.rest.delete_capella(f"/v4/organizations/{self.organization_id}/projects/{project_id}")
            except Exception as err:
                raise CapellaError(f"Can not delete project: {err}")

    def list_clusters(self):
        return self.rest.get_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters").list()

    def get_cluster(self, name):
        return self.rest.get_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters").by_name(name).unique().record()

    def get_cluster_by_id(self, cluster_id: str):
        endpoint = f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}"
        url = self.rest.build_url(endpoint)
        return self.rest.get(url).validate().json()

    def create_cluster(self, cluster: CapellaCluster):
        cidr_util = NetworkDriver()
        # noinspection PyTypeChecker
        parameters = attrs.asdict(cluster)
        cluster_cidr = cluster.cloudProvider.cidr
        cidr_util.add_network(cluster_cidr)
        cidr_util.get_next_network()
        subnet_list = list(cidr_util.get_next_subnet(prefix=23))
        subnet_cycle = cycle(subnet_list)

        if parameters.get("couchbaseServer", {}).get("version") in (None, "latest"):
            if parameters.get("couchbaseServer"):
                del parameters["couchbaseServer"]

        response = self.get_cluster(cluster.name)
        if response:
            return response.get('id')

        logger.debug(f"create_cluster: \n{json.dumps(parameters, indent=2)}")
        logger.debug(f"create_cluster: org_id = {self.organization_id} project_id = {self.project_id}")

        while True:
            try:
                return self.rest.post_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters", parameters).id()
            except RuntimeError as err:
                match = re.search(r"The provided CIDR of .* is not unique within this organization", str(err))
                if match:
                    logger.debug(f"Provided CIDR {cluster.cloudProvider.cidr} is in use in the organization")
                    network_cidr = next(subnet_cycle)
                    parameters['cloudProvider']['cidr'] = network_cidr
                    logger.debug(f"Trying new CIDR {network_cidr}")
                else:
                    raise CapellaError(f"Can not create Capella database: {err}")
            except Exception as err:
                raise CapellaError(f"Unknown Error: {err}")

    def update_cluster(self, updates: CapellaClusterUpdate):
        cluster = self.get_cluster(updates.name)
        if cluster:
            cluster_id = cluster.get('id')
            # noinspection PyTypeChecker
            parameters = attrs.asdict(updates)
            return self.rest.put_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}", parameters).record()

    def wait_for_cluster(self, name, retry_count=240, state="healthy"):
        for retry_number in range(retry_count + 1):
            cluster = self.get_cluster(name)
            if cluster and cluster.get('currentState') == state:
                return True
            else:
                if retry_number == retry_count:
                    return False
                logger.debug(f"Waiting for cluster {name} to reach state {state}")
                time.sleep(5)

    def wait_for_cluster_delete(self, name, retry_count=240):
        for retry_number in range(retry_count + 1):
            cluster = self.get_cluster(name)
            if cluster and cluster.get('currentState') == 'destroying':
                if retry_number == retry_count:
                    return False
                logger.debug(f"Waiting for cluster {name} to delete")
                time.sleep(5)
            else:
                return True

    def delete_cluster(self, cluster_name: str):
        cluster = self.get_cluster(cluster_name)
        if cluster:
            cluster_id = cluster.get('id')
            return self.rest.delete_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}")

    def get_allowed_cidr(self, cluster_id: str, cidr: str):
        return (self.rest.get_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}/allowedcidrs")
                .filter('cidr', cidr).unique().record())

    def allow_cidr(self, cluster_id: str, cidr: AllowedCIDR):
        response = self.get_allowed_cidr(cluster_id, cidr.cidr)
        if response:
            return response.get('id')

        # noinspection PyTypeChecker
        parameters = attrs.asdict(cidr)
        logger.debug(f"allow_cidr: \n{json.dumps(parameters, indent=2)}")
        logger.debug(f"allow_cidr: org_id = {self.organization_id} project_id = {self.project_id} cluster_id = {cluster_id}")

        try:
            return self.rest.post_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}/allowedcidrs", parameters).id()
        except Exception as err:
            raise CapellaError(f"Can not add database allowed CIDR: {err}")

    def get_db_user(self, cluster_id: str, name: str):
        return self.rest.get_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}/users").by_name(name).unique().record()

    def add_db_user(self, cluster_id: str, credentials: Credentials):
        response = self.get_db_user(cluster_id, credentials.name)
        if response:
            return response.get('id')

        # noinspection PyTypeChecker
        parameters = attrs.asdict(credentials)
        logger.debug(f"add_db_user: \n{json.dumps(parameters, indent=2)}")
        logger.debug(f"add_db_user: org_id = {self.organization_id} project_id = {self.project_id} cluster_id = {cluster_id}")

        try:
            return self.rest.post_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}/users", parameters).id()
        except Exception as err:
            raise CapellaError(f"Can not add database user: {err}")

    def change_db_user_password(self, cluster_id: str, username: str, password: str):
        user_settings = self.get_db_user(cluster_id, username)
        if user_settings:
            user_id = user_settings.get('id')
            parameters = dict(password=password)
            return self.rest.put_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}/users/{user_id}", parameters)

    def get_bucket(self, cluster_id: str, name: str):
        return self.rest.get_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}/buckets").by_name(name).unique().record()

    def list_buckets(self, cluster_id: str):
        return self.rest.get_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}/buckets").list()

    def add_bucket(self, cluster_id: str, bucket: Bucket):
        response = self.get_bucket(cluster_id, bucket.name)
        if response:
            return response.get('id')

        # noinspection PyTypeChecker
        parameters = dict(
            name=bucket.name,
            type=bucket.bucket_type.to_server_str,
            storageBackend=bucket.storage_backend.value,
            memoryAllocationInMb=bucket.ram_quota_mb,
            bucketConflictResolution=bucket.conflict_resolution_type.value,
            durabilityLevel=bucket.minimum_durability_level.to_server_str,
            replicas=bucket.num_replicas,
            flush=bucket.flush_enabled,
            timeToLiveInSeconds=bucket.max_ttl
        )
        logger.debug(f"add_bucket: \n{json.dumps(parameters, indent=2)}")
        logger.debug(f"add_bucket: org_id = {self.organization_id} project_id = {self.project_id} cluster_id = {cluster_id}")

        try:
            return self.rest.post_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}/buckets", parameters).id()
        except Exception as err:
            raise CapellaError(f"Can not add bucket: {err}")

    def delete_bucket(self, cluster_name: str, bucket_name: str):
        cluster = self.get_cluster(cluster_name)
        if cluster:
            cluster_id = cluster.get('id')
            bucket = self.get_bucket(cluster_id, bucket_name)
            if bucket:
                bucket_id = bucket.get('id')
                return self.rest.delete_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}/buckets/{bucket_id}")

    def list_app_svc(self):
        return self.rest.get_capella(f"/v4/organizations/{self.organization_id}/appservices").list()

    def get_app_svc(self, cluster_id: str):
        return self.rest.get_capella(f"/v4/organizations/{self.organization_id}/appservices").filter("clusterId", cluster_id).unique().record()

    def get_app_svc_by_id(self, cluster_id: str, app_svc_id: str):
        endpoint = f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}/appservices/{app_svc_id}"
        url = self.rest.build_url(endpoint)
        return self.rest.get(url).validate().json()

    def create_app_svc(self, cluster_id: str, app_svc: AppService):
        # noinspection PyTypeChecker
        parameters = attrs.asdict(app_svc)

        response = self.get_app_svc(cluster_id)
        if response:
            return response.get('id')

        if parameters.get("version") in (None, "latest"):
            if parameters.get("version"):
                del parameters["version"]

        try:
            return self.rest.post_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}/appservices", parameters).id()
        except Exception as err:
            raise CapellaError(f"Can not create Capella app service: {err}")

    def delete_app_svc(self, cluster_id: str):
        app_svc = self.get_app_svc(cluster_id)
        if not app_svc:
            return
        app_svc_id = app_svc.get('id')
        return self.rest.delete_capella(f"/v4/organizations/{self.organization_id}/projects/{self.project_id}/clusters/{cluster_id}/appservices/{app_svc_id}")

    def wait_for_app_svc(self, cluster_id: str, retry_count=360, state="healthy"):
        for retry_number in range(retry_count + 1):
            app_svc = self.get_app_svc(cluster_id)
            if app_svc and app_svc.get('currentState') == state:
                return True
            else:
                if retry_number == retry_count:
                    return False
                logger.debug(f"Waiting for cluster {cluster_id} app service to reach state {state}")
                time.sleep(5)

    def wait_for_app_svc_delete(self, cluster_id: str, retry_count=360):
        for retry_number in range(retry_count + 1):
            app_svc = self.get_app_svc(cluster_id)
            if app_svc and app_svc.get('currentState') == 'destroying':
                if retry_number == retry_count:
                    return False
                logger.debug(f"Waiting for cluster {cluster_id} app service to delete")
                time.sleep(5)
            else:
                return True
