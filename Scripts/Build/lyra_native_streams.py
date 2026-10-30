"""Pure native stream/profile primitives from the reviewed C1 intake. No allocation grant."""

import lyra_project_admission as A
import lyra_project_allocation as R

POINTER_TABLES = (0x02F94D, 0x02FB2D)

class _ReadTrace:
    """Observe the existing decoder's actual byte reads; no second codec."""
    def __init__(self, source):
        self.source, self.first, self.last = source, None, None

    def __getitem__(self, offset):
        self.first = offset if self.first is None else min(self.first, offset)
        self.last = offset if self.last is None else max(self.last, offset)
        return self.source[offset]

def _plane(source, area, table):
    at = A.pc(table) + area * 3
    pointer = int.from_bytes(source[at:at + 3], 'little')
    trace = _ReadTrace(source)
    decoded = A._decode_plane(trace, pointer)
    return bytes(decoded), pointer, [trace.first, trace.last + 1]

def reject_stream_aliases(source, stream_spans):
    reads = []
    for area in range(160):
        for table in POINTER_TABLES:
            decoded, pointer, span = _plane(source, area, table)
            R.require(all(span[1] <= start or span[0] >= end for start, end in stream_spans),
                      f'Reserved streams alias native map{area:02X}')
            reads.append(dict(map_id=area, table=table, pointer=pointer, pc=span,
                              decoded_sha256=R.sha(decoded)))
    return reads

def _native_grid(planes, definitions):
    grid = [[0] * 32 for _ in range(32)]
    for cell, (high, low) in enumerate(zip(*planes)):
        quad = definitions[high << 8 | low]
        y, x = divmod(cell, 16)
        grid[y * 2][x * 2:x * 2 + 2] = quad[:2]
        grid[y * 2 + 1][x * 2:x * 2 + 2] = quad[2:]
    return grid

def native_profile(source, area):
    """The accepted v3 parent/default selectors, read from actual native rows.

    Table addresses reuse the admission contract. Native light/dark sprite
    phases use their original tables; special maps use the special selectors.
    """
    R.require(type(area) is int and 0 <= area < 160, 'Native profile map must be00..9F')
    R.require(source[0x140145] == 3 and all(source[p] for p in (0x140141, 0x140143, 0x140148)),
              'Unsupported native v3 profile controls')

    def row(name, index, count=None):
        spec = next(s for s in A.SPECS if s[0] == name)
        at = A.pc(spec[1]) + (index - spec[3]) * spec[5]
        return source[at:at + (count or spec[5])]

    parent = row('parent', area)[0]
    R.require(parent < 160, 'Native profile parent exceeds source tables')
    explicit = list(row('gfx', parent))
    defaults_at = A.pc(0x288980) + ((parent & 0xC0) >> 3)
    defaults = list(source[defaults_at:defaults_at + 8])
    sheets = [defaults[i] if value == 255 else value for i, value in enumerate(explicit)]
    animated = row('animated', parent)[0]
    if animated in (0, 255):
        animated = defaults[7]
    if area < 128:
        sprites = [source[0x7A41 + parent + phase * 64] for phase in range(3)]
        palettes = [source[0x7B41 + parent + phase * 64] for phase in range(3)]
    else:
        R.require(parent >= 128, 'Special native profile has a non-special parent')
        sprites = [row('special_sprite_gfx', parent)[0]] * 3
        palettes = [row('special_sprite_palettes', parent)[0]] * 3
    return dict(map_id=area, parent=parent, size=row('area_size', area)[0],
        graphics_sheets=sheets, explicit_graphics_sheets=explicit, default_graphics_sheets=defaults,
        main_palette=row('main_palette', parent)[0], palette_set=row('palette_set', parent)[0],
        animated_sheet=animated, area_specific_bg_color=int.from_bytes(row('bg_color', parent), 'little'),
        sprite_graphics=sprites, sprite_palettes=palettes,
        subscreen_overlay=int.from_bytes(row('overlay', parent), 'little') if source[0x140144] else 255,
        protected_overlay_artifact=None, raw_child_custom_graphics=list(row('gfx', area)))
