#!/usr/bin/env python3
"""Run current-state smoke only against an explicitly selected, matching ROM.

Exit 0: requested checks passed. Normal mode requires the suite plus both
identity checks to pass. Exit 1: failure/refusal.
Exit 2: emulator/identity API unavailable before the suite started.

The operator must provide an owned emulator already running the required smoke
scenario. This helper never discovers, launches, loads, resets, or resumes an
emulator. --skip-load keeps the existing suite's scenario preconditions; this is
not proof of boot or complete-route acceptance. The suite still sends gameplay
input and captures screenshots on the selected instance.
The smoke manifest must list existing definitions. Exec steps take the ROM
through the {rom} placeholder (with {sym}/{hooks} beside it), which this helper
binds to --rom; OOS_TEST_REQUIRE_ARTIFACTS=1 makes a missing build output fail
instead of skip. Any literal ROM argument must still select --rom.

--verify-only performs the same protected-instance and ROM-identity preflight
without starting the suite. Its receipt has scope identity_only; it does not
claim smoke coverage or issue any reset/load command.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
IDENTITY_KEYS = {
    "name", "instance", "instanceName", "instance_name", "profile", "profilePath",
    "path", "rom", "romPath", "rom_path", "romName", "filename", "socketPath",
    "socket", "statusPath",
}


class SmokeError(Exception):
    def __init__(self, message: str, *, unavailable: bool = False):
        super().__init__(message)
        self.unavailable = unavailable


class ExactEndpoint:
    """Mesen newline-JSON protocol, with no discovery or reconnect fallback.

    Current SocketServer STATE supplies running/paused state; ROMINFO supplies
    filename and SHA1. This tiny read-only client avoids importing the regression
    runner (whose module initialization attaches a backend).
    """

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def request(self, command: str) -> dict[str, Any]:
        if command not in {"STATE", "ROMINFO"}:
            raise SmokeError(f"Unsupported preflight command: {command}")
        try:
            if self.endpoint.startswith("tcp://"):
                parsed = urlsplit(self.endpoint)
                conn = socket.create_connection((parsed.hostname, parsed.port), timeout=3)
            else:
                conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                conn.settimeout(3)
                try:
                    conn.connect(self.endpoint)
                except BaseException:
                    conn.close()
                    raise
            with conn:
                conn.sendall((json.dumps({"type": command}) + "\n").encode())
                with conn.makefile("rb") as stream:
                    raw = stream.readline(1024 * 1024 + 1)
        except OSError as exc:
            raise SmokeError(f"{command} unavailable at {self.endpoint}: {exc}", unavailable=True) from exc
        if not raw:
            raise SmokeError(f"{command} returned no response", unavailable=True)
        if len(raw) > 1024 * 1024:
            raise SmokeError(f"{command} response exceeds limit")
        try:
            response = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise SmokeError(f"{command} returned malformed JSON") from exc
        if not isinstance(response, dict):
            raise SmokeError(f"{command} returned a non-object response")
        return response


def normalize_endpoint(value: str) -> str:
    if not value.strip():
        raise SmokeError("--socket must name an explicit endpoint")
    if value.startswith(("tcp://", "tcp:")):
        endpoint = value if value.startswith("tcp://") else "tcp://" + value[4:]
        try:
            parsed = urlsplit(endpoint)
            valid = (parsed.hostname and parsed.port and not parsed.username and
                     not parsed.password and not parsed.path and not parsed.query and not parsed.fragment)
        except ValueError as exc:
            raise SmokeError(f"Invalid TCP endpoint: {value}") from exc
        if not valid:
            raise SmokeError(f"Invalid TCP endpoint: {value}")
        return endpoint
    return str(Path(value).expanduser().resolve())


def refuse_protected(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in IDENTITY_KEYS:
                refuse_protected(item)
    elif isinstance(value, str):
        name = value.lower()
        if "oos-rc-play" in name or Path(name).name in {"oos-play", "oos-play.sfc"}:
            raise SmokeError("Refusing protected user play instance/artifact oos-rc-play (oos-play.sfc)")


def read_status(endpoint: str) -> dict[str, Any]:
    # Only the supplied Unix endpoint's sidecar; never scan status files/sockets.
    if endpoint.startswith("tcp://"):
        return {}
    path = Path(endpoint[:-5] + ".status" if endpoint.endswith(".sock") else endpoint + ".status")
    try:
        content = path.read_text()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise SmokeError(f"Cannot read explicit endpoint status {path}: {exc}") from exc
    try:
        status = json.loads(content)
    except ValueError as exc:
        raise SmokeError(f"Malformed endpoint status: {path}") from exc
    if not isinstance(status, dict):
        raise SmokeError(f"Endpoint status is not an object: {path}")
    return status


def payload(client: Any, command: str) -> dict[str, Any]:
    response = client.request(command)
    if not isinstance(response, dict):
        raise SmokeError(f"{command} returned a non-object response")
    if response.get("success") is not True:
        raise SmokeError(f"{command} unavailable: {response.get('error', 'unsuccessful response')}", unavailable=True)
    data = response.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError as exc:
            raise SmokeError(f"{command} data is malformed JSON") from exc
    if not isinstance(data, dict):
        raise SmokeError(f"{command} data is not an object")
    refuse_protected(data)
    return data


def file_identity(path: Path) -> dict[str, str]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise SmokeError(f"Cannot read requested ROM {path}: {exc}") from exc
    return {"sha1": hashlib.sha1(data).hexdigest(), "sha256": hashlib.sha256(data).hexdigest()}


def compare_hash(value: Any, kind: str, expected: dict[str, str], source: str) -> None:
    if not isinstance(value, str) or value.lower() != expected[kind]:
        raise SmokeError(f"{source} {kind} does not match requested ROM: {value!r}")


def check_smoke_definitions(root: Path, rom: Path) -> dict:
    """Reject silently omitted tests and static lint against a different ROM."""
    manifest_path = root / "Tests/manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
        entries = manifest["suites"]["smoke"]["tests"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SmokeError(f"Cannot read smoke test list from {manifest_path}: {exc}") from exc
    if not isinstance(entries, list) or not entries:
        raise SmokeError("Smoke manifest must list at least one test definition")
    definitions, rom_inputs = [], set()
    for entry in entries:
        if not isinstance(entry, str) or not entry.strip():
            raise SmokeError(f"Invalid smoke test definition entry: {entry!r}")
        path = root / "Tests" / entry
        if not path.is_file():
            raise SmokeError(f"Smoke test definition is missing: {path}")
        try:
            definition = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise SmokeError(f"Cannot read smoke test definition {path}: {exc}") from exc
        if not isinstance(definition, dict) or not isinstance(definition.get("steps", []), list):
            raise SmokeError(f"Invalid smoke test definition: {path}")
        definitions.append(str(path.resolve()))
        for step in definition.get("steps", []):
            if not isinstance(step, dict) or step.get("type") != "exec":
                continue
            command = step.get("command", [])
            if isinstance(command, str):
                try:
                    command = shlex.split(command)
                except ValueError as exc:
                    raise SmokeError(f"Malformed smoke exec command in {path}: {exc}") from exc
            if not isinstance(command, list):
                raise SmokeError(f"Malformed smoke exec command in {path}")
            for argument in command:
                if not isinstance(argument, str) or not argument.lower().endswith((".sfc", ".smc")):
                    continue
                # Existing lint uses separate positional/--rom arguments; also
                # recognize --rom=PATH without evaluating variables or a shell.
                literal = argument.split("=", 1)[1] if argument.startswith("--rom=") else argument
                literal_path = (root / literal).resolve()
                if literal_path != rom.resolve():
                    raise SmokeError(
                        f"Smoke definition {path} uses literal ROM {literal_path}, not requested ROM {rom}; "
                        "parameterize the test definition before qualifying another build")
                rom_inputs.add(str(literal_path))
    return {"manifest": str(manifest_path.resolve()), "definitions": definitions,
            "literal_rom_inputs": sorted(rom_inputs)}


def check_identity(client: Any, endpoint: str, expected: dict[str, str], status_reader: Any) -> dict:
    status = status_reader(endpoint)
    refuse_protected(status)
    if status.get("socketPath") and normalize_endpoint(status["socketPath"]) != endpoint:
        raise SmokeError("Endpoint status names a different socket")
    state = payload(client, "STATE")
    if state.get("running") is not True:
        raise SmokeError("Selected emulator has no running ROM", unavailable=True)
    info = payload(client, "ROMINFO")
    hashes = [kind for kind in ("sha1", "sha256") if info.get(kind)]
    if not hashes:
        raise SmokeError("ROMINFO has no SHA1/SHA256 identity", unavailable=True)
    for kind in hashes:
        compare_hash(info[kind], kind, expected, "ROMINFO")
    for source, record in (("Status", status), ("STATE", state)):
        for kind in ("sha1", "sha256"):
            if record.get(kind):
                compare_hash(record[kind], kind, expected, source)
        if record.get("romHash"):
            value = record["romHash"]
            kind = "sha1" if len(str(value)) == 40 else "sha256"
            compare_hash(value, kind, expected, source)
    return {"state": state, "rom_info": info, "status": status}


def run_smoke(rom: Path, endpoint: str, *, root: Path = ROOT,
              client_factory: Any = ExactEndpoint, runner: Any = subprocess.run,
              status_reader: Any = read_status, environ: dict | None = None,
              verify_only: bool = False) -> tuple[int, dict]:
    receipt: dict[str, Any] = {
        "check": "rom-identity" if verify_only else "current-state-smoke",
        "scope": "identity_only" if verify_only else "current_state_smoke",
        "status": "failed", "suite_started": False,
    }
    try:
        endpoint = normalize_endpoint(endpoint)
        rom = rom.expanduser().resolve()
        receipt.update(rom=str(rom), socket=endpoint)
        refuse_protected(endpoint)
        refuse_protected(str(rom))
        expected = file_identity(rom)
        receipt["expected"] = expected
        if not verify_only:
            receipt["suite_definition"] = check_smoke_definitions(root, rom)
        client = client_factory(endpoint)
        receipt["preflight"] = check_identity(client, endpoint, expected, status_reader)
        if verify_only:
            if file_identity(rom) != expected:
                raise SmokeError("Requested ROM file changed during identity preflight")
            receipt["status"] = "passed"
            return 0, receipt
        command = ["bash", str(root / "Scripts/Validate/run_regression_tests.sh"),
                   "smoke", "--no-moe", "--fail-fast", "--skip-load", "--rom", str(rom)]
        env = dict(os.environ if environ is None else environ)
        env.update(MESEN2_SOCKET_PATH=endpoint, OOS_TEST_BACKEND="socket",
                   OOS_TEST_REQUIRE_EMULATOR="1", OOS_TEST_REQUIRE_ARTIFACTS="1",
                   MESEN_AUTO_FOCUS="0",
                   MESEN_AUTO_UNSTASH="0", MESEN_AUTO_STASH="0", MESEN_STASH_ON_FAIL="0",
                   MESEN2_HANDHELD="0")
        receipt["command"] = command
        receipt["suite_started"] = True
        try:
            result = runner(command, cwd=str(root), env=env, capture_output=True, text=True,
                            timeout=180, check=False)
            receipt.update(suite_returncode=result.returncode, suite_stdout=result.stdout,
                           suite_stderr=result.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            receipt["suite_error"] = str(exc)
            result = None
        # Even a failing suite must retain the final identity evidence.
        receipt["postflight"] = check_identity(client, endpoint, expected, status_reader)
        before_pid = receipt["preflight"]["status"].get("pid")
        after_pid = receipt["postflight"]["status"].get("pid")
        if before_pid is not None and after_pid is not None and before_pid != after_pid:
            raise SmokeError("Emulator process changed while smoke ran")
        if file_identity(rom) != expected:
            raise SmokeError("Requested ROM file changed while smoke ran")
        if result is None or result.returncode != 0:
            raise SmokeError("Smoke suite failed; see suite output/error")
        receipt["status"] = "passed"
        return 0, receipt
    except SmokeError as exc:
        unavailable = exc.unavailable and not receipt["suite_started"]
        receipt.update(status="unavailable" if unavailable else "failed", error=str(exc))
        return 2 if unavailable else 1, receipt


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise SmokeError(message)


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--socket", required=True, help="Explicit operator-owned Unix path or tcp://host:port")
    parser.add_argument("--verify-only", action="store_true", help="Check identity only; do not run smoke or reset")
    try:
        args = parser.parse_args(argv)
        code, receipt = run_smoke(args.rom, args.socket, verify_only=args.verify_only)
    except SmokeError as exc:
        code, receipt = 1, {"check": "current-state-smoke", "status": "failed", "error": str(exc)}
    print(json.dumps(receipt, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
