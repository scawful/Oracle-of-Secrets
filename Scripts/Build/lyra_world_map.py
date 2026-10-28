#!/usr/bin/env python3
"""Plan Lyra's atlas from a current native Save; never emit ROM writes.

The Tile16 lattice is an input for atlas authoring, not Mode7 artwork. No
palette, map-screen projection or runtime storage is selected by this tool.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from dataclasses import dataclass
import json
from pathlib import Path
import struct

import lyra_current_transfer as current
import lyra_native_loaders as native
import lyra_project_admission as A
import lyra_project_prepare as Q
import lyra_project_publisher as P
from lyra_project_terrain import FIRST_MAP, MAP_COUNT, MAP_SIZE, TerrainDocument


KIND = 'lyra.world_map_source_plan.v1'
COLUMNS, ROWS, TILE_PIXELS = 8, 4, 16
CELL_PIXELS = MAP_SIZE * TILE_PIXELS


@dataclass(frozen=True)
class AtlasRoute:
    domain: str
    atlas: str
    marker: str
    prizes: str | None
    role: str


@dataclass(frozen=True)
class AtlasPlan:
    document_sha256: str
    tile16_grid: bytes
    routes: tuple[AtlasRoute, ...]
    overlay_templates: tuple[int, ...]
    protected_storage: tuple[int, int]
    selected_maps: tuple[int, ...]

    def select(self, map_id: int) -> AtlasRoute:
        A.require(type(map_id) is int and 0 <= map_id < len(self.routes),
                  'WORLD_MAP_DOMAIN_UNADMITTED: physical map must be 00..BF')
        return self.routes[map_id]

    def runtime_selection(self, map_id: int) -> AtlasRoute:
        route = self.select(map_id)
        A.require(route.atlas != 'lyra',
                  'LYRA_WORLD_MAP_ASSETS_UNBOUND: atlas art, palette, marker projection and hooks required')
        return route

    def document_marker(self, map_id: int, local_x: int, local_y: int) -> tuple[int, int]:
        """Project cell-local pixels into the document, not native map-screen WRAM.

        Native Link coordinates are camera/parent-relative. The caller must
        first derive cell-local coordinates from the bound current tables.
        Silently masking a native coordinate would hide a wrong parent/cell.
        """
        A.require(self.select(map_id).atlas == 'lyra',
                  'WORLD_MAP_MARKER_DOMAIN_MISMATCH: Lyra document coordinates required')
        A.require(all(type(v) is int and 0 <= v < CELL_PIXELS for v in (local_x, local_y)),
                  'WORLD_MAP_MARKER_OUTSIDE_CELL: explicit cell-local pixels required')
        row, column = divmod(map_id - FIRST_MAP, COLUMNS)
        return column * CELL_PIXELS + local_x, row * CELL_PIXELS + local_y

    def report(self) -> dict:
        return dict(kind=KIND, scope='source_only', document_sha256=self.document_sha256,
            lattice=dict(file='lyra.tile16.bin', encoding='u16le_tile16_ids',
                width=COLUMNS * MAP_SIZE, height=ROWS * MAP_SIZE,
                bytes=len(self.tile16_grid), sha256=A.sha(self.tile16_grid),
                artwork=False),
            marker=dict(coordinate_space='lyra_document_pixels',
                width=COLUMNS * CELL_PIXELS, height=ROWS * CELL_PIXELS,
                native_projection=None),
            routes=[dict(map_id=i, **vars(route)) for i, route in enumerate(self.routes)],
            protected_overlay_templates=list(self.overlay_templates),
            protected_legacy_storage_span=list(self.protected_storage),
            runtime_selected_maps=list(self.selected_maps),
            required_assets=dict(mode7_tilemap_bytes=0x1000, mode7_graphics_bytes=0x4000,
                palette_bytes=0x100, palette_colors=128, addresses=None),
            # A complete saved terrain is not evidence that every cell is playable.
            atlas_art_bound=False, marker_projection_bound=False,
            allocation_granted=False, runtime_admission=False, rom_written=False)


def plan(document: TerrainDocument, boundary: dict) -> AtlasPlan:
    """Consume the existing canonical boundary and preserve its named roles."""
    A.require(isinstance(document, TerrainDocument) and type(boundary) is dict,
              'WORLD_MAP_SAVED_DOCUMENT_REQUIRED')
    expected = native.plan_private_pilot_boundaries(document, boundary.get('selected_areas'))
    A.require(boundary == expected, 'WORLD_MAP_BOUNDARY_STALE: canonical saved-document boundary required')
    A.require(len(document.maps) == MAP_COUNT
              and all(len(cells) == MAP_SIZE ** 2 for cells in document.maps)
              and all(type(tile) is int and 0 <= tile < document.profile['tile_count']
                      for cells in document.maps for tile in cells),
              'WORLD_MAP_TERRAIN_MALFORMED: all saved Tile16 cells required')
    protected = tuple(boundary['protected_legacy_storage_span'])
    templates = tuple(boundary['named_overlay_templates'])
    A.require(all(protected[0] <= i <= protected[1] < FIRST_MAP for i in templates),
              'WORLD_MAP_PROTECTED_ROLES_INVALID')
    routes = []
    for map_id in range(FIRST_MAP + MAP_COUNT):
        if map_id < 0x40:
            route = AtlasRoute('light', 'light', 'native_live', 'light', 'native')
        elif map_id < 0x80:
            route = AtlasRoute('dark', 'dark', 'native_live', 'dark', 'native')
        elif map_id < FIRST_MAP:
            # Native special areas retain their existing Light atlas and cached
            # marker. Template identity is explicit, not inferred from bit 7.
            role = ('overlay_template' if map_id in templates else
                    'preserved_storage' if protected[0] <= map_id <= protected[1] else
                    'native_special')
            route = AtlasRoute('special', 'light', 'native_cached', 'light', role)
        else:
            route = AtlasRoute('special', 'lyra', 'document_cell', None, 'saved_terrain')
        routes.append(route)
    lattice = bytearray()
    for grid_y in range(ROWS * MAP_SIZE):
        map_row, local_y = divmod(grid_y, MAP_SIZE)
        for map_column in range(COLUMNS):
            cells = document.maps[map_row * COLUMNS + map_column]
            start = local_y * MAP_SIZE
            lattice.extend(struct.pack('<32H', *cells[start:start + MAP_SIZE]))
    return AtlasPlan(current._document_identity(document), bytes(lattice), tuple(routes),
                     templates, protected, tuple(boundary['allowed_tail_maps']))


def from_transfer(request_path, project, base_rom) -> tuple[AtlasPlan, dict, list[str]]:
    """Use the ordinary build's native-Save verifier and immutable snapshot.

    candidate_inspection admits an existing target only as an unchanged input;
    it does not reopen publication or bypass a stale Save/producer/terrain pin.
    """
    request_binding = Q.bound(request_path)
    request = json.loads(Q.read_bound(request_binding))
    target = Path(request['target']['path'])
    inspection = current.candidate_inspection(target) if target.exists() else nullcontext()
    with inspection:
        request, source, document = current.verify_transfer(request_path, project, base_rom)
        boundary = current.native_checkpoint_boundaries(document)
        result = plan(document, boundary)
        binding = dict(request=request_binding, transfer_id=request['transfer_id'],
            generation=request['live']['generation'], operation_id=request['live']['operation_id'],
            source_rom_sha256=A.sha(source), terrain=request['inputs']['terrain'])
        protected = [str(project), str(base_rom), str(target), request_binding['path'],
                     *[row['path'] for row in request['inputs'].values()],
                     *[row['path'] for row in request['live']['inputs'].values()]]
        Q.read_bound(request_binding)
    return result, binding, protected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
        epilog='Requires the same YAZE_NATIVE_SAVE_CONTEXT as the current native-Save build.')
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--base-rom', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        A.require(not args.output.exists(), 'WORLD_MAP_OUTPUT_EXISTS: use a new planning folder')
        atlas, binding, protected = from_transfer(args.request, args.project, args.base_rom)
        report = dict(atlas.report(), saved_source=binding)
        P.write_outputs(args.output, {'lyra.tile16.bin': atlas.tile16_grid,
            'WORLD_MAP_PLAN.json': P.encoded(report)}, protected=protected)
        print(json.dumps(dict(kind=KIND, status='SOURCE_READY_RUNTIME_UNBOUND',
            output=str(args.output), lattice_sha256=A.sha(atlas.tile16_grid),
            generation=binding['generation'], runtime_admission=False), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps(dict(kind=KIND, status='REFUSED', error=str(error)), sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
