#!/usr/bin/env python3
"""Compile a portable overworld graphics pack without opening or writing a ROM.

The canonical format is Yaze's version 2 resource/profile/binding catalog. Version
1 area manifests can be migrated: individual 32-byte glyphs in an area are
bundled, preserving their destinations through source_offset slices. Outputs
include a version 1 compatibility preview and proposed Asar descriptor data.
The generated ASM is not included by the game: upload timing, cache policy and
safe ROM allocation still belong to the runtime adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


class PackError(ValueError):
    """A catalog or its resource bytes do not satisfy the shared format."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(document: object) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise PackError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackError(f"cannot read catalog {path}: {exc}") from exc


def integer(value: object, name: str, maximum: int = 0x7FFFFFFF) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise PackError(f"invalid {name}: {value!r}")
    return value


def object_value(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise PackError(f"{name} must be an object")
    return value


def list_value(value: object, name: str, *, nonempty: bool = False) -> list:
    if not isinstance(value, list) or (nonempty and not value):
        raise PackError(f"{name} must be {'a nonempty' if nonempty else 'an'} array")
    return value


def string_value(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PackError(f"{name} must be a nonempty string")
    return value


def read_asset(root: Path, path: object, count: object, *, portable: bool) -> bytes:
    name = string_value(path, "resource path")
    amount = integer(count, "resource byte_count", 0x8000)
    if not amount or amount % 32:
        raise PackError("resource size must be 32-byte aligned and at most $8000")
    # Legacy manifests may point at ../../Overworld/gfx. Canonical packs resolve
    # entirely inside their directory and remain valid after a folder move.
    relative = PurePosixPath(name)
    if portable and (relative.is_absolute() or ".." in relative.parts or "\\" in name):
        raise PackError(f"resource path is not portable: {name}")
    target = root / name
    if portable and not target.resolve().is_relative_to(root.resolve()):
        raise PackError(f"resource escapes pack directory: {name}")
    try:
        if target.stat().st_size != amount:
            raise PackError(f"wrong resource byte count: {name}")
        data = target.read_bytes()
    except OSError as exc:
        raise PackError(f"cannot read resource {name}: {exc}") from exc
    if len(data) != amount:
        raise PackError(f"resource changed during read: {name}")
    return data


def _characters(base: int, destination: object, count: object) -> range:
    target = integer(destination, "VRAM word address", 0x7FFF)
    amount = integer(count, "transfer byte_count", 0x8000)
    offset = (target - base) * 2
    if (not amount or amount % 32 or offset < 0 or offset % 32 or
            offset + amount > 0x8000 or target * 2 + amount > 0x10000):
        raise PackError("transfer must contain aligned 4bpp BG characters within VRAM")
    return range(offset // 32, (offset + amount) // 32)


def _parent_count(value: int) -> int:
    if type(value) is not int or value not in (160, 192):
        raise PackError("parent_count must explicitly select native160 or current192")
    return value


def validate(catalog: dict, assets: dict[str, bytes], *,
             parent_count: int = 160) -> dict[int, tuple[int, dict[int, bytes]]]:
    """Resolve exact native character bytes, using the same bounds as Yaze."""
    parent_count = _parent_count(parent_count)
    if integer(catalog.get("schema_version"), "schema_version") != 2:
        raise PackError("canonical graphics packs use schema_version 2")
    resources = object_value(catalog.get("resources"), "resources")
    profiles = object_value(catalog.get("profiles"), "profiles")
    bindings = list_value(catalog.get("bindings"), "bindings")
    if set(resources) != set(assets):
        raise PackError("resource identities differ from loaded assets")
    for resource_id, resource in resources.items():
        string_value(resource_id, "resource ID")
        object_value(resource, "resource")
        if resource.get("format") != "snes4bpp":
            raise PackError("resource format must be snes4bpp")
        count = integer(resource.get("byte_count"), "resource byte_count", 0x8000)
        if not count or count % 32 or count != len(assets[resource_id]):
            raise PackError(f"invalid resource size: {resource_id}")
        digest = resource.get("sha256")
        if (not isinstance(digest, str) or len(digest) != 64 or
                any(c not in "0123456789abcdefABCDEF" for c in digest) or
                digest.lower() != sha256(assets[resource_id])):
            raise PackError(f"resource SHA256 mismatch: {resource_id}")
    resolved_profiles = {}
    for profile_id, profile in profiles.items():
        string_value(profile_id, "profile ID")
        object_value(profile, "profile")
        base = integer(profile.get("bg_character_base_word"), "BG base", 0x4000)
        characters = {}
        for transfer in list_value(profile.get("transfers"), "transfers", nonempty=True):
            object_value(transfer, "transfer")
            resource_id = transfer.get("resource_id")
            if not isinstance(resource_id, str) or resource_id not in assets:
                raise PackError(f"unknown resource: {resource_id!r}")
            offset = integer(transfer.get("source_offset", 0), "source_offset")
            count = integer(transfer.get("byte_count"), "transfer byte_count", 0x8000)
            data = assets[resource_id]
            if offset % 32 or offset > len(data) or count > len(data) - offset:
                raise PackError("invalid resource slice")
            ids = _characters(base, transfer.get("vram_word_address"), count)
            for index, character in enumerate(ids):
                if character in characters:
                    raise PackError(f"overlapping transfers in {profile_id}")
                start = offset + index * 32
                characters[character] = data[start:start + 32]
        resolved_profiles[profile_id] = (base, characters)
    result = {}
    for binding in bindings:
        object_value(binding, "binding")
        profile_id = binding.get("profile_id")
        if not isinstance(profile_id, str) or profile_id not in profiles:
            raise PackError(f"unknown profile: {profile_id!r}")
        for parent in list_value(binding.get("parent_maps"), "parent_maps", nonempty=True):
            parent = integer(parent, "parent_map", parent_count - 1)
            if parent in result:
                raise PackError(f"duplicate parent_map: {parent}")
            result[parent] = resolved_profiles[profile_id]
    return result


def load_v2(path: Path, document: dict, *,
            parent_count: int = 160) -> tuple[dict, dict[str, bytes]]:
    assets = {}
    for resource_id, resource in object_value(document.get("resources"), "resources").items():
        object_value(resource, "resource")
        assets[resource_id] = read_asset(path.parent, resource.get("path"),
                                        resource.get("byte_count"), portable=True)
    validate(document, assets, parent_count=parent_count)
    return document, assets


def migrate_v1(path: Path, document: dict) -> tuple[dict, dict[str, bytes]]:
    catalog = {"schema_version": 2, "resources": {}, "profiles": {}, "bindings": []}
    assets = {}

    def add_resource(data: bytes) -> str:
        digest = sha256(data)
        resource_id = "snes4bpp:" + digest
        assets[resource_id] = data
        catalog["resources"][resource_id] = {
            "path": f"assets/{digest}.4bpp.bin", "format": "snes4bpp",
            "byte_count": len(data), "sha256": digest}
        return resource_id

    for area in list_value(document.get("areas"), "areas"):
        object_value(area, "area")
        parent = integer(area.get("parent_map"), "parent_map", 159)
        profile_id = f"ow-parent-{parent:02x}"
        if profile_id in catalog["profiles"]:
            raise PackError(f"duplicate parent_map: {parent}")
        transfers = list_value(area.get("transfers"), "transfers", nonempty=True)
        raw = []
        for transfer in transfers:
            object_value(transfer, "legacy transfer")
            if transfer.get("format") != "snes4bpp":
                raise PackError("legacy transfer format must be snes4bpp")
            raw.append(read_asset(path.parent, transfer.get("path"),
                                  transfer.get("byte_count"), portable=False))
        # Bundle only glyph-sized resources. Larger source payloads keep their
        # exact identity, including the existing docks and ship ABI assets.
        glyphs = b"".join(data for data in raw if len(data) == 32)
        if len(glyphs) > 0x8000:
            raise PackError("legacy glyph bundle exceeds $8000 bytes")
        glyph_resource = add_resource(glyphs) if glyphs else None
        glyph_offset = 0
        compiled = []
        for transfer, data in zip(transfers, raw):
            if len(data) == 32:
                resource_id, offset = glyph_resource, glyph_offset
                glyph_offset += 32
            else:
                resource_id, offset = add_resource(data), 0
            compiled.append({"resource_id": resource_id, "source_offset": offset,
                             "byte_count": len(data),
                             "vram_word_address": transfer.get("vram_word_address")})
        catalog["profiles"][profile_id] = {
            "bg_character_base_word": area.get("bg_character_base_word"),
            "transfers": compiled}
        catalog["bindings"].append({"parent_maps": [parent], "profile_id": profile_id})
    validate(catalog, assets)
    return catalog, assets


def load(path: Path, *, parent_count: int = 160) -> tuple[dict, dict[str, bytes]]:
    parent_count = _parent_count(parent_count)
    document = object_value(read_json(path), "catalog")
    version = integer(document.get("schema_version"), "schema_version")
    if version == 1:
        if parent_count != 160:
            raise PackError("current192 requires a canonical saved V2 catalog")
        return migrate_v1(path, document)
    if version == 2:
        return load_v2(path, document, parent_count=parent_count)
    raise PackError(f"unsupported schema_version: {version}")


def compatibility(catalog: dict, assets: dict[str, bytes]) -> tuple[dict, dict[str, bytes]]:
    """V1 cannot slice resources; materialize its exact transfer bytes separately."""
    areas, slices = [], {}
    for binding in catalog["bindings"]:
        profile = catalog["profiles"][binding["profile_id"]]
        transfers = []
        for transfer in profile["transfers"]:
            start, count = transfer.get("source_offset", 0), transfer["byte_count"]
            data = assets[transfer["resource_id"]][start:start + count]
            # Frozen V1 needs one file per sparse glyph. These are compatibility
            # exports only; the canonical V2 catalog uses the bundled payload.
            path = f"compat-assets/{sha256(data)}.4bpp.bin"
            slices[path] = data
            transfers.append({"path": path, "format": "snes4bpp", "byte_count": count,
                              "vram_word_address": transfer["vram_word_address"]})
        for parent in binding["parent_maps"]:
            areas.append({"parent_map": parent,
                          "bg_character_base_word": profile["bg_character_base_word"],
                          "transfers": transfers})
    return {"schema_version": 1, "areas": sorted(areas, key=lambda a: a["parent_map"])}, slices


def descriptor_asm(catalog: dict) -> str:
    """Emit unallocated data, never executable hooks or inferred upload phases."""
    profiles = sorted(catalog["profiles"])
    if len(profiles) > 255:
        raise PackError("descriptor format supports at most 255 profiles")
    indices = {profile_id: index for index, profile_id in enumerate(profiles)}
    parents = [255] * 160
    for binding in catalog["bindings"]:
        for parent in binding["parent_maps"]:
            parents[parent] = indices[binding["profile_id"]]
    lines = ["; Generated by compile_graphics_pack.py. Proposed data only; no org/hooks.",
             "; Caller owns ROM placement and runtime phase/cache policies.",
             "; Parent table: profile index, $FF = native graphics.",
             "; Profile: BG base word, first transfer record index, transfer count (3 words).",
             "; Transfer: source long, destination word, byte count word (7 bytes).",
             "GraphicsPackParentProfiles:"]
    for start in range(0, 160, 16):
        lines.append("  db " + ",".join(f"${n:02X}" for n in parents[start:start + 16]))
    lines.append("GraphicsPackProfiles:")
    first = 0
    for profile_id in profiles:
        profile = catalog["profiles"][profile_id]
        count = len(profile["transfers"])
        if first + count > 0xFFFF:
            raise PackError("descriptor transfer count exceeds 16-bit indices")
        lines.append(f"  ; {json.dumps(profile_id)}")
        lines.append(f"  dw ${profile['bg_character_base_word']:04X},${first:04X},${count:04X}")
        first += count
    resources = sorted(catalog["resources"])
    # Hash-derived labels avoid injecting arbitrary catalog IDs into ASM.
    labels = {key: "GraphicsPackResource_" + sha256(key.encode()) for key in resources}
    lines.append("GraphicsPackTransfers:")
    for profile_id in profiles:
        for transfer in catalog["profiles"][profile_id]["transfers"]:
            offset = transfer.get("source_offset", 0)
            lines.append(f"  dl {labels[transfer['resource_id']]}+${offset:04X}")
            lines.append(f"  dw ${transfer['vram_word_address']:04X},${transfer['byte_count']:04X}")
    lines.append("GraphicsPackTransferEnd:")
    lines.append("; Resource placement must keep each DMA source within one CPU bank.")
    for resource_id in resources:
        resource = catalog["resources"][resource_id]
        # Resources are emitted to safe, generated names by compile_pack.
        path = f"assets/{resource['sha256'].lower()}.4bpp.bin"
        label = labels[resource_id]
        lines += [f"{label}:", f'  incbin "{path}"',
                  f"assert {label}+${resource['byte_count']:04X} <= (({label}&$FF0000)+$10000)"]
    return "\n".join(lines) + "\n"


def _fields(value: object, expected: set[str], name: str) -> dict:
    record = object_value(value, name)
    if set(record) != expected:
        raise PackError(f"{name} fields differ: expected {sorted(expected)}")
    return record


def _transfer_reference(value: object, transfers: list[dict]) -> dict:
    """Bind policy to an exact semantic slice, never a sorted numeric index."""
    record = _fields(value, {"resource_id", "source_offset", "vram_word_address",
                             "byte_count"}, "runtime transfer reference")
    string_value(record["resource_id"], "runtime resource ID")
    for key in ("source_offset", "vram_word_address", "byte_count"):
        integer(record[key], f"runtime {key}")
    matches = [dict(t, source_offset=t.get("source_offset", 0)) for t in transfers]
    if record not in matches:
        raise PackError("runtime transfer reference differs from catalog slice/layout")
    return dict(record)


def lower_runtime_policy(catalog: dict, assets: dict[str, bytes], policy: dict, *,
                         parent_count: int = 160) -> dict:
    """Lower explicit phase policy to data. This does not enable an ASM consumer.

    ABI is fixed by the existing helpers: outdoor $1B==0, parent $8A;
    normal A8/XY8, transition A16/XY8 preserving X/Y, late A8/XY16
    preserving X/Y. The policy chooses phases; destinations never imply them.
    """
    validate(catalog, assets, parent_count=parent_count)
    _fields(policy, {"schema_version", "profiles"}, "runtime policy")
    if integer(policy["schema_version"], "runtime policy schema_version") != 1:
        raise PackError("runtime policy schema_version must be 1")
    policies = object_value(policy["profiles"], "runtime profiles")
    if set(policies) != set(catalog["profiles"]):
        raise PackError("runtime policy must name every catalog profile exactly")
    lowered = {}
    for profile_id in sorted(policies):
        p = _fields(policies[profile_id], {"runtime_enabled", "normal", "transition",
                    "cache_slots", "staging", "late"}, f"runtime profile {profile_id}")
        if type(p["runtime_enabled"]) is not bool:
            raise PackError("runtime_enabled must be boolean")
        if p["normal"] != "all_declared_transfers":
            raise PackError("normal policy must explicitly select all_declared_transfers")
        profile = catalog["profiles"][profile_id]
        if profile["bg_character_base_word"] != 0x2000:
            raise PackError("runtime ABI requires BG character base $2000")
        transfers = [dict(t, source_offset=t.get("source_offset", 0))
                     for t in profile["transfers"]]
        slots = list_value(p["cache_slots"], "runtime cache_slots", nonempty=True)
        for slot in slots:
            if integer(slot, "runtime cache slot", 6) < 3:
                raise PackError("runtime cache slots must lie in 3..6")
        if slots != sorted(set(slots)):
            raise PackError("runtime cache slots must be unique and sorted")
        expected_slots = set()
        for t in transfers:
            start, end = t["vram_word_address"], t["vram_word_address"] + t["byte_count"] // 2
            if start < 0x3C00 and end > 0x2C00:
                if start < 0x2C00 or end > 0x3C00:
                    raise PackError("runtime BG slice crosses auxiliary staging bounds")
                expected_slots.update(range((start - 0x2000) // 0x400,
                                            (end - 1 - 0x2000) // 0x400 + 1))
        if set(slots) != expected_slots:
            raise PackError("runtime cache slots differ from declared BG coverage")
        transition = object_value(p["transition"], "runtime transition")
        mode = transition.get("mode")
        staging_records = []
        if mode in ("source_range", "source_start"):
            _fields(transition, {"mode", "transfer"}, "runtime source transition")
            selected = _transfer_reference(transition["transfer"], transfers)
            start, count = selected["vram_word_address"], selected["byte_count"]
            if start % 0x400 or count % 0x800 or not 0x2C00 <= start < 0x3C00 or start + count // 2 > 0x3C00:
                raise PackError("runtime source transition requires complete auxiliary slots")
            if mode == "source_start" and count != 0x800:
                raise PackError("start-only transition must replace exactly one native slot")
            bg = dict(mode=mode, transfer=selected, target_start_word=start,
                      target_end_word=start + count // 2)
            if p["staging"] is not None:
                raise PackError("source substitution cannot also patch native staging")
        elif mode == "native_staging":
            _fields(transition, {"mode"}, "runtime native transition")
            stage = _fields(p["staging"], {"mode", "vram_start_word", "vram_end_word",
                            "wram_base"}, "runtime staging")
            for key in ("vram_start_word", "vram_end_word", "wram_base"):
                integer(stage[key], f"runtime staging {key}")
            if stage != dict(mode="native_after_conversion", vram_start_word=0x2C00,
                             vram_end_word=0x3C00, wram_base=0x7F0000):
                raise PackError("native staging must use the reviewed postconversion $7F buffer")
            for t in transfers:
                if t["byte_count"] != 32 or not 0x2C00 <= t["vram_word_address"] < 0x3C00:
                    raise PackError("sparse staging requires individual auxiliary 32-byte glyphs")
                staging_records.append(dict(t, wram_address=0x7F0000 +
                                            2 * (t["vram_word_address"] - 0x2C00)))
            bg = dict(mode=mode, source_bank=0x7F)
        else:
            raise PackError(f"unknown runtime transition mode: {mode!r}")
        late = None
        if p["late"] is not None:
            spec = _fields(p["late"], {"transfer", "first_step", "end_step", "chunk_bytes"},
                           "runtime late phase")
            selected = _transfer_reference(spec["transfer"], transfers)
            for key in ("first_step", "end_step", "chunk_bytes"):
                integer(spec[key], f"runtime late {key}", 0xFFFF)
            if (spec["first_step"], spec["end_step"], spec["chunk_bytes"]) != (0x50, 0x60, 512):
                raise PackError("late ABI requires existing $50..$5F steps and 512-byte chunks")
            if selected["byte_count"] != 8192 or selected["vram_word_address"] != 0x5000:
                raise PackError("late ABI requires the declared full $5000 extended slice")
            late = dict(spec, chunks=[dict(step=step, resource_id=selected["resource_id"],
                        source_offset=selected["source_offset"] + (step - 0x50) * 512,
                        vram_word_address=0x5000 + (step - 0x50) * 256, byte_count=512)
                        for step in range(0x50, 0x60)])
        assigned = staging_records if mode == "native_staging" else [bg["transfer"]]
        covered = [{k: t[k] for k in ("resource_id", "source_offset", "vram_word_address", "byte_count")}
                   for t in assigned]
        if late is not None:
            covered.append(late["transfer"])
        if sorted(json_bytes(t) for t in covered) != sorted(json_bytes(t) for t in transfers):
            raise PackError("runtime phases must cover each declared transfer exactly once")
        lowered[profile_id] = dict(runtime_enabled=p["runtime_enabled"], normal=transfers,
                    transition=bg, cache_slots=slots, cache_slot_mask=sum(1 << s for s in slots),
                    staging=staging_records, late=late)
    parents = {}
    for binding in catalog["bindings"]:
        for parent in binding["parent_maps"]:
            parents[str(parent)] = dict(profile_id=binding["profile_id"],
                            runtime_enabled=lowered[binding["profile_id"]]["runtime_enabled"])
    return dict(schema_version=1, status="data only; no executable runtime consumer linked",
                abi=dict(outdoor_guard="$1B==0", parent="$8A", normal="A8/XY8",
                         transition="A16/XY8; preserve X/Y", late="A8/XY16; preserve X/Y"),
                profiles=lowered, parents=parents)


def runtime_policy_asm(lowered: dict) -> str:
    """Emit unallocated phase/cache/copy records, with stable label references."""
    label = lambda key: "GraphicsRuntimePolicy_" + sha256(key.encode())
    resource = lambda t: "GraphicsPackResource_" + sha256(t["resource_id"].encode()) + f"+${t['source_offset']:04X}"
    lines = ["; Generated runtime phase policy DATA ONLY. No org, hooks or include registration.",
             "; Record: enabled byte, transition mode byte, cache mask byte, normal/staging/late counts words.",
             "; Normal/source: source long, VRAM word, count word. Staging: source long, WRAM long, count word.",
             "; Late: step byte, source long, VRAM word, count word. Parent pointers are zero unless admitted.",
             "GraphicsRuntimeParentPolicies:"]
    for parent in range(160):
        binding = lowered["parents"].get(str(parent))
        target = label(binding["profile_id"]) if binding and binding["runtime_enabled"] else "$000000"
        lines.append(f"  dl {target} ; ${parent:02X}")
    modes = {"source_range": 1, "source_start": 2, "native_staging": 3}
    for profile_id, p in lowered["profiles"].items():
        base = label(profile_id)
        chunks = p["late"]["chunks"] if p["late"] else []
        lines += [f"; {json.dumps(profile_id)}", f"{base}:",
                  f"  db ${int(p['runtime_enabled']):02X},${modes[p['transition']['mode']]:02X},${p['cache_slot_mask']:02X}",
                  f"  dw ${len(p['normal']):04X},${len(p['staging']):04X},${len(chunks):04X}",
                  f"{base}_Normal:"]
        for t in p["normal"]:
            lines += [f"  dl {resource(t)}", f"  dw ${t['vram_word_address']:04X},${t['byte_count']:04X}"]
        lines.append(f"{base}_Transition:")
        t = p["transition"].get("transfer")
        if t:
            lines += [f"  dl {resource(t)}", f"  dw ${t['vram_word_address']:04X},${t['byte_count']:04X}"]
        lines.append(f"{base}_Staging:")
        for t in p["staging"]:
            lines += [f"  dl {resource(t)},${t['wram_address']:06X}", f"  dw ${t['byte_count']:04X}"]
        lines.append(f"{base}_Late:")
        for t in chunks:
            lines += [f"  db ${t['step']:02X}", f"  dl {resource(t)}",
                      f"  dw ${t['vram_word_address']:04X},${t['byte_count']:04X}"]
    return "\n".join(lines) + "\n"


def compile_pack(source: Path, output: Path, reference: Path | None = None,
                 runtime_policy: Path | None = None) -> dict:
    """Validate all inputs first; then write only an exclusive new directory."""
    source_bytes = source.read_bytes()
    catalog, assets = load(source)
    resolved = validate(catalog, assets)
    policy_bytes = runtime_policy.read_bytes() if runtime_policy is not None else None
    lowered = lower_runtime_policy(catalog, assets, read_json(runtime_policy)) if runtime_policy is not None else None
    reference_parents = []
    if reference is not None:
        reference_bytes = reference.read_bytes()
        ref_catalog, ref_assets = load(reference)
        for parent, expected in validate(ref_catalog, ref_assets).items():
            if resolved.get(parent) != expected:
                raise PackError(f"runtime reference differs at parent ${parent:02X}")
            reference_parents.append(parent)
        if reference.read_bytes() != reference_bytes:
            raise PackError("runtime reference changed during compilation")
    if source.read_bytes() != source_bytes:
        raise PackError("source catalog changed during compilation")
    if runtime_policy is not None and runtime_policy.read_bytes() != policy_bytes:
        raise PackError("runtime policy changed during compilation")
    # Normalize paths even when recompiling a caller-authored V2 catalog.
    catalog = json.loads(json.dumps(catalog))
    files = {}
    for resource_id, resource in catalog["resources"].items():
        path = f"assets/{sha256(assets[resource_id])}.4bpp.bin"
        resource["path"] = path
        resource["sha256"] = sha256(assets[resource_id])
        files[path] = assets[resource_id]
    legacy, slices = compatibility(catalog, assets)
    files.update(slices)
    files["catalog.json"] = json_bytes(catalog)
    files["preview-v1.json"] = json_bytes(legacy)
    files["transfer-descriptors.asm"] = descriptor_asm(catalog).encode()
    if lowered is not None:
        files["runtime-phase-policy.json"] = json_bytes(lowered)
        files["runtime-phase-descriptors.asm"] = runtime_policy_asm(lowered).encode()
    receipt = {
        "schema_version": 1, "source_sha256": sha256(source_bytes),
        "catalog_sha256": sha256(files["catalog.json"]),
        "parent_maps": sorted(resolved), "resource_count": len(assets),
        "resource_bytes": sum(len(data) for data in assets.values()),
        "character_counts": {str(p): len(chars) for p, (_, chars) in sorted(resolved.items())},
        "runtime_reference_parent_maps": sorted(reference_parents),
        "runtime_reference_sha256": sha256(reference_bytes) if reference is not None else None,
        "runtime_adapter_status": "proposed data only; no ASM include or ROM writes",
        "runtime_policy_source_sha256": sha256(policy_bytes) if policy_bytes is not None else None,
        "files": {path: {"byte_count": len(data), "sha256": sha256(data)}
                  for path, data in sorted(files.items())}}
    files["receipt.json"] = json_bytes(receipt)
    # No existing pack or project is ever replaced. Validation failures leave
    # no output; write failures leave a recognizable partial new directory.
    output.mkdir(parents=False, exist_ok=False)
    for path, data in files.items():
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
    saved_catalog, saved_assets = load(output / "catalog.json")
    saved_legacy, saved_legacy_assets = load(output / "preview-v1.json")
    if validate(saved_catalog, saved_assets) != resolved or validate(saved_legacy, saved_legacy_assets) != resolved:
        raise PackError("saved canonical or compatibility pack differs from source")
    for path, data in files.items():
        if (output / path).read_bytes() != data:
            raise PackError(f"saved output differs: {path}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="V1 manifest or canonical V2 catalog")
    parser.add_argument("output", type=Path, help="exclusive new pack directory; parent must exist")
    parser.add_argument("--runtime-reference", type=Path,
                        help="require matching character bytes for every parent in this manifest")
    parser.add_argument("--runtime-policy", type=Path,
                        help="lower explicit per-profile phase/cache policy to unlinked data")
    arguments = parser.parse_args()
    try:
        receipt = compile_pack(arguments.source, arguments.output, arguments.runtime_reference,
                               arguments.runtime_policy)
    except (PackError, OSError) as exc:
        print(f"graphics pack: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"catalog_sha256": receipt["catalog_sha256"],
                      "parent_maps": receipt["parent_maps"],
                      "resource_count": receipt["resource_count"],
                      "resource_bytes": receipt["resource_bytes"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
