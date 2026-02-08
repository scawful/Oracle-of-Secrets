#!/usr/bin/env python3
"""
Ralph Codex Loop
Lightweight orchestrator for autonomous Oracle of Secrets gameplay/debugging.
Keeps emulator-level controls separate from in-game navigation, leans on AFS.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import random
import requests
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[2]  # oracle-of-secrets

# Make scripts importable
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

try:
    from mesen2_client_lib.client import OracleDebugClient  # type: ignore
except Exception:
    OracleDebugClient = None  # pragma: no cover
try:
    from agent.brain import AgentBrain  # type: ignore
except Exception:
    AgentBrain = None  # pragma: no cover
try:
    from mesen2_client_lib.capture import capture_debug_snapshot  # type: ignore
except Exception:
    capture_debug_snapshot = None  # pragma: no cover
try:
    from agent.brain import WALKABLE_TILES, TILE_SIZE, MAP_WIDTH, MAP_HEIGHT  # type: ignore
except Exception:
    WALKABLE_TILES = None  # pragma: no cover
    TILE_SIZE = 8  # pragma: no cover
    MAP_WIDTH = 32  # pragma: no cover
    MAP_HEIGHT = 64  # pragma: no cover

DEFAULT_CONFIG: Dict[str, Any] = {
    "root": str(ROOT),
    "rom": str(ROOT / "Roms/oos168x.sfc"),
    "mesen_socket": "/tmp/mesen2-*.sock",
    "mesen_client": str(ROOT / "scripts/mesen2_client.py"),
    "mesen_instance": "agent",
    "afs_cli": str(Path("~").expanduser() / "src/lab/afs/scripts/afs"),
    "contexts": {
        "oracle": str(ROOT / ".context"),
        "mesen2": str((ROOT.parent / "mesen2-oos/.context").resolve()),
        "z3dk": str((ROOT.parent / "z3dk/.context").resolve()),
        "yaze": str((ROOT.parent / "yaze/.context").resolve()),
    },
    "models": {
        "codex_xhigh": {"provider": "openai", "name": "gpt-5.2-codex-xhigh"},
        "gemini_flash": {"provider": "google", "name": "gemini-3.0-flash-preview-01-28"},
        "claude_opus": {"provider": "anthropic", "name": "claude-opus-4.5"},
        "din_local": {"provider": "lmstudio", "name": "din", "endpoint": "http://localhost:1234/v1"},
        "nayru_local": {"provider": "lmstudio", "name": "nayru", "endpoint": "http://localhost:1234/v1"},
        "farore_local": {"provider": "lmstudio", "name": "farore", "endpoint": "http://localhost:1234/v1"},
    },
    "triforce_models": [
        "~/.context/projects/oracle-of-secrets/knowledge/triforce_models.json",
    ],
    "embeddings": {
        "usdasm_index": "~/.context/projects/oracle-of-secrets/knowledge/disassembly",
        "code_embeddings": "~/.context/projects/oracle-of-secrets/knowledge/debug_info.md",
    },
    "model": "gpt-5.2-codex-xhigh",
    "session_log_dir": "~/.context/projects/oracle-of-secrets/scratchpad/sessions",
    "status_dir": str((ROOT / "Docs/Planning/Status/ralph").resolve()),
    "autosave_dir": "",
    "input_chunk_frames": 20,
    "dangerous_paths": ["dw_softlock_south"],
}


def expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def load_config() -> Dict[str, Any]:
    cfg = DEFAULT_CONFIG.copy()
    cfg_path = ROOT / "Tools/ralph-codex-loop/config.yaml"
    if cfg_path.exists():
        if yaml:
            with cfg_path.open() as f:
                loaded = yaml.safe_load(f) or {}
                cfg = deep_merge(cfg, loaded)
        else:
            # YAML not available; proceed with defaults
            pass
    # env overrides
    if os.getenv("MESEN2_SOCKET_PATH"):
        cfg["mesen_socket"] = os.environ["MESEN2_SOCKET_PATH"]
    if os.getenv("MESEN2_INSTANCE"):
        cfg["mesen_instance"] = os.environ["MESEN2_INSTANCE"]
    if os.getenv("RALPH_ROM"):
        cfg["rom"] = os.environ["RALPH_ROM"]
    if os.getenv("RALPH_STATUS_DIR"):
        cfg["status_dir"] = os.environ["RALPH_STATUS_DIR"]
    if os.getenv("RALPH_SESSION_LOG_DIR"):
        cfg["session_log_dir"] = os.environ["RALPH_SESSION_LOG_DIR"]
    if os.getenv("RALPH_AUTOSAVE_DIR"):
        cfg["autosave_dir"] = os.environ["RALPH_AUTOSAVE_DIR"]
    if os.getenv("RALPH_CONTEXT_ORACLE"):
        cfg.setdefault("contexts", {})["oracle"] = os.environ["RALPH_CONTEXT_ORACLE"]
    if cfg.get("mesen_instance") and not os.getenv("MESEN2_INSTANCE"):
        os.environ["MESEN2_INSTANCE"] = str(cfg["mesen_instance"])
    # normalize key paths
    cfg["mesen_client"] = str(expand(cfg["mesen_client"]))
    cfg["rom"] = str(expand(cfg["rom"]))
    cfg["status_dir"] = str(expand(cfg.get("status_dir", ROOT / "Docs/Planning/Status/ralph")))
    cfg["session_log_dir"] = str(expand(cfg.get("session_log_dir", "~/.context/projects/oracle-of-secrets/scratchpad/sessions")))
    return cfg


def deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = base.copy()
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def list_sockets(pattern: str) -> List[Path]:
    return [
        Path(p).resolve()
        for p in sorted(glob.glob(pattern), key=lambda p: os.path.getmtime(p), reverse=True)
    ]


def find_socket(pattern: str) -> Optional[Path]:
    candidates = list_sockets(pattern)
    return candidates[0] if candidates else None


def read_latest_socket_hint() -> Optional[Path]:
    hint = ROOT / ".context/scratchpad/mesen2/latest_socket.txt"
    if hint.exists():
        content = hint.read_text().strip()
        if content:
            return Path(content)
    return None


def run(cmd: List[str], env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def load_secrets_if_present() -> None:
    """Load API keys from ~/.secrets if not already set. Does not log contents."""
    secrets_path = Path.home() / ".secrets"
    if not secrets_path.exists():
        return
    for line in secrets_path.read_text().splitlines():
        line = line.strip()
        if not line.startswith("export "):
            continue
        try:
            _, rest = line.split("export ", 1)
            key, val = rest.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'").strip('"')
            if key and val and key not in os.environ:
                os.environ[key] = val
        except ValueError:
            continue


def dispatch_model(question: str, cfg_model: Dict[str, Any]) -> str:
    """Best-effort model call; returns reply text or raises on hard failure."""
    load_secrets_if_present()
    provider = cfg_model.get("provider")
    name = cfg_model.get("name")
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return "OPENAI_API_KEY missing"
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": name, "messages": [{"role": "user", "content": question}], "max_tokens": 128},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    if provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            return "ANTHROPIC_API_KEY missing"
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
            json={"model": name, "max_tokens": 128, "messages": [{"role": "user", "content": question}]},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", [{}])[0].get("text", "")
    if provider == "google":
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            return "GOOGLE_API_KEY missing"
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{name}:generateContent?key={key}",
            json={"contents": [{"parts": [{"text": question}]}]},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    if provider == "lmstudio":
        endpoint = cfg_model.get("endpoint", "http://localhost:1234/v1")
        resp = requests.post(
            f"{endpoint}/chat/completions",
            json={"model": name, "messages": [{"role": "user", "content": question}], "max_tokens": 128},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    return "Unknown provider"


def mesen_client(cfg: Dict[str, Any], args: List[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    instance = env.get("MESEN2_INSTANCE") or cfg.get("mesen_instance")
    if instance:
        env["MESEN2_INSTANCE"] = str(instance)
    if not env.get("MESEN2_SOCKET_PATH") and not instance:
        hint = read_latest_socket_hint()
        if hint:
            env["MESEN2_SOCKET_PATH"] = str(hint)
        else:
            sockets = list_sockets(cfg["mesen_socket"])
            if len(sockets) > 1:
                raise RuntimeError(
                    "Multiple Mesen2 sockets found. Set MESEN2_INSTANCE or MESEN2_SOCKET_PATH."
                )
            if sockets:
                env["MESEN2_SOCKET_PATH"] = str(sockets[0])
    if not env.get("MESEN2_SOCKET_PATH") and not instance:
        raise RuntimeError("No MESEN2 socket found; start Mesen2 OOS or set MESEN2_SOCKET_PATH.")
    client_args = [sys.executable, str(expand(cfg["mesen_client"]))]
    if instance and "--instance" not in args:
        client_args += ["--instance", str(instance)]
    client_args += args
    return run(client_args, env=env)


def run_state(cfg: Dict[str, Any]) -> Dict[str, Any]:
    res = mesen_client(cfg, ["run-state", "--json"])
    if res.returncode != 0:
        raise RuntimeError(f"run-state failed: {res.stderr.strip() or res.stdout.strip()}")
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return {"raw": res.stdout}


def diagnostics(cfg: Dict[str, Any], deep: bool = False) -> Dict[str, Any]:
    args = ["diagnostics", "--json"]
    if deep:
        args.insert(1, "--deep")
    res = mesen_client(cfg, args)
    if res.returncode != 0:
        raise RuntimeError(f"diagnostics failed: {res.stderr.strip() or res.stdout.strip()}")
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return {"raw": res.stdout}


def append_session_log(cfg: Dict[str, Any], line: str) -> Path:
    log_dir = expand(cfg["session_log_dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    fname = log_dir / f"{dt.date.today()}_ralph.md"
    ts = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    with fname.open("a", encoding="utf-8") as f:
        f.write(f"- {ts}: {line}\n")
    return fname


def record_diag(cfg: Dict[str, Any], payload: Dict[str, Any]) -> Path:
    status_dir = expand(cfg["status_dir"])
    status_dir.mkdir(parents=True, exist_ok=True)
    path = status_dir / f"diag_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


def _autosave_dir(cfg: Dict[str, Any]) -> Optional[Path]:
    raw = cfg.get("autosave_dir") or ""
    if not raw:
        return None
    target = expand(raw)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _autosave_state(client: OracleDebugClient, cfg: Dict[str, Any], label: str, slot: int) -> str:
    autosave_dir = _autosave_dir(cfg)
    if autosave_dir:
        stamp = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_label = label.replace(" ", "_").replace("/", "_")
        path = autosave_dir / f"{safe_label}_{stamp}.mss"
        try:
            client.save_state(path=str(path), allow_external=True)
            return str(path)
        except Exception:
            return "failed"
    try:
        client.save_state(slot=slot)
        return f"slot_{slot}"
    except Exception:
        return "failed"


def get_client(cfg: Dict[str, Any]) -> OracleDebugClient:
    if OracleDebugClient is None:
        raise RuntimeError("mesen2_client_lib not importable; ensure scripts/ is on PYTHONPATH")
    instance = os.getenv("MESEN2_INSTANCE") or cfg.get("mesen_instance")
    if instance:
        os.environ["MESEN2_INSTANCE"] = str(instance)
        return OracleDebugClient()
    sock = os.getenv("MESEN2_SOCKET_PATH")
    if not sock:
        hint = read_latest_socket_hint()
        if hint:
            sock = str(hint)
        else:
            sockets = list_sockets(cfg["mesen_socket"])
            if len(sockets) > 1:
                raise RuntimeError(
                    "Multiple Mesen2 sockets found. Set MESEN2_INSTANCE or MESEN2_SOCKET_PATH."
                )
            if sockets:
                sock = str(sockets[0])
    if not sock:
        raise RuntimeError("No MESEN2 socket found; start Mesen2 OOS or set MESEN2_SOCKET_PATH.")
    return OracleDebugClient(socket_path=sock)


def detect_black_screen(client: OracleDebugClient, diag: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
    if diag is None:
        diag = client.get_diagnostics(deep=True) if hasattr(client, "get_diagnostics") else {}
    camera_ok = diag.get("camera_ok", True)
    overworld = diag.get("overworld", {})
    run_state = diag.get("run_state", {})
    # INIDISP force blank attempt
    inidisp = None
    try:
        inidisp = client.bridge.read(0x002100, 1)[0]  # PPU register
    except Exception:
        pass
    # BG tilemap checksum (best-effort; skip on failure)
    bg_checksum = None
    try:
        if hasattr(client.bridge, "send_command"):
            vres = client.bridge.send_command("VRAM_READ", addr="0x0000", length=512)  # small window
            if isinstance(vres, dict) and vres.get("success") and isinstance(vres.get("data"), list):
                data = bytes(vres["data"])
                bg_checksum = sum(data) & 0xFFFF
    except Exception:
        pass
    indicators = {
        "camera_ok": camera_ok,
        "is_transition": overworld.get("is_transition"),
        "paused": run_state.get("paused"),
        "mode": overworld.get("mode"),
        "submode": overworld.get("submode"),
        "inidisp": inidisp,
        "bg_checksum": bg_checksum,
    }
    # heuristic: camera failure or INIDISP blank bit or paused in gameplay
    blank_bit = (inidisp is not None) and (inidisp & 0x80) != 0
    return (not camera_ok) or blank_bit, indicators


def detect_spawn_flag(client: OracleDebugClient) -> Dict[str, Any]:
    state = client.get_oracle_state()
    spawn_flag = state.get("spawn_flag") or state.get("spawnpoint") or state.get("spawn_point")
    addr_val = None
    try:
        if hasattr(client.bridge, "read_memory"):
            addr_val = client.bridge.read_memory(0x7EF3C8)
    except Exception:
        pass
    return {"spawn_flag": spawn_flag, "spawn_point_ram": addr_val}


def input_gate_from_diag(
    diag: Optional[Dict[str, Any]],
    black_screen: Optional[bool] = None,
) -> Dict[str, Any]:
    """Determine whether it is safe to send inputs based on diagnostics."""
    if not diag:
        return {"allowed": False, "blockers": ["no_diagnostics"], "black_screen": black_screen}

    run_state = diag.get("run_state", {}) or {}
    story_state = diag.get("story_state", {}) or {}
    overworld = diag.get("overworld", {}) or {}
    oracle_state = diag.get("oracle_state", {}) or {}

    paused = run_state.get("paused")
    in_cutscene = story_state.get("in_cutscene")
    transition = overworld.get("is_transition")
    camera_ok = diag.get("camera_ok", True)
    mode = oracle_state.get("mode")

    blockers = []
    if paused is not False:
        blockers.append("paused")
    if in_cutscene is True:
        blockers.append("cutscene")
    if transition is True:
        blockers.append("transition")
    if camera_ok is False:
        blockers.append("camera")
    # Gameplay modes from AgentBrain (overworld/dungeon).
    if mode is not None and mode not in (0x07, 0x09):
        blockers.append("non_gameplay")
    if black_screen is True:
        blockers.append("black_screen")

    return {
        "allowed": not blockers,
        "blockers": blockers,
        "paused": paused,
        "in_cutscene": in_cutscene,
        "transition": transition,
        "camera_ok": camera_ok,
        "black_screen": black_screen,
        "mode": mode,
    }


def ensure_story_state(client: OracleDebugClient, diag: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not diag:
        return diag
    if "story_state" not in diag and hasattr(client, "get_story_state"):
        try:
            diag["story_state"] = client.get_story_state()
        except Exception:
            pass
    return diag


def read_joypad_state(client: OracleDebugClient) -> Dict[str, Any]:
    """Read joypad mirror bytes (best-effort)."""
    try:
        read = client.bridge.read_memory
    except Exception:
        return {}
    try:
        return {
            "JOY1A_ALL": read(0x7E00F0),
            "JOY1B_ALL": read(0x7E00F2),
            "JOY1A_NEW": read(0x7E00F4),
            "JOY1B_NEW": read(0x7E00F6),
            "JOY1A_OLD": read(0x7E00F8),
            "JOY1B_OLD": read(0x7E00FA),
        }
    except Exception:
        return {}


def summarize_collision(client: OracleDebugClient, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Summarize collision map and Link's current tile."""
    cmap = client.get_collision_map()
    if not cmap:
        return {"available": False}

    if state is None:
        state = client.get_oracle_state()

    screen_w = MAP_WIDTH * TILE_SIZE
    screen_h = MAP_HEIGHT * TILE_SIZE
    link_x = state.get("link_x", 0)
    link_y = state.get("link_y", 0)
    tx = (link_x % screen_w) // TILE_SIZE
    ty = (link_y % screen_h) // TILE_SIZE
    idx = ty * MAP_WIDTH + tx
    tile = cmap[idx] if idx < len(cmap) else None
    walkable = None
    if tile is not None and WALKABLE_TILES is not None:
        walkable = tile in WALKABLE_TILES

    unique_tiles = len(set(cmap))
    return {
        "available": True,
        "tile": tile,
        "tile_walkable": walkable,
        "link_tile": (tx, ty),
        "unique_tiles": unique_tiles,
        "map_bytes": len(cmap),
    }


def detect_softlock(
    client: OracleDebugClient,
    sample_seconds: float = 2.5,
    interval: float = 0.25,
    move_threshold: int = 2,
    nudge: bool = True,
    diag: Optional[Dict[str, Any]] = None,
    gate: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Heuristic softlock detection: no movement + no transition + no response to nudges."""
    if gate is None:
        if diag is None:
            diag = client.get_diagnostics(deep=False) if hasattr(client, "get_diagnostics") else {}
        diag = ensure_story_state(client, diag)
        black, _ = detect_black_screen(client, diag=diag)
        gate = input_gate_from_diag(diag, black_screen=black)
    if gate.get("blockers"):
        return False, {"reason": "input_blocked", "gate": gate}

    # Never auto-resume here; if paused, report and exit.
    run_state = client.get_run_state() or {}
    if run_state.get("paused"):
        return False, {"reason": "paused"}

    positions: List[Tuple[int, int]] = []
    joy_before = read_joypad_state(client)
    start = time.time()
    while time.time() - start < sample_seconds:
        state = client.get_oracle_state()
        positions.append((state.get("link_x", 0), state.get("link_y", 0)))
        time.sleep(interval)

    if not positions:
        return False, {"reason": "no_samples"}

    first = positions[0]
    max_delta = max(abs(x - first[0]) + abs(y - first[1]) for x, y in positions)

    diag = diag or client.get_diagnostics(deep=False)
    run_state = diag.get("run_state", {}) if diag else {}
    overworld = diag.get("overworld", {}) if diag else {}

    if run_state.get("paused"):
        return False, {"reason": "paused", "positions": positions[-3:]}
    if overworld.get("is_transition"):
        return False, {"reason": "transition", "positions": positions[-3:]}
    if max_delta >= move_threshold:
        return False, {"reason": "moved", "max_delta": max_delta}

    nudge_results = {}
    if nudge and gate.get("allowed", False):
        for direction in ("up", "down", "left", "right"):
            state = client.get_oracle_state()
            sx, sy = state.get("link_x", 0), state.get("link_y", 0)
            client.press_button(direction, frames=6)
            time.sleep(6 / 60.0 + 0.05)
            state = client.get_oracle_state()
            dx, dy = state.get("link_x", 0) - sx, state.get("link_y", 0) - sy
            nudge_results[direction] = {
                "delta": (dx, dy),
                "joypad": read_joypad_state(client),
            }
            if abs(dx) + abs(dy) >= move_threshold:
                return False, {"reason": "nudge_moved", "nudges": nudge_results, "joy_before": joy_before}

    return True, {"reason": "no_movement", "max_delta": max_delta, "nudges": nudge_results, "joy_before": joy_before, "gate": gate}


def scrutinize_state(client: OracleDebugClient, deep: bool = True, allow_nudge: bool = True) -> Dict[str, Any]:
    diag = client.get_diagnostics(deep=deep)
    joypad = read_joypad_state(client)
    black, indicators = detect_black_screen(client, diag=diag)
    gate = input_gate_from_diag(diag, black_screen=black)
    softlock, soft_info = detect_softlock(client, diag=diag, gate=gate, nudge=allow_nudge)
    collision = summarize_collision(client, diag.get("oracle_state"))

    issues = []
    if black:
        issues.append("black_screen")
    if not diag.get("camera_ok", True):
        issues.append("camera")
    if diag.get("overworld", {}).get("is_transition"):
        issues.append("transition")
    if diag.get("run_state", {}).get("paused"):
        issues.append("paused")
    if diag.get("story_state", {}).get("in_cutscene"):
        issues.append("cutscene")
    if "non_gameplay" in (gate.get("blockers") or []):
        issues.append("non_gameplay")
    if softlock:
        issues.append("softlock")

    return {
        "issues": issues,
        "black_screen": black,
        "black_indicators": indicators,
        "softlock": softlock,
        "softlock_info": soft_info,
        "input_gate": gate,
        "collision": collision,
        "joypad": joypad,
        "diagnostics": diag,
    }


def deep_investigate(cfg: Dict[str, Any], client: OracleDebugClient, label: str, details: Dict[str, Any]) -> Path:
    payload = {
        "label": label,
        "details": details,
    }
    try:
        payload["diagnostics"] = client.get_diagnostics(deep=True)
    except Exception as exc:
        payload["diagnostics_error"] = str(exc)

    if capture_debug_snapshot is not None:
        try:
            snap = capture_debug_snapshot(
                client,
                expand(cfg["status_dir"]),
                watch_profile="overworld",
                prefix=f"investigate_{label}",
                include_cpu=True,
                include_rom=True,
                include_story=True,
                include_watch=True,
                screenshot=True,
            )
            payload["snapshot"] = snap
        except Exception as exc:
            payload["snapshot_error"] = str(exc)

    path = record_diag(cfg, payload)
    append_session_log(cfg, f"investigate {label} -> {path}")
    return path


def safe_input(
    client: OracleDebugClient,
    kind: str,
    value: str,
    frames: int = 30,
    allow_resume: bool = False,
    gate: Optional[Dict[str, Any]] = None,
    chunk_frames: Optional[int] = None,
) -> bool:
    if gate is None:
        diag = client.get_diagnostics(deep=False) if hasattr(client, "get_diagnostics") else {}
        diag = ensure_story_state(client, diag)
        black, _ = detect_black_screen(client, diag=diag)
        gate = input_gate_from_diag(diag, black_screen=black)
    if gate.get("blockers"):
        if allow_resume and gate.get("paused") is True:
            if not client.ensure_running():
                return False
            diag = client.get_diagnostics(deep=False) if hasattr(client, "get_diagnostics") else {}
            diag = ensure_story_state(client, diag)
            black, _ = detect_black_screen(client, diag=diag)
            gate = input_gate_from_diag(diag, black_screen=black)
        if gate.get("blockers"):
            return False
    def send_input(step_frames: int) -> bool:
        if kind == "direction":
            return bool(client.hold_direction(value, frames=step_frames, ensure_running=False))
        if kind == "button":
            return bool(client.press_button(value, frames=step_frames, ensure_running=False))
        raise ValueError("unknown input kind")

    if kind == "button" or not chunk_frames or frames <= chunk_frames:
        return send_input(frames)

    remaining = frames
    while remaining > 0:
        step = min(chunk_frames, remaining)
        if not send_input(step):
            return False
        remaining -= step
        if remaining <= 0:
            break
        # Re-check input gate after each chunk to avoid long blind runs.
        diag = client.get_diagnostics(deep=False) if hasattr(client, "get_diagnostics") else {}
        diag = ensure_story_state(client, diag)
        black, _ = detect_black_screen(client, diag=diag)
        gate = input_gate_from_diag(diag, black_screen=black)
        if gate.get("blockers"):
            return False
    return True


def agent_follow_path_guarded(
    agent: AgentBrain,
    target: Tuple[int, int],
    timeout_seconds: int = 12,
    slice_seconds: float = 2.0,
    allow_resume: bool = False,
) -> Tuple[bool, Dict[str, Any]]:
    start = time.time()
    segments = 0
    last_gate = None
    while time.time() - start < timeout_seconds:
        diag = agent.client.get_diagnostics(deep=False)
        diag = ensure_story_state(agent.client, diag)
        black, _ = detect_black_screen(agent.client, diag=diag)
        gate = input_gate_from_diag(diag, black_screen=black)
        last_gate = gate
        if gate.get("blockers"):
            if allow_resume and gate.get("paused") is True:
                try:
                    agent.client.resume()
                except Exception:
                    return False, {"reason": "resume_failed", "gate": gate, "segments": segments}
                time.sleep(0.1)
                continue
            return False, {"reason": "input_blocked", "gate": gate, "segments": segments}
        remaining = timeout_seconds - (time.time() - start)
        if remaining <= 0:
            break
        ok = agent.follow_path(target[0], target[1], timeout_seconds=min(slice_seconds, remaining))
        segments += 1
        if ok:
            return True, {"segments": segments}
    return False, {"reason": "timeout", "segments": segments, "gate": last_gate}


def run_path_with_agent(path_name: str, allow_resume: bool = False) -> Dict[str, Any]:
    if AgentBrain is None:
        raise RuntimeError("AgentBrain not available")
    agent = AgentBrain()
    targets = {
        "spawn_to_house": (25, 36),
        "spawn_to_pyramid": (22, 30),
        "dw_softlock_south": (16, 48),
    }
    if path_name not in targets:
        raise ValueError(f"Unknown path '{path_name}'")
    tx, ty = targets[path_name]
    pre_diag = agent.client.get_diagnostics(deep=False)
    pre_diag = ensure_story_state(agent.client, pre_diag)
    black, _ = detect_black_screen(agent.client, diag=pre_diag)
    gate = input_gate_from_diag(pre_diag, black_screen=black)
    if gate.get("blockers"):
        if allow_resume and gate.get("paused") is True:
            agent.client.resume()
            time.sleep(0.1)
            pre_diag = agent.client.get_diagnostics(deep=False)
            pre_diag = ensure_story_state(agent.client, pre_diag)
            black, _ = detect_black_screen(agent.client, diag=pre_diag)
            gate = input_gate_from_diag(pre_diag, black_screen=black)
        if gate.get("blockers"):
            return {"ok": False, "error": "input_blocked", "gate": gate, "target": [tx, ty]}
    ok, info = agent_follow_path_guarded(agent, (tx, ty), timeout_seconds=12, allow_resume=allow_resume)
    return {"ok": ok, "target": [tx, ty], **info}


def discover_contexts(cfg: Dict[str, Any]) -> Dict[str, Any]:
    afs_cli = expand(cfg["afs_cli"])
    results = {}
    for name, ctx_path in cfg.get("contexts", {}).items():
        ctx = expand(ctx_path)
        cmd = [str(afs_cli), "context", "discover", "--path", str(ctx.parent if ctx.is_dir() else ctx), "--json"]
        out = run(cmd)
        results[name] = {
            "path": str(ctx),
            "ok": out.returncode == 0,
            "stdout": out.stdout.strip(),
            "stderr": out.stderr.strip(),
        }
    return results


def cmd_diag(cfg: Dict[str, Any]) -> None:
    ctxs = discover_contexts(cfg)
    instance = os.getenv("MESEN2_INSTANCE") or cfg.get("mesen_instance")
    socket_hint = os.getenv("MESEN2_SOCKET_PATH")
    if not socket_hint and not instance:
        socket_hint = read_latest_socket_hint() or find_socket(cfg["mesen_socket"])
    payload: Dict[str, Any] = {
        "instance": instance,
        "socket": str(socket_hint) if socket_hint else None,
        "contexts": ctxs,
        "model": cfg.get("model"),
    }
    try:
        payload["run_state"] = run_state(cfg)
        payload["diagnostics"] = diagnostics(cfg, deep=True)
    except Exception as exc:  # pragma: no cover
        payload["error"] = str(exc)
    path = record_diag(cfg, payload)
    append_session_log(cfg, f"diag captured -> {path}")
    print(json.dumps(payload, indent=2))


def cmd_attach(cfg: Dict[str, Any]) -> None:
    try:
        state = run_state(cfg)
        append_session_log(cfg, f"attach state: {state}")
        print(json.dumps(state, indent=2))
    except Exception as exc:
        append_session_log(cfg, f"attach failed: {exc}")
        print(json.dumps({"error": str(exc)}, indent=2))


def cmd_nav_demo(cfg: Dict[str, Any]) -> None:
    """
    Placeholder navigator: verifies running state and emits the planned path.
    Real pathing should call Overworld/Collision navigator helpers.
    """
    payload: Dict[str, Any] = {}
    try:
        state = run_state(cfg)
        payload["state"] = state
        if state.get("paused"):
            payload["note"] = "paused: nav-demo is read-only; not resuming"
    except Exception as exc:
        payload["state_error"] = str(exc)
    planned = [
        {"name": "spawn_to_house", "area": "light_world", "target": [0x0C8, 0x120]},
        {"name": "spawn_to_pyramid", "area": "dark_world", "target": [0x0B0, 0x0F0]},
    ]
    payload["planned_paths"] = planned
    append_session_log(cfg, f"nav-demo planned paths: {planned}; state={payload.get('state','err')}")
    print(json.dumps(payload, indent=2))


def cmd_nav_run(cfg: Dict[str, Any], path_name: str, allow_resume: bool = False, allow_danger: bool = False) -> None:
    client = get_client(cfg)
    preflight = scrutinize_state(client, deep=True, allow_nudge=False)
    gate = preflight.get("input_gate", {})
    resume_attempted = False
    if path_name in (cfg.get("dangerous_paths") or []) and not allow_danger:
        investigate_path = None
        try:
            investigate_path = str(deep_investigate(cfg, client, f"nav_run_{path_name}_danger_blocked", preflight))
        except Exception:
            investigate_path = "failed"
        payload = {
            "path": path_name,
            "blocked": True,
            "reason": "dangerous_path",
            "resume_attempted": resume_attempted,
            "preflight": preflight,
            "investigate_path": investigate_path,
        }
        append_session_log(cfg, f"nav-run {path_name} blocked=dangerous investigate={investigate_path}")
        print(json.dumps(payload, indent=2))
        return
    if gate.get("paused") is True and allow_resume:
        resume_attempted = True
        try:
            client.resume()
        except Exception:
            pass
        time.sleep(0.1)
        preflight = scrutinize_state(client, deep=True, allow_nudge=False)
        gate = preflight.get("input_gate", {})
    if gate.get("blockers"):
        investigate_path = None
        try:
            investigate_path = str(deep_investigate(cfg, client, f"nav_run_{path_name}_blocked", preflight))
        except Exception:
            investigate_path = "failed"
        payload = {
            "path": path_name,
            "blocked": True,
            "resume_attempted": resume_attempted,
            "preflight": preflight,
            "investigate_path": investigate_path,
        }
        append_session_log(cfg, f"nav-run {path_name} blocked gate={gate} investigate={investigate_path}")
        print(json.dumps(payload, indent=2))
        return

    # Prefer AgentBrain pathfinding if available
    try:
        agent_result = run_path_with_agent(path_name, allow_resume=allow_resume)
    except Exception as agent_err:
        agent_result = {"error": str(agent_err)}
    fallback_steps = {
        "spawn_to_house": [("Down", 140), ("Left", 60)],
        "spawn_to_pyramid": [("Down", 120), ("Right", 90)],
        "dw_softlock_south": [("Down", 220)],
    }
    step_results = []
    if path_name in fallback_steps and agent_result.get("ok") is not True:
        chunk_frames = int(cfg.get("input_chunk_frames") or 0) or None
        for direction, frames in fallback_steps[path_name]:
            ok = safe_input(
                client,
                "direction",
                direction,
                frames=frames,
                allow_resume=allow_resume,
                chunk_frames=chunk_frames,
            )
            step_results.append({"direction": direction, "frames": frames, "ok": ok})
            if not ok:
                break
    scrutiny = scrutinize_state(client, deep=True, allow_nudge=False)
    spawn_info = detect_spawn_flag(client)
    autosave_path = None
    investigate_path = None
    if scrutiny.get("issues"):
        autosave_path = _autosave_state(client, cfg, f"nav_run_{path_name}", 98)
        try:
            investigate_path = str(deep_investigate(cfg, client, f"nav_run_{path_name}", scrutiny))
        except Exception:
            investigate_path = "failed"
    payload = {
        "path": path_name,
        "agent_result": agent_result,
        "fallback_steps": step_results,
        "preflight": preflight,
        "scrutiny": scrutiny,
        "spawn": spawn_info,
        "autosave": autosave_path,
        "investigate_path": investigate_path,
    }
    append_session_log(
        cfg,
        f"nav-run {path_name} agent={agent_result} issues={scrutiny.get('issues')} spawn={spawn_info} autosave={autosave_path} investigate={investigate_path}",
    )
    print(json.dumps(payload, indent=2))


def cmd_detect(cfg: Dict[str, Any]) -> None:
    client = get_client(cfg)
    scrutiny = scrutinize_state(client, deep=True, allow_nudge=False)
    spawn_info = detect_spawn_flag(client)
    autosave = None
    investigate_path = None
    if scrutiny.get("issues"):
        autosave = _autosave_state(client, cfg, "detect", 97)
        try:
            investigate_path = str(deep_investigate(cfg, client, "detect", scrutiny))
        except Exception:
            investigate_path = "failed"
    payload = {
        "scrutiny": scrutiny,
        "spawn": spawn_info,
        "autosave": autosave,
        "investigate_path": investigate_path,
    }
    append_session_log(cfg, f"detect issues={scrutiny.get('issues')} spawn={spawn_info} autosave={autosave} investigate={investigate_path}")
    print(json.dumps(payload, indent=2))


def _pick_target_tile(agent: AgentBrain, min_dist: int = 6) -> Optional[Tuple[int, int]]:
    agent.tick()
    if not agent.nav.collision_map:
        return None
    candidates = []
    start_tx, start_ty = agent.state.link_screen_tile
    for ty in range(MAP_HEIGHT):
        for tx in range(MAP_WIDTH):
            if agent.nav.is_walkable(tx, ty, agent.state.is_swimming):
                dist = abs(tx - start_tx) + abs(ty - start_ty)
                if dist >= min_dist:
                    candidates.append((tx, ty))
    if not candidates:
        return None
    return random.choice(candidates)


def cmd_explore(
    cfg: Dict[str, Any],
    steps: int,
    strict: bool,
    fallback_input: bool,
    max_softlocks: int,
    allow_resume: bool = False,
) -> None:
    if AgentBrain is None:
        raise RuntimeError("AgentBrain not available")
    if fallback_input:
        os.environ["OOS_INPUT_FORCE_FALLBACK"] = "1"
    agent = AgentBrain()
    preflight = scrutinize_state(agent.client, deep=True, allow_nudge=False)
    gate = preflight.get("input_gate", {})
    resume_attempted = False
    if gate.get("paused") is True and allow_resume:
        resume_attempted = True
        try:
            agent.client.resume()
        except Exception:
            pass
        time.sleep(0.1)
        preflight = scrutinize_state(agent.client, deep=True, allow_nudge=False)
        gate = preflight.get("input_gate", {})
    if gate.get("blockers"):
        investigate_path = str(deep_investigate(cfg, agent.client, "explore_preflight_blocked", preflight))
        append_session_log(cfg, f"explore preflight blocked gate={gate} investigate={investigate_path}")
        print(
            json.dumps(
                {
                    "steps": steps,
                    "results": [],
                    "preflight_blocked": True,
                    "resume_attempted": resume_attempted,
                    "preflight": preflight,
                    "investigate_path": investigate_path,
                },
                indent=2,
            )
        )
        return

    story_prev = agent.client.get_story_state()
    results = []
    softlock_streak = 0

    # Preflight softlock check (no nudges)
    pre_softlock, pre_info = detect_softlock(agent.client, diag=preflight.get("diagnostics"), gate=gate, nudge=False)
    if pre_softlock:
        investigate_path = str(deep_investigate(cfg, agent.client, "explore_preflight", {"softlock": True, "info": pre_info}))
        append_session_log(cfg, f"explore preflight softlock investigate={investigate_path}")
        print(json.dumps({"steps": steps, "results": results, "preflight_softlock": True, "investigate_path": investigate_path}, indent=2))
        return

    for step in range(steps):
        target = _pick_target_tile(agent)
        if target is None:
            break

        ok, path_info = agent_follow_path_guarded(agent, target, timeout_seconds=12, allow_resume=allow_resume)
        agent.tick()

        story_now = agent.client.get_story_state()
        story_diff = {k: (story_prev.get(k), story_now.get(k)) for k in story_now if story_now.get(k) != story_prev.get(k)}
        story_prev = story_now

        if ok:
            label = f"explore_step_{step+1}_area_{agent.state.area:02X}"
            saved = agent.save_labeled_deep(label, tags=["exploration", "auto"], strict=strict)
            results.append({"step": step + 1, "target": target, "saved": saved, "story_diff": story_diff, "path_info": path_info})
            softlock_streak = 0
            continue

        if path_info.get("reason") == "input_blocked":
            investigate_path = str(deep_investigate(cfg, agent.client, f"explore_step_{step+1}_blocked", path_info))
            results.append({
                "step": step + 1,
                "target": target,
                "saved": False,
                "blocked": True,
                "path_info": path_info,
                "investigate_path": investigate_path,
                "story_diff": story_diff,
            })
            append_session_log(cfg, f"explore blocked at step {step+1} gate={path_info.get('gate')} investigate={investigate_path}")
            break

        scrutiny = scrutinize_state(agent.client, deep=True, allow_nudge=False)
        investigate_path = None
        if scrutiny.get("issues"):
            _autosave_state(agent.client, cfg, f"explore_step_{step+1}", 96)
            try:
                investigate_path = str(deep_investigate(cfg, agent.client, f"explore_step_{step+1}", scrutiny))
            except Exception:
                investigate_path = "failed"
        if "softlock" in (scrutiny.get("issues") or []):
            softlock_streak += 1
        else:
            softlock_streak = 0
        results.append({
            "step": step + 1,
            "target": target,
            "saved": False,
            "scrutiny": scrutiny,
            "investigate_path": investigate_path,
            "story_diff": story_diff,
            "path_info": path_info,
        })
        if softlock_streak >= max_softlocks:
            append_session_log(cfg, f"explore abort: softlock streak {softlock_streak}")
            break

    append_session_log(cfg, f"explore steps={steps} results={len(results)}")
    print(json.dumps({"steps": steps, "results": results}, indent=2))


def cmd_consult(cfg: Dict[str, Any], question: str, model_key: Optional[str] = None) -> None:
    """
    Consult hook: if API keys/endpoints are present, perform a live call; otherwise log intent.
    """
    model = model_key or "codex_xhigh"
    models = cfg.get("models", {})
    chosen = models.get(model, {})
    payload = {"question": question, "model": model, "details": chosen}
    try:
        reply = dispatch_model(question, chosen)
        payload["reply_preview"] = reply[:280] if isinstance(reply, str) else reply
    except Exception as exc:
        payload["error"] = str(exc)
    append_session_log(cfg, f"consult model={model} q={question} result={payload.get('reply_preview','err')}")
    print(json.dumps(payload, indent=2))


def cmd_log(cfg: Dict[str, Any], message: str) -> None:
    path = append_session_log(cfg, message)
    print(f"logged to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ralph Codex autonomous loop harness")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("diag", help="capture diagnostics and write session log")
    sub.add_parser("attach", help="print current run-state")
    sub.add_parser("nav-demo", help="stub path runner (no inputs yet)")
    navr = sub.add_parser("nav-run", help="run a predefined navigation path")
    navr.add_argument("path", help="path name (spawn_to_house|spawn_to_pyramid|dw_softlock_south)")
    navr.add_argument("--resume", action="store_true", help="resume emulation if paused before running inputs")
    navr.add_argument("--allow-danger", action="store_true", help="allow running paths marked as dangerous")
    sub.add_parser("detect", help="run black-screen and spawn flag detectors")
    explore = sub.add_parser("explore", help="autonomous exploration with deep validation")
    explore.add_argument("--steps", type=int, default=10)
    explore.add_argument("--no-strict", dest="strict", action="store_false", help="allow saves with warnings")
    explore.add_argument("--fallback-input", action="store_true", help="force RAM input fallback")
    explore.add_argument("--max-softlocks", type=int, default=2, help="abort after N consecutive softlocks")
    explore.add_argument("--resume", action="store_true", help="resume emulation if paused during preflight/steps")
    explore.set_defaults(strict=True)
    consult = sub.add_parser("consult", help="consult a subagent model (stub)")
    consult.add_argument("question")
    consult.add_argument("--model", default=None, help="model key from config.yaml")
    log_p = sub.add_parser("log-session", help="append a message to session log")
    log_p.add_argument("message", help="message to append")

    args = parser.parse_args()
    cfg = load_config()

    try:
        if args.command == "diag":
            cmd_diag(cfg)
        elif args.command == "attach":
            cmd_attach(cfg)
        elif args.command == "nav-demo":
            cmd_nav_demo(cfg)
        elif args.command == "nav-run":
            cmd_nav_run(cfg, args.path, allow_resume=args.resume, allow_danger=args.allow_danger)
        elif args.command == "detect":
            cmd_detect(cfg)
        elif args.command == "explore":
            cmd_explore(
                cfg,
                steps=args.steps,
                strict=args.strict,
                fallback_input=args.fallback_input,
                max_softlocks=args.max_softlocks,
                allow_resume=args.resume,
            )
        elif args.command == "consult":
            cmd_consult(cfg, args.question, args.model)
        elif args.command == "log-session":
            cmd_log(cfg, args.message)
    except Exception as exc:  # pragma: no cover
        append_session_log(cfg, f"error: {exc}")
        raise


if __name__ == "__main__":
    main()
