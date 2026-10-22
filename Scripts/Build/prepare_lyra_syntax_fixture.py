#!/usr/bin/env python3
"""Prepare a synthetic selected-project Asar syntax fixture, never a release ROM.

Use the CI job's seeded zero ROM before its default assembly. The fixture uses
normal generated tables and the normal Oracle_main.asm selected include path;
it has no private source ROM, source-bound assignments or runtime qualification.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import lyra_project_admission as A
import lyra_native_loaders as L
import lyra_project_publisher as P

KIND = 'lyra.synthetic_selected_asm_fixture.v1'
# Public synthetic guards already seeded by .github/workflows/test-rom.yml.
SYNTHETIC_GUARDS = {0xE9E6: bytes.fromhex('738039'), 0xE9F5: bytes.fromhex('7a8038'),
                    0x773FF: b'\x7f', 0x0C0E: bytes.fromhex('a97f8d0443')}


def prepare_fixture(seed):
    """Return fixture bytes/generated inputs without writing or invoking Asar."""
    A.require(type(seed) is bytes and len(seed) in (0x200000, 0x400000),
              'Syntax fixture requires a seeded unheadered2MiB/4MiB zero ROM')
    A.require(seed[:0x400] == bytes(0x400) and seed[0x7FC0:0x7FE0] == bytes(32),
              'Syntax fixture refuses a real/nonzero SNES header or initial code block')
    A.require(all(seed[at:at + len(raw)] == raw for at, raw in SYNTHETIC_GUARDS.items()),
              'Syntax fixture requires the existing CI synthetic guard preimages')
    fixture = bytearray(seed + bytes(0x400000 - len(seed)))
    preimages = {}
    for site, _, original in L.POINTER_HOOKS:
        preimages[A.pc(site)] = (b'\xbf' + original.to_bytes(3, 'little') + b'\x85\xc8'
            + b'\xbf' + (original + 1).to_bytes(3, 'little') + b'\x85\xc9')
    for site in L.FIXED_SIZE_SITES:
        preimages[A.pc(site)] = bytes.fromhex('bf8df802')
    for site in L.FIXED_SPRITE_PALETTE_SITES:
        preimages[A.pc(site)] = bytes.fromhex('bf40fd7e')
    preimages[A.pc(0x1BC8B8)] = bytes.fromhex('bf84a782')
    preimages[A.pc(0x02C4BC)] = bytes.fromhex('e210ab6b')
    for at, raw in preimages.items():
        fixture[at:at + len(raw)] = raw
    source = bytes(fixture)
    props = dict(graphics_sheets=list(range(8)), main_palette=0, palette_set=1, animated_sheet=1,
                 message_id=0, sprite_graphics=[-1] * 3, sprite_palettes=[-1] * 3, music=[0] * 4)
    high, low = 0x3D4206, 0x3D4309
    compiled = SimpleNamespace(maps=[SimpleNamespace(map_id=0xA1, properties=props,
        high=SimpleNamespace(snes=A.snes(high)), low=SimpleNamespace(snes=A.snes(low)))])
    tables = A.relocated_table_payloads(source, None, compiled, [0xA1])
    writes = [dict(kind='runtime_table', pc=row['proposed_pc'], payload_hex=row['payload_hex'],
                   label='LyraRuntime_' + row['name']) for row in tables]
    for at in (high, low):
        writes.append(dict(kind='synthetic_a1_stream', pc=[at, at + 259],
                           payload_hex=(b'\xe0\xff' + bytes(256) + b'\xff').hex()))
    descriptor, description = P.descriptor_payload(props)
    writes.append(dict(kind='a1_descriptor', pc=[P.DESCRIPTOR_PC, P.DESCRIPTOR_PC + 64],
                       payload_hex=descriptor.hex(), label='Lyra_A1Descriptor'))
    plan = dict(kind=KIND, selected=True, writes=writes, descriptor=description,
                syntax_only=True, production_maps=[], production_edge_ids=[])
    files = P.render_outputs(plan)
    report = dict(kind=KIND, syntax_only=True, seed_sha256=A.sha(seed),
        fixture_seed_sha256=A.sha(source), source_size=len(seed), fixture_size=len(source),
        native_preimage_spans=[dict(pc=at, payload_hex=raw.hex()) for at, raw in sorted(preimages.items())],
        generated_files={name: A.sha(raw) for name, raw in files.items()}, table_count=len(tables),
        private_rom_used=False, runtime_verified=False, production_admission=False)
    return source, files, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=Path, required=True)
    parser.add_argument('--output-rom', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    A.require(not args.output_rom.exists() and not args.report.exists(),
              'Syntax fixture refuses to replace an existing ROM/report')
    A.require(args.output_rom.resolve() != args.seed.resolve(), 'Syntax fixture cannot replace its input seed')
    source, files, report = prepare_fixture(args.seed.read_bytes())
    protected = [args.seed, args.output_rom, args.report]
    P.write_outputs(args.output_dir, files, protected=protected)
    P.write_outputs(args.output_rom.parent, {args.output_rom.name: source}, protected=[args.seed,
        args.report, *[args.output_dir / name for name in files]])
    P.write_outputs(args.report.parent, {args.report.name: P.encoded(report)},
                    protected=[args.seed, args.output_rom, *[args.output_dir / name for name in files]])
    print(f'Selected-path syntax fixture:4MiB,{len(files)} generated files,30 tables; no runtime qualification')


if __name__ == '__main__':
    main()
