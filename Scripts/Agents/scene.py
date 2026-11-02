#!/usr/bin/env python3
"""Scene director CLI: drive Link inside one room from a JSON scene file.

  Scripts/Agents/scene.py run SCENE --rom ROM [--record OUT] [--out DIR]
  Scripts/Agents/scene.py check SCENE          # parse and validate only, no emulator

`run` takes one heavy-lock slot, launches a private headless Mesen2 OOS
instance on a copy of ROM, runs the steps, writes DIR/result.json and stops
the instance. Exit codes: 0 pass, 1 failed check/wait/walk or runtime error,
2 bad scene file or unsupported step (record), 3 heavy lock busy.
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
    run.add_argument("--record", type=Path, help="video output (slice 2; errors in slice 1)")
    run.add_argument("--out", type=Path, help="work/result directory (default: a new temp dir)")
    chk = sub.add_parser("check", help="validate a scene file offline")
    chk.add_argument("scene", type=Path)
    args = ap.parse_args(argv)

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
    print(json.dumps({k: result[k] for k in ("scene", "passed", "frame_count", "wram_sha256", "work")
                      if k in result}, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
