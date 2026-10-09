#!/usr/bin/env python3
"""
Test runner for Oracle of Secrets with MoE orchestrator integration.

Executes test definitions and routes failures to specialized Triforce models.

Defaults to the Mesen2 fork socket API. Set `OOS_TEST_BACKEND=yaze` to force the
YAZE gRPC backend; otherwise `auto` will use the socket backend when available.

Tests with "requiresEmulator": false (e.g. Tests/smoke/lint_pass.json) never touch
an emulator backend. Exec steps may use {repo}, {rom}, {sym}, {hooks} and
{analyzer} placeholders; {rom} comes from --rom, then OOS_TEST_ROM, then the
manifest default. A step's "skipIfMissing" paths turn into a reported step skip
when absent (a failure when OOS_TEST_REQUIRE_ARTIFACTS=1).

--dry-run validates definitions without running them: script paths, step types,
placeholders and saveState IDs (Data/debug/save_state_library.json). Errors fail
the test; artifacts missing from this checkout are reported as warnings.

Usage:
    ./Scripts/Validate/test_runner.py Tests/lr_swap_test.json
    ./Scripts/Validate/test_runner.py Tests/*.json --verbose
    ./Scripts/Validate/test_runner.py Tests/lr_swap_test.json --dry-run
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

_MESEN2_DIR = Path(__file__).resolve().parents[1] / "Mesen2"
if str(_MESEN2_DIR) not in sys.path:
    sys.path.insert(0, str(_MESEN2_DIR))

try:
    from mesen2_client_lib.client import OracleDebugClient
    HAS_SOCKET_BACKEND = True
except Exception:
    HAS_SOCKET_BACKEND = False

try:
    from mesen2_client_lib.state_library import (
        disallowed_state_reason,
        is_disallowed_state_path,
    )
except Exception:
    def is_disallowed_state_path(_path: Path) -> bool:
        return False

    def disallowed_state_reason(path: Path) -> str:
        return f"Blocked legacy save state: {path}"

HAS_YAZE_BACKEND = False
YAZE_ADAPTER = None
YAZE_MCP_ROOT = os.getenv("YAZE_MCP_PATH") or str(Path.home() / "src/tools/yaze-mcp")
if Path(YAZE_MCP_ROOT).exists():
    sys.path.insert(0, YAZE_MCP_ROOT)
    try:
        from core.emulator_abstraction.yaze_adapter import YazeAdapter as _YazeAdapter
        YAZE_ADAPTER = _YazeAdapter
        HAS_YAZE_BACKEND = True
    except Exception:
        HAS_YAZE_BACKEND = False

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "Tests" / "manifest.json"
SAVE_STATE_LIBRARY = REPO_ROOT / "Data" / "debug" / "save_state_library.json"
DEFAULT_ROM = "Roms/oos168x.sfc"

KNOWN_STEP_TYPES = {
    "press", "wait", "assert", "screenshot", "write", "write16", "command",
    "wait_addr", "wait-address", "wait_state", "wait-state", "exec", "comment",
}
# The only step types a "requiresEmulator": false test may use.
HOST_STEP_TYPES = {"exec", "wait", "comment"}
SCRIPT_INTERPRETERS = {"bash", "sh", "zsh"}
_PLACEHOLDER = re.compile(r"\{([A-Za-z_]+)\}")

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def log(msg: str, color: str = ''):
    """Print colored log message."""
    print(f"{color}{msg}{Colors.RESET}")

# No longer using legacy CLI backend.


def _parse_addr(addr: Any) -> Optional[int]:
    if isinstance(addr, int):
        return addr
    if isinstance(addr, str):
        s = addr.strip()
        if s.startswith("$"):
            s = "0x" + s[1:]
        try:
            return int(s, 16 if s.lower().startswith("0x") else 10)
        except ValueError:
            return None
    try:
        return int(addr)
    except Exception:
        return None


class MesenSocketBackend:
    def __init__(self):
        self.client = OracleDebugClient()

    def is_connected(self) -> bool:
        return self.client.is_connected()

    def send(self, cmd: str, *args, timeout: float = 2.0) -> tuple[bool, str]:
        command = cmd.lower()

        if command == "ping":
            return (self.is_connected(), "pong" if self.is_connected() else "not connected")

        if not self.is_connected():
            return False, "Mesen2 socket not connected"

        try:
            if command in ("read", "read8"):
                addr = _parse_addr(args[0]) if args else None
                if addr is None:
                    return False, "Invalid address"
                value = self.client.read_address(addr)
                return True, f"READ:0x{addr:06X}=0x{value:02X} ({value})"

            if command == "read16":
                addr = _parse_addr(args[0]) if args else None
                if addr is None:
                    return False, "Invalid address"
                value = self.client.read_address16(addr)
                return True, f"READ16:0x{addr:06X}=0x{value:04X} ({value})"

            if command == "readblock":
                addr = _parse_addr(args[0]) if len(args) >= 1 else None
                length = parse_int(args[1]) if len(args) >= 2 else None
                if addr is None or length is None:
                    return False, "Invalid readblock args"
                data = self.client.bridge.read_block(addr, int(length))
                return True, f"READBLOCK:0x{addr:06X}={data.hex()}"

            if command == "write":
                addr = _parse_addr(args[0]) if len(args) >= 1 else None
                value = parse_int(args[1]) if len(args) >= 2 else None
                if addr is None or value is None:
                    return False, "Invalid write args"
                ok = self.client.write_address(addr, int(value))
                return ok, f"WRITE:0x{addr:06X}=0x{int(value):02X}"

            if command == "write16":
                addr = _parse_addr(args[0]) if len(args) >= 1 else None
                value = parse_int(args[1]) if len(args) >= 2 else None
                if addr is None or value is None:
                    return False, "Invalid write16 args"
                ok = self.client.bridge.write_memory16(addr, int(value))
                return ok, f"WRITE16:0x{addr:06X}=0x{int(value):04X}"

            if command == "press":
                button = args[0] if args else ""
                frames = parse_int(args[1]) if len(args) >= 2 else 5
                ok = self.client.press_button(str(button), int(frames or 0))
                return ok, f"PRESSED:{button}"
            if command == "reset":
                ok = self.client.reset()
                return ok, "RESET"

            if command == "state":
                state = self.client.get_oracle_state()
                try:
                    story = self.client.get_story_state()
                    state.update(story)
                except Exception:
                    pass
                return True, json.dumps(state)

            if command == "screenshot":
                path = str(args[0]) if args else ""
                if not path:
                    stamp = time.strftime("%Y%m%d_%H%M%S")
                    path = str(Path("Tests/screenshots") / f"mesen_capture_{stamp}.png")
                path_obj = Path(path)
                path_obj.parent.mkdir(parents=True, exist_ok=True)
                data = self.client.screenshot()
                if not data:
                    return False, "Screenshot failed"
                path_obj.write_bytes(data)
                return True, str(path_obj)

            if command in ("loadstate", "load"):
                path = str(args[0]) if args else ""
                if not path:
                    return False, "Missing loadstate path"
                ok = self.client.load_state(path=path)
                return ok, f"LOADSTATE:{path}"

            if command == "loadslot":
                slot = parse_int(args[0]) if args else None
                if slot is None:
                    return False, "Invalid loadslot"
                ok = self.client.load_state(slot=int(slot))
                return ok, f"LOADSLOT:{slot}"

            if command == "wait-load":
                seconds = parse_int(args[0]) if args else 1
                time.sleep(float(seconds or 0))
                return True, f"WAIT:{seconds}"

            return False, f"Unsupported socket command: {cmd}"
        except Exception as exc:
            return False, f"Socket backend error: {exc}"


class YazeBackend:
    def __init__(self):
        if not HAS_YAZE_BACKEND or YAZE_ADAPTER is None:
            raise RuntimeError("Yaze backend not available")
        grpc_target = os.getenv("YAZE_GRPC_TARGET")
        if not grpc_target:
            port = os.getenv("YAZE_GRPC_PORT", "50052")
            grpc_target = f"127.0.0.1:{port}"
        symbols_path = os.getenv("YAZE_SYMBOLS_PATH")
        self.adapter = YAZE_ADAPTER(grpc_target=grpc_target, symbols_path=symbols_path)

    def is_connected(self) -> bool:
        return self.adapter.is_available()

    def _read(self, addr: int, size: int = 1) -> int:
        data = self.adapter.read_memory(addr, size)
        if not data:
            return 0
        if size == 1:
            return data[0]
        if size == 2:
            return data[0] | (data[1] << 8)
        value = 0
        for i, b in enumerate(data):
            value |= b << (i * 8)
        return value

    def send(self, cmd: str, *args, timeout: float = 2.0) -> tuple[bool, str]:
        command = cmd.lower()

        if command == "ping":
            return (self.is_connected(), "pong" if self.is_connected() else "not connected")

        if not self.is_connected():
            return False, "yaze backend not connected"

        try:
            if command in ("read", "read8"):
                addr = _parse_addr(args[0]) if args else None
                if addr is None:
                    return False, "Invalid address"
                value = self._read(addr, 1)
                return True, f"READ:0x{addr:06X}=0x{value:02X} ({value})"

            if command == "read16":
                addr = _parse_addr(args[0]) if args else None
                if addr is None:
                    return False, "Invalid address"
                value = self._read(addr, 2)
                return True, f"READ16:0x{addr:06X}=0x{value:04X} ({value})"

            if command == "readblock":
                addr = _parse_addr(args[0]) if len(args) >= 1 else None
                length = parse_int(args[1]) if len(args) >= 2 else None
                if addr is None or length is None:
                    return False, "Invalid readblock args"
                data = self.adapter.read_memory(addr, int(length))
                return True, f"READBLOCK:0x{addr:06X}={data.hex()}"

            if command == "write":
                addr = _parse_addr(args[0]) if len(args) >= 1 else None
                value = parse_int(args[1]) if len(args) >= 2 else None
                if addr is None or value is None:
                    return False, "Invalid write args"
                ok = self.adapter.write_memory(addr, bytes([int(value) & 0xFF]))
                return ok, f"WRITE:0x{addr:06X}=0x{int(value) & 0xFF:02X}"

            if command == "write16":
                addr = _parse_addr(args[0]) if len(args) >= 1 else None
                value = parse_int(args[1]) if len(args) >= 2 else None
                if addr is None or value is None:
                    return False, "Invalid write16 args"
                lo = int(value) & 0xFF
                hi = (int(value) >> 8) & 0xFF
                ok = self.adapter.write_memory(addr, bytes([lo, hi]))
                return ok, f"WRITE16:0x{addr:06X}=0x{int(value) & 0xFFFF:04X}"

            if command == "state":
                try:
                    from mesen2_client_lib.constants import OracleRAM
                except Exception:
                    OracleRAM = None
                state = {}
                if OracleRAM is not None:
                    state = {
                        "mode": self._read(OracleRAM.MODE, 1),
                        "submode": self._read(OracleRAM.SUBMODE, 1),
                        "area": self._read(OracleRAM.AREA_ID, 1),
                        "room": self._read(OracleRAM.ROOM_LAYOUT, 1),
                        "indoors": self._read(OracleRAM.INDOORS, 1),
                        "link_x": self._read(OracleRAM.LINK_X, 2),
                        "link_y": self._read(OracleRAM.LINK_Y, 2),
                        "link_z": self._read(OracleRAM.LINK_Z, 2),
                    }
                    state["dungeon_room"] = self._read(OracleRAM.ROOM_ID, 2)
                    state["health"] = self._read(OracleRAM.HEALTH_CURRENT, 1)
                    state["max_health"] = self._read(OracleRAM.HEALTH_MAX, 1)
                    state["rupees"] = self._read(OracleRAM.RUPEES, 2)
                return True, json.dumps(state)

            if command == "screenshot":
                path = str(args[0]) if args else ""
                if not path:
                    stamp = time.strftime("%Y%m%d_%H%M%S")
                    path = str(Path("Tests/screenshots") / f"yaze_capture_{stamp}.png")
                path_obj = Path(path)
                path_obj.parent.mkdir(parents=True, exist_ok=True)
                data = self.adapter.screenshot()
                if not data:
                    return False, "Screenshot failed"
                path_obj.write_bytes(data)
                return True, str(path_obj)

            if command in ("loadstate", "load"):
                path = str(args[0]) if args else ""
                if not path:
                    return False, "Missing loadstate path"
                if path.endswith(".mss"):
                    return False, "yaze does not support Mesen2 .mss states"
                ok = self.adapter.load_state(path)
                return ok, f"LOADSTATE:{path}"

            if command == "loadslot":
                return False, "yaze does not support slot-based loads"

            if command == "wait-load":
                seconds = parse_int(args[0]) if args else 1
                time.sleep(float(seconds or 0))
                return True, f"WAIT:{seconds}"

            if command == "press":
                return False, "yaze input not supported via gRPC"

            return False, f"Unsupported yaze command: {cmd}"
        except Exception as exc:
            return False, f"Yaze backend error: {exc}"


class MesenBackend:
    def __init__(self):
        mode = os.environ.get("OOS_TEST_BACKEND", "auto").lower()
        if mode == "cli":
            # Legacy backend removed; treat as socket for compatibility with older envs.
            mode = "socket"
        self.mode = mode
        self.socket_backend = None
        self.yaze_backend = None

        if mode == "yaze":
            if HAS_YAZE_BACKEND:
                self.yaze_backend = YazeBackend()
            else:
                self.mode = "none"

        if self.yaze_backend is None and mode in ("auto", "socket") and HAS_SOCKET_BACKEND:
            candidate = MesenSocketBackend()
            if candidate.is_connected() or mode == "socket":
                self.socket_backend = candidate

    def backend_name(self) -> str:
        if self.yaze_backend is not None:
            return "yaze"
        if self.socket_backend is not None:
            return "socket"
        return "none"

    def send(self, cmd: str, *args, timeout: float = 2.0) -> tuple[bool, str]:
        if self.yaze_backend is not None:
            success, output = self.yaze_backend.send(cmd, *args, timeout=timeout)
            if success or self.mode == "yaze":
                return success, output
        if self.socket_backend is not None:
            success, output = self.socket_backend.send(cmd, *args, timeout=timeout)
            if success or self.mode == "socket":
                return success, output
        return False, "No available backend (socket or yaze)"


_BACKEND: Optional[MesenBackend] = None


def get_backend() -> MesenBackend:
    """Create the backend on first use so host-only tests never probe a socket."""
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = MesenBackend()
    return _BACKEND


def mesen_cmd(cmd: str, *args, timeout: float = 2.0) -> tuple[bool, str]:
    """Execute command via socket API (default) or YAZE gRPC backend."""
    return get_backend().send(cmd, *args, timeout=timeout)


def default_analyzer(repo_root: Path) -> Path:
    """Find z3dk's oracle_analyzer.py like build_rom.sh, also beside the main checkout of a worktree."""
    override = os.environ.get("OOS_ANALYZER")
    if override:
        return Path(override).expanduser()
    roots = [repo_root]
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            roots.append(Path(result.stdout.strip()).parent)
    except (OSError, subprocess.SubprocessError):
        pass
    candidates = [root.parent / "z3dk" / "scripts" / "oracle_analyzer.py" for root in roots]
    return next((path for path in candidates if path.is_file()), candidates[0])


def build_placeholders(repo_root: Path, rom: Any = None, default_rom: str = DEFAULT_ROM) -> dict[str, str]:
    """Values for {name} tokens in exec steps. {sym} and {hooks} sit beside {rom}, as build_rom.sh writes them."""
    rom_path = Path(rom or os.environ.get("OOS_TEST_ROM") or default_rom).expanduser()
    if not rom_path.is_absolute():
        rom_path = repo_root / rom_path
    return {
        "repo": str(repo_root),
        "rom": str(rom_path),
        "sym": str(rom_path.with_suffix(".sym")),
        "hooks": str(rom_path.parent / "hooks.json"),
        "analyzer": str(default_analyzer(repo_root)),
    }


def expand_placeholders(value: Any, placeholders: dict[str, str]) -> str:
    """Replace {name} tokens. An unknown name raises KeyError so a typo cannot pass silently."""
    return _PLACEHOLDER.sub(lambda match: placeholders[match.group(1)], str(value))


def _resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def _skip_if_missing(step: dict) -> list[str]:
    entries = step.get("skipIfMissing") or []
    return [entries] if isinstance(entries, str) else list(entries)


def step_missing_files(step: dict, placeholders: dict[str, str], repo_root: Path) -> list[str]:
    """Paths in the step's skipIfMissing list that do not exist."""
    missing = []
    for entry in _skip_if_missing(step):
        path = _resolve_path(expand_placeholders(entry, placeholders), repo_root)
        if not path.exists():
            missing.append(str(path))
    return missing


def requires_emulator(test: dict) -> bool:
    """Tests need the emulator unless they opt out with "requiresEmulator": false."""
    return test.get("requiresEmulator", True) is not False


def run_yabai(action: str, *args: str) -> None:
    script_path = Path(__file__).parent / "yabai_mesen_window.sh"
    if not script_path.exists():
        return
    cmd = [str(script_path), action, *[str(a) for a in args if a]]
    try:
        subprocess.run(cmd, timeout=2, check=False)
    except Exception:
        pass


def normalize_addr(addr: Any) -> str:
    if isinstance(addr, str):
        addr = addr.strip()
        if addr.startswith("$"):
            addr = "0x" + addr[1:]
        return addr
    return str(addr)


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("$"):
            s = "0x" + s[1:]
        base = 16 if s.lower().startswith("0x") else 10
        try:
            return int(s, base)
        except ValueError:
            return None
    return None


def load_test_manifest(path: Path) -> dict:
    """Load JSON manifest (suite config or save-state library)."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def load_manifest(path: Path) -> dict:
    """Alias for load_test_manifest (used by resolve_save_state)."""
    return load_test_manifest(path)


def get_tests_for_suite(manifest: dict, suite: str, tests_root: Path) -> list[Path]:
    """Get list of test files for a suite; patterns are relative to the manifest's directory."""
    import glob as glob_module

    suite_config = manifest.get("suites", {}).get(suite)
    if not suite_config:
        return []

    test_patterns = suite_config.get("tests", [])
    test_files = []

    for pattern in test_patterns:
        if "*" in pattern:
            # Glob pattern
            for f in sorted(glob_module.glob(str(tests_root / pattern))):
                path = Path(f)
                if path.suffix == ".json" and path.is_file():
                    test_files.append(path)
        else:
            # Exact path
            test_path = tests_root / pattern
            if test_path.exists() and test_path.suffix == ".json":
                test_files.append(test_path)

    return test_files


def missing_suite_entries(manifest: dict, suite: str, tests_root: Path) -> list[Path]:
    """Exact (non-glob) suite entries whose file does not exist."""
    patterns = manifest.get("suites", {}).get(suite, {}).get("tests", [])
    return [tests_root / p for p in patterns if "*" not in p and not (tests_root / p).is_file()]


def get_tests_by_tag(manifest: dict, tag: str, tests_root: Path) -> list[Path]:
    """Get list of test files matching a tag."""
    tag_config = manifest.get("tags", {}).get(tag)
    if not tag_config:
        return []

    test_names = tag_config.get("tests", [])
    test_files = []

    # Search for matching tests in all suites
    for suite_config in manifest.get("suites", {}).values():
        for pattern in suite_config.get("tests", []):
            for test_name in test_names:
                if test_name in pattern or pattern.endswith(f"{test_name}.json"):
                    test_path = tests_root / pattern
                    if test_path.exists() and test_path not in test_files:
                        test_files.append(test_path)

    return test_files


def resolve_save_state(save_state: Any, repo_root: Path, manifest_path: Path) -> dict | None:
    if not save_state:
        return None

    if isinstance(save_state, str):
        save_state = {"path": save_state}
    elif not isinstance(save_state, dict):
        raise ValueError("saveState must be a string or object")

    manifest = load_manifest(manifest_path)
    library_root = save_state.get("libraryRoot") or manifest.get("library_root") or "Roms/SaveStates/library"

    wait_seconds = save_state.get("waitSeconds")
    if wait_seconds is None:
        wait_seconds = save_state.get("wait_seconds")
    if wait_seconds is None:
        wait_seconds = save_state.get("wait")
    wait_seconds = float(wait_seconds) if wait_seconds is not None else 10.0

    reload_caches = bool(save_state.get("reloadCaches") or save_state.get("reload_caches"))
    allow_missing = bool(save_state.get("allowMissing") or save_state.get("skipMissing"))

    state_path = None
    warning = None
    if "id" in save_state:
        state_id = save_state.get("id")
        entries = manifest.get("entries", []) if manifest else []
        found = False
        for entry in entries:
            if entry.get("id") == state_id:
                state_path = entry.get("state_path") or entry.get("path")
                found = True
                break
        if not found:
            warning = f"saveState id not found in manifest: {state_id}"
    # An unknown id falls back to the test's own path/category+file (then slot below).
    if state_path is None and "path" in save_state:
        state_path = save_state.get("path")
    elif state_path is None and "category" in save_state and "file" in save_state:
        state_path = str(Path(save_state["category"]) / save_state["file"])

    if state_path:
        path_obj = Path(str(state_path)).expanduser()
        if not path_obj.is_absolute():
            candidate = repo_root / path_obj
            in_library = repo_root / library_root / path_obj
            if candidate.exists() or (
                not in_library.exists() and path_obj.parts[:1] == Path(library_root).parts[:1]
            ):
                # Repo-relative ("Roms/...") paths stay repo-relative even when absent.
                path_obj = candidate
            else:
                path_obj = in_library
        if is_disallowed_state_path(path_obj):
            return {
                "kind": "missing",
                "reason": disallowed_state_reason(path_obj),
                "blocked": True,
                "allow_missing": allow_missing,
                "warning": warning,
            }
        return {
            "kind": "path",
            "path": path_obj,
            "wait_seconds": wait_seconds,
            "reload_caches": reload_caches,
            "allow_missing": allow_missing,
            "warning": warning,
        }

    slot = save_state.get("slot")
    if slot is not None:
        return {
            "kind": "slot",
            "slot": parse_int(slot),
            "wait_seconds": wait_seconds,
            "reload_caches": reload_caches,
            "allow_missing": allow_missing,
            "warning": warning,
        }

    if warning:
        return {
            "kind": "missing",
            "reason": warning,
            "allow_missing": allow_missing,
        }

    return None


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def check_save_state(save_state: Any, repo_root: Path, library_path: Path) -> tuple[list[str], list[str]]:
    """Check a saveState reference against the catalog. Returns (errors, warnings)."""
    if isinstance(save_state, str):
        save_state = {"path": save_state}
    if not isinstance(save_state, dict):
        return ["saveState must be a string or object"], []
    errors: list[str] = []
    warnings: list[str] = []
    allow_missing = bool(save_state.get("allowMissing") or save_state.get("skipMissing"))
    outcome = "skip" if allow_missing else "fail"

    state_id = save_state.get("id")
    if state_id is not None:
        library = load_manifest(library_path)
        known = {entry.get("id") for entry in library.get("entries", []) if isinstance(entry, dict)}
        if state_id not in known:
            msg = f"saveState id {state_id!r} is not in {_display_path(library_path, repo_root)}"
            has_fallback = ("path" in save_state or "slot" in save_state
                            or ("category" in save_state and "file" in save_state))
            if has_fallback:
                warnings.append(msg + "; the run falls back to the test's path/slot")
            elif allow_missing:
                warnings.append(msg + "; the run will always skip")
            else:
                errors.append(msg)

    try:
        resolved = resolve_save_state(save_state, repo_root, library_path)
    except ValueError as exc:
        return errors + [str(exc)], warnings
    if not resolved:
        return errors, warnings
    if resolved["kind"] == "path" and not resolved["path"].exists():
        warnings.append(
            f"save state file not in this checkout: {_display_path(resolved['path'], repo_root)} "
            f"(the run would {outcome})")
    elif resolved["kind"] == "missing" and resolved.get("blocked"):
        (warnings if allow_missing else errors).append(resolved["reason"])
    return errors, warnings


def _check_exec_step(step: dict, repo_root: Path, placeholders: dict[str, str]) -> tuple[list[str], list[str]]:
    command = step.get("command")
    if not command:
        return ["exec step has no command"], []
    try:
        raw = command if isinstance(command, list) else shlex.split(str(command))
        args = [expand_placeholders(arg, placeholders) for arg in raw]
        cwd = _resolve_path(expand_placeholders(step.get("cwd") or repo_root, placeholders), repo_root)
        missing = step_missing_files(step, placeholders, repo_root)
        optional = {_resolve_path(expand_placeholders(entry, placeholders), repo_root)
                    for entry in _skip_if_missing(step)}
    except KeyError as exc:
        return [f"unknown placeholder {{{exc.args[0]}}}"], []
    except ValueError as exc:
        return [f"malformed command: {exc}"], []
    if not args:
        return ["exec step has no command"], []

    errors: list[str] = []
    if not cwd.is_dir():
        errors.append(f"cwd not found: {cwd}")
    program = args[0]
    name = Path(program).name
    if name in SCRIPT_INTERPRETERS or name.startswith("python"):
        if shutil.which(program) is None:
            errors.append(f"interpreter not on PATH: {program}")
        target = args[1] if len(args) > 1 and not args[1].startswith("-") else None
    else:
        target = program if "/" in program else None
        if target is None and shutil.which(program) is None:
            errors.append(f"command not on PATH: {program}")
    if target is not None:
        target_path = _resolve_path(target, cwd)
        if not target_path.exists() and target_path not in optional:
            errors.append(f"script not found: {target}")
    warnings = [f"would skip: missing {_display_path(Path(path), repo_root)}" for path in missing]
    return errors, warnings


def validate_test_definition(test: dict, repo_root: Path, placeholders: dict[str, str],
                             library_path: Path = SAVE_STATE_LIBRARY) -> tuple[list[str], list[str]]:
    """Static checks behind --dry-run. Errors mean the definition is broken;
    warnings mean this checkout lacks an artifact (ROM, save state) the run needs."""
    errors: list[str] = []
    warnings: list[str] = []
    needs_emulator = requires_emulator(test)
    steps = test.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("test has no steps")
        steps = []
    if not needs_emulator:
        for key in ("saveState", "preconditions"):
            if test.get(key):
                errors.append(f"{key} needs an emulator but requiresEmulator is false")

    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            errors.append(f"step {index}: not an object")
            continue
        kind = step.get("type")
        if kind not in KNOWN_STEP_TYPES:
            errors.append(f"step {index}: unknown type {kind!r}")
            continue
        if not needs_emulator and kind not in HOST_STEP_TYPES:
            errors.append(f"step {index}: {kind} needs an emulator but requiresEmulator is false")
        if kind == "exec":
            step_errors, step_warnings = _check_exec_step(step, repo_root, placeholders)
            errors.extend(f"step {index}: {msg}" for msg in step_errors)
            warnings.extend(f"step {index}: {msg}" for msg in step_warnings)

    if needs_emulator and test.get("saveState"):
        state_errors, state_warnings = check_save_state(test["saveState"], repo_root, library_path)
        errors.extend(state_errors)
        warnings.extend(state_warnings)
    return errors, warnings


def normalize_preconditions(test: dict) -> list[dict]:
    pre = test.get("preconditions", [])
    if isinstance(pre, dict):
        normalized = []
        for addr, cond in pre.items():
            entry = {"address": addr}
            if isinstance(cond, dict):
                entry.update(cond)
            else:
                entry["equals"] = cond
            if "desc" in entry and "description" not in entry:
                entry["description"] = entry["desc"]
            normalized.append(entry)
        return normalized
    if isinstance(pre, list):
        for entry in pre:
            if "desc" in entry and "description" not in entry:
                entry["description"] = entry["desc"]
        return pre
    return []


def parse_condition(step: dict) -> tuple[str | None, Any, list[Any] | None]:
    condition = step.get("condition")
    expected = None
    values = None

    if condition:
        condition = str(condition).lower()
        if condition == "in":
            values = step.get("values", step.get("in"))
        else:
            expected = step.get("value", step.get("equals", step.get("expected")))
    else:
        if "equals" in step:
            condition = "equals"
            expected = step.get("equals")
        elif "in" in step:
            condition = "in"
            values = step.get("in")
        elif "not_equals" in step:
            condition = "not_equals"
            expected = step.get("not_equals")

    return condition, expected, values


def evaluate_condition(actual: int, condition: str, expected: Any, values: list[Any] | None) -> tuple[bool, str]:
    if condition == "equals":
        exp = parse_int(expected)
        if exp is None:
            return False, "Invalid expected value"
        return actual == exp, f"{actual} == {exp}"
    if condition == "not_equals":
        exp = parse_int(expected)
        if exp is None:
            return False, "Invalid expected value"
        return actual != exp, f"{actual} != {exp}"
    if condition == "in":
        vals = values or []
        parsed = [parse_int(v) for v in vals]
        parsed = [v for v in parsed if v is not None]
        if not parsed:
            return False, "Invalid expected list"
        return actual in parsed, f"{actual} in {parsed}"
    if condition in ("less_than", "lt"):
        exp = parse_int(expected)
        if exp is None:
            return False, "Invalid expected value"
        return actual < exp, f"{actual} < {exp}"
    if condition in ("greater_than", "gt"):
        exp = parse_int(expected)
        if exp is None:
            return False, "Invalid expected value"
        return actual > exp, f"{actual} > {exp}"
    return False, f"Unknown condition: {condition}"


def normalize_state_value(value: Any) -> tuple[str, Any]:
    if isinstance(value, bool):
        return "bool", value
    if isinstance(value, (int, float)):
        return "int", int(value)
    if value is None:
        return "none", ""
    return "str", str(value)

def parse_mesen_value(output: str) -> int | None:
    """Parse integer value from the backend read output."""
    # Format: "READ:0x7E0739=0x02 (2)"
    try:
        if '=' in output and '0x' in output:
            hex_part = output.split('=')[1].split()[0]
            return int(hex_part, 16)
    except (IndexError, ValueError):
        pass
    return None

def check_preconditions(test: dict, verbose: bool = False) -> tuple[bool, list[str]]:
    """Check all preconditions are met. Returns (passed, errors)."""
    errors = []

    for pre in normalize_preconditions(test):
        addr = normalize_addr(pre.get("address"))
        desc = pre.get('description', addr)

        condition, expected, values = parse_condition(pre)
        if not condition:
            errors.append(f"Missing condition for {addr}")
            continue

        success, output = mesen_cmd('read', addr)
        if not success:
            errors.append(f"Failed to read {addr}: {output}")
            continue

        actual = parse_mesen_value(output)
        if actual is None:
            errors.append(f"Could not parse value for {addr}: {output}")
            continue

        ok, detail = evaluate_condition(actual, condition, expected, values)
        if not ok:
            errors.append(f"Precondition failed: {desc} ({detail})")
        elif verbose:
            log(f"  ✓ {desc}: {detail}", Colors.GREEN)

    return len(errors) == 0, errors

def execute_step(step: dict, verbose: bool = False,
                 placeholders: Optional[dict[str, str]] = None) -> tuple[bool, str]:
    """Execute a single test step. Returns (passed, message)."""
    step_type = step['type']

    if step_type == 'comment':
        return True, step.get('description', '')

    if step_type == 'press':
        button = step['button']
        frames = step.get('frames', 5)
        success, output = mesen_cmd('press', button, frames, timeout=step.get("timeout", 2.0))
        if verbose:
            log(f"  → Press {button} ({frames} frames)", Colors.BLUE)
        return success, output

    elif step_type == 'wait':
        seconds = step.get('seconds')
        if seconds is None:
            ms = step.get('ms', 100)
            seconds = ms / 1000.0
        if verbose:
            log(f"  → Wait {seconds:.3f}s", Colors.BLUE)
        time.sleep(float(seconds))
        return True, f"Waited {seconds:.3f}s"

    elif step_type == 'assert':
        addr = normalize_addr(step['address'])
        desc = step.get('description', step.get('desc', f"Check {addr}"))

        condition, expected, values = parse_condition(step)
        if not condition:
            return False, f"Missing condition for {addr}"

        success, output = mesen_cmd('read', addr, timeout=step.get("timeout", 2.0))
        if not success:
            return False, f"Failed to read {addr}: {output}"

        actual = parse_mesen_value(output)
        if actual is None:
            return False, f"Could not parse value for {addr}: {output}"

        ok, detail = evaluate_condition(actual, condition, expected, values)
        if ok:
            if verbose:
                log(f"  ✓ {desc}: {detail}", Colors.GREEN)
            return True, f"{desc}: PASS"
        return False, f"{desc}: {detail}"

    elif step_type == 'screenshot':
        path = step.get('path', '')
        success, output = mesen_cmd('screenshot', path, timeout=step.get("timeout", 4.0))
        if verbose:
            log(f"  → Screenshot: {output}", Colors.BLUE)
        return success, output
    elif step_type == "write":
        addr = normalize_addr(step["address"])
        value = step.get("value", step.get("equals"))
        if value is None:
            return False, f"Missing value for write to {addr}"
        success, output = mesen_cmd('write', addr, value, timeout=step.get("timeout", 2.0))
        if verbose:
            log(f"  → Write {addr} = {value}", Colors.BLUE)
        return success, output
    elif step_type == "write16":
        addr = normalize_addr(step["address"])
        value = step.get("value", step.get("equals"))
        if value is None:
            return False, f"Missing value for write16 to {addr}"
        success, output = mesen_cmd('write16', addr, value, timeout=step.get("timeout", 2.0))
        if verbose:
            log(f"  → Write16 {addr} = {value}", Colors.BLUE)
        return success, output
    elif step_type == "command":
        cmd = step.get("command")
        args = step.get("args", [])
        if not cmd:
            return False, "Missing command in command step"
        success, output = mesen_cmd(cmd, *args, timeout=step.get("timeout", 2.0))
        if verbose:
            log(f"  → Command {cmd} {args}", Colors.BLUE)
        return success, output
    elif step_type in ("wait_addr", "wait-address"):
        addr = normalize_addr(step.get("address"))
        desc = step.get('description', step.get('desc', f"Wait for {addr}"))
        condition, expected, values = parse_condition(step)
        if not condition:
            return False, f"Missing condition for {addr}"
        timeout = float(step.get("timeout", 5.0))
        interval = float(step.get("interval", 0.1))
        start = time.time()
        while True:
            success, output = mesen_cmd('read', addr, timeout=step.get("readTimeout", 2.0))
            if success:
                actual = parse_mesen_value(output)
                if actual is not None:
                    ok, detail = evaluate_condition(actual, condition, expected, values)
                    if ok:
                        if verbose:
                            log(f"  ✓ {desc}: {detail}", Colors.GREEN)
                        return True, f"{desc}: PASS"
            if time.time() - start >= timeout:
                return False, f"{desc}: timeout after {timeout}s"
            time.sleep(interval)
    elif step_type in ("wait_state", "wait-state"):
        key = step.get("key") or step.get("field")
        if not key:
            return False, "Missing key for wait_state"
        condition, expected, values = parse_condition(step)
        if not condition:
            return False, f"Missing condition for state.{key}"
        timeout = float(step.get("timeout", 5.0))
        interval = float(step.get("interval", 0.2))
        start = time.time()
        while True:
            success, output = mesen_cmd('state', timeout=step.get("readTimeout", 2.0))
            if success and output:
                try:
                    state = json.loads(output)
                except json.JSONDecodeError:
                    state = None
                if state is not None:
                    value = state.get(key)
                    kind, actual = normalize_state_value(value)
                    if kind in ("int", "bool"):
                        actual_int = int(actual)
                        ok, detail = evaluate_condition(actual_int, condition, expected, values)
                    else:
                        if condition == "equals":
                            ok = str(actual) == str(expected)
                            detail = f"{actual} == {expected}"
                        elif condition == "not_equals":
                            ok = str(actual) != str(expected)
                            detail = f"{actual} != {expected}"
                        elif condition == "in":
                            vals = [str(v) for v in (values or [])]
                            ok = str(actual) in vals
                            detail = f"{actual} in {vals}"
                        else:
                            ok = False
                            detail = "Unknown condition"
                    if ok:
                        if verbose:
                            log(f"  ✓ state.{key}: {detail}", Colors.GREEN)
                        return True, f"state.{key}: PASS"
            if time.time() - start >= timeout:
                return False, f"state.{key}: timeout after {timeout}s"
            time.sleep(interval)
    elif step_type == "exec":
        cmd = step.get("command")
        if not cmd:
            return False, "Missing command in exec step"

        if isinstance(cmd, list):
            args = [str(a) for a in cmd]
        else:
            args = shlex.split(str(cmd))

        extra_args = step.get("args")
        if extra_args:
            if not isinstance(extra_args, list):
                return False, "exec args must be a list"
            args.extend([str(a) for a in extra_args])

        if placeholders is None:
            placeholders = build_placeholders(REPO_ROOT)
        env = os.environ.copy()
        step_env = step.get("env")
        try:
            args = [expand_placeholders(a, placeholders) for a in args]
            if isinstance(step_env, dict):
                env.update({str(k): expand_placeholders(v, placeholders) for k, v in step_env.items()})
            cwd = expand_placeholders(step.get("cwd") or REPO_ROOT, placeholders)
        except KeyError as exc:
            return False, f"Unknown placeholder {{{exc.args[0]}}} in exec step"
        timeout = step.get("timeout", step.get("timeout_seconds"))

        if verbose:
            log(f"  → Exec: {' '.join(args)} (cwd={cwd})", Colors.BLUE)

        try:
            result = subprocess.run(
                args,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, f"Exec timed out after {timeout}s"

        expected = step.get("expectedExitCode", 0)
        output = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode != expected:
            return False, (
                f"Exec exit {result.returncode} (expected {expected}). "
                f"{output}".strip()
            )
        return True, output or "OK"

    else:
        return False, f"Unknown step type: {step_type}"

    return True, "OK"

def route_to_expert(failure_info: dict, test: dict, verbose: bool = False) -> str:
    """Route failure to MoE orchestrator for analysis."""
    on_failure = test.get('onFailure', {})
    expert = on_failure.get('expert', 'farore')
    context = on_failure.get('context', 'Test failed')

    # Build prompt for orchestrator
    prompt = f"""Test Failure Analysis Request

Test: {test['name']}
Description: {test.get('description', 'N/A')}

Failure: {failure_info.get('message', 'Unknown')}
Step: {failure_info.get('step', 'N/A')}

Context: {context}

Please analyze this failure and suggest potential fixes."""

    # Avoid blowing past OS argv limits when failures include large blobs
    # (e.g. static analysis output). Save the full prompt to /tmp and truncate
    # the routed prompt to a reasonable size.
    max_chars = 12000
    try:
        max_chars = int(os.getenv("OOS_MOE_MAX_PROMPT_CHARS", str(max_chars)))
    except Exception:
        max_chars = 12000

    prompt_path: Path | None = None
    if max_chars > 0 and len(prompt) > max_chars:
        try:
            import tempfile
            from datetime import datetime

            prompt_path = Path(tempfile.gettempdir()) / (
                "oos_moe_prompt_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
            )
            prompt_path.write_text(prompt)
        except Exception:
            prompt_path = None

        head_len = max(1, max_chars // 2)
        tail_len = max(1, max_chars - head_len)
        prompt_excerpt = (
            prompt[:head_len]
            + "\n\n...[snip]...\n\n"
            + prompt[-tail_len:]
        )
        note = f"\n\n[Prompt truncated to {max_chars} chars to fit argv limits."
        if prompt_path:
            note += f" Full prompt saved to {prompt_path}]"
        else:
            note += " Full prompt could not be saved.]"
        prompt = prompt_excerpt + note

    log(f"\n{Colors.YELLOW}Routing to {expert} for analysis...{Colors.RESET}")

    # Try to call MoE orchestrator
    orchestrator_path = Path.home() / "src/lab/afs/tools/moe_orchestrator.py"
    if orchestrator_path.exists():
        try:
            result = subprocess.run(
                ["python3", str(orchestrator_path), "--force", expert, "--prompt", prompt],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Orchestrator error: {result.stderr}"
        except subprocess.TimeoutExpired:
            return "Orchestrator timed out"
        except Exception as e:
            return f"Failed to call orchestrator: {e}"
    else:
        return f"Orchestrator not found at {orchestrator_path}. Manual analysis needed:\n{prompt}"

def _prepare_emulator(test: dict, out, *, verbose: bool, quiet: bool, skip_preconditions: bool,
                      skip_load: bool, skip_missing_state: bool) -> Optional[tuple[str, Optional[str]]]:
    """Connect, load the save state and check preconditions. Returns a final (status, message) to stop early."""
    # Bring Mesen to front when tests start (optional)
    if os.environ.get("MESEN_AUTO_FOCUS", "1") not in ("0", "false", "False"):
        script_path = Path(__file__).parent / "yabai_mesen_window.sh"
        if script_path.exists():
            try:
                subprocess.run([str(script_path), "show"], timeout=2, check=False)
            except Exception:
                pass

    # Check bridge connection
    backend = get_backend()
    out("\nChecking bridge connection...")
    out(f"Using backend: {backend.backend_name()} (mode={backend.mode})")
    success, output = mesen_cmd('ping')
    if not success:
        require_emulator = os.environ.get("OOS_TEST_REQUIRE_EMULATOR") == "1"
        msg = (
            f"Bridge not connected: {output}. "
            "Start Mesen2-OOS with the socket API enabled (or set MESEN2_SOCKET_PATH) and re-run. "
            "Set OOS_TEST_REQUIRE_EMULATOR=1 to make this a hard failure."
        )
        if require_emulator:
            if quiet:
                return "failed", msg
            log(f"{Colors.RED}{msg}{Colors.RESET}")
            return "failed", msg

        # Default dev workflow: skip tests when no emulator backend is available.
        if quiet:
            return "skipped", msg
        log(f"{Colors.YELLOW}{msg}{Colors.RESET}")
        return "skipped", msg
    out(f"{Colors.GREEN}Bridge connected{Colors.RESET}")

    # Subscribe to events and show OSD message
    if backend.backend_name() == "socket":
        mesen_cmd("command", "SUBSCRIBE", "events=all")
        mesen_cmd("command", "OSD", f"text=Running Test: {test['name']}")

    # Load save state (optional)
    if not skip_load and test.get("saveState"):
        try:
            repo_root = Path(__file__).resolve().parents[2]
            resolved = resolve_save_state(test.get("saveState"), repo_root, SAVE_STATE_LIBRARY)
        except Exception as exc:
            if not quiet:
                log(f"{Colors.RED}Invalid saveState: {exc}{Colors.RESET}")
            return "failed", str(exc)

        if resolved:
            if resolved.get("warning"):
                out(f"{Colors.YELLOW}{resolved['warning']} (using fallback){Colors.RESET}")
            if resolved["kind"] == "missing":
                msg = resolved.get("reason", "Save state missing")
                if skip_missing_state or resolved.get("allow_missing"):
                    out(f"{Colors.YELLOW}{msg} (skipping){Colors.RESET}")
                    return "skipped", msg
                out(f"{Colors.RED}{msg}{Colors.RESET}")
                return "failed", msg
            if resolved["kind"] == "path":
                state_path = resolved["path"]
                if not state_path.exists():
                    msg = f"Save state not found: {state_path}"
                    if skip_missing_state or resolved.get("allow_missing"):
                        out(f"{Colors.YELLOW}{msg} (skipping){Colors.RESET}")
                        return "skipped", msg
                    out(f"{Colors.RED}{msg}{Colors.RESET}")
                    return "failed", msg
                out(f"\nLoading save state: {state_path}")
                success, output = mesen_cmd("loadstate", str(state_path), timeout=4.0)
                if not success:
                    out(f"{Colors.RED}Loadstate failed: {output}{Colors.RESET}")
                    return "failed", output
            elif resolved["kind"] == "slot":
                slot = resolved.get("slot")
                if not slot:
                    out(f"{Colors.RED}Invalid saveState slot{Colors.RESET}")
                    return "failed", "Invalid saveState slot"
                out(f"\nLoading save slot: {slot}")
                success, output = mesen_cmd("loadslot", str(slot), timeout=4.0)
                if not success:
                    out(f"{Colors.RED}Loadslot failed: {output}{Colors.RESET}")
                    return "failed", output

            if resolved.get("wait_seconds", 0) > 0:
                success, output = mesen_cmd("wait-load", str(int(resolved["wait_seconds"])), timeout=resolved["wait_seconds"] + 2)
                if not success:
                    out(f"{Colors.RED}Wait-load failed: {output}{Colors.RESET}")
                    return "failed", output

            if resolved.get("reload_caches"):
                out("Reloading runtime caches (L+R+Select+Start)...")
                # Hotkey: L+R+Select+Start
                mesen_cmd("press", "L+R+SELECT+START", 5, timeout=2.0)
                time.sleep(0.2)

    # Check preconditions
    if not skip_preconditions:
        out("\nChecking preconditions...")
        passed, errors = check_preconditions(test, verbose)
        if not passed:
            out(f"\n{Colors.RED}Preconditions not met:{Colors.RESET}")
            for err in errors:
                out(f"  • {err}", Colors.RED)
            if test.get("saveState"):
                ss = test["saveState"]
                label = ss.get("id") or ss.get("path") or ss.get("slot") or "unknown"
                out(f"\nLoad save state: {label}")
            return "failed", "; ".join(errors) if errors else "Preconditions not met"
        out(f"{Colors.GREEN}All preconditions met{Colors.RESET}")
    return None


def run_test(test_path: Path, verbose: bool = False, quiet: bool = False, dry_run: bool = False,
             skip_preconditions: bool = False, skip_load: bool = False,
             skip_missing_state: bool = False, moe_enabled: bool = False,
             placeholders: Optional[dict[str, str]] = None) -> tuple[str, str | None]:
    """Run a single test file. Returns (status, message): status is 'passed', 'failed', or 'skipped';
    message explains a failure or skip, or lists skipped steps/dry-run warnings on a pass."""

    with open(test_path) as f:
        test = json.load(f)

    def out(msg: str, color: str = ""):
        if not quiet:
            log(msg, color)

    if placeholders is None:
        placeholders = build_placeholders(REPO_ROOT)
    steps = test.get('steps', [])

    out(f"\n{'='*60}", Colors.BOLD)
    out(f"Test: {test.get('name', test_path.stem)}", Colors.BOLD)
    out(f"{'='*60}")
    out(f"Description: {test.get('description', 'N/A')}")

    if dry_run:
        out(f"\n{Colors.YELLOW}[DRY RUN] Would execute {len(steps) if isinstance(steps, list) else 0} steps{Colors.RESET}")
        for i, step in enumerate(steps if isinstance(steps, list) else [], 1):
            if isinstance(step, dict):
                out(f"  {i}. {step.get('type')}: {step.get('description', step)}")
        errors, warnings = validate_test_definition(test, REPO_ROOT, placeholders)
        for warning in warnings:
            out(f"  ! {warning}", Colors.YELLOW)
        for error in errors:
            out(f"  ✗ {error}", Colors.RED)
        if errors:
            return "failed", "; ".join(errors)
        return "passed", "; ".join(warnings) or None

    if requires_emulator(test):
        stop = _prepare_emulator(test, out, verbose=verbose, quiet=quiet,
                                 skip_preconditions=skip_preconditions, skip_load=skip_load,
                                 skip_missing_state=skip_missing_state)
        if stop is not None:
            return stop
    else:
        out("\nNo emulator required (requiresEmulator: false)")

    # Execute steps
    require_artifacts = os.environ.get("OOS_TEST_REQUIRE_ARTIFACTS") == "1"
    skipped_steps: list[str] = []
    out("\nExecuting test steps...")
    for i, step in enumerate(steps, 1):
        step_desc = step.get('description', step['type'])

        try:
            missing = step_missing_files(step, placeholders, REPO_ROOT)
        except KeyError as exc:
            success, message, missing = False, f"Unknown placeholder {{{exc.args[0]}}} in skipIfMissing", []
        else:
            success, message = True, ""
        if missing and not require_artifacts:
            note = f"step {i} ({step_desc}): missing " + ", ".join(
                _display_path(Path(path), REPO_ROOT) for path in missing)
            skipped_steps.append(note)
            out(f"  SKIP {note}", Colors.YELLOW)
            continue
        if missing:
            success, message = False, (
                f"Missing required file(s): {', '.join(missing)} (OOS_TEST_REQUIRE_ARTIFACTS=1)")
        elif success:
            success, message = execute_step(step, verbose, placeholders)

        if not success:
            out(f"\n{Colors.RED}FAILED at step {i}: {step_desc}{Colors.RESET}")
            out(f"  {message}", Colors.RED)

            if moe_enabled and not quiet:
                failure_info = {
                    'message': message,
                    'step': i,
                    'step_desc': step_desc,
                    'step_data': step
                }
                analysis = route_to_expert(failure_info, test, verbose)
                log(f"\n{Colors.YELLOW}Expert Analysis:{Colors.RESET}")
                log(analysis)
            elif not quiet:
                out(f"\n{Colors.YELLOW}MoE analysis disabled; skipping expert routing.{Colors.RESET}")

            return "failed", message

    if skipped_steps and len(skipped_steps) == len(steps):
        msg = "all steps skipped: " + "; ".join(skipped_steps)
        out(f"\n{Colors.YELLOW}{msg}{Colors.RESET}")
        return "skipped", msg

    out(f"\n{Colors.GREEN}{'='*60}{Colors.RESET}")
    out(f"{Colors.GREEN}TEST PASSED: {test.get('name', test_path.stem)}{Colors.RESET}")
    out(f"{Colors.GREEN}{'='*60}{Colors.RESET}")
    if skipped_steps:
        note = f"{len(skipped_steps)} of {len(steps)} steps skipped: " + "; ".join(skipped_steps)
        out(f"{Colors.YELLOW}{note}{Colors.RESET}")
        return "passed", note
    return "passed", None


def output_results_json(results: list[dict], passed: int, failed: int, skipped: int) -> None:
    """Output results in JSON format."""
    output = {
        "summary": {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": passed + failed + skipped,
        },
        "tests": results,
    }
    print(json.dumps(output, indent=2))


def output_results_junit(results: list[dict], passed: int, failed: int, skipped: int) -> None:
    """Output results in JUnit XML format."""
    import xml.etree.ElementTree as ET

    testsuite = ET.Element("testsuite")
    testsuite.set("name", "oracle-of-secrets")
    testsuite.set("tests", str(passed + failed + skipped))
    testsuite.set("failures", str(failed))
    testsuite.set("skipped", str(skipped))

    for result in results:
        testcase = ET.SubElement(testsuite, "testcase")
        testcase.set("name", result.get("name", "unknown"))
        testcase.set("classname", result.get("file", "unknown"))

        if result.get("status") == "failed":
            failure = ET.SubElement(testcase, "failure")
            failure.set("message", result.get("message", "Test failed"))
        elif result.get("status") == "skipped":
            ET.SubElement(testcase, "skipped")

    tree = ET.ElementTree(testsuite)
    import io
    output = io.StringIO()
    tree.write(output, encoding="unicode", xml_declaration=True)
    print(output.getvalue())


def main():
    parser = argparse.ArgumentParser(description='Oracle of Secrets Test Runner')
    parser.add_argument('tests', nargs='*', help='Test JSON files to run')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--dry-run', action='store_true',
                        help='Validate definitions (scripts, step types, saveState IDs) without executing')
    parser.add_argument('--skip-preconditions', action='store_true',
                        help='Skip precondition checks')
    parser.add_argument('--skip-load', action='store_true',
                        help='Skip loading save states')
    parser.add_argument('--skip-missing-state', action='store_true',
                        help='Skip tests when save state files are missing')
    parser.add_argument('--suite', '-s', type=str,
                        help='Run tests from a manifest suite (smoke, regression, full)')
    parser.add_argument('--manifest', '-m', type=str,
                        help='Path to test manifest (default: Tests/manifest.json)')
    parser.add_argument('--tag', '-t', type=str,
                        help='Run tests matching a specific tag')
    parser.add_argument('--moe-enabled', action='store_true',
                        help='Enable MoE analysis on failures')
    parser.add_argument('--output-format', choices=['text', 'json', 'junit'],
                        default='text', help='Output format')
    parser.add_argument('--fail-fast', action='store_true',
                        help='Stop on first failure')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='One line per test; no bridge/precondition/step chatter')
    parser.add_argument('--rom', type=str,
                        help='ROM bound to {rom} in exec steps (default: $OOS_TEST_ROM, '
                             f'then the manifest default, then {DEFAULT_ROM})')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    # Determine test files to run
    test_files = []
    missing_entries: list[Path] = []
    default_rom = DEFAULT_ROM

    if args.suite or args.tag:
        # Load manifest
        manifest_path = Path(args.manifest) if args.manifest else DEFAULT_MANIFEST
        manifest = load_test_manifest(manifest_path)

        if not manifest:
            log(f"{Colors.RED}Could not load manifest: {manifest_path}{Colors.RESET}")
            return 1
        tests_root = manifest_path.parent
        default_rom = manifest.get("defaults", {}).get("rom") or DEFAULT_ROM

        if args.suite:
            test_files = get_tests_for_suite(manifest, args.suite, tests_root)
            missing_entries = missing_suite_entries(manifest, args.suite, tests_root)
            if not test_files and not missing_entries:
                log(f"{Colors.RED}No tests found for suite: {args.suite}{Colors.RESET}")
                log(f"Available suites: {', '.join(manifest.get('suites', {}).keys())}")
                return 1

        if args.tag:
            tag_tests = get_tests_by_tag(manifest, args.tag, tests_root)
            if not tag_tests:
                log(f"{Colors.YELLOW}No tests found for tag: {args.tag}{Colors.RESET}")
            else:
                test_files.extend([t for t in tag_tests if t not in test_files])

    # Add explicit test files
    for test_pattern in args.tests:
        test_path = Path(test_pattern)
        if test_path.is_file():
            if test_path not in test_files:
                test_files.append(test_path)
        else:
            # Glob pattern
            for p in Path('.').glob(test_pattern):
                if p.suffix == '.json' and p not in test_files:
                    test_files.append(p)

    if not test_files and not missing_entries:
        log(f"{Colors.RED}No test files specified{Colors.RESET}")
        parser.print_help()
        return 1

    rom = Path(args.rom).expanduser().absolute() if args.rom else None
    placeholders = build_placeholders(repo_root, rom, default_rom)
    if args.dry_run and not args.quiet:
        log("Placeholders: " + ", ".join(
            f"{{{key}}}={value}{'' if key == 'repo' or Path(value).exists() else ' (missing)'}"
            for key, value in placeholders.items()))

    if not args.dry_run and os.environ.get("MESEN_AUTO_UNSTASH", "1") not in ("0", "false", "False"):
        run_yabai("unstash")

    passed = 0
    failed = 0
    skipped = 0
    results = []

    if args.quiet and len(test_files) > 1:
        log(f"Suite: {args.suite or 'explicit'} ({len(test_files)} tests)")

    for missing_path in missing_entries:
        failed += 1
        msg = f"listed in manifest but missing: {missing_path}"
        log(f"  {Colors.RED}{missing_path.stem}: FAIL{Colors.RESET} — {msg}")
        results.append({"name": missing_path.stem, "file": str(missing_path),
                        "status": "failed", "message": msg})
    if missing_entries and args.fail_fast:
        test_files = []

    for test_path in test_files:
        result, fail_msg = run_test(
            test_path,
            verbose=args.verbose,
            quiet=args.quiet,
            dry_run=args.dry_run,
            skip_preconditions=args.skip_preconditions,
            skip_load=args.skip_load,
            skip_missing_state=args.skip_missing_state,
            moe_enabled=args.moe_enabled,
            placeholders=placeholders,
        )

        test_result = {
            "name": test_path.stem,
            "file": str(test_path),
            "status": result,
        }
        if fail_msg:
            test_result["message"] = fail_msg

        if result == "passed":
            passed += 1
            if args.quiet:
                log(f"  {Colors.GREEN}{test_path.stem}: PASS{Colors.RESET}" + (f" — {fail_msg}" if fail_msg else ""))
        elif result == "skipped":
            skipped += 1
            if args.quiet:
                log(f"  {Colors.YELLOW}{test_path.stem}: SKIP{Colors.RESET}" + (f" — {fail_msg}" if fail_msg else ""))
        else:
            failed += 1
            if args.quiet:
                log(f"  {Colors.RED}{test_path.stem}: FAIL{Colors.RESET}" + (f" — {fail_msg}" if fail_msg else ""))
            if args.fail_fast:
                test_result["message"] = fail_msg or "Test failed (fail-fast triggered)"
                results.append(test_result)
                break

        results.append(test_result)

    # Output results
    if args.output_format == "json":
        output_results_json(results, passed, failed, skipped)
    elif args.output_format == "junit":
        output_results_junit(results, passed, failed, skipped)
    else:
        log(f"\n{'='*60}")
        log(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
        log(f"{'='*60}")

    if os.environ.get("MESEN_STASH_ON_FAIL", "0") not in ("0", "false", "False"):
        if failed > 0:
            scratch = os.environ.get("SCRATCH_SPACE", "")
            if scratch:
                run_yabai("stash", scratch)
            else:
                run_yabai("hide")
    elif os.environ.get("MESEN_AUTO_STASH", "0") not in ("0", "false", "False"):
        scratch = os.environ.get("SCRATCH_SPACE", "")
        if scratch:
            run_yabai("stash", scratch)
        else:
            run_yabai("hide")

    # Exit codes: 0 = all passed, 1 = failures, 2 = all skipped
    if failed > 0:
        return 1
    if passed == 0 and skipped > 0:
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(main())
