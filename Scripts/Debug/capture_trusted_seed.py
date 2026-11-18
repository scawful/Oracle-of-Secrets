#!/usr/bin/env python3
"""Capture a labeled save-state for later trusted_state_seeds mapping.

Writes a draft library state via mesen2_client lib-save. Canon policy is
unchanged: a human must lib-verify to canon, then run set_trusted_state_seed.py.

Never targets oos-rc-play.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MESEN = [sys.executable, str(ROOT / "Scripts" / "Mesen2" / "mesen2_client.py")]
SET_TRUSTED = [sys.executable, str(ROOT / "Scripts" / "set_trusted_state_seed.py")]
RC_MARKERS = ("oos-rc-play", "mesen2-oos-rc-play")
TASKS = ("maku", "d4", "d6", "d6inside", "d6cart", "menu")


def refuse_rc(socket: str | None, instance: str | None) -> None:
    for value in (socket or "", instance or ""):
        lowered = value.lower()
        for marker in RC_MARKERS:
            if marker in lowered:
                raise SystemExit(f"refusing oos-rc-play target ({value})")


def run_json(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"Command failed: {' '.join(cmd)}\n{proc.stderr or proc.stdout}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Expected JSON from {' '.join(cmd)}: {exc}\n{proc.stdout}"
        ) from exc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("label", help="Library label for the new draft state")
    p.add_argument("--socket", help="Private Mesen socket")
    p.add_argument("--instance", help="Private registry instance")
    p.add_argument(
        "--captured-by",
        choices=("human", "agent"),
        default="human",
        help="Who captured this state (default: human)",
    )
    p.add_argument(
        "--tag",
        action="append",
        dest="tags",
        default=[],
        help="Optional library tag (repeatable)",
    )
    p.add_argument(
        "--task",
        choices=TASKS,
        help="If set, also map trusted_state_seeds after capture (requires canon)",
    )
    p.add_argument(
        "--map-even-if-draft",
        action="store_true",
        help="With --task, call set_trusted_state_seed.py --allow-nonhuman "
        "(still requires status=canon unless you verify first)",
    )
    args = p.parse_args()
    refuse_rc(args.socket, args.instance)

    mesen = list(MESEN)
    if args.socket:
        mesen.extend(["--socket", args.socket])
    elif args.instance:
        mesen.extend(["--instance", args.instance])
    else:
        raise SystemExit("Need --socket or --instance (private owned session)")

    save_cmd = mesen + [
        "lib-save",
        args.label,
        "--captured-by",
        args.captured_by,
        "--json",
    ]
    for tag in args.tags:
        save_cmd.extend(["--tag", tag])
    saved = run_json(save_cmd)
    state_id = saved.get("id") or saved.get("state_id") or saved.get("entry", {}).get("id")
    result = {
        "ok": True,
        "saved": saved,
        "state_id": state_id,
        "next": [
            f"mesen2_client.py lib-verify {state_id} --verified-by <you>  # when canon",
            f"Scripts/set_trusted_state_seed.py <task> {state_id}",
        ],
        "mapped": None,
    }

    if args.task and state_id:
        map_cmd = list(SET_TRUSTED) + [args.task, str(state_id)]
        if args.map_even_if_draft:
            map_cmd.append("--allow-nonhuman")
        map_proc = subprocess.run(map_cmd, text=True, capture_output=True)
        if map_proc.returncode == 0:
            try:
                result["mapped"] = json.loads(map_proc.stdout)
            except json.JSONDecodeError:
                result["mapped"] = {"ok": True, "raw": map_proc.stdout}
        else:
            result["mapped"] = {
                "ok": False,
                "error": (map_proc.stderr or map_proc.stdout).strip(),
                "hint": "Promote to canon with lib-verify, then re-run set_trusted_state_seed.py",
            }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
