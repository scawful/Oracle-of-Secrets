"""Bridge import helper for mesen2-mcp with auto-reconnect helpers."""

import json
import os
import sys
import time
from pathlib import Path


def _add_to_path(path: Path) -> None:
    if path.exists():
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


env_path = os.getenv("MESEN2_MCP_PATH")
if env_path:
    _add_to_path(Path(env_path).expanduser())
else:
    _add_to_path(Path.home() / "src" / "tools" / "mesen2-mcp")


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
    socket = data.get("socket")
    if socket:
        os.environ["MESEN2_SOCKET_PATH"] = socket


_resolve_instance_socket()

try:
    from mesen2_mcp.bridge import MesenBridge as _BaseBridge
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "mesen2_mcp not found. Set MESEN2_MCP_PATH to the mesen2-mcp repo root."
    ) from exc

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
    """Remove stale Mesen2 sockets whose PIDs no longer exist.

    Looks for /tmp/mesen2-<PID>.sock files and removes them
    if the corresponding process is no longer running.

    Args:
        verbose: If True, print info about removed sockets

    Returns:
        List of removed socket paths
    """
    import glob
    import signal

    removed = []
    sock_pattern = "/tmp/mesen2-*.sock"

    for sock_path in glob.glob(sock_pattern):
        # Extract PID from socket name
        basename = os.path.basename(sock_path)
        if not basename.startswith("mesen2-") or not basename.endswith(".sock"):
            continue

        try:
            pid_str = basename[7:-5]  # "mesen2-<PID>.sock"
            pid = int(pid_str)
        except ValueError:
            continue

        # Check if process is still running
        try:
            os.kill(pid, 0)  # Signal 0 = check existence
            # Process still exists, don't remove
        except OSError:
            # Process doesn't exist, clean up socket and status file
            try:
                os.unlink(sock_path)
                removed.append(sock_path)
                if verbose:
                    print(f"Removed stale socket: {sock_path}")
            except OSError:
                pass

            # Also clean up corresponding .status file
            status_path = sock_path.replace(".sock", ".status")
            try:
                os.unlink(status_path)
                if verbose:
                    print(f"Removed stale status: {status_path}")
            except OSError:
                pass

    return removed


class MesenBridge(_BaseBridge):
    """Thin wrapper with auto-reconnect + health check helpers."""

    def __init__(
        self,
        socket_path: str | None = None,
        *,
        auto_reconnect: bool | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
        ping_timeout: float | None = None,
    ) -> None:
        super().__init__(socket_path)
        self._auto_reconnect = _env_bool("MESEN2_AUTO_RECONNECT", True) if auto_reconnect is None else auto_reconnect
        self._max_retries = _env_int("MESEN2_RECONNECT_RETRIES", 2) if max_retries is None else max_retries
        self._retry_delay = _env_float("MESEN2_RECONNECT_DELAY", 0.15) if retry_delay is None else retry_delay
        self._ping_timeout = _env_float("MESEN2_PING_TIMEOUT", 1.0) if ping_timeout is None else ping_timeout

    def _reset_socket(self) -> None:
        try:
            self._socket_path = None  # type: ignore[attr-defined]
        except Exception:
            pass

    def send_command(self, *args, **kwargs):  # type: ignore[override]
        attempts = self._max_retries if self._auto_reconnect else 0
        for attempt in range(attempts + 1):
            try:
                return super().send_command(*args, **kwargs)
            except (ConnectionError, TimeoutError, OSError, ValueError) as exc:
                if not self._auto_reconnect or attempt >= attempts:
                    raise
                self._reset_socket()
                if self._retry_delay:
                    time.sleep(self._retry_delay)
        # Should never reach here - loop either returns or raises
        raise RuntimeError("send_command: unexpected loop exit")

    def check_health(self, timeout: float | None = None) -> dict:
        start = time.time()
        ok = False
        error = ""
        try:
            result = super().send_command("PING", timeout=timeout or self._ping_timeout)
            ok = bool(result.get("success"))
            if not ok:
                error = str(result.get("error") or "PING failed")
        except Exception as exc:  # pragma: no cover - health should not crash
            error = str(exc)
        latency_ms = int((time.time() - start) * 1000)
        return {
            "ok": ok,
            "socket": self.socket_path,
            "latency_ms": latency_ms,
            "error": error,
        }

    def ensure_connected(self, retries: int = 3, delay: float = 0.25) -> bool:
        for _ in range(max(1, retries)):
            info = self.check_health()
            if info.get("ok"):
                return True
            self._reset_socket()
            if delay:
                time.sleep(delay)
        return False


__all__ = ["MesenBridge"]
