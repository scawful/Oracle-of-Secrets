"""CLI entrypoint for the Oracle Mesen2 debug client."""

import argparse
import json
import os
import re
import sys
import time
import subprocess
import tempfile
from pathlib import Path

from .client import OracleDebugClient
from .capture import capture_debug_snapshot
from .constants import ITEMS, STORY_FLAGS, WATCH_PROFILES, BREAKPOINT_PROFILES
from .expr import ExprEvaluator, EvalContext, ExprError
from .paths import MANIFEST_PATH
from .state_diff import StateDiffer
from .state_symbols import load_oos_symbols
from .bridge import cleanup_stale_sockets

# Try to import AgentBrain (might fail if run directly from lib)
try:
    from agent.brain import AgentBrain
except ImportError:
    AgentBrain = None

SCRIPT_DIR = Path(__file__).resolve().parents[1]
WATCH_PRESETS = {
    "debug": SCRIPT_DIR / "oracle_debug.watch",
    "story": SCRIPT_DIR / "oracle_story.watch",
    "symbols": SCRIPT_DIR / "oracle_symbols.watch",
}


def _normalize_watch_id(label: str, index: int, used: set[str]) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", label.strip()).strip("_")
    if not slug:
        slug = f"watch_{index:02d}"
    base = slug
    suffix = 2
    while slug in used:
        slug = f"{base}_{suffix}"
        suffix += 1
    used.add(slug)
    return slug


def _parse_watch_file(path: Path, default_format: str) -> list[tuple[str, str, str]]:
    watches = []
    used_ids: set[str] = set()
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if not parts:
            continue
        addr = parts[0]
        fmt = default_format
        label_parts = parts[1:]
        if label_parts and label_parts[-1].lower() in {"hex", "dec", "bin"}:
            fmt = label_parts[-1].lower()
            label_parts = label_parts[:-1]
        label = " ".join(label_parts)
        watch_id = _normalize_watch_id(label, len(watches) + 1, used_ids)
        watches.append((watch_id, addr, fmt))
    return watches


def _build_usdasm_symbol_payload(client: OracleDebugClient) -> tuple[dict | None, int, int, str]:
    if not client._usdasm_labels:
        client.load_usdasm_labels()
    if not client._usdasm_labels:
        return None, 0, 0, "No USDASM labels found to sync."

    symbols_data: dict[str, dict[str, object]] = {}
    filtered = 0
    total = len(client._usdasm_labels)
    for name, linear_addr in client._usdasm_labels.items():
        bank = (linear_addr >> 16) & 0xFF
        offset = linear_addr & 0xFFFF
        if bank in (0x7E, 0x7F) or offset < 0x8000:
            filtered += 1
            continue
        symbols_data[name] = {
            "addr": f"{linear_addr:06X}",
            "size": 1,
            "type": "code",
        }
    return symbols_data, filtered, total, ""


def _sync_usdasm_labels(client: OracleDebugClient, clear: bool) -> dict:
    symbols_data, filtered, total, error = _build_usdasm_symbol_payload(client)
    if error:
        return {"success": False, "error": error, "filtered": filtered, "total": total}

    temp_path = Path(tempfile.gettempdir()) / "vanilla_symbols.json"
    try:
        temp_path.write_text(json.dumps(symbols_data))
        res = client.bridge.send_command(
            "SYMBOLS_LOAD",
            {"file": str(temp_path), "clear": "true" if clear else "false"},
        )
        if res.get("success"):
            return {"success": True, "count": len(symbols_data), "filtered": filtered, "total": total}
        return {
            "success": False,
            "error": res.get("error", "Unknown error"),
            "count": len(symbols_data),
            "filtered": filtered,
            "total": total,
        }
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _resolve_z3dk_root(path: str | None) -> Path:
    if path:
        return Path(path).expanduser()
    env_root = os.getenv("Z3DK_ROOT")
    if env_root:
        return Path(env_root).expanduser()
    return Path.home() / "src" / "hobby" / "z3dk"


def _coerce_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    raw = value.strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _find_socket_candidates() -> list[Path]:
    candidates = sorted(Path("/tmp").glob("mesen2-*.sock"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p for p in candidates if p.is_socket()]


def _preflight_socket(args: argparse.Namespace) -> None:
    if args.socket:
        os.environ["MESEN2_SOCKET_PATH"] = args.socket
        return
    if args.instance:
        os.environ["MESEN2_INSTANCE"] = args.instance
        return
    if os.getenv("MESEN2_SOCKET_PATH") or os.getenv("MESEN2_INSTANCE") or os.getenv("MESEN2_REGISTRY_INSTANCE"):
        return

    cleanup_stale_sockets()
    sockets = _find_socket_candidates()
    if not sockets:
        print("Error: No Mesen2 socket found. Launch an instance or set MESEN2_SOCKET_PATH.", file=sys.stderr)
        sys.exit(2)

    if os.getenv("MESEN2_AUTO_ATTACH"):
        os.environ["MESEN2_SOCKET_PATH"] = str(sockets[0])
        print(
            f"Warning: multiple sockets found; auto-attaching to newest {sockets[0]} "
            "(set --socket/--instance to be explicit).",
            file=sys.stderr,
        )
        return

    print(
        "Error: Mesen2 socket not specified. Use --socket or --instance "
        "(or set MESEN2_AUTO_ATTACH=1 to auto-select).",
        file=sys.stderr,
    )
    print("Detected sockets:", file=sys.stderr)
    for sock in sockets[:5]:
        print(f"  - {sock}", file=sys.stderr)
    if len(sockets) > 5:
        print(f"  ... and {len(sockets) - 5} more", file=sys.stderr)
    sys.exit(2)


def _load_watch_preset(client: OracleDebugClient, path: Path, default_format: str, clear: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f"Watch file not found: {path}"

    if clear:
        client.execute_lua("if DebugBridge and DebugBridge.clearWatches then DebugBridge.clearWatches() end")

    watches = _parse_watch_file(path, default_format)
    if not watches:
        return False, f"No watch entries found in {path}"

    for watch_id, expr, fmt in watches:
        # If it's a hex address, make sure it's 0x prefixed for Lua
        if expr.startswith("$"):
            expr = "0x" + expr[1:]
            
        code = f"if DebugBridge and DebugBridge.addWatch then DebugBridge.addWatch('{watch_id}', '{expr}', '{fmt}') end"
        res = client.execute_lua(code)
        if res.get("error"):
            return False, f"Failed to add watch '{watch_id}': {res.get('error')}"

    return True, f"Loaded {len(watches)} watch entries from {path} via socket"


def _normalize_assert_expr(raw: str) -> str:
    text = (raw or "").strip()
    lower = text.lower()
    if "@assert" in lower:
        idx = lower.find("@assert")
        text = text[idx + len("@assert"):].strip()
    if text.startswith(":"):
        text = text[1:].strip()
    return text


def _build_expr_evaluator(client: OracleDebugClient) -> ExprEvaluator:
    table = load_oos_symbols()

    def read8(addr: int) -> int:
        return client.bridge.read_memory(addr)

    def read16(addr: int) -> int:
        return client.bridge.read_memory16(addr)

    def resolve_value(name: str) -> int:
        symbol = table.lookup_by_label(name)
        if not symbol:
            raise ExprError(f"Unknown symbol: {name}")
        addr = symbol.address
        label = symbol.label.upper()
        if label.endswith(("H", "L", "U")):
            return read8(addr)
        if symbol.size >= 2:
            return read16(addr)
        hi = table.lookup_by_label(f"{symbol.label}H")
        if hi and hi.address == addr + 1:
            return read16(addr)
        return read8(addr)

    ctx = EvalContext(resolve_value=resolve_value, read_mem8=read8, read_mem16=read16)
    return ExprEvaluator(ctx)


class SessionLogger:
    """Logs CLI session activity to JSONL."""
    def __init__(self, path: str):
        self.path = Path(path).expanduser()
        
    def log(self, cmd: str, args: argparse.Namespace, result: dict = None, error: str = None):
        entry = {
            "timestamp": time.time(),
            "command": cmd,
            "args": vars(args),
            "result": result,
            "error": error
        }
        # Filter non-serializable args if needed
        if "func" in entry["args"]:
            del entry["args"]["func"]
            
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Oracle of Secrets Debug Client")
    parser.add_argument("--socket", help="Target Mesen2 socket path (recommended; avoids auto-attaching)")
    parser.add_argument("--instance", help="Registry instance name to target (preferred for multi-agent)")
    parser.add_argument("--log", help="Log session activity to JSONL file")
    parser.add_argument("--vanilla", action="store_true", help="Include USDASM vanilla labels")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Commands list (no socket required; for agent discoverability)
    commands_parser = subparsers.add_parser("commands", help="List available command names (no socket required)")
    commands_parser.add_argument("--json", "-j", action="store_true", help="Output JSON array of {name, help}")

    # State command
    state_parser = subparsers.add_parser("state", help="Show game state")
    state_parser.add_argument("--json", "-j", action="store_true")

    run_state_parser = subparsers.add_parser("run-state", help="Show emulator run/paused state")
    run_state_parser.add_argument("--json", "-j", action="store_true")

    time_parser = subparsers.add_parser("time", help="Show Oracle time system state")
    time_parser.add_argument("--json", "-j", action="store_true")

    diag_parser = subparsers.add_parser("diagnostics", help="Show diagnostic snapshot")
    diag_parser.add_argument("--deep", action="store_true", help="Include items, flags, sprites, and watch values")
    diag_parser.add_argument("--json", "-j", action="store_true")

    # Debug Status command (Consolidated)
    debug_status_parser = subparsers.add_parser("debug-status", help="High-level debug status summary")
    debug_status_parser.add_argument("--json", "-j", action="store_true")

    # Debug Context command (Discovery)
    debug_context_parser = subparsers.add_parser("debug-context", help="Discovery command for all debugging assets")
    debug_context_parser.add_argument("--json", "-j", action="store_true")

    # Story command
    story_parser = subparsers.add_parser("story", help="Show story progress")
    story_parser.add_argument("--json", "-j", action="store_true")

    # Health command
    health_parser = subparsers.add_parser("health", help="Check socket health")
    health_parser.add_argument("--json", "-j", action="store_true")

    capabilities_parser = subparsers.add_parser("capabilities", help="Show socket capabilities")
    capabilities_parser.add_argument("--json", "-j", action="store_true")

    metrics_parser = subparsers.add_parser("metrics", help="Show socket metrics")
    metrics_parser.add_argument("--json", "-j", action="store_true")

    history_parser = subparsers.add_parser("command-history", help="Show recent socket command history")
    history_parser.add_argument("--count", type=int, default=20)
    history_parser.add_argument("--json", "-j", action="store_true")

    register_parser = subparsers.add_parser("agent-register", help="Register agent with socket server")
    register_parser.add_argument("--id", dest="agent_id", required=True, help="Agent ID (unique)")
    register_parser.add_argument("--name", dest="agent_name", help="Agent name")
    register_parser.add_argument("--version", help="Agent version")
    register_parser.add_argument("--json", "-j", action="store_true")

    rom_info_parser = subparsers.add_parser("rom-info", help="Show loaded ROM info")
    rom_info_parser.add_argument("--json", "-j", action="store_true")

    cpu_parser = subparsers.add_parser("cpu", help="Show CPU registers")
    cpu_parser.add_argument("--json", "-j", action="store_true")

    pc_parser = subparsers.add_parser("pc", help="Get or set program counter")
    pc_parser.add_argument("address", nargs="?", help="Optional address to set (hex)")
    pc_parser.add_argument("--json", "-j", action="store_true")

    eval_parser = subparsers.add_parser("eval", help="Evaluate debugger expression")
    eval_parser.add_argument("expression", help="Expression string")
    eval_parser.add_argument("--cpu", default="snes")
    eval_parser.add_argument("--no-cache", action="store_true")
    eval_parser.add_argument("--json", "-j", action="store_true")

    expr_eval_parser = subparsers.add_parser("expr-eval", help="Evaluate mini-expr against symbols")
    expr_eval_parser.add_argument("expression", help="Mini-expr string")
    expr_eval_parser.add_argument("--json", "-j", action="store_true")

    assert_parser = subparsers.add_parser("assert-run", help="Evaluate @assert annotations")
    assert_parser.add_argument("--annotations",
                               default=str(SCRIPT_DIR.parent / ".cache" / "annotations.json"),
                               help="Path to annotations.json")
    assert_parser.add_argument("--expr", action="append",
                               help="Inline expression to evaluate (repeatable)")
    assert_parser.add_argument("--strict", action="store_true",
                               help="Exit non-zero if any assert fails or errors")
    assert_parser.add_argument("--fail-fast", action="store_true",
                               help="Stop on first failure/error")
    assert_parser.add_argument("--json", "-j", action="store_true")

    mem_read_parser = subparsers.add_parser("mem-read", help="Read memory")
    mem_read_parser.add_argument("addr", help="Start address (hex)")
    mem_read_parser.add_argument("--len", type=int, default=16)
    mem_read_parser.add_argument("--memtype", default="wram")
    mem_read_parser.add_argument("--json", "-j", action="store_true")

    mem_write_parser = subparsers.add_parser("mem-write", help="Write memory")
    mem_write_parser.add_argument("addr", help="Start address (hex)")
    mem_write_parser.add_argument("values", help="Space-separated hex bytes")
    mem_write_parser.add_argument("--memtype", default="wram")
    mem_write_parser.add_argument("--json", "-j", action="store_true")

    mem_size_parser = subparsers.add_parser("mem-size", help="Get memory region size")
    mem_size_parser.add_argument("--memtype", default="wram")
    mem_size_parser.add_argument("--json", "-j", action="store_true")

    mem_search_parser = subparsers.add_parser("mem-search", help="Search memory for a value or pattern")
    mem_search_parser.add_argument("--pattern", help="Pattern string (e.g., 'A9 00 8D')")
    mem_search_parser.add_argument("--value", help="Value to search (hex)")
    mem_search_parser.add_argument("--size", type=int, default=1)
    mem_search_parser.add_argument("--start", help="Start address (hex)")
    mem_search_parser.add_argument("--end", help="End address (hex)")
    mem_search_parser.add_argument("--memtype", default="wram")
    mem_search_parser.add_argument("--json", "-j", action="store_true")

    mem_snapshot_parser = subparsers.add_parser("mem-snapshot", help="Create memory snapshot")
    mem_snapshot_parser.add_argument("name", help="Snapshot name")
    mem_snapshot_parser.add_argument("--memtype", default="WRAM")
    mem_snapshot_parser.add_argument("--json", "-j", action="store_true")

    mem_diff_parser = subparsers.add_parser("mem-diff", help="Diff memory snapshot")
    mem_diff_parser.add_argument("name", help="Snapshot name")
    mem_diff_parser.add_argument("--json", "-j", action="store_true")

    cheat_parser = subparsers.add_parser("cheat", help="Manage cheat codes")
    cheat_sub = cheat_parser.add_subparsers(dest="cheat_cmd")
    cheat_add = cheat_sub.add_parser("add")
    cheat_add.add_argument("code", help="Cheat code (e.g., 7E0DBE:99)")
    cheat_add.add_argument("--format", default="ProActionReplay")
    cheat_add.add_argument("--json", "-j", action="store_true")
    cheat_list = cheat_sub.add_parser("list")
    cheat_list.add_argument("--json", "-j", action="store_true")
    cheat_clear = cheat_sub.add_parser("clear")
    cheat_clear.add_argument("--json", "-j", action="store_true")

    screenshot_parser = subparsers.add_parser("screenshot", help="Capture screenshot")
    screenshot_parser.add_argument("--out", help="Output path (PNG)")
    screenshot_parser.add_argument("--json", "-j", action="store_true")

    run_parser = subparsers.add_parser("run", help="Run emulator for seconds/frames")
    run_parser.add_argument("--seconds", type=float, default=0.0)
    run_parser.add_argument("--frames", type=int, default=0)
    run_parser.add_argument("--pause-after", choices=("true", "false"), default="true")

    speed_parser = subparsers.add_parser("speed", help="Get or set emulation speed")
    speed_parser.add_argument("multiplier", nargs="?", help="Speed multiplier (0=max, 1=normal)")
    speed_parser.add_argument("--json", "-j", action="store_true")

    rewind_parser = subparsers.add_parser("rewind", help="Rewind emulation")
    rewind_parser.add_argument("--seconds", type=int, default=1)
    rewind_parser.add_argument("--json", "-j", action="store_true")

    p_watch_parser = subparsers.add_parser("p-watch", help="Manage P-register tracking")
    p_watch_sub = p_watch_parser.add_subparsers(dest="p_cmd")
    p_watch_start = p_watch_sub.add_parser("start")
    p_watch_start.add_argument("--depth", type=int, default=1000)
    p_watch_sub.add_parser("stop")
    p_watch_sub.add_parser("status")

    p_log_parser = subparsers.add_parser("p-log", help="Get recent P-register changes")
    p_log_parser.add_argument("--count", type=int, default=50)
    p_log_parser.add_argument("--json", "-j", action="store_true")

    p_assert_parser = subparsers.add_parser("p-assert", help="Assert P-register value at address")
    p_assert_parser.add_argument("addr", help="Address (hex)")
    p_assert_parser.add_argument("expected", help="Expected P value (hex)")
    p_assert_parser.add_argument("--mask", default="0xFF")
    p_assert_parser.add_argument("--json", "-j", action="store_true")

    mem_watch_parser = subparsers.add_parser("mem-watch", help="Manage memory write watches")
    mem_watch_sub = mem_watch_parser.add_subparsers(dest="mem_watch_cmd")
    mem_watch_add = mem_watch_sub.add_parser("add")
    mem_watch_add.add_argument("addr", help="Address (hex)")
    mem_watch_add.add_argument("--size", type=int, default=1)
    mem_watch_add.add_argument("--depth", type=int, default=100)
    mem_watch_sub.add_parser("list")
    mem_watch_remove = mem_watch_sub.add_parser("remove")
    mem_watch_remove.add_argument("id", type=int)
    mem_watch_sub.add_parser("clear")

    mem_blame_parser = subparsers.add_parser("mem-blame", help="Get write history for watched memory")
    mem_blame_parser.add_argument("--addr", help="Address (hex)")
    mem_blame_parser.add_argument("--watch-id", type=int)
    mem_blame_parser.add_argument("--json", "-j", action="store_true")

    symbols_load_parser = subparsers.add_parser("symbols-load", help="Load symbols JSON into Mesen2")
    symbols_load_parser.add_argument("path", help="Path to symbols JSON")
    symbols_load_parser.add_argument("--clear", action="store_true")
    symbols_load_parser.add_argument("--json", "-j", action="store_true")

    collision_overlay_parser = subparsers.add_parser("collision-overlay", help="Toggle collision overlay")
    collision_overlay_parser.add_argument("--enable", action="store_true")
    collision_overlay_parser.add_argument("--disable", action="store_true")
    collision_overlay_parser.add_argument("--colmap", default="A")
    collision_overlay_parser.add_argument("--highlight", help="Comma-separated tile values (hex)")
    collision_overlay_parser.add_argument("--json", "-j", action="store_true")

    collision_dump_parser = subparsers.add_parser("collision-dump", help="Dump collision map")
    collision_dump_parser.add_argument("--colmap", default="A")
    collision_dump_parser.add_argument("--json", "-j", action="store_true")

    draw_path_parser = subparsers.add_parser("draw-path", help="Draw path overlay")
    draw_path_parser.add_argument("points", nargs="?", default="",
                                  help="Comma-separated x,y pairs (e.g. 10,10,20,15). Omit to clear.")
    draw_path_parser.add_argument("--color", help="Hex color (e.g. 0x00FF00 or #00FF00)")
    draw_path_parser.add_argument("--frames", type=int, help="Frames to display")
    draw_path_parser.add_argument("--json", "-j", action="store_true")

    lua_parser = subparsers.add_parser("lua", help="Execute Lua in Mesen2")
    lua_parser.add_argument("code", nargs="?", help="Lua code string")
    lua_parser.add_argument("--file", help="Lua file to execute")
    lua_parser.add_argument("--json", "-j", action="store_true")

    load_script_parser = subparsers.add_parser("load-script", help="Load Lua script into Mesen2")
    load_script_parser.add_argument("path", help="Lua script path")
    load_script_parser.add_argument("--name", default="cli_script")
    load_script_parser.add_argument("--json", "-j", action="store_true")

    state_compare_parser = subparsers.add_parser("state-compare", help="Diff two save slots")
    state_compare_parser.add_argument("--slot-a", type=int, default=1)
    state_compare_parser.add_argument("--slot-b", type=int, default=2)
    state_compare_parser.add_argument("--regions", help="Comma-separated region names")
    state_compare_parser.add_argument("--format", choices=("json", "markdown"), default="json")

    # ROM load command (when UI shows load ROM screen)
    rom_load_parser = subparsers.add_parser("rom-load", help="Load ROM by path via socket")
    rom_load_parser.add_argument("path", help="Path to ROM (.sfc, .smc, .gb, etc.)")
    rom_load_parser.add_argument("--patch", help="Optional patch file (IPS/BPS)")
    rom_load_parser.add_argument("--stop", choices=("true", "false"), help="Stop current ROM first (default true)")
    rom_load_parser.add_argument("--powercycle", choices=("true", "false"), help="Power-cycle load (default false)")
    rom_load_parser.add_argument("--json", "-j", action="store_true")

    # Socket cleanup command
    socket_cleanup_parser = subparsers.add_parser("socket-cleanup", help="Remove stale Mesen2 sockets")
    socket_cleanup_parser.add_argument("--json", "-j", action="store_true")

    # Close command (registry-based)
    close_parser = subparsers.add_parser("close", help="Close a registered Mesen2 instance (graceful)")
    close_parser.add_argument("--force", action="store_true")
    close_parser.add_argument("--confirm", action="store_true")
    close_parser.add_argument("--owner")

    # Watch command
    watch_parser = subparsers.add_parser("watch", help="Watch addresses")
    watch_parser.add_argument("--profile", "-p", default="overworld")
    watch_parser.add_argument("--json", "-j", action="store_true")

    # Breakpoint command
    bp_parser = subparsers.add_parser("breakpoint", help="Manage breakpoints")
    bp_parser.add_argument("--profile", "-p", help="Load a breakpoint profile")
    bp_parser.add_argument("--add", "-a", help="Add breakpoint (addr:type)")
    bp_parser.add_argument("--remove", "-r", type=int, help="Remove breakpoint ID")
    bp_parser.add_argument("--list", "-l", action="store_true", help="List breakpoints")
    bp_parser.add_argument("--clear", "-c", action="store_true", help="Clear all breakpoints")
    bp_parser.add_argument("--json", "-j", action="store_true")

    # Trace command (socket TRACE)
    trace_parser = subparsers.add_parser("trace", help="Control or fetch execution trace (socket)")
    trace_parser.add_argument("--action", choices=("start", "stop", "status", "clear"))
    trace_parser.add_argument("--count", type=int, default=20, help="Entries to fetch (default 20, max 100)")
    trace_parser.add_argument("--offset", type=int, default=0, help="Trace buffer offset")
    trace_parser.add_argument("--format", help="Trace format string")
    trace_parser.add_argument("--condition", help="Trace condition")
    trace_parser.add_argument("--labels", choices=("true", "false"), help="Enable label resolution")
    trace_parser.add_argument("--indent", choices=("true", "false"), help="Indent code blocks")
    trace_parser.add_argument("--clear", action="store_true", help="Clear buffer when starting trace")
    trace_parser.add_argument("--json", "-j", action="store_true")

    trace_run_parser = subparsers.add_parser("trace-run", help="Run frames and dump trace entries as JSONL")
    trace_run_parser.add_argument("--frames", type=int, default=60, help="Frames to run before dumping trace")
    trace_run_parser.add_argument("--count", type=int, default=2000, help="Trace entries to fetch")
    trace_run_parser.add_argument("--offset", type=int, default=0, help="Trace buffer offset")
    trace_run_parser.add_argument("--format", help="Trace format string")
    trace_run_parser.add_argument("--condition", help="Trace condition")
    trace_run_parser.add_argument("--labels", choices=("true", "false"), default="true",
                                  help="Enable label resolution (default true)")
    trace_run_parser.add_argument("--clear", action="store_true", help="Clear trace buffer before running")
    trace_run_parser.add_argument("--output", "-o", help="Output JSONL path (default: stdout)")

    freeze_guard_parser = subparsers.add_parser("freeze-guard", help="Detect stalls and capture snapshot")
    freeze_guard_parser.add_argument("--frames", type=int, default=60, help="Frames to test for progress")
    freeze_guard_parser.add_argument("--watch-profile", default="overworld", help="Watch profile for capture")
    freeze_guard_parser.add_argument("--prefix", default="freeze_guard", help="Capture filename prefix")
    freeze_guard_parser.add_argument("--out-dir", default=str(SCRIPT_DIR.parent / "Roms" / "SaveStates" / "bug_captures"),
                                     help="Output directory for capture JSON/screenshot")
    freeze_guard_parser.add_argument("--save-slot", type=int, help="Save state to slot on freeze")
    freeze_guard_parser.add_argument("--no-screenshot", action="store_true", help="Skip screenshot capture")
    freeze_guard_parser.add_argument("--json", "-j", action="store_true")

    step_parser = subparsers.add_parser("step", help="Step CPU instructions (socket)")
    step_parser.add_argument("count", nargs="?", type=int, default=1, help="Instructions to step (default 1)")
    step_parser.add_argument(
        "--mode",
        choices=("instruction", "step", "into", "over", "out", "cycle", "ppu", "scanline", "frame", "nmi", "irq", "back"),
        default="into",
        help="Step mode (default: into)",
    )
    step_parser.add_argument("--pause", action="store_true",
                             help="Pause before stepping (recommended)")
    step_parser.add_argument("--json", "-j", action="store_true")

    # Watch loader command
    watch_load_parser = subparsers.add_parser(
        "watch-load", help="Load watch preset into Mesen2 (debug bridge)"
    )
    watch_load_parser.add_argument(
        "--preset", choices=sorted(WATCH_PRESETS.keys()), default="debug"
    )
    watch_load_parser.add_argument("--file", help="Watch list file path")
    watch_load_parser.add_argument(
        "--format", choices=("hex", "dec", "bin"), default="hex"
    )
    watch_load_parser.add_argument(
        "--clear", action="store_true", help="Clear existing watches before loading"
    )

    # Sprites command
    sprites_parser = subparsers.add_parser("sprites", help="Debug sprites")
    sprites_parser.add_argument("--slot", "-s", type=int, default=0)
    sprites_parser.add_argument("--all", "-a", action="store_true")
    sprites_parser.add_argument("--json", "-j", action="store_true")

    # Profiles command
    profiles_parser = subparsers.add_parser("profiles", help="List watch profiles")
    profiles_parser.add_argument("--json", "-j", action="store_true")

    # Assistant command
    subparsers.add_parser("assistant", help="Live debug assistant")

    # === NEW COMMANDS ===

    # Items command
    items_parser = subparsers.add_parser("items", help="List/get items")
    items_parser.add_argument("item", nargs="?", help="Item name to get")
    items_parser.add_argument("--json", "-j", action="store_true")

    # Give command (set item)
    give_parser = subparsers.add_parser("give", help="Give item to Link")
    give_parser.add_argument("item", help="Item name")
    give_parser.add_argument("value", type=int, help="Value to set")

    # Flags command
    flags_parser = subparsers.add_parser("flags", help="List/get story flags")
    flags_parser.add_argument("flag", nargs="?", help="Flag name to get")
    flags_parser.add_argument("--json", "-j", action="store_true")

    # Set flag command
    setflag_parser = subparsers.add_parser("setflag", help="Set a story flag")
    setflag_parser.add_argument("flag", help="Flag name")
    setflag_parser.add_argument("value", help="Value (number or true/false)")

    # Press command (input injection)
    press_parser = subparsers.add_parser("press", help="Press buttons")
    press_parser.add_argument("buttons", help="Comma-separated buttons (a,b,up,down,etc)")
    press_parser.add_argument("--frames", "-f", type=int, default=5)
    press_parser.add_argument("--allow-paused", action="store_true", help="Allow input while paused")

    # Position command
    pos_parser = subparsers.add_parser("pos", help="Set Link position")
    pos_parser.add_argument("x", type=int)
    pos_parser.add_argument("y", type=int)

    # Navigation command
    nav_parser = subparsers.add_parser("navigate", help="Navigate Link autonomously")
    nav_group = nav_parser.add_mutually_exclusive_group(required=True)
    nav_group.add_argument("--poi", type=str, help="Point of interest name")
    nav_group.add_argument("--area", type=str, help="Area ID (hex, e.g., 0x40)")
    nav_group.add_argument("--pos", type=str, help="Coordinates (x,y)")
    nav_parser.add_argument("--timeout", type=int, default=600, help="Timeout in frames")
    nav_parser.add_argument("--no-safe", action="store_true", help="Disable checkpoint")

    # Move command
    move_parser = subparsers.add_parser("move", help="Basic directional movement")
    move_group = move_parser.add_mutually_exclusive_group(required=True)
    move_group.add_argument("--direction", "-d", choices=("up", "down", "left", "right"), help="Direction to move")
    move_group.add_argument("--to", type=str, help="X,Y coordinates")
    move_group.add_argument("--to-poi", type=str, help="POI name")
    move_parser.add_argument("--distance", type=int, default=30, help="Distance in frames (for --direction)")
    move_parser.add_argument("--timeout", type=int, default=600, help="Timeout in frames (for --to)")

    # Hypothesis Testing command
    hypo_parser = subparsers.add_parser("test-hypothesis", help="Test memory patches against a state")
    hypo_parser.add_argument("state_id", help="State ID to test against")
    hypo_parser.add_argument("--patch", "-p", action="append", help="Patch in addr:val format (hex)")
    hypo_parser.add_argument("--patch-file", "-f", help="JSON file containing patches")
    hypo_parser.add_argument("--frames", type=int, default=300, help="Frames to wait before verification")
    hypo_parser.add_argument("--watch", help="Watch profile to load")
    hypo_parser.add_argument("--json", "-j", action="store_true")

    # Control commands
    subparsers.add_parser("pause", help="Pause emulation")
    subparsers.add_parser("resume", help="Resume emulation")
    subparsers.add_parser("reset", help="Reset game")

    # Disassembly command
    disasm_parser = subparsers.add_parser("disasm", help="Disassemble code")
    disasm_parser.add_argument("address", nargs="?", help="Address to disassemble (hex)")
    disasm_parser.add_argument("--count", "-c", type=int, default=10, help="Number of instructions")
    disasm_parser.add_argument("--json", "-j", action="store_true")

    # Frame advance
    frame_parser = subparsers.add_parser("frame", help="Advance frames")
    frame_parser.add_argument("count", type=int, nargs="?", default=1)

    # Save state commands
    save_parser = subparsers.add_parser("save", help="Save state")
    save_parser.add_argument("slot", type=int, nargs="?", help="Slot number (1-99 or configured)")
    save_parser.add_argument("--path", "-p", help="Custom save path")

    load_parser = subparsers.add_parser("load", help="Load state")
    load_parser.add_argument("slot", type=int, nargs="?", help="Slot number (1-99 or configured)")
    load_parser.add_argument("--path", "-p", help="Custom load path")

    label_parser = subparsers.add_parser("savestate-label", help="Get/set save state labels")
    label_parser.add_argument("action", choices=("get", "set", "clear"))
    label_parser.add_argument("slot", type=int, nargs="?", help="Slot number (1-99 or configured)")
    label_parser.add_argument("--path", "-p", help="Save state path")
    label_parser.add_argument("--label", "-l", help="Label text (for set)")
    label_parser.add_argument("--json", "-j", action="store_true")

    # Smart Save command
    smart_save_parser = subparsers.add_parser("smart-save", help="Save state only if safe (Agent verified)")
    smart_save_parser.add_argument("slot", type=int, help="Slot number (1-99 or configured)")
    smart_save_parser.add_argument(
        "--b008-mode",
        choices=("auto", "on", "off"),
        default="auto",
        help="B008 input correction mode for AgentBrain (auto/on/off)",
    )

    # AgentBrain calibration command
    subparsers.add_parser(
        "brain-calibrate",
        help="Auto-detect B008 input rotation (AgentBrain)",
    )

    # Library commands
    lib_parser = subparsers.add_parser("library", help="List library entries")
    lib_parser.add_argument("--tag", "-t", help="Filter by tag")
    lib_parser.add_argument("--json", "-j", action="store_true")

    # Repro command
    repro_parser = subparsers.add_parser("repro", help="Reproduce bug from state")
    repro_parser.add_argument("state_id", help="State ID from library")
    repro_parser.add_argument("--trace", action="store_true", help="Start trace after loading")
    repro_parser.add_argument("--watch", help="Watch profile to load")
    repro_parser.add_argument("--json", "-j", action="store_true")

    lib_save_parser = subparsers.add_parser("lib-save", help="Save labeled state to library")
    lib_save_parser.add_argument("label", help="Label for the state")
    lib_save_parser.add_argument("--tag", "-t", action="append", dest="tags", help="Optional tag (repeatable)")
    lib_save_parser.add_argument("--captured-by", choices=["human", "agent"], default="agent",
                                  help="Who captured this state (default: agent)")
    lib_save_parser.add_argument("--json", "-j", action="store_true")

    lib_verify_parser = subparsers.add_parser("lib-verify", help="Promote draft state to canon status")
    lib_verify_parser.add_argument("state_id", help="State ID to verify")
    lib_verify_parser.add_argument("--by", dest="verified_by", default="scawful", help="Verifier name")
    lib_verify_parser.add_argument("--json", "-j", action="store_true")

    lib_verify_all_parser = subparsers.add_parser("lib-verify-all", help="Verify all canon states by loading them")
    lib_verify_all_parser.add_argument("--json", "-j", action="store_true")

    lib_deprecate_parser = subparsers.add_parser("lib-deprecate", help="Mark state as deprecated")
    lib_deprecate_parser.add_argument("state_id", help="State ID to deprecate")
    lib_deprecate_parser.add_argument("--reason", "-r", default="", help="Deprecation reason")
    lib_deprecate_parser.add_argument("--json", "-j", action="store_true")

    lib_backfill_parser = subparsers.add_parser("lib-backfill", help="Backfill missing hashes in manifest")
    lib_backfill_parser.add_argument("--json", "-j", action="store_true")

    lib_load_parser = subparsers.add_parser("lib-load", help="Load state from library by ID")
    lib_load_parser.add_argument("state_id", help="State ID from library")

    lib_info_parser = subparsers.add_parser("lib-info", help="Show library entry details")
    lib_info_parser.add_argument("state_id", help="State ID")
    lib_info_parser.add_argument("--json", "-j", action="store_true")

    lib_scan_parser = subparsers.add_parser("lib-scan", help="Scan library folder for unmanaged states")
    lib_scan_parser.add_argument("--json", "-j", action="store_true")

    capture_parser = subparsers.add_parser("capture", help="Capture current state metadata")
    capture_parser.add_argument("--json", "-j", action="store_true")

    # Symbols command
    symbols_parser = subparsers.add_parser("symbols", help="Query symbols and labels")
    symbols_parser.add_argument("query", nargs="?", help="Symbol name or address to look up")
    symbols_parser.add_argument("--json", "-j", action="store_true")

    labels_parser = subparsers.add_parser("labels", help="Manage Mesen2 labels")
    labels_sub = labels_parser.add_subparsers(dest="labels_cmd")
    labels_set = labels_sub.add_parser("set", help="Set label at address")
    labels_set.add_argument("addr", help="Address (hex)")
    labels_set.add_argument("label", help="Label name")
    labels_set.add_argument("--comment", default="")
    labels_set.add_argument("--memtype", default="WRAM")
    labels_set.add_argument("--json", "-j", action="store_true")
    labels_get = labels_sub.add_parser("get", help="Get label at address")
    labels_get.add_argument("addr", help="Address (hex)")
    labels_get.add_argument("--memtype", default="WRAM")
    labels_get.add_argument("--json", "-j", action="store_true")
    labels_lookup = labels_sub.add_parser("lookup", help="Resolve label to address")
    labels_lookup.add_argument("label", help="Label name")
    labels_lookup.add_argument("--json", "-j", action="store_true")
    labels_clear = labels_sub.add_parser("clear", help="Clear all labels")
    labels_clear.add_argument("--json", "-j", action="store_true")

    # Labels refresh command (z3dk)
    labels_refresh_parser = subparsers.add_parser(
        "labels-refresh",
        help="Regenerate label indexes via z3dk (USDASM + Oracle).",
    )
    labels_refresh_parser.add_argument("--z3dk-root", help="Path to z3dk repo (default: $Z3DK_ROOT or ~/src/hobby/z3dk)")
    labels_refresh_parser.add_argument("--usdasm-root", help="Override USDASM disassembly root")
    labels_refresh_parser.add_argument("--sync", action="store_true", help="Sync refreshed USDASM labels into Mesen2")
    labels_refresh_parser.add_argument("--clear", action="store_true", help="Clear existing labels before syncing")
    labels_refresh_parser.add_argument("--json", "-j", action="store_true")

    # Labels Sync command
    labels_sync_parser = subparsers.add_parser(
        "labels-sync",
        help="Sync vanilla USDASM ROM labels to Mesen2 (filters RAM/low addresses)",
    )
    labels_sync_parser.add_argument("--clear", action="store_true", help="Clear existing labels before syncing")
    labels_sync_parser.add_argument("--json", "-j", action="store_true")

    # === ADVANCED COMMANDS ===

    # Subscribe command
    subscribe_parser = subparsers.add_parser("subscribe", help="Subscribe to events")
    subscribe_parser.add_argument("events", help="Comma-separated events (breakpoint_hit,frame_complete,all)")

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Execute batch commands")
    batch_parser.add_argument("commands", help="JSON array of commands")

    # Watchdog command
    watchdog_parser = subparsers.add_parser("watchdog", help="Detect stalled game loop and auto-recover")
    watchdog_parser.add_argument("--slot", type=int, default=1, help="Savestate slot to reload on stall")
    watchdog_parser.add_argument("--frames", type=int, default=30, help="Frames to run while checking progress")
    watchdog_parser.add_argument("--json", "-j", action="store_true")

    # State Diff command
    state_diff_parser = subparsers.add_parser("state-diff", help="Get state changes since last call")
    state_diff_parser.add_argument("--json", "-j", action="store_true")

    # Watch Trigger commands
    trigger_parser = subparsers.add_parser("watch-trigger", help="Manage memory watch triggers")
    trigger_sub = trigger_parser.add_subparsers(dest="trigger_cmd")

    trig_add = trigger_sub.add_parser("add", help="Add a watch trigger")
    trig_add.add_argument("addr", help="Address (hex)")
    trig_add.add_argument("value", help="Value (hex)")
    trig_add.add_argument("--condition", "-c", default="eq", choices=("eq", "ne", "gt", "lt", "ge", "le"))

    trig_rem = trigger_sub.add_parser("remove", help="Remove a watch trigger")
    trig_rem.add_argument("id", type=int, help="Trigger ID")

    trigger_sub.add_parser("list", help="List watch triggers")

    # Stack return decoder (STACK_RETADDR)
    stack_ret_parser = subparsers.add_parser("stack-retaddr", help="Decode stack return addresses")
    stack_ret_parser.add_argument("--mode", choices=("rtl", "rts"), default="rtl", help="Return type (default rtl)")
    stack_ret_parser.add_argument("--count", type=int, default=4, help="Number of entries to decode")
    stack_ret_parser.add_argument("--sp", help="Override SP (hex)")
    stack_ret_parser.add_argument("--json", "-j", action="store_true")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Notify YAZE of state save")
    sync_parser.add_argument("path", help="Path to state file")

    # Agent-friendly JSON commands (single entry point)
    agent_parser = subparsers.add_parser("agent", help="Agent-friendly JSON commands")
    agent_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    agent_sub = agent_parser.add_subparsers(dest="agent_cmd")

    agent_sub.add_parser("health", help="Check socket health")
    agent_sub.add_parser("state", help="Get full emulator state")
    agent_sub.add_parser("oracle-state", help="Get Oracle-specific state")
    agent_sub.add_parser("story", help="Get story progress state")
    agent_sub.add_parser("run-state", help="Get emulator run/paused state")
    agent_sub.add_parser("time", help="Get Oracle time system state")
    diag_agent = agent_sub.add_parser("diagnostics", help="Get diagnostic snapshot")
    diag_agent.add_argument("--deep", action="store_true", help="Include items, flags, sprites, and watch values")

    press_agent = agent_sub.add_parser("press", help="Press buttons")
    press_agent.add_argument("buttons", help="Comma-separated buttons")
    press_agent.add_argument("--frames", type=int, default=5)
    press_agent.add_argument("--allow-paused", action="store_true")

    save_agent = agent_sub.add_parser("save", help="Save state")
    save_agent.add_argument("slot", nargs="?", type=int)
    save_agent.add_argument("--path")

    load_agent = agent_sub.add_parser("load", help="Load state")
    load_agent.add_argument("slot", nargs="?", type=int)
    load_agent.add_argument("--path")

    label_agent = agent_sub.add_parser("savestate-label", help="Get/set save state labels")
    label_agent.add_argument("action", choices=("get", "set", "clear"))
    label_agent.add_argument("slot", nargs="?", type=int)
    label_agent.add_argument("--path")
    label_agent.add_argument("--label")

    lib_save_agent = agent_sub.add_parser("lib-save", help="Save labeled state to library")
    lib_save_agent.add_argument("label")
    lib_save_agent.add_argument("--tag", action="append", dest="tags")

    agent_sub.add_parser("lib-scan", help="Scan library folder for unmanaged states")

    snap_agent = agent_sub.add_parser("snapshot", help="Capture state JSON + screenshot")
    snap_agent.add_argument("--out-dir", default=str(SCRIPT_DIR.parent / "Roms" / "SaveStates" / "bug_captures"))

    wait_agent = agent_sub.add_parser("wait", help="Sleep for seconds")
    wait_agent.add_argument("seconds", type=float)

    args = parser.parse_args()
    logger = SessionLogger(args.log) if args.log else None
    if logger:
        logger.log(args.command, args)

    if not args.command:
        parser.print_help()
        return

    if args.command == "commands":
        names = sorted(subparsers.choices.keys())
        choice_help = {}
        for a in getattr(subparsers, "_choices_actions", []):
            for opt in getattr(a, "option_strings", []) or []:
                choice_help[opt] = (getattr(a, "help", None) or "").strip()
        if getattr(args, "json", False):
            arr = [{"name": n, "help": choice_help.get(n, "")} for n in names]
            print(json.dumps(arr))
        else:
            for n in names:
                print(n)
        return

    if args.command == "agent":
        _preflight_socket(args)
        def emit(payload: dict, ok: bool = True) -> None:
            data = {"ok": ok, **payload}
            if args.pretty:
                print(json.dumps(data, indent=2))
            else:
                print(json.dumps(data))
            if not ok:
                sys.exit(1)

        if not args.agent_cmd:
            agent_parser.print_help()
            sys.exit(1)

        client = OracleDebugClient()
        if args.agent_cmd == "health":
            info = client.health_check()
            emit(info, ok=bool(info.get("ok")))
            return

        if not client.ensure_connected():
            emit({"error": "Cannot connect to Mesen2 socket", "socket": getattr(client.bridge, "socket_path", None)}, ok=False)

        if args.agent_cmd == "state":
            raw = client.bridge.get_state()
            data = raw.get("data") if isinstance(raw, dict) else None
            if data is None:
                data = client.get_oracle_state()
            emit({"state": data})
            return
        if args.agent_cmd == "oracle-state":
            emit({"state": client.get_oracle_state()})
            return
        if args.agent_cmd == "story":
            emit({"story": client.get_story_state()})
            return
        if args.agent_cmd == "run-state":
            emit({"run_state": client.get_run_state()})
            return
        if args.agent_cmd == "time":
            emit({"time": client.get_time_state()})
            return
        if args.agent_cmd == "diagnostics":
            emit({"diagnostics": client.get_diagnostics(deep=getattr(args, "deep", False))})
            return
        if args.agent_cmd == "press":
            ok = client.press_button(args.buttons, frames=args.frames, ensure_running=not args.allow_paused)
            emit({"pressed": args.buttons, "frames": args.frames}, ok=ok)
            return
        if args.agent_cmd == "save":
            ok = False
            if args.path:
                ok = client.save_state(path=args.path)
                emit({"saved": args.path}, ok=ok)
            elif args.slot is not None:
                ok = client.save_state(slot=args.slot)
                emit({"saved": args.slot}, ok=ok)
            else:
                emit({"error": "Missing slot or path"}, ok=False)
            return
        if args.agent_cmd == "load":
            if args.path:
                ok = client.load_state(path=args.path)
                if ok:
                    emit({"loaded": args.path}, ok=True)
                else:
                    emit({"error": client.last_error or "Load failed", "path": args.path}, ok=False)
            elif args.slot is not None:
                ok = client.load_state(slot=args.slot)
                if ok:
                    emit({"loaded": args.slot}, ok=True)
                else:
                    emit({"error": "Load failed", "slot": args.slot}, ok=False)
            else:
                emit({"error": "Missing slot or path"}, ok=False)
            return
        if args.agent_cmd == "savestate-label":
            if args.slot is None and not args.path:
                emit({"error": "Missing slot or path"}, ok=False)
            if args.action == "set" and not args.label:
                emit({"error": "Missing label"}, ok=False)
            res = client.save_state_label(
                action=args.action,
                slot=args.slot,
                path=args.path,
                label=args.label,
            )
            emit({"response": res}, ok=bool(res.get("success")))
            return
        if args.agent_cmd == "lib-save":
            try:
                state_id = client.save_library_state(args.label, tags=args.tags)
                emit({"state_id": state_id, "label": args.label})
            except Exception as exc:
                emit({"error": str(exc)}, ok=False)
            return
        if args.agent_cmd == "lib-scan":
            try:
                added = client.scan_library()
                emit({"added": added})
            except Exception as exc:
                emit({"error": str(exc)}, ok=False)
            return
        if args.agent_cmd == "snapshot":
            out_dir = Path(args.out_dir).expanduser()
            out_dir.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            state_path = out_dir / f"state_{stamp}.json"
            shot_path = out_dir / f"shot_{stamp}.png"

            raw = client.bridge.get_state()
            data = raw.get("data") if isinstance(raw, dict) else None
            if data is None:
                data = client.get_oracle_state()
            state_path.write_text(json.dumps(data, indent=2))

            shot_bytes = client.screenshot()
            shot_out = ""
            if shot_bytes:
                shot_path.write_bytes(shot_bytes)
                shot_out = str(shot_path)

            emit({"state": str(state_path), "screenshot": shot_out})
            return
        if args.agent_cmd == "wait":
            time.sleep(args.seconds)
            emit({"waited": args.seconds})
            return

        emit({"error": f"Unknown agent command: {args.agent_cmd}"}, ok=False)
        return

    # Handle commands that don't require connection first
    if args.command == "close":
        instance = args.instance or os.getenv("MESEN2_INSTANCE") or os.getenv("MESEN2_REGISTRY_INSTANCE")
        if not instance:
            print("Error: --instance is required (or set MESEN2_INSTANCE).")
            sys.exit(1)
        registry = SCRIPT_DIR / "mesen2_registry.py"
        if not registry.exists():
            print("Error: mesen2_registry.py not found.")
            sys.exit(1)
        cmd = [sys.executable, str(registry), "close", "--instance", instance]
        if args.owner:
            cmd += ["--owner", args.owner]
        if args.force:
            cmd.append("--force")
        if args.confirm:
            cmd.append("--confirm")
        result = subprocess.run(cmd, check=False)
        sys.exit(result.returncode)

    if args.command == "watch-load":
        _preflight_socket(args)
        client = OracleDebugClient()
        path = Path(args.file).expanduser() if args.file else WATCH_PRESETS.get(args.preset)
        ok, msg = _load_watch_preset(client, path, args.format, args.clear)
        print(msg)
        if not ok:
            sys.exit(1)
        return

    if args.command == "profiles":
        if args.json:
            profiles = {name: p["description"] for name, p in WATCH_PROFILES.items()}
            print(json.dumps(profiles, indent=2))
        else:
            print("=== Available Watch Profiles ===")
            for name, p in WATCH_PROFILES.items():
                print(f"  {name}: {p['description']}")
        return

    if args.command == "items" and not args.item:
        # List available items
        print("=== Available Items ===")
        for name, (addr, desc, vals) in ITEMS.items():
            print(f"  {name}: {desc}")
        return

    if args.command == "flags" and not args.flag:
        # List available flags
        print("=== Available Flags ===")
        for name, (addr, desc, mask) in STORY_FLAGS.items():
            bit_info = f" (bit 0x{mask:02X})" if isinstance(mask, int) else ""
            print(f"  {name}: {desc}{bit_info}")
        return

    if args.command == "labels-refresh":
        z3dk_root = _resolve_z3dk_root(args.z3dk_root)
        script_path = z3dk_root / "scripts" / "generate_label_indexes.py"
        if not script_path.exists():
            print(f"Error: z3dk script not found at {script_path}", file=sys.stderr)
            sys.exit(1)

        cmd = [sys.executable, str(script_path)]
        if args.usdasm_root:
            cmd += ["--usdasm-root", str(Path(args.usdasm_root).expanduser())]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            if args.json:
                print(json.dumps({
                    "ok": False,
                    "error": result.stderr.strip(),
                    "stdout": result.stdout.strip(),
                }, indent=2))
            else:
                print(result.stdout.strip())
                print(result.stderr.strip(), file=sys.stderr)
            sys.exit(result.returncode)

        # Refresh USDASM labels in the current client cache
        client = OracleDebugClient()
        loaded = client.load_usdasm_labels()

        payload = {
            "ok": True,
            "usdasm_loaded": loaded,
            "stdout": result.stdout.strip(),
        }

        if args.sync:
            _preflight_socket(args)
            client = OracleDebugClient()
            if not client.ensure_connected():
                print("Error: Could not connect to Mesen2 socket for label sync.", file=sys.stderr)
                sys.exit(1)
            sync_result = _sync_usdasm_labels(client, args.clear)
            payload["sync"] = sync_result
            if not sync_result.get("success"):
                if args.json:
                    print(json.dumps(payload, indent=2))
                else:
                    print(sync_result.get("error", "Label sync failed"), file=sys.stderr)
                sys.exit(1)

        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            if result.stdout.strip():
                print(result.stdout.strip())
            print(f"USDASM labels loaded: {loaded}")
            if args.sync:
                sync_info = payload.get("sync", {})
                print(f"Synced {sync_info.get('count', 0)} labels (filtered {sync_info.get('filtered', 0)})")
        return

    _preflight_socket(args)
    client = OracleDebugClient()
    if args.vanilla:
        client.load_usdasm_labels()

    if args.command == "debug-status":
        info = client.health_check()
        rom_info = client.get_rom_info()
        rom_loaded = bool(rom_info)
        run_state = client.get_run_state() if rom_loaded else {}
        state = {}
        if rom_loaded:
            try:
                state = client.get_oracle_state()
            except Exception:
                state = {}
        manifest = client.get_library_manifest()
        
        canon_states = [e["id"] for e in manifest.get("entries", []) if e.get("status") == "canon"]
        
        status = {
            "health": info,
            "run_state": run_state,
            "rom_loaded": rom_loaded,
            "rom_info": rom_info,
            "game_mode": state.get("mode_name"),
            "location": state.get("area_name"),
            "pos": (state.get("link_x"), state.get("link_y")),
            "canon_states": canon_states,
            "watch_profile": client._watch_profile,
        }
        
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print("=== Debug Status ===")
            print(f"Health: {'OK' if info.get('ok') else 'FAIL'} (Latency: {info.get('latency_ms')}ms)")
            if not rom_loaded:
                print("ROM: not loaded (load screen)")
                print("Hint: python3 scripts/mesen2_client.py rom-load <path-to-rom>")
            else:
                print(f"ROM: {rom_info.get('filename')} (crc32={rom_info.get('crc32')})")
                print(f"Emulator: {'Paused' if run_state.get('paused') else 'Running'} (Frame: {run_state.get('frame')})")
                print(f"Game: {state.get('mode_name')} | {state.get('area_name')} | Pos: ({state.get('link_x')}, {state.get('link_y')})")
            print(f"Canon States: {len(canon_states)} available")
            if canon_states:
                print(f"  Example: {canon_states[0]}")
            print(f"Watch Profile: {client._watch_profile}")
        return

    if args.command == "health":
        info = client.health_check()
        rom_info = client.get_rom_info()
        rom_loaded = bool(rom_info)
        if args.json:
            payload = dict(info)
            payload["rom_loaded"] = rom_loaded
            payload["rom_info"] = rom_info
            if not rom_loaded and client.last_error:
                payload["rom_error"] = client.last_error
            print(json.dumps(payload, indent=2))
        else:
            status = "OK" if info.get("ok") else "FAIL"
            print(f"Health: {status}")
            if info.get("socket"):
                print(f"Socket: {info.get('socket')}")
            if info.get("latency_ms") is not None:
                print(f"Latency: {info.get('latency_ms')} ms")
            if info.get("error"):
                print(f"Error: {info.get('error')}")
            if not rom_loaded:
                print("ROM: not loaded (load screen)")
                print("Hint: python3 scripts/mesen2_client.py rom-load <path-to-rom>")
            else:
                print(f"ROM: {rom_info.get('filename')} (crc32={rom_info.get('crc32')})")
        if not info.get("ok"):
            sys.exit(1)
        return

    if args.command == "capabilities":
        res = client.bridge.capabilities()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                print(json.dumps(res.get("data", {}), indent=2))
            else:
                print(f"Error: {res.get('error', 'Unknown error')}", file=sys.stderr)
                sys.exit(1)
        return

    if args.command == "metrics":
        res = client.bridge.metrics()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                print(json.dumps(res.get("data", {}), indent=2))
            else:
                print(f"Error: {res.get('error', 'Unknown error')}", file=sys.stderr)
                sys.exit(1)
        return

    if args.command == "command-history":
        res = client.bridge.command_history(args.count)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                print(json.dumps(res.get("data", {}), indent=2))
            else:
                print(f"Error: {res.get('error', 'Unknown error')}", file=sys.stderr)
                sys.exit(1)
        return

    if args.command == "agent-register":
        res = client.bridge.register_agent(args.agent_id, agent_name=args.agent_name, version=args.version)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                print(json.dumps(res.get("data", {}), indent=2))
            else:
                print(f"Error: {res.get('error', 'Unknown error')}", file=sys.stderr)
                sys.exit(1)
        return

    if args.command == "rom-info":
        info = client.get_rom_info()
        if args.json:
            print(json.dumps(info, indent=2))
        else:
            if not info:
                print("No ROM loaded")
            else:
                print("=== ROM Info ===")
                for key in ("filename", "crc32", "sha1", "format", "consoleType"):
                    if key in info:
                        print(f"{key}: {info.get(key)}")
        return

    if args.command == "cpu":
        regs = client.get_cpu_state()
        if args.json:
            print(json.dumps(regs, indent=2))
        else:
            if not regs:
                print("No CPU state available")
            else:
                print("=== CPU Registers ===")
                for key in ("A", "X", "Y", "SP", "PC", "K", "DB", "P"):
                    if key in regs:
                        val = regs.get(key)
                        if isinstance(val, int):
                            width = 2 if val <= 0xFF else 4
                            print(f"{key}: ${val:0{width}X}")
                        else:
                            print(f"{key}: {val}")
                flags = regs.get("flags")
                if isinstance(flags, dict):
                    flag_str = "".join([
                        "N" if flags.get("N") else "n",
                        "V" if flags.get("V") else "v",
                        "M" if flags.get("M") else "m",
                        "X" if flags.get("X") else "x",
                        "D" if flags.get("D") else "d",
                        "I" if flags.get("I") else "i",
                        "Z" if flags.get("Z") else "z",
                        "C" if flags.get("C") else "c",
                    ])
                    print(f"Flags: [{flag_str}]")
        return

    if args.command == "pc":
        if args.address:
            try:
                addr = int(args.address.replace("$", "0x"), 16)
            except ValueError:
                print(f"Invalid address: {args.address}")
                sys.exit(1)
            res = client.set_pc(addr)
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                if res.get("success"):
                    print(f"PC set to 0x{addr:06X}")
                else:
                    print(f"Failed: {res.get('error')}")
                    sys.exit(1)
        else:
            info = client.get_pc()
            if args.json:
                print(json.dumps(info, indent=2))
            else:
                full = info.get("full")
                if full is not None:
                    print(f"PC: 0x{full:06X}")
                else:
                    print("PC: unavailable")
        return

    if args.command == "eval":
        res = client.eval_expression(args.expression, cpu_type=args.cpu, use_cache=not args.no_cache)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                data = res.get("data")
                if isinstance(data, dict):
                    value = data.get("hex") or data.get("value")
                    label = data.get("type")
                    if label:
                        print(f"{value} ({label})")
                    else:
                        print(value)
                else:
                    print(data)
            else:
                print(f"Eval failed: {res.get('error')}")
                sys.exit(1)
        return

    if args.command == "expr-eval":
        evaluator = _build_expr_evaluator(client)
        try:
            value = evaluator.evaluate(args.expression)
        except ExprError as exc:
            if args.json:
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            else:
                print(f"Expr error: {exc}")
            sys.exit(1)
        payload = {
            "ok": True,
            "expression": args.expression,
            "value": value,
            "hex": f"0x{value:X}",
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"{args.expression} = {value} (0x{value:X})")
        return

    if args.command == "assert-run":
        evaluator = _build_expr_evaluator(client)
        expressions: list[dict] = []
        if args.expr:
            for expr in args.expr:
                expressions.append({"expr": expr, "source": "inline"})
        else:
            ann_path = Path(args.annotations).expanduser()
            if not ann_path.exists():
                print(f"Annotations not found: {ann_path}")
                print("Hint: python3 z3dk/scripts/generate_annotations.py "
                      f"--root {SCRIPT_DIR.parent} --out {ann_path}")
                sys.exit(2)
            try:
                data = json.loads(ann_path.read_text())
            except json.JSONDecodeError as exc:
                print(f"Invalid annotations.json: {exc}")
                sys.exit(2)
            for entry in data.get("annotations", []):
                if entry.get("type") != "assert":
                    continue
                expr = entry.get("expr") or entry.get("note") or ""
                expressions.append({
                    "expr": expr,
                    "source": entry.get("source", "annotations"),
                })

        results = []
        failed = 0
        errors = 0
        for entry in expressions:
            raw = entry.get("expr", "")
            expr = _normalize_assert_expr(raw)
            if not expr:
                continue
            try:
                value = evaluator.evaluate(expr)
                ok = bool(value)
                if not ok:
                    failed += 1
                results.append({
                    "expression": expr,
                    "source": entry.get("source", ""),
                    "value": value,
                    "ok": ok,
                })
                if args.fail_fast and not ok:
                    break
            except ExprError as exc:
                errors += 1
                results.append({
                    "expression": expr,
                    "source": entry.get("source", ""),
                    "error": str(exc),
                    "ok": False,
                })
                if args.fail_fast:
                    break

        summary = {
            "total": len(results),
            "failed": failed,
            "errors": errors,
            "passed": len([r for r in results if r.get("ok")]),
        }

        if args.json:
            print(json.dumps({"summary": summary, "results": results}, indent=2))
        else:
            print(f"Assert run: {summary['passed']} passed, {failed} failed, {errors} errors")
            for entry in results:
                if entry.get("ok"):
                    continue
                src = entry.get("source", "")
                if entry.get("error"):
                    print(f"ERROR {src}: {entry.get('expression')} -> {entry.get('error')}")
                else:
                    value = entry.get("value")
                    print(f"FAIL  {src}: {entry.get('expression')} (value={value})")

        if args.strict and (failed or errors):
            sys.exit(1)
        return

    if args.command == "mem-read":
        try:
            addr = int(args.addr.replace("$", "0x"), 16)
        except ValueError:
            print(f"Invalid address: {args.addr}")
            sys.exit(1)
        data = client.read_block(addr, args.len, memtype=args.memtype.upper())
        if args.json:
            print(json.dumps({"addr": f"0x{addr:06X}", "len": args.len, "bytes": data.hex()}, indent=2))
        else:
            hex_str = " ".join(data.hex()[i:i+2].upper() for i in range(0, len(data.hex()), 2))
            print(f"0x{addr:06X}: {hex_str}")
        return

    if args.command == "mem-write":
        try:
            addr = int(args.addr.replace("$", "0x"), 16)
        except ValueError:
            print(f"Invalid address: {args.addr}")
            sys.exit(1)
        raw = args.values.replace(",", " ").split()
        try:
            data = bytes(int(b, 16) for b in raw)
        except ValueError:
            print("Invalid hex bytes")
            sys.exit(1)
        ok = client.write_block(addr, data, memtype=args.memtype.upper())
        if args.json:
            print(json.dumps({"ok": ok, "addr": f"0x{addr:06X}", "len": len(data)}, indent=2))
        else:
            print("Write OK" if ok else "Write failed")
        if not ok:
            sys.exit(1)
        return

    if args.command == "mem-size":
        res = client.memory_size(memtype=args.memtype)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                print(res.get("data"))
            else:
                print(f"Error: {res.get('error')}")
                sys.exit(1)
        return

    if args.command == "mem-search":
        if not args.pattern and not args.value:
            print("Provide --pattern or --value")
            sys.exit(1)
        start = int(args.start.replace("$", "0x"), 16) if args.start else None
        end = int(args.end.replace("$", "0x"), 16) if args.end else None
        if args.value:
            val = int(args.value.replace("$", "0x"), 16)
            pattern = val.to_bytes(args.size, "little").hex().upper()
            pattern = " ".join(pattern[i:i+2] for i in range(0, len(pattern), 2))
        else:
            pattern = args.pattern
        matches = client.bridge.search_memory(pattern, memtype=args.memtype, start=start, end=end)
        payload = {"count": len(matches), "matches": [f"0x{m:06X}" for m in matches]}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Found {payload['count']} match(es)")
            for m in payload["matches"][:20]:
                print(f"  {m}")
            if payload["count"] > 20:
                print(f"  ... ({payload['count'] - 20} more)")
        return

    if args.command == "mem-snapshot":
        ok = client.bridge.create_snapshot(args.name, memtype=args.memtype)
        payload = {"ok": ok, "name": args.name, "memtype": args.memtype}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Snapshot '{args.name}' saved ({args.memtype})" if ok else "Snapshot failed")
        if not ok:
            sys.exit(1)
        return

    if args.command == "mem-diff":
        changes = client.bridge.diff_snapshot(args.name)
        payload = {"snapshot": args.name, "count": len(changes), "changes": changes}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Changes for '{args.name}': {payload['count']}")
            for change in changes[:20]:
                addr = change.get("addr", 0)
                old_val = change.get("old", 0)
                new_val = change.get("new", 0)
                print(f"  0x{addr:06X}: 0x{old_val:02X} -> 0x{new_val:02X}")
            if payload["count"] > 20:
                print(f"  ... ({payload['count'] - 20} more)")
        return

    if args.command == "cheat":
        if args.cheat_cmd == "add":
            ok = client.bridge.add_cheat(args.code, format=args.format)
            payload = {"ok": ok, "code": args.code, "format": args.format}
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print("Cheat added" if ok else "Cheat add failed")
            if not ok:
                sys.exit(1)
        elif args.cheat_cmd == "list":
            cheats = client.bridge.list_cheats()
            payload = {"count": len(cheats), "cheats": cheats}
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                if not cheats:
                    print("No cheats configured.")
                else:
                    for cheat in cheats:
                        code = cheat.get("code", "")
                        ctype = cheat.get("type", "")
                        print(f"{code} ({ctype})")
        elif args.cheat_cmd == "clear":
            ok = client.bridge.clear_cheats()
            payload = {"ok": ok}
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print("Cheats cleared" if ok else "Cheat clear failed")
            if not ok:
                sys.exit(1)
        else:
            print("Choose a cheat command: add, list, clear")
            sys.exit(1)
        return

    if args.command == "screenshot":
        shot = client.screenshot()
        if not shot:
            print("Screenshot failed")
            sys.exit(1)
        if args.out:
            out_path = Path(args.out).expanduser()
            out_path.write_bytes(shot)
            if args.json:
                print(json.dumps({"path": str(out_path)}, indent=2))
            else:
                print(f"Saved: {out_path}")
        else:
            import base64
            b64 = base64.b64encode(shot).decode("ascii")
            if args.json:
                print(json.dumps({"png_base64": b64}, indent=2))
            else:
                print(b64)
        return

    if args.command == "run":
        seconds = max(0.0, args.seconds)
        frames = max(0, args.frames)
        pause_after = args.pause_after == "true"
        if seconds <= 0 and frames <= 0:
            print("Provide --seconds and/or --frames")
            sys.exit(1)
        run_state = client.get_run_state()
        was_paused = bool(run_state.get("paused")) if run_state else False
        if seconds > 0 and was_paused:
            client.resume()
        if seconds > 0:
            time.sleep(seconds)
        if frames > 0:
            client.run_frames(frames)
        if pause_after or was_paused:
            client.pause()
        print(f"Ran for {seconds:.2f}s and {frames} frame(s)")
        return

    if args.command == "speed":
        if args.multiplier is None:
            fps = client.bridge.get_speed()
            payload = {"fps": fps}
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"FPS: {fps:.2f}")
            return

        try:
            multiplier = float(args.multiplier)
        except ValueError:
            print(f"Invalid multiplier: {args.multiplier}")
            sys.exit(1)
        ok = client.bridge.set_speed(multiplier)
        payload = {"ok": ok, "multiplier": multiplier}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Speed set to {multiplier}x" if ok else "Speed update failed")
        if not ok:
            sys.exit(1)
        return

    if args.command == "rewind":
        seconds = max(0, args.seconds)
        if seconds <= 0:
            print("Provide --seconds > 0")
            sys.exit(1)
        ok = client.bridge.rewind(seconds)
        payload = {"ok": ok, "seconds": seconds}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Rewound {seconds}s" if ok else "Rewind failed")
        if not ok:
            sys.exit(1)
        return

    if args.command == "p-watch":
        if args.p_cmd == "start":
            res = client.p_watch_start(depth=args.depth)
        elif args.p_cmd == "stop":
            res = client.p_watch_stop()
        else:
            res = client.p_watch_status()
        print(json.dumps(res, indent=2))
        return

    if args.command == "p-log":
        res = client.p_log(count=args.count)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                print(json.dumps(res.get("data", []), indent=2))
            else:
                print(f"Error: {res.get('error')}")
                sys.exit(1)
        return

    if args.command == "p-assert":
        try:
            addr = int(args.addr.replace("$", "0x"), 16)
            expected = int(args.expected.replace("$", "0x"), 16)
            mask = int(args.mask.replace("$", "0x"), 16)
        except ValueError:
            print("Invalid hex value")
            sys.exit(1)
        res = client.p_assert(addr, expected, mask)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                print(res.get("data"))
            else:
                print(f"Error: {res.get('error')}")
                sys.exit(1)
        return

    if args.command == "mem-watch":
        if args.mem_watch_cmd == "add":
            addr = int(args.addr.replace("$", "0x"), 16)
            res = client.mem_watch_add(addr, size=args.size, depth=args.depth)
        elif args.mem_watch_cmd == "remove":
            res = client.mem_watch_remove(args.id)
        elif args.mem_watch_cmd == "clear":
            res = client.mem_watch_clear()
        else:
            res = client.mem_watch_list()
        print(json.dumps(res, indent=2))
        return

    if args.command == "mem-blame":
        addr = int(args.addr.replace("$", "0x"), 16) if args.addr else None
        res = client.mem_blame(watch_id=args.watch_id, addr=addr)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                print(json.dumps(res.get("data", []), indent=2))
            else:
                print(f"Error: {res.get('error')}")
                sys.exit(1)
        return

    if args.command == "symbols-load":
        res = client.symbols_load(args.path, clear=args.clear)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                print(res.get("data"))
            else:
                print(f"Error: {res.get('error')}")
                sys.exit(1)
        return

    if args.command == "collision-overlay":
        enabled = True
        if args.disable:
            enabled = False
        elif args.enable:
            enabled = True
        highlight = None
        if args.highlight:
            try:
                highlight = [int(x.strip(), 16) for x in args.highlight.split(",") if x.strip()]
            except ValueError:
                print("Invalid highlight list")
                sys.exit(1)
        res = client.collision_overlay(enabled=enabled, colmap=args.colmap, highlight=highlight)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                print(res.get("data"))
            else:
                print(f"Error: {res.get('error')}")
                sys.exit(1)
        return

    if args.command == "collision-dump":
        res = client.collision_dump(colmap=args.colmap)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                print(json.dumps(res.get("data", {}), indent=2))
            else:
                print(f"Error: {res.get('error')}")
                sys.exit(1)
        return

    if args.command == "draw-path":
        points: list[tuple[int, int]] = []
        if args.points:
            parts = [p.strip() for p in args.points.split(",") if p.strip()]
            if len(parts) % 2 != 0:
                print("draw-path: expected even number of coordinates (x,y pairs)")
                sys.exit(1)
            try:
                for i in range(0, len(parts), 2):
                    x = int(parts[i].replace("$", "0x"), 0)
                    y = int(parts[i + 1].replace("$", "0x"), 0)
                    points.append((x, y))
            except ValueError:
                print("draw-path: invalid coordinate value")
                sys.exit(1)
        ok = client.draw_path(points, color=args.color, frames=args.frames)
        if args.json:
            print(json.dumps({"success": bool(ok)}, indent=2))
        else:
            print("OK" if ok else "Failed")
        return

    if args.command == "lua":
        code = args.code
        if args.file:
            code = Path(args.file).read_text()
        if not code:
            print("Provide Lua code or --file")
            sys.exit(1)
        res = client.execute_lua(code)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("error"):
                print(f"Error: {res['error']}")
                sys.exit(1)
            print(res)
        return

    if args.command == "load-script":
        script_path = Path(args.path).expanduser()
        if not script_path.exists():
            print(f"Script not found: {script_path}")
            sys.exit(1)
        script_id = client.bridge.load_script(name=args.name, path=str(script_path))
        payload = {"id": script_id}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            if script_id >= 0:
                print(f"Loaded script (id={script_id})")
            else:
                print("Load failed")
                sys.exit(1)
        return

    if args.command == "state-compare":
        regions = [r.strip() for r in args.regions.split(",")] if args.regions else None
        differ = StateDiffer(client)
        result = differ.diff_states(slot_a=args.slot_a, slot_b=args.slot_b, regions=regions)
        if args.format == "markdown":
            print(result.to_markdown())
        else:
            print(json.dumps(result.to_dict(), indent=2))
        return

    if args.command == "rom-load":
        stop = None
        if args.stop is not None:
            stop = args.stop.lower() == "true"
        powercycle = None
        if args.powercycle is not None:
            powercycle = args.powercycle.lower() == "true"
        ok = client.load_rom(args.path, patch=args.patch, stop=stop, powercycle=powercycle)
        if args.json:
            print(json.dumps({"ok": ok, "rom": args.path, "error": client.last_error}, indent=2))
        else:
            if ok:
                print(f"Loaded ROM: {args.path}")
            else:
                print(f"Failed to load ROM: {client.last_error}")
        if not ok:
            sys.exit(1)
        return

    if args.command == "socket-cleanup":
        from .bridge import cleanup_stale_sockets
        removed = cleanup_stale_sockets(verbose=not args.json)
        if args.json:
            print(json.dumps({"removed": removed, "count": len(removed)}, indent=2))
        else:
            if removed:
                print(f"Removed {len(removed)} stale socket(s)")
            else:
                print("No stale sockets found")
        return

    if not client.is_connected():
        print("ERROR: Cannot connect to Mesen2. Is it running with socket enabled?")
        print("Looking for socket at: /tmp/mesen2-*.sock")
        sys.exit(1)

    elif args.command == "debug-context":
        manifest = client.get_library_manifest()
        
        context = {
            "watch_profiles": {name: p["description"] for name, p in WATCH_PROFILES.items()},
            "items": {name: desc for name, (addr, desc, vals) in ITEMS.items()},
            "flags": {name: desc for name, (addr, desc, mask) in STORY_FLAGS.items()},
            "canon_states": [
                {
                    "id": e["id"], 
                    "desc": e.get("description") or e.get("label"), 
                    "location": e.get("meta", {}).get("location")
                } 
                for e in manifest.get("entries", []) if e.get("status") == "canon"
            ],
            "usdasm": {
                "loaded": len(client._usdasm_labels) > 0,
                "label_count": len(client._usdasm_labels)
            }
        }
        
        if args.json:
            print(json.dumps(context, indent=2))
        else:
            print("=== Debugging Context ===")
            print(f"Watch Profiles: {len(context['watch_profiles'])}")
            print(f"Items: {len(context['items'])} | Flags: {len(context['flags'])}")
            print(f"Canon States: {len(context['canon_states'])}")
            print(f"USDASM Labels: {'Loaded' if context['usdasm']['loaded'] else 'Not Loaded'} ({context['usdasm']['label_count']})")
            print("\nTip: Use --json for the full metadata payload.")
        return

    elif args.command == "state":
        state = client.get_oracle_state()
        if args.json:
            print(json.dumps(state, indent=2))
        else:
            print("=== Oracle Game State ===")
            print(f"Mode: {state['mode_name']} (0x{state['mode']:02X})")
            print(f"Location: {state['area_name']}")
            print(f"Area: 0x{state['area']:02X} | Room: 0x{state['room']:02X}")
            if state['indoors']:
                print(f"Dungeon Room: 0x{state['dungeon_room']:02X} ({state['room_name']})")
            print(f"Indoors: {bool(state['indoors'])}")
            print(f"Link: ({state['link_x']}, {state['link_y']}, Z={state['link_z']})")
            print(f"Direction: {state['link_dir_name']}")
            print(f"Form: {state['link_form_name']} (0x{state['link_form']:02X})")
            print(f"Scroll: ({state['scroll_x']}, {state['scroll_y']})")

            # Time system (Oracle custom)
            print(f"\n=== Time System ===")
            print(f"Time: {state['time_hours']:02d}:{state['time_minutes']:02d}")
            print(f"Speed: {state['time_speed']}")

            # Player stats
            print(f"\n=== Player Stats ===")
            print(f"Health: {state['health']}/{state['max_health']}")
            print(f"Magic: {state['magic']}")
            print(f"Rupees: {state['rupees']}")

            # Check for issues
            warnings = client.check_known_issues(state)
            if warnings:
                print("\n=== Warnings ===")
                for w in warnings:
                    print(w)

    elif args.command == "run-state":
        run_state = client.get_run_state()
        if args.json:
            print(json.dumps(run_state, indent=2))
        else:
            running = run_state.get("running")
            paused = run_state.get("paused")
            frame = run_state.get("frame")
            fps = run_state.get("fps")
            print("=== Emulator Run State ===")
            print(f"Running: {running}")
            print(f"Paused: {paused}")
            if frame is not None:
                print(f"Frame: {frame}")
            if fps is not None:
                print(f"FPS: {fps}")

    elif args.command == "time":
        time_state = client.get_time_state()
        if args.json:
            print(json.dumps(time_state, indent=2))
        else:
            print("=== Time System ===")
            print(f"Time: {time_state['hours']:02d}:{time_state['minutes']:02d}")
            print(f"Phase: {time_state['phase']} (night={time_state['is_night']})")
            print(f"Speed: {time_state['speed']}")
            print(f"SubColor: {time_state['subcolor']}")
            palette = time_state.get("palette", {})
            print(f"Palette: R={palette.get('red')} G={palette.get('green')} B={palette.get('blue')}")

    elif args.command == "diagnostics":
        diagnostics = client.get_diagnostics(deep=args.deep)
        if args.json:
            print(json.dumps(diagnostics, indent=2))
        else:
            run_state = diagnostics.get("run_state", {})
            rom_info = diagnostics.get("rom_info", {})
            time_state = diagnostics.get("time_state", {})
            overworld = diagnostics.get("overworld", {})
            camera = diagnostics.get("camera", {})
            items = diagnostics.get("items", {})
            flags = diagnostics.get("flags", {})
            story = diagnostics.get("story_state", {})
            watch_profile = diagnostics.get("watch_profile", "")
            watch_values = diagnostics.get("watch_values", {})
            sprites = diagnostics.get("sprites", [])

            print("=== Diagnostic Snapshot ===")
            print(f"Paused: {run_state.get('paused')} | Running: {run_state.get('running')}")
            if rom_info:
                print(f"ROM: {rom_info.get('filename')} (crc32={rom_info.get('crc32')})")
            print(f"Mode: {overworld.get('mode_name')} (0x{overworld.get('mode', 0):02X})")
            print(f"Submode: {overworld.get('submode_name')} (0x{overworld.get('submode', 0):02X})")
            print(f"Indoors: {overworld.get('indoors')} | Overworld: {overworld.get('is_overworld')}")
            print(f"Transition: {overworld.get('is_transition')}")
            print(f"Time: {time_state.get('hours', 0):02d}:{time_state.get('minutes', 0):02d} ({time_state.get('phase')})")
            print(f"Camera offsets: x={camera.get('offset_x')} y={camera.get('offset_y')}")
            if not diagnostics.get("camera_ok", True):
                print("WARN: Camera offset exceeds expected bounds.")
            warnings = diagnostics.get("warnings", [])
            if warnings:
                print("\n=== Warnings ===")
                for w in warnings:
                    print(w)
            if args.deep:
                if story:
                    print(f"Story: game_state={story.get('game_state')} oosprog=0x{story.get('oosprog', 0):02X}")
                if items:
                    non_zero = sum(1 for item in items.values() if item.get("value", 0))
                    print(f"Items: {non_zero}/{len(items)} non-zero")
                if flags:
                    set_flags = sum(1 for flag in flags.values() if flag.get("is_set"))
                    print(f"Flags: {set_flags}/{len(flags)} set")
                if watch_profile:
                    print(f"Watch profile: {watch_profile} ({len(watch_values)} values)")
                if sprites:
                    print(f"Sprites: {len(sprites)} active")
                print("Tip: use --deep --json for full diagnostic payload.")

    elif args.command == "story":
        story = client.get_story_state()
        if args.json:
            print(json.dumps(story, indent=2))
        else:
            print("=== Story Progress ===")
            print(f"GameState: {story['game_state']}")
            print(f"OOSPROG: 0x{story['oosprog']:02X}")
            print(f"OOSPROG2: 0x{story['oosprog2']:02X}")
            print(f"SideQuest: 0x{story['side_quest']:02X}")
            print(f"Crystals: 0x{story['crystals']:02X}")
            print(f"Pendants: 0x{story['pendants']:02X}")
            print(f"Maku Tree Met: {bool(story['maku_tree_quest'])}")
            print(f"In Cutscene: {bool(story['in_cutscene'])}")

    elif args.command == "watch":
        if not client.set_watch_profile(args.profile):
            print(f"Unknown profile: {args.profile}")
            print(f"Available: {', '.join(WATCH_PROFILES.keys())}")
            sys.exit(1)

        values = client.read_watch_values()
        profile_info = WATCH_PROFILES[args.profile]

        if args.json:
            print(json.dumps({"profile": args.profile, "values": values}, indent=2))
        else:
            print(f"=== Watch Profile: {args.profile} ===")
            print(f"({profile_info['description']})")
            for name, val in values.items():
                print(f"  {name}: {val}")

    elif args.command == "breakpoint":
        if args.profile:
            profile = BREAKPOINT_PROFILES.get(args.profile)
            if not profile:
                print(f"Unknown profile: {args.profile}")
                print(f"Available: {', '.join(BREAKPOINT_PROFILES.keys())}")
                sys.exit(1)
            
            print(f"Loading profile: {args.profile} ({profile['description']})")
            count = 0
            for bp in profile["breakpoints"]:
                client.add_breakpoint(address=bp["addr"], mode=bp.get("type", "exec"))
                print(f"  + Breakpoint at 0x{bp['addr']:06X} ({bp['desc']})")
                count += 1
            if args.json:
                print(json.dumps({"profile": args.profile, "count": count}, indent=2))

        elif args.add:
            # Format: addr or addr:type
            parts = args.add.split(":")
            addr_str = parts[0]
            mode = parts[1] if len(parts) > 1 else "exec"
            
            if addr_str.startswith("0x") or addr_str.startswith("$"):
                addr = int(addr_str.replace("$", "0x"), 16)
            else:
                addr = client.resolve_symbol(addr_str)
                if addr is None:
                    print(f"Error: Could not resolve symbol '{addr_str}'")
                    sys.exit(1)
            
            client.add_breakpoint(address=addr, mode=mode)
            print(f"Added {mode} breakpoint at 0x{addr:06X}")
            if args.json:
                print(json.dumps({"action": "add", "address": addr, "mode": mode}, indent=2))

        elif args.remove:
            ok = client.bridge.remove_breakpoint(args.remove)
            if args.json:
                print(json.dumps({"action": "remove", "id": args.remove, "ok": ok}, indent=2))
            else:
                print("Removed breakpoint" if ok else "Failed to remove breakpoint")
            if not ok:
                sys.exit(1)

        elif args.clear:
            ok = client.bridge.clear_breakpoints()
            if args.json:
                print(json.dumps({"action": "clear", "ok": ok}, indent=2))
            else:
                print("Cleared all breakpoints." if ok else "Failed to clear breakpoints")
            if not ok:
                sys.exit(1)

        elif args.list:
            bps = client.bridge.list_breakpoints()
            if args.json:
                print(json.dumps({"breakpoints": bps}, indent=2))
            else:
                if not bps:
                    print("No breakpoints set")
                else:
                    print("=== Breakpoints ===")
                    for bp in bps:
                        addr = bp.get("addr") or bp.get("start")
                        bptype = bp.get("type") or bp.get("bptype")
                        bp_id = bp.get("id")
                        print(f"{bp_id}: {addr} ({bptype})")

        else:
            print("Usage: breakpoint --profile <name> OR --add <addr> OR --remove <id> OR --list OR --clear")

    elif args.command == "trace":
        if args.action:
            try:
                labels = _coerce_bool(args.labels)
                indent = _coerce_bool(args.indent)
            except ValueError as exc:
                print(f"Error: {exc}")
                sys.exit(1)

            res = client.trace_control(
                args.action,
                format=args.format,
                condition=args.condition,
                labels=labels,
                indent=indent,
                clear=args.clear if args.action == "start" else None,
            )
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                if res.get("success"):
                    data = res.get("data")
                    if isinstance(data, dict):
                        print(f"Trace {args.action}: {data}")
                    elif data is not None:
                        print(f"Trace {args.action}: {data}")
                    else:
                        print(f"Trace {args.action}: OK")
                else:
                    print(f"Trace {args.action} failed: {res.get('error')}")
                    sys.exit(1)
            return

        count = max(1, args.count)
        offset = max(0, args.offset)
        success, entries = client.trace(count=count, offset=offset)
        payload = {"success": success, "count": len(entries), "offset": offset, "entries": entries}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            if not success:
                print(f"Trace fetch failed: {client.last_error}")
                sys.exit(1)
            print(f"=== Trace ({len(entries)} entries, offset={offset}) ===")
            for row in entries:
                pc = row.get("pc") or row.get("address") or ""
                bytecode = row.get("bytes") or row.get("bytecode") or ""
                disasm = row.get("disasm") or row.get("instruction") or ""
                line = f"  {pc}: {bytecode} {disasm}".rstrip()
                print(line if pc else f"  {row}")

    elif args.command == "trace-run":
        try:
            labels = _coerce_bool(args.labels)
        except ValueError as exc:
            print(f"Error: {exc}")
            sys.exit(1)

        client.trace_control(
            "start",
            format=args.format,
            condition=args.condition,
            labels=labels,
            clear=args.clear,
        )
        client.run_frames(max(1, int(args.frames)))
        client.trace_control("stop")

        count = max(1, int(args.count))
        offset = max(0, int(args.offset))
        success, entries = client.trace(count=count, offset=offset)
        if not success:
            print(f"Trace fetch failed: {client.last_error}")
            sys.exit(1)

        output_lines = [json.dumps(entry) for entry in entries]
        if args.output:
            output_path = Path(args.output).expanduser()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("\n".join(output_lines) + ("\n" if output_lines else ""))
            print(f"Wrote {len(entries)} trace entries to {output_path}")
        else:
            for line in output_lines:
                print(line)

    elif args.command == "freeze-guard":
        progressed = client.ensure_frame_progress(frames=max(1, int(args.frames)))
        payload = {
            "ok": progressed,
            "frames": args.frames,
            "capture": None,
        }
        if progressed:
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print("Frame counter advanced; no freeze detected.")
            return

        out_dir = Path(args.out_dir).expanduser()
        capture = capture_debug_snapshot(
            client,
            out_dir,
            watch_profile=args.watch_profile,
            prefix=args.prefix,
            screenshot=not args.no_screenshot,
        )
        payload["capture"] = capture

        if args.save_slot is not None:
            saved = client.save_state(slot=int(args.save_slot))
            payload["saved_slot"] = int(args.save_slot)
            payload["saved_ok"] = bool(saved)

        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("Freeze detected; captured snapshot.")
            if capture:
                print(f"  JSON: {capture.get('json')}")
                if capture.get("screenshot"):
                    print(f"  Screenshot: {capture.get('screenshot')}")
            if args.save_slot is not None:
                print(f"  Saved slot {args.save_slot}: {'OK' if payload.get('saved_ok') else 'FAIL'}")
        sys.exit(1)

    elif args.command == "step":
        if args.pause:
            client.ensure_paused()
        count = max(1, int(args.count))
        res = client.step(count=count, mode=args.mode)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res is True:
                print(f"Stepped {count} instruction(s) ({args.mode}).")
            elif isinstance(res, dict) and res.get("success"):
                print(f"Stepped {count} instruction(s) ({args.mode}).")
            else:
                print(f"Step failed: {res}")
                sys.exit(1)

    elif args.command == "sprites":
        if args.all:
            sprites = client.get_all_sprites()
            if args.json:
                print(json.dumps(sprites, indent=2))
            else:
                print(f"=== Active Sprites ({len(sprites)}) ===")
                for spr in sprites:
                    print(
                        f"  Slot {spr['slot']}: Type=0x{spr['type']:02X} "
                        f"State=0x{spr['state']:02X} "
                        f"Pos=({spr['x']},{spr['y']}) "
                        f"Action={spr['action']} HP={spr['health']}"
                    )
        else:
            slot = client.get_sprite_slot(args.slot)
            if args.json:
                print(json.dumps(slot, indent=2))
            else:
                print(f"=== Sprite Slot {args.slot} ===")
                print(f"  Type: 0x{slot['type']:02X}")
                print(f"  State: 0x{slot['state']:02X}")
                print(f"  Position: ({slot['x']}, {slot['y']})")
                print(f"  Action: {slot['action']}")
                print(f"  Health: {slot['health']}")
                print(f"  TimerA: {slot['timer_a']}")
                print(f"  TimerB: {slot['timer_b']}")
                print(f"  TimerD: {slot['timer_d']}")
                print(f"  Parent: {slot['parent']}")

    elif args.command == "assistant":
        print("=== Debug Assistant Mode ===")
        print("Monitoring area changes and known issues...")
        print("Press Ctrl+C to exit")
        print()

        last_area = None
        while True:
            try:
                state = client.get_oracle_state()
                current_area = state["area"]

                if current_area != last_area:
                    msg = client.on_area_change(current_area)
                    print(msg)
                    print(f"  Mode: {state['mode_name']}")
                    print(f"  Profile: {client._watch_profile}")

                    values = client.read_watch_values()
                    for name, val in values.items():
                        print(f"  {name}: {val}")

                    warnings = client.check_known_issues(state)
                    for w in warnings:
                        print(w)
                    print()

                last_area = current_area
                time.sleep(0.1)  # 10Hz polling

            except KeyboardInterrupt:
                print("\nExiting.")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(1)

    # === NEW COMMAND HANDLERS ===

    elif args.command == "items":
        if args.item:
            try:
                val, desc = client.get_item(args.item)
                if args.json:
                    print(json.dumps({"item": args.item, "value": val, "description": desc}))
                else:
                    print(f"{args.item}: {desc} (value={val})")
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
        else:
            # Show all items with values
            items = client.get_all_items()
            if args.json:
                print(json.dumps(items, indent=2))
            else:
                print("=== Current Items ===")
                for name, data in items.items():
                    if data["value"] != 0:
                        print(f"  {name}: {data['description']} (value={data['value']})")

    elif args.command == "give":
        try:
            if client.set_item(args.item, args.value):
                print(f"Set {args.item} = {args.value}")
            else:
                print(f"Failed to set {args.item}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "flags":
        if args.flag:
            try:
                val, is_set = client.get_flag(args.flag)
                if args.json:
                    print(json.dumps({"flag": args.flag, "value": val, "is_set": is_set}))
                else:
                    print(f"{args.flag}: {'SET' if is_set else 'NOT SET'} (raw=0x{val:02X})")
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
        else:
            # Show all flags with values
            flags = client.get_all_flags()
            if args.json:
                print(json.dumps(flags, indent=2))
            else:
                print("=== Current Flags ===")
                for name, data in flags.items():
                    status = "SET" if data["is_set"] else "---"
                    print(f"  {name}: {status} (0x{data['value']:02X})")

    elif args.command == "setflag":
        try:
            # Parse value - could be number or true/false
            if args.value.lower() in ("true", "1", "yes", "on"):
                value = True
            elif args.value.lower() in ("false", "0", "no", "off"):
                value = False
            else:
                value = int(args.value, 0)

            if client.set_flag(args.flag, value):
                print(f"Set {args.flag} = {value}")
            else:
                print(f"Failed to set {args.flag}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "press":
        ok = client.press_button(args.buttons, args.frames, ensure_running=not args.allow_paused)
        if ok:
            print(f"Pressed: {args.buttons}")
        else:
            if client.last_error:
                print(f"Button press failed: {client.last_error}")
            else:
                print("Button press failed")

    elif args.command == "pos":
        if client.set_position(args.x, args.y):
            print(f"Set position to ({args.x}, {args.y})")
        else:
            print("Position set failed")

    elif args.command == "move":
        if args.direction:
            ok = client.hold_direction(args.direction, frames=args.distance)
            if ok:
                print(f"Moved {args.direction} for {args.distance} frames")
            else:
                print(f"Movement failed: {client.last_error}")
        else:
            # Delegate to navigate logic
            try:
                sys.path.insert(0, str(Path.home() / ".claude" / "skills" / "hyrule-navigator" / "scripts"))
                from navigator import HyruleNavigator
            except ImportError:
                print("Error: hyrule-navigator skill not installed (required for --to/--to-poi)")
                sys.exit(1)

            nav = HyruleNavigator(timeout_frames=args.timeout)
            nav.bridge = client.bridge
            nav.client = client

            if args.to_poi:
                result = nav.goto_poi(args.to_poi)
            elif args.to:
                x, y = map(int, args.to.split(","))
                result = nav.goto_position(x, y)
            
            print(f"Movement: {result.status.name}")
            if result.error:
                print(f"  Error: {result.error}")

    elif args.command == "navigate":
        # Import navigation module
        try:
            sys.path.insert(0, str(Path.home() / ".claude" / "skills" / "hyrule-navigator" / "scripts"))
            from navigator import HyruleNavigator, NavResult
        except ImportError:
            print("Error: hyrule-navigator skill not installed")
            print("Install at: ~/.claude/skills/hyrule-navigator/")
            sys.exit(1)

        nav = HyruleNavigator(
            timeout_frames=args.timeout,
            safe_mode=not args.no_safe
        )
        # Reuse existing connection
        nav.bridge = client.bridge
        nav.client = client

        if args.poi:
            result = nav.goto_poi(args.poi)
        elif args.area:
            area_id = int(args.area, 16) if args.area.startswith("0x") else int(args.area)
            result = nav.goto_area(area_id)
        elif args.pos:
            x, y = map(int, args.pos.split(","))
            result = nav.goto_position(x, y)

        print(f"\nNavigation: {result.status.name}")
        if result.start_pos:
            print(f"  Start: ({result.start_pos[0]}, {result.start_pos[1]})")
        if result.end_pos:
            print(f"  End:   ({result.end_pos[0]}, {result.end_pos[1]})")
        if result.frames_elapsed:
            print(f"  Frames: {result.frames_elapsed}")
        if result.error:
            print(f"  Error: {result.error}")

    elif args.command == "test-hypothesis":
        patches = {}
        # Load from file if provided
        if args.patch_file:
            try:
                with open(args.patch_file, "r") as f:
                    file_patches = json.load(f)
                for addr_str, val in file_patches.items():
                    addr = int(addr_str, 0)
                    patches[addr] = val
            except Exception as e:
                print(f"Error loading patch file: {e}")
                sys.exit(1)
        
        # Load from CLI args
        if args.patch:
            for p in args.patch:
                if ":" not in p:
                    print(f"Error: Invalid patch format '{p}'. Use addr:val")
                    sys.exit(1)
                addr_str, val_str = p.split(":", 1)
                try:
                    addr = int(addr_str, 0)
                    # Check if val is a list of bytes [1, 2, 3]
                    if val_str.startswith("[") and val_str.endswith("]"):
                        val = json.loads(val_str)
                    else:
                        val = int(val_str, 0)
                    patches[addr] = val
                except Exception as e:
                    print(f"Error parsing patch '{p}': {e}")
                    sys.exit(1)
        
        if not patches:
            print("Error: No patches provided. Use --patch or --patch-file")
            sys.exit(1)
            
        print(f"Testing hypothesis on state '{args.state_id}' with {len(patches)} patches...")
        result = client.test_hypothesis(
            args.state_id, 
            patches, 
            timeout_frames=args.frames,
            watch_profile=args.watch
        )
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["passed"]:
                print("PASSED: Hypothesis verified (no warnings, engine active).")
            else:
                print("FAILED: Hypothesis failed verification.")
                for err in result.get("errors", []):
                    print(f"  ERROR: {err}")
                for warn in result.get("warnings", []):
                    print(f"  WARNING: {warn}")
            
        sys.exit(0 if result["passed"] else 1)

    elif args.command == "pause":
        if client.pause():
            print("Paused")
        else:
            print("Pause failed")

    elif args.command == "resume":
        if client.resume():
            print("Resumed")
        else:
            print("Resume failed")

    elif args.command == "disasm":
        addr_str = args.address
        if not addr_str:
            # Get current PC if no address provided
            regs = client.get_cpu_state()
            pc = regs.get("PC", 0)
            pb = regs.get("K", 0) or regs.get("DB", 0)
            addr = (pb << 16) | pc
        else:
            # Try to resolve label if not a hex number
            if addr_str.startswith("0x") or addr_str.startswith("$"):
                addr = int(addr_str.replace("$", "0x"), 16)
            else:
                addr = client.resolve_symbol(addr_str)
                if addr is None:
                    print(f"Error: Could not resolve symbol '{addr_str}'")
                    sys.exit(1)

        lines = client.disassemble(addr, args.count)
        
        # Resolve symbols for each line if possible
        for line in lines:
            line_addr_str = line.get("address", "")
            if line_addr_str:
                line_addr = int(line_addr_str.replace("$", "0x"), 16)
                symbol = client.get_symbol_at(line_addr)
                if symbol:
                    line["symbol"] = symbol

        if args.json:
            print(json.dumps(lines, indent=2))
        else:
            print(f"=== Disassembly at 0x{addr:06X} ===")
            for line in lines:
                symbol_part = f"<{line['symbol']}> " if "symbol" in line else ""
                print(f"  {line.get('address')}: {symbol_part}{line.get('bytes')}  {line.get('instruction')}")

    elif args.command == "reset":
        if client.reset():
            print("Reset")
        else:
            print("Reset failed")

    elif args.command == "frame":
        if client.run_frames(args.count):
            print(f"Advanced {args.count} frame(s)")
        else:
            print("Frame advance failed")

    elif args.command == "save":
        if args.path:
            if client.save_state(path=args.path):
                print(f"Saved to {args.path}")
            else:
                print("Save failed")
        elif args.slot:
            if client.save_state(slot=args.slot):
                print(f"Saved to slot {args.slot}")
            else:
                print("Save failed")
        else:
            print("Usage: save <slot> OR save --path <file>")

    elif args.command == "load":
        if args.path:
            if client.load_state(path=args.path):
                print(f"Loaded from {args.path}")
            else:
                if client.last_error:
                    print(f"Load failed: {client.last_error}")
                else:
                    print("Load failed")
        elif args.slot:
            if client.load_state(slot=args.slot):
                print(f"Loaded from slot {args.slot}")
            else:
                print("Load failed")
        else:
            print("Usage: load <slot> OR load --path <file>")

    elif args.command == "savestate-label":
        if args.slot is None and not args.path:
            print("Usage: savestate-label <get|set|clear> <slot> OR --path <file>")
            sys.exit(1)
        if args.action == "set" and not args.label:
            print("Error: --label is required for action=set")
            sys.exit(1)
        res = client.save_state_label(
            action=args.action,
            slot=args.slot,
            path=args.path,
            label=args.label,
        )
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                label_text = res.get("data") if isinstance(res.get("data"), str) else ""
                if args.action == "get":
                    print(label_text or "(no label)")
                else:
                    print("OK")
            else:
                print(f"Error: {res.get('error', 'Unknown error')}")
                sys.exit(1)

    elif args.command == "smart-save":
        if AgentBrain is None:
            print("Error: Could not import AgentBrain. Run via mesen2_client.py.")
            sys.exit(1)
        
        try:
            print("Initializing Agent Brain...")
            agent = AgentBrain(args.b008_mode)
            print(f"Attempting smart save to slot {args.slot}...")
            agent.validate_and_save(args.slot)
        except Exception as e:
            print(f"Smart Save Error: {e}")
            sys.exit(1)
    elif args.command == "brain-calibrate":
        if AgentBrain is None:
            print("Error: Could not import AgentBrain. Run via mesen2_client.py.")
            sys.exit(1)

        try:
            print("Initializing Agent Brain...")
            agent = AgentBrain("auto")
            mode = agent.calibrate_b008()
            if mode == "unknown":
                print("B008 calibration: unknown (not in gameplay or no movement)")
            else:
                print(f"B008 calibration: {mode}")
        except Exception as e:
            print(f"B008 calibration error: {e}")
            sys.exit(1)

    # === STATE LIBRARY COMMANDS ===

    elif args.command == "repro":
        # 1. Load the state
        try:
            if not client.load_library_state(args.state_id):
                print(f"Error: Failed to load state '{args.state_id}'")
                sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
            
        print(f"Loaded state: {args.state_id}")
        
        # 2. Set watch profile if requested
        if args.watch:
            if client.set_watch_profile(args.watch):
                print(f"Set watch profile: {args.watch}")
            else:
                print(f"Warning: Unknown watch profile '{args.watch}'")
                
        # 3. Start trace if requested
        if args.trace:
            res = client.execute_lua("if DebugBridge and DebugBridge.startTrace then DebugBridge.startTrace() end")
            if res.get("error"):
                print(f"Warning: Failed to start trace: {res.get('error')}")
            else:
                print("Trace started.")
                
        if args.json:
            print(json.dumps({"success": True, "state": args.state_id, "trace": args.trace, "watch": args.watch}, indent=2))
        else:
            print("\nReady for reproduction.")

    elif args.command == "library":
        entries = client.list_library_entries(tag=args.tag)
        if args.json:
            print(json.dumps(entries, indent=2))
        else:
            if not entries:
                print("No entries in library" + (f" with tag '{args.tag}'" if args.tag else ""))
                print(f"Manifest path: {MANIFEST_PATH}")
            else:
                print(f"=== State Library ({len(entries)} entries) ===")
                for entry in entries:
                    tags = ", ".join(entry.get("tags", []))
                    desc = entry.get("description") or entry.get("label") or "No description"
                    status = entry.get("status", "draft")
                    status_badge = {"canon": "[CANON]", "deprecated": "[DEPR]", "draft": "[draft]"}.get(status, "[?]")
                    print(f"  {status_badge} {entry['id']}: {desc}")
                    if tags:
                        print(f"         Tags: {tags}")

    elif args.command == "lib-save":
        try:
            captured_by = getattr(args, "captured_by", "agent")
            state_id, warnings = client.save_library_state(
                args.label, tags=args.tags, captured_by=captured_by
            )
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
        if args.json:
            print(json.dumps({
                "state_id": state_id,
                "label": args.label,
                "tags": args.tags or [],
                "status": "draft",
                "warnings": warnings
            }, indent=2))
        else:
            print(f"Saved: {args.label} ({state_id}) [status: draft]")
            for warn in warnings:
                print(f"  WARNING: {warn}")

    elif args.command == "lib-scan":
        try:
            added = client.scan_library()
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
        if args.json:
            print(json.dumps({"added": added}, indent=2))
        else:
            print(f"Added {added} entr{'y' if added == 1 else 'ies'} from library scan")

    elif args.command == "lib-verify":
        try:
            if client.verify_library_state(args.state_id, verified_by=args.verified_by):
                if args.json:
                    print(json.dumps({
                        "state_id": args.state_id,
                        "status": "canon",
                        "verified_by": args.verified_by
                    }, indent=2))
                else:
                    print(f"Verified: {args.state_id} -> canon (by {args.verified_by})")
            else:
                entry = client.find_library_entry(args.state_id)
                if entry:
                    print(f"State '{args.state_id}' is already canon")
                else:
                    print(f"State '{args.state_id}' not found")
                    sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "lib-deprecate":
        try:
            if client.deprecate_library_state(args.state_id, reason=args.reason):
                if args.json:
                    print(json.dumps({
                        "state_id": args.state_id,
                        "status": "deprecated",
                        "reason": args.reason
                    }, indent=2))
                else:
                    print(f"Deprecated: {args.state_id}")
                    if args.reason:
                        print(f"  Reason: {args.reason}")
            else:
                print(f"State '{args.state_id}' not found")
                sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "lib-verify-all":
        manifest = client.get_library_manifest()
        entries = [e for e in manifest.get("entries", []) if e.get("status") == "canon"]
        
        if not entries:
            print("No canon states to verify.")
            return
            
        from .state_validator import StateValidator
        validator = StateValidator()
        results = []
        
        print(f"Verifying {len(entries)} canon states...")
        for entry in entries:
            state_id = entry["id"]
            print(f"  Loading {state_id}...", end="", flush=True)
            
            try:
                ok = client.load_library_state(state_id)
                if not ok:
                    print(" LOAD FAILED")
                    results.append({"id": state_id, "valid": False, "error": "Load failed"})
                    continue
                
                # Wait a few frames for engine to settle
                client.run_frames(2)
                
                # Validate metadata
                # Map library metadata format to validator expected format
                meta = entry.get("meta", {})
                expected = {
                    "gameState": {
                        "mode": meta.get("module"),
                        "room": meta.get("room"),
                        "overworldArea": meta.get("area"),
                        "indoors": meta.get("indoors") == "true" or meta.get("indoors") is True
                    },
                    "linkState": {
                        "x": int(meta.get("link_x", 0)) if meta.get("link_x") else None,
                        "y": int(meta.get("link_y", 0)) if meta.get("link_y") else None
                    }
                }
                
                res = validator.validate(client.bridge, expected, state_id=state_id)
                
                # Also check if frame counter is still advancing
                stalled = not client.ensure_frame_progress(frames=10)
                if stalled:
                    res.valid = False
                    res.errors.append("Game engine stalled (frame counter not advancing)")
                
                if res.valid:
                    print(" OK")
                else:
                    print(f" INVALID: {', '.join(res.errors)}")
                
                results.append({
                    "id": state_id,
                    "valid": res.valid,
                    "errors": res.errors,
                    "warnings": res.warnings
                })
                
            except Exception as e:
                print(f" ERROR: {e}")
                results.append({"id": state_id, "valid": False, "error": str(e)})

        total_valid = sum(1 for r in results if r["valid"])
        if args.json:
            print(json.dumps({"results": results, "total": len(results), "valid": total_valid}, indent=2))
        else:
            print(f"\nVerification complete: {total_valid}/{len(results)} canon states valid.")
            if total_valid < len(results):
                sys.exit(1)

    elif args.command == "lib-backfill":
        try:
            updated = client.backfill_library_hashes()
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
        if args.json:
            print(json.dumps({"updated": updated}, indent=2))
        else:
            print(f"Backfilled {updated} entr{'y' if updated == 1 else 'ies'} with MD5 hashes")

    elif args.command == "lib-load":
        try:
            if client.load_library_state(args.state_id):
                entry = client.find_library_entry(args.state_id)
                desc = entry.get("description", args.state_id) if entry else args.state_id
                print(f"Loaded: {desc}")
            else:
                print("Load failed")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "lib-info":
        entry = client.find_library_entry(args.state_id)
        if not entry:
            print(f"State '{args.state_id}' not found in library")
            sys.exit(1)

        if args.json:
            print(json.dumps(entry, indent=2))
        else:
            print(f"=== {entry['id']} ===")
            print(f"Label: {entry.get('label', 'N/A')}")
            print(f"Path: {entry.get('path', 'N/A')}")
            print(f"Status: {entry.get('status', 'draft')}")
            print(f"Captured by: {entry.get('captured_by', 'unknown')}")
            print(f"Tags: {', '.join(entry.get('tags', []))}")
            if entry.get("md5"):
                print(f"MD5: {entry['md5']}")
            created_at = entry.get("created_at")
            if created_at:
                print(f"Created: {created_at}")
            verified_by = entry.get("verified_by")
            verified_at = entry.get("verified_at")
            if verified_by:
                print(f"Verified by: {verified_by} at {verified_at}")
            if entry.get("deprecation_reason"):
                print(f"Deprecation reason: {entry['deprecation_reason']}")
            metadata = entry.get("metadata") or {}
            if metadata:
                print("Metadata:")
                for k, v in metadata.items():
                    print(f"  {k}: {v}")

    elif args.command == "capture":
        metadata = client.capture_state_metadata()
        if args.json:
            print(json.dumps(metadata, indent=2))
        else:
            print("=== Current State Metadata ===")
            print(f"Location: {metadata['location']}")
            print(f"Summary: {metadata['summary']}")
            print(f"Area: 0x{metadata['area']:02X}")
            print(f"Room: 0x{metadata['room']:02X}")
            print(f"Position: ({metadata['link_x']}, {metadata['link_y']})")
            print(f"Indoors: {metadata['indoors']}")
            print(f"Form: {metadata['link_form_name']} (0x{metadata['link_form']:02X})")
            print(f"Time: {metadata['time_hours']:02d}:{metadata['time_minutes']:02d} (speed: {metadata['time_speed']})")
            print(f"Health: {metadata['health']}/{metadata['max_health']}")
            print(f"Magic: {metadata['magic']}, Rupees: {metadata['rupees']}")
            print(f"GameState: {metadata['game_state']}")
            print(f"OOSPROG: 0x{metadata['oosprog']:02X}")
            print(f"OOSPROG2: 0x{metadata['oosprog2']:02X}")
            print(f"Crystals: 0x{metadata['crystals']:02X}")
            print(f"Pendants: 0x{metadata['pendants']:02X}")

    elif args.command == "labels":
        if args.labels_cmd == "set":
            try:
                addr = int(args.addr.replace("$", "0x"), 16)
            except ValueError:
                print(f"Invalid address: {args.addr}")
                sys.exit(1)
            ok = client.bridge.set_label(addr, args.label, comment=args.comment, memtype=args.memtype)
            payload = {
                "ok": ok,
                "addr": f"0x{addr:06X}",
                "label": args.label,
                "memtype": args.memtype,
                "comment": args.comment,
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print("Label set" if ok else "Label set failed")
            if not ok:
                sys.exit(1)
        elif args.labels_cmd == "get":
            try:
                addr = int(args.addr.replace("$", "0x"), 16)
            except ValueError:
                print(f"Invalid address: {args.addr}")
                sys.exit(1)
            label_info = client.bridge.get_label(addr, memtype=args.memtype)
            payload = {"addr": f"0x{addr:06X}", "label": None, "comment": None, "memtype": args.memtype}
            if label_info:
                payload["label"] = label_info.get("label")
                payload["comment"] = label_info.get("comment")
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                if payload["label"]:
                    comment = f" ({payload['comment']})" if payload["comment"] else ""
                    print(f"{payload['label']} @ 0x{addr:06X}{comment}")
                else:
                    print(f"No label at 0x{addr:06X}")
        elif args.labels_cmd == "lookup":
            addr = client.bridge.lookup_label(args.label)
            payload = {"label": args.label, "addr": f"0x{addr:06X}" if addr is not None else None}
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                if addr is not None:
                    print(f"{args.label} = 0x{addr:06X}")
                else:
                    print(f"Label not found: {args.label}")
        elif args.labels_cmd == "clear":
            ok = client.bridge.clear_labels()
            payload = {"ok": ok}
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print("Labels cleared" if ok else "Label clear failed")
            if not ok:
                sys.exit(1)
        else:
            print("Choose labels command: set, get, lookup, clear")
            sys.exit(1)

    elif args.command == "symbols":
        if args.query:
            # Check if query is an address
            if args.query.startswith("0x") or args.query.startswith("$"):
                addr = int(args.query.replace("$", "0x"), 16)
                symbol = client.get_symbol_at(addr)
                result = {"address": f"0x{addr:06X}", "symbol": symbol}
            else:
                addr = client.resolve_symbol(args.query)
                result = {"symbol": args.query, "address": f"0x{addr:06X}" if addr is not None else None}
            
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                if result.get("address") and result.get("symbol"):
                    print(f"{result['symbol']} = {result['address']}")
                elif result.get("address"):
                    print(f"{result['address']}: (no symbol found)")
                elif result.get("symbol"):
                    print(f"Could not resolve symbol '{result['symbol']}'")
        else:
            # List some stats
            stats = {
                "usdasm_loaded": len(client._usdasm_labels),
            }
            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print(f"USDASM Labels: {stats['usdasm_loaded']} loaded")
                print("Use 'symbols <name>' or 'symbols <address>' to query.")

    elif args.command == "labels-sync":
        result = _sync_usdasm_labels(client, args.clear)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("success"):
                filtered = result.get("filtered", 0)
                total = result.get("total", 0)
                print(f"Successfully synced {result.get('count', 0)} labels to Mesen2 (filtered {filtered}/{total} non-ROM).")
            else:
                print(f"Error syncing labels: {result.get('error', 'Unknown error')}")
                sys.exit(1)

    elif args.command == "subscribe":
        if client.subscribe(args.events):
            print(f"Subscribed to: {args.events}")
            print("Listening for events... (Press Ctrl+C to stop)")
            try:
                # Direct access to bridge to read pushed events
                # This depends on bridge implementation of a blocking read
                while True:
                    # For now just print that we are waiting
                    # If bridge supports it, we would read here
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nUnsubscribed.")
        else:
            print("Subscription failed")

    elif args.command == "batch":
        try:
            cmds = json.loads(args.commands)
            results = client.batch_execute(cmds)
            print(json.dumps(results, indent=2))
        except json.JSONDecodeError:
            print("Error: Invalid JSON commands")
            sys.exit(1)

    elif args.command == "watchdog":
        ok, msg = client.watchdog_recover(slot=args.slot, frames=args.frames)
        if args.json:
            print(json.dumps({"ok": ok, "message": msg}, indent=2))
        else:
            print(msg)
        if not ok:
            sys.exit(1)

    elif args.command == "state-diff":
        diff = client.get_state_diff()
        print(json.dumps(diff, indent=2))

    elif args.command == "watch-trigger":
        if args.trigger_cmd == "add":
            try:
                addr = int(args.addr, 0)
                val = int(args.value, 0)
                tid = client.add_watch_trigger(addr, val, condition=args.condition)
                if tid:
                    print(f"Trigger added with ID: {tid}")
                else:
                    print("Failed to add trigger")
            except ValueError:
                print("Error: Invalid address or value")
                sys.exit(1)
        elif args.trigger_cmd == "remove":
            if client.remove_watch_trigger(args.id):
                print(f"Trigger {args.id} removed")
            else:
                print("Failed to remove trigger")
        elif args.trigger_cmd == "list":
            triggers = client.list_watch_triggers()
            print(json.dumps(triggers, indent=2))

    elif args.command == "mem-watch":
        if args.add:
            if not args.addr:
                print("Error: --addr is required for --add")
                sys.exit(1)
            try:
                addr = int(args.addr, 0)
            except ValueError:
                print("Error: Invalid --addr")
                sys.exit(1)
            res = client.mem_watch("add", addr=addr, size=args.size, depth=args.depth)
        elif args.remove is not None:
            res = client.mem_watch("remove", watch_id=args.remove)
        elif args.list:
            res = client.mem_watch("list")
        elif args.clear:
            res = client.mem_watch("clear")
        else:
            print("Usage: mem-watch --add --addr <hex> [--size N] [--depth N] | --remove <id> | --list | --clear")
            sys.exit(1)

        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                data = res.get("data")
                if isinstance(data, str):
                    print(data)
                else:
                    print(json.dumps(data, indent=2))
            else:
                print(f"Error: {res.get('error', 'MEM_WATCH_WRITES failed')}")
                sys.exit(1)

    elif args.command == "mem-blame":
        if args.watch_id is None and not args.addr:
            print("Error: --watch-id or --addr is required")
            sys.exit(1)
        addr = None
        if args.addr:
            try:
                addr = int(args.addr, 0)
            except ValueError:
                print("Error: Invalid --addr")
                sys.exit(1)
        res = client.mem_blame(watch_id=args.watch_id, addr=addr)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                data = res.get("data")
                if isinstance(data, str):
                    print(data)
                else:
                    print(json.dumps(data, indent=2))
            else:
                print(f"Error: {res.get('error', 'MEM_BLAME failed')}")
                sys.exit(1)

    elif args.command == "stack-retaddr":
        sp = None
        if args.sp:
            try:
                sp = int(args.sp, 0)
            except ValueError:
                print("Error: Invalid --sp")
                sys.exit(1)
        res = client.stack_retaddr(count=args.count, mode=args.mode, sp=sp)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if not res.get("success"):
                print(f"Error: {res.get('error', 'STACK_RETADDR failed')}")
                sys.exit(1)
            data = res.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    print(data)
                    return
            print(f"SP: {data.get('sp')} | Mode: {data.get('mode')} | Count: {data.get('count')}")
            if data.get("bank"):
                print(f"Bank: {data.get('bank')}")
            entries = data.get("entries", [])
            for entry in entries:
                print(
                    f"  [{entry.get('index')}] {entry.get('bytes')} "
                    f"-> {entry.get('next')} ({entry.get('region')})"
                )

    elif args.command == "sync":
        if client.save_state_sync(args.path):
            print(f"Synced state: {args.path}")
        else:
            print("Sync failed")


if __name__ == "__main__":
    main()
