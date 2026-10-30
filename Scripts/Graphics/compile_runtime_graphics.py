#!/usr/bin/env python3
"""Lower the canonical graphics catalog/policy to the bank-$5B runtime ABI.

This command never reads or writes a ROM. --write explicitly updates generated
ASM; --check verifies it without writing. Executable helpers own hook timing.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
import tempfile

import compile_graphics_pack as pack

ROOT = Path(__file__).resolve().parents[2]
CONSTANTS = {
    "ABIVersion": 1, "Bank": 0x5B, "ParentCount": 160, "HeaderSize": 22,
    "NormalCount": 0, "NormalPtr": 2, "CacheMask": 4,
    "TransitionMode": 5, "TransitionStart": 6, "TransitionEnd": 8,
    "TransitionSource": 10, "StagingCount": 13, "StagingPtr": 15,
    "LateFirst": 17, "LateEnd": 18, "LateSource": 19,
    "NormalRecordSize": 7, "StagingRecordSize": 8,
    "ModeNone": 0, "ModeRange": 1, "ModeStart": 2, "ModeNative": 3,
}
LEGACY_ALIASES = {
    "gfx/boat.bin": "ShipBackgroundGraphics",
    "gfx/boat2.bin": "ShipExtendedGraphics",
    "gfx/kalyxo_docks_bg.bin": "KalyxoDocksBackgroundGraphics",
    "gfx/kalyxo_docks_slot3.bin": "KalyxoDocksSlot3Graphics",
}


def _source_binding(binding: dict, root: Path) -> None:
    if not isinstance(binding, dict):
        raise pack.PackError("current graphics source binding is missing")
    path, digest = binding.get("path"), binding.get("sha256")
    if (not isinstance(path, str) or not path or
            not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise pack.PackError("current graphics source binding is unbound")
    target = Path(path) if Path(path).is_absolute() else root / path
    if not target.resolve().is_relative_to(root.resolve()) or target.is_symlink():
        raise pack.PackError("current graphics source binding escapes its source root")
    try:
        actual = pack.sha256(target.read_bytes())
    except OSError as exc:
        raise pack.PackError(f"cannot read current graphics source binding: {path}") from exc
    if actual != digest:
        raise pack.PackError(f"current graphics source binding changed: {path}")


def current_graphics_contract(contract: dict, *, source_root: Path = ROOT) -> dict:
    """Validate the root-owned source proposal; this grants no publication.

    The same current-engine domain drives catalog admission and the table ABI.
    Origins never fall back to the historical bank-$5B prototype reservation.
    """
    if (not isinstance(contract, dict) or
            contract.get("kind") != "lyra.current_engine_source_contract.v1" or
            contract.get("scope") != "source_review_only"):
        raise pack.PackError("unsupported current graphics source contract")
    expected = dict(first_map=160, end_map=192, native_parent_count=160,
                    parent_count=192)
    domain = contract.get("source_domain")
    if (not isinstance(domain, dict) or set(domain) != set(expected) or
            any(type(domain[k]) is not int or domain[k] != v
                for k, v in expected.items())):
        raise pack.PackError("current graphics domain must be native160 plus A0..BF")
    if (contract.get("engine_head") != "8b004e65efacbd0777121c49a36f09a43759c922" or
            contract.get("base_head") != "c19cf98873c0d409043b1d59016633f415b72dba"):
        raise pack.PackError("current graphics engine/base provenance changed")
    for flag in ("allocation_granted", "publication_authorized",
                 "producer_enforcement_verified", "ordinary_build_ready",
                 "runtime_admission"):
        if contract.get(flag) is not False:
            raise pack.PackError("current graphics source tables cannot grant publication")
    origins = contract.get("origins")
    origin = origins.get("graphics") if isinstance(origins, dict) else None
    if origin is None:
        raise pack.PackError("current graphics origin is unbound; no table emission")
    pack._fields(origin, {"pc", "snes", "source_binding"}, "current graphics origin")
    pc, snes = origin["pc"], origin["snes"]
    if (not isinstance(pc, list) or not isinstance(snes, list) or
            len(pc) != 2 or len(snes) != 2 or
            any(type(v) is not int for v in pc + snes)):
        raise pack.PackError("current graphics origin requires explicit numeric intervals")
    start, end = snes
    if (not 0 <= start <= 0xFFFFFF or start & 0x8000 == 0 or
            start >> 16 in (0x7E, 0x7F) or
            not start < end <= ((start >> 16) + 1) << 16 or
            not 0 <= pc[0] < pc[1] <= 0x400000 or
            pc[0] != ((start & 0x7F0000) >> 1) + (start & 0x7FFF) or
            pc[1] - pc[0] != end - start):
        raise pack.PackError("current graphics origin must fit one mapped LoROM bank")
    _source_binding(origin["source_binding"], source_root)
    _source_binding(contract.get("ledger"), source_root)
    return dict(parent_count=192, first_map=160, end_map=192,
                origin=start, end=end, bank=start >> 16)


def merge_normal(records: list[dict]) -> list[dict]:
    """Coalesce exact adjacent slices; preserve declared order and every gap."""
    merged = []
    for record in records:
        current = dict(record)
        previous = merged[-1] if merged else None
        if (previous and previous["resource_id"] == current["resource_id"] and
                previous["source_offset"] + previous["byte_count"] == current["source_offset"] and
                previous["vram_word_address"] + previous["byte_count"] // 2 == current["vram_word_address"]):
            previous["byte_count"] += current["byte_count"]
        else:
            merged.append(current)
    return merged


def profile_label(profile_id: str) -> str:
    return "SharedGraphicsProfile_" + pack.sha256(profile_id.encode())


def validate_authoring_contracts(catalog: dict, assets: dict[str, bytes]) -> None:
    """Opt-in art contracts constrain pixels, never all SNES 4bpp resources.

    Native high-palette imports must express background as transparent index0;
    palette column8 is not an alternate background color on the hardware.
    """
    for profile_id, profile in catalog["profiles"].items():
        contract = profile.get("authoring_contract")
        if contract is None:
            continue
        pack._fields(contract, {"schema_version", "kind", "background_pixel_index",
                              "forbidden_opaque_indices"}, "graphics authoring contract")
        if (type(contract["schema_version"]) is not int or contract["schema_version"] != 1 or
                contract["kind"] != "native-high-import" or
                type(contract["background_pixel_index"]) is not int or
                contract["background_pixel_index"] != 0):
            raise pack.PackError("unsupported graphics authoring contract")
        forbidden = pack.list_value(contract["forbidden_opaque_indices"],
                                    "forbidden opaque indices", nonempty=True)
        for value in forbidden:
            if pack.integer(value, "forbidden opaque index", 15) == 0:
                raise pack.PackError("transparent background cannot be forbidden")
        if forbidden != sorted(set(forbidden)):
            raise pack.PackError("forbidden opaque indices must be unique and sorted")
        if 8 not in forbidden:
            raise pack.PackError("native-high-import must forbid opaque index 8")
        for transfer in profile["transfers"]:
            start = transfer.get("source_offset", 0)
            data = assets[transfer["resource_id"]][start:start + transfer["byte_count"]]
            for at in range(0, len(data), 32):
                for row in range(8):
                    planes = [data[at + row * 2], data[at + row * 2 + 1],
                              data[at + 16 + row * 2], data[at + 17 + row * 2]]
                    for bit in range(8):
                        index = sum(((value >> bit) & 1) << plane
                                    for plane, value in enumerate(planes))
                        if index in forbidden:
                            raise pack.PackError(
                                f"profile {profile_id} violates native-high-import "
                                f"authoring contract: forbidden opaque index {index}")


def render(catalog: dict, assets: dict[str, bytes], policy: dict,
           catalog_dir: Path, output_dir: Path, *, legacy_root: Path = ROOT,
           current_contract: dict | None = None,
           source_root: Path = ROOT,
           resident_native: dict | None = None) -> tuple[str, dict]:
    current = (current_graphics_contract(current_contract, source_root=source_root)
               if current_contract is not None else None)
    parent_count = current["parent_count"] if current else 160
    lowered = pack.lower_runtime_policy(catalog, assets, policy,
                                        parent_count=parent_count)
    resident = None
    external = {}
    if resident_native is not None:
        if current is None:
            raise pack.PackError("resident resources require the explicit current source contract")
        pack._fields(resident_native, {"plan", "emission", "preimage"}, "resident native input")
        build_modules = str(ROOT / "Scripts/Build")
        if build_modules not in sys.path:
            sys.path.insert(0, build_modules)
        from lyra_resident_graphics import resident_runtime_inputs
        try:
            resident = resident_runtime_inputs(resident_native["plan"],
                resident_native["emission"], preimage=resident_native["preimage"])
        except ValueError as exc:
            raise pack.PackError(str(exc)) from exc
        if (set(lowered["profiles"]) & set(resident["profiles"]) or
                set(catalog["resources"]) & set(resident["resources"])):
            raise pack.PackError("resident resource/profile identifier collides with saved catalog")
        lowered["profiles"].update(resident["profiles"])
        lowered["parents"].update(resident["parents"])
        external = resident["resources"]
    if current:
        missing = [parent for parent in range(current["first_map"], current["end_map"])
                   if str(parent) not in lowered["parents"]]
        if missing:
            raise pack.PackError("current graphics requires saved catalog rows for every "
                                 "tail parent: " + ",".join(f"{p:02X}" for p in missing))
    validate_authoring_contracts(catalog, assets)
    profiles = {key: value for key, value in lowered["profiles"].items()
                if value["runtime_enabled"]}
    if resident is not None:
        bound_profiles = {row["profile_id"] for row in lowered["parents"].values()}
        profiles = {key: value for key, value in profiles.items() if key in bound_profiles}
    used = {t["resource_id"] for p in profiles.values() for t in p["normal"]}
    # Current c19 owns these two existing payload labels. Historical docks
    # labels at $448000/$44A000 are not current grants: emit those resources
    # inside the explicitly bound current graphics interval instead.
    aliases = ({"gfx/boat.bin": "BoatBitmap", "gfx/boat2.bin": "AdditionalBitmap"}
               if current else LEGACY_ALIASES)
    labels, payloads = {}, {}
    for resource_id in sorted(used):
        if resource_id in external:
            # The authenticated resident emitter already owns these bytes.
            # Long addresses need no duplicate incbin or same-bank relocation.
            labels[resource_id] = f"${external[resource_id]['snes']:06X}"
            continue
        resource = catalog["resources"][resource_id]
        path = resource["path"]
        if path in aliases:
            expected = legacy_root / "Overworld" / path
            try:
                if expected.read_bytes() != assets[resource_id]:
                    raise pack.PackError(f"existing label bytes differ: {path}")
            except OSError as exc:
                raise pack.PackError(f"cannot verify existing label bytes: {path}") from exc
            labels[resource_id] = aliases[path]
        else:
            digest = pack.sha256(assets[resource_id])
            label = "SharedGraphicsResource_" + digest
            labels[resource_id] = label
            relative = Path(os.path.relpath(catalog_dir / path, output_dir)).as_posix()
            if any(c in relative for c in ('"', "\n", "\r")):
                raise pack.PackError("resource path cannot be represented safely in ASM")
            payloads.setdefault(label, (relative, assets[resource_id]))

    normal = {key: merge_normal(p["normal"]) for key, p in profiles.items()}
    table_bytes = parent_count * 2 + sum(22 + 7 * len(normal[key]) + 8 * len(p["staging"])
                              for key, p in profiles.items())
    payload_bytes = sum(len(data) for _, data in payloads.values())
    capacity = current["end"] - current["origin"] if current else 0x8000
    if table_bytes + payload_bytes > capacity:
        raise pack.PackError("runtime tables and new resources exceed bank $5B")
    if resident is not None:
        pc = current_contract["origins"]["graphics"]["pc"]
        if any(pc[0] < row["pc"][1] and row["pc"][0] < pc[1]
               for row in resident_native["emission"]["placements"]):
            raise pack.PackError("resident payload overlaps the current graphics interval")

    def source(t):
        return f"{labels[t['resource_id']]}+${t['source_offset']:04X}"

    lines = ["; Generated by Scripts/Graphics/compile_runtime_graphics.py; do not edit.",
             "; Same-bank word pointers. Parent $00A0..$FFFF is never an index.",
             "; Include inside the caller's reserved bank $5B; no org or hooks here."]
    constants = dict(CONSTANTS)
    if current:
        constants.update(Bank=current["bank"], ParentCount=parent_count)
        lines[1:3] = ["; Current source contract: native160 plus explicit saved A0..BF rows.",
                      "; Same-bank pointers; source proposal only, no publication grant."]
    lines.extend(f"!GfxRT_{name} = ${value:04X}" for name, value in constants.items())
    origin_assert = (f"assert pc() == ${current['origin']:06X}" if current
                     else "assert pc() >= $5B8000")
    lines += [origin_assert, "assert (pc()>>16) == !GfxRT_Bank",
              "SharedGraphicsParentProfiles:"]
    for parent in range(parent_count):
        bound = lowered["parents"].get(str(parent))
        target = (profile_label(bound["profile_id"]) + "&$FFFF"
                  if bound and bound["runtime_enabled"] else "$0000")
        lines.append(f"  dw {target} ; ${parent:02X}")
    modes = {"source_range": 1, "source_start": 2, "native_staging": 3}
    for key, p in profiles.items():
        label = profile_label(key)
        transition, late = p["transition"], p["late"]
        t = transition.get("transfer")
        lines += [f"; {pack.json.dumps(key)}", f"{label}:",
                  f"  dw ${len(normal[key]):04X},{label}_Normal&$FFFF",
                  f"  db ${p['cache_slot_mask']:02X},${modes[transition['mode']]:02X}",
                  f"  dw ${transition.get('target_start_word', 0):04X},${transition.get('target_end_word', 0):04X}",
                  f"  dl {source(t) if t else '$000000'}",
                  f"  dw ${len(p['staging']):04X}," + (f"{label}_Staging&$FFFF" if p["staging"] else "$0000"),
                  f"  db ${late['first_step'] if late else 0:02X},${late['end_step'] if late else 0:02X}",
                  f"  dl {source(late['transfer']) if late else '$000000'}",
                  f"assert pc()-{label} == !GfxRT_HeaderSize", f"{label}_Normal:"]
        for t in normal[key]:
            lines += [f"  dl {source(t)}", f"  dw ${t['vram_word_address']:04X},${t['byte_count']:04X}"]
        lines += [f"assert pc()-{label}_Normal == ${len(normal[key]) * 7:04X}"]
        if p["staging"]:
            lines.append(f"{label}_Staging:")
            for t in p["staging"]:
                lines += [f"  dl {source(t)},${t['wram_address']:06X}", f"  dw ${t['byte_count']:04X}"]
            lines += [f"assert pc()-{label}_Staging == ${len(p['staging']) * 8:04X}",
                      f"assert ({label}_Staging>>16) == !GfxRT_Bank"]
        lines += [f"assert ({label}>>16) == !GfxRT_Bank",
                  f"assert ({label}_Normal>>16) == !GfxRT_Bank"]
    for label, (path, data) in sorted(payloads.items()):
        lines += [f"{label}:", f'  incbin "{path}"', f"{label}_End:",
                  f"assert {label}_End-{label} == ${len(data):04X}"]
    # Each resource fits one CPU bank. Every normal/source/staging/late DMA is
    # a validated slice of that resource; none can wrap the 16-bit DMA source.
    for resource_id in sorted(used):
        label = labels[resource_id]
        count = (external[resource_id]["byte_count"] if resource_id in external
                 else len(assets[resource_id]))
        lines += [f"assert (({label}&$FFFF)+${count:04X}) <= $10000"]
    lines += ["SharedGraphicsTablesEnd:",
              "assert (SharedGraphicsTablesEnd>>16) == !GfxRT_Bank",
              (f"assert SharedGraphicsTablesEnd <= ${current['end']:06X}" if current
               else "assert SharedGraphicsTablesEnd <= $5C0000")]
    report = dict(schema_version=1, enabled_profiles=list(profiles),
                  parent_profiles={parent: b["profile_id"] for parent, b in lowered["parents"].items()
                                   if b["runtime_enabled"]},
                  normal_counts={key: len(value) for key, value in normal.items()},
                  staging_counts={key: len(p["staging"]) for key, p in profiles.items()},
                  table_bytes=table_bytes, new_payload_bytes=payload_bytes,
                  new_payload_count=len(payloads), aliases={key: labels[key] for key in sorted(used)
                  if key not in external and catalog["resources"][key]["path"] in aliases})
    if resident is not None:
        report.update(resident_bridge=resident,
                      external_resource_count=len(external),
                      external_resource_bytes=sum(row["byte_count"] for row in external.values()))
    if current:
        report.update(current_mode=True, parent_count=parent_count,
                      source_contract_sha256=pack.sha256(pack.json_bytes(current_contract)),
                      generated_sha256=pack.sha256(("\n".join(lines) + "\n").encode()),
                      graphics_origin_snes=[current["origin"], current["end"]],
                      status="source tables only; no publication grant",
                      unsupported_fields=["graphics_sheets", "main_palette", "palette_set",
                          "animated_sheet", "sprite_graphics", "sprite_palettes",
                          "actors", "entries", "save/return", "world-map", "mirror", "flight"])
    return "\n".join(lines) + "\n", report


def compile_tables(catalog_path: Path, policy_path: Path, output: Path, *,
                   current_contract_path: Path | None = None) -> tuple[str, dict]:
    before = {catalog_path: catalog_path.read_bytes(), policy_path: policy_path.read_bytes()}
    current_contract = None
    if current_contract_path is not None:
        before[current_contract_path] = current_contract_path.read_bytes()
        current_contract = pack.read_json(current_contract_path)
        current_graphics_contract(current_contract)
    catalog, assets = pack.load(catalog_path,
                                parent_count=192 if current_contract else 160)
    policy = pack.read_json(policy_path)
    protected = set(before) | {catalog_path.parent / r["path"] for r in catalog["resources"].values()}
    if current_contract:
        for binding in (current_contract["ledger"],
                        current_contract["origins"]["graphics"]["source_binding"]):
            target = Path(binding["path"])
            protected.add(target if target.is_absolute() else ROOT / target)
    canonical_path = ROOT / "Overworld/graphics_catalog.json"
    canonical, _ = pack.load(canonical_path)
    protected.update({canonical_path, ROOT / "Overworld/graphics_runtime_policy.json"})
    protected.update(canonical_path.parent / r["path"] for r in canonical["resources"].values())
    protected.update(ROOT / "Overworld" / path for path in LEGACY_ALIASES)
    if output.is_symlink() or output.resolve() in {p.resolve() for p in protected}:
        raise pack.PackError("output overlaps an input or is a symlink")
    text, report = render(catalog, assets, policy, catalog_path.parent, output.parent,
                          current_contract=current_contract)
    for path, data in before.items():
        if path.read_bytes() != data:
            raise pack.PackError(f"input changed during compilation: {path}")
    for key, resource in catalog["resources"].items():
        if (catalog_path.parent / resource["path"]).read_bytes() != assets[key]:
            raise pack.PackError("resource changed during compilation")
    if current_contract:
        current_graphics_contract(current_contract)
    report["generated_sha256"] = pack.sha256(text.encode())
    return text, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "Overworld/graphics_catalog.json")
    parser.add_argument("--policy", type=Path, default=ROOT / "Overworld/graphics_runtime_policy.json")
    parser.add_argument("--output", type=Path,
                        help="default: historical Overworld table or current Data/Generated table")
    parser.add_argument("--current-contract", type=Path,
                        help="explicit current-engine source contract; unbound origins refuse")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="verify generated ASM; never write")
    mode.add_argument("--write", action="store_true", help="explicitly update generated ASM")
    args = parser.parse_args(argv)
    if args.output is None:
        args.output = ROOT / ("Data/Generated/lyra_project/graphics_runtime_tables.asm"
                              if args.current_contract else "Overworld/graphics_runtime_tables.asm")
    try:
        text, report = compile_tables(args.catalog, args.policy, args.output,
                                      current_contract_path=args.current_contract)
        if args.check:
            if args.output.read_text() != text:
                raise pack.PackError("generated runtime tables are stale; run with --write")
        else:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent,
                                             prefix=".graphics-runtime-", delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    stream.write(text)
                    stream.flush()
                    os.replace(temporary, args.output)
                finally:
                    temporary.unlink(missing_ok=True)
        print(pack.json.dumps(report, sort_keys=True))
        return 0
    except (OSError, pack.PackError) as exc:
        print(f"runtime graphics: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
