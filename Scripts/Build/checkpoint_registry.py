"""Central regional checkpoint records and policy; no runtime/save writer.

Consumers must bind destination provenance and runtime placement before wiring
this module into a build or game hook. Logical domains are independent of physical
map numbering. Native SpawnPoint remains owned by its compatibility adapters.
"""
from dataclasses import dataclass
from enum import IntEnum
import hashlib
import re


class Domain(IntEnum):
    LIGHT = 0
    DARK = 1
    SPECIAL = 2
    MINISH = 3


class ResumeIntent(IntEnum):
    HOME = 0
    REGIONAL = 1


class OverrideKind(IntEnum):
    NATIVE_SPAWN = 0
    GORON_FACTORY = 1
    ABYSS_SCRIPT = 2


SCHEMA = 1
NO_CHECKPOINT = 0
CACHE_BYTES = 0x32
RECORD_BYTES = 10 + CACHE_BYTES


def require(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class RegionalCheckpoint:
    key: int
    domain: Domain
    map_id: int
    region_key: int
    parent_map: int
    exit_cache: bytes
    source_rom_sha256: str

    def pack(self, expected_source):
        require(type(self.key) is int and 0 < self.key < 0xFFFF,
                'Checkpoint key must be a stable nonzero u16, excluding FFFF')
        require(isinstance(self.domain, Domain), 'Checkpoint domain must be explicit')
        require(type(self.region_key) is int and 0 < self.region_key < 0xFFFF,
                'Checkpoint region must be explicit and independent of camera grouping')
        require(type(self.map_id) is int and 0 <= self.map_id < 0xC0 and
                type(self.parent_map) is int and 0 <= self.parent_map < 0xC0,
                'Checkpoint map/parent exceeds the current physical map engine')
        require(self.source_rom_sha256 == expected_source,
                'Checkpoint destination is bound to a different source ROM')
        require(type(self.exit_cache) is bytes and len(self.exit_cache) == CACHE_BYTES,
                'Checkpoint requires the complete native 50-byte exit cache')
        require(int.from_bytes(self.exit_cache[0:2], 'little') == self.parent_map,
                'Checkpoint cache parent disagrees with the explicit parent')
        require(int.from_bytes(self.exit_cache[12:14], 'little') == self.map_id,
                'Checkpoint cache physical map disagrees with the explicit map')
        return (self.key.to_bytes(2, 'little') + bytes((self.domain, 0)) +
                self.region_key.to_bytes(2, 'little') + self.map_id.to_bytes(2, 'little') + self.parent_map.to_bytes(2, 'little') +
                self.exit_cache)


@dataclass(frozen=True)
class Registry:
    epoch: int
    source_rom_sha256: str
    records: tuple
    packed_records: bytes

    @classmethod
    def compile(cls, records, *, epoch, source_rom_sha256):
        require(type(epoch) is int and 0 < epoch < 0xFF,
                'Registry epoch must be explicit and exclude old-save 00/FF')
        require(type(source_rom_sha256) is str and
                re.fullmatch(r'[0-9a-f]{64}', source_rom_sha256) is not None,
                'Registry requires an exact source ROM SHA256')
        records = tuple(records)
        require(all(isinstance(r, RegionalCheckpoint) for r in records),
                'Registry contains a non-checkpoint record')
        require(len(records) <= 0x100, 'Registry exceeds the bounded 256-record resolver')
        packed = [(r.key, r.pack(source_rom_sha256), r) for r in records]
        require(len({key for key, _, _ in packed}) == len(packed),
                'Checkpoint keys must be globally unique across logical domains')
        packed.sort(key=lambda row: row[0])
        return cls(epoch, source_rom_sha256, tuple(row[2] for row in packed),
                   b''.join(row[1] for row in packed))

    @property
    def content_sha256(self):
        return hashlib.sha256(bytes((SCHEMA, self.epoch)) +
                              bytes.fromhex(self.source_rom_sha256) + self.packed_records).hexdigest()

    def runtime_tables(self):
        """Return immutable bytes for the unplaced ASM codec, not ROM allocations."""
        return {
            'CheckpointRegistry_Keys': b''.join(r.key.to_bytes(2, 'little') for r in self.records),
            'CheckpointRegistry_Domains': b''.join(int(r.domain).to_bytes(2, 'little') for r in self.records),
            'CheckpointRegistry_Maps': b''.join(r.map_id.to_bytes(2, 'little') for r in self.records),
            'CheckpointRegistry_Regions': b''.join(r.region_key.to_bytes(2, 'little') for r in self.records),
            'CheckpointRegistry_Records': self.packed_records,
        }

    def find(self, key):
        return next((r for r in self.records if r.key == key), None)


@dataclass(frozen=True)
class SavedCheckpoint:
    """Granted B4..B8 last-activated value; this host codec performs no RAM writes."""
    schema: int
    epoch: int
    key: int

    def encode(self):
        require(type(self.schema) is int and 0 <= self.schema <= 255 and
                type(self.epoch) is int and 0 <= self.epoch <= 255 and
                type(self.key) is int and 0 <= self.key <= 0xFFFF,
                'Saved checkpoint does not fit the proposed four-byte value')
        return bytes((self.schema, self.epoch)) + self.key.to_bytes(2, 'little')


def restore_saved_checkpoint(raw, registry):
    """Pure migration; current save-buffer addresses are in Core/sram.asm."""
    require(type(raw) is bytes and len(raw) == 4, 'Checkpoint snapshot must be exactly four bytes')
    schema, epoch, key = raw[0], raw[1], int.from_bytes(raw[2:], 'little')
    reason = ('old_or_unknown_schema' if schema != SCHEMA else
              'retired_registry_epoch' if epoch != registry.epoch else
              'unknown_checkpoint_key' if key and registry.find(key) is None else 'current')
    return SavedCheckpoint(SCHEMA, registry.epoch, key if reason == 'current' else 0), reason


def activate_checkpoint(key, *, domain, map_id, region_key, registry):
    """Explicit activation only; returns a value for the existing save owner to persist."""
    record = registry.find(key)
    require(record is not None, 'Cannot activate an unregistered checkpoint')
    require(isinstance(domain, Domain) and record.domain == domain and record.map_id == map_id and
            type(region_key) is int and record.region_key == region_key,
            'Checkpoint activation domain/region/map does not match the registered destination')
    return SavedCheckpoint(SCHEMA, registry.epoch, record.key)


def prepare_resume_intent(saved, *, domain, region_key, registry):
    """Snapshot a qualified current region before saving; never erase the last key.

    Persisting this result requires separate ownership, not schema/epoch bits.
    The caller supplies domain/region from the live owning loader, not raw8A.
    """
    require(isinstance(domain, Domain) and type(region_key) is int and 0 < region_key < 0xFFFF,
            'Resume preparation requires explicit current domain and region')
    if saved.schema == SCHEMA and saved.epoch == registry.epoch:
        record = registry.find(saved.key)
        if record is not None and record.domain == domain and record.region_key == region_key:
            return ResumeIntent.REGIONAL
    return ResumeIntent.HOME


@dataclass(frozen=True)
class ScriptOverride:
    kind: OverrideKind
    native_spawn: int | None = None

    def __post_init__(self):
        require(isinstance(self.kind, OverrideKind), 'Script override kind must be explicit')
        if self.kind == OverrideKind.NATIVE_SPAWN:
            require(type(self.native_spawn) is int and 0 <= self.native_spawn <= 6,
                    'Native spawn adapter accepts only native selectors 0..6')
        else:
            require(self.native_spawn is None, 'Factory/Abyss adapters do not index native spawn tables')


def native_spawn_adapter(selector):
    """Explicit legacy adapter, never an implicit interpretation of the regional key."""
    require(type(selector) is int and 0 <= selector <= 7, 'Unsupported legacy SpawnPoint selector')
    return (ScriptOverride(OverrideKind.GORON_FACTORY) if selector == 7 else
            ScriptOverride(OverrideKind.NATIVE_SPAWN, selector))


@dataclass(frozen=True)
class Resolution:
    route: str
    checkpoint: RegionalCheckpoint | None = None
    override: ScriptOverride | None = None


def resolve_checkpoint(saved, *, registry, resume_intent, dungeon_entrance_continue=False, script_override=None):
    """One priority order, independent of domain and physical map numbering.

    Callers qualify normal dungeon death/Continue and live script predicates.
    Cold file load must not infer an active dungeon from stale volatile RAM.
    """
    require(isinstance(saved, SavedCheckpoint), 'Resolver requires explicit restored checkpoint state')
    require(isinstance(resume_intent, ResumeIntent), 'Resolver requires explicit qualified resume intent')
    require(type(dungeon_entrance_continue) is bool, 'Dungeon continue context must be explicit')
    require(script_override is None or isinstance(script_override, ScriptOverride),
            'Resolver requires a validated explicit script override')
    if dungeon_entrance_continue:
        return Resolution('dungeon_entrance')
    if script_override is not None:
        return Resolution('script_override', override=script_override)
    if resume_intent == ResumeIntent.REGIONAL and saved.schema == SCHEMA and saved.epoch == registry.epoch:
        record = registry.find(saved.key)
        if record is not None:
            return Resolution('regional_checkpoint', checkpoint=record)
    return Resolution('home', override=native_spawn_adapter(0))
