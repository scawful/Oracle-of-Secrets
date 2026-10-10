"""Bounded allocation/table checks for the existing Oracle manifest.

This is an ownership ledger, not a free-space allocator. Addresses are half-open;
save_buffer records occupy physical WRAM. Unknown evidence never grants space.
Exact ROM spans are supplied by generate_hack_manifest.load_exact_hooks.
"""
from __future__ import annotations
import hashlib
import itertools
import json
from pathlib import Path
import re

from asm_source import _iter_active_lines, _load_global_defines


class AllocationError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise AllocationError(message)


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_ledger(path):
    data = json.loads(Path(path).read_text())
    require(data.get('schema_version') == 1, 'Unsupported ownership ledger version')
    require(data.get('allocation_available') is False, 'Ledger cannot grant unverified free space')
    claims = data.get('claims')
    require(isinstance(claims, list) and claims, 'Missing ownership claims')
    ids = set()
    for c in claims:
        require(isinstance(c, dict) and isinstance(c.get('id'), str), 'Invalid claim')
        require(c['id'] not in ids, f"Duplicate claim {c['id']}")
        ids.add(c['id'])
        for field in ('owner', 'lifetime', 'reset', 'save'):
            require(isinstance(c.get(field), str) and bool(c[field]), f"{c['id']}: missing {field}")
        require(c.get('space') in ('wram', 'save_buffer', 'pc_rom', 'snes_rom'), f"{c['id']}: invalid address space")
        require(c.get('status') in ('shared', 'pending', 'proposed'), f"{c['id']}: invalid status")
        require(c.get('base') is None or integer(c['base']) and c['base'] >= 0, f"{c['id']}: invalid base")
        require(c.get('size') is None or integer(c['size']) and c['size'] > 0, f"{c['id']}: invalid size")
        require(isinstance(c.get('condition'), dict) and all(integer(v) and v in (0, 1) for v in c['condition'].values()), f"{c['id']}: invalid feature condition")
        require(c.get('provenance') and all(key in data.get('sources', {}) for key in c['provenance']), f"{c['id']}: missing provenance")
        if c.get('count') is not None:
            require(integer(c['count']) and integer(c.get('stride')) and c['count'] > 0 and c['stride'] > 0 and c['count'] * c['stride'] == c['size'], f"{c['id']}: count/stride mismatch")
        if c['base'] is not None and c['size'] is not None:
            start, end = c['base'], c['base'] + c['size']
            if c['space'] == 'save_buffer':
                require(0x7EF000 <= start < end <= 0x7EF500, f"{c['id']}: outside save buffer")
            elif c['space'] == 'wram':
                require(0x7E0000 <= start < end <= 0x800000, f"{c['id']}: outside WRAM")
    for c in claims:
        for key in ('contained_by', 'replaces'):
            if key in c:
                require(c[key] in ids and c[key] != c['id'], f"{c['id']}: invalid {key}")
    return data


def source_evidence(ledger, roots):
    texts = {}
    for key, src in ledger['sources'].items():
        require(src['source_set'] in roots, f"Missing required source set: {src['source_set']}")
        root = Path(roots[src['source_set']]).resolve()
        path = (root / src['path']).resolve()
        require(path.is_relative_to(root) and path.is_file(), f"Missing/invalid evidence: {key}")
        require(digest(path) == src['sha256'], f"Stale source evidence: {key}")
        texts[key] = path.read_text()
    for c in ledger['claims']:
        text = '\n'.join(texts[key] for key in c['provenance'])
        for anchor in c.get('anchors', []):
            require(anchor in text, f"{c['id']}: absent provenance anchor {anchor}")
        if binding := c.get('binding'):
            matches = re.findall(r'^\s*' + re.escape(binding['symbol']) + r'\s*=\s*\$([0-9a-fA-F]+)\b', texts[binding['source']], re.M)
            require(len(matches) == 1, f"{c['id']}: missing/ambiguous symbol binding")
            address = int(matches[0], 16)
            if binding.get('bank00_mirror') and address < 0x2000:
                address += 0x7E0000
            require(address == c['base'], f"{c['id']}: source address disagrees with ledger")
    return {key: value['sha256'] for key, value in ledger['sources'].items()}


def physical(c):
    space = 'wram' if c['space'] == 'save_buffer' else c['space']
    return space, c['base'], c['base'] + c['size']


def ownership_conflicts(ledger, profile, *, pending=False, proposed=False):
    selected, notes = [], []
    for c in ledger['claims']:
        if c['status'] == 'pending' and not pending or c['status'] == 'proposed' and not proposed:
            continue
        unknown = set(c['condition']) - set(profile)
        require(not unknown, f"{c['id']}: unknown feature condition {sorted(unknown)}")
        if any(profile[k] != v for k, v in c['condition'].items()):
            notes.append({'id': c['id'], 'status': 'inactive_in_profile'})
            continue
        if c['base'] is None or c['size'] is None:
            notes.append({'id': c['id'], 'status': 'unresolved_extent_or_address'})
            continue
        selected.append(c)
    by_id = {c['id']: c for c in ledger['claims']}
    # A proposed successor must cover the original owner, not silently erase it.
    replaced = set()
    for c in selected:
        if old_id := c.get('replaces'):
            old = by_id[old_id]
            require(c['status'] == 'proposed' and c['space'] == old['space'] and c['base'] == old['base'] and c['size'] >= old['size'], f"{c['id']}: invalid replacement")
            replaced.add(old_id)
        if parent_id := c.get('contained_by'):
            parent = by_id[parent_id]
            require(parent.get('container') is True and parent['space'] == c['space'] and parent['base'] <= c['base'] and c['base'] + c['size'] <= parent['base'] + parent['size'], f"{c['id']}: invalid containment")
    selected = [c for c in selected if c['id'] not in replaced]
    allowed = set()
    for alias in ledger.get('lifetime_aliases', []):
        owners = alias.get('owners', [])
        require(len(owners) == 2 and len(set(owners)) == 2 and all(i in by_id for i in owners), 'Invalid lifetime alias owners')
        phases = alias.get('phases', {})
        require(all(phases.get(i) for i in owners) and not set(phases[owners[0]]) & set(phases[owners[1]]), 'Lifetime alias phases must be explicit and disjoint')
        require(alias.get('proof_sources') and all(k in ledger['sources'] for k in alias['proof_sources']), 'Lifetime alias requires provenance')
        allowed.add(frozenset(owners))
    conflicts = []
    for a, b in itertools.combinations(selected, 2):
        sa, start_a, end_a = physical(a); sb, start_b, end_b = physical(b)
        if sa != sb or max(start_a, start_b) >= min(end_a, end_b):
            continue
        if a.get('contained_by') == b['id'] or b.get('contained_by') == a['id'] or frozenset((a['id'], b['id'])) in allowed:
            continue
        conflicts.append({'owners': [a['id'], b['id']], 'space': sa, 'start': max(start_a, start_b), 'end': min(end_a, end_b), 'classification': 'proposed_conflict' if 'proposed' in (a['status'], b['status']) else 'path_dependent_hazard' if 'path_dependent' in (a.get('activation'), b.get('activation')) else 'active_profile_conflict'})
    return conflicts, notes


def snes_pc(address):
    require(integer(address) and 0 <= address < 0x400000 and address & 0xFFFF >= 0x8000, f'Not a canonical LoROM address: {address!r}')
    return ((address >> 16) * 0x8000) + (address & 0x7FFF)


def read_symbols(path):
    symbols = {}
    section = None
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith(';'):
            continue
        if line.startswith('['):
            section = line.strip()
            continue
        if section != '[labels]':
            continue
        match = re.fullmatch(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)', line)
        require(match is not None, 'Malformed WLA label')
        value = int(match[1] + match[2], 16)
        require(match[3] not in symbols or symbols[match[3]] == value, 'Conflicting WLA symbol')
        symbols[match[3]] = value
    require(bool(symbols), 'Missing WLA symbol evidence')
    return symbols


def table_checks(tables, symbols, rom_size):
    ranges = []
    for t in tables:
        require(t.get('count') == 160 and integer(t.get('stride')) and t.get('stride') in (1, 2, 3, 8), f"{t['id']}: current table must have 160 records and a supported stride")
        start = snes_pc(t['address']); end = start + t['count'] * t['stride']
        fence = snes_pc(t['boundary'])
        require(end <= fence and end <= rom_size, f"{t['id']}: table crosses its boundary")
        require((t['address'] & 0xFFFF) + t['count'] * t['stride'] <= 0x10000, f"{t['id']}: bank-relative table crosses bank")
        if symbol := t.get('symbol'):
            require(symbol in symbols and symbols[symbol] == t['address'], f"{t['id']}: missing/stale table symbol")
        ranges.append({'id': t['id'], 'start': start, 'end': end, 'boundary': fence, 'source': t['source'], 'payload': t['payload']})
    for a, b in itertools.combinations(ranges, 2):
        require(max(a['start'], b['start']) >= min(a['end'], b['end']), f"Tables overlap: {a['id']}/{b['id']}")
    return ranges


def emission_crossings(spans, ranges):
    """Exact spans only, after the existing manifest loader verifies ROM identity."""
    for span in spans:
        for region in ranges:
            if max(span.start_pc, region['start']) >= min(span.end_pc, region['end']):
                continue
            require(region['start'] <= span.start_pc and span.end_pc <= region['end'], f"Exact emission crosses {region['id']} boundary")
            require(span.hook.kind == region['payload'] and re.sub(r':\d+$', '', span.hook.source.replace('\\', '/')) == region['source'], f"Wrong source/payload in {region['id']}")


def cart_checks(root, config, symbols, rom):
    count, stride = config['count'], config['stride']
    require(count == 32 and stride == 2, 'Current cart capacity must remain 32 words')
    path = Path(root) / config['source']
    require(path.is_file(), 'Missing cart table source')
    # Exercise both branches without modifying the project's feature defaults.
    for flag in (0, 1):
        defines = _load_global_defines(Path(root)); defines['ENABLE_MINECART_PLANNED_TRACK_TABLE'] = flag
        active = [line.split(';', 1)[0].strip() for _, line, _ in _iter_active_lines(path.read_text().splitlines(), defines)]
        for suffix in ('Rooms', 'X', 'Y'):
            start_label = '.TrackStarting' + suffix; end_label = start_label + 'End'
            require(start_label in active and end_label in active, f'Missing cart extent label: {suffix}')
            body = active[active.index(start_label) + 1:active.index(end_label)]
            values = []
            for line in body:
                if not line:
                    continue
                require(line.lower().startswith('dw '), f'Unsupported cart table evidence: {line}')
                values.extend(line[3:].split(','))
            require(len(values) == count and all(re.fullmatch(r'\s*\$[0-9A-Fa-f]{1,4}\s*', v) for v in values), f'{suffix}: invalid count/word evidence for planned={flag}')
            name = config['symbols_prefix'] + suffix
            require(name in symbols and name + 'End' in symbols and symbols[name + 'End'] - symbols[name] == count * stride, f'{suffix}: missing/stale emitted table extent')
    require(config['reset_symbol'] in symbols, 'Missing ResetTrackVars symbol')
    start = snes_pc(symbols[config['reset_symbol']]); code = rom[start:start + 26]
    # Deliberately bounded decoder for the current 8-bit pre-decrement reset.
    # Different code/widths require a new proof, never a guessed pass.
    pattern = rb'\x22...\xA9\x00\x8D\xE8\x07\xA2(.)\xCA\x9D\x28\x07\x9D\x68\x07\x9D\xA8\x07\xE0\x00\xD0\xF2\x6B'
    match = re.fullmatch(pattern, code, re.S)
    require(match is not None, 'Unrecognized ResetTrackVars encoding; reset extent unproven')
    stores = match[1][0]
    return {'count': count, 'stride': stride, 'reset_bytes_per_array': stores, 'expected_bytes_per_array': count * stride, 'reset_bounds_passed': stores == count * stride, 'explicit_cache_reset': 0x7E07E8}


def verify_receipt(path, root, rom_path, symbols_path):
    from build_receipt import verify_source_identity
    receipt = json.loads(Path(path).read_text())
    require(receipt.get('schema_version') == 1 and receipt.get('finish', {}).get('exit_code') == 0 and receipt.get('state') in ('complete', 'completed', 'completed_with_gaps'), 'Missing/successless build receipt')
    require(Path(receipt['root']).resolve() == Path(root).resolve(), 'Receipt root mismatch')
    require(not receipt['finish'].get('required_gaps') and any(c.get('name') == 'assembly' and c.get('status') == 'passed' and c.get('required') is True for c in receipt.get('checks', [])), 'Missing required assembly evidence')
    require(receipt.get('snapshots', {}).get('pre_assembly', {}).get('files'), 'Missing pre-assembly source evidence')
    require(verify_source_identity(receipt, Path(path)) is None, 'Stale build source snapshot')
    for name, artifact in [('output_rom', rom_path), ('symbols', symbols_path)]:
        identity = receipt.get('artifacts', {}).get(name, {})
        require(Path(artifact).is_file() and identity.get('sha256') == digest(artifact) and identity.get('size') == Path(artifact).stat().st_size, f'Stale/missing receipt artifact: {name}')
    profile = receipt['snapshots']['pre_assembly']['profile']
    require(not profile.get('unresolved_assignments'), 'Unresolved build profile')
    return profile['effective_flags']


def validate_draft(c, *, current_tables=None, require_ready=False):
    require(c.get('schema_version') == 1 and c.get('status') == 'draft_unallocated' and c.get('runtime_supported') is False, 'Not a supported unallocated draft')
    require(c.get('area_count') == 192 and c.get('reject_from') == 192 and c.get('preserve_ids') == [0, 159] and c.get('sea_ids') == [160, 191], 'Invalid 192-area namespace')
    require([(w['base'], w['count']) for w in c['worlds']] == [(0,64),(64,64),(128,64)], 'Invalid world ranges')
    require(c['roles'].get('preserve_existing') is True and c['roles'].get('overlay_storage_preserve') == [147,159] and c['roles'].get('roles_are_explicit_not_inferred_from_id') is True, 'Legacy overlay storage must be preserved')
    require(c.get('sprite_phases') == 3 and c.get('sprite_phase_stride') == 192 * 2, 'Invalid sprite phase stride')
    strides = dict(bg_color=2, main_palette=1, mosaic=1, animated=1,
        overlay=2, gfx=8, parent=1, ByScreen1=2, ByScreen2=2,
        ByScreen3=2, ByScreen4=2, transition_y=2, transition_x=2,
        scroll_north=2, scroll_west=2, sprite_phase0=2, sprite_phase1=2,
        sprite_phase2=2, sign_text=2, map32_high=3, map32_low=3,
        bomb_doors=2, hidden_items=2)
    require(len(c['tables']) == len(strides) and {t['id'] for t in c['tables']} == set(strides), 'Missing/duplicate/unknown format tables')
    for t in c['tables']:
        require(t['count'] == 192 and t['stride'] == strides[t['id']], 'Invalid draft table count/stride')
        require(t['address'] is None, 'This draft has no approved ROM allocations')
        addressing = ('long_pointer' if t['id'] in ('map32_high', 'map32_low') else
            'bank_relative_02' if t['id'] in ('bomb_doors', 'hidden_items') else 'bank_relative_28_or_long')
        require(t['addressing'] == addressing, 'Invalid table address restriction')
    if current_tables is not None:
        legacy = {t['id']: t for t in current_tables}
        require(set(legacy) == set(strides), 'Current/draft table identities disagree')
        for t in c['tables']:
            old = legacy[t['id']]
            require(old['count'] == 160 and (old['address'], old['stride'], old['addressing']) == (t['legacy_address'], t['stride'], t['addressing']), 'Current/draft table layout disagrees')
    require(c['events'] == dict(normal_base=0x7EF280,normal_count=128,special_count=64,special_base=None,forbid_direct_special_indexing=True,migration=None), 'Invalid event storage contract')
    require(c['music']['count'] == 192 and c['music']['stride'] == 1 and c['music']['cache_base'] is None and c['music']['forbidden_in_place'] == [0x7F5BA0,0x7F5BA4], 'Invalid music contract')
    for field in ('special_sprite_gfx', 'special_sprite_palettes'):
        require(c[field] == dict(count=64, stride=1, address=None), 'Special sprite properties must be 64 unresolved bytes')
    for field, address in [('area_size',0x02F88D), ('palette_set',0x09C635)]:
        require(c[field] == dict(count=192, stride=1, address=None, legacy_address=address), 'Invalid existing 192-byte table contract')
    require(c['sprites']['pointer_width'] == 2 and c['sprites']['bank'] == 9 and c['sprites']['list_region'] is None and c['sprites']['capacity_unresolved'] is True, 'Invalid sprite list capacity/addressing')
    require(c['map_streams'] == dict(pointer_width=3, streams_per_cell=2, decoded_bytes_per_stream=256, regions=None, terminator=255), 'Invalid compressed map contract')
    require(c['tile_definitions'] == dict(tile16_capacity=None, tile32_capacity=None, unresolved=True) and c['menu_names'] == dict(count=192, pointer_table=None, encoding=None) and c['world_map'] == dict(special_world_projection=None, unresolved=True), 'Unapproved tile/menu/world-map allocation')
    require(c['legacy_detection'] == dict(zs_version_address=0x288145, zs_version=3, absent_expanded_signature='legacy_160_only', unknown_or_malformed_expanded_signature='reject_writes', never_fallback_on_invalid_expanded=True), 'Unsafe legacy detection')
    require(c['signature']['address'] is None and c['signature']['revision'] == 1 and c['signature']['proposed_magic'] == 'OOSOW192', 'Invalid draft signature')
    require(c['four_cell_proof'] == dict(ids=[160,161,162,163], north_ids=[152,153,154,155], requires_role_audit=True, activation_allowed=False), 'Four-cell proof needs overlay role audit and later approval')
    require(not require_ready, '192-area activation refused: allocations, save migration and writer support unresolved')
    return {'status': 'valid_draft_not_activation_ready', 'area_count': 192, 'unresolved': c['unresolved_allocations']}


def valid_area(area):
    return integer(area) and 0 <= area < 192
