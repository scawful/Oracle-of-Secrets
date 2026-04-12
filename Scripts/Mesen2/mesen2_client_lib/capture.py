"""Shared capture helpers for Oracle of Secrets debugging."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from .client import OracleDebugClient
from .constants import FORM_NAMES, MODE_NAMES, OracleRAM


def resolve_oos_root() -> Optional[Path]:
    env_root = os.getenv("ORACLE_OF_SECRETS_ROOT") or os.getenv("OOS_ROOT")
    if env_root:
        candidate = Path(env_root).expanduser()
        if candidate.exists():
            return candidate
    default_root = Path.home() / "src" / "hobby" / "oracle-of-secrets"
    return default_root if default_root.exists() else None


def get_build_metadata(oos_root: Optional[Path]) -> dict[str, Any]:
    if not oos_root:
        return {}
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(oos_root), "rev-parse", "--short", "HEAD"],
            text=True,
        ).strip()
        dirty = subprocess.check_output(
            ["git", "-C", str(oos_root), "status", "--porcelain"],
            text=True,
        ).strip()
        return {"commit": commit, "dirty": bool(dirty)}
    except Exception:
        return {}


def read_current_state(client: OracleDebugClient) -> dict[str, Any]:
    """Read detailed game state from Mesen2 via the socket bridge."""
    bridge = client.bridge
    link_form = bridge.read_memory(OracleRAM.LINK_FORM)

    scroll_x = bridge.read_memory(OracleRAM.SCROLL_X_LO) | (
        bridge.read_memory(OracleRAM.SCROLL_X_HI) << 8
    )
    scroll_y = bridge.read_memory(OracleRAM.SCROLL_Y_LO) | (
        bridge.read_memory(OracleRAM.SCROLL_Y_HI) << 8
    )

    dungeon_id = bridge.read_memory(0x7E040C)

    return {
        "area": bridge.read_memory(OracleRAM.AREA_ID),
        "room": bridge.read_memory(OracleRAM.ROOM_LAYOUT),
        "mode": bridge.read_memory(OracleRAM.MODE),
        "mode_name": MODE_NAMES.get(bridge.read_memory(OracleRAM.MODE), "Unknown"),
        "submode": bridge.read_memory(OracleRAM.SUBMODE),
        "indoors": bridge.read_memory(OracleRAM.INDOORS),
        "dungeon_id": dungeon_id,
        "link_x": bridge.read_memory16(OracleRAM.LINK_X),
        "link_y": bridge.read_memory16(OracleRAM.LINK_Y),
        "link_dir": bridge.read_memory(OracleRAM.LINK_DIR),
        "link_state": bridge.read_memory(OracleRAM.LINK_STATE),
        "link_form": link_form,
        "link_form_name": FORM_NAMES.get(link_form, f"Unknown (0x{link_form:02X})"),
        "scroll_x": scroll_x,
        "scroll_y": scroll_y,
        "time_hours": bridge.read_memory(OracleRAM.TIME_HOURS),
        "time_minutes": bridge.read_memory(OracleRAM.TIME_MINUTES),
        "time_speed": bridge.read_memory(OracleRAM.TIME_SPEED),
        "health": bridge.read_memory(OracleRAM.HEALTH_CURRENT),
        "max_health": bridge.read_memory(OracleRAM.HEALTH_MAX),
        "magic": bridge.read_memory(OracleRAM.MAGIC_POWER),
        "rupees": bridge.read_memory16(OracleRAM.RUPEES),
        "game_state": bridge.read_memory(OracleRAM.GAME_STATE),
        "oosprog": bridge.read_memory(OracleRAM.OOSPROG),
        "crystals": bridge.read_memory(OracleRAM.CRYSTALS),
    }


def capture_debug_snapshot(
    client: OracleDebugClient,
    output_dir: Path,
    watch_profile: str = "overworld",
    prefix: str = "mesen_capture",
    include_cpu: bool = True,
    include_rom: bool = True,
    include_story: bool = True,
    include_watch: bool = True,
    include_build: bool = True,
    screenshot: bool = True,
) -> dict[str, Any]:
    """Capture a debug snapshot (JSON + optional screenshot)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")

    json_path = output_dir / f"{prefix}_{stamp}.json"
    png_path = output_dir / f"{prefix}_{stamp}.png"

    if watch_profile:
        client.set_watch_profile(watch_profile)

    state = read_current_state(client)
    payload: dict[str, Any] = {
        "timestamp": stamp,
        "state": state,
        "watch_profile": watch_profile,
    }

    if include_story:
        try:
            payload["story"] = client.get_story_state()
        except Exception:
            payload["story"] = {}

    if include_watch:
        try:
            payload["watch_values"] = client.read_watch_values()
        except Exception:
            payload["watch_values"] = {}

    if include_cpu:
        try:
            payload["cpu"] = client.get_cpu_state()
        except Exception:
            payload["cpu"] = {}

    if include_rom:
        try:
            payload["rom"] = client.bridge.get_rom_info()
        except Exception:
            payload["rom"] = {}

    if include_build:
        payload["build"] = get_build_metadata(resolve_oos_root())

    json_path.write_text(json.dumps(payload, indent=2))

    screenshot_path = None
    screenshot_error = None
    if screenshot:
        try:
            data = client.screenshot()
            if data:
                png_path.write_bytes(data)
                screenshot_path = str(png_path)
        except Exception as exc:
            screenshot_error = str(exc)

    return {
        "ok": True,
        "json": str(json_path),
        "screenshot": screenshot_path,
        "screenshot_error": screenshot_error,
    }
