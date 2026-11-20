#!/usr/bin/env python3
"""Private-ROM polish for D4 Zora Temple and D5 Glacia lower ice.

Safety:
- Never writes the live yaze ROM or Roms/oos168*.sfc.
- Copies --source into --work-dir and edits only that copy.
- Water-level control stays in Dungeons/d4_water_control.asm. This script
  only adds blockset props that the current rooms already know how to draw.

Locked visual targets (hashed, not ripped into CHR):
- MCGFX minish_dungeon_01.png  (Zora aqueduct / sluice)
- Zoras_Domain_Tiles2.bmp      (carved blue stone)
- dungeonaqua8vx.gif           (basin lip and flood channel)
- FSA Tile Sheet 08 and 20     (ice palace / timber estate)
- m_icecave.png                (cracked ice floor, icicle arch)
- TempleOfDroplets1.png, TempleOfDroplets2.png, minish_dungeon_04.png

Edits, each a single 2x2 object $089 already used as a carved block:
- Room $044 basin edge: two studs on the floor immediately west of the
  basin pipe (object $044 at 23,20).
- Room $027 floodgate: one footing on the floor beside the $137 gate,
  clear of the gate graphic.
- Room $09F lower ice: two frost blocks on the open ice-floor run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

LIVE_ROM = Path("/Users/scawful/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom")
REPO_ROMS = Path("/Users/scawful/src/hobby/oracle-of-secrets/Roms")
Z3ED = Path("/Users/scawful/.local/bin/z3ed")
DEFAULT_WORK = Path("/tmp/oos-door-surrounds")

REFERENCES = {
    "minish_dungeon_01": Path("/Users/scawful/Zelda/ReferenceLibrary/sources/documents-zelda/SePH Folder/Christmas_Present_2/_MC Style/minish_dungeon_01.png"),
    "zoras_domain_tiles2": Path("/Users/scawful/Documents/Zelda/Graphics/26 maart ZFGC resources/6. Tileset/Zoras_Domain_Tiles2.bmp"),
    "dungeonaqua": Path("/Users/scawful/Documents/Zelda/Graphics/26 maart ZFGC resources/6. Tileset/dungeonaqua8vx.gif"),
    "fsa_sheet_08": Path("/Users/scawful/Documents/Zelda/FSA Tilesets/Tile Sheet 08.PNG"),
    "fsa_sheet_20": Path("/Users/scawful/Documents/Zelda/FSA Tilesets/Tile Sheet 20.PNG"),
    "m_icecave": Path("/Users/scawful/Zelda/ReferenceLibrary/sources/documents-zelda/SePH Folder/Christmas_Present_2/___Unsorted/misc/m_icecave.png"),
    "temple_of_droplets_1": Path("/Users/scawful/Documents/Zelda/Graphics/MCGFX/TempleOfDroplets1.png"),
    "temple_of_droplets_2": Path("/Users/scawful/Documents/Zelda/Graphics/MCGFX/TempleOfDroplets2.png"),
    "minish_dungeon_04": Path("/Users/scawful/Zelda/ReferenceLibrary/sources/documents-zelda/SePH Folder/Christmas_Present_2/_MC Style/minish_dungeon_04.png"),
}

# Anchors must already be in the room. Studs are appended only when absent.
PLANS = (
    {
        "room": 0x44,
        "role": "D4 basin edge",
        "anchor": {"id": 0x044, "x": 23, "y": 20, "size": 7, "layer": 0},
        "studs": (
            {"id": 0x089, "x": 26, "y": 32, "size": 0, "list": 0},
            {"id": 0x089, "x": 28, "y": 32, "size": 0, "list": 0},
        ),
    },
    {
        "room": 0x27,
        "role": "D4 floodgate footing",
        "anchor": {"id": 0x137, "x": 39, "y": 12, "size": 0, "layer": 0},
        "studs": (
            {"id": 0x089, "x": 33, "y": 15, "size": 0, "list": 0},
        ),
    },
    {
        "room": 0x9F,
        "role": "D5 lower ice frost blocks",
        "anchor": {"id": 0x00, "x": None, "y": None, "size": None, "layer": None},
        "require_any_door": True,
        "studs": (
            {"id": 0x089, "x": 16, "y": 40, "size": 0, "list": 0},
            {"id": 0x089, "x": 20, "y": 40, "size": 0, "list": 0},
        ),
    },
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def refuse_live(path: Path) -> None:
    resolved = path.resolve()
    live_root = LIVE_ROM.parent.resolve()
    repo_roms = REPO_ROMS.resolve()
    if resolved == live_root or live_root in resolved.parents:
        raise SystemExit(f"refusing to write live project path: {resolved}")
    if resolved == repo_roms or repo_roms in resolved.parents:
        raise SystemExit(f"refusing to write repo ROM path: {resolved}")


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout[-1500:], file=sys.stderr)
        print(result.stderr[-1500:], file=sys.stderr)
        raise SystemExit(result.returncode)
    return result


def list_objects(rom: Path, room: int) -> list[dict]:
    result = run([
        str(Z3ED), "dungeon-list-objects",
        f"--rom={rom}", f"--room={room:#x}", "--format=json",
    ])
    payload = json.loads(result.stdout)
    return payload["Dungeon Room Objects"]["objects"]


def has_object(objects: list[dict], spec: dict) -> bool:
    for obj in objects:
        if all(obj.get(key) == spec[key] for key in ("id", "x", "y", "size")):
            layer = spec.get("layer", spec.get("list"))
            if layer is None or obj.get("layer") == layer:
                return True
    return False


def apply_room(rom: Path, plan: dict) -> dict:
    objects = list_objects(rom, plan["room"])
    anchor = plan["anchor"]
    if anchor["id"] != 0x00:
        if not has_object(objects, anchor):
            raise SystemExit(
                f"room ${plan['room']:03X} lost anchor {anchor}; refusing to polish"
            )
    elif plan.get("require_any_door"):
        described = run([
            str(Z3ED), "dungeon-describe-room",
            f"--rom={rom}", f"--room={plan['room']:#x}", "--format=json",
        ])
        doors = json.loads(described.stdout).get("doors") or []
        if not doors:
            raise SystemExit(f"room ${plan['room']:03X} has no doors; refusing")
    edits = []
    for stud in plan["studs"]:
        if has_object(objects, {**stud, "layer": stud["list"]}):
            continue
        edits.append({"op": "append", "object": stud})
    if not edits:
        return {"room": plan["room"], "role": plan["role"], "applied": 0}
    plan_path = rom.with_name(f"plan_{plan['room']:03X}.json")
    plan_path.write_text(json.dumps({
        "version": 1,
        "rom_sha256": sha256_file(rom),
        "room": plan["room"],
        "edits": edits,
    }), encoding="utf-8")
    result = run([
        str(Z3ED), "dungeon-apply-object-plan",
        f"--rom={rom}",
        f"--room={plan['room']:#x}",
        f"--object-plan={plan_path}",
        "--write",
        "--allow-lyra-layout-writes",
        "--format=json",
    ])
    payload = json.loads(result.stdout)
    return {
        "room": f"${plan['room']:03X}",
        "role": plan["role"],
        "applied": len(edits),
        "objects_before": payload.get("objects_before"),
        "objects_after": payload.get("objects_after"),
        "write_status": payload.get("write_status"),
    }


def reference_manifest() -> dict[str, str]:
    found = {}
    for name, path in REFERENCES.items():
        if not path.is_file():
            raise SystemExit(f"locked reference missing: {path}")
        found[name] = sha256_file(path)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=LIVE_ROM)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--render", action="store_true", help="Write z3ed PNGs into the work dir")
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    work = args.work_dir.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"source ROM missing: {source}")
    refuse_live(work)
    work.mkdir(parents=True, exist_ok=True)
    dest = work / "polished.sfc"
    refuse_live(dest)
    source_sha = sha256_file(source)
    if source != dest:
        shutil.copyfile(source, dest)
    if sha256_file(source) != source_sha:
        raise SystemExit(f"source ROM changed while copying: {source}")

    report = {
        "source": str(source),
        "source_sha256": source_sha,
        "dest": str(dest),
        "references": reference_manifest(),
        "rooms": [apply_room(dest, plan) for plan in PLANS],
        "dest_sha256": sha256_file(dest),
    }
    if args.render:
        render_dir = work / "polish-renders"
        render_dir.mkdir(exist_ok=True)
        for plan in PLANS:
            out = render_dir / f"room_{plan['room']:03X}.png"
            run([
                str(Z3ED), "dungeon-render",
                f"--rom={dest}",
                f"--room={plan['room']:#x}",
                f"--output={out}",
                "--scale=2",
            ])
            report.setdefault("renders", []).append(str(out))
    manifest = work / "d4_d5_polish_manifest.json"
    manifest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
