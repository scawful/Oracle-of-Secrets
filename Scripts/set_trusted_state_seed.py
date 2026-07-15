#!/usr/bin/env python3
"""Map a trusted save-state library ID to an oos-session task."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "Docs" / "Debugging" / "Testing" / "trusted_state_seeds.json"
MESEN = [sys.executable, str(ROOT / "Scripts" / "Mesen2" / "mesen2_client.py")]


def run_json(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(f"Command failed: {' '.join(cmd)}\n{proc.stderr or proc.stdout}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Expected JSON from {' '.join(cmd)}: {exc}\n{proc.stdout}") from exc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("task", choices=["maku", "d4", "d6", "d6inside", "d6cart", "menu"])
    p.add_argument("state_id", help="Library state ID to trust for this task")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument(
        "--allow-nonhuman",
        action="store_true",
        help="Allow captured_by != human (not recommended)",
    )
    args = p.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Config not found: {config_path}")

    state = run_json(MESEN + ["lib-info", args.state_id, "--json"])
    status = state.get("status")
    captured_by = state.get("captured_by")

    if status != "canon":
        raise SystemExit(f"State rejected: {args.state_id} status={status!r}, need 'canon'.")
    if captured_by != "human" and not args.allow_nonhuman:
        raise SystemExit(
            f"State rejected: {args.state_id} captured_by={captured_by!r}, need 'human'. "
            "Use --allow-nonhuman to override."
        )

    cfg = json.loads(config_path.read_text())
    cfg.setdefault("tasks", {})
    cfg["tasks"][args.task] = args.state_id
    config_path.write_text(json.dumps(cfg, indent=2) + "\n")

    print(
        json.dumps(
            {
                "ok": True,
                "task": args.task,
                "state_id": args.state_id,
                "status": status,
                "captured_by": captured_by,
                "config": str(config_path),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
