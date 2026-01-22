#!/usr/bin/env python3
"""
Yaze-Mesen2 Sync Daemon

Bidirectional synchronization between yaze and Mesen2:
- Syncs symbols from yaze to Mesen2 bridge
- Notifies yaze of breakpoint hits / PC changes in Mesen2
- Monitors both for changes and keeps them in sync

Usage:
    ./scripts/yaze_sync.py                    # Start sync daemon
    ./scripts/yaze_sync.py --once             # Single sync, then exit
    ./scripts/yaze_sync.py --push-symbols     # Push symbols to Mesen2
    ./scripts/yaze_sync.py --status           # Check connection status
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

# Configuration
YAZE_HOST = os.getenv("YAZE_HOST", "127.0.0.1")
YAZE_PORT = int(os.getenv("YAZE_PORT", "8080"))
YAZE_BASE_URL = f"http://{YAZE_HOST}:{YAZE_PORT}"

MESEN2_BRIDGE_DIR = Path.home() / "Documents" / "Mesen2" / "bridge"
MESEN2_STATE_FILE = MESEN2_BRIDGE_DIR / "state.json"
MESEN2_SYMBOLS_FILE = MESEN2_BRIDGE_DIR / "symbols.json"

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent

# Sync state
last_yaze_symbols_hash = ""
last_mesen_state = {}
running = True

def log(msg: str, level: str = "INFO"):
    """Print timestamped log message."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")

def http_get(path: str, timeout: float = 2.0) -> dict | None:
    """Make HTTP GET request to yaze server."""
    url = f"{YAZE_BASE_URL}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.URLError as e:
        return None
    except json.JSONDecodeError:
        return None
    except Exception as e:
        log(f"HTTP error: {e}", "ERROR")
        return None

def http_post(path: str, data: dict, timeout: float = 5.0) -> dict | None:
    """Make HTTP POST request to yaze server."""
    url = f"{YAZE_BASE_URL}{path}"
    try:
        body = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        log(f"HTTP POST error: {e}", "ERROR")
        return None

def check_yaze_status() -> dict:
    """Check if yaze server is running."""
    health = http_get("/api/v1/health")
    if health:
        return {
            "connected": True,
            "version": health.get("version", "unknown"),
            "rom_loaded": health.get("rom_loaded", False),
            "symbols_count": health.get("symbols_count", 0)
        }
    return {"connected": False}

def check_mesen_status() -> dict:
    """Check if Mesen2 bridge is active."""
    if not MESEN2_STATE_FILE.exists():
        return {"connected": False, "reason": "state file not found"}

    try:
        stat = MESEN2_STATE_FILE.stat()
        age = time.time() - stat.st_mtime

        if age > 5:
            return {"connected": False, "reason": f"state file is {age:.1f}s old"}

        with open(MESEN2_STATE_FILE) as f:
            state = json.load(f)

        return {
            "connected": True,
            "frame": state.get("frame", 0),
            "mode": state.get("mode", -1),
            "room": state.get("roomId", -1)
        }
    except Exception as e:
        return {"connected": False, "reason": str(e)}

def fetch_yaze_symbols() -> list[dict] | None:
    """Fetch symbols from yaze server."""
    result = http_get("/api/v1/symbols?format=json")
    if result and "symbols" in result:
        return result["symbols"]
    return None

def push_symbols_to_mesen() -> bool:
    """Fetch symbols from yaze and write to Mesen2 bridge directory."""
    symbols = fetch_yaze_symbols()
    if not symbols:
        log("No symbols fetched from yaze", "WARN")
        return False

    # Write symbols to bridge directory for Mesen2 Lua script to read
    MESEN2_BRIDGE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with open(MESEN2_SYMBOLS_FILE, 'w') as f:
            json.dump({
                "timestamp": time.time(),
                "count": len(symbols),
                "symbols": symbols
            }, f, indent=2)
        log(f"Pushed {len(symbols)} symbols to Mesen2 bridge")
        return True
    except Exception as e:
        log(f"Failed to write symbols: {e}", "ERROR")
        return False

def notify_yaze_breakpoint(address: int, pc: int, registers: dict) -> bool:
    """Notify yaze of a breakpoint hit in Mesen2."""
    data = {
        "event": "breakpoint",
        "address": address,
        "pc": pc,
        "registers": registers
    }
    result = http_post("/api/v1/events/breakpoint", data)
    return result is not None

def notify_yaze_state_change(old_state: dict, new_state: dict) -> bool:
    """Notify yaze of significant state changes in Mesen2."""
    # Only notify on significant changes
    significant_keys = ["mode", "roomId", "linkState"]

    changes = {}
    for key in significant_keys:
        old_val = old_state.get(key)
        new_val = new_state.get(key)
        if old_val != new_val:
            changes[key] = {"old": old_val, "new": new_val}

    if not changes:
        return True

    data = {
        "event": "state_change",
        "changes": changes,
        "frame": new_state.get("frame", 0)
    }
    result = http_post("/api/v1/events/state", data)
    return result is not None

def read_mesen_state() -> dict:
    """Read current Mesen2 state from bridge file."""
    try:
        if MESEN2_STATE_FILE.exists():
            with open(MESEN2_STATE_FILE) as f:
                return json.load(f)
    except:
        pass
    return {}

def sync_once():
    """Perform a single sync cycle."""
    global last_mesen_state

    # Check connections
    yaze = check_yaze_status()
    mesen = check_mesen_status()

    if not yaze["connected"]:
        log("Yaze not connected", "WARN")
        return

    if not mesen["connected"]:
        log(f"Mesen2 not connected: {mesen.get('reason', 'unknown')}", "WARN")
        return

    # Push symbols yaze -> Mesen2
    push_symbols_to_mesen()

    # Check for Mesen2 state changes
    current_state = read_mesen_state()
    if current_state and last_mesen_state:
        notify_yaze_state_change(last_mesen_state, current_state)
    last_mesen_state = current_state

def run_daemon(interval: float = 1.0):
    """Run continuous sync daemon."""
    global running

    def signal_handler(sig, frame):
        global running
        log("Shutting down...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    log("Starting yaze-Mesen2 sync daemon")
    log(f"Yaze: {YAZE_BASE_URL}")
    log(f"Mesen2 bridge: {MESEN2_BRIDGE_DIR}")

    # Initial status check
    yaze = check_yaze_status()
    mesen = check_mesen_status()
    log(f"Yaze: {'connected' if yaze['connected'] else 'not connected'}")
    log(f"Mesen2: {'connected' if mesen['connected'] else 'not connected'}")

    while running:
        try:
            sync_once()
            time.sleep(interval)
        except Exception as e:
            log(f"Sync error: {e}", "ERROR")
            time.sleep(interval * 2)

    log("Daemon stopped")

def main():
    parser = argparse.ArgumentParser(
        description='Yaze-Mesen2 bidirectional sync daemon'
    )
    parser.add_argument('--once', action='store_true',
                        help='Single sync then exit')
    parser.add_argument('--status', action='store_true',
                        help='Show connection status')
    parser.add_argument('--push-symbols', action='store_true',
                        help='Push symbols from yaze to Mesen2')
    parser.add_argument('--interval', type=float, default=1.0,
                        help='Sync interval in seconds (default: 1.0)')
    parser.add_argument('--yaze-url', help='Yaze server URL')

    args = parser.parse_args()

    if args.yaze_url:
        global YAZE_BASE_URL
        YAZE_BASE_URL = args.yaze_url

    if args.status:
        print("=== Connection Status ===")
        yaze = check_yaze_status()
        mesen = check_mesen_status()

        print(f"\nYaze Server ({YAZE_BASE_URL}):")
        if yaze["connected"]:
            print(f"  Status: Connected")
            print(f"  Version: {yaze.get('version', 'unknown')}")
            print(f"  ROM Loaded: {yaze.get('rom_loaded', False)}")
            print(f"  Symbols: {yaze.get('symbols_count', 0)}")
        else:
            print(f"  Status: Not connected")

        print(f"\nMesen2 Bridge ({MESEN2_BRIDGE_DIR}):")
        if mesen["connected"]:
            print(f"  Status: Connected")
            print(f"  Frame: {mesen.get('frame', 0)}")
            print(f"  Mode: {mesen.get('mode', -1)}")
            print(f"  Room: 0x{mesen.get('room', 0):02X}")
        else:
            print(f"  Status: Not connected")
            print(f"  Reason: {mesen.get('reason', 'unknown')}")

        return 0

    if args.push_symbols:
        if push_symbols_to_mesen():
            return 0
        return 1

    if args.once:
        sync_once()
        return 0

    run_daemon(args.interval)
    return 0

if __name__ == '__main__':
    sys.exit(main())
