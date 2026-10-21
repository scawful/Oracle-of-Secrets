#!/usr/bin/env python3
"""Derive fresh candidate allocation from source ownership and actual ROM bytes.

This reads the existing ownership ledger and returns the existing allocation
format with exact preimages. It never searches for free space or writes a ROM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[2] / 'Config/allocation_ownership.json'
CLAIM = 'lyra_project_runtime_candidate'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def reservation_claim(ledger_path=None):
    path = Path(ledger_path) if ledger_path is not None else LEDGER
    raw = path.read_bytes()
    ledger = json.loads(raw)
    require(ledger.get('schema_version') == 1 and ledger.get('allocation_available') is False,
            'Source ledger cannot grant general free-space allocation')
    claims = [c for c in ledger.get('rom_candidate_reservations', []) if c.get('id') == CLAIM]
    require(len(claims) == 1, 'No unique source-declared Lyra candidate reservation')
    claim = claims[0]
    require(claim.get('status') == 'proposed' and claim.get('scope') == 'isolated_candidate_only'
            and claim.get('production_admission') is False and claim.get('parent_count') == 160
            and claim.get('owned_tile32_ids') == [], 'Unsupported source reservation policy')
    regions = claim.get('regions')
    require(type(regions) is list and [r.get('purpose') for r in regions] == ['tables', 'code', 'streams'],
            'Malformed source reservation regions')
    spans = []
    for region in regions:
        require(set(region) == {'purpose', 'pc', 'allowed_fills'}, 'Malformed source reservation region')
        span, fills = region['pc'], region['allowed_fills']
        require(type(span) is list and len(span) == 2 and all(type(v) is int for v in span)
                and 0 <= span[0] < span[1] <= 0x400000, 'Invalid source reservation span')
        require(all(span[1] <= a or span[0] >= b for a, b in spans), 'Overlapping source reservations')
        require(type(fills) is list and fills and all(type(v) is int and v in (0, 255) for v in fills),
                'Invalid source reservation fill')
        spans.append(tuple(span))
    def physical(address):
        require(type(address) is int and address & 0x8000
                and address >> 16 not in (0x7E, 0x7F), 'Invalid legacy ROM ownership address')
        return ((address & 0x7F0000) >> 1) | (address & 0x7FFF)

    # Named future ROM claims also conflict: a currently blank range cannot
    # become ours merely because another source owner has not emitted it yet.
    owners = list(ledger.get('claims', []))
    owners += [dict(id=t['id'], space=t.get('space'), base=t.get('address'),
                    size=t['count'] * t['stride']) for t in ledger.get('tables', [])]
    for owner in owners:
        space, begin, size = owner.get('space'), owner.get('base'), owner.get('size')
        if space not in ('pc_rom', 'snes_rom') or begin is None or size is None:
            continue
        require(type(begin) is int and type(size) is int and size > 0, 'Invalid legacy ROM ownership')
        end = begin + size
        if space == 'snes_rom':
            begin, end = physical(begin), physical(end - 1) + 1
        require(all(end <= a or begin >= b for a, b in spans),
                f"Source reservation conflicts with ROM owner {owner.get('id')}")
    return claim, sha(raw)


def derive_allocation(source, *, ledger_path=None):
    require(type(source) is bytes and len(source) == 0x400000,
            'Source reservation requires an actual unheadered4MiB ROM')
    claim, ledger_hash = reservation_claim(ledger_path)
    preimages = []
    for region in claim['regions']:
        start, end = region['pc']
        raw = source[start:end]
        require(raw and raw[0] in region['allowed_fills'] and raw == bytes([raw[0]]) * len(raw),
                f"Source-declared {region['purpose']} reservation is occupied")
        preimages.append(dict(purpose=region['purpose'], pc=[start, end],
                              fill=raw[0], sha256=sha(raw)))
    regions = {r['purpose']: r['pc'] for r in claim['regions']}
    return dict(kind='lyra.project_runtime_allocation.v1', source_rom_sha256=sha(source),
        expanded_size=len(source), table_range=regions['tables'], code_range=regions['code'],
        stream_ranges=[regions['streams']], owned_tile32_ids=[],
        reservation=dict(kind='lyra.project_source_reservation.v1', claim_id=CLAIM,
                         source_rom_sha256=sha(source), ledger_sha256=ledger_hash, regions=preimages),
        admission=dict(candidate_maps=[], candidate_edge_ids=[], production_maps=[], production_edge_ids=[]))


def verify_reservation(source, allocation, reservation, *, ledger_path=None):
    expected = derive_allocation(bytes(source), ledger_path=ledger_path)
    require(reservation == expected['reservation'], 'Source reservation/preimages are stale or forged')
    require(tuple(expected['table_range']) == (0x144000, 0x1469C0)
            and tuple(expected['code_range']) == (0x3C4000, 0x3C6000)
            and tuple(map(tuple, expected['stream_ranges'])) == allocation.stream_ranges
            and tuple(expected['owned_tile32_ids']) == allocation.owned_tile32_ids,
            'Allocation differs from the source-declared reservation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(derive_allocation(args.rom.read_bytes()), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
