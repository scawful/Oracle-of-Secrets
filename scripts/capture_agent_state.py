#!/usr/bin/env python3
"""Capture a canon-ready gameplay save state for agent workflows.

Workflow:
1) Optional load a source state path.
2) Run settle frames so mode/indoors/location metadata stabilizes.
3) Save into library via mesen2_client lib-save.
4) Regenerate .meta.json (ROM + state SHA1) via z3ed mesen-state-regen.
5) Verify freshness via z3ed mesen-state-verify.
6) Promote draft -> canon via mesen2_client lib-verify.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MESEN = [sys.executable, str(REPO_ROOT / "scripts" / "mesen2_client.py")]
DEFAULT_Z3ED = Path.home() / "src/hobby/yaze/build_ai/bin/Debug/z3ed"
DEFAULT_ROM = REPO_ROOT / "Roms/oos168x.sfc"


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def _json(cmd: list[str]) -> dict:
    proc = _run(cmd)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Expected JSON from {' '.join(cmd)}: {exc}\n{proc.stdout}") from exc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--label", required=True, help="Human label for state")
    p.add_argument("--tag", action="append", default=[], help="Repeatable tag")
    p.add_argument("--load-state", help="Optional state path to load first")
    p.add_argument("--settle-frames", type=int, default=120, help="Frames to run before capture")
    p.add_argument("--rom", default=str(DEFAULT_ROM), help="ROM path for metadata verification")
    p.add_argument("--z3ed", default=str(DEFAULT_Z3ED), help="z3ed binary path")
    p.add_argument("--captured-by", default="agent", choices=["agent", "human"])
    args = p.parse_args()

    if args.load_state:
        _run(MESEN + ["load", args.load_state])

    if args.settle_frames > 0:
        _run(MESEN + ["run", "--frames", str(args.settle_frames)])

    save_cmd = MESEN + ["lib-save", args.label, "--captured-by", args.captured_by, "--json"]
    for t in args.tag:
        save_cmd += ["-t", t]
    out = _json(save_cmd)
    state_id = out.get("id") or out.get("state_id") or (out.get("entry") or {}).get("id")
    if not state_id:
        raise RuntimeError(f"Could not parse state id from lib-save output: {out}")

    manifest = _json(MESEN + ["library", "--json"])
    match = next((e for e in manifest if e.get("id") == state_id), None)
    if not match:
        raise RuntimeError(f"State id {state_id} not found in library manifest")

    state_path = REPO_ROOT / "Roms/SaveStates/library" / match["path"]
    _run([args.z3ed, "mesen-state-regen", "--state", str(state_path), "--rom-file", args.rom])
    _run([args.z3ed, "mesen-state-verify", "--state", str(state_path), "--rom-file", args.rom])
    _run(MESEN + ["lib-verify", state_id, "--by", args.captured_by])

    print(
        json.dumps(
            {
                "ok": True,
                "id": state_id,
                "label": args.label,
                "path": str(state_path),
                "status": "canon",
                "tags": args.tag,
                "rom": args.rom,
                "settle_frames": args.settle_frames,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

