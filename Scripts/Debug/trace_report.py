#!/usr/bin/env python3
"""
Generate a symbol-mapped report from Mesen bridge write_trace.jsonl logs.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from symbols import SymbolResolver, parse_int

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_trace(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Trace not found: {path}")
    entries = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def format_addr(addr: int | None) -> str:
    if addr is None:
        return "unknown"
    return f"0x{addr:06X}"


def build_report(
    entries: list[dict],
    resolver: SymbolResolver,
    limit: int,
    state_log: list[dict] | None = None,
) -> str:
    if not entries and not state_log:
        return "No trace entries found."

    by_addr = defaultdict(list)
    for e in entries:
        addr = parse_int(e.get("addr"))
        if addr is None and isinstance(e.get("addr"), str):
            addr = parse_int(e.get("addr"))
        if addr is None:
            continue
        by_addr[addr].append(e)

    lines = []
    lines.append("# Trace Report")
    lines.append("")
    lines.append(f"Total entries: {len(entries)}")
    lines.append("")

    if entries:
        for addr in sorted(by_addr.keys()):
            items = by_addr[addr]
            last = items[-1]
            bank = parse_int(last.get("pb"))
            pc = parse_int(last.get("pc"))
            symbol = resolver.resolve(bank, pc) or "unknown"
            lines.append(f"## Address {format_addr(addr)}")
            lines.append(f"- Total writes: {len(items)}")
            lines.append(f"- Last write: frame {last.get('frame')} value {last.get('value')} writer {symbol} (PB={bank}, PC={pc})")

            counter = Counter()
            for e in items:
                bank = parse_int(e.get("pb"))
                pc = parse_int(e.get("pc"))
                counter[resolver.resolve(bank, pc) or "unknown"] += 1
            top = counter.most_common(limit)
            lines.append("- Top writers:")
            for name, count in top:
                lines.append(f"  - {name}: {count}")
            lines.append("")

    # Recent events
    if entries:
        lines.append("## Recent Writes")
        for e in entries[-limit:]:
            addr = parse_int(e.get("addr"))
            bank = parse_int(e.get("pb"))
            pc = parse_int(e.get("pc"))
            symbol = resolver.resolve(bank, pc) or "unknown"
            lines.append(
                f"- frame {e.get('frame')} addr {format_addr(addr)} value {e.get('value')} writer {symbol}"
            )

    if state_log:
        transitions = summarize_transitions(state_log, limit)
        if transitions:
            lines.append("")
            lines.append("## State Transitions (from log)")
            for row in transitions:
                lines.append(row)

    return "\n".join(lines)


def load_state_log(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"State log not found: {path}")
    text = path.read_text()
    lines = text.splitlines()
    entries: list[dict] = []
    buf: list[str] = []
    depth = 0
    in_obj = False
    for line in lines:
        if not line.strip() and not in_obj:
            continue
        if "{" in line:
            depth += line.count("{")
            in_obj = True
        if in_obj:
            buf.append(line)
        if "}" in line and in_obj:
            depth -= line.count("}")
            if depth <= 0:
                raw = "\n".join(buf).strip()
                buf = []
                in_obj = False
                depth = 0
                if not raw:
                    continue
                try:
                    entries.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
    return entries


def summarize_transitions(entries: list[dict], limit: int) -> list[str]:
    transitions = []
    prev = None
    for e in entries:
        key = (
            e.get("mode"),
            e.get("submode"),
            e.get("indoors"),
            e.get("roomId"),
            e.get("overworldArea"),
        )
        if key != prev:
            transitions.append(
                f"- frame {e.get('frame')} mode {e.get('mode')} sub {e.get('submode')} "
                f"indoors {e.get('indoors')} room {e.get('roomId')} area {e.get('overworldArea')}"
            )
            prev = key
    return transitions[-limit:]


def add_llm_summary(report: str, args: argparse.Namespace) -> str | None:
    if not args.llm_summary:
        return None
    try:
        from lmstudio_client import (
            chat_completion,
            ensure_model_loaded,
            resolve_model,
        )
    except Exception as exc:
        print(f"[trace_report] LM Studio integration unavailable: {exc}", file=sys.stderr)
        return None

    model, identifier, host, port = resolve_model(
        model=args.llm_model,
        expert=args.llm_expert,
        config_path=Path(args.llm_config) if args.llm_config else None,
        host=args.llm_host,
        port=args.llm_port,
    )
    if args.llm_ensure and model:
        ensure_model_loaded(
            model=model,
            identifier=identifier,
            host=host,
            port=port,
            context_length=args.llm_context,
        )
    prompt = (
        "Summarize this Mesen write-trace report. "
        "Call out likely writer routines, suspicious transitions, "
        "and 2-3 concrete next debug steps.\n\n"
        f"{report}"
    )
    try:
        return chat_completion(
            prompt,
            model=identifier or model,
            host=host,
            port=port,
            temperature=args.llm_temp,
            max_tokens=args.llm_max_tokens,
            system=args.llm_system,
        )
    except Exception as exc:
        print(f"[trace_report] LM Studio request failed: {exc}", file=sys.stderr)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate report from write_trace.jsonl")
    parser.add_argument("--trace", default=str(Path.home() / "Documents/Mesen2/bridge/logs/write_trace.jsonl"))
    parser.add_argument("--sym", default=str(REPO_ROOT / "Roms/oos168x.sym"))
    parser.add_argument("--state-log", help="Optional state log JSONL for transition summary")
    parser.add_argument("--out", help="Output path for report markdown")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--llm-summary", action="store_true", help="Append LM Studio summary")
    parser.add_argument("--llm-model", help="Explicit LM Studio model name")
    parser.add_argument("--llm-expert", help="Expert name to resolve via config")
    parser.add_argument("--llm-config", help="Path to LM Studio model config JSON")
    parser.add_argument("--llm-host", default="127.0.0.1")
    parser.add_argument("--llm-port", type=int, default=1234)
    parser.add_argument("--llm-context", type=int, default=None)
    parser.add_argument("--llm-temp", type=float, default=0.2)
    parser.add_argument("--llm-max-tokens", type=int, default=512)
    parser.add_argument("--llm-ensure", action="store_true", help="Load model via lms before query")
    parser.add_argument("--llm-system", default="You are a ROM hack debugging assistant.")
    args = parser.parse_args()

    trace_path = Path(args.trace)
    state_log = load_state_log(Path(args.state_log)) if args.state_log else None
    if not trace_path.exists() and state_log is not None:
        print(f"[trace_report] Trace file missing: {trace_path} (continuing with state log only)", file=sys.stderr)
        entries = []
    else:
        entries = load_trace(trace_path)
    resolver = SymbolResolver(Path(args.sym))
    report = build_report(entries, resolver, args.limit, state_log=state_log)
    summary = add_llm_summary(report, args)
    if summary:
        report = report + "\n\n## LLM Summary\n\n" + summary.strip() + "\n"
    if args.out:
        Path(args.out).write_text(report + "\n")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
