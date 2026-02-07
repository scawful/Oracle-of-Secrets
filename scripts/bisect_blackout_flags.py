#!/usr/bin/env python3
"""Bisect dungeon blackout root cause across feature flags.

This is a helper around scripts/repro_blackout_transition.py that tries to find
the *smallest* set of feature flags that, when disabled, makes the blackout stop
reproducing from a known seed savestate (slot/path).

It assumes:
  - "defaults" profile reproduces the blackout (exit code 1)
  - disabling all candidate flags fixes it (exit code 0)

If either assumption doesn't hold, it prints guidance and exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _csv(items: list[str]) -> str:
    return ",".join([x.strip() for x in items if x.strip()])


def _run(cmd: list[str], *, cwd: Path) -> int:
    r = subprocess.run(cmd, cwd=cwd)
    return int(r.returncode)


@dataclass(frozen=True)
class TestConfig:
    version: int
    profile: str
    enable: list[str]
    disable: list[str]
    instance: str
    socket: str
    launch: bool
    launch_ui: bool
    arm: bool
    seed_slot: int | None
    seed_state: str | None
    seed_lib: str | None
    press: str
    press_frames: int
    settle_frames: int
    max_frames: int
    poll_every: int
    no_capture: bool


def run_repro(cfg: TestConfig) -> int:
    cmd = [
        sys.executable,
        "scripts/repro_blackout_transition.py",
        "--build",
        "--version",
        str(cfg.version),
        "--instance",
        str(cfg.instance),
        "--profile",
        str(cfg.profile),
        "--enable",
        _csv(cfg.enable),
        "--disable",
        _csv(cfg.disable),
        "--press",
        str(cfg.press),
        "--press-frames",
        str(cfg.press_frames),
        "--settle-frames",
        str(cfg.settle_frames),
        "--max-frames",
        str(cfg.max_frames),
        "--poll-every",
        str(cfg.poll_every),
        "--capture-kind",
        "bisect",
        "--capture-desc",
        "feature-flag bisect",
    ]
    if cfg.no_capture:
        cmd.append("--no-capture")
    if cfg.socket:
        cmd += ["--socket", str(cfg.socket)]
    if cfg.launch:
        cmd.append("--launch")
    if cfg.launch_ui:
        cmd.append("--launch-ui")
    if cfg.arm:
        cmd.append("--arm")

    if cfg.seed_lib:
        cmd += ["--lib", str(cfg.seed_lib)]
    elif cfg.seed_state:
        cmd += ["--state", str(cfg.seed_state)]
    else:
        cmd += ["--slot", str(cfg.seed_slot or 20)]

    return _run(cmd, cwd=REPO_ROOT)


def is_fixed(
    cfg: TestConfig,
    *,
    runs: int,
    sleep_s: float,
    log: list[dict],
) -> bool:
    """Return True if the blackout does NOT reproduce (rc==0) for all runs."""
    for i in range(runs):
        t0 = time.time()
        rc = run_repro(cfg)
        dt = time.time() - t0
        log.append(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "run": i + 1,
                "runs": runs,
                "disable": cfg.disable,
                "enable": cfg.enable,
                "profile": cfg.profile,
                "rc": rc,
                "seconds": round(dt, 2),
            }
        )
        # 0 = no anomaly; 1 = anomaly; 125 = no mesen2; 2 = build fail.
        if rc == 125:
            raise RuntimeError("Mesen2 not connected or seed state could not be loaded (rc=125).")
        if rc == 2:
            raise RuntimeError("Build failed (rc=2).")
        if rc != 0:
            return False
        if sleep_s:
            time.sleep(float(sleep_s))
    return True


def ddmin(disable_set: list[str], test_fixed) -> list[str]:
    """Classic ddmin on a set where predicate is 'fixed when these are disabled'."""
    n = 2
    current = list(disable_set)
    while len(current) >= 2:
        chunks: list[list[str]] = []
        chunk_size = max(1, len(current) // n)
        for i in range(0, len(current), chunk_size):
            chunks.append(current[i : i + chunk_size])

        reduced = False

        # 1) Try disabling only a chunk
        for c in chunks:
            if test_fixed(c):
                current = c
                n = 2
                reduced = True
                break
        if reduced:
            continue

        # 2) Try disabling everything except a chunk (i.e. remove c from current)
        for c in chunks:
            complement = [x for x in current if x not in c]
            if test_fixed(complement):
                current = complement
                n = max(2, n - 1)
                reduced = True
                break
        if reduced:
            continue

        if n >= len(current):
            break
        n = min(len(current), n * 2)

    return current


def main() -> int:
    ap = argparse.ArgumentParser(description="Bisect dungeon blackout across feature flags (disable-set minimization).")
    ap.add_argument("--version", type=int, default=168)
    ap.add_argument("--profile", default="defaults", help="Base profile (default defaults).")
    ap.add_argument("--candidates", default="", help="Comma-separated flags to bisect (default: common suspects).")
    ap.add_argument("--runs", type=int, default=2, help="How many times to run each config (pass must be stable).")
    ap.add_argument("--sleep", type=float, default=0.05, help="Sleep between runs (seconds).")
    ap.add_argument("--no-capture", action="store_true", help="Do not emit /tmp captures during bisect.")
    ap.add_argument("--instance", default="oos-bisect", help="Mesen2 instance name (default: oos-bisect)")
    ap.add_argument("--socket", default="", help="Mesen2 socket path override (optional)")
    ap.add_argument("--launch", action="store_true", help="Auto-launch Mesen2 if not connected")
    ap.add_argument("--launch-ui", action="store_true", help="Launch with UI instead of --headless")
    ap.add_argument("--arm", action="store_true", help="Arm agentic instrumentation once before bisect")

    seed = ap.add_mutually_exclusive_group(required=False)
    seed.add_argument("--slot", type=int, default=20, help="Seed savestate slot (default 20).")
    seed.add_argument("--state", type=str, help="Seed savestate path (.mss).")
    seed.add_argument("--lib", type=str, help="Seed state ID from the local state library")

    ap.add_argument("--press", default="DOWN")
    ap.add_argument("--press-frames", type=int, default=90)
    ap.add_argument("--settle-frames", type=int, default=120)
    ap.add_argument("--max-frames", type=int, default=1200)
    ap.add_argument("--poll-every", type=int, default=10)
    ap.add_argument("--out", default="", help="Write JSON log here (optional).")
    args = ap.parse_args()

    os.chdir(REPO_ROOT)

    default_candidates = [
        "custom_room_collision",
        "water_gate_hooks",
        "water_gate_overlay_redirect",
        "graphics_transfer_scroll_hook",
        "follower_transition_hooks",
    ]
    candidates = [x.strip() for x in (args.candidates.split(",") if args.candidates else default_candidates) if x.strip()]
    if not candidates:
        print("No candidates provided.", file=sys.stderr)
        return 2

    log: list[dict] = []

    base_cfg = TestConfig(
        version=int(args.version),
        profile=str(args.profile or "defaults"),
        enable=[],
        disable=[],
        instance=str(args.instance),
        socket=str(args.socket or ""),
        launch=bool(args.launch),
        launch_ui=bool(args.launch_ui),
        arm=bool(args.arm),
        seed_slot=None if args.state else int(args.slot),
        seed_state=str(args.state) if args.state else None,
        seed_lib=str(args.lib) if args.lib else None,
        press=str(args.press),
        press_frames=int(args.press_frames),
        settle_frames=int(args.settle_frames),
        max_frames=int(args.max_frames),
        poll_every=int(args.poll_every),
        no_capture=bool(args.no_capture),
    )

    print(f"Candidates: {candidates}")
    print("Sanity check: baseline should reproduce (defaults, no disables).")
    try:
        baseline_fixed = is_fixed(base_cfg, runs=max(1, int(args.runs)), sleep_s=float(args.sleep), log=log)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 125
    if baseline_fixed:
        print("Baseline did NOT reproduce (blackout not seen).")
        print("Action: adjust seed state/press window or increase --max-frames; then rerun.")
        _write_log(args.out, log)
        return 3

    print("Sanity check: disabling all candidates should fix.")
    all_disabled_cfg = TestConfig(**{**base_cfg.__dict__, "disable": list(candidates)})
    try:
        all_disabled_fixed = is_fixed(all_disabled_cfg, runs=max(1, int(args.runs)), sleep_s=float(args.sleep), log=log)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 125
    if not all_disabled_fixed:
        print("Disabling all candidates did NOT fix the repro.")
        print("Action: expand --candidates (or the root cause is outside feature-flagged code).")
        _write_log(args.out, log)
        return 4

    def predicate(disable_subset: list[str]) -> bool:
        cfg = TestConfig(**{**base_cfg.__dict__, "disable": list(disable_subset)})
        return is_fixed(cfg, runs=max(1, int(args.runs)), sleep_s=float(args.sleep), log=log)

    print("Minimizing disable set...")
    minimal = ddmin(list(candidates), predicate)
    minimal = sorted(set(minimal), key=lambda x: candidates.index(x) if x in candidates else 9999)

    print("")
    print("Result (minimal disables that make it stop reproducing):")
    for f in minimal:
        print(f"  - {f}")
    print("")
    print("Next action:")
    print(f"  python3 scripts/repro_blackout_transition.py --build --profile {base_cfg.profile} --disable {','.join(minimal)}")
    print("")
    _write_log(args.out, log)
    return 0


def _write_log(out_path: str, log: list[dict]) -> None:
    if not out_path:
        return
    p = Path(out_path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"runs": log}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
