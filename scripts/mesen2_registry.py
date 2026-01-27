#!/usr/bin/env python3
"""Mesen2 instance registry for multi-agent coordination."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# Allow imports from scripts/mesen2_client_lib
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from mesen2_client_lib.bridge import MesenBridge  # type: ignore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _age_seconds(raw: str | None) -> int | None:
    dt = _parse_iso(raw)
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))


def _registry_dir() -> Path:
    override = os.getenv("MESEN2_REGISTRY_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return (REPO_ROOT / ".context" / "scratchpad" / "mesen2" / "instances").resolve()


def _ensure_dir() -> Path:
    path = _registry_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _record_path(instance: str) -> Path:
    return _ensure_dir() / f"{instance}.json"


def _load_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _save_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def _parse_pid_from_socket(socket_path: str) -> int | None:
    name = Path(socket_path).name
    if not name.startswith("mesen2-") or not name.endswith(".sock"):
        return None
    try:
        return int(name.replace("mesen2-", "").replace(".sock", ""))
    except ValueError:
        return None


def _check_socket_health(bridge: MesenBridge) -> tuple[bool, dict[str, Any]]:
    if hasattr(bridge, "check_health"):
        info = bridge.check_health()
        return bool(info.get("ok")), info
    try:
        return bool(bridge.is_connected()), {"error": ""}
    except Exception as exc:
        return False, {"error": str(exc)}


def _socket_details(socket_path: str) -> dict[str, Any]:
    bridge = MesenBridge(socket_path)
    alive, health = _check_socket_health(bridge)
    entry: dict[str, Any] = {
        "socket": socket_path,
        "pid": _parse_pid_from_socket(socket_path),
        "alive": alive,
    }
    if not alive:
        entry["error"] = health.get("error")
        return entry
    rominfo: dict[str, Any] = {}
    state: dict[str, Any] = {}
    error = ""
    try:
        rominfo = bridge.send_command("ROMINFO")
    except Exception as exc:
        error = str(exc)
    try:
        state = bridge.get_state().get("data", {})
    except Exception as exc:
        if not error:
            error = str(exc)
    data = rominfo.get("data", {}) if rominfo.get("success") else {}
    entry.update({
        "rom_filename": data.get("filename"),
        "rom_crc32": data.get("crc32"),
        "rom_sha1": data.get("sha1"),
        "frame": state.get("frame"),
        "paused": state.get("paused"),
        "running": state.get("running"),
        "error": error,
    })
    return entry


def _confirm(prompt: str) -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        return input(prompt).strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def _scan_sockets() -> list[dict[str, Any]]:
    sockets = sorted(Path("/tmp").glob("mesen2-*.sock"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [_socket_details(str(sock)) for sock in sockets]


def _mark_records_pruned(removed: list[str]) -> int:
    if not removed:
        return 0
    count = 0
    for path in sorted(_ensure_dir().glob("*.json")):
        record = _load_record(path)
        if record.get("socket") in removed:
            record["alive"] = False
            record["socket_pruned_at"] = _now_iso()
            _save_record(path, record)
            count += 1
    return count


def cmd_prune(args) -> None:
    scans = _scan_sockets()
    removed: list[str] = []
    errors: list[dict[str, str]] = []
    for entry in scans:
        if entry.get("alive"):
            continue
        socket_path = entry.get("socket")
        if not socket_path:
            continue
        path = Path(socket_path)
        if not path.exists():
            continue
        if args.dry_run:
            removed.append(socket_path)
            continue
        try:
            path.unlink()
            removed.append(socket_path)
        except Exception as exc:
            errors.append({"socket": socket_path, "error": str(exc)})

    updated = _mark_records_pruned(removed)
    if args.json:
        print(json.dumps({"removed": removed, "errors": errors, "records_updated": updated}, indent=2))
        return
    if not removed:
        print("No dead sockets to prune.")
        return
    for sock in removed:
        print(f"Pruned: {sock}")
    if errors:
        for err in errors:
            print(f"Failed: {err.get('socket')} ({err.get('error')})")
    if updated:
        print(f"Updated {updated} registry record(s).")


def _choose_socket(args) -> tuple[str, dict[str, Any]]:
    if args.socket:
        return args.socket, _socket_details(args.socket)
    if args.pid:
        socket_path = f"/tmp/mesen2-{args.pid}.sock"
        if not Path(socket_path).exists():
            raise SystemExit(f"Socket not found for pid {args.pid}: {socket_path}")
        return socket_path, _socket_details(socket_path)

    scans = _scan_sockets()
    if args.rom:
        target = Path(args.rom).name
        matches = [s for s in scans if s.get("rom_filename") == target and s.get("alive")]
    else:
        matches = [s for s in scans if s.get("alive")]

    if not matches:
        raise SystemExit("No matching live Mesen2 socket found.")

    return matches[0]["socket"], matches[0]


def cmd_scan(args) -> None:
    data = _scan_sockets()
    if args.json:
        print(json.dumps(data, indent=2))
        return
    if not data:
        print("No sockets found.")
        return
    for entry in data:
        status = "alive" if entry.get("alive") else "dead"
        rom = entry.get("rom_filename") or "unknown"
        print(f"{entry.get('socket')} pid={entry.get('pid')} {status} rom={rom} frame={entry.get('frame')}")


def cmd_list(args) -> None:
    records = []
    for path in sorted(_ensure_dir().glob("*.json")):
        records.append(_load_record(path))
    if args.json:
        print(json.dumps(records, indent=2))
        return
    if not records:
        print("No registry entries.")
        return
    for rec in records:
        instance = rec.get("instance", "unknown")
        owner = rec.get("owner", "unknown")
        active = rec.get("active", False)
        socket = rec.get("socket", "unknown")
        rom = rec.get("rom_filename") or rec.get("rom") or "unknown"
        last_seen = rec.get("last_seen", "unknown")
        active_str = "yes" if active else "no"
        print(f"{instance} owner={owner} active={active_str} socket={socket} rom={rom} last_seen={last_seen}")


def cmd_status(args) -> None:
    records: list[dict[str, Any]] = []
    for path in sorted(_ensure_dir().glob("*.json")):
        rec = _load_record(path)
        if args.instance and rec.get("instance") != args.instance:
            continue
        records.append(rec)

    stale_seconds = args.stale_seconds
    updated_records = []

    for rec in records:
        socket = rec.get("socket")
        if args.refresh and socket:
            details = _socket_details(socket)
            rec.update(details)
            if details.get("alive"):
                rec["last_seen"] = _now_iso()
            _save_record(_record_path(rec.get("instance", "unknown")), rec)
        age_s = _age_seconds(rec.get("last_seen") or rec.get("created_at"))
        stale = None if age_s is None else age_s > stale_seconds
        updated_records.append({
            **rec,
            "age_seconds": age_s,
            "stale": stale,
        })

    if args.json:
        print(json.dumps(updated_records, indent=2))
        return

    if not updated_records:
        print("No registry entries.")
        return

    for rec in updated_records:
        instance = rec.get("instance", "unknown")
        owner = rec.get("owner", "unknown")
        active = rec.get("active", False)
        socket = rec.get("socket", "unknown")
        alive = rec.get("alive", "unknown")
        age = rec.get("age_seconds")
        stale = rec.get("stale")
        rom = rec.get("rom_filename") or rec.get("rom") or "unknown"
        age_str = "unknown" if age is None else str(age)
        stale_str = "unknown" if stale is None else ("yes" if stale else "no")
        active_str = "yes" if active else "no"
        print(f"{instance} owner={owner} active={active_str} alive={alive} age_s={age_str} stale={stale_str} socket={socket} rom={rom}")


def cmd_claim(args) -> None:
    socket_path, scan_meta = _choose_socket(args)
    pid = _parse_pid_from_socket(socket_path)
    if not scan_meta.get("alive", True) and not args.allow_dead:
        raise SystemExit(
            f"Socket not responding: {socket_path} (use --allow-dead to override)"
        )

    record_path = _record_path(args.instance)
    record = _load_record(record_path)
    record.setdefault("created_at", _now_iso())

    if record.get("alive") and record.get("owner") and record.get("owner") != args.owner and not args.force:
        raise SystemExit(
            f"Instance {args.instance} already claimed by {record.get('owner')} (use --force to override)"
        )

    if args.rom and scan_meta.get("rom_filename"):
        expected = Path(args.rom).name
        actual = scan_meta.get("rom_filename")
        if actual and expected != actual and not args.force:
            raise SystemExit(
                f"ROM mismatch for {args.instance}: expected {expected}, got {actual} (use --force to override)"
            )

    record.update({
        "instance": args.instance,
        "owner": args.owner,
        "socket": socket_path,
        "pid": pid,
        "rom": args.rom or record.get("rom"),
        "rom_filename": scan_meta.get("rom_filename") or record.get("rom_filename"),
        "rom_crc32": scan_meta.get("rom_crc32") or record.get("rom_crc32"),
        "rom_sha1": scan_meta.get("rom_sha1") or record.get("rom_sha1"),
        "bridge": args.bridge or record.get("bridge"),
        "note": args.note or record.get("note"),
        "source": args.source or record.get("source"),
        "app_name": args.app_name or record.get("app_name"),
        "app_path": args.app_path or record.get("app_path"),
        "last_seen": _now_iso(),
        "alive": scan_meta.get("alive", True),
    })
    if args.active:
        if not record.get("active"):
            record["active_since"] = _now_iso()
        record["active"] = True

    _save_record(record_path, record)
    print(f"Claimed {args.instance}: owner={args.owner} socket={socket_path}")


def cmd_release(args) -> None:
    record_path = _record_path(args.instance)
    if not record_path.exists():
        raise SystemExit(f"Instance not found: {args.instance}")
    record = _load_record(record_path)
    record["released_at"] = _now_iso()
    record["owner"] = args.owner or record.get("owner")
    _save_record(record_path, record)
    print(f"Released {args.instance}")


def cmd_activate(args) -> None:
    record_path = _record_path(args.instance)
    if not record_path.exists():
        raise SystemExit(f"Instance not found: {args.instance}")
    record = _load_record(record_path)
    if not record.get("active"):
        record["active_since"] = _now_iso()
    record["active"] = True
    if args.source:
        record["source"] = args.source
    _save_record(record_path, record)
    print(f"Activated {args.instance}")


def cmd_deactivate(args) -> None:
    record_path = _record_path(args.instance)
    if not record_path.exists():
        raise SystemExit(f"Instance not found: {args.instance}")
    record = _load_record(record_path)
    record["active"] = False
    record["inactive_since"] = _now_iso()
    _save_record(record_path, record)
    print(f"Deactivated {args.instance}")


def cmd_heartbeat(args) -> None:
    record_path = _record_path(args.instance)
    if not record_path.exists():
        raise SystemExit(f"Instance not found: {args.instance}")
    record = _load_record(record_path)
    record["last_seen"] = _now_iso()
    if record.get("socket"):
        bridge = MesenBridge(record["socket"])
        if hasattr(bridge, "check_health"):
            record["alive"] = bool(bridge.check_health().get("ok"))
        else:
            record["alive"] = bridge.is_connected()
    _save_record(record_path, record)
    print(f"Heartbeat {args.instance}: alive={record.get('alive')}")


def cmd_close(args) -> None:
    record_path = _record_path(args.instance)
    if not record_path.exists():
        raise SystemExit(f"Instance not found: {args.instance}")
    record = _load_record(record_path)
    if args.force:
        print("Note: --force only extends the graceful-quit wait; no kill signals are sent.")
    if record.get("active") and not args.force:
        warning = f"Instance {args.instance} is marked active (owner={record.get('owner')})."
        if args.confirm:
            if not _confirm(f"{warning} Close anyway? [y/N]: "):
                raise SystemExit("Close aborted.")
        else:
            raise SystemExit(f"{warning} Use --force to close or --confirm for a prompt.")
    pid = record.get("pid")
    if not pid:
        socket = record.get("socket")
        if socket:
            pid = _parse_pid_from_socket(socket)
    if not pid:
        raise SystemExit(f"No PID available for {args.instance}")

    def _pid_alive(pid_value: int) -> bool:
        try:
            os.kill(pid_value, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    if not _pid_alive(int(pid)):
        record["alive"] = False
        _save_record(record_path, record)
        print(f"Closed {args.instance} (pid={pid})")
        return

    app_name = record.get("app_name") or "Mesen2 OOS"
    if sys.platform != "darwin":
        raise SystemExit("Graceful close is only supported on macOS. Close the app manually.")
    osascript = shutil.which("osascript")
    if not osascript:
        raise SystemExit("osascript not available; close the app manually.")

    subprocess.run([osascript, "-e", f'tell application \"{app_name}\" to quit'], check=False)
    wait_loops = 40 if args.force else 20
    for _ in range(wait_loops):
        if not _pid_alive(int(pid)):
            record["closed_at"] = _now_iso()
            record["closed_by"] = args.owner or record.get("owner")
            record["active"] = False
            record["alive"] = False
            _save_record(record_path, record)
            print(f"Closed {args.instance} (pid={pid})")
            return
        time.sleep(0.1)

    raise SystemExit("App did not exit cleanly. Close it manually.")


def cmd_resolve(args) -> None:
    record_path = _record_path(args.instance)
    if not record_path.exists():
        raise SystemExit(f"Instance not found: {args.instance}")
    record = _load_record(record_path)
    socket = record.get("socket")
    if not socket:
        raise SystemExit(f"No socket recorded for {args.instance}")
    if args.json:
        print(json.dumps({"instance": args.instance, "socket": socket}, indent=2))
        return
    if args.export:
        print(f"export MESEN2_INSTANCE={args.instance}")
        print(f"export MESEN2_SOCKET_PATH={socket}")
        return
    print(socket)


def cmd_who(args) -> None:
    socket_path, _ = _choose_socket(args)
    records = []
    for path in sorted(_ensure_dir().glob("*.json")):
        record = _load_record(path)
        if record.get("socket") == socket_path:
            records.append(record)
    if args.json:
        print(json.dumps(records, indent=2))
        return
    if not records:
        print(f"Socket {socket_path} is unclaimed.")
        return
    for record in records:
        print(f"{record.get('instance')} owner={record.get('owner')} socket={socket_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mesen2 instance registry")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_cmd = sub.add_parser("scan", help="Scan live Mesen2 sockets")
    scan_cmd.add_argument("--json", action="store_true")
    scan_cmd.set_defaults(func=cmd_scan)

    list_cmd = sub.add_parser("list", help="List registry entries")
    list_cmd.add_argument("--json", action="store_true")
    list_cmd.set_defaults(func=cmd_list)

    status_cmd = sub.add_parser("status", help="Show registry status with staleness info")
    status_cmd.add_argument("--instance")
    status_cmd.add_argument("--stale-seconds", type=int, default=600)
    status_cmd.add_argument("--refresh", action="store_true")
    status_cmd.add_argument("--json", action="store_true")
    status_cmd.set_defaults(func=cmd_status)

    claim_cmd = sub.add_parser("claim", help="Claim an instance")
    claim_cmd.add_argument("--instance", required=True)
    claim_cmd.add_argument("--owner", required=True)
    claim_cmd.add_argument("--socket")
    claim_cmd.add_argument("--pid")
    claim_cmd.add_argument("--rom")
    claim_cmd.add_argument("--bridge")
    claim_cmd.add_argument("--note")
    claim_cmd.add_argument("--source")
    claim_cmd.add_argument("--app-name")
    claim_cmd.add_argument("--app-path")
    claim_cmd.add_argument("--active", action="store_true")
    claim_cmd.add_argument("--force", action="store_true")
    claim_cmd.add_argument("--allow-dead", action="store_true")
    claim_cmd.set_defaults(func=cmd_claim)

    release_cmd = sub.add_parser("release", help="Release an instance")
    release_cmd.add_argument("--instance", required=True)
    release_cmd.add_argument("--owner")
    release_cmd.set_defaults(func=cmd_release)

    activate_cmd = sub.add_parser("activate", help="Mark instance as active")
    activate_cmd.add_argument("--instance", required=True)
    activate_cmd.add_argument("--source")
    activate_cmd.set_defaults(func=cmd_activate)

    deactivate_cmd = sub.add_parser("deactivate", help="Mark instance as inactive")
    deactivate_cmd.add_argument("--instance", required=True)
    deactivate_cmd.set_defaults(func=cmd_deactivate)

    heartbeat_cmd = sub.add_parser("heartbeat", help="Update last_seen for instance")
    heartbeat_cmd.add_argument("--instance", required=True)
    heartbeat_cmd.set_defaults(func=cmd_heartbeat)

    close_cmd = sub.add_parser("close", help="Close instance via graceful app quit")
    close_cmd.add_argument("--instance", required=True)
    close_cmd.add_argument("--owner")
    close_cmd.add_argument("--force", action="store_true")
    close_cmd.add_argument("--confirm", action="store_true")
    close_cmd.set_defaults(func=cmd_close)

    resolve_cmd = sub.add_parser("resolve", help="Resolve socket for instance")
    resolve_cmd.add_argument("--instance", required=True)
    resolve_cmd.add_argument("--export", action="store_true")
    resolve_cmd.add_argument("--json", action="store_true")
    resolve_cmd.set_defaults(func=cmd_resolve)

    prune_cmd = sub.add_parser("prune", help="Remove dead socket files")
    prune_cmd.add_argument("--dry-run", action="store_true")
    prune_cmd.add_argument("--json", action="store_true")
    prune_cmd.set_defaults(func=cmd_prune)

    who_cmd = sub.add_parser("who", help="Show owner for socket/pid")
    who_cmd.add_argument("--socket")
    who_cmd.add_argument("--pid")
    who_cmd.add_argument("--rom")
    who_cmd.add_argument("--json", action="store_true")
    who_cmd.set_defaults(func=cmd_who)

    args = parser.parse_args()
    if args.command in {"claim", "who"} and args.pid is not None:
        try:
            args.pid = int(args.pid)
        except ValueError:
            raise SystemExit(f"Invalid pid: {args.pid}")

    args.func(args)


if __name__ == "__main__":
    main()
