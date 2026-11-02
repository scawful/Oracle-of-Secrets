#!/usr/bin/env python3
"""Scene director CLI: drive Link inside one room from a JSON scene file.

  Scripts/Agents/scene.py run SCENE --rom ROM [--record OUT] [--out DIR]
  Scripts/Agents/scene.py check SCENE          # parse and validate only, no emulator
  Scripts/Agents/scene.py srm IN OUT [--file 1] --set 7EF360:u16=87 [--set ...]
                                               # edit save fields on a copy, fix the checksum

`run` takes one heavy-lock slot, launches a private headless Mesen2 OOS
instance on a copy of ROM, runs the steps, writes DIR/result.json and stops
the instance. `--record OUT` (or record start/stop steps) captures every frame
as PNG and encodes a 30 fps mp4 with ffmpeg (no audio). Power-on RAM is pinned
to zeros so the same scene ends on the same WRAM hash.
Exit codes: 0 pass, 1 failed check/wait/walk or runtime error,
2 bad scene file, 3 heavy lock busy.
See Scripts/Agents/scene_director/scenefile.py for the format.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_director.scenefile import SceneError, load_scene  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run a scene in a private headless Mesen")
    run.add_argument("scene", type=Path)
    run.add_argument("--rom", type=Path, required=True, help="patched ROM, e.g. Roms/oos168x.sfc")
    run.add_argument("--record", type=Path, help="mp4 output (every frame between record start/stop, or all after load)")
    run.add_argument("--out", type=Path, help="work/result directory (default: a new temp dir)")
    chk = sub.add_parser("check", help="validate a scene file offline")
    chk.add_argument("scene", type=Path)
    srm = sub.add_parser("srm", help="copy a battery SRM with edited save fields and a fixed checksum")
    srm.add_argument("input", type=Path)
    srm.add_argument("output", type=Path)
    srm.add_argument("--file", type=int, default=1, help="save file 1..3 (default 1, the file scenes boot)")
    srm.add_argument("--set", action="append", required=True, metavar="ADDR[:u8|u16]=VALUE")
    args = ap.parse_args(argv)
    if args.cmd == "srm":
        return _srm(args)

    try:
        scene = load_scene(args.scene)
    except (SceneError, OSError) as error:
        print(f"scene error: {error}", file=sys.stderr)
        return 2
    if args.cmd == "check":
        print(json.dumps({"scene": scene.name, "steps": [s.kind for s in scene.steps]}, indent=2))
        return 0

    from scene_director import runner
    try:
        result = runner.run_scene(scene, args.rom, out=args.out, record=args.record,
                                  log=lambda m: print(m, file=sys.stderr, flush=True))
    except SceneError as error:
        print(f"scene error: {error}", file=sys.stderr)
        return 2
    except runner.SceneFailed as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # noqa: BLE001 - any setup/runtime failure is exit 1
        print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        return 3 if "heavy lock is busy" in str(error) else 1
    print(json.dumps({k: result[k] for k in ("scene", "passed", "frame_count", "wram_sha256", "work", "record")
                      if k in result}, indent=2))
    return 0 if result.get("passed") else 1


def _srm(args) -> int:
    from scene_director import srm
    if args.input.resolve() == args.output.resolve() or args.output.exists():
        print(f"srm error: {args.output} exists or is the input; never overwrite a save", file=sys.stderr)
        return 2
    try:
        writes = [srm.parse_set(text) for text in args.set]
        data = args.input.read_bytes()
        out = srm.edit(data, args.file, writes)
    except (srm.SrmError, OSError) as error:
        print(f"srm error: {error}", file=sys.stderr)
        return 2
    with args.output.open("xb") as handle:
        handle.write(out)
    print(json.dumps({"input": str(args.input), "output": str(args.output),
                      **srm.report(data, out, args.file, writes)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
