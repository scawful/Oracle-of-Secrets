#!/usr/bin/env python3
"""Derive D4 runtime states from the saved canonical Low room on normal Build.

The selected source pair describes a native state transformation; common saved
geometry stays authoritative. Only generated states/runtime tables are written.
The older explicit --write private materializer is retained as a separate action.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import subprocess
import tempfile
import re
from collections import Counter
from dataclasses import dataclass

import sky_d8_room_writer as rooms

SOURCE_SHA256 = 'e1478831c8e34208703296a77a15a63ce597b79cc731efcbfadcfee778448f36'
STREAM_HASHES = {
    '25-low': 'a500a0f2f9326f2eff05b3ca5fb0b938c801e00177dc02ffc19b3f66085836eb',
    '25-high': '50317fed0484137d7d80475a353cca3bd7d33a85a3b01daf2bb121080b54bf2f',
    '37-closed': 'da2fbd2b7d47a4011ea0dd099563be1140b937d4d1645fa04cd70ae971e1ca5b',
    '37-open': '46f02baebdfeb5af46edb13fae3e9e98ef78814e198c4ce61b1a8efa13f9fa15',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


class StateDerivationError(ValueError):
    """The saved canonical room no longer satisfies its selected water kit."""


def object_id(record):
    return (rooms.decode_object(record)[0]
            if record[0] >= 0xfc or record[2] >= 0xf8 else record[2])


def record_xy(record):
    return (rooms.decode_object(record)[1:]
            if record[0] >= 0xfc or record[2] >= 0xf8
            else (record[0] >> 2, record[1] >> 2))


def parse_stream(raw):
    stream = rooms.parse_object_stream(raw, 0, len(raw))
    encoded, _ = rooms.encode_object_stream(stream.header, stream.lists, stream.doors)
    if stream.end != len(raw) or encoded != raw:
        raise StateDerivationError('room stream must round-trip without trailing bytes')
    return stream


def _remove(records, counts):
    pending = counts.copy()
    kept = []
    for record in records:
        if pending[record]:
            pending[record] -= 1
        else:
            kept.append(record)
    if +pending:
        raise StateDerivationError('saved room changed a state-owned record')
    return kept


@dataclass(frozen=True)
class DerivedStates:
    low: bytes
    high: bytes


def derive_states(saved_raw, selected_low_raw, selected_high_raw):
    """Apply the selected native state delta to the current saved Low room.

    Templates describe the reviewed transformation, never replace saved common
    geometry. A non-additive common-record reorder is unsupported. Native133
    precedes135 because their shared renderer counters depend on that order.
    """
    saved, low, high = map(parse_stream,
                           (saved_raw, selected_low_raw, selected_high_raw))
    if saved.header != low.header or low.header != high.header:
        raise StateDerivationError('water-kit floor/layout header changed')
    if low.doors != high.doors or saved.doors != low.doors:
        raise StateDerivationError('water-kit door contacts changed')
    transformed = []
    for layer in range(3):
        before, after = Counter(low.lists[layer]), Counter(high.lists[layer])
        removed, added = before - after, after - before
        before_common = _remove(low.lists[layer], removed)
        after_common = _remove(high.lists[layer], added)
        if before_common != after_common:
            raise StateDerivationError('selected states reorder common geometry')
        # A duplicate controlled record is a conflict, not an extra contact.
        actual = Counter(saved.lists[layer])
        for record, count in removed.items():
            if actual[record] != count:
                raise StateDerivationError('state-owned record missing or duplicated')
        if any(actual[record] for record in added):
            raise StateDerivationError('saved canonical room already contains High geometry')
        kept = _remove(saved.lists[layer], removed)
        # Preserve reviewed insertion order, including all133 before all135.
        pending = added.copy()
        additions = []
        for record in high.lists[layer]:
            if pending[record]:
                pending[record] -= 1
                additions.append(record)
        if before_common + additions != high.lists[layer]:
            raise StateDerivationError('selected High requires an unsupported insertion order')
        transformed.append(kept + additions)
    result, _ = rooms.encode_object_stream(saved.header, transformed, saved.doors)
    if saved_raw == selected_low_raw and result != selected_high_raw:
        raise StateDerivationError('selected High requires an unsupported insertion order')
    parse_stream(result)
    return DerivedStates(saved_raw, result)


def validate_paint_trace(saved_raw, trace, controlled_cells, protected_records,
                         baseline_records=()):
    """Refuse controlled-contact edits and common objects painting into them.

    Uses the maintained z3ed per-object paint trace. It deliberately does not
    infer footprints from catalog dimensions or treat object-list indices as BGs.
    """
    saved = parse_stream(saved_raw)
    flattened = [(layer, index, record) for layer, records in enumerate(saved.lists)
                 for index, record in enumerate(records)]
    cases = trace.get('cases', [])
    if trace.get('case_count') != len(flattened) or len(cases) != len(flattened):
        raise StateDerivationError('incomplete native object paint trace')
    actual = Counter((layer, record) for layer, _, record in flattened)
    expected = Counter(protected_records)
    for key, count in expected.items():
        if actual[key] != count:
            raise StateDerivationError('protected water-kit contact missing or duplicated')
    protected = set(expected)
    baseline = Counter(baseline_records)
    writes = {}
    for global_index, ((layer, index, record), case) in enumerate(zip(flattened, cases)):
        x, y = record_xy(record)
        size = 0 if record[0] >= 0xfc else ((record[0] & 3) << 2) | (record[1] & 3)
        if (case.get('object_index'), case.get('object_layer'),
                case.get('object_id_dec'), case.get('object_x'), case.get('object_y'),
                case.get('size'), case.get('room_id')) != (
                    global_index, layer, object_id(record), x, y, size, 0x25):
            raise StateDerivationError('paint trace does not describe the saved room')
        tiles = case.get('tiles')
        if not isinstance(tiles, list) or not tiles:
            raise StateDerivationError('untraced object in controlled room')
        cells = set()
        for tile in tiles:
            tx, ty, bg = tile.get('x_tile'), tile.get('y_tile'), tile.get('layer')
            if (not all(type(v) is int for v in (tx, ty, bg)) or
                    not 0 <= tx < 64 or not 0 <= ty < 64 or bg not in (0, 1)):
                raise StateDerivationError('native trace cell outside the two room maps')
            cells.add(bg * 4096 + ty * 64 + tx)
        retained_baseline = baseline[layer, record] > 0
        if retained_baseline:
            baseline[layer, record] -= 1
        if ((layer, record) not in protected and not retained_baseline
                and cells & controlled_cells):
            raise StateDerivationError('saved object overlaps state-owned water/contact cells')
        writes[(layer, index)] = cells
    return writes


def selected_room25_contacts(low_raw):
    """The selected native Low kit; coordinate changes require a new contract.

    These are object anchors in Tile8. Actor roles and pixel recovery bounds
    remain the existing runtime-table generator's typed ABI1 contract.
    """
    stream = parse_stream(low_raw)
    wanted = {0x11f: (24, 8), 0x124: (13, 9), 0x129: (12, 27),
              0xfee: (6, 49), 0xfef: (55, 49)}
    for ident, xy in wanted.items():
        found = [(layer, record) for layer, records in enumerate(stream.lists)
                 for record in records if object_id(record) == ident]
        if (len(found) != 1 or found[0][0] != 0 or
                record_xy(found[0][1]) != xy):
            raise StateDerivationError(f'selected Room25 contact {ident:03X} changed')
    ports = [record_xy(record) for record in stream.lists[0]
             if object_id(record) == 0x132]
    if sorted(ports) != [(12, 39), (30, 25)]:
        raise StateDerivationError('selected Room25 dry service ports changed')
    if any(object_id(record) in (0x133, 0x135, 0xc9, 0xd9, 0xe7)
           for records in stream.lists for record in records):
        raise StateDerivationError('selected canonical Low contains wet-state objects')
    # All retained structure in this kit is controlled. The inherited small
    # decorative pieces may be changed/removed; added objects need trace clearance.
    decoration = {0x005, 0x03a, 0x03e}
    return [(layer, record) for layer, records in enumerate(stream.lists)
            for record in records if object_id(record) not in decoration]


def prepare_saved_room25(saved_raw, selected_low_raw, selected_high_raw, trace):
    """Derive state streams and prove unrelated edits do not repaint the kit."""
    protected = selected_room25_contacts(selected_low_raw)
    selected_room25_contacts(saved_raw)
    state_families = {0xc9, 0xdb, 0xd9, 0xe7, 0x132, 0x133, 0x135}
    def state_records(raw):
        return Counter((layer, record) for layer, records in
                       enumerate(parse_stream(raw).lists) for record in records
                       if object_id(record) in state_families)
    if state_records(saved_raw) != state_records(selected_low_raw):
        raise StateDerivationError('saved room adds or changes an unbound state surface')
    derived = derive_states(saved_raw, selected_low_raw, selected_high_raw)
    # First bind every trace record to the saved stream and require controlled
    # signatures. Then derive the reserved footprint from actual native writes.
    baseline = [(layer, record) for layer, records in
                enumerate(parse_stream(selected_low_raw).lists) for record in records]
    writes = validate_paint_trace(saved_raw, trace, set(), protected, baseline)
    stream = parse_stream(saved_raw)
    protected_set = set(protected)
    controlled = set().union(*(cells for (layer, index), cells in writes.items()
                              if (layer, stream.lists[layer][index]) in protected_set))
    # The selected moving-water surface is wider than the Low bed. Protect it
    # on both native BGs too: an added BG1 object can change BG2 reveal ownership.
    for cell in surface_cells(selected_high_raw, {0xc9, 0xe7}):
        controlled.update((cell, cell + 4096))
    controlled.update(recovery_clearance_cells())
    validate_paint_trace(saved_raw, trace, controlled, protected, baseline)
    return derived, controlled


def recovery_clearance_cells():
    """Protected native/model contact clearance, not new collision writes.

    Catch origins cover48..152/104..120 with a16px body. The manual bank
    covers its actual snap/animation origins through the selected approach.
    Four Low132 landing bodies are part of the measured service-port contract.
    """
    boxes = [(48, 104, 168, 136), (112, 245, 128, 288),
             (248, 176, 264, 192), (248, 224, 264, 240),
             (104, 288, 120, 304), (104, 336, 120, 352)]
    cells = set()
    for x0, y0, x1, y1 in boxes:
        for y in range(y0 // 8, (y1 + 7) // 8):
            for x in range(x0 // 8, (x1 + 7) // 8):
                cells.update((y * 64 + x, 4096 + y * 64 + x))
    return cells


def surface_cells(raw, families):
    """Use the existing D4 native four-by-four superblock size convention."""
    import d4_water_collision
    stream = parse_stream(raw)
    cells = set()
    for record in stream.lists[1]:
        ident, x, y, size = d4_water_collision.decode(record)
        if ident not in families:
            continue
        width, height = 4 * ((size >> 2) + 1), 4 * ((size & 3) + 1)
        if x + width > 64 or y + height > 64:
            raise StateDerivationError('selected water superblock exceeds the room')
        cells.update(yy * 64 + xx for yy in range(y, y + height)
                     for xx in range(x, x + width))
    return cells


SELECTED_PAIR_SHA256 = (
    '917d061e96d303b8d34f15cee482083ec77ae9e8784e6a36a3d1778de153963d',
    'c94564667a77edbafa1f48c99451406258bee185b469603e93780b7a36f713d1',
)
# These source files determine native attribute loading and Room25's plain
# wall-profile path. A source change requires requalifying this native-only kit.
NATIVE_ATTRIBUTE_SOURCES = {
    'Dungeons/Collision/CollisionTablesExpanded.asm':
        '56b31841b303eb401e03cdc8a41a24a97b390cc0cdd0220a57bc8d1abb5aef97',
    'Dungeons/wall_profile_selector.asm':
        'fb9ae42f75fdcd810c1f6d9409c183f9a247c3e0f23829007b4af6efc601ecbc',
    'Dungeons/Data/wall_profiles/wall_profiles.asm':
        '72c1e5f974bc762234df5434bafcf2611f7998daba0d95a707584fd8461f2d51',
    # The selected backend suppresses all three old25/bit02 entry/fill paths.
    'Dungeons/Collision/water_collision.asm':
        '33b928028d7d5de14025ba7c256e51d6c0c8ce675fd08a0fccb90f08a40b2023',
}


def validate_selected_pair(low_raw, high_raw):
    if (sha(low_raw), sha(high_raw)) != SELECTED_PAIR_SHA256:
        raise StateDerivationError('unqualified Room25 state transformation')
    validate_north_water_budget(low_raw)
    validate_north_water_budget(high_raw)
    wanted = {y * 64 + x for x0, y0, x1, y1 in
              ((22, 26, 50, 40), (6, 40, 58, 58))
              for y in range(y0, y1) for x in range(x0, x1)}
    high = parse_stream(high_raw)
    if (surface_cells(high_raw, {0xc9}) != wanted or
            surface_cells(high_raw, {0xd9}) != wanted or
            len(wanted) != 1328 or
            any(object_id(r) not in (0xc9, 0xd9) for r in high.lists[1])):
        raise StateDerivationError('moving water is not the selected one-Tile8 inset')


def validate_north_water_budget(raw):
    # Native133/135 share06B8..06BF. Entry5 overwrites BGTOGGLEAT06C0.
    # Interroom139 has separate storage and must not consume this budget.
    ids = [object_id(record) for records in parse_stream(raw).lists for record in records]
    entries = [(index, ident) for index, ident in enumerate(ids) if ident in (0x133, 0x135)]
    if len(entries) > 4:
        raise StateDerivationError('native north-water entries exceed four-word storage')
    stairs = [index for index, ident in entries if ident == 0x133]
    hops = [index for index, ident in entries if ident == 0x135]
    if stairs and hops and max(stairs) > min(hops):
        raise StateDerivationError('native133 must precede135 across all object lists')


def validate_native_sources(root):
    for name, expected in NATIVE_ATTRIBUTE_SOURCES.items():
        if sha((root / name).read_bytes()) != expected:
            raise StateDerivationError(f'Room25 native source contract changed: {name}')
    controller = (root / 'Dungeons/d4_water_control.asm').read_text()
    routine = re.search(r'(?ms)^D4Water_ApplyCollision:\s*\{(.*?)^\}', controller)
    first = re.search(r'(?ms)^\s*\.pointer\s*\n(.*?)^\s*\.next\s*\n',
                      routine.group(1)) if routine else None
    first_ops = ' '.join(line.split(';', 1)[0].strip()
                         for line in first.group(1).splitlines()) if first else ''
    first_ops = re.sub(r'\s+', ' ', first_ops).strip()
    # The later .next loop has the same terminator needle. It cannot protect
    # the initial TAX and sentinel read at+3; require the first-load sequence.
    required_first = ('STA.b $08 SEP #$20 LDA.b #$50 : STA.b $0A REP #$20 '
                      'LDY.w #$0000 LDA.b [$08],Y : CMP.w #$FFFF : BEQ .done '
                      'TAX LDY.w #$0003 ')
    if not first_ops.startswith(required_first):
        raise StateDerivationError('Room25 native-only collision requires empty-table loader admission')
    for label, name in (('D4Water25Low', '25-low.bin'), ('D4Water25High', '25-high.bin'),
                        ('D4Water25LowCollision', '25-low-collision.bin'),
                        ('D4Water25HighCollision', '25-high-collision.bin')):
        pattern = (r'^' + label + r':\s+incbin\s+"Dungeons/generated/d4_water/'
                   + re.escape(name) + r'"\s*$')
        if not re.search(pattern, controller, re.MULTILINE):
            raise StateDerivationError(f'{label} still consumes an ungenerated state/profile')


def saved_room25_input(base):
    inv = rooms.build_inventory(base)
    stream = inv.objects[0x25]
    header = base[inv.header_pc[0x25]:inv.header_pc[0x25] + 14]
    if (header[0] != 0x90 or header[2] != 1 or header[4:7] != b'\x00\x00\x00'
            or header[10] != 0x34):
        raise StateDerivationError('Room25 BG/collision/blockset/tag/effect/stair context changed')
    return bytes(base[stream.pc:stream.end])


def validate_legacy_collision(root, base):
    sys.path.insert(0, str(root / 'Scripts/Generate'))
    import validate_custom_collision_source as custom
    slot = custom.POINTER_TABLE_START + 0x25 * 3
    pointer = int.from_bytes(base[slot:slot + 3], 'little')
    cells = custom._decode_room(base, 0x25, pointer) if pointer else {}
    if any(value != 0xf5 for value in cells.values()):
        raise StateDerivationError('Room25 has unqualified physical custom collision')
    # F5 is editor metadata. Runtime isolation from legacy02 is a distinct
    # required backend source change, not a mutation of the saved bits/table.


def validated_hub_words(runtime, base):
    required = ('read_hub_roles_strict', 'hub_contact_words', 'write_hub_contacts')
    if not all(hasattr(runtime, name) for name in required):
        raise StateDerivationError('typed Room25 ABI1 runtime generator is unavailable')
    objects, sprites = runtime.read_hub_roles_strict(base)
    words = runtime.hub_contact_words(objects, sprites, (104, 112), (48, 104, 152, 120))
    ox, oy = 5 * 512, 2 * 512
    expected = [ox + 112, oy + 101, ox + 112, oy + 240,
                ox + 104, oy + 72, ox + 104, oy + 112,
                ox + 48, ox + 153, oy + 104, oy + 121]
    if words != expected:
        raise StateDerivationError('saved actors/hatch moved outside the qualified recovery contacts')
    return words


def generate_saved(root, source, output, z3ed):
    """Common source/project Build producer; only generated files are written."""
    root, source, output = map(lambda p: Path(p).resolve(), (root, source, output))
    sys.path.insert(0, str(root / 'Scripts/Generate'))
    import asm_source
    import generate_water_gate_runtime_tables as runtime
    enabled = asm_source._load_global_defines(root).get('ENABLE_D4_WATER_CONTROLS', 0)
    base = source.read_bytes()
    words, derived = None, None
    inputs = [source]
    with tempfile.TemporaryDirectory(prefix='oos-d4-generated-') as temporary:
        stage = Path(temporary)
        if enabled:
            validate_native_sources(root)
            low_path = root / 'Data/Rooms/d4_water/25-low.bin'
            high_path = root / 'Data/Rooms/d4_water/25-high.bin'
            low, high = low_path.read_bytes(), high_path.read_bytes()
            validate_selected_pair(low, high)
            saved = saved_room25_input(base)
            validate_legacy_collision(root, base)
            words = validated_hub_words(runtime, base)
            if not z3ed or not Path(z3ed).is_file():
                raise StateDerivationError('maintained z3ed native paint trace is required')
            trace_path = stage / 'native-paint-trace.json'
            try:
                subprocess.run([str(z3ed), 'dungeon-object-validate', '--rom=' + str(source),
                                '--room=0x25', '--project=' + str(root),
                                '--trace-out=' + str(trace_path), '--format=json'],
                               check=True, capture_output=True, text=True, timeout=60)
            except subprocess.CalledProcessError as exc:
                raise StateDerivationError(
                    f'native object trace failed (exit {exc.returncode}): {exc.stderr}') from exc
            derived, _ = prepare_saved_room25(saved, low, high,
                                             json.loads(trace_path.read_text()))
            inputs.extend((low_path, high_path))
        # Reuse the existing runtime-table API, including its typed contacts.
        overlays, targets = runtime.generate_tables(base, room_max=0xff,
            overlay_object_ids=[0xc9, 0xd9], target_marker_ids=[0x124, 0x137, 0x135])
        generated = stage / 'water_gate_runtime_tables.asm'
        runtime.write_asm(generated, source, overlays, targets,
                          [0xc9, 0xd9], [0x124, 0x137, 0x135])
        if hasattr(runtime, 'write_hub_contacts'):
            runtime.write_hub_contacts(generated, words)
        if source.read_bytes() != base:
            raise StateDerivationError('saved source ROM changed while deriving water states')
        if enabled:
            # This exact kit's native132 and C9/expanded133/135 collision already
            # owns the complete surfaces. Retire old masks, without forced cells.
            files = {Path('d4_water/25-low.bin'): derived.low,
                     Path('d4_water/25-high.bin'): derived.high,
                     Path('d4_water/25-low-collision.bin'): b'\xff\xff',
                     Path('d4_water/25-high-collision.bin'): b'\xff\xff'}
            import d4_water_collision
            for name, data in files.items():
                if name.name.endswith('-collision.bin'):
                    d4_water_collision.decode_runs(data, allow_empty=True)
        else:
            files = {}
        # Publish the consuming include last, after one complete validation.
        files[Path('water_gate_runtime_tables.asm')] = generated.read_bytes()
        from sheet_overrides import write_outputs
        write_outputs(output, files, inputs)
    return dict(enabled=bool(enabled), source_sha256=sha(base), files=len(files),
                generated_sha256={str(name): sha(data) for name, data in files.items()})


def derive_main():
    parser = argparse.ArgumentParser(description='Derive current D4 states from saved Low; never write a ROM.')
    parser.add_argument('--derive-saved', action='store_true', required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--z3ed', type=Path)
    args = parser.parse_args()
    print(json.dumps(generate_saved(args.root, args.source, args.output, args.z3ed)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--write', action='store_true', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    source = args.source.resolve()
    base = source.read_bytes()
    assert sha(base) == SOURCE_SHA256, 'Unreviewed editable input'
    inv = rooms.build_inventory(base)
    streams = {}
    for name, expected in STREAM_HASHES.items():
        raw = (root / 'Data/Rooms/d4_water' / (name + '.bin')).read_bytes()
        assert sha(raw) == expected, name
        streams[name] = rooms.parse_object_stream(raw, 0, len(raw))
    assert streams['37-open'].header == inv.objects[0x37].header
    assert streams['37-open'].lists == inv.objects[0x37].lists
    assert streams['37-open'].doors == inv.objects[0x37].doors
    for name, stream in streams.items():
        old = inv.objects[int(name[:2], 16)]
        stairs = lambda lists: [rec for layer in lists for rec in layer
                               if rec[0] >= 0xfc and rooms.decode_object(rec)[0]
                               in (0x133, 0x135, 0x138, 0x139)]
        assert stairs(stream.lists) == stairs(old.lists), name
        assert stream.doors == old.doors, name
    stream = streams['25-low']
    raw, door_offset = rooms.encode_object_stream(stream.header, stream.lists, stream.doors)
    tail = max(item.end for item in inv.objects
               if rooms.OBJECT_ALLOC_REGION[0] <= item.pc < rooms.OBJECT_ALLOC_REGION[1])
    assert tail + len(raw) < rooms.OBJECT_ALLOC_REGION[1]
    assert not any(base[tail:tail + len(raw)])
    output = bytearray(base)
    edits = []

    def edit(pc, after, purpose):
        before = bytes(output[pc:pc + len(after)])
        assert len(before) == len(after)
        edits.append(dict(pc=pc, before=before.hex(), after=after.hex(), purpose=purpose))
        output[pc:pc + len(after)] = after

    edit(tail, raw, 'Approved room25 Low native objects')
    edit(rooms.OBJECT_TABLE_PC + 0x25 * 3, rooms.encode_long(tail, inv.obj_ptr[0x25]), 'Room25 object pointer')
    edit(rooms.DOOR_TABLE_PC + 0x25 * 3, rooms.encode_long(tail + door_offset, inv.door_ptr[0x25]), 'Same room25 door records')
    edit(inv.header_pc[0x25] + 4, b'\x00', 'Still water; remove inherited rapids/current')
    edit(inv.header_pc[0x25] + 5, b'\x00', 'Replace irreversible WaterOff tag with private controller')
    # The old one-way water-lever actor would compete with the new A control.
    start, end = inv.spr_span[0x25]
    assert list(inv.spr_span).count((start, end)) == 1
    assert base[start:end] == bytes.fromhex('00 06 07 21 05 13 39 ff')
    edit(start, bytes.fromhex('00 05 13 39 ff'), 'Replace obsolete native water-lever21; keep other actor39')
    final = bytes(output)
    ni = rooms.build_inventory(final)
    for room in range(296):
        before = rooms.logical_room(base, inv, room)
        after = rooms.logical_room(final, ni, room)
        if room != 0x25:
            assert before == after, room
        assert before['pots'] == after['pots'], room
        if room != 0x25:
            assert before['sprites'] == after['sprites'], room
    assert final[rooms.CHEST_TABLE_PC:rooms.CHEST_TABLE_PC + rooms.CHEST_CAPACITY] == base[rooms.CHEST_TABLE_PC:rooms.CHEST_TABLE_PC + rooms.CHEST_CAPACITY]
    assert final[0x128090:0x130000] == base[0x128090:0x130000]
    assert source.read_bytes() == base
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / 'd4-service-inlet-editable.sfc'
    assert not target.exists(), 'Use a fresh output directory'
    target.write_bytes(final)
    receipt = dict(source=str(source), sourceSha256=sha(base), output=str(target),
                   outputSha256=sha(final), edits=edits, streams=STREAM_HASHES,
                   other295RoomsExact=True, room37OriginalExact=True,
                   all296PotsAndChestDataExact=True, customCollisionInputExact=True,
                   obsoleteRoom25LeverReplaced=True, existingStairCoordinatesAndDestinationsExact=True)
    (args.output / 'LAYOUT_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(output=str(target), sha256=sha(final), changedBytes=sum(a != b for a, b in zip(base, final)))))


if __name__ == '__main__':
    if '--derive-saved' in sys.argv:
        derive_main()
    else:
        main()
