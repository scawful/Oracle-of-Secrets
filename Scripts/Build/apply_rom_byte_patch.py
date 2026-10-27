#!/usr/bin/env python3
"""Apply a reviewed byte patch (JSON) to the base ROM, with before-byte guards.

Usage:
  python3 Scripts/Build/apply_rom_byte_patch.py PATCH.json --rom Roms/oos168.sfc          # dry run
  python3 Scripts/Build/apply_rom_byte_patch.py PATCH.json --rom Roms/oos168.sfc --apply  # write

PATCH.json:
  {"base_sha1": "<sha1 of the ROM the patch was made against, optional>",
   "edits": [{"id": "...", "pc": "0x7163B", "snes": "$0E963B",
              "before": "4B", "after": "02", "why": "..."}]}

Every edit must read its "before" bytes (or already read "after": re-running is a
no-op). Any other value aborts without writing. Offsets are unheadered PC.

Schema2 paired recipes instead require --source-root, --output-root and --output.
They default to dry run, reject --apply and require an exact whole-input hash.
--write-output creates one new private output after validation and readback;
it never writes --rom. Output roots must be owned mode0700 directories outside
the source/input trees. Existing destinations are always refused in this mode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


def snes_to_pc(snes: int) -> int:
    return ((snes >> 16) & 0x7F) * 0x8000 + (snes & 0x7FFF)


PAIRED_FILES = (
    "Data/dungeons/custom_collision.json",
    "Dungeons/generated/water_fill_table.asm",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def full_hash(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Strict recipes require full lowercase SHA256 values")
    return value


def source_state(root: Path, expected: dict) -> dict:
    if set(expected["files"]) != set(PAIRED_FILES):
        raise ValueError("Strict source binding must name exactly the collision JSON and fill ASM")
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    diff = subprocess.check_output(["git", "-C", str(root), "diff", "--binary", "HEAD"])
    if head != expected["head"] or sha256(diff) != full_hash(expected["diff_sha256"]):
        raise ValueError("Selected source HEAD or complete diff differs from recipe")
    files = {}
    for rel in PAIRED_FILES:
        path = root / rel
        if path.is_symlink() or sha256(path.read_bytes()) != full_hash(expected["files"][rel]):
            raise ValueError(f"Paired source hash differs: {rel}")
        files[rel] = expected["files"][rel]
    common = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--git-common-dir"], text=True).strip()
    common = Path(common) if Path(common).is_absolute() else root / common
    return dict(head=head, diff_sha256=sha256(diff), files=files,
                main_checkout=str(common.resolve().parent))


def strict_paths(args, main_checkout: Path) -> tuple[Path, Path]:
    output, folder = args.output, args.output_root
    if not output.is_absolute() or not folder.is_absolute() or not args.source_root.is_absolute():
        raise ValueError("Strict source/output paths must be absolute")
    for path in (output, folder):
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise ValueError("Output paths must not contain symlinks")
    info = folder.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("Output root must be an existing owned mode0700 directory")
    folder, output = folder.resolve(), output.resolve()
    protected = (args.source_root.resolve(), args.rom.resolve().parent,
                 Path(__file__).resolve().parents[2], main_checkout)
    if any(folder.is_relative_to(p) or p.is_relative_to(folder) for p in protected):
        raise ValueError("Private output root overlaps an input or source tree")
    if output.parent != folder:
        raise ValueError("Output must be a direct child of the private output root")
    if os.path.lexists(output):
        raise ValueError("Strict output must not already exist")
    inputs = (args.rom, args.patch, Path(__file__), *(args.source_root / rel for rel in PAIRED_FILES))
    if any(output == path.resolve() for path in inputs):
        raise ValueError("Output aliases an input")
    return output, folder


def strict_plan(args, spec: dict) -> tuple[bytes, dict]:
    if spec.get("schema_version") != 2 or spec.get("write_policy") != "private_output_only":
        raise ValueError("Strict output requires a schema2 private_output_only recipe")
    if "edits" in spec:
        raise ValueError("Schema2 requires private_edits without a legacy edits key")
    original = args.rom.read_bytes()
    if len(original) != spec["base_size"] or sha256(original) != full_hash(spec["base_sha256"]):
        raise ValueError("Exact base size/SHA256 differs from recipe")
    source = source_state(args.source_root, spec["source"])
    output, _ = strict_paths(args, Path(source["main_checkout"]))
    candidate, positions, edits = bytearray(original), set(), []
    if not spec["private_edits"]:
        raise ValueError("Strict edits must not be empty")
    for edit in spec["private_edits"]:
        pc = int(edit["pc"], 16)
        before, after = bytes.fromhex(edit["before"]), bytes.fromhex(edit["after"])
        span = set(range(pc, pc + len(before)))
        if not before or len(before) != len(after) or pc < 0 or pc + len(before) > len(original):
            raise ValueError("Edit is empty, unequal-length or outside the input")
        snes = int(edit["snes"].lstrip("$"), 16)
        if (not 0 <= snes <= 0xFFFFFF or (snes & 0xFFFF) < 0x8000
                or (snes >> 16) in (0x7E, 0x7F, 0xFE, 0xFF)):
            raise ValueError("Strict edit requires a 24-bit high-half LoROM address")
        if span & positions or snes_to_pc(snes) != pc:
            raise ValueError("Edits overlap or PC/SNES addresses disagree")
        if original[pc:pc + len(before)] != before:
            raise ValueError(f"Exact before bytes differ at PC {pc:06X}")
        candidate[pc:pc + len(before)] = after
        positions.update(span)
        edits.append(dict(pc=f"0x{pc:06X}", before=before.hex(), after=after.hex(),
                          in_memory_readback=bytes(candidate[pc:pc + len(after)]).hex()))
    changed = {i for i, (a, b) in enumerate(zip(original, candidate)) if a != b}
    if changed != positions or len(changed) != spec["changed_bytes"]:
        raise ValueError("Actual changed-byte set/count differs from the recipe")
    if sha256(candidate) != full_hash(spec["result_sha256"]):
        raise ValueError("Expected result SHA256 differs")
    preserved = []
    for region in spec.get("preserve_ranges", []):
        start, end = int(region["pc_start"], 16), int(region["pc_end_exclusive"], 16)
        if not 0 <= start < end <= len(original):
            raise ValueError("Preserved range is outside the input")
        expected = full_hash(region["sha256"])
        if sha256(original[start:end]) != expected or sha256(candidate[start:end]) != expected:
            raise ValueError(f"Preserved range differs: {region['id']}")
        preserved.append(region)
    recipe_bytes = args.patch.read_bytes()
    recipe_hash = sha256(recipe_bytes)
    if (recipe_hash != getattr(args, "recipe_sha256", recipe_hash)
            or json.loads(recipe_bytes) != spec):
        raise ValueError("Recipe changed after selection")
    return bytes(candidate), dict(dry_run=not args.write_output, base_sha256=sha256(original),
                                  result_sha256=sha256(candidate), size=len(candidate),
                                  changed_bytes=len(changed), edits=edits, source=source,
                                  recipe_sha256=recipe_hash,
                                  script_sha256=sha256(Path(__file__).read_bytes()),
                                  preserved_ranges=preserved, output=str(output), written=False)


def strict_output(args, spec: dict) -> int:
    candidate, report = strict_plan(args, spec)
    if args.write_output:
        # Recheck all input/source/destination guards immediately before creation.
        again, checked = strict_plan(args, spec)
        if again != candidate or checked != report:
            raise ValueError("Inputs changed before output creation")
        output, folder = Path(report["output"]), args.output_root.resolve()
        directory = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            descriptor = os.open(output.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(candidate)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(directory)
        if output.read_bytes() != candidate or sha256(args.rom.read_bytes()) != report["base_sha256"]:
            raise ValueError("Output readback or unchanged-input check failed; retain private output")
        if source_state(args.source_root, spec["source"]) != report["source"]:
            raise ValueError("Source changed during output creation; retain private output")
        if (sha256(args.patch.read_bytes()) != report["recipe_sha256"]
                or sha256(Path(__file__).read_bytes()) != report["script_sha256"]):
            raise ValueError("Recipe/script changed during output creation; retain private output")
        report.update(written=True, output_readback_sha256=sha256(output.read_bytes()))
    print(json.dumps(report, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patch", type=Path)
    ap.add_argument("--rom", type=Path, required=True)
    ap.add_argument("--apply", action="store_true", help="write the ROM (default: dry run)")
    ap.add_argument("--output", type=Path, help="strict private output path; dry run unless --write-output")
    ap.add_argument("--output-root", type=Path, help="existing owned mode0700 private test directory")
    ap.add_argument("--source-root", type=Path, help="exact source checkout bound by a strict recipe")
    ap.add_argument("--write-output", action="store_true", help="create the strict output; never change --rom")
    args = ap.parse_args()

    recipe_bytes = args.patch.read_bytes()
    spec = json.loads(recipe_bytes)
    args.recipe_sha256 = sha256(recipe_bytes)
    if "schema_version" in spec and (type(spec["schema_version"]) is not int or spec["schema_version"] not in (1, 2)):
        ap.error("unsupported byte-patch schema_version")
    strict = spec.get("schema_version") == 2 or any((args.output, args.output_root, args.source_root, args.write_output))
    if strict or spec.get("write_policy") == "private_output_only":
        if args.apply or not all((args.output, args.output_root, args.source_root)):
            ap.error("strict mode requires --output/--output-root/--source-root and refuses --apply")
        try:
            return strict_output(args, spec)
        except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
            print(f"ERROR: {error}; no input was written", file=sys.stderr)
            return 1
    rom = bytearray(args.rom.read_bytes())
    sha_before = hashlib.sha1(rom).hexdigest()
    print(f"ROM {args.rom} SHA-1 {sha_before}")
    if spec.get("base_sha1") and not sha_before.startswith(spec["base_sha1"]):
        print(f"note: patch was made against base SHA-1 {spec['base_sha1']}")

    pending, failed = [], False
    for edit in spec["edits"]:
        pc = int(edit["pc"], 16)
        if "snes" in edit:
            snes = int(edit["snes"].lstrip("$"), 16)
            if snes_to_pc(snes) != pc:
                print(f"FAIL {edit['id']}: {edit['snes']} maps to PC 0x{snes_to_pc(snes):X}, not 0x{pc:X}")
                failed = True
                continue
        before, after = bytes.fromhex(edit["before"]), bytes.fromhex(edit["after"])
        if len(before) != len(after):
            print(f"FAIL {edit['id']}: before/after length differ")
            failed = True
            continue
        now = bytes(rom[pc:pc + len(before)])
        if now == after:
            print(f"ok   {edit['id']}: PC 0x{pc:06X} already {after.hex(' ').upper()}")
        elif now == before:
            print(f"edit {edit['id']}: PC 0x{pc:06X} {before.hex(' ').upper()} -> {after.hex(' ').upper()}")
            pending.append((pc, after))
        else:
            print(f"FAIL {edit['id']}: PC 0x{pc:06X} reads {now.hex(' ').upper()}, "
                  f"expected {before.hex(' ').upper()} (or {after.hex(' ').upper()})")
            failed = True
    if failed:
        print("aborted: nothing written")
        return 1
    for pc, after in pending:
        rom[pc:pc + len(after)] = after
    sha_after = hashlib.sha1(rom).hexdigest()
    if not args.apply:
        print(f"dry run: {len(pending)} edit(s) pending; result SHA-1 would be {sha_after}")
        return 0
    if pending:
        args.rom.write_bytes(rom)
    print(f"wrote {len(pending)} edit(s); SHA-1 {sha_after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
