##
##

from __future__ import annotations
from datetime import timedelta
from typing import Optional
from enum import IntEnum, Enum
import attr


class DurabilityLevel(IntEnum):
    NONE = 0
    MAJORITY = 1
    MAJORITY_AND_PERSIST_TO_ACTIVE = 2
    PERSIST_TO_MAJORITY = 3

    @property
    def to_server_str(self):
        if self.name == 'MAJORITY_AND_PERSIST_TO_ACTIVE':
            return 'majorityAndPersistActive'
        elif self.name == 'NONE':
            return 'none'
        elif self.name == 'MAJORITY':
            return 'majority'
        elif self.name == 'PERSIST_TO_MAJORITY':
            return 'persistToMajority'
        else:
            return 'none'


class BucketType(Enum):
    COUCHBASE = "membase"
    MEMCACHED = "memcached"
    EPHEMERAL = "ephemeral"

    @property
    def to_server_str(self):
        if self.name == 'COUCHBASE':
            return 'couchbase'
        elif self.name == 'MEMCACHED':
            return 'memcached'
        elif self.name == 'EPHEMERAL':
            return 'ephemeral'
        else:
            return 'couchbase'


class CompressionMode(Enum):
    OFF = "off"
    PASSIVE = "passive"
    ACTIVE = "active"


class ConflictResolutionType(Enum):
    TIMESTAMP = "lww"
    SEQUENCE_NUMBER = "seqno"
    CUSTOM = "custom"


class EvictionPolicyType(Enum):
    NOT_RECENTLY_USED = "nruEviction"
    NO_EVICTION = "noEviction"
    FULL = "fullEviction"
    VALUE_ONLY = "valueOnly"


class StorageBackend(Enum):
    UNDEFINED = "undefined"
    COUCHSTORE = "couchstore"
    MAGMA = "magma"


@attr.s
class Bucket:
    flush_enabled: Optional[bool] = attr.ib(default=False)
    num_replicas: Optional[int] = attr.ib(default=1)
    ram_quota_mb: Optional[int] = attr.ib(default=128)
    replica_index: Optional[bool] = attr.ib(default=False)
    bucket_type: Optional[BucketType] = attr.ib(default=BucketType.COUCHBASE)
    max_ttl: Optional[int] = attr.ib(default=0)
    max_expiry: Optional[timedelta] = attr.ib(default=timedelta(0))
    compression_mode: Optional[CompressionMode] = attr.ib(default=CompressionMode.PASSIVE)
    conflict_resolution_type: Optional[ConflictResolutionType] = attr.ib(default=ConflictResolutionType.SEQUENCE_NUMBER)
    eviction_policy: Optional[EvictionPolicyType] = attr.ib(default=EvictionPolicyType.VALUE_ONLY)
    name: Optional[str] = attr.ib(default=None)
    minimum_durability_level: Optional[DurabilityLevel] = attr.ib(default=DurabilityLevel.NONE)
    storage_backend: Optional[StorageBackend] = attr.ib(default=StorageBackend.COUCHSTORE)

    @classmethod
    def from_dict(cls, values: dict):
        return cls(
            values.get('flush_enabled', False),
            values.get('num_replicas', 1),
            values.get('ram_quota_mb', 128),
            values.get('replica_index', False),
            BucketType(values.get('bucket_type', "membase")),
            values.get('max_ttl', 0),
            timedelta(values.get('max_expiry', 0)),
            CompressionMode(values.get('compression_mode', "passive")),
            ConflictResolutionType(values.get('conflict_resolution_type', "seqno")),
            EvictionPolicyType(values.get('eviction_policy', "valueOnly")),
            values.get('name'),
            DurabilityLevel(values.get('minimum_durability_level', 0)),
            StorageBackend(values.get('storage_backend', "couchstore")),
        )
