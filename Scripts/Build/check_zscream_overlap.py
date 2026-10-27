#!/usr/bin/env python3
"""Check Asar WLA emission addresses against the ZScream PC reservation map.

WLA labels also include constants and inactive data declarations. The
address-to-line section identifies emitted code/data, including unlabeled
instructions. It records starts, not byte lengths: this is not a proof that
every emitted byte is outside a reservation.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


# Explicit allocations inside the editor's coarse reserved banks. Require the
# emitting source as well as the PC range; never exempt an entire bank for all
# Oracle code. Bounds are inclusive, in unheadered PC offsets.
OWNED_REGIONS = (
    ("Overworld/ZSCustomOverworld.asm", 0x140000, 0x147FFF),
    ("Overworld/lost_woods.asm", 0x107000, 0x107FFF),
    ("Masks/bunny_hood.asm", 0x102F20, 0x102F6F),
    ("Masks/bunny_hood.asm", 0x102F70, 0x102F8D),
    # generate_water_fill_table.py reserves this tail of custom collision data
    # and rejects tables that exceed it. The collision source contract excludes
    # this area from the editor's per-room collision streams.
    ("Dungeons/generated/water_fill_table.asm", 0x12E000, 0x12FFFF),
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def normalize_source_path(source: str) -> str:
    """Normalize WLA absolute source paths to repository-relative paths."""
    path = Path(source.replace("\\", "/"))
    if path.is_absolute():
        try:
            return path.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix().removeprefix("./")


def snes_to_pc(address: int) -> int | None:
    """Map LoROM/FastROM ROM addresses; omit WRAM and unmapped low halves."""
    bank, offset = address >> 16, address & 0xFFFF
    if bank in (0x7E, 0x7F):
        return None
    # $40-$6F/$C0-$EF low halves mirror their ROM high halves. Low halves
    # in other banks are RAM, hardware registers, SRAM, or unmapped.
    if offset < 0x8000 and not 0x40 <= (bank & 0x7F) <= 0x6F:
        return None
    return ((bank & 0x7F) << 15) | (offset & 0x7FFF)


def parse_zs_map(map_path: Path) -> list[dict]:
    content = map_path.read_text()
    pattern = (
        r'(0x[0-9A-Fa-f]+)\s*-\s*(0x[0-9A-Fa-f]+):'
        r'\s*\d+\s*Banks?\s*\n[ \t]+([^\n]+)'
    )
    ranges = []
    for match in re.finditer(pattern, content):
        start, end = int(match[1], 16), int(match[2], 16)
        if end < start:
            raise ValueError(f"Reversed ZScream range: {match[0]}")
        ranges.append({"start": start, "end": end, "name": match[3].strip()})
    if not ranges:
        raise ValueError(f"No reserved ranges parsed from {map_path}")
    return ranges


def parse_symbols(symbols_path: Path) -> tuple[dict, list[dict]]:
    """Read full Asar WLA symbols, failing on missing/truncated input."""
    sources, labels, mappings = {}, {}, []
    section = None
    sections = set()
    for number, raw in enumerate(symbols_path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("["):
            section = line
            sections.add(section)
            continue
        if section == "[source files]":
            match = re.fullmatch(r'([0-9A-Fa-f]+) [0-9A-Fa-f]+ (.+)', line)
            if match:
                sources[int(match[1], 16)] = normalize_source_path(match[2])
        elif section in ("[labels]", "[addr-to-line mapping]"):
            match = re.fullmatch(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)', line)
            if match:
                address = (int(match[1], 16) << 16) | int(match[2], 16)
                pc = snes_to_pc(address)
                if section == "[labels]":
                    if pc is not None:
                        labels.setdefault(pc, []).append(match[3])
                else:
                    origin = re.fullmatch(r'([0-9A-Fa-f]+):([0-9A-Fa-f]+)', match[3])
                    if origin:
                        mappings.append({"snes": address, "pc": pc,
                                         "source_id": int(origin[1], 16),
                                         "line": int(origin[2], 16)})
                    else:
                        match = None
        else:
            continue
        if not match:
            raise ValueError(f"Malformed {section} entry at {symbols_path}:{number}")

    required = {"[labels]", "[source files]", "[addr-to-line mapping]"}
    if not required <= sections or not sources or not mappings:
        raise ValueError(f"Incomplete Asar WLA symbols: {symbols_path}")
    for item in mappings:
        try:
            item["source"] = sources[item.pop("source_id")]
        except KeyError as exc:
            raise ValueError(f"Unknown source id in {symbols_path}") from exc
    return labels, mappings


def lyra_owned_regions(verification_path: Path, rom_path: Path, symbols_path: Path,
                       input_path: Path | None = None) -> tuple[tuple[str, int, int], ...]:
    """Authorize only this verified generated source's exact current writes.

    Reconstruct the selected plan, rather than granting its reservation or
    trusting receipt claims. All validation is read-only; no receipt is emitted.
    Returned bounds are inclusive, matching OWNED_REGIONS.
    """
    import lyra_native_loaders as native
    import lyra_project_admission as A
    import lyra_project_allocation as R
    import lyra_project_publisher as P

    folder = Path(input_path) if input_path is not None else REPO_ROOT / P.OUTPUT
    current_prior = json.loads((folder / 'prepare.json').read_bytes())
    if current_prior.get('kind') == 'lyra.current_build_prepare.v1':
        import lyra_current_transfer as current
        R.require(Path(rom_path).resolve() == Path(current_prior['terrain_plan']['target']['path']),
                  'CURRENT_BUILD_TARGET_MISMATCH')
        with current.candidate_inspection(rom_path):
            files = current.verify_current_context(P.ROOT,current_prior)
            compiled,symbols = Path(rom_path).read_bytes(),Path(symbols_path).read_bytes()
            proof = json.loads(Path(verification_path).read_bytes())
            actual = current.verify_current_output(current_prior,compiled,symbols)
            actual['prepared_sha256'] = R.sha(files['prepare.json'])
            R.require(proof == actual,'Current Lyra ownership receipt differs from actual consumers')
            source = normalize_source_path(str((folder / 'runtime_data.asm').resolve()))
            spans = [row['pc'] for row in current_prior['terrain_plan']['writes']]
            spans += [row['pc'] for row in current_prior['tables']['tables']]
            return tuple((source,a,b-1) for a,b in spans)
    paths = [Path(verification_path), Path(rom_path), Path(symbols_path)]
    paths += [folder / name for name in P.GENERATED_FILES]
    snapshot = {path: path.read_bytes() for path in paths}
    proof = json.loads(snapshot[Path(verification_path)])
    prior = json.loads(snapshot[folder / 'prepare.json'])
    R.require(type(proof) is dict and type(prior) is dict
              and proof.get('kind') == 'lyra.ordinary_build_verification.v1'
              and prior.get('kind') == 'lyra.ordinary_build_prepare.v1'
              and prior.get('selected') is True, 'No verified selected Lyra ownership context')
    plan = P.make_plan(prior['project'], prior['base_rom'], prior['request'], ledger_path=prior['ledger'])
    generated = P.render_outputs(plan)
    R.require(all(snapshot[folder / name] == raw for name, raw in generated.items()),
              'Lyra generated ownership inputs are stale or changed')
    saved, compiled, symbols = Path(plan['base_rom']).read_bytes(), snapshot[Path(rom_path)], snapshot[Path(symbols_path)]
    R.require(proof.get('prepared_sha256') == R.sha(generated['prepare.json'])
              and proof.get('saved_rom_sha256') == plan['saved_rom_sha256'] == R.sha(saved)
              and proof.get('compiled_rom_sha256') == R.sha(compiled)
              and proof.get('symbols_sha256') == R.sha(symbols)
              and proof.get('current_ledger_sha256') == plan['current_ledger_sha256']
              and proof.get('production_maps') == [] and proof.get('production_edge_ids') == []
              and proof.get('save_exit_policy') == 'unchanged_held',
              'Lyra ownership receipt identity or publication scope differs')
    P.require_verified_native_receipt(proof.get('native_loaders'), R.sha(compiled))
    actual_native = native.verify_native_loaders(saved, compiled, symbols,
        compiled[P.DESCRIPTOR_PC:P.DESCRIPTOR_PC + 64], ledger_path=plan['ledger'])
    R.require(P.encoded(actual_native) == P.encoded(proof['native_loaders']),
              'Lyra ownership receipt does not match actual compiled consumers')
    for row in plan['writes']:
        start, end = row['pc']
        R.require(0 <= start < end <= len(saved) == len(compiled)
                  and saved[start:end].hex() == row['preimage_hex']
                  and compiled[start:end].hex() == row['payload_hex'],
                  'Lyra owned write preimage, payload or extent differs')
    # This also verifies actual payloads, complete dictionary meaning, all160
    # native component controls and the emitted table legacy prefixes.
    actual_data = P.verify_data(saved, compiled, plan['writes'],
        dict(enumerate(A.read_tile32(saved, i) for i in range(0x4540))),
        {r['tile32_id']: tuple(r['quadrants']) for r in plan['emitted_definitions']},
        plan['targets']['native37'], plan['targets']['a1'])
    R.require(all(proof.get(key) == value for key, value in actual_data.items()),
              'Lyra ownership data receipt differs from actual readback')
    source = normalize_source_path(str((folder / 'runtime_data.asm').resolve()))
    regions = tuple((source, row['pc'][0], row['pc'][1] - 1) for row in plan['writes']
                    if row['kind'] in ('a1_dictionary_group', 'runtime_table'))
    R.require(regions and all(start <= end for _, start, end in regions), 'Empty Lyra owned write scope')
    R.require(all(path.read_bytes() == raw for path, raw in snapshot.items())
              and all(R.sha(Path(row['path']).read_bytes()) == row['sha256'] for row in plan['inputs']),
              'Lyra ownership input changed during verification')
    return regions


def check_overlaps(symbols_path: Path, zs_ranges: list[dict], *,
                   verified_regions: tuple[tuple[str, int, int], ...] = ()) -> list[dict]:
    labels, mappings = parse_symbols(symbols_path)
    overlaps = []
    seen = set()
    for item in mappings:
        pc = item["pc"]
        if pc is None:
            continue
        for reserved in zs_ranges:
            if not reserved["start"] <= pc <= reserved["end"]:
                continue
            if any(source == item["source"] and start <= pc <= end
                   for source, start, end in (*OWNED_REGIONS, *verified_regions)):
                continue
            key = (pc, item["source"], item["line"])
            if key in seen:
                continue
            seen.add(key)
            overlaps.append({
                "label": ", ".join(labels.get(pc, ["<unlabeled emission>"])),
                "pc": f"0x{pc:06X}",
                "snes": f"0x{item['snes']:06X}",
                "source": f"{item['source']}:{item['line']}",
                "range": f"0x{reserved['start']:06X}-0x{reserved['end']:06X}",
                "system": reserved["name"],
            })
    return overlaps


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", type=Path, default=root / "Roms/oos168x.sym",
                        help="Fresh Asar WLA .sym from the build (default: Roms/oos168x.sym)")
    parser.add_argument("--map", type=Path, default=root / "Core/ZS ROM MAP.txt",
                        help="ZScream reserved PC address map")
    parser.add_argument("--lyra-verification", type=Path,
                        help="Current successful Lyra verification receipt; requires --rom")
    parser.add_argument("--rom", type=Path,
                        help="Exact assembled ROM bound to --lyra-verification and --symbols")
    parser.add_argument("--lyra-input", type=Path,
                        help="Current prepared Lyra inputs (default: Data/Generated/lyra_project)")
    args = parser.parse_args()
    if bool(args.lyra_verification) != bool(args.rom) or (args.lyra_input and not args.lyra_verification):
        parser.error("--lyra-verification and --rom are required together; --lyra-input requires both")
    print(f"[*] Checking mapped emission starts in {args.symbols}...")
    try:
        owned = (lyra_owned_regions(args.lyra_verification, args.rom, args.symbols, args.lyra_input)
                 if args.lyra_verification else ())
        overlaps = check_overlaps(args.symbols, parse_zs_map(args.map), verified_regions=owned)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"[-] Error: {exc}")
        return 1
    if overlaps:
        print(f"[!] {len(overlaps)} unowned emission addresses overlap ZScream reservations:")
        for item in overlaps[:30]:
            print(f"  {item['pc']} (SNES {item['snes']}) {item['label']} "
                  f"[{item['source']}] — {item['system']}")
        if len(overlaps) > 30:
            print(f"  ... {len(overlaps) - 30} additional addresses")
        return 1
    print("[+] No unowned mapped emission starts in ZScream reserved regions.")
    print("    Declared source allocations allowed; byte-span overlap is not checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
