#!/usr/bin/env python3
"""Oracle Agent Gateway for Mesen2 + Oracle-of-Secrets tooling.

Provides a local HTTP server and CLI wrapper to trigger common actions from
Mesen2 menu items (state capture, yaze service control, docs, AFS warm).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error, request

DEFAULT_PORT = int(os.getenv("OOS_AGENT_GATEWAY_PORT", "8765"))


# ---- Path helpers ----

def _expand_home(path: str) -> Path:
    if path.startswith("~"):
        return Path(path.replace("~", str(Path.home()), 1)).expanduser()
    return Path(path).expanduser()


def _resolve_oos_root() -> Path | None:
    env_root = os.getenv("ORACLE_OF_SECRETS_ROOT") or os.getenv("OOS_ROOT")
    if env_root:
        candidate = _expand_home(env_root)
        if candidate.exists():
            return candidate

    default_root = Path.home() / "src" / "hobby" / "oracle-of-secrets"
    if default_root.exists():
        return default_root

    return None


def _resolve_docs_root() -> Path:
    return Path.home() / "src" / "docs"


def _resolve_afs_root() -> Path:
    return Path.home() / "src" / "lab" / "afs"


def _resolve_afs_scawful_root() -> Path:
    return Path.home() / "src" / "lab" / "afs-scawful"


def _resolve_models_root() -> Path:
    return Path.home() / "models"


def _resolve_context_root() -> Path:
    return Path.home() / ".context" / "projects" / "oracle-of-secrets"


def _resolve_scratchpad() -> Path:
    return _resolve_context_root() / "scratchpad"


def _resolve_default_rom(oos_root: Path) -> Path | None:
    roms_dir = oos_root / "Roms"
    if not roms_dir.exists():
        return None

    preferred = [
        "oos168x.sfc",
        "oos168.sfc",
        "oos169.sfc",
        "oos-patched.sfc",
        "Zelda_OracleOfSecrets.sfc",
    ]
    for name in preferred:
        candidate = roms_dir / name
        if candidate.exists():
            return candidate

    sfcs = sorted(roms_dir.glob("*.sfc"), key=lambda p: p.stat().st_mtime, reverse=True)
    return sfcs[0] if sfcs else None


def _resolve_tests_dir(oos_root: Path) -> Path:
    candidate = oos_root / "tests"
    if candidate.exists():
        return candidate
    candidate = oos_root / "Tests"
    if candidate.exists():
        return candidate
    return oos_root / "tests"


# ---- Process helpers ----

def _spawn(cmd: list[str], cwd: Path | None = None) -> dict[str, Any]:
    try:
        subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"ok": True, "cmd": cmd}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "cmd": cmd}


def _run(cmd: list[str], cwd: Path | None = None) -> dict[str, Any]:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return {
            "ok": result.returncode == 0,
            "cmd": cmd,
            "code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "cmd": cmd}


# ---- OS open helpers ----

def _open_path(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {"ok": False, "error": "Path not found", "path": str(path)}
        if sys.platform == "darwin":
            return _spawn(["open", str(path)])
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
            return {"ok": True, "path": str(path)}
        return _spawn(["xdg-open", str(path)])
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": str(path)}


def _open_url(url: str) -> dict[str, Any]:
    try:
        if sys.platform == "darwin":
            return _spawn(["open", url])
        if os.name == "nt":
            os.startfile(url)  # type: ignore[attr-defined]
            return {"ok": True, "url": url}
        return _spawn(["xdg-open", url])
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": url}


# ---- Actions ----

def action_capture_state(args: dict[str, Any]) -> dict[str, Any]:
    try:
        from mesen2_client_lib.client import OracleDebugClient
        from mesen2_client_lib.capture import capture_debug_snapshot
    except Exception as exc:
        return {"ok": False, "error": f"Import failed: {exc}"}

    client = OracleDebugClient()
    if not client.is_connected():
        return {"ok": False, "error": "Mesen2 socket not found (expected /tmp/mesen2-*.sock)"}

    scratchpad = _resolve_scratchpad()
    watch_profile = (args.get("watch_profile") or "overworld") if isinstance(args, dict) else "overworld"
    prefix = (args.get("prefix") or "mesen_capture") if isinstance(args, dict) else "mesen_capture"
    include_cpu = bool(args.get("include_cpu", True)) if isinstance(args, dict) else True
    include_rom = bool(args.get("include_rom", True)) if isinstance(args, dict) else True
    include_story = bool(args.get("include_story", True)) if isinstance(args, dict) else True
    include_watch = bool(args.get("include_watch", True)) if isinstance(args, dict) else True
    include_build = bool(args.get("include_build", True)) if isinstance(args, dict) else True
    include_screenshot = bool(args.get("screenshot", True)) if isinstance(args, dict) else True

    return capture_debug_snapshot(
        client,
        scratchpad,
        watch_profile=watch_profile,
        prefix=prefix,
        include_cpu=include_cpu,
        include_rom=include_rom,
        include_story=include_story,
        include_watch=include_watch,
        include_build=include_build,
        screenshot=include_screenshot,
    )


def action_open_scratchpad(_: dict[str, Any]) -> dict[str, Any]:
    scratchpad = _resolve_scratchpad()
    scratchpad.mkdir(parents=True, exist_ok=True)
    return _open_path(scratchpad)


def action_open_agent_handoff(_: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_scratchpad() / "agent_handoff.md"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Agent Handoff\n\n")
    return _open_path(path)


def action_open_model_catalog(_: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_docs_root() / "MODEL_CATALOG.md"
    return _open_path(path)


def action_open_integration_plan(_: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_docs_root() / "zelda-model-integration-plan.md"
    return _open_path(path)


def action_open_vscode_models(_: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_docs_root() / "vscode-local-models.md"
    return _open_path(path)


def action_open_models_dir(_: dict[str, Any]) -> dict[str, Any]:
    return _open_path(_resolve_models_root())


def action_open_state_library(_: dict[str, Any]) -> dict[str, Any]:
    oos_root = _resolve_oos_root()
    if not oos_root:
        return {"ok": False, "error": "Oracle-of-Secrets root not found"}
    path = oos_root / "Docs" / "Testing" / "save_state_library.json"
    return _open_path(path)


def action_open_tests_dir(_: dict[str, Any]) -> dict[str, Any]:
    oos_root = _resolve_oos_root()
    if not oos_root:
        return {"ok": False, "error": "Oracle-of-Secrets root not found"}
    return _open_path(_resolve_tests_dir(oos_root))


def action_build_rom(args: dict[str, Any]) -> dict[str, Any]:
    oos_root = _resolve_oos_root()
    if not oos_root:
        return {"ok": False, "error": "Oracle-of-Secrets root not found"}
    version = str(args.get("version", "168")) if isinstance(args, dict) else "168"
    script = oos_root / "scripts" / "build_rom.sh"
    if script.exists():
        cmd = ["bash", str(script), version]
        asar_bin = args.get("asar") if isinstance(args, dict) else None
        if asar_bin:
            cmd.append(str(asar_bin))
        return _spawn(cmd, cwd=oos_root)
    fallback = oos_root / "build.sh"
    if fallback.exists():
        return _spawn(["bash", str(fallback)], cwd=oos_root)
    return {"ok": False, "error": "build_rom.sh or build.sh not found"}


def action_export_symbols(args: dict[str, Any]) -> dict[str, Any]:
    oos_root = _resolve_oos_root()
    if not oos_root:
        return {"ok": False, "error": "Oracle-of-Secrets root not found"}
    script = oos_root / "scripts" / "export_symbols.py"
    if not script.exists():
        return {"ok": False, "error": "export_symbols.py not found"}
    cmd = [sys.executable, str(script)]
    if isinstance(args, dict):
        if args.get("sync", True):
            cmd.append("--sync")
        if args.get("filter"):
            cmd += ["--filter", str(args["filter"])]
        if args.get("format"):
            cmd += ["--format", str(args["format"])]
    else:
        cmd.append("--sync")
    return _spawn(cmd, cwd=oos_root)


def action_run_smoke_tests(_: dict[str, Any]) -> dict[str, Any]:
    oos_root = _resolve_oos_root()
    if not oos_root:
        return {"ok": False, "error": "Oracle-of-Secrets root not found"}
    script = oos_root / "scripts" / "test_runner.py"
    tests_dir = _resolve_tests_dir(oos_root)
    test_file = tests_dir / "overworld_basic.json"
    if not script.exists() or not test_file.exists():
        return {"ok": False, "error": "Smoke test not found"}
    return _spawn([sys.executable, str(script), str(test_file), "--verbose"], cwd=oos_root)


def action_run_test_suite(_: dict[str, Any]) -> dict[str, Any]:
    oos_root = _resolve_oos_root()
    if not oos_root:
        return {"ok": False, "error": "Oracle-of-Secrets root not found"}
    script = oos_root / "scripts" / "test_runner.py"
    tests_dir = _resolve_tests_dir(oos_root)
    tests = sorted(tests_dir.glob("*.json"))
    if not script.exists() or not tests:
        return {"ok": False, "error": "No tests found"}
    cmd = [sys.executable, str(script), *[str(p) for p in tests]]
    return _spawn(cmd, cwd=oos_root)


def action_health(_: dict[str, Any]) -> dict[str, Any]:
    status: dict[str, Any] = {}
    sockets = glob.glob("/tmp/mesen2-*.sock")
    status["mesen2_sockets"] = sockets

    try:
        from mesen2_client_lib.client import OracleDebugClient
        client = OracleDebugClient()
        status["mesen2_connected"] = client.is_connected()
    except Exception as exc:
        status["mesen2_connected"] = False
        status["mesen2_error"] = str(exc)

    if shutil.which("pgrep"):
        try:
            result = subprocess.run(
                ["pgrep", "-f", "yaze"],
                capture_output=True,
                text=True,
                check=False,
            )
            status["yaze_running"] = bool(result.stdout.strip())
        except Exception as exc:
            status["yaze_running"] = False
            status["yaze_error"] = str(exc)
    else:
        status["yaze_running"] = "unknown"

    oos_root = _resolve_oos_root()
    status["default_rom"] = str(_resolve_default_rom(oos_root)) if oos_root else None
    return {"ok": True, "status": status}

def action_open_afs_repo(_: dict[str, Any]) -> dict[str, Any]:
    return _open_path(_resolve_afs_root())


def action_open_afs_scawful_repo(_: dict[str, Any]) -> dict[str, Any]:
    return _open_path(_resolve_afs_scawful_root())


def action_open_chat_registry(_: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_afs_scawful_root() / "config" / "chat_registry.toml"
    return _open_path(path)


def action_afs_context_warm(_: dict[str, Any]) -> dict[str, Any]:
    afs_root = _resolve_afs_root()
    warm_script = afs_root / "scripts" / "afs-warm"
    if warm_script.exists():
        return _spawn([str(warm_script)], cwd=afs_root)

    if shutil.which("afs"):
        return _spawn(["afs", "agents", "run", "context-warm", "--", "--interval", "0"], cwd=afs_root)

    return {"ok": False, "error": "afs-warm script not found and afs not in PATH"}


def _yaze_allowed() -> bool:
    return os.getenv("ALLOW_YAZE") == "1"


def action_yaze_start(_: dict[str, Any]) -> dict[str, Any]:
    if not _yaze_allowed():
        return {"ok": False, "error": "YAZE is disabled for agents. Use Mesen2 OOS only."}
    oos_root = _resolve_oos_root()
    if not oos_root:
        return {"ok": False, "error": "Oracle-of-Secrets root not found"}
    script = oos_root / "scripts" / "yaze_service.sh"
    rom = _resolve_default_rom(oos_root)
    if not script.exists():
        return {"ok": False, "error": "yaze_service.sh not found"}
    if not rom:
        return {"ok": False, "error": "No ROM found in Roms/"}
    return _spawn([str(script), "start", "--rom", str(rom)], cwd=oos_root)


def action_yaze_stop(_: dict[str, Any]) -> dict[str, Any]:
    if not _yaze_allowed():
        return {"ok": False, "error": "YAZE is disabled for agents. Use Mesen2 OOS only."}
    oos_root = _resolve_oos_root()
    if not oos_root:
        return {"ok": False, "error": "Oracle-of-Secrets root not found"}
    script = oos_root / "scripts" / "yaze_service.sh"
    if not script.exists():
        return {"ok": False, "error": "yaze_service.sh not found"}
    return _spawn([str(script), "stop"], cwd=oos_root)


def action_yaze_gui_toggle(_: dict[str, Any]) -> dict[str, Any]:
    if not _yaze_allowed():
        return {"ok": False, "error": "YAZE is disabled for agents. Use Mesen2 OOS only."}
    oos_root = _resolve_oos_root()
    if not oos_root:
        return {"ok": False, "error": "Oracle-of-Secrets root not found"}
    script = oos_root / "scripts" / "yaze_service.sh"
    rom = _resolve_default_rom(oos_root)
    if not script.exists():
        return {"ok": False, "error": "yaze_service.sh not found"}
    if not rom:
        return {"ok": False, "error": "No ROM found in Roms/"}
    return _spawn([str(script), "gui-toggle", "--rom", str(rom)], cwd=oos_root)


def action_headless_workflow_start(_: dict[str, Any]) -> dict[str, Any]:
    if not _yaze_allowed():
        return {"ok": False, "error": "Headless YAZE workflow disabled for agents. Use Mesen2 OOS only."}
    oos_root = _resolve_oos_root()
    if not oos_root:
        return {"ok": False, "error": "Oracle-of-Secrets root not found"}
    script = oos_root / "scripts" / "agent_workflow_start.sh"
    rom = _resolve_default_rom(oos_root)
    if not script.exists():
        return {"ok": False, "error": "agent_workflow_start.sh not found"}
    if not rom:
        return {"ok": False, "error": "No ROM found in Roms/"}
    return _spawn([str(script), "--rom", str(rom), "--export-fast"], cwd=oos_root)


def action_headless_workflow_stop(_: dict[str, Any]) -> dict[str, Any]:
    oos_root = _resolve_oos_root()
    if not oos_root:
        return {"ok": False, "error": "Oracle-of-Secrets root not found"}
    script = oos_root / "scripts" / "agent_workflow_stop.sh"
    if not script.exists():
        return {"ok": False, "error": "agent_workflow_stop.sh not found"}
    return _spawn([str(script)], cwd=oos_root)


def action_start_llm_gateway(_: dict[str, Any]) -> dict[str, Any]:
    script = Path.home() / "src" / "lab" / "llama-harness" / "scripts" / "openai_gateway.py"
    if not script.exists():
        return {"ok": False, "error": "openai_gateway.py not found"}
    return _spawn([sys.executable, str(script)])


def action_open_llm_status(_: dict[str, Any]) -> dict[str, Any]:
    return _open_url("http://127.0.0.1:11440/status")


def _run_mesen2_cli(args: list[str]) -> dict[str, Any]:
    oos_root = _resolve_oos_root()
    if not oos_root:
        return {"ok": False, "error": "Oracle-of-Secrets root not found"}
    script = oos_root / "scripts" / "mesen2_client.py"
    if not script.exists():
        return {"ok": False, "error": "mesen2_client.py not found"}
    cmd = [sys.executable, str(script)] + args
    return _run(cmd, cwd=oos_root)


def action_check_day_night(_: dict[str, Any]) -> dict[str, Any]:
    return _run_mesen2_cli(["time", "--json"])


def action_check_zsow_status(_: dict[str, Any]) -> dict[str, Any]:
    return _run_mesen2_cli(["diagnostics", "--json"])


ACTIONS: dict[str, dict[str, Any]] = {
    "capture_state": {
        "fn": action_capture_state,
        "description": "Capture state + screenshot to .context scratchpad",
    },
    "open_scratchpad": {
        "fn": action_open_scratchpad,
        "description": "Open Oracle scratchpad folder",
    },
    "open_agent_handoff": {
        "fn": action_open_agent_handoff,
        "description": "Open agent_handoff.md",
    },
    "open_model_catalog": {
        "fn": action_open_model_catalog,
        "description": "Open MODEL_CATALOG.md",
    },
    "open_integration_plan": {
        "fn": action_open_integration_plan,
        "description": "Open zelda-model-integration-plan.md",
    },
    "open_vscode_models": {
        "fn": action_open_vscode_models,
        "description": "Open vscode-local-models.md",
    },
    "open_models_dir": {
        "fn": action_open_models_dir,
        "description": "Open ~/models",
    },
    "open_state_library": {
        "fn": action_open_state_library,
        "description": "Open save_state_library.json",
    },
    "open_tests_dir": {
        "fn": action_open_tests_dir,
        "description": "Open tests directory",
    },
    "build_rom": {
        "fn": action_build_rom,
        "description": "Build patched ROM via build_rom.sh",
    },
    "export_symbols": {
        "fn": action_export_symbols,
        "description": "Export symbols (sync to Mesen2)",
    },
    "run_smoke_tests": {
        "fn": action_run_smoke_tests,
        "description": "Run overworld_basic smoke test",
    },
    "run_test_suite": {
        "fn": action_run_test_suite,
        "description": "Run all JSON tests",
    },
    "health": {
        "fn": action_health,
        "description": "Check Mesen2/yaze health status",
    },
    "open_afs_repo": {
        "fn": action_open_afs_repo,
        "description": "Open AFS repo",
    },
    "open_afs_scawful_repo": {
        "fn": action_open_afs_scawful_repo,
        "description": "Open AFS-Scawful repo",
    },
    "open_chat_registry": {
        "fn": action_open_chat_registry,
        "description": "Open chat_registry.toml",
    },
    "afs_context_warm": {
        "fn": action_afs_context_warm,
        "description": "Warm AFS context",
    },
    "yaze_start": {
        "fn": action_yaze_start,
        "description": "Start yaze service (disabled unless ALLOW_YAZE=1)",
    },
    "yaze_stop": {
        "fn": action_yaze_stop,
        "description": "Stop yaze service (disabled unless ALLOW_YAZE=1)",
    },
    "yaze_gui_toggle": {
        "fn": action_yaze_gui_toggle,
        "description": "Toggle yaze GUI (disabled unless ALLOW_YAZE=1)",
    },
    "headless_workflow_start": {
        "fn": action_headless_workflow_start,
        "description": "Start agent workflow (headless, disabled unless ALLOW_YAZE=1)",
    },
    "headless_workflow_stop": {
        "fn": action_headless_workflow_stop,
        "description": "Stop agent workflow",
    },
    "start_llm_gateway": {
        "fn": action_start_llm_gateway,
        "description": "Start local OpenAI gateway",
    },
    "open_llm_status": {
        "fn": action_open_llm_status,
        "description": "Open local OpenAI gateway status",
    },
    "check_day_night": {
        "fn": action_check_day_night,
        "description": "Report day/night time system state",
    },
    "check_zsow_status": {
        "fn": action_check_zsow_status,
        "description": "Report ZSCustomOverworld/overworld diagnostic snapshot",
    },
}


def run_action(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    if name not in ACTIONS:
        return {"ok": False, "error": f"Unknown action: {name}"}
    fn = ACTIONS[name]["fn"]
    return fn(args or {})


# ---- HTTP server ----

class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "OracleAgentGateway/0.1"

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/status":
            self._send(200, {"ok": True, "uptime": time.time() - self.server.start_time})
            return
        if self.path == "/actions":
            payload = {k: v["description"] for k, v in ACTIONS.items()}
            self._send(200, {"ok": True, "actions": payload})
            return
        self._send(404, {"ok": False, "error": "Not found"})

    def do_POST(self) -> None:
        if self.path == "/action":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._send(400, {"ok": False, "error": "Invalid JSON"})
                return

            action = data.get("action")
            args = data.get("args") or {}
            if not action:
                self._send(400, {"ok": False, "error": "Missing action"})
                return

            result = run_action(action, args)
            self._send(200 if result.get("ok") else 500, result)
            return

        if self.path == "/shutdown":
            self._send(200, {"ok": True, "message": "Shutting down"})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        self._send(404, {"ok": False, "error": "Not found"})

    def log_message(self, format: str, *args: Any) -> None:
        # Silence default logging
        return


def serve(port: int) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), GatewayHandler)
    server.start_time = time.time()  # type: ignore[attr-defined]
    server.serve_forever()


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(url, data=data, headers=headers, method=method)
        with request.urlopen(req, timeout=2) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.URLError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Oracle Agent Gateway")
    sub = parser.add_subparsers(dest="cmd")

    serve_p = sub.add_parser("serve", help="Start HTTP gateway")
    serve_p.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve_p.add_argument("--daemon", action="store_true")

    stop_p = sub.add_parser("stop", help="Stop HTTP gateway")
    stop_p.add_argument("--port", type=int, default=DEFAULT_PORT)

    status_p = sub.add_parser("status", help="Gateway status")
    status_p.add_argument("--port", type=int, default=DEFAULT_PORT)

    action_p = sub.add_parser("action", help="Run a gateway action")
    action_p.add_argument("name")
    action_p.add_argument("--port", type=int, default=DEFAULT_PORT)
    action_p.add_argument("--json", action="store_true")
    action_p.add_argument("--no-local", action="store_true")

    list_p = sub.add_parser("list-actions", help="List available actions")
    list_p.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.cmd == "serve":
        if args.daemon:
            cmd = [sys.executable, str(Path(__file__).resolve()), "serve", "--port", str(args.port)]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        serve(args.port)
        return

    if args.cmd == "stop":
        url = f"http://127.0.0.1:{args.port}/shutdown"
        resp = request_json("POST", url, {})
        print(json.dumps(resp or {"ok": False, "error": "not running"}, indent=2))
        return

    if args.cmd == "status":
        url = f"http://127.0.0.1:{args.port}/status"
        resp = request_json("GET", url)
        print(json.dumps(resp or {"ok": False, "error": "not running"}, indent=2))
        return

    if args.cmd == "list-actions":
        actions = {k: v["description"] for k, v in ACTIONS.items()}
        if args.json:
            print(json.dumps(actions, indent=2))
        else:
            for name, desc in actions.items():
                print(f"{name}: {desc}")
        return

    if args.cmd == "action":
        url = f"http://127.0.0.1:{args.port}/action"
        payload = {"action": args.name, "args": {}}
        resp = request_json("POST", url, payload)
        if resp is None and not args.no_local:
            resp = run_action(args.name, {})
        if args.json:
            print(json.dumps(resp or {"ok": False}, indent=2))
        else:
            print(resp)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
