"""Socket bridge for Mesen2 OOS.

Standalone socket client (no mesen2-mcp dependency). Provides a
high-level API for the Mesen2 fork socket server.
"""

from __future__ import annotations

import glob
import json
import os
import errno
import socket
import time
from pathlib import Path
from typing import Any


def _registry_dir() -> Path:
    override = os.getenv("MESEN2_REGISTRY_DIR")
    if override:
        return Path(override).expanduser().resolve()
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root / ".context" / "scratchpad" / "mesen2" / "instances").resolve()


def _resolve_instance_socket() -> None:
    if os.getenv("MESEN2_SOCKET_PATH"):
        return
    instance = os.getenv("MESEN2_INSTANCE") or os.getenv("MESEN2_REGISTRY_INSTANCE")
    if not instance:
        return
    record_path = _registry_dir() / f"{instance}.json"
    if not record_path.exists():
        return
    try:
        data = json.loads(record_path.read_text())
    except json.JSONDecodeError:
        return
    socket_path = data.get("socket")
    if socket_path:
        os.environ["MESEN2_SOCKET_PATH"] = socket_path


_resolve_instance_socket()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def cleanup_stale_sockets(verbose: bool = False) -> list[str]:
    """Remove stale Mesen2 sockets whose PIDs no longer exist."""
    removed: list[str] = []
    sock_pattern = "/tmp/mesen2-*.sock"

    for sock_path in glob.glob(sock_pattern):
        basename = os.path.basename(sock_path)
        if not basename.startswith("mesen2-") or not basename.endswith(".sock"):
            continue

        try:
            pid_str = basename[7:-5]  # "mesen2-<PID>.sock"
            pid = int(pid_str)
        except ValueError:
            continue

        try:
            os.kill(pid, 0)
        except OSError as exc:
            # Only treat ESRCH (no such process) as stale.
            # In sandboxed environments we may get EPERM for a *live* PID; do not delete.
            if getattr(exc, "errno", None) == errno.EPERM:
                if verbose:
                    print(f"Skip socket (no permission to probe PID {pid}): {sock_path}")
                continue
            if getattr(exc, "errno", None) != errno.ESRCH:
                if verbose:
                    print(f"Skip socket (unknown kill() failure for PID {pid}): {sock_path} ({exc})")
                continue
            try:
                os.unlink(sock_path)
                removed.append(sock_path)
                if verbose:
                    print(f"Removed stale socket: {sock_path}")
            except OSError:
                pass

            status_path = sock_path.replace(".sock", ".status")
            try:
                os.unlink(status_path)
                if verbose:
                    print(f"Removed stale status: {status_path}")
            except OSError:
                pass

    return removed


def _coerce_param_key(command_type: str, value: Any) -> dict[str, Any]:
    """Best-effort wrapper for legacy positional params."""
    if command_type == "EXEC_LUA":
        return {"code": value}
    if command_type == "LABELS" and isinstance(value, str):
        if value.startswith(("0x", "0X", "$")):
            return {"action": "get", "addr": value.replace("$", "0x")}
        return {"action": "lookup", "label": value}
    if command_type == "SYMBOLS_RESOLVE" and isinstance(value, str):
        return {"symbol": value}
    return {"value": value}


class MesenBridge:
    """Communicate with Mesen2 via Unix socket server."""

    def __init__(
        self,
        socket_path: str | None = None,
        *,
        auto_reconnect: bool | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
        ping_timeout: float | None = None,
    ) -> None:
        self._socket_path = socket_path
        self._socket: socket.socket | None = None
        self._auto_reconnect = _env_bool("MESEN2_AUTO_RECONNECT", True) if auto_reconnect is None else auto_reconnect
        self._max_retries = _env_int("MESEN2_RECONNECT_RETRIES", 2) if max_retries is None else max_retries
        self._retry_delay = _env_float("MESEN2_RECONNECT_DELAY", 0.15) if retry_delay is None else retry_delay
        self._ping_timeout = _env_float("MESEN2_PING_TIMEOUT", 1.0) if ping_timeout is None else ping_timeout

    @property
    def socket_path(self) -> str | None:
        """Get or discover the socket path.

        Canonical order:
          1) explicit path (constructor arg)
          2) MESEN2_SOCKET_PATH / MESEN2_SOCKET env vars
          3) status files (mesen2-*.status, socketPath) by mtime
          4) glob /tmp/mesen2-*.sock by mtime

        Important: if an explicit socket path is provided, return it as-is.
        Callers can use `is_connected()`/`check_health()` to validate.

        We only probe sockets (PING) during *auto-discovery* to avoid picking
        stale sockets, and to keep unit tests deterministic (no surprise
        discovery of a real emulator socket).
        """
        # Explicit path: do not probe (tests + deterministic callers).
        if self._socket_path:
            return self._socket_path

        # Env (prefer MESEN2_SOCKET_PATH, then deprecated MESEN2_SOCKET).
        # Do not probe; send_command() will fail clearly if it's wrong.
        for env_var in ("MESEN2_SOCKET_PATH", "MESEN2_SOCKET"):
            env_socket = os.getenv(env_var)
            if env_socket:
                self._socket_path = env_socket
                return self._socket_path

        discovered = self._discover_socket_path()
        if discovered:
            self._socket_path = discovered
        return self._socket_path

    def _discover_socket_path(self) -> str | None:
        # Status files: read socketPath, sort by status file mtime (newest first)
        status_files = glob.glob("/tmp/mesen2-*.status")
        if status_files:
            candidates = []
            for sf in status_files:
                try:
                    with open(sf) as f:
                        data = json.load(f)
                    sp = data.get("socketPath")
                    if sp and isinstance(sp, str):
                        candidates.append((os.path.getmtime(sf), sp))
                except (OSError, json.JSONDecodeError, KeyError):
                    continue
            if candidates:
                candidates.sort(key=lambda x: -x[0])
                # Prefer first socketPath that responds to PING; else fall back to most recent.
                for _, sp in candidates:
                    if self._probe_socket(sp):
                        return sp
                return candidates[0][1]

        # Fallback: glob sockets by socket file mtime (do not assume PID in name)
        sockets = glob.glob("/tmp/mesen2-*.sock")
        if not sockets:
            return None
        sockets.sort(key=os.path.getmtime, reverse=True)
        # Prefer first socket that responds to PING; else use most recent
        for candidate in sockets:
            if self._probe_socket(candidate):
                return candidate
        return sockets[0]

    @staticmethod
    def _probe_socket(path: str) -> bool:
        """Check whether a socket responds to PING."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            sock.connect(path)
            cmd = json.dumps({"type": "PING"}) + "\n"
            sock.sendall(cmd.encode())

            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b"\n" in response:
                    break

            sock.close()
            if not response:
                return False
            payload = json.loads(response.decode().strip())
            return bool(payload.get("success"))
        except Exception:
            return False

    def _reset_socket(self) -> None:
        try:
            self._socket_path = None
        except Exception:
            pass

    def is_connected(self) -> bool:
        try:
            result = self.send_command("PING", timeout=2.0)
            return result.get("success", False)
        except Exception:
            return False

    def check_health(self, timeout: float | None = None) -> dict[str, Any]:
        start = time.time()
        ok = False
        error = ""
        try:
            result = self.send_command("PING", timeout=timeout or self._ping_timeout)
            ok = bool(result.get("success"))
            if not ok:
                error = str(result.get("error") or "PING failed")
        except Exception as exc:
            error = str(exc)
        latency_ms = int((time.time() - start) * 1000)
        return {
            "ok": ok,
            "socket": self.socket_path,
            "latency_ms": latency_ms,
            "error": error,
        }

    def capabilities(self) -> dict[str, Any]:
        """Fetch socket capability metadata."""
        return self.send_command("CAPABILITIES")

    def register_agent(
        self,
        agent_id: str,
        *,
        agent_name: str | None = None,
        version: str | None = None,
    ) -> dict[str, Any]:
        """Register an agent with the socket server for diagnostics."""
        params: dict[str, str] = {"agentId": agent_id}
        if agent_name:
            params["agentName"] = agent_name
        if version:
            params["version"] = version
        return self.send_command("AGENT_REGISTER", params)

    def metrics(self) -> dict[str, Any]:
        """Fetch socket metrics from the server."""
        return self.send_command("METRICS")

    def command_history(self, count: int = 20) -> dict[str, Any]:
        """Fetch recent socket command history."""
        return self.send_command("COMMAND_HISTORY", {"count": str(count)})

    def ensure_connected(self, retries: int = 3, delay: float = 0.25) -> bool:
        for _ in range(max(1, retries)):
            info = self.check_health()
            if info.get("ok"):
                return True
            self._reset_socket()
            if delay:
                time.sleep(delay)
        return False

    def send_command(
        self,
        command_type: str,
        params: dict[str, Any] | Any | None = None,
        timeout: float = 5.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a command to Mesen2 and wait for response."""
        path = self.socket_path
        # Do not require stat()-ability; some environments may hide socket
        # paths even though connect() works.
        if not path:
            raise ConnectionError("Mesen2 socket not found. Is Mesen2 running?")

        payload: dict[str, Any] = {}
        if isinstance(params, dict):
            payload.update(params)
        elif params is not None:
            payload.update(_coerce_param_key(command_type, params))
        if kwargs:
            payload.update(kwargs)

        cmd = {"type": command_type}
        cmd.update(payload)

        attempts = self._max_retries if self._auto_reconnect else 0
        for attempt in range(attempts + 1):
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect(path)

                cmd_json = json.dumps(cmd) + "\n"
                sock.sendall(cmd_json.encode())

                response = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                    if b"\n" in response:
                        break

                sock.close()

                if not response:
                    raise TimeoutError(f"No response from Mesen2 within {timeout}s")

                return json.loads(response.decode().strip())

            except (socket.timeout, TimeoutError):
                if not self._auto_reconnect or attempt >= attempts:
                    raise TimeoutError(f"No response from Mesen2 within {timeout}s")
                self._reset_socket()
                if self._retry_delay:
                    time.sleep(self._retry_delay)
            except (socket.error, ConnectionError, OSError, json.JSONDecodeError) as exc:
                if not self._auto_reconnect or attempt >= attempts:
                    raise ConnectionError(f"Socket error: {exc}")
                self._reset_socket()
                if self._retry_delay:
                    time.sleep(self._retry_delay)

        raise RuntimeError("send_command: unexpected retry loop exit")

    def get_state(self) -> dict[str, Any]:
        return self.send_command("STATE")

    def read_memory(self, address: int, memtype: str | None = None) -> int:
        params: dict[str, str] = {"addr": f"0x{address:06X}"}
        if memtype:
            params["memtype"] = memtype
        result = self.send_command("READ", params)
        if result.get("success"):
            data = result.get("data", "0x00")
            if isinstance(data, str):
                return int(data.replace("0x", "").replace('"', ""), 16)
        return 0

    def read_memory16(self, address: int, memtype: str | None = None) -> int:
        params: dict[str, str] = {"addr": f"0x{address:06X}"}
        if memtype:
            params["memtype"] = memtype
        result = self.send_command("READ16", params)
        if result.get("success"):
            data = result.get("data", "0x0000")
            if isinstance(data, str):
                return int(data.replace("0x", "").replace('"', ""), 16)
        return 0

    def read_block(self, address: int, length: int, memtype: str | None = None) -> bytes:
        params: dict[str, str] = {
            "addr": f"0x{address:06X}",
            "len": str(length),
        }
        if memtype:
            params["memtype"] = memtype
        result = self.send_command("READBLOCK", params)
        if result.get("success"):
            data = result.get("data", "")
            if isinstance(data, str):
                hex_str = data.replace('"', "")
                return bytes.fromhex(hex_str)
        return b""

    def read_block_binary(self, address: int, length: int, memtype: str | None = None) -> bytes:
        import base64
        params: dict[str, str] = {
            "addr": f"0x{address:06X}",
            "size": str(length),
        }
        if memtype:
            params["memtype"] = memtype
        result = self.send_command("READBLOCK_BINARY", params)
        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict) and isinstance(data.get("bytes"), str):
                try:
                    return base64.b64decode(data.get("bytes", ""))
                except Exception:
                    return b""
        return b""

    def write_memory(self, address: int, value: int, memtype: str | None = None) -> bool:
        params: dict[str, str] = {
            "addr": f"0x{address:06X}",
            "value": f"0x{value:02X}",
        }
        if memtype:
            params["memtype"] = memtype
        result = self.send_command("WRITE", params)
        return result.get("success", False)

    def write_memory16(self, address: int, value: int, memtype: str | None = None) -> bool:
        params: dict[str, str] = {
            "addr": f"0x{address:06X}",
            "value": f"0x{value:04X}",
        }
        if memtype:
            params["memtype"] = memtype
        result = self.send_command("WRITE16", params)
        return result.get("success", False)

    def write_block(self, address: int, data: bytes, memtype: str | None = None) -> bool:
        params: dict[str, str] = {
            "addr": f"0x{address:06X}",
            "hex": data.hex().upper(),
        }
        if memtype:
            params["memtype"] = memtype
        result = self.send_command("WRITEBLOCK", params)
        return result.get("success", False)

    def press_button(self, buttons: str, frames: int = 5, player: int = 0) -> bool:
        result = self.send_command("INPUT", {
            "buttons": buttons,
            "player": str(player),
            "frames": str(frames),
        })
        return result.get("success", False)

    def pause(self) -> bool:
        result = self.send_command("PAUSE")
        return result.get("success", False)

    def resume(self) -> bool:
        result = self.send_command("RESUME")
        return result.get("success", False)

    def reset(self) -> bool:
        result = self.send_command("RESET")
        return result.get("success", False)

    def save_state(self, slot: int | None = None, path: str | None = None) -> bool:
        params: dict[str, str] = {}
        if slot is not None:
            params["slot"] = str(slot)
        if path is not None:
            params["path"] = path
        result = self.send_command("SAVESTATE", params)
        return result.get("success", False)

    def load_state(self, slot: int | None = None, path: str | None = None) -> bool:
        params: dict[str, str] = {}
        if slot is not None:
            params["slot"] = str(slot)
        if path is not None:
            params["path"] = path
        result = self.send_command("LOADSTATE", params)
        return result.get("success", False)

    def load_script(self, name: str = "mcp_script", path: str | None = None, content: str | None = None) -> int:
        params: dict[str, str] = {"name": name}
        if path:
            params["path"] = path
        if content:
            params["content"] = content
        result = self.send_command("LOADSCRIPT", params)
        if result.get("success"):
            try:
                return int(result.get("data", -1))
            except (ValueError, TypeError):
                return -1
        return -1

    def execute_lua(self, base64_code: str) -> dict[str, Any]:
        return self.send_command("EXEC_LUA", {"code": base64_code})

    def screenshot(self) -> bytes | None:
        import base64
        result = self.send_command("SCREENSHOT")
        if result.get("success"):
            data = result.get("data", "")
            if isinstance(data, str):
                b64_data = data.strip('"')
                try:
                    return base64.b64decode(b64_data)
                except Exception:
                    return None
        return None

    def get_cpu_state(self) -> dict[str, Any]:
        result = self.send_command("CPU")
        if result.get("success"):
            data = result.get("data")
            if isinstance(data, dict):
                return data
        return {}

    def disassemble(self, address: int, count: int = 10) -> list[dict[str, Any]]:
        result = self.send_command("DISASM", {
            "addr": f"0x{address:06X}",
            "count": str(count),
        })
        if result.get("success"):
            data = result.get("data", [])
            if isinstance(data, list):
                return data
        return []

    def step(self, count: int = 1, mode: str = "into") -> bool:
        result = self.send_command("STEP", {"count": str(count), "mode": mode})
        return result.get("success", False)

    def run_frames(self, count: int = 1) -> bool:
        """Advance emulation by `count` frames.

        On the Mesen2-OOS fork, the most reliable cross-build behavior is:
        - RESUME (if paused)
        - wait wall-clock time for `count` frames (based on STATE.fps)
        - PAUSE (if we resumed)

        Some socket builds expose STEP/FRAME-style frame stepping, but it is not
        consistently implemented across local setups and can result in "OK"
        responses without advancing game logic. We intentionally avoid relying
        on those semantics here.
        """
        count = max(0, int(count))
        if count <= 0:
            return True

        # Fetch FPS + paused state.
        fps = 60.0
        was_paused = False
        try:
            state = self.send_command("STATE", timeout=2.0)
            if state.get("success"):
                data = state.get("data", {})
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except Exception:
                        data = {}
                if isinstance(data, dict):
                    was_paused = bool(data.get("paused", False))
                    fps_val = data.get("fps")
                    if isinstance(fps_val, (int, float)) and fps_val > 1:
                        fps = float(fps_val)
        except Exception:
            pass

        # Run.
        if was_paused:
            self.resume()
            time.sleep(0.01)
        time.sleep(count / max(1.0, fps))
        if was_paused:
            self.pause()
        return True

    def get_rom_info(self) -> dict[str, Any]:
        result = self.send_command("ROMINFO")
        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict):
                return data
        return {}

    def rewind(self, seconds: int = 1) -> bool:
        result = self.send_command("REWIND", {"seconds": str(seconds)})
        return result.get("success", False)

    def add_cheat(self, code: str, format: str = "ProActionReplay") -> bool:
        result = self.send_command("CHEAT", {
            "action": "add",
            "code": code,
            "format": format,
        })
        return result.get("success", False)

    def list_cheats(self) -> list[dict[str, Any]]:
        result = self.send_command("CHEAT", {"action": "list"})
        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict):
                return data.get("cheats", [])
        return []

    def clear_cheats(self) -> bool:
        result = self.send_command("CHEAT", {"action": "clear"})
        return result.get("success", False)

    def set_speed(self, multiplier: float) -> bool:
        result = self.send_command("SPEED", {"multiplier": str(multiplier)})
        return result.get("success", False)

    def get_speed(self) -> float:
        result = self.send_command("SPEED")
        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict):
                return data.get("fps", 0.0)
        return 0.0

    def search_memory(self, pattern: str, memtype: str = "WRAM", start: int | None = None, end: int | None = None) -> list[int]:
        params: dict[str, str] = {"pattern": pattern, "memtype": memtype}
        if start is not None:
            params["start"] = f"0x{start:X}"
        if end is not None:
            params["end"] = f"0x{end:X}"
        result = self.send_command("SEARCH", params)
        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict):
                matches = data.get("matches", [])
                return [int(m.replace("0x", "").replace('"', ""), 16) for m in matches if isinstance(m, str)]
        return []

    def create_snapshot(self, name: str, memtype: str = "WRAM") -> bool:
        result = self.send_command("SNAPSHOT", {"name": name, "memtype": memtype})
        return result.get("success", False)

    def diff_snapshot(self, snapshot_name: str) -> list[dict[str, Any]]:
        result = self.send_command("DIFF", {"snapshot": snapshot_name})
        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict):
                changes = data.get("changes", [])
                return [
                    {
                        "addr": int(c["addr"].replace("0x", ""), 16),
                        "old": int(c["old"].replace("0x", ""), 16),
                        "new": int(c["new"].replace("0x", ""), 16),
                    }
                    for c in changes
                    if isinstance(c, dict)
                ]
        return []

    def set_label(self, address: int, label: str, comment: str = "", memtype: str = "WRAM") -> bool:
        result = self.send_command("LABELS", {
            "action": "set",
            "addr": f"0x{address:06X}",
            "label": label,
            "comment": comment,
            "memtype": memtype,
        })
        return result.get("success", False)

    def get_label(self, address: int, memtype: str = "WRAM") -> dict[str, str] | None:
        result = self.send_command("LABELS", {
            "action": "get",
            "addr": f"0x{address:06X}",
            "memtype": memtype,
        })
        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict) and data.get("label"):
                return {
                    "label": data.get("label", ""),
                    "comment": data.get("comment", ""),
                }
        return None

    def lookup_label(self, label: str) -> int | None:
        result = self.send_command("LABELS", {"action": "lookup", "label": label})
        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict):
                addr_str = data.get("addr", "")
                if addr_str:
                    return int(addr_str.replace("0x", "").replace('"', ""), 16)
        return None

    def clear_labels(self) -> bool:
        result = self.send_command("LABELS", {"action": "clear"})
        return result.get("success", False)

    def add_breakpoint(
        self,
        address: int,
        bptype: str = "exec",
        end_address: int | None = None,
        memtype: str = "SnesMemory",
        cputype: str = "Snes",
        condition: str = "",
    ) -> int:
        params: dict[str, str] = {
            "action": "add",
            "addr": f"0x{address:06X}",
            "bptype": bptype,
            "memtype": memtype,
            "cputype": cputype,
        }
        if end_address is not None:
            params["endaddr"] = f"0x{end_address:06X}"
        if condition:
            params["condition"] = condition

        result = self.send_command("BREAKPOINT", params)
        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict):
                return data.get("id", -1)
        return -1

    def remove_breakpoint(self, breakpoint_id: int) -> bool:
        result = self.send_command("BREAKPOINT", {"action": "remove", "id": str(breakpoint_id)})
        return result.get("success", False)

    def list_breakpoints(self) -> list[dict[str, Any]]:
        result = self.send_command("BREAKPOINT", {"action": "list"})
        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict):
                return data.get("breakpoints", [])
        return []

    def enable_breakpoint(self, breakpoint_id: int) -> bool:
        result = self.send_command("BREAKPOINT", {"action": "enable", "id": str(breakpoint_id)})
        return result.get("success", False)

    def disable_breakpoint(self, breakpoint_id: int) -> bool:
        result = self.send_command("BREAKPOINT", {"action": "disable", "id": str(breakpoint_id)})
        return result.get("success", False)

    def clear_breakpoints(self) -> bool:
        result = self.send_command("BREAKPOINT", {"action": "clear"})
        return result.get("success", False)

    def p_watch_start(self, depth: int = 1000) -> dict[str, Any]:
        return self.send_command("P_WATCH", {"action": "start", "depth": str(depth)})

    def p_watch_stop(self) -> dict[str, Any]:
        return self.send_command("P_WATCH", {"action": "stop"})

    def p_watch_status(self) -> dict[str, Any]:
        return self.send_command("P_WATCH", {"action": "status"})

    def p_log(self, count: int = 50) -> dict[str, Any]:
        return self.send_command("P_LOG", {"count": str(count)})

    def p_assert(self, addr: int, expected: int, mask: int = 0xFF) -> dict[str, Any]:
        return self.send_command("P_ASSERT", {
            "addr": f"0x{addr:06X}",
            # Mesen2-OOS socket API expects `expected_p`.
            "expected_p": f"0x{expected:02X}",
            "mask": f"0x{mask:02X}",
        })

    def mem_watch_add(self, addr: int, size: int = 1, depth: int = 100) -> dict[str, Any]:
        return self.send_command("MEM_WATCH_WRITES", {
            "action": "add",
            "addr": f"0x{addr:06X}",
            "size": str(size),
            "depth": str(depth),
        })

    def mem_watch_remove(self, watch_id: int) -> dict[str, Any]:
        return self.send_command("MEM_WATCH_WRITES", {"action": "remove", "watch_id": str(watch_id)})

    def mem_watch_list(self) -> dict[str, Any]:
        return self.send_command("MEM_WATCH_WRITES", {"action": "list"})

    def mem_watch_clear(self) -> dict[str, Any]:
        return self.send_command("MEM_WATCH_WRITES", {"action": "clear"})

    def mem_blame(self, watch_id: int | None = None, addr: int | None = None) -> dict[str, Any]:
        params: dict[str, str] = {}
        if watch_id is not None:
            params["watch_id"] = str(watch_id)
        if addr is not None:
            params["addr"] = f"0x{addr:06X}"
        return self.send_command("MEM_BLAME", params)

    def symbols_load(self, file_path: str, clear: bool = False) -> dict[str, Any]:
        return self.send_command("SYMBOLS_LOAD", {
            "file": file_path,
            "clear": "true" if clear else "false",
        })

    def symbols_resolve(self, symbol: str) -> dict[str, Any]:
        return self.send_command("SYMBOLS_RESOLVE", {"symbol": symbol})

    def collision_overlay(self, enabled: bool | None = None, colmap: str | None = None, highlight: list[int] | None = None) -> dict[str, Any]:
        params: dict[str, str] = {}
        if enabled is not None:
            params["enabled"] = "true" if enabled else "false"
        if colmap is not None:
            params["colmap"] = colmap
        if highlight is not None:
            params["highlight"] = ",".join(f"0x{t:02X}" for t in highlight)
        return self.send_command("COLLISION_OVERLAY", params)

    def collision_dump(self, colmap: str = "A") -> dict[str, Any]:
        return self.send_command("COLLISION_DUMP", {"colmap": colmap})

    def eval_expression(self, expression: str, cpu_type: str = "snes", use_cache: bool = True) -> dict[str, Any]:
        return self.send_command("EVAL", {
            "expression": expression,
            "cpu": cpu_type,
            "cache": "true" if use_cache else "false",
        })

    def set_pc(self, address: int) -> dict[str, Any]:
        return self.send_command("SET_PC", {"addr": f"0x{address:06X}"})

    def memory_size(self, memtype: str = "wram") -> dict[str, Any]:
        return self.send_command("MEMORY_SIZE", {"memtype": memtype})

    def draw_path(self, points: str, color: str | None = None, frames: int | None = None) -> dict[str, Any]:
        params: dict[str, str] = {"points": points}
        if color is not None:
            params["color"] = color
        if frames is not None:
            params["frames"] = str(frames)
        return self.send_command("DRAW_PATH", params)


__all__ = ["MesenBridge", "cleanup_stale_sockets"]
