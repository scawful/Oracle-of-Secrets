#!/usr/bin/env python3
"""Private-socket director smoke: refuse rc-play, apply one shot, non-empty PNG.

Requires MESEN2_SOCKET_PATH (or --socket) pointing at an owned instance that is
already in overworld play. Skips cleanly when no socket is available.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MESEN_ROOT = Path(os.environ.get("MESEN2_OOS_ROOT") or ROOT.parent / "mesen2-oos")
CLIENT_DIR = MESEN_ROOT / "tools" / "oos_client"
sys.path.insert(0, str(CLIENT_DIR))

from mesen2_client_lib.client import OracleDebugClient  # noqa: E402
from mesen2_client_lib.director_camera import (  # noqa: E402
    DirectorCamera,
    DirectorError,
    load_cutscene_shots,
    refuse_rc_play_socket,
    shot_by_name,
)

DEFAULT_SHOTS = ROOT / "Data" / "debug" / "promo_shots" / "starter_shots.json"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--socket", default=os.environ.get("MESEN2_SOCKET_PATH"))
    p.add_argument("--shots", type=Path, default=DEFAULT_SHOTS)
    p.add_argument("--shot", default="village_center")
    p.add_argument("--require", action="store_true", help="Fail if no socket")
    args = p.parse_args()

    if not args.socket:
        payload = {"ok": True, "skipped": True, "reason": "no socket"}
        print(json.dumps(payload))
        return 1 if args.require else 0

    if "oos-rc-play" in args.socket:
        print(json.dumps({"ok": False, "error": "refusing oos-rc-play"}))
        return 2

    os.environ["MESEN2_SOCKET_PATH"] = args.socket
    try:
        refuse_rc_play_socket(args.socket)
        client = OracleDebugClient()
        director = DirectorCamera(client)
        shots = load_cutscene_shots(args.shots)
        shot = shot_by_name(shots, args.shot)
        result = director.apply_shot(shot)
        png = client.screenshot() if result.ok else None
        ok = bool(result.ok and png and len(png) > 8)
        print(
            json.dumps(
                {
                    "ok": ok,
                    "shot": shot.name,
                    "camera": {"x": result.camera_x, "y": result.camera_y},
                    "screenshot_bytes": len(png) if png else 0,
                    "error": result.error,
                    "socket": args.socket,
                }
            )
        )
        return 0 if ok else 1
    except DirectorError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
