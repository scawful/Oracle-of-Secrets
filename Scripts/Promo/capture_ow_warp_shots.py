#!/usr/bin/env python3
"""Batch-capture OW promo shots via director StageResolver (private socket).

Staging (story checkpoint loadout → warp-area → live landing → walkable snap)
lives in mesen2-oos director apply_shot. This script only orchestrates outputs.
Never targets oos-rc-play.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SHOTS = ROOT / "Data" / "debug" / "promo_shots" / "ow_warp_shots.json"
DIRECTOR = ROOT / "Scripts" / "Mesen2" / "oos_director.sh"
CLIENT = ROOT / "Scripts" / "Mesen2" / "mesen2_client.py"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--socket", required=True)
    p.add_argument("--shots", type=Path, default=DEFAULT_SHOTS)
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "Roms" / "telemetry" / "promo" / "ow-warp-batch",
    )
    p.add_argument("--clip", action="store_true")
    p.add_argument("--gif", action="store_true", default=True)
    p.add_argument("--preset", default="square")
    p.add_argument("--only", action="append", help="Limit to shot name(s)")
    p.add_argument("--areas", action="append", help="Limit to area hex (0x23)")
    p.add_argument(
        "--no-rom",
        action="store_true",
        default=True,
        help="Prefer warp-area path (ROM warp gated unhealthy by default)",
    )
    args = p.parse_args()

    sock = args.socket
    if "rc-play" in sock.lower():
        raise SystemExit("refusing oos-rc-play socket")

    shots = json.loads(args.shots.read_text()).get("shots", [])
    if args.only:
        want = set(args.only)
        shots = [s for s in shots if s["name"] in want]
    if args.areas:
        areas = {a.lower() for a in args.areas}
        shots = [s for s in shots if str(s["area"]).lower() in areas]

    by_area: dict[str, list[dict]] = defaultdict(list)
    for s in shots:
        by_area[str(s["area"]).lower()].append(s)

    args.out.mkdir(parents=True, exist_ok=True)
    summary: dict = {"ok": True, "socket": sock, "areas": [], "errors": []}

    # Ensure play module before first stage
    run([sys.executable, str(CLIENT), "--socket", sock, "load",
         str(ROOT / "Roms" / "SaveStates" / "oos168x" / "oos168x_1.mss")])
    run([sys.executable, str(CLIENT), "--socket", sock, "frame", "30"])

    for area, group in by_area.items():
        area_dir = args.out / f"area_{area}"
        area_dir.mkdir(parents=True, exist_ok=True)
        names = [s["name"] for s in group]
        cmd = [
            "bash",
            str(DIRECTOR),
            "--socket",
            sock,
            "capture",
            "--shots",
            str(args.shots),
            "--out",
            str(area_dir),
            "--preset",
            args.preset,
        ]
        if args.no_rom:
            cmd.append("--no-rom")
        if args.gif:
            cmd.append("--gif")
        if args.clip:
            cmd.append("--clip")
        for n in names:
            cmd.extend(["--shot", n])

        cap = run(cmd)
        try:
            cap_payload = json.loads(cap.stdout or "{}")
        except json.JSONDecodeError:
            cap_payload = {"raw": cap.stdout, "stderr": cap.stderr}
        ok = cap.returncode == 0 and bool(cap_payload.get("ok", False))
        if not ok:
            summary["ok"] = False
            summary["errors"].append(
                {
                    "area": area,
                    "stage": "capture",
                    "error": cap_payload.get("errors")
                    or cap_payload.get("error")
                    or cap.stderr,
                }
            )
        summary["areas"].append(
            {
                "area": area,
                "label": group[0].get("label"),
                "checkpoint": group[0].get("checkpoint"),
                "shots": names,
                "ok": ok,
                "out": str(area_dir),
                "capture": {
                    "ok": cap_payload.get("ok"),
                    "stills": cap_payload.get("stills"),
                    "exports": cap_payload.get("exports"),
                    "errors": cap_payload.get("errors"),
                },
            }
        )

    pan_pairs = [
        ("wayward_village", "wayward_village_east_pan"),
        ("loom_beach", "loom_beach_east_pan"),
        ("kalyxo_castle", "kalyxo_castle_east_pan"),
    ]
    present = {s["name"] for s in shots}
    for frm, to in pan_pairs:
        if frm not in present or to not in present:
            continue
        pan_dir = args.out / f"pan_{frm}_to_{to}"
        pan = run(
            [
                "bash",
                str(DIRECTOR),
                "--socket",
                sock,
                "pan",
                "--shots",
                str(args.shots),
                "--from",
                frm,
                "--to",
                to,
                "--frames",
                "48",
                "--sample-every",
                "2",
                "--out",
                str(pan_dir),
            ]
        )
        try:
            pan_payload = json.loads(pan.stdout or "{}")
        except json.JSONDecodeError:
            pan_payload = {"raw": pan.stdout}
        summary.setdefault("pans", []).append(
            {
                "from": frm,
                "to": to,
                "ok": pan.returncode == 0,
                "out": str(pan_dir),
                "result": pan_payload,
            }
        )
        if pan.returncode != 0:
            summary["ok"] = False

    (args.out / "batch_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
