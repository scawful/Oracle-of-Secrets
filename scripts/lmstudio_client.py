#!/usr/bin/env python3
"""
LM Studio helper for loading models and calling the local API.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "Docs" / "Tooling" / "lmstudio_models.json"


def _find_lms() -> str:
    lms = shutil.which("lms")
    if not lms:
        raise SystemExit("lms not found in PATH. Install LM Studio CLI.")
    return lms


def _json_from_output(output: str) -> Any:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("{") or line.startswith("["):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    raise ValueError("No JSON payload found in output")


def run_lms(args: list[str], host: str | None = None, port: int | None = None, instance: bool = True) -> str:
    cmd = [_find_lms(), *args]
    if instance:
        if host:
            cmd.extend(["--host", host])
        if port:
            cmd.extend(["--port", str(port)])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "lms command failed")
    return result.stdout


def load_config(path: Path | None) -> dict:
    if path and path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def resolve_model(
    model: str | None = None,
    expert: str | None = None,
    config_path: Path | None = None,
    host: str | None = None,
    port: int | None = None,
) -> tuple[str | None, str | None, str, int]:
    cfg = load_config(config_path or DEFAULT_CONFIG)
    defaults = cfg.get("defaults", {}) if isinstance(cfg, dict) else {}
    host = host or defaults.get("host") or "127.0.0.1"
    port = port or int(defaults.get("port") or 1234)

    if model:
        return model, None, host, port

    if expert:
        entry = (cfg.get("experts") or {}).get(expert)
        if isinstance(entry, str):
            return entry, None, host, port
        if isinstance(entry, dict):
            return entry.get("model") or entry.get("name"), entry.get("identifier"), host, port

    default_model = cfg.get("default_model") or cfg.get("model")
    default_id = cfg.get("default_identifier")
    return default_model, default_id, host, port


def server_status() -> dict:
    output = run_lms(["server", "status", "--json"], instance=False)
    return _json_from_output(output)


def ensure_server() -> None:
    try:
        status = server_status()
        if status.get("running"):
            return
    except Exception:
        pass
    run_lms(["server", "start"], instance=False)


def list_models(host: str | None = None, port: int | None = None) -> list[dict]:
    output = run_lms(["ls", "--json"], host=host, port=port)
    data = _json_from_output(output)
    return data if isinstance(data, list) else []


def list_loaded(host: str | None = None, port: int | None = None) -> list[dict]:
    output = run_lms(["ps", "--json"], host=host, port=port)
    data = _json_from_output(output)
    return data if isinstance(data, list) else []


def ensure_model_loaded(
    model: str,
    identifier: str | None = None,
    host: str | None = None,
    port: int | None = None,
    context_length: int | None = None,
    gpu: str | None = None,
    ttl: int | None = None,
) -> None:
    loaded = list_loaded(host=host, port=port)
    for entry in loaded:
        if identifier and entry.get("identifier") == identifier:
            return
        for key in ("modelKey", "modelPath", "name", "model", "id"):
            val = entry.get(key)
            if isinstance(val, str) and model in val:
                return

    args = ["load", model, "--yes"]
    if identifier:
        args.extend(["--identifier", identifier])
    if context_length:
        args.extend(["--context-length", str(context_length)])
    if gpu:
        args.extend(["--gpu", gpu])
    if ttl:
        args.extend(["--ttl", str(ttl)])
    run_lms(args, host=host, port=port)


def chat_completion(
    prompt: str,
    model: str | None,
    host: str = "127.0.0.1",
    port: int = 1234,
    temperature: float = 0.2,
    max_tokens: int = 512,
    system: str | None = None,
) -> str:
    if not model:
        raise SystemExit("No model specified for LM Studio chat completion.")
    url = f"http://{host}:{port}/v1/chat/completions"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return message.get("content") or ""


def cmd_status(args: argparse.Namespace) -> int:
    ensure_server()
    status = server_status()
    loaded = list_loaded(host=args.host, port=args.port)
    print(json.dumps({"server": status, "loaded": loaded}, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    models = list_models(host=args.host, port=args.port)
    print(json.dumps(models, indent=2))
    return 0


def cmd_ps(args: argparse.Namespace) -> int:
    loaded = list_loaded(host=args.host, port=args.port)
    print(json.dumps(loaded, indent=2))
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    ensure_server()
    ensure_model_loaded(
        model=args.model,
        identifier=args.identifier,
        host=args.host,
        port=args.port,
        context_length=args.context_length,
        gpu=args.gpu,
        ttl=args.ttl,
    )
    return 0


def cmd_ensure(args: argparse.Namespace) -> int:
    ensure_server()
    model, identifier, host, port = resolve_model(
        model=args.model,
        expert=args.expert,
        config_path=Path(args.config) if args.config else None,
        host=args.host,
        port=args.port,
    )
    if not model:
        raise SystemExit("No model resolved; specify --model or config default.")
    ensure_model_loaded(
        model=model,
        identifier=identifier,
        host=host,
        port=port,
        context_length=args.context_length,
        gpu=args.gpu,
        ttl=args.ttl,
    )
    print(json.dumps({"model": model, "identifier": identifier, "host": host, "port": port}))
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    ensure_server()
    model, identifier, host, port = resolve_model(
        model=args.model,
        expert=args.expert,
        config_path=Path(args.config) if args.config else None,
        host=args.host,
        port=args.port,
    )
    if args.ensure and model:
        ensure_model_loaded(
            model=model,
            identifier=identifier,
            host=host,
            port=port,
            context_length=args.context_length,
            gpu=args.gpu,
            ttl=args.ttl,
        )
    prompt = args.prompt or sys.stdin.read()
    response = chat_completion(
        prompt,
        model=identifier or model,
        host=host,
        port=port,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        system=args.system,
    )
    print(response)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LM Studio CLI helper")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = parser.add_subparsers(dest="cmd")

    status = sub.add_parser("status", help="Show LM Studio server + loaded models")
    status.set_defaults(func=cmd_status)

    ls = sub.add_parser("list", help="List downloaded models")
    ls.set_defaults(func=cmd_list)

    ps = sub.add_parser("ps", help="List loaded models")
    ps.set_defaults(func=cmd_ps)

    load = sub.add_parser("load", help="Load a model (no config lookup)")
    load.add_argument("model")
    load.add_argument("--identifier")
    load.add_argument("--context-length", type=int, default=None)
    load.add_argument("--gpu")
    load.add_argument("--ttl", type=int, default=None)
    load.set_defaults(func=cmd_load)

    ensure = sub.add_parser("ensure", help="Resolve model (config/expert) and load")
    ensure.add_argument("--model")
    ensure.add_argument("--expert")
    ensure.add_argument("--context-length", type=int, default=None)
    ensure.add_argument("--gpu")
    ensure.add_argument("--ttl", type=int, default=None)
    ensure.set_defaults(func=cmd_ensure)

    chat = sub.add_parser("chat", help="Send a prompt to LM Studio API")
    chat.add_argument("--model")
    chat.add_argument("--expert")
    chat.add_argument("--ensure", action="store_true")
    chat.add_argument("--prompt")
    chat.add_argument("--system", default=None)
    chat.add_argument("--temperature", type=float, default=0.2)
    chat.add_argument("--max-tokens", type=int, default=512)
    chat.add_argument("--context-length", type=int, default=None)
    chat.add_argument("--gpu")
    chat.add_argument("--ttl", type=int, default=None)
    chat.set_defaults(func=cmd_chat)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
