"""Central regional checkpoint records and policy; no runtime/save writer.

Consumers must bind destination provenance and runtime placement before wiring
this module into a build or game hook. Logical domains are independent of physical
map numbering. Native SpawnPoint remains owned by its compatibility adapters.
"""
from dataclasses import dataclass
from enum import IntEnum
import hashlib
import json
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
    native_affinity: int
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
        require(type(self.native_affinity) is int and self.native_affinity in (0, 0x40),
                'Native affinity must be explicit and independent of logical domain')
        require(self.source_rom_sha256 == expected_source,
                'Checkpoint destination is bound to a different source ROM')
        require(type(self.exit_cache) is bytes and len(self.exit_cache) == CACHE_BYTES,
                'Checkpoint requires the complete native 50-byte exit cache')
        require(int.from_bytes(self.exit_cache[0:2], 'little') == self.parent_map,
                'Checkpoint cache parent disagrees with the explicit parent')
        require(int.from_bytes(self.exit_cache[12:14], 'little') == self.map_id,
                'Checkpoint cache physical map disagrees with the explicit map')
        return (self.key.to_bytes(2, 'little') + bytes((self.domain, self.native_affinity)) +
                self.region_key.to_bytes(2, 'little') + self.map_id.to_bytes(2, 'little') + self.parent_map.to_bytes(2, 'little') +
                self.exit_cache)


@dataclass(frozen=True)
class RegionMembership:
    map_id: int
    domain: Domain
    native_affinity: int
    region_key: int

    def validate(self):
        require(type(self.map_id) is int and 0 <= self.map_id < 0xC0 and
                isinstance(self.domain, Domain) and self.native_affinity in (0,0x40) and
                type(self.region_key) is int and 0 < self.region_key < 0xFFFF,
                'Region membership must explicitly bind map/domain/affinity/region')


@dataclass(frozen=True)
class Registry:
    epoch: int
    source_rom_sha256: str
    records: tuple
    memberships: tuple
    packed_records: bytes

    @classmethod
    def compile(cls, records, *, memberships, epoch, source_rom_sha256):
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
        memberships = tuple(memberships)
        require(len(memberships) <= 0xC0, 'Region membership exceeds current physical map space')
        require(all(isinstance(m, RegionMembership) for m in memberships), 'Invalid region membership record')
        for member in memberships:
            member.validate()
        require(len({(m.map_id,m.domain,m.native_affinity) for m in memberships}) == len(memberships),
                'Duplicate/ambiguous explicit region membership')
        for record in records:
            require(any((m.map_id,m.domain,m.native_affinity,m.region_key) ==
                        (record.map_id,record.domain,record.native_affinity,record.region_key) for m in memberships),
                    'Checkpoint anchor lacks matching explicit region membership')
        memberships = tuple(sorted(memberships, key=lambda m:(m.map_id,m.domain,m.native_affinity)))
        packed.sort(key=lambda row: row[0])
        return cls(epoch, source_rom_sha256, tuple(row[2] for row in packed), memberships,
                   b''.join(row[1] for row in packed))

    @property
    def content_sha256(self):
        return hashlib.sha256(bytes((SCHEMA, self.epoch)) +
                              bytes.fromhex(self.source_rom_sha256) +
                              b''.join(self.runtime_tables().values())).hexdigest()

    def runtime_tables(self):
        """Return immutable bytes for the unplaced ASM codec, not ROM allocations."""
        return {
            'CheckpointRegistry_Keys': b''.join(r.key.to_bytes(2, 'little') for r in self.records),
            'CheckpointRegistry_Domains': b''.join(int(r.domain).to_bytes(2, 'little') for r in self.records),
            'CheckpointRegistry_Maps': b''.join(r.map_id.to_bytes(2, 'little') for r in self.records),
            'CheckpointRegistry_Regions': b''.join(r.region_key.to_bytes(2, 'little') for r in self.records),
            'CheckpointRegions_Maps': b''.join(m.map_id.to_bytes(2, 'little') for m in self.memberships),
            'CheckpointRegions_Domains': b''.join(int(m.domain).to_bytes(2, 'little') for m in self.memberships),
            'CheckpointRegions_Affinities': b''.join(m.native_affinity.to_bytes(2, 'little') for m in self.memberships),
            'CheckpointRegions_Regions': b''.join(m.region_key.to_bytes(2, 'little') for m in self.memberships),
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


def restore_runtime_state(raw, registry):
    """Pure five-byte restore: intent migration never erases a valid last key."""
    require(type(raw) is bytes and len(raw) == 5, 'Runtime checkpoint snapshot must be five bytes')
    saved, reason = restore_saved_checkpoint(raw[:4], registry)
    intent = ResumeIntent.HOME
    if reason == 'current' and raw[4] in (0, 1):
        intent = ResumeIntent(raw[4])
    elif reason == 'current':
        reason = 'unknown_resume_intent'
    return saved, intent, reason


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

# The first runtime row is an existing source-qualified native control. The
# approved source file (1bd8212f, SHA d1d0bd3a...) is preserved in the review;
# this is its exact50B cache hash, not a new destination recipe.
GORON_CACHE_SHA256 = 'f93f5bb9b6dd018c293a48789adff16cc9363cde71dfb3e12100100084634c8d'
CODE_BASE, CODE_LIMIT = 0x34F900, 0x34FE00


def qualify_native_control(source_rom):
    """Bind the approved1a5 control's relevant native area, allowing unrelated art."""
    import json
    import lyra_native_streams as N
    import lyra_project_admission as A
    # Existing native Large36 includes all four source-qualified pages. The
    # cached point is on its lower half; checking only page36 is insufficient.
    profiles, grid_bytes, tiles = [], b'', set()
    for area in (0x36, 0x37, 0x3E, 0x3F):
        profile = N.native_profile(source_rom, area)
        require(profile['parent'] == 0x36 and profile['size'] == 1,
                'Native Goron control camera topology changed')
        profiles.append(profile)
        planes = [N._plane(source_rom, area, table)[0] for table in N.POINTER_TABLES]
        ids = {high << 8 | low for high, low in zip(*planes)}
        grid = N._native_grid(planes, {i:A.read_tile32(source_rom, i) for i in ids})
        grid_bytes += area.to_bytes(2, 'little') + b''.join(t.to_bytes(2, 'little') for row in grid for t in row)
        tiles |= {t for row in grid for t in row}
    definitions = b''.join(t.to_bytes(2, 'little') + source_rom[0x1E8000+t*8:0x1E8008+t*8]
                           for t in sorted(tiles))
    expected = ('5577a04e285a103a8951af3f8021e5789d0ec978d1945ef679c2e5b6748ea76e',
                'f963be5bb78d3d3958f146a339451a3638d74e10c618f3eb050ef045ea3684ec',
                '9e2177fa90e01eb549e1d9bc4e8b1127ad088560f2f2159a1742ad637cf51fba')
    actual = tuple(hashlib.sha256(data).hexdigest() for data in
                   (json.dumps(profiles, sort_keys=True, separators=(',', ':')).encode(),
                    grid_bytes, definitions))
    require(actual == expected, 'Native Goron control profile/terrain/Tile16 binding changed; review required')
    return actual


def goron_control_registry(source_rom, goron_source):
    """Bind the known native control cache; admit no invented pilot coordinate."""
    m = re.search(r'macro RegionalCheckpoint_GoronControlCache\(\)(.*?)endmacro', goron_source, re.S)
    require(m is not None, 'Missing shared native Goron control-cache producer')
    words = []
    for line in m[1].splitlines():
        line = line.split(';', 1)[0].strip()
        if not line:
            continue
        require(line.startswith('dw '), 'Unsupported native control-cache data declaration')
        for value in line[3:].split(','):
            require(re.fullmatch(r'\$[0-9A-Fa-f]{4}', value.strip()) is not None,
                    'Native control cache must retain explicit source words')
            words.append(int(value.strip()[1:], 16))
    cache = b''.join(value.to_bytes(2, 'little') for value in words)
    require(hashlib.sha256(cache).hexdigest() == GORON_CACHE_SHA256,
            'Source-qualified Goron cache changed; checkpoint binding requires review')
    require('GoronCheckpoint_Cache:\n  %RegionalCheckpoint_GoronControlCache()' in goron_source,
            'Native factory must consume the same source-qualified cache producer')
    row = RegionalCheckpoint(1, Domain.LIGHT, 0x36, 1, 0x36, 0, cache,
                             hashlib.sha256(source_rom).hexdigest())
    return Registry.compile([row], memberships=[RegionMembership(area,Domain.LIGHT,0,1)
                           for area in (0x36,0x37,0x3E,0x3F)],
                            epoch=1, source_rom_sha256=row.source_rom_sha256)


def _private_binding(value):
    """Check the shape of independently verified current-transfer identities."""
    from pathlib import Path
    require(type(value) is dict and set(value) == {
        'source_rom_sha256', 'document_sha256', 'transfer_id', 'live',
        'selected_pair', 'cache_source'}, 'Malformed private checkpoint bindings')
    for key in ('source_rom_sha256', 'document_sha256', 'transfer_id'):
        require(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}', value[key]),
                'Private checkpoint requires exact '+key)
    live = value['live']
    require(type(live) is dict and set(live) == {'generation', 'operation_id', 'save_receipt'}
            and type(live['generation']) is int and 0 < live['generation'] <= 0xFFFFFFFFFFFFFFFF,
            'Private checkpoint requires the exact live save generation')
    token = live['operation_id']
    require(type(token) is str and 0 < len(token) <= 128 and all(32 < ord(c) < 127 for c in token),
            'Private checkpoint requires the live save operation ID')
    require(type(value['selected_pair']) is list and
            all(type(n) is int for n in value['selected_pair']) and
            value['selected_pair'] == [0xA0, 0xA1],
            'Private checkpoint requires the selected A0/A1 pair')
    for pin in (live['save_receipt'], value['cache_source']):
        require(type(pin) is dict and set(pin) == {'path', 'sha256'} and
                type(pin['path']) is str and '\0' not in pin['path'] and
                Path(pin['path']).is_absolute() and type(pin['sha256']) is str and
                re.fullmatch('[0-9a-f]{64}', pin['sha256']),
                'Private checkpoint requires exact save/cache-source artifact pins')


def runtime_registry(source_rom, goron_source, *, private_plan=None,
                     verified_bindings=None, expected_cache=None):
    """Compile the existing control plus an explicitly bound seeded preview.

    The caller must obtain verified_bindings independently from verify_transfer
    and current_native_source_profile, and expected_cache from the same reviewed
    landing/table producer as cache_source. Copying fields out of private_plan
    is not verification. Reconstruct these live bindings before every use: a
    later Save retires the plan even if ROM/document bytes did not change.
    This helper validates data only; it grants no allocation, route, publication,
    activation or native admission and writes neither a save nor a ROM.
    """
    control = goron_control_registry(source_rom, goron_source)
    if private_plan is None:
        require(verified_bindings is None and expected_cache is None,
                'Private checkpoint inputs require an explicit private plan')
        return control
    require(type(private_plan) is dict and set(private_plan) == {
        'kind', 'scope', 'production_admission', 'epoch', 'bindings', 'entry', 'memberships'} and
        private_plan['kind'] == 'checkpoint.private_preview_plan.v1' and
        private_plan['scope'] == 'seeded_private_preview' and
        private_plan['production_admission'] is False,
        'Checkpoint plan must be an explicit seeded private preview')
    require(type(private_plan['epoch']) is int and private_plan['epoch'] == control.epoch,
            'Private checkpoint registry epoch differs from the control')
    _private_binding(verified_bindings)
    _private_binding(private_plan['bindings'])
    require(private_plan['bindings'] == verified_bindings and
            verified_bindings['source_rom_sha256'] == control.source_rom_sha256,
            'Private checkpoint source/current save/selected pair bindings differ')
    # Reuse the current-transfer bound artifact reader. These reads do not
    # replace the caller's live transfer/profile and landing qualification.
    import lyra_project_prepare as Q
    Q.read_bound(verified_bindings['live']['save_receipt'])
    Q.read_bound(verified_bindings['cache_source'])
    require(type(expected_cache) is bytes and len(expected_cache) == CACHE_BYTES,
            'Private checkpoint requires an independently bound complete cache')
    entry = private_plan['entry']
    require(type(entry) is dict and set(entry) == {'key', 'domain', 'map_id', 'parent_map',
            'native_affinity', 'region_key', 'exit_cache_hex', 'cache_sha256'},
            'Malformed private checkpoint entry')
    require(type(entry['key']) is int and entry['key'] == 2 and
            type(entry['domain']) is str and entry['domain'] == 'SPECIAL' and
            type(entry['native_affinity']) is int and entry['native_affinity'] == 0 and
            type(entry['map_id']) is int and entry['map_id'] == 0xA0 and
            type(entry['parent_map']) is int and entry['parent_map'] == 0xA0,
            'Private checkpoint must explicitly select key2/SPECIAL/affinity0/A0')
    require(type(entry['exit_cache_hex']) is str and
            re.fullmatch('[0-9a-f]{100}', entry['exit_cache_hex']) and
            type(entry['cache_sha256']) is str and
            re.fullmatch('[0-9a-f]{64}', entry['cache_sha256']),
            'Private checkpoint requires an exact 50-byte cache and digest')
    cache = bytes.fromhex(entry['exit_cache_hex'])
    require(cache == expected_cache and hashlib.sha256(cache).hexdigest() == entry['cache_sha256'],
            'Private checkpoint cache differs from the independent landing binding')
    row = RegionalCheckpoint(entry['key'], Domain.SPECIAL, entry['map_id'], entry['region_key'],
                             entry['parent_map'], entry['native_affinity'], cache,
                             control.source_rom_sha256)
    row.pack(control.source_rom_sha256)
    members = private_plan['memberships']
    require(type(members) is list and len(members) == 2,
            'Private checkpoint requires exactly the selected pair memberships')
    for member, area in zip(members, verified_bindings['selected_pair']):
        require(type(member) is dict and set(member) == {'map_id', 'domain', 'native_affinity', 'region_key'}
                and type(member['map_id']) is int and member['map_id'] == area
                and type(member['domain']) is str and member['domain'] == 'SPECIAL'
                and type(member['native_affinity']) is int and member['native_affinity'] == 0
                and type(member['region_key']) is int and member['region_key'] == row.region_key,
                'Private checkpoint has an unselected map/domain/affinity/region membership')
    preview_members = tuple(RegionMembership(area, Domain.SPECIAL, 0, row.region_key)
                            for area in verified_bindings['selected_pair'])
    return Registry.compile((*control.records, row), memberships=(*control.memberships, *preview_members),
                            epoch=control.epoch, source_rom_sha256=control.source_rom_sha256)


def emit_runtime_asm(registry):
    """Return separate unplaced constants/table text from compiled registry bytes."""
    require(isinstance(registry, Registry), 'ASM emission requires a compiled checkpoint registry')
    constants = ('; Source-bound checkpoint registry; placement/admission remains with the caller.\n'
                 f'!CHECKPOINT_STATE_SCHEMA = ${SCHEMA:02X}\n'
                 f'!CHECKPOINT_REGISTRY_EPOCH = ${registry.epoch:02X}\n'
                 f'!CHECKPOINT_REGISTRY_COUNT = {len(registry.records)}\n'
                 f'!CHECKPOINT_REGION_MEMBER_COUNT = {len(registry.memberships)}\n')
    lines = ['; Exact Registry.runtime_tables() bytes; no org, cache inference or save writes.']
    for name, raw in registry.runtime_tables().items():
        lines.append(name+':')
        for start in range(0, len(raw), 16):
            lines.append('  db '+','.join(f'${byte:02X}' for byte in raw[start:start+16]))
        lines.append(f'assert pc()-{name} == ${len(raw):04X}')
    return dict(constants=constants, tables='\n'.join(lines)+'\n')


def private_preview_cache(source, document, landing, recipe):
    """Derive a complete interior A0 cache; no allocation or gameplay grant.

    Reuse current Small-area transition lowering and the qualified cached-exit
    ABI. This first preview refuses camera clamping and nonzero collision; it
    does not invent a native entrance or transplant the Goron coordinates.
    """
    import struct
    import lyra_current_transfer as T
    import lyra_native_loaders as N
    import lyra_project_admission as A
    require(type(source) is bytes and len(source) in (0x200000, 0x400000),
            'Private landing requires exact saved ROM bytes')
    keys = {'kind', 'scope', 'source_rom_sha256', 'document_sha256', 'map_id',
            'parent_map', 'local_pixel', 'region_key', 'clear_radius', 'tile16_id',
            'tile_attributes', 'grid_sha256', 'geometry_source'}
    require(type(landing) is dict and set(landing) == keys and
            landing['kind'] == 'checkpoint.private_landing.v1' and
            landing['scope'] == 'seeded_A0_A1_only' and
            landing['source_rom_sha256'] == hashlib.sha256(source).hexdigest() and
            landing['document_sha256'] == T._document_identity(document),
            'Private landing source/document binding differs')
    require(type(landing['map_id']) is int and landing['map_id'] == 0xA0 and
            type(landing['parent_map']) is int and landing['parent_map'] == 0xA0 and
            type(landing['region_key']) is int and 0 < landing['region_key'] < 0xFFFF,
            'Private landing must explicitly select A0 parent and region')
    point = landing['local_pixel']
    require(type(point) is list and len(point) == 2 and
            all(type(n) is int and n % 16 == 0 for n in point) and
            120 <= point[0] <= 376 and 80 <= point[1] <= 398 and
            type(landing['clear_radius']) is int and landing['clear_radius'] == 4,
            'Private landing requires an interior tile anchor and four-tile clearance')
    require(type(recipe) is dict and set(recipe) == {'A0', 'A1'} and
            all(type(recipe[k]) is dict for k in recipe) and
            type(recipe['A0'].get('area_gfx')) is int and 0 <= recipe['A0']['area_gfx'] <= 255,
            'Private landing requires the same selected A0/A1 runtime recipe')
    grid = document.maps[0]
    require(len(grid) == 1024 and all(type(t) is int and 0 <= t < 4096 for t in grid) and
            landing['grid_sha256'] == hashlib.sha256(struct.pack('<1024H', *grid)).hexdigest(),
            'Private landing grid differs')
    x, y = (n // 16 for n in point)
    tile = grid[y * 32 + x]
    require(type(landing['tile16_id']) is int and landing['tile16_id'] == tile and
            landing['tile_attributes'] == [0, 0, 0, 0] and
            all(type(n) is int for n in landing['tile_attributes']),
            'Private landing must bind plain walkable quarters')
    atlas = A.pc(int.from_bytes(source[0x865:0x868], 'little'))
    require(atlas + 0x8000 <= len(source), 'Private landing Tile16 atlas is truncated')
    def attributes(tile_id):
        words = struct.unpack('<4H', source[atlas + tile_id * 8:atlas + tile_id * 8 + 8])
        return [source[0x71459 + (word & 0x1FF)] for word in words]
    for yy in range(y - 4, y + 5):
        for xx in range(x - 4, x + 5):
            require(0 <= xx < 32 and 0 <= yy < 32 and
                    attributes(grid[yy * 32 + xx]) == [0, 0, 0, 0],
                    'Private landing clearance contains a blocked collision quarter')
    pilot = N.plan_private_pilot_boundaries(document, [
        dict(parent_map_id=a, size='small', maps=[a]) for a in (0xA0, 0xA1)])
    view = N.private_pilot_document(document, pilot)
    row = A.gameplay_transition_rows(source, view, private_pilot=True)[0xA0]
    properties = N.current_property_rows(document, source=source)[0xA0]
    px, py = point[0] + row['transition_x'], point[1] + row['transition_y']
    sx, sy = px - 120, py - 80
    # Both existing source-qualified cache records (Goron and SwordWarp) use
    # this 16px-aligned stripe origin; 8px alignment would produce wrong tiles.
    origin = ((sy & 0x1F0) << 3) | ((sx & 0x1F0) >> 3)
    words = [0xA0, 0x16, sy, sx, py, px, 0xA0, origin, py + 31, px + 7,
             row['transition_y'], row['transition_y'] + 0x11E,
             row['transition_x'], row['transition_x'] + 0x100,
             row['scroll_north'], (row['scroll_north'] + 0x2E0) & 0xFFFF,
             row['scroll_west'], (row['scroll_west'] + 0x300) & 0xFFFF,
             0x2000, (recipe['A0']['area_gfx'] | 0x20) |
             properties['special_sprite_gfx'] << 8, 0, 0, 0, 0, 0]
    cache = struct.pack('<25H', *words)
    return cache, dict(map_id=0xA0, parent_map=0xA0, region_key=landing['region_key'],
        local_pixel=list(point), world_pixel=[px, py], scroll=[sx, sy], tilemap_origin=origin,
        tile16_id=tile, tile_attributes=attributes(tile), clear_radius=4,
        native_exit_walk_y=19, stable_after_walk=[px, py + 19],
        cache_sha256=hashlib.sha256(cache).hexdigest(), native_gameplay_verified=False)


def bind_private_preview(project, base_rom, request_path, profile, plan_binding, landing_binding):
    """Reconstruct the live private registry; callers cannot copy plan claims."""
    from pathlib import Path
    import lyra_current_transfer as T
    import lyra_project_prepare as Q
    request, source, document = T.verify_transfer(request_path, project, base_rom)
    T.verify_current_native_source_profile(profile, source, document)
    defines = profile['selected_source']['defines']
    require(defines.get('ENABLE_REGIONAL_CHECKPOINTS') == 1 and
            defines.get('ENABLE_REGIONAL_CHECKPOINT_SOURCE_BINDING') == 1,
            'Private checkpoint requires its enabled/source-bound engine profile')
    plan = json.loads(Q.read_bound(plan_binding))
    landing = json.loads(Q.read_bound(landing_binding))
    ledger = json.loads(Path(T.R.LEDGER).read_bytes())
    policies = [p for p in ledger.get('current_save_transfer_policies', [])
                if p['id'] == request['allocation_policy_id']]
    require(len(policies) == 1, 'Private checkpoint allocation policy is absent')
    runtime = policies[0].get('current_runtime', {})
    require(runtime.get('kind') == 'lyra.private_checkpoint_preview_policy.v1' and
            runtime.get('scope') == 'seeded_checkpoint_preview' and
            runtime.get('private_checkpoint') == dict(plan=plan_binding, landing=landing_binding),
            'Private checkpoint policy bindings differ')
    recipe_binding = runtime['tail_recipe']
    recipe = json.loads(Q.read_bound(recipe_binding))
    engine = Path(profile['selected_source']['root'])
    require(hashlib.sha256((engine / 'Scripts/Build/checkpoint_registry.py').read_bytes()).hexdigest()
            == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'Private checkpoint binder differs from the selected engine source')
    required_sources = ('Scripts/Build/checkpoint_registry.py', 'Overworld/checkpoint_state.asm',
                        'Overworld/goron_checkpoint.asm', 'Overworld/ZSCustomOverworld.asm',
                        'Oracle_main.asm', 'Core/sram.asm')
    inputs = [plan_binding, landing_binding, recipe_binding, Q.bound(T.R.LEDGER),
              *[Q.bound(engine / name) for name in required_sources]]
    geometry = Q.bound(engine / 'Overworld/ZSCustomOverworld.asm')
    require(landing['geometry_source'] == geometry, 'Private camera source binding differs')
    Q.read_bound(geometry)
    cache, derived = private_preview_cache(source, document, landing, recipe)
    bindings = dict(source_rom_sha256=hashlib.sha256(source).hexdigest(),
        document_sha256=T._document_identity(document), transfer_id=request['transfer_id'],
        live={key: request['live'][key] for key in ('generation', 'operation_id', 'save_receipt')},
        selected_pair=[0xA0, 0xA1], cache_source=landing_binding)
    registry = runtime_registry(source, (engine / 'Overworld/goron_checkpoint.asm').read_text(),
        private_plan=plan, verified_bindings=bindings, expected_cache=cache)
    require(registry.records[1].region_key == landing['region_key'],
            'Private checkpoint landing and registry region differ')
    for row in inputs:
        Q.read_bound(row)
    return registry, dict(plan=plan, bindings=bindings, cache_hex=cache.hex(),
                          inputs=inputs, derived=derived)


def verify_runtime_tables(registry, image, symbols):
    """Check actual placed tables against all explicit registry bytes, read-only."""
    require(isinstance(registry, Registry) and type(image) is bytes,
            'Compiled table verification requires registry and ROM bytes')
    first, offset = None, 0
    for name, expected in registry.runtime_tables().items():
        address = symbols.get('Oracle_'+name)
        require(type(address) is int and CODE_BASE <= address <= CODE_LIMIT,
                'Missing/out-of-range compiled checkpoint table '+name)
        if first is None:
            first = address
        require(address == first+offset, 'Compiled checkpoint table layout differs: '+name)
        pc = ((address >> 16) & 0x7F)*0x8000+(address & 0x7FFF)
        require(image[pc:pc+len(expected)] == expected,
                'Compiled checkpoint table/cache disagrees with source: '+name)
        offset += len(expected)
    require(first+offset <= CODE_LIMIT, 'Compiled checkpoint tables exceed their reservation')
    return dict(first_data=first, end=first+offset, data_bytes=offset)


def validate_runtime_capacity(registry, code_bytes, limit=CODE_LIMIT):
    require(type(code_bytes) is int and code_bytes >= 0, 'Checkpoint code size must be explicit')
    payload = sum(len(value) for value in registry.runtime_tables().values())
    require(CODE_BASE + code_bytes + payload <= limit,
            f'Checkpoint aggregate exceeds {limit:06X}: {code_bytes}+{payload} bytes')
    return dict(code_bytes=code_bytes, data_bytes=payload, aggregate_bytes=code_bytes+payload,
                limit=limit, remaining=limit-CODE_BASE-code_bytes-payload)


def verify_compiled_checkpoint(root, base_rom, image, symbols, *, require_prefix=True,
                               private_plan=None, verified_bindings=None, expected_cache=None):
    """Read-only compiled consumer/data check; partial CPU fixture is never admission."""
    qualify_native_control(base_rom)
    registry = runtime_registry(base_rom, (root/'Overworld/goron_checkpoint.asm').read_text(),
                                private_plan=private_plan, verified_bindings=verified_bindings,
                                expected_cache=expected_cache)
    def symbol(name):
        key = 'Oracle_'+name
        require(key in symbols, 'Missing compiled checkpoint consumer '+key)
        return symbols[key]
    def pc(a):
        return ((a >> 16) & 0x7F)*0x8000+(a & 0x7FFF)
    def read(a, count):
        return image[pc(a):pc(a)+count]
    first_data = symbol('CheckpointRegistry_Keys')
    end = symbol('Checkpoint_StateCodeEnd')
    require(symbol('Checkpoint_StateCodeBegin') == CODE_BASE and end <= CODE_LIMIT,
            'Compiled checkpoint aggregate moved/exceeds the reserved interval')
    tables = verify_runtime_tables(registry, image, symbols)
    footprint = validate_runtime_capacity(registry, first_data-CODE_BASE)
    require(CODE_BASE+footprint['aggregate_bytes'] == end,
            'Unexpected bytes/gap outside the checkpoint aggregate contract')
    require(tables['end'] == end, 'Compiled checkpoint table end differs from the aggregate end')
    for site, name in ((0x09F540,'Checkpoint_PrepareAndReset'), (0x02A5A2,'Checkpoint_FrameAndLink'),
                       (0x0CD049,'Checkpoint_ColdContext')):
        require(read(site,4) == b'\x22'+symbol(name).to_bytes(3,'little'),
                f'Checkpoint hook consumer moved at {site:06X}')
    require(read(0x0CD04D,2) == b'\xEA\xEA', 'Cold-copy continuation padding changed')
    for wrapper, target in (('Checkpoint_PrepareAndReset',0x0BFFBF),('Checkpoint_FrameAndLink',0x078000)):
        require(read(symbol(wrapper)+4,4) == b'\x5C'+target.to_bytes(3,'little'),
                'Checkpoint wrapper lost its original native tail call: '+wrapper)
    if require_prefix:
        prefix = symbol('Checkpoint_OrdinaryOverworldEnd')
        require(prefix >> 16 == 0x34 and prefix <= CODE_BASE,
                'Fresh ordinary Overworld prefix overlaps the checkpoint range')
        loader = symbol('LoadCheckpointOrWorld')
        require(read(0x028192,4) == b'\x5C'+loader.to_bytes(3,'little'),
                'Module05 checkpoint owner hook changed')
        span = read(loader, symbol('LyraHost_LoadCheckpointOrWorld_End')-loader)
        require(b'\x22'+symbol('Checkpoint_Load').to_bytes(3,'little') in span,
                'Existing file-load owner does not call the central resolver')
    report = dict(kind='checkpoint.compiled_contract.v1', passed=True, prefix_bound=require_prefix,
                source_rom_sha256=hashlib.sha256(base_rom).hexdigest(),
                output_rom_sha256=hashlib.sha256(image).hexdigest(), registry_sha256=registry.content_sha256,
                checkpoint_count=len(registry.records), **footprint)
    if private_plan is not None:
        report.update(private_seeded_preview=True, production_admission=False,
                      private_plan_sha256=hashlib.sha256(json.dumps(private_plan, sort_keys=True,
                        separators=(',', ':')).encode()).hexdigest(),
                      transfer_id=verified_bindings['transfer_id'],
                      generation=verified_bindings['live']['generation'],
                      operation_id=verified_bindings['live']['operation_id'])
    return report


def main():
    import argparse
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'Generate'))
    from asm_source import _load_global_defines
    from allocation_contracts import read_symbols
    parser = argparse.ArgumentParser(description='Read-only shared checkpoint source/compiled binding check')
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--base-rom', type=Path, required=True)
    parser.add_argument('--rom', type=Path)
    parser.add_argument('--symbols', type=Path)
    parser.add_argument('--no-symbols', action='store_true')
    args = parser.parse_args()
    flags = _load_global_defines(args.root)
    if not flags.get('REGIONAL_CHECKPOINTS_ENABLED'):
        print('{"selected":false,"status":"disabled"}')
        return
    require(flags.get('REGIONAL_CHECKPOINTS_BOUND') == 1, 'Checkpoint source binding flag is absent')
    require(flags.get('DISABLE_OVERWORLD') == 0, 'Checkpoint runtime requires its existing Overworld owner')
    require(not args.no_symbols, 'Checkpoint runtime requires compiled symbols; remove --no-symbols')
    base = args.base_rom.read_bytes()
    qualify_native_control(base)
    registry = goron_control_registry(base, (args.root/'Overworld/goron_checkpoint.asm').read_text())
    private = {}
    if flags.get('LYRA_PRIVATE_CHECKPOINT_ENABLED') == 1:
        prepared = json.loads((args.root/'Data/Generated/lyra_project/prepare.json').read_bytes())
        selection = prepared.get('checkpoint_preview')
        require(prepared.get('runtime_scope') == 'seeded_checkpoint_preview' and
                type(selection) is dict and set(selection) == {'plan_binding', 'landing_binding'},
                'Private checkpoint requires a reconstructed scoped preparation')
        registry, context = bind_private_preview(prepared['project'], args.base_rom,
            prepared['request'], prepared['current_source_profile'],
            selection['plan_binding'], selection['landing_binding'])
        private = dict(private_plan=context['plan'], verified_bindings=context['bindings'],
                       expected_cache=bytes.fromhex(context['cache_hex']))
    if args.rom:
        require(args.symbols is not None, 'Checkpoint runtime requires exact compiled symbols')
        report = verify_compiled_checkpoint(args.root, base, args.rom.read_bytes(), read_symbols(args.symbols),
                                           **private)
    else:
        report = dict(selected=True, status='source_control_bound', source_rom_sha256=registry.source_rom_sha256,
                      registry_sha256=registry.content_sha256, checkpoint_count=len(registry.records),
                      claim='native source-qualified Goron control; no Lyra entry or gameplay qualification')
        if private:
            report.update(status='private_preview_source_bound', production_admission=False,
                          claim='Bound seeded A0 preview data only; native gameplay qualification pending')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
