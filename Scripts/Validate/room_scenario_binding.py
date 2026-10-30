"""Fail-closed admission for an explicitly owned room-scenario session.

No Mesen imports, discovery, socket connection, UI action or writes occur here.
The registry/status files are the existing mesen2_registry protocol. Process
identity follows the maintained minecart_stair_entry.py lstart/command check.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
from typing import Any
from xml.parsers.expat import ExpatError


def _path(value: str | Path, label: str) -> Path:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ValueError(f"Explicit {label} path is required")
    try:
        return Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Cannot resolve {label}: {exc}") from exc


def _digest(value: str, label: str, length: int = 64) -> str:
    if not isinstance(value, str) or not re.fullmatch(rf"[0-9a-fA-F]{{{length}}}", value):
        raise ValueError(f"Explicit {label} must be a {length}-digit hash")
    return value.lower()


def _hash_file(path: Path) -> tuple[str, str]:
    try:
        before = path.stat()
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"Not a regular file: {path}")
        sha256, sha1 = hashlib.sha256(), hashlib.sha1()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                sha256.update(block)
                sha1.update(block)
        after = path.stat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise ValueError(f"File changed during hashing: {path}")
        return sha256.hexdigest(), sha1.hexdigest()
    except OSError as exc:
        raise ValueError(f"Cannot hash {path}: {exc}") from exc


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate session field: {key}")
        result[key] = value
    return result


def _read_record(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file() or path.stat().st_size > 131072:
            raise ValueError(f"Invalid session metadata file: {path}")
        value = json.loads(path.read_text(), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read session metadata {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Session metadata must be an object: {path}")
    return value


def _pid(value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("Session PID must be a positive integer")
    return value


def _process_identity(pid: int) -> tuple[str, str]:
    """Read only the named process; never scan, signal or control a process."""
    values = []
    for field in ("lstart=", "command="):
        try:
            result = subprocess.run(
                ["/bin/ps", "-p", str(pid), "-o", field], capture_output=True,
                text=True, check=False, timeout=2,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError(f"Cannot inspect owned PID {pid}: {exc}") from exc
        if result.returncode != 0 or not result.stdout.strip():
            raise ValueError(f"Owned PID {pid} is not live")
        values.append(result.stdout.strip())
    return values[0], values[1]


def _socket_identity(path: Path) -> tuple[int, int, int]:
    try:
        info = path.stat()
    except OSError as exc:
        raise ValueError(f"Owned socket is unavailable: {exc}") from exc
    if not stat.S_ISSOCK(info.st_mode):
        raise ValueError("Explicit endpoint is not a Unix socket")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise ValueError("Explicit socket belongs to another OS user")
    return info.st_dev, info.st_ino, info.st_uid


def _protected(instance: Any, path: Path) -> bool:
    return (str(instance).casefold() == "oos-rc-play" or
            path.name.casefold() in {"mesen2-oos-rc-play.sock", "oos-rc-play.json"})


def _session(record_path: Path, endpoint: Path, owner: str):
    record = _read_record(record_path)
    if (not isinstance(record.get("instance"), str) or not record["instance"] or
            _protected(record["instance"], record_path) or
            _protected(record["instance"], endpoint)):
        raise ValueError("Missing instance or protected oos-rc-play session")
    if record.get("owner") != owner or record.get("active") is not True or record.get("alive") is not True:
        raise ValueError("Session must be active, alive and owned by the exact caller")
    if _path(record.get("socket"), "registry socket") != endpoint:
        raise ValueError("Explicit socket does not match the owned registry record")

    status_path = endpoint.with_suffix(".status")
    status = _read_record(status_path) if status_path.exists() else None
    if status is not None and "socketPath" in status:
        if _path(status["socketPath"], "status socket") != endpoint:
            raise ValueError("Status socketPath differs from the explicit endpoint")
    record_pid = _pid(record["pid"]) if record.get("pid") is not None else None
    status_pid = _pid(status.get("pid")) if status is not None else None
    if record_pid is None and status_pid is None:
        raise ValueError("Owned session has no registry or status PID")
    if record_pid is not None and status_pid is not None and record_pid != status_pid:
        raise ValueError("Registry and status PID differ")
    pid = record_pid if record_pid is not None else status_pid

    # Inspect only sibling coordination records, never discover/probe sockets.
    for sibling in record_path.parent.glob("*.json"):
        other = _read_record(sibling)
        if sibling.resolve() == record_path:
            continue
        protected = _protected(other.get("instance"), sibling)
        foreign_active = other.get("active") is True and other.get("owner") != owner
        if not (protected or foreign_active):
            continue
        other_socket = other.get("socket")
        other_pid = _pid(other["pid"]) if other.get("pid") is not None else None
        same_socket = False
        if other_socket:
            other_endpoint = Path(other_socket).expanduser().resolve()
            same_socket = other_endpoint == endpoint or (
                other_endpoint.exists() and endpoint.samefile(other_endpoint))
            other_status_path = other_endpoint.with_suffix(".status")
            if other_pid is None and other_status_path.exists():
                other_status = _read_record(other_status_path)
                if "socketPath" in other_status and _path(
                    other_status["socketPath"], "sibling status socket"
                ) != other_endpoint:
                    raise ValueError("Sibling status socketPath differs")
                other_pid = _pid(other_status.get("pid"))
        if same_socket or other_pid == pid:
            raise ValueError("Endpoint or PID aliases a protected/foreign session")
        if protected and other_pid is None:
            raise ValueError("Protected session has no resolvable PID")

    app = _path(record.get("app_path"), "session app_path")
    start, command = _process_identity(pid)
    declared_app = Path(record["app_path"]).expanduser().absolute()
    names = ("Mesen2", "Mesen", "Mesen2 OOS")  # Maintained launcher fallback.
    if app.is_dir():
        info_path = app / "Contents" / "Info.plist"
        if info_path.exists():
            try:
                if info_path.stat().st_size > 131072:
                    raise ValueError("Oversized app Info.plist")
                with info_path.open("rb") as stream:
                    info = plistlib.load(stream)
            except (OSError, plistlib.InvalidFileException, ExpatError) as exc:
                raise ValueError(f"Cannot read session app Info.plist: {exc}") from exc
            if not isinstance(info, dict):
                raise ValueError("App Info.plist must be a dictionary")
            name = info.get("CFBundleExecutable")
            if name is not None:
                if not isinstance(name, str) or not name or Path(name).name != name or name in {".", ".."}:
                    raise ValueError("Invalid app CFBundleExecutable")
                names = (name,)
    candidates = [declared_app] if app.is_file() else [
        declared_app / "Contents" / "MacOS" / name for name in names]
    matches = set()
    for candidate in candidates:
        if not candidate.is_file():
            continue
        resolved = candidate.resolve(strict=True)
        if any(command == str(path) or command.startswith(str(path) + " ")
               for path in (candidate, resolved)):
            matches.add(resolved)
    if not start or not command or len(matches) != 1:
        raise ValueError("Live process command does not match session app_path")
    executable = matches.pop()
    return pid, start, command, executable, _socket_identity(endpoint)


@dataclass(frozen=True)
class RoomScenarioBinding:
    rom_path: Path
    state_path: Path
    socket_path: str
    session_record: Path
    owner: str
    pid: int
    process_identity: str
    rom_sha1: str
    rom_sha256: str
    state_sha256: str
    app_path: Path
    _start: str
    _command: str
    _socket_token: tuple[int, int, int]

    @classmethod
    def create(cls, rom, expected_rom_sha256, state, expected_state_sha256,
               socket_path, session_record, owner):
        rom_hash = _digest(expected_rom_sha256, "ROM SHA256")
        state_hash = _digest(expected_state_sha256, "state SHA256")
        if not isinstance(owner, str) or not owner or owner.strip() != owner:
            raise ValueError("Explicit exact session owner is required")
        if not isinstance(socket_path, (str, Path)) or not str(socket_path).startswith("/"):
            raise ValueError("Explicit absolute Unix socket path is required")
        endpoint = _path(socket_path, "socket")
        rom_path, state_path = _path(rom, "ROM"), _path(state, "state")
        record_path = _path(session_record, "session record")
        if rom_path == state_path or rom_path.samefile(state_path):
            raise ValueError("ROM and state must be different files")
        actual_rom, sha1 = _hash_file(rom_path)
        actual_state, _ = _hash_file(state_path)
        if actual_rom != rom_hash or actual_state != state_hash:
            raise ValueError("Local ROM or state hash mismatch")
        pid, start, command, app, token = _session(record_path, endpoint, owner)
        binding = cls(rom_path, state_path, str(endpoint), record_path, owner, pid,
                      start + "\n" + command, sha1, rom_hash, state_hash, app,
                      start, command, token)
        binding.verify_local()
        return binding

    def verify_local(self) -> None:
        actual_rom, sha1 = _hash_file(self.rom_path)
        actual_state, _ = _hash_file(self.state_path)
        if (actual_rom, sha1, actual_state) != (self.rom_sha256, self.rom_sha1, self.state_sha256):
            raise ValueError("Local ROM or state changed after admission")
        pid, start, command, app, token = _session(
            self.session_record, Path(self.socket_path), self.owner)
        if (pid, start, command, app, token) != (
            self.pid, self._start, self._command, self.app_path, self._socket_token
        ):
            raise ValueError("Owned process, application or socket identity changed")

    def verify_remote(self, bridge) -> None:
        self.verify_local()
        # The injected bridge's only permitted operation is ROMINFO.
        try:
            info = bridge.get_rom_info()
        except Exception as exc:
            raise ValueError(f"ROMINFO identity query failed: {exc}") from exc
        if not isinstance(info, dict):
            raise ValueError("ROMINFO did not return an identity object")
        remote_sha1 = _digest(info.get("sha1"), "remote ROM SHA1", 40)
        if remote_sha1 != self.rom_sha1:
            raise ValueError("Remote ROM hash differs from the admitted local ROM")
        self.verify_local()
