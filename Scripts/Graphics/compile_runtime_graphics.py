#!/usr/bin/env python3
"""Lower the canonical graphics catalog/policy to the bank-$5B runtime ABI.

This command never reads or writes a ROM. --write explicitly updates generated
ASM; --check verifies it without writing. Executable helpers own hook timing.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
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
           catalog_dir: Path, output_dir: Path, *, legacy_root: Path = ROOT) -> tuple[str, dict]:
    lowered = pack.lower_runtime_policy(catalog, assets, policy)
    validate_authoring_contracts(catalog, assets)
    profiles = {key: value for key, value in lowered["profiles"].items()
                if value["runtime_enabled"]}
    used = {t["resource_id"] for p in profiles.values() for t in p["normal"]}
    labels, payloads, aliases = {}, {}, {}
    legacy_assets = {}

    def legacy_bytes(path):
        if path not in legacy_assets:
            try:
                legacy_assets[path] = (legacy_root / "Overworld" / path).read_bytes()
            except OSError as exc:
                raise pack.PackError(f"cannot verify existing label bytes: {path}") from exc
        return legacy_assets[path]

    for resource_id in sorted(used):
        resource = catalog["resources"][resource_id]
        path = resource["path"]
        if path in LEGACY_ALIASES:
            # Preserve the explicit canonical-path contract: changed content
            # cannot silently replace an existing payload through its label.
            if legacy_bytes(path) != assets[resource_id]:
                raise pack.PackError(f"existing label bytes differ: {path}")
            alias = LEGACY_ALIASES[path]
        else:
            # Portable packs rename assets by content. Reuse only a vetted
            # label whose actual source bytes match, never a claimed hash/ID.
            matches = [label for name, label in LEGACY_ALIASES.items()
                       if legacy_bytes(name) == assets[resource_id]]
            if len(matches) > 1:
                raise pack.PackError(f"ambiguous existing label bytes: {resource_id}")
            alias = matches[0] if matches else None
        if alias is not None:
            labels[resource_id] = aliases[resource_id] = alias
        else:
            digest = pack.sha256(assets[resource_id])
            label = "SharedGraphicsResource_" + digest
            labels[resource_id] = label
            relative = Path(os.path.relpath(catalog_dir / path, output_dir)).as_posix()
            if any(c in relative for c in ('"', "\n", "\r")):
                raise pack.PackError("resource path cannot be represented safely in ASM")
            payloads.setdefault(label, (relative, assets[resource_id]))

    normal = {key: merge_normal(p["normal"]) for key, p in profiles.items()}
    table_bytes = 160 * 2 + sum(22 + 7 * len(normal[key]) + 8 * len(p["staging"])
                              for key, p in profiles.items())
    payload_bytes = sum(len(data) for _, data in payloads.values())
    if table_bytes + payload_bytes > 0x8000:
        raise pack.PackError("runtime tables and new resources exceed bank $5B")

    def source(t):
        return f"{labels[t['resource_id']]}+${t['source_offset']:04X}"

    lines = ["; Generated by Scripts/Graphics/compile_runtime_graphics.py; do not edit.",
             "; Same-bank word pointers. Parent $00A0..$FFFF is never an index.",
             "; Include inside the caller's reserved bank $5B; no org or hooks here."]
    lines.extend(f"!GfxRT_{name} = ${value:04X}" for name, value in CONSTANTS.items())
    lines += ["assert pc() >= $5B8000", "assert (pc()>>16) == !GfxRT_Bank",
              "SharedGraphicsParentProfiles:"]
    for parent in range(160):
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
        label, count = labels[resource_id], len(assets[resource_id])
        lines += [f"assert (({label}&$FFFF)+${count:04X}) <= $10000"]
    lines += ["SharedGraphicsTablesEnd:",
              "assert (SharedGraphicsTablesEnd>>16) == !GfxRT_Bank",
              "assert SharedGraphicsTablesEnd <= $5C0000"]
    report = dict(schema_version=1, enabled_profiles=list(profiles),
                  parent_profiles={parent: b["profile_id"] for parent, b in lowered["parents"].items()
                                   if b["runtime_enabled"]},
                  normal_counts={key: len(value) for key, value in normal.items()},
                  staging_counts={key: len(p["staging"]) for key, p in profiles.items()},
                  table_bytes=table_bytes, new_payload_bytes=payload_bytes,
                  new_payload_count=len(payloads), aliases=aliases)
    return "\n".join(lines) + "\n", report


def compile_tables(catalog_path: Path, policy_path: Path, output: Path) -> tuple[str, dict]:
    before = {catalog_path: catalog_path.read_bytes(), policy_path: policy_path.read_bytes()}
    catalog, assets = pack.load(catalog_path)
    policy = pack.read_json(policy_path)
    protected = set(before) | {catalog_path.parent / r["path"] for r in catalog["resources"].values()}
    canonical_path = ROOT / "Overworld/graphics_catalog.json"
    canonical, _ = pack.load(canonical_path)
    protected.update({canonical_path, ROOT / "Overworld/graphics_runtime_policy.json"})
    protected.update(canonical_path.parent / r["path"] for r in canonical["resources"].values())
    protected.update(ROOT / "Overworld" / path for path in LEGACY_ALIASES)
    if output.is_symlink() or output.resolve() in {p.resolve() for p in protected}:
        raise pack.PackError("output overlaps an input or is a symlink")
    text, report = render(catalog, assets, policy, catalog_path.parent, output.parent)
    for path, data in before.items():
        if path.read_bytes() != data:
            raise pack.PackError(f"input changed during compilation: {path}")
    for key, resource in catalog["resources"].items():
        if (catalog_path.parent / resource["path"]).read_bytes() != assets[key]:
            raise pack.PackError("resource changed during compilation")
    report["generated_sha256"] = pack.sha256(text.encode())
    return text, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "Overworld/graphics_catalog.json")
    parser.add_argument("--policy", type=Path, default=ROOT / "Overworld/graphics_runtime_policy.json")
    parser.add_argument("--output", type=Path, default=ROOT / "Overworld/graphics_runtime_tables.asm")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="verify generated ASM; never write")
    mode.add_argument("--write", action="store_true", help="explicitly update generated ASM")
    args = parser.parse_args(argv)
    try:
        text, report = compile_tables(args.catalog, args.policy, args.output)
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
