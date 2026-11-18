#!/usr/bin/env python3
"""Unified host-director staging + promo capture for Oracle of Secrets.

Wraps mesen2_client director-* commands and checkpoint/trusted-seed staging.
Never targets oos-rc-play.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MESEN = [sys.executable, str(ROOT / "Scripts" / "Mesen2" / "mesen2_client.py")]
DEFAULT_SHOTS = ROOT / "Data" / "debug" / "promo_shots" / "starter_shots.json"
TRUSTED = ROOT / "Data" / "debug" / "trusted_state_seeds.json"
RC_MARKERS = ("oos-rc-play", "mesen2-oos-rc-play")


def refuse_rc(socket: str | None, instance: str | None) -> None:
    for value in (socket or "", instance or ""):
        lowered = value.lower()
        for marker in RC_MARKERS:
            if marker in lowered:
                raise SystemExit(
                    f"refusing oos-rc-play target ({value}); use a private instance"
                )


def mesen_argv(socket: str | None, instance: str | None) -> list[str]:
    cmd = list(MESEN)
    if socket:
        cmd.extend(["--socket", socket])
    elif instance:
        cmd.extend(["--instance", instance])
    return cmd


def run_mesen(
    args: argparse.Namespace,
    extra: list[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess:
    refuse_rc(args.socket, args.instance)
    cmd = mesen_argv(args.socket, args.instance) + extra
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout or "")
        raise SystemExit(proc.returncode)
    return proc


def print_json(data: dict) -> None:
    print(json.dumps(data, indent=2))


def cmd_stage(args: argparse.Namespace) -> int:
    refuse_rc(args.socket, args.instance)
    target = args.target
    # Trusted session task names map through trusted_state_seeds.json → lib-load.
    if target.startswith("task:"):
        task = target.split(":", 1)[1]
        cfg = json.loads(TRUSTED.read_text())
        state_id = (cfg.get("tasks") or {}).get(task)
        if not state_id:
            print_json(
                {
                    "ok": False,
                    "error": f"trusted seed for task {task!r} is null; "
                    "capture with Scripts/Debug/capture_trusted_seed.py then "
                    "Scripts/set_trusted_state_seed.py",
                }
            )
            return 1
        proc = run_mesen(args, ["lib-load", state_id, "--json"], check=False)
        out = proc.stdout.strip() or "{}"
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            payload = {"raw": out}
        payload["ok"] = proc.returncode == 0
        payload["staged"] = {"kind": "task", "task": task, "state_id": state_id}
        print_json(payload)
        return proc.returncode

    if target.startswith("checkpoint:") or not target.startswith(
        ("warp-entrance:", "warp-area:", "entrance:", "area:")
    ):
        cp = target.split(":", 1)[1] if target.startswith("checkpoint:") else target
        proc = run_mesen(args, ["checkpoint", cp, "--json"], check=False)
        out = proc.stdout.strip() or "{}"
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            payload = {"raw": out}
        if "ok" not in payload:
            payload["ok"] = proc.returncode == 0
        payload["staged"] = {"kind": "checkpoint", "id": cp}
        print_json(payload)
        return proc.returncode

    if target.startswith(("warp-entrance:", "entrance:")):
        key = target.split(":", 1)[1]
        proc = run_mesen(args, ["warp-entrance", key, "--json"], check=False)
    else:
        key = target.split(":", 1)[1]
        proc = run_mesen(args, ["warp-area", key, "--json"], check=False)
    out = proc.stdout.strip() or "{}"
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        payload = {"raw": out}
    if "ok" not in payload:
        payload["ok"] = proc.returncode == 0
    payload["staged"] = {"kind": "warp", "target": target}
    print_json(payload)
    return proc.returncode


def cmd_apply(args: argparse.Namespace) -> int:
    shots = args.shots or DEFAULT_SHOTS
    extra = ["director-apply", str(shots), "--json"]
    if args.shot:
        extra.extend(["--shot", args.shot])
    if args.settle is not None:
        extra.extend(["--settle", str(args.settle)])
    if args.no_fly:
        extra.append("--no-fly")
    if args.no_rom:
        extra.append("--no-rom")
    if args.no_hold:
        extra.append("--no-hold")
    proc = run_mesen(args, extra, check=False)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


def cmd_pan(args: argparse.Namespace) -> int:
    shots = args.shots or DEFAULT_SHOTS
    extra = [
        "director-pan",
        str(shots),
        "--from",
        args.from_shot,
        "--to",
        args.to_shot,
        "--frames",
        str(args.frames),
        "--sample-every",
        str(args.sample_every),
        "--easing",
        args.easing,
        "--json",
    ]
    if args.out:
        extra.extend(["--out", str(args.out)])
    if args.no_hold:
        extra.append("--no-hold")
    proc = run_mesen(args, extra, check=False)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


def cmd_capture(args: argparse.Namespace) -> int:
    shots = args.shots or DEFAULT_SHOTS
    out = args.out
    if out is None:
        out = ROOT / "Roms" / "telemetry" / "promo" / "latest"
    extra = [
        "director-capture",
        str(shots),
        "--out",
        str(out),
        "--preset",
        args.preset,
        "--fps",
        str(args.fps),
        "--json",
    ]
    if args.shot:
        for name in args.shot:
            extra.extend(["--shot", name])
    if args.clip:
        extra.append("--clip")
    if args.gif:
        extra.append("--gif")
    if getattr(args, 'avi', False):
        extra.append("--avi")
        extra.extend(["--avi-codec", args.avi_codec])
    if args.no_hold:
        extra.append("--no-hold")
    if getattr(args, "no_rom", False):
        extra.append("--no-rom")
    if getattr(args, "hud_off", False):
        extra.append("--hud-off")
    if args.settle is not None:
        extra.extend(["--settle", str(args.settle)])
    proc = run_mesen(args, extra, check=False)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


def cmd_smoke(args: argparse.Namespace) -> int:
    shots = args.shots or DEFAULT_SHOTS
    extra = ["director-smoke", str(shots), "--json"]
    if args.shot:
        extra.extend(["--shot", args.shot])
    if getattr(args, "no_rom", False):
        extra.append("--no-rom")
    proc = run_mesen(args, extra, check=False)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


def cmd_validate(args: argparse.Namespace) -> int:
    shots = args.shots or DEFAULT_SHOTS
    # Socketless: call mesen client without --socket.
    cmd = list(MESEN) + ["director-validate", str(shots), "--json"]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


def cmd_list(args: argparse.Namespace) -> int:
    shots_path = args.shots or DEFAULT_SHOTS
    shots = json.loads(shots_path.read_text())
    checkpoints_path = ROOT / "Data" / "debug" / "checkpoints.json"
    trusted = json.loads(TRUSTED.read_text()) if TRUSTED.exists() else {"tasks": {}}
    cps = []
    if checkpoints_path.exists():
        data = json.loads(checkpoints_path.read_text())
        cps = [
            {"id": c.get("id"), "label": c.get("label"), "beat": c.get("beat")}
            for c in data.get("checkpoints", [])
        ]
    print_json(
        {
            "ok": True,
            "shots_file": str(shots_path),
            "shots": [
                {"name": s.get("name"), "area": s.get("area")}
                for s in shots.get("shots", [])
            ],
            "checkpoints": cps,
            "trusted_tasks": {
                k: v for k, v in (trusted.get("tasks") or {}).items()
            },
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Host-director testing + promo capture (private Mesen only)"
    )
    p.add_argument("--socket", help="Private Mesen socket path")
    p.add_argument("--instance", help="Private registry instance name")
    sub = p.add_subparsers(dest="command", required=True)

    stage = sub.add_parser(
        "stage",
        help="checkpoint ID | task:<name> | warp-entrance:<id> | warp-area:<id>",
    )
    stage.add_argument("target")
    stage.set_defaults(func=cmd_stage)

    apply_p = sub.add_parser("apply", help="Apply a yaze shot from shots.json")
    apply_p.add_argument("--shots", type=Path, default=None)
    apply_p.add_argument("--shot")
    apply_p.add_argument("--settle", type=int, default=8)
    apply_p.add_argument("--no-fly", action="store_true")
    apply_p.add_argument("--no-rom", action="store_true")
    apply_p.add_argument("--no-hold", action="store_true")
    apply_p.set_defaults(func=cmd_apply)

    pan = sub.add_parser("pan", help="Pan between two shots")
    pan.add_argument("--shots", type=Path, default=None)
    pan.add_argument("--from", dest="from_shot", required=True)
    pan.add_argument("--to", dest="to_shot", required=True)
    pan.add_argument("--frames", type=int, default=60)
    pan.add_argument("--sample-every", type=int, default=2)
    pan.add_argument("--easing", choices=("ease", "linear"), default="ease")
    pan.add_argument("--out", type=Path)
    pan.add_argument("--no-hold", action="store_true")
    pan.set_defaults(func=cmd_pan)

    cap = sub.add_parser("capture", help="Capture shot list to promo bundle")
    cap.add_argument("--shots", type=Path, default=None)
    cap.add_argument("--out", type=Path, default=None)
    cap.add_argument("--shot", action="append", default=None)
    cap.add_argument("--clip", action="store_true")
    cap.add_argument("--gif", action="store_true")
    cap.add_argument("--avi", action="store_true")
    cap.add_argument("--avi-codec", choices=("none", "zmbv", "cscd", "gif"), default="zmbv")
    cap.add_argument(
        "--preset",
        choices=("square", "story", "wide", "none"),
        default="none",
    )
    cap.add_argument("--fps", type=int, default=30)
    cap.add_argument("--settle", type=int, default=8)
    cap.add_argument("--no-hold", action="store_true")
    cap.add_argument(
        "--no-rom",
        action="store_true",
        help="Prefer fly fallback when ROM warp dispatcher is unavailable",
    )
    cap.add_argument(
        "--hud-off",
        action="store_true",
        help="Cinema: blank HUD tilemap before stills",
    )
    cap.set_defaults(func=cmd_capture)

    smoke = sub.add_parser("smoke", help="One-shot director smoke on private socket")
    smoke.add_argument("--shots", type=Path, default=None)
    smoke.add_argument("--shot")
    smoke.add_argument(
        "--no-rom",
        action="store_true",
        help="Prefer fly fallback when ROM warp dispatcher is unavailable",
    )
    smoke.set_defaults(func=cmd_smoke)

    validate = sub.add_parser(
        "validate", help="Offline dry-run of shots.json (no emulator)"
    )
    validate.add_argument("--shots", type=Path, default=None)
    validate.set_defaults(func=cmd_validate)

    listing = sub.add_parser(
        "list", help="List starter shots, checkpoints, trusted task seeds"
    )
    listing.add_argument("--shots", type=Path, default=None)
    listing.set_defaults(func=cmd_list)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    # Socketless commands skip env rc-play checks that would block local validate.
    if args.command not in ("validate", "list"):
        if "MESEN2_SOCKET_PATH" in os.environ:
            refuse_rc(os.environ.get("MESEN2_SOCKET_PATH"), None)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
