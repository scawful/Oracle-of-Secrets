"""Pure parser, validator and normalizer for oracle.native-terrain-delta manifests.

Never writes a ROM, grants Tile32 IDs, or copies fixture stream/PC witnesses into
production requests. Reconstruction uses the agreed encoded_grid / qkey / quad /
reconstruct contract shared with the read-only route extractors.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from lyra_project_allocation import require, sha

SCHEMA = 'oracle.native-terrain-delta'
SCHEMA_VERSION = 1
NORMALIZED_KIND = 'lyra.project_terrain_delta_normalized.v1'
ENCODING_COMPILER_MODE = (
    'source-bound sparse native-map delta; unchanged blocks inherit pinned source')
ENCODING_GRID_HASH = 'SHA256 of1024little-endian uint16 values, row-major32x32'
ENCODING_QUAD_LOGICAL_ID = 'q16:TL:TR:BL:BR lowercase4hex Tile16 IDs'
ENCODING_QUAD_ORDER = ['top_left', 'top_right', 'bottom_left', 'bottom_right']
ENCODING_TILE16_DELTA_ROW = [
    'x_tile16', 'y_tile16', 'source_tile16', 'target_tile16']
ENCODING_TILE32_DELTA_ROW = [
    'x_tile32', 'y_tile32', 'source_quad_logical_id', 'target_quad_logical_id']
NATIVE_COMPILER_MAP_ID_MAX = 159
LYRA_PROVENANCE_MAP_ID_MAX = 191
_QUAD_KEY = re.compile(
    r'^q16:([0-9a-f]{4}):([0-9a-f]{4}):([0-9a-f]{4}):([0-9a-f]{4})$')


def encoded_grid(grid: list[list[int]]) -> bytes:
    require(len(grid) == 32 and all(len(row) == 32 for row in grid),
            'Native map grid must be 32x32 Tile16 cells')
    return struct.pack('<1024H', *(cell for row in grid for cell in row))


def qkey(quad: list[int] | tuple[int, ...]) -> str:
    require(len(quad) == 4 and all(type(v) is int and 0 <= v < 4096 for v in quad),
            'Tile32 logical quad must be four 12-bit Tile16 IDs')
    return 'q16:' + ':'.join(f'{v:04x}' for v in quad)


def quad_at(grid: list[list[int]], x: int, y: int) -> list[int]:
    require(0 <= x < 31 and 0 <= y < 31 and y + 1 < 32 and x + 1 < 32,
            'Tile32 block origin out of range')
    return [grid[y][x], grid[y][x + 1], grid[y + 1][x], grid[y + 1][x + 1]]


def content_sha256(quad: list[int] | tuple[int, ...]) -> str:
    return sha(struct.pack('<4H', *quad))


def parse_quad_key(key: str) -> tuple[int, int, int, int]:
    match = _QUAD_KEY.fullmatch(key)
    require(match is not None, f'Invalid logical quad id: {key}')
    return tuple(int(part, 16) for part in match.groups())


def load_manifest(path: str | Path, *, expected_sha256: str | None = None) -> dict:
    data = Path(path).read_bytes()
    digest = sha(data)
    require(expected_sha256 is None or digest == expected_sha256,
            'Terrain delta manifest SHA256 differs from pinned input')
    return json.loads(data.decode())


def _fingerprint(value: object) -> bool:
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _validate_encoding(encoding: object) -> None:
    require(type(encoding) is dict, 'Malformed terrain delta encoding')
    require(encoding.get('compiler_mode') == ENCODING_COMPILER_MODE,
            'Unsupported terrain delta compiler_mode')
    require(encoding.get('grid_hash') == ENCODING_GRID_HASH,
            'Unsupported terrain delta grid_hash encoding')
    require(encoding.get('quad_logical_id') == ENCODING_QUAD_LOGICAL_ID,
            'Unsupported terrain delta quad_logical_id encoding')
    require(encoding.get('quad_order') == ENCODING_QUAD_ORDER,
            'Unsupported terrain delta quad_order')
    require(encoding.get('tile16_delta_row') == ENCODING_TILE16_DELTA_ROW,
            'Unsupported terrain delta tile16_delta_row field order')
    require(encoding.get('tile32_delta_row') == ENCODING_TILE32_DELTA_ROW,
            'Unsupported terrain delta tile32_delta_row field order')


def _validate_inputs(inputs: object) -> dict[str, str]:
    require(type(inputs) is dict, 'Malformed terrain delta inputs')
    pinned = {}
    for key in ('source_rom', 'candidate_fixture_rom', 'project', 'recipe'):
        entry = inputs.get(key)
        require(type(entry) is dict and _fingerprint(entry.get('sha256'))
                and type(entry.get('path')) is str and entry['path'],
                f'Malformed terrain delta input {key}')
        pinned[key] = entry['sha256']
    for key in ('tile16_definitions_sha256', 'collision_table_sha256'):
        require(_fingerprint(inputs.get(key)), f'Missing pinned {key}')
        pinned[key] = inputs[key]
    if 'tile32_definitions_sha256' in inputs:
        require(_fingerprint(inputs['tile32_definitions_sha256']),
                'Invalid tile32_definitions_sha256')
        pinned['tile32_definitions_sha256'] = inputs['tile32_definitions_sha256']
    if 'lyra_sidecar_sha256' in inputs:
        require(_fingerprint(inputs['lyra_sidecar_sha256']), 'Invalid lyra_sidecar_sha256')
        pinned['lyra_sidecar_sha256'] = inputs['lyra_sidecar_sha256']
    return pinned


def _validate_quad_library(library: object) -> dict[str, dict]:
    require(type(library) is dict and library, 'Terrain delta quad_library required')
    for key, entry in library.items():
        parse_quad_key(key)
        require(type(entry) is dict and set(entry) == {'tile16', 'content_sha256'},
                'Malformed quad_library entry')
        tile16 = entry['tile16']
        require(type(tile16) is list and len(tile16) == 4
                and all(type(v) is int and 0 <= v < 4096 for v in tile16),
                'Invalid quad_library tile16')
        require(entry['content_sha256'] == content_sha256(tile16),
                'quad_library content_sha256 differs from tile16 preimage')
        require(qkey(tile16) == key, 'quad_library key does not match tile16 order')
    return library


def _validate_map_delta(entry: object, library: Mapping[str, dict]) -> None:
    require(type(entry) is dict and type(entry.get('map_id')) is int,
            'Malformed terrain delta map')
    require(type(entry.get('source_grid_sha256')) is str
            and _fingerprint(entry['source_grid_sha256'])
            and _fingerprint(entry.get('target_grid_sha256')),
            'Malformed map grid hashes')
    profile = entry.get('source_profile')
    require(type(profile) is dict, 'Missing source_profile')
    mid = entry['map_id']
    if 'map_id' in profile:
        require(type(profile['map_id']) is int and profile['map_id'] == mid,
                'source_profile.map_id differs from map entry')
    tile16 = entry.get('tile16_delta')
    tile32 = entry.get('tile32_delta')
    require(type(tile16) is list and type(tile32) is list, 'Malformed map deltas')
    seen16, seen32 = set(), set()
    for row in tile16:
        require(type(row) is list and len(row) == 4
                and all(type(v) is int and 0 <= v < 4096 for v in row),
                'Malformed tile16_delta row')
        x, y, before, after = row
        require(0 <= x < 32 and 0 <= y < 32 and (x, y) not in seen16 and before != after,
                'Invalid tile16_delta coordinates or duplicate cell')
        seen16.add((x, y))
    for row in tile32:
        require(type(row) is list and len(row) == 4
                and all(type(v) is int and 0 <= v < 16 for v in row[:2])
                and type(row[2]) is str and type(row[3]) is str,
                'Malformed tile32_delta row')
        bx, by, before, after = row
        require(0 <= bx < 16 and 0 <= by < 16 and (bx, by) not in seen32,
                'Invalid tile32_delta coordinates or duplicate block')
        require(before in library and after in library and before != after,
                'tile32_delta references unknown or unchanged logical quad')
        seen32.add((bx, by))


def _validate_map_list(maps: object, library: Mapping[str, dict], *, minimum: int,
                       maximum: int, label: str) -> None:
    require(type(maps) is list and maps, f'Terrain delta {label} maps required')
    seen: set[int] = set()
    for entry in maps:
        require(type(entry) is dict and type(entry.get('map_id')) is int,
                f'Malformed {label} map entry')
        mid = entry['map_id']
        require(minimum <= mid <= maximum,
                f'{label} map_id {mid} outside supported range {minimum}..{maximum}')
        require(mid not in seen, f'Duplicate {label} map_id')
        seen.add(mid)
        _validate_map_delta(entry, library)


def _validate_fixture(fixture: object) -> None:
    if fixture is None:
        return
    require(type(fixture) is dict and fixture.get('must_not_copy_allocations_to_production') is True
            and fixture.get('production_relocation_required') is True,
            'Malformed fixture_evidence_only guard')
    for definition in fixture.get('tile32_definitions', []):
        require(type(definition) is dict and definition.get('production_slot') is None
                and definition.get('relocation_required') is True,
                'Fixture Tile32 witness must not claim production ownership')
    for stream in fixture.get('streams', []):
        if 'production_pc' in stream:
            require(stream['production_pc'] is None,
                    'Fixture stream must not assign production_pc')


def validate_manifest(manifest: object, *, maps_key: str = 'maps') -> None:
    """Refuse malformed manifests before normalization or reconstruction."""
    require(type(manifest) is dict, 'Terrain delta manifest must be a JSON object')
    require(manifest.get('schema') == SCHEMA and manifest.get('schema_version') == SCHEMA_VERSION,
            'Unsupported terrain delta schema')
    require(manifest.get('status') == 'INTEGRATION_INPUT_ONLY_NOT_PRODUCTION_ADMITTED',
            'Terrain delta is not integration-input-only')
    ownership = manifest.get('ownership')
    require(type(ownership) is dict and ownership.get('production_ids_assigned') is False
            and ownership.get('production_streams_assigned') is False,
            'Terrain delta claims production allocation')
    _validate_encoding(manifest.get('encoding'))
    pinned = _validate_inputs(manifest.get('inputs'))
    require(pinned, 'Terrain delta inputs missing')
    library = _validate_quad_library(manifest.get('quad_library'))
    if maps_key == 'maps':
        _validate_map_list(manifest.get('maps'), library, minimum=0,
                           maximum=NATIVE_COMPILER_MAP_ID_MAX, label='Compiler')
    else:
        _validate_map_list(manifest.get(maps_key), library, minimum=0,
                           maximum=NATIVE_COMPILER_MAP_ID_MAX, label=maps_key)
    required = manifest.get('required_changed_block_quads')
    require(type(required) is list and all(key in library for key in required),
            'required_changed_block_quads must reference quad_library')
    new_content = manifest.get('new_content_relative_to_source_used_quads', [])
    require(type(new_content) is list and all(key in library for key in new_content),
            'new_content_relative_to_source_used_quads must reference quad_library')
    _validate_fixture(manifest.get('fixture_evidence_only'))
    provenance = manifest.get('lyra_source_provenance')
    if provenance is not None:
        require(provenance.get('compiler_target_input') is False,
                'Lyra provenance section cannot be compiler target input')
        require(provenance.get('production_ids_assigned') is False
                and provenance.get('production_streams_assigned') is False,
                'Lyra provenance cannot claim production allocation')
        _validate_map_list(provenance.get('maps', []), library, minimum=0,
                           maximum=LYRA_PROVENANCE_MAP_ID_MAX, label='Lyra provenance')


def reconstruct(manifest: Mapping[str, Any], source_grids: Mapping[int, list[list[int]]],
                *, maps_key: str = 'maps',
                quad_library: Mapping[str, dict] | None = None,
                include_fixture: bool = True) -> dict[int, list[list[int]]]:
    """Apply sparse tile16/tile32 deltas to pinned source grids."""
    library = quad_library if quad_library is not None else manifest['quad_library']
    body = dict(manifest)
    if not include_fixture and 'fixture_evidence_only' in body:
        body = {k: v for k, v in body.items() if k != 'fixture_evidence_only'}
    result: dict[int, list[list[int]]] = {}
    for item in body[maps_key]:
        mid = item['map_id']
        require(mid in source_grids, f'Missing source grid for map {mid}')
        cells = copy.deepcopy(source_grids[mid])
        blocks = copy.deepcopy(source_grids[mid])
        require(sha(encoded_grid(cells)) == item['source_grid_sha256'],
                'Source grid hash differs from manifest preimage')
        seen16, seen32 = set(), set()
        for x, y, before, after in item['tile16_delta']:
            require((x, y) not in seen16 and cells[y][x] == before, 'Stale tile16 preimage')
            seen16.add((x, y))
            cells[y][x] = after
        for bx, by, before, after in item['tile32_delta']:
            require((bx, by) not in seen32, 'Duplicate tile32 block')
            x, y = bx * 2, by * 2
            require(qkey(quad_at(blocks, x, y)) == before, 'Stale tile32 preimage')
            seen32.add((bx, by))
            quad = library[after]['tile16']
            blocks[y][x:x + 2] = quad[:2]
            blocks[y + 1][x:x + 2] = quad[2:]
        require(cells == blocks, 'tile16 and tile32 delta paths disagree')
        require(sha(encoded_grid(cells)) == item['target_grid_sha256'],
                'Target grid hash differs after reconstruction')
        result[mid] = cells
    return result


def refuse_fixture_allocation_use(normalized: Mapping[str, Any]) -> None:
    """Reject any normalized request that treats fixture evidence as production."""
    for request in normalized.get('content_requests', []):
        require(request.get('production_slot') is None,
                'Fixture or witness slot cannot become production_slot')
        require(request.get('relocation_required') is True,
                'Unresolved content must keep relocation_required')
        witness = request.get('fixture_candidate_slot')
        if witness is not None:
            require(request.get('production_slot') is None,
                    'Fixture candidate_slot cannot be promoted to production')
    for stream in normalized.get('fixture_witness_streams', []):
        require(stream.get('production_pc') is None,
                'Fixture stream PC cannot be copied to production')


@dataclass(frozen=True)
class NormalizedDelta:
    kind: str
    manifest_name: str
    manifest_sha256: str
    compiler_target_input: bool
    source_identity: dict[str, str]
    maps: tuple[dict, ...]
    content_requests: tuple[dict, ...]
    required_changed_block_quads: tuple[str, ...]
    new_content_relative_to_source_used_quads: tuple[str, ...]
    lyra_source_provenance: dict | None
    fixture_witness_streams: tuple[dict, ...]
    w02_reference_only: dict | None

    def to_dict(self) -> dict:
        return {
            'kind': self.kind,
            'manifest_name': self.manifest_name,
            'manifest_sha256': self.manifest_sha256,
            'compiler_target_input': self.compiler_target_input,
            'source_identity': self.source_identity,
            'maps': list(self.maps),
            'content_requests': list(self.content_requests),
            'required_changed_block_quads': list(self.required_changed_block_quads),
            'new_content_relative_to_source_used_quads': list(self.new_content_relative_to_source_used_quads),
            'lyra_source_provenance': self.lyra_source_provenance,
            'fixture_witness_streams': list(self.fixture_witness_streams),
            'w02_reference_only': self.w02_reference_only,
        }


def _profile_request(profile: Mapping[str, Any]) -> dict:
    keys = ('graphics_sheets', 'main_palette', 'palette_set', 'animated_sheet',
            'sprite_graphics', 'sprite_palettes')
    request = {key: copy.deepcopy(profile[key]) for key in keys if key in profile}
    if 'map_id' in profile:
        request['map_id'] = profile['map_id']
    return request


def _content_requests(manifest: Mapping[str, Any], library: Mapping[str, dict]) -> list[dict]:
    requests = []
    new_keys = set(manifest.get('new_content_relative_to_source_used_quads', []))
    for key in manifest.get('required_changed_block_quads', []):
        entry = library[key]
        requests.append({
            'logical_quad_id': key,
            'tile16': copy.deepcopy(entry['tile16']),
            'content_sha256': entry['content_sha256'],
            'production_slot': None,
            'relocation_required': True,
            'role': 'required_changed_block_quad',
            'new_relative_to_source_used_quads': key in new_keys,
        })
    fixture = manifest.get('fixture_evidence_only') or {}
    for witness in fixture.get('tile32_definitions', []):
        key = witness['logical_quad']
        require(key in library, 'Fixture logical quad missing from quad_library')
        requests.append({
            'logical_quad_id': key,
            'tile16': copy.deepcopy(library[key]['tile16']),
            'content_sha256': library[key]['content_sha256'],
            'production_slot': None,
            'relocation_required': True,
            'fixture_candidate_slot': witness.get('candidate_slot'),
            'fixture_slot_preimage_tile16': copy.deepcopy(
                witness.get('source_slot_preimage_tile16')),
            'role': 'fixture_evidence_only',
            'new_relative_to_source_used_quads': key in new_keys,
        })
    return requests


def normalize_manifest(manifest: Mapping[str, Any], *, manifest_sha256: str) -> NormalizedDelta:
    """Validate and emit canonical compiler-facing requests without allocating."""
    validate_manifest(manifest)
    library = manifest['quad_library']
    maps = []
    for entry in manifest['maps']:
        maps.append({
            'map_id': entry['map_id'],
            'source_grid_sha256': entry['source_grid_sha256'],
            'target_grid_sha256': entry['target_grid_sha256'],
            'profile_request': _profile_request(entry['source_profile']),
            'native_source_profile': copy.deepcopy(entry['source_profile']),
            'tile16_changes': copy.deepcopy(entry['tile16_delta']),
            'tile32_content_changes': copy.deepcopy(entry['tile32_delta']),
        })
    fixture = manifest.get('fixture_evidence_only') or {}
    streams = tuple(copy.deepcopy(stream) for stream in fixture.get('streams', []))
    provenance = manifest.get('lyra_source_provenance')
    provenance_out = None
    if provenance is not None:
        provenance_out = {
            'compiler_target_input': False,
            'common_profile_sha256': provenance.get('common_profile_sha256'),
            'map_summaries': [{
                'map_id': row['map_id'],
                'source_grid_sha256': row['source_grid_sha256'],
                'target_grid_sha256': row['target_grid_sha256'],
                'tile16_change_count': len(row['tile16_delta']),
                'tile32_block_change_count': len(row['tile32_delta']),
                'profile_request': _profile_request(row['source_profile']),
            } for row in provenance.get('maps', [])],
        }
    reference = manifest.get('existing_w02_complete_input_reference_only')
    reference_out = copy.deepcopy(reference) if reference is not None else None
    if reference_out is not None:
        require(reference_out.get('duplicate_or_replace_input') is False
                and reference_out.get('copy_assignments') is False,
                'W02 complete Power input must not be duplicated')
    normalized = NormalizedDelta(
        kind=NORMALIZED_KIND,
        manifest_name=manifest.get('name', ''),
        manifest_sha256=manifest_sha256,
        compiler_target_input=True,
        source_identity=_validate_inputs(manifest['inputs']),
        maps=tuple(maps),
        content_requests=tuple(_content_requests(manifest, library)),
        required_changed_block_quads=tuple(manifest['required_changed_block_quads']),
        new_content_relative_to_source_used_quads=tuple(
            manifest.get('new_content_relative_to_source_used_quads', [])),
        lyra_source_provenance=provenance_out,
        fixture_witness_streams=streams,
        w02_reference_only=reference_out,
    )
    refuse_fixture_allocation_use(normalized.to_dict())
    return normalized


def native_map_grid(source: bytes, map_id: int) -> list[list[int]]:
    """Decode one native map grid from ROM bytes (read-only helper for verification)."""
    import lyra_project_admission as admission

    definitions = {index: admission.read_tile32(source, index) for index in range(0x4540)}
    planes = []
    for table in (0x02F94D, 0x02FB2D):
        pointer = int.from_bytes(
            source[admission.pc(table) + map_id * 3:admission.pc(table) + map_id * 3 + 3],
            'little',
        )
        planes.append(admission._decode_plane(source, pointer))
    tiles = [hi << 8 | lo for hi, lo in zip(*planes)]
    require(len(tiles) == 256, 'Incomplete native Tile32 plane')
    rebuilt = [[0] * 32 for _ in range(32)]
    for cell, tile in enumerate(tiles):
        y, x = divmod(cell, 16)
        quad = definitions[tile]
        for quadrant, value in enumerate(quad):
            rebuilt[(y * 2 + quadrant // 2)][x * 2 + quadrant % 2] = value
    return rebuilt


def native_grids_from_rom(source: bytes, map_ids: tuple[int, ...] | None = None) -> dict[int, list[list[int]]]:
    require(len(source) in (0x200000, 0x400000), 'Expected native ROM size')
    if map_ids is None:
        map_ids = tuple(range(160))
    return {mid: native_map_grid(source, mid) for mid in map_ids}
