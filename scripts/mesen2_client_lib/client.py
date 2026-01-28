"""Oracle of Secrets debugging client wrapping MesenBridge."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

from .bridge import MesenBridge
from .constants import (
    BUTTONS,
    DIRECTION_NAMES,
    DUNGEON_INFO,
    ENTRANCE_INFO,
    FORM_NAMES,
    GameMode,
    ITEMS,
    LOST_WOODS_AREAS,
    MODE_NAMES,
    OracleRAM,
    OVERWORLD_AREAS,
    OverworldSubmode,
    OVERWORLD_SUBMODE_NAMES,
    ROOM_NAMES,
    STORY_FLAGS,
    WARP_LOCATIONS,
    WATCH_PROFILES,
)
from .issues import KNOWN_ISSUES
from .state_library import StateLibrary


NAME_ENTRY_GUARD_ENV = "OOS_NAME_ENTRY_GUARD"
NAME_ENTRY_ALLOW_ENV = "OOS_NAME_ENTRY_ALLOW_A"
NAME_ENTRY_GUARD_FILE_ENV = "OOS_NAME_ENTRY_GUARD_FILE"
NAME_ENTRY_GUARD_COOLDOWN_ENV = "OOS_NAME_ENTRY_GUARD_COOLDOWN"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _guard_state_path() -> Path:
    override = os.getenv(NAME_ENTRY_GUARD_FILE_ENV)
    if override:
        return Path(override).expanduser()
    return Path(tempfile.gettempdir()) / "oos_name_entry_guard.json"


def _guard_cooldown_seconds() -> float:
    raw = os.getenv(NAME_ENTRY_GUARD_COOLDOWN_ENV)
    if raw is None:
        return 1.0
    try:
        return float(raw)
    except ValueError:
        return 1.0


def _load_guard_state(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        return {}
    return {}


def _write_guard_state(path: Path, mode: int, timestamp: float) -> None:
    payload = {"mode": mode, "timestamp": timestamp}
    try:
        path.write_text(json.dumps(payload))
    except Exception:
        pass


def _guard_active_for_mode(state: dict, mode: int, now: float, cooldown: float) -> bool:
    if state.get("mode") != mode:
        return False
    last_time = state.get("timestamp", 0.0)
    return now - last_time < cooldown


class OracleDebugClient:
    """Oracle of Secrets debugging client wrapping MesenBridge."""

    def __init__(self, socket_path: Optional[str] = None):
        socket_path = socket_path or os.getenv("MESEN2_SOCKET_PATH")
        self.bridge = MesenBridge(socket_path)
        self._last_area: Optional[int] = None
        self._watch_profile = "overworld"
        self.state_library = StateLibrary()
        self.last_error = ""
        self._usdasm_labels: dict[str, int] = {}
        self._usdasm_index: dict[int, str] = {}
        
        # Auto-load USDASM labels if they exist
        self.load_usdasm_labels()

    def load_usdasm_labels(self, path: Optional[Path] = None) -> int:
        """Load USDASM labels from a CSV index file."""
        if path is None:
            # Try to find it in the known location
            candidates = [
                Path(__file__).resolve().parents[3] / "z3dk" / ".context" / "knowledge" / "label_index_usdasm.csv",
                Path.home() / "src/hobby/z3dk/.context/knowledge/label_index_usdasm.csv"
            ]
            for candidate in candidates:
                if candidate.exists():
                    path = candidate
                    break
        
        if not path or not path.exists():
            return 0
            
        import csv
        count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    label = row["label"]
                    addr_str = row["address"] # format "$BB:AAAA"
                    try:
                        bank_str, offset_str = addr_str.replace("$", "").split(":")
                        bank = int(bank_str, 16)
                        offset = int(offset_str, 16)
                        # Linear SNES address (for LoROM)
                        linear = (bank << 16) | offset
                        self._usdasm_labels[label] = linear
                        self._usdasm_index[linear] = label
                        count += 1
                    except Exception:
                        continue
        except Exception as exc:
            self.last_error = f"Failed to load USDASM labels: {exc}"
            return 0
        return count

    def resolve_symbol(self, symbol: str) -> Optional[int]:
        """Resolve a symbol name to a SNES address.
        
        Checks internal USDASM labels first, then queries Mesen2.
        """
        if symbol in self._usdasm_labels:
            return self._usdasm_labels[symbol]
            
        res = self.bridge.send_command("SYMBOLS_RESOLVE", symbol=symbol)
        if res.get("success"):
            data = res.get("data", {})
            if isinstance(data, dict):
                addr_str = data.get("addr", "")
                if addr_str:
                    return int(addr_str.replace("0x", ""), 16)
        return None

    def get_symbol_at(self, address: int) -> Optional[str]:
        """Get the symbol name at a given address."""
        # Check USDASM index first
        if address in self._usdasm_index:
            return self._usdasm_index[address]
            
        # Try Mesen2 labels command
        res = self.bridge.send_command("LABELS", action="get", addr=f"0x{address:06X}")
        if res.get("success"):
            data = res.get("data", {})
            if isinstance(data, dict) and data.get("label"):
                return data.get("label")
        return None

    def is_connected(self) -> bool:
        if hasattr(self.bridge, "ensure_connected"):
            return bool(self.bridge.ensure_connected())
        return self.bridge.is_connected()

    def ensure_connected(self) -> bool:
        if hasattr(self.bridge, "ensure_connected"):
            return bool(self.bridge.ensure_connected())
        return self.bridge.is_connected()

    def health_check(self) -> dict:
        if hasattr(self.bridge, "check_health"):
            return self.bridge.check_health()
        return {
            "ok": self.bridge.is_connected(),
            "socket": getattr(self.bridge, "socket_path", None),
            "latency_ms": None,
            "error": "",
        }

    # --- Emulator Run State ---

    def get_run_state(self) -> dict:
        """Return emulator run/paused state."""
        try:
            raw = self.bridge.send_command("STATE")
        except Exception as exc:
            self.last_error = f"STATE failed: {exc}"
            return {}
        if not isinstance(raw, dict) or not raw.get("success"):
            self.last_error = str(raw.get("error") if isinstance(raw, dict) else "STATE failed")
            return {}
        data = raw.get("data", {})
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {}
        return data

    def get_rom_info(self) -> dict:
        """Return ROM info from the socket API."""
        try:
            raw = self.bridge.send_command("ROMINFO")
        except Exception as exc:
            self.last_error = f"ROMINFO failed: {exc}"
            return {}
        if not isinstance(raw, dict) or not raw.get("success"):
            self.last_error = str(raw.get("error") if isinstance(raw, dict) else "ROMINFO failed")
            return {}
        data = raw.get("data", {})
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {}
        return data

    def is_paused(self) -> Optional[bool]:
        """Return True if paused, False if running, or None if unknown."""
        state = self.get_run_state()
        if not state:
            return None
        return bool(state.get("paused")) if "paused" in state else None

    def ensure_running(self) -> bool:
        """Resume emulation if paused. Returns True if running or resumed."""
        paused = self.is_paused()
        if paused is None:
            return False
        if paused:
            return bool(self.resume())
        return True

    def ensure_paused(self) -> bool:
        """Pause emulation if running. Returns True if paused or paused successfully."""
        paused = self.is_paused()
        if paused is None:
            return False
        if not paused:
            return bool(self.pause())
        return True

    # --- State Reading ---

    def get_oracle_state(self) -> dict:
        """Get Oracle-specific game state."""
        mode = self.bridge.read_memory(OracleRAM.MODE)
        link_form = self.bridge.read_memory(OracleRAM.LINK_FORM)
        link_dir = self.bridge.read_memory(OracleRAM.LINK_DIR)
        area = self.bridge.read_memory(OracleRAM.AREA_ID)
        room = self.bridge.read_memory(OracleRAM.ROOM_LAYOUT)
        dungeon_room = self.bridge.read_memory16(OracleRAM.ROOM_ID)
        indoors = self.bridge.read_memory(OracleRAM.INDOORS)

        # Determine location name based on context
        if indoors:
            # Use room ID for indoor locations (dungeons)
            room_name = ROOM_NAMES.get(dungeon_room, f"Room 0x{dungeon_room:02X}")
            area_name = f"Inside: {room_name}"
        else:
            # Use area ID for overworld
            area_name = OVERWORLD_AREAS.get(area, f"Area 0x{area:02X}")
            room_name = area_name

        return {
            "mode": mode,
            "mode_name": MODE_NAMES.get(mode, f"Unknown (0x{mode:02X})"),
            "submode": self.bridge.read_memory(OracleRAM.SUBMODE),
            "area": area,
            "area_name": area_name,
            "room": room,
            "room_name": room_name,
            "dungeon_room": dungeon_room,
            "indoors": indoors,
            # Link position and state
            "link_x": self.bridge.read_memory16(OracleRAM.LINK_X),
            "link_y": self.bridge.read_memory16(OracleRAM.LINK_Y),
            "link_z": self.bridge.read_memory16(OracleRAM.LINK_Z),
            "link_dir": link_dir,
            "link_dir_name": DIRECTION_NAMES.get(link_dir, "?"),
            "link_state": self.bridge.read_memory(OracleRAM.LINK_STATE),
            "link_form": link_form,
            "link_form_name": FORM_NAMES.get(link_form, f"Unknown (0x{link_form:02X})"),
            # Scroll registers
            "scroll_x": self.bridge.read_memory(OracleRAM.SCROLL_X_LO),
            "scroll_y": self.bridge.read_memory(OracleRAM.SCROLL_Y_LO),
            # Time system (Oracle custom)
            "time_hours": self.bridge.read_memory(OracleRAM.TIME_HOURS),
            "time_minutes": self.bridge.read_memory(OracleRAM.TIME_MINUTES),
            "time_speed": self.bridge.read_memory(OracleRAM.TIME_SPEED),
            # Player stats
            "health": self.bridge.read_memory(OracleRAM.HEALTH_CURRENT),
            "max_health": self.bridge.read_memory(OracleRAM.HEALTH_MAX),
            "magic": self.bridge.read_memory(OracleRAM.MAGIC_POWER),
            "rupees": self.bridge.read_memory16(OracleRAM.RUPEES),
        }

    def get_time_state(self) -> dict:
        """Return Oracle day/night time state and palette values."""
        hours = self.bridge.read_memory(OracleRAM.TIME_HOURS)
        minutes = self.bridge.read_memory(OracleRAM.TIME_MINUTES)
        speed = self.bridge.read_memory(OracleRAM.TIME_SPEED)
        subcolor = self.bridge.read_memory16(OracleRAM.TIME_SUBCOLOR)
        red = self.bridge.read_memory16(OracleRAM.TIME_RED)
        green = self.bridge.read_memory16(OracleRAM.TIME_GREEN)
        blue = self.bridge.read_memory16(OracleRAM.TIME_BLUE)

        is_night = hours < 6 or hours >= 18
        phase = "night" if is_night else "day"

        return {
            "hours": hours,
            "minutes": minutes,
            "speed": speed,
            "phase": phase,
            "is_night": is_night,
            "subcolor": f"0x{subcolor:04X}",
            "palette": {
                "red": f"0x{red:04X}",
                "green": f"0x{green:04X}",
                "blue": f"0x{blue:04X}",
            },
        }

    def get_overworld_status(self) -> dict:
        """Return overworld/transition status with heuristics."""
        mode = self.bridge.read_memory(OracleRAM.MODE)
        submode = self.bridge.read_memory(OracleRAM.SUBMODE)
        indoors = self.bridge.read_memory(OracleRAM.INDOORS)

        overworld_modes = {GameMode.OVERWORLD, GameMode.OVERWORLD_SPECIAL}
        loading_modes = {GameMode.OVERWORLD_LOAD, GameMode.OVERWORLD_SPECIAL_LOAD, GameMode.DUNGEON_LOAD}
        is_overworld = mode in overworld_modes and not indoors
        is_transition = mode in loading_modes or (mode in overworld_modes and submode != OverworldSubmode.PLAYER_CONTROL)

        return {
            "mode": mode,
            "mode_name": MODE_NAMES.get(mode, f"0x{mode:02X}"),
            "submode": submode,
            "submode_name": OVERWORLD_SUBMODE_NAMES.get(submode, f"0x{submode:02X}"),
            "indoors": bool(indoors),
            "is_overworld": is_overworld,
            "is_transition": is_transition,
        }

    def get_camera_offset(self) -> dict:
        """Return scroll offsets relative to Link position."""
        scroll_x_lo = self.bridge.read_memory(OracleRAM.SCROLL_X_LO)
        scroll_x_hi = self.bridge.read_memory(OracleRAM.SCROLL_X_HI)
        scroll_y_lo = self.bridge.read_memory(OracleRAM.SCROLL_Y_LO)
        scroll_y_hi = self.bridge.read_memory(OracleRAM.SCROLL_Y_HI)

        scroll_x = (scroll_x_hi << 8) | scroll_x_lo
        scroll_y = (scroll_y_hi << 8) | scroll_y_lo

        link_x = self.bridge.read_memory16(OracleRAM.LINK_X)
        link_y = self.bridge.read_memory16(OracleRAM.LINK_Y)

        return {
            "scroll_x": scroll_x,
            "scroll_y": scroll_y,
            "link_x": link_x,
            "link_y": link_y,
            "offset_x": abs(link_x - scroll_x),
            "offset_y": abs(link_y - scroll_y),
        }

    def get_diagnostics(self, deep: bool = False) -> dict:
        """Composite diagnostic snapshot for agents."""
        oracle_state = self.get_oracle_state()
        run_state = self.get_run_state()
        rom_info = self.get_rom_info()
        time_state = self.get_time_state()
        overworld = self.get_overworld_status()
        camera = self.get_camera_offset()
        warnings = self.check_known_issues(oracle_state)

        camera_ok = camera["offset_x"] <= 200 and camera["offset_y"] <= 200

        snapshot = {
            "run_state": run_state,
            "rom_info": rom_info,
            "oracle_state": oracle_state,
            "time_state": time_state,
            "overworld": overworld,
            "camera": camera,
            "camera_ok": camera_ok,
            "warnings": warnings,
        }
        if deep:
            snapshot.update(
                {
                    "story_state": self.get_story_state(),
                    "items": self.get_all_items(),
                    "flags": self.get_all_flags(),
                    "watch_profile": self._watch_profile,
                    "watch_values": self.read_watch_values(),
                    "sprites": self.get_all_sprites(),
                }
            )
        return snapshot

    def get_story_state(self) -> dict:
        """Get story progression state."""
        return {
            "game_state": self.bridge.read_memory(OracleRAM.GAME_STATE),
            "oosprog": self.bridge.read_memory(OracleRAM.OOSPROG),
            "oosprog2": self.bridge.read_memory(OracleRAM.OOSPROG2),
            "side_quest": self.bridge.read_memory(OracleRAM.SIDE_QUEST),
            "side_quest2": self.bridge.read_memory(OracleRAM.SIDE_QUEST2),
            "crystals": self.bridge.read_memory(OracleRAM.CRYSTALS),
            "pendants": self.bridge.read_memory(OracleRAM.PENDANTS),
            "maku_tree_quest": self.bridge.read_memory(OracleRAM.MAKU_TREE_QUEST),
            "kydrog_farore_removed": self.bridge.read_memory(
                OracleRAM.KYDROG_FARORE_REMOVED
            ),
            "deku_mask_quest": self.bridge.read_memory(OracleRAM.DEKU_MASK_QUEST_DONE),
            "zora_mask_quest": self.bridge.read_memory(OracleRAM.ZORA_MASK_QUEST_DONE),
            "in_cutscene": self.bridge.read_memory(OracleRAM.IN_CUTSCENE),
        }

    def get_sprite_slot(self, slot: int) -> dict:
        """Read sprite slot data."""
        return {
            "state": self.bridge.read_memory(OracleRAM.SPR_STATE + slot),
            "x": self.bridge.read_memory(OracleRAM.SPR_X + slot),
            "y": self.bridge.read_memory(OracleRAM.SPR_Y + slot),
            "x_hi": self.bridge.read_memory(OracleRAM.SPR_X_HI + slot),
            "y_hi": self.bridge.read_memory(OracleRAM.SPR_Y_HI + slot),
            "type": self.bridge.read_memory(OracleRAM.SPR_TYPE + slot),
            "action": self.bridge.read_memory(OracleRAM.SPR_ACTION + slot),
            "health": self.bridge.read_memory(OracleRAM.SPR_HEALTH + slot),
            "timer_a": self.bridge.read_memory(OracleRAM.SPR_TIMER_A + slot),
            "timer_b": self.bridge.read_memory(OracleRAM.SPR_TIMER_B + slot),
            "timer_d": self.bridge.read_memory(OracleRAM.SPR_TIMER_D + slot),
            "parent": self.bridge.read_memory(OracleRAM.SPR_PARENT + slot),
        }

    def get_all_sprites(self) -> list[dict]:
        """Read all active sprite slots (0-15)."""
        sprites = []
        for slot in range(16):
            sprite = self.get_sprite_slot(slot)
            # Only include if sprite has a type (is active)
            if sprite["type"] != 0 or sprite["state"] != 0:
                sprite["slot"] = slot
                sprites.append(sprite)
        return sprites

    # --- Event Subscription ---

    def subscribe(self, events: str) -> bool:
        """Subscribe to real-time events.
        
        Args:
            events: Comma-separated list of event types (breakpoint_hit, frame_complete, etc.)
        """
        res = self.bridge.send_command("SUBSCRIBE", events=events)
        return bool(res.get("success"))

    def get_events(self) -> list[dict]:
        """Receive pending events from the socket."""
        # This requires the bridge to have a way to read pushed messages
        # without sending a command.
        if hasattr(self.bridge.bridge, "read_event"):
            return self.bridge.bridge.read_event()
        return []

    # --- Batch Execution ---

    def batch_execute(self, commands: list[dict]) -> tuple[list[dict], str]:
        """Execute multiple commands in one request.

        Returns:
            Tuple of (results, error). If error is non-empty, the batch failed.
            On success, error is empty string and results contains command outputs.
        """
        res = self.bridge.send_command("BATCH", commands=json.dumps(commands))
        if res.get("success"):
            data = res.get("data")
            if isinstance(data, str):
                return json.loads(data).get("results", []), ""
            return data.get("results", []), ""
        error = res.get("error", "BATCH command failed")
        self.last_error = error
        return [], error

    # --- YAZE State Synchronization ---

    def save_state_sync(self, path: str) -> bool:
        """Notify YAZE of a state save."""
        res = self.bridge.send_command("SAVESTATE_SYNC", path=path)
        return bool(res.get("success"))

    def save_state_watch(self, action: str = "status") -> dict:
        """Manage YAZE state file watching."""
        res = self.bridge.send_command("SAVESTATE_WATCH", action=action)
        if res.get("success"):
            return res.get("data", {})
        return {}

    # --- State Tracking ---

    def get_state_diff(self) -> dict:
        """Get state changes since last call."""
        res = self.bridge.send_command("STATE_DIFF")
        if res.get("success"):
            return res.get("data", {})
        return {}

    # --- Watchdog helpers ---

    def _frame_value(self) -> int:
        """Read the game's own frame counter (not emulator host frame)."""
        return self.bridge.read_memory(OracleRAM.FRAME_COUNTER)

    def ensure_frame_progress(self, frames: int = 30) -> bool:
        """Return True if the in-game frame counter advances after running a few frames."""
        before = self._frame_value()
        # Run minimal frames to give the main loop a chance to tick
        self.bridge.run_frames(max(1, frames))
        after = self._frame_value()
        return after != before

    def watchdog_recover(self, slot: int = 1, frames: int = 30) -> tuple[bool, str]:
        """Detect stalled game loop and auto-reload a state to recover.

        Args:
            slot: savestate slot to reload on stall
            frames: frames to run while checking for progress
        Returns:
            (ok, message) where ok=True if no stall detected, False if a reload was issued.
        """
        try:
            progressed = self.ensure_frame_progress(frames=frames)
        except Exception as exc:
            self.last_error = f"Watchdog read failed: {exc}"
            return False, self.last_error

        if progressed:
            return True, "Frame counter advanced; no action taken."

        # Attempt recovery: reload slot and resume
        reloaded = self.bridge.load_state(slot=slot)
        if reloaded:
            self.bridge.resume()
            return False, f"Frame counter stalled; reloaded slot {slot} and resumed."

        self.last_error = f"Frame counter stalled and reload of slot {slot} failed."
        return False, self.last_error

    # --- Watch Triggers ---

    def add_watch_trigger(self, addr: int, value: int, condition: str = "eq") -> Optional[int]:
        """Add a memory watch trigger."""
        payload = {
            "action": "add",
            "addr": hex(addr),
            "value": hex(value),
            "condition": condition,
        }
        res = self.bridge.send_command("WATCH_TRIGGER", payload)
        if res.get("success"):
            data = res.get("data")
            if isinstance(data, str):
                return json.loads(data).get("id")
            return data.get("id")
        return None

    def remove_watch_trigger(self, trigger_id: int) -> bool:
        """Remove a memory watch trigger."""
        payload = {"action": "remove", "trigger_id": str(trigger_id)}
        res = self.bridge.send_command("WATCH_TRIGGER", payload)
        return bool(res.get("success"))

    def list_watch_triggers(self) -> list[dict]:
        """List active watch triggers."""
        res = self.bridge.send_command("WATCH_TRIGGER", action="list")
        if res.get("success"):
            data = res.get("data")
            if isinstance(data, str):
                return json.loads(data).get("triggers", [])
            return data.get("triggers", [])
        return []

    # --- Watch Profiles ---

    def set_watch_profile(self, profile: str) -> bool:
        """Set the active watch profile."""
        if profile in WATCH_PROFILES:
            self._watch_profile = profile
            return True
        return False

    def get_available_profiles(self) -> dict:
        """Get all available watch profiles."""
        return {name: p["description"] for name, p in WATCH_PROFILES.items()}

    def read_watch_values(self) -> dict:
        """Read all values in the current watch profile."""
        profile = WATCH_PROFILES.get(self._watch_profile, {})
        addresses = profile.get("addresses", [])

        values = {}
        for addr, name, fmt in addresses:
            if fmt == "dec16":
                values[name] = self.bridge.read_memory16(addr)
            elif fmt == "hex":
                values[name] = f"0x{self.bridge.read_memory(addr):02X}"
            elif fmt == "bool":
                values[name] = bool(self.bridge.read_memory(addr))
            else:
                values[name] = self.bridge.read_memory(addr)

        return values

    # --- Issue Detection ---

    def check_known_issues(self, state: dict) -> list[str]:
        """Check current state against known issue patterns."""
        warnings = []
        for issue_id, issue in KNOWN_ISSUES.items():
            if issue["trigger"](state):
                warnings.append(f"[{issue_id}] {issue['warning']}")
        return warnings

    # --- Area Tracking ---

    def on_area_change(self, new_area: int) -> str:
        """Called when area changes. Returns status message."""
        old_area = self._last_area
        self._last_area = new_area

        # Auto-switch watch profile
        if new_area in LOST_WOODS_AREAS:
            self.set_watch_profile("lost_woods")
        elif new_area >= 0x80:  # Dungeon areas (typically high IDs)
            self.set_watch_profile("dungeon")
        else:
            self.set_watch_profile("overworld")

        old_str = f"0x{old_area:02X}" if old_area is not None else "None"
        return f"Entered area 0x{new_area:02X} (from {old_str})"

    # --- Memory Operations ---

    def read_address(self, addr: int) -> int:
        """Read a single byte from an address."""
        return self.bridge.read_memory(addr)

    def read_address16(self, addr: int) -> int:
        """Read a 16-bit value from an address."""
        return self.bridge.read_memory16(addr)

    def write_address(self, addr: int, value: int) -> bool:
        """Write a byte to an address."""
        return self.bridge.write_memory(addr, value)

    # --- Hypothesis Testing ---

    def apply_hypothesis(self, patches: dict[int, list[int] | int]) -> bool:
        """Apply temporary memory patches for hypothesis testing.
        
        Args:
            patches: Dict mapping address (int) to value (int) or list of bytes.
        """
        success = True
        for addr, data in patches.items():
            if isinstance(data, list):
                # Write byte array
                for i, byte in enumerate(data):
                    success &= self.bridge.write_memory(addr + i, byte)
            else:
                # Write single byte
                success &= self.bridge.write_memory(addr, data)
        return success

    def test_hypothesis(
        self, 
        state_id: str, 
        patches: dict[int, list[int] | int], 
        timeout_frames: int = 300,
        watch_profile: Optional[str] = None
    ) -> dict:
        """Test a hypothesis by applying patches to a state and checking for issues.
        
        Args:
            state_id: State ID to load from library
            patches: Memory patches to apply
            timeout_frames: How many frames to run before verifying
            watch_profile: Optional watch profile to load
            
        Returns:
            Dict with result: 'passed', 'warnings', 'errors', 'diagnostics'
        """
        # 1. Load the state
        if not self.load_library_state(state_id):
            return {"passed": False, "errors": [f"Failed to load state: {state_id}"]}
            
        # 2. Save recovery checkpoint (slot 99)
        self.bridge.save_state(slot=99)
        
        try:
            # 3. Apply patches
            if not self.apply_hypothesis(patches):
                return {"passed": False, "errors": ["Failed to apply patches"]}
                
            # 4. Set watch profile
            if watch_profile:
                self.set_watch_profile(watch_profile)
                
            # 5. Run scenario (wait for frames)
            self.run_frames(timeout_frames)
            
            # 6. Verify result
            diagnostics = self.get_diagnostics(deep=True)
            warnings = diagnostics.get("warnings", [])
            
            # A hypothesis "passes" if there are no warnings triggered after the wait
            # and the frame counter is still advancing.
            stalled = not self.ensure_frame_progress(frames=10)
            
            passed = not warnings and not stalled
            errors = []
            if stalled:
                errors.append("Game engine stalled after applying hypothesis")
                
            return {
                "passed": passed,
                "warnings": warnings,
                "errors": errors,
                "diagnostics": diagnostics if not passed else None
            }
            
        finally:
            # 7. Rollback
            self.bridge.load_state(slot=99)

    # --- Item Management ---

    def get_item(self, item_name: str) -> tuple[int, str]:
        """Get an item's current value and description."""
        if item_name not in ITEMS:
            raise ValueError(f"Unknown item: {item_name}")
        addr, name, values = ITEMS[item_name]
        if item_name == "rupees":
            val = self.bridge.read_memory16(addr)
        else:
            val = self.bridge.read_memory(addr)
        desc = values.get(val, str(val)) if values else str(val)
        return val, desc

    def set_item(self, item_name: str, value: int) -> bool:
        """Set an item's value."""
        if item_name not in ITEMS:
            raise ValueError(f"Unknown item: {item_name}")
        addr, _, _ = ITEMS[item_name]
        if item_name == "rupees":
            return self.bridge.write_memory16(addr, value)
        return self.bridge.write_memory(addr, value)

    def get_all_items(self) -> dict:
        """Get all items and their values."""
        result = {}
        for name in ITEMS:
            try:
                val, desc = self.get_item(name)
                result[name] = {"value": val, "description": desc}
            except Exception:
                pass
        return result

    # --- Story Flag Management ---

    def get_flag(self, flag_name: str) -> tuple[int, bool]:
        """Get a story flag's value. Returns (raw_value, is_set)."""
        if flag_name not in STORY_FLAGS:
            raise ValueError(f"Unknown flag: {flag_name}")
        addr, name, mask_or_values = STORY_FLAGS[flag_name]
        val = self.bridge.read_memory(addr)
        if isinstance(mask_or_values, int):
            # Bitfield flag
            is_set = bool(val & mask_or_values)
            return val, is_set
        else:
            # Full byte value
            return val, val != 0

    def set_flag(self, flag_name: str, value: int | bool) -> bool:
        """Set a story flag. For bitflags, True sets the bit, False clears it."""
        if flag_name not in STORY_FLAGS:
            raise ValueError(f"Unknown flag: {flag_name}")
        addr, name, mask_or_values = STORY_FLAGS[flag_name]

        if isinstance(mask_or_values, int):
            # Bitfield flag - set or clear bit
            current = self.bridge.read_memory(addr)
            if value:
                new_val = current | mask_or_values
            else:
                new_val = current & ~mask_or_values
            return self.bridge.write_memory(addr, new_val)
        else:
            # Full byte value
            return self.bridge.write_memory(addr, int(value))

    def get_all_flags(self) -> dict:
        """Get all story flags."""
        result = {}
        for name in STORY_FLAGS:
            try:
                val, is_set = self.get_flag(name)
                result[name] = {"value": val, "is_set": is_set}
            except Exception:
                pass
        return result

    # --- Warp / Teleport ---

    def warp_to(
        self,
        location: str | None = None,
        area: int | None = None,
        x: int | None = None,
        y: int | None = None,
        kind: str = "ow",
        use_rom_warp: bool = True,
        timeout_frames: int = 120,
    ) -> bool:
        """Warp Link to a location or specific coordinates.

        This uses the ROM debug warp system (code at $3CB400) which properly
        handles transitions for both overworld and dungeon warps.

        For overworld: triggers mosaic transition, reloads graphics/palettes
        For dungeons: triggers UnderworldLoad (Mode 0x06), reloads room

        The ROM code auto-detects if you're in overworld (Mode 0x09) or
        dungeon (Mode 0x07) and uses the appropriate transition method.

        Args:
            location: Named location from WARP_LOCATIONS
            area: Area ID (overworld) or Room ID (dungeon)
            x, y: Coordinates
            kind: "ow" for overworld, "uw" for underworld/dungeon (informational)
            use_rom_warp: Use ROM debug warp system (default True)
            timeout_frames: Max frames to wait for warp completion

        Returns:
            True if warp was successful, False otherwise
        """
        target_area = area
        if location and location in WARP_LOCATIONS:
            target_area, x, y, _ = WARP_LOCATIONS[location]

        if x is None or y is None:
            raise ValueError("Must specify location name or x+y coordinates")

        current_area = self.bridge.read_memory(OracleRAM.AREA_ID)
        needs_area_change = target_area is not None and target_area != current_area

        if not use_rom_warp:
            # Legacy direct RAM write (may cause issues for cross-area warps)
            success = True
            if needs_area_change:
                success &= self.bridge.write_memory(OracleRAM.AREA_ID, target_area)
            success &= self.bridge.write_memory16(OracleRAM.LINK_X, x)
            success &= self.bridge.write_memory16(OracleRAM.LINK_Y, y)
            return success

        # Use ROM debug warp system
        # 1. Write target area
        if target_area is not None:
            self.bridge.write_memory(OracleRAM.DBG_WARP_AREA, target_area)
        else:
            self.bridge.write_memory(OracleRAM.DBG_WARP_AREA, current_area)

        # 2. Write target position (16-bit)
        self.bridge.write_memory16(OracleRAM.DBG_WARP_X, x)
        self.bridge.write_memory16(OracleRAM.DBG_WARP_Y, y)

        # 3. Arm + clear status before triggering
        self.bridge.write_memory(OracleRAM.DBG_WARP_ARM, OracleRAM.DBG_WARP_ARM_MAGIC)
        self.bridge.write_memory(OracleRAM.DBG_WARP_STATUS, OracleRAM.DBG_WARP_STATUS_ARMED)
        self.bridge.write_memory(OracleRAM.DBG_WARP_ERROR, 0)

        # 4. Trigger the warp (1=cross-area with transition, 2=same-area teleport)
        request_type = 1 if needs_area_change else 2
        self.bridge.write_memory(OracleRAM.DBG_WARP_REQUEST, request_type)

        if needs_area_change:
            print(f"Debug warp: area 0x{current_area:02X} -> 0x{target_area:02X}, "
                  f"pos ({x}, {y})")
        else:
            print(f"Debug teleport: pos ({x}, {y}) in area 0x{current_area:02X}")

        # 5. Poll for completion (optional - warp happens on next frame)
        # The ROM code sets status to 3 when complete
        import time
        for _ in range(timeout_frames):
            status = self.bridge.read_memory(OracleRAM.DBG_WARP_STATUS)
            if status == 3:  # Complete
                return True
            if status in (0, OracleRAM.DBG_WARP_STATUS_ARMED):  # Not yet processed/armed
                time.sleep(1 / 60)  # Wait one frame
                continue
            # Status 1 or 2 means still processing
            time.sleep(1 / 60)

        # Check for errors
        error = self.bridge.read_memory(OracleRAM.DBG_WARP_ERROR)
        if error:
            error_msgs = {
                1: "Wrong game mode (not in overworld/dungeon play)",
                2: "Underworld warps not yet supported",
                3: "Cross-world warp (LW<->DW) - use mirror first, then warp within that world",
                4: "Invalid request byte (garbage request)",
                5: "Warp not armed (missing arm byte)",
                6: "Warp not armed (status mismatch)",
            }
            print(f"Warp failed: {error_msgs.get(error, f'Error code {error}')}")
            return False

        # Timeout - warp may still be in progress
        print("Warp status check timed out (warp may still be processing)")
        return True  # Assume success if no error

    def set_position(self, x: int, y: int) -> bool:
        """Set Link's position without changing area (instant teleport)."""
        success = True
        success &= self.bridge.write_memory16(OracleRAM.LINK_X, x)
        success &= self.bridge.write_memory16(OracleRAM.LINK_Y, y)
        return success

    # --- Input Injection ---

    def press_button(self, buttons: str, frames: int = 5, ensure_running: bool | None = None) -> bool:
        """Press button(s) for specified frames.

        Args:
            buttons: Comma-separated button names (a,b,up,down,left,right,start,select,l,r,x,y)
            frames: Number of frames to hold (default 5, ~83ms at 60fps). 0 = indefinite.
        """
        if ensure_running is None:
            ensure_running = _env_flag("OOS_INPUT_REQUIRE_RUNNING", True)
        if ensure_running and not self.ensure_running():
            self.last_error = "Emulator appears paused; resume before input."
            return False

        if _env_flag(NAME_ENTRY_GUARD_ENV, True) and not _env_flag(NAME_ENTRY_ALLOW_ENV, False):
            try:
                # GameMode values are sourced from usdasm Zelda_3_RAM.log.
                mode = self.bridge.read_memory(OracleRAM.MODE)
            except Exception as exc:
                # Connection error - block button presses as a safety measure
                self.last_error = f"Name entry guard: failed to read mode ({exc})"
                return False
            if mode == GameMode.NAME_ENTRY:
                guard_path = _guard_state_path()
                now = time.time()
                cooldown = _guard_cooldown_seconds()
                guard_state = _load_guard_state(guard_path)
                if _guard_active_for_mode(guard_state, mode, now, cooldown):
                    return True
                buttons = "start"
                frames = max(2, min(frames, 5))
                _write_guard_state(guard_path, mode, now)

        # Normalize button names
        btn_list = []
        for btn in buttons.lower().replace(" ", "").split(","):
            if btn in BUTTONS:
                btn_list.append(BUTTONS[btn])
            else:
                btn_list.append(btn.upper())

        btn_str = ",".join(btn_list)
        force_fallback = _env_flag("OOS_INPUT_FORCE_FALLBACK", False)
        if not force_fallback:
            ok = self.bridge.press_button(btn_str, frames=frames)
            if ok:
                return True

        # Fallback: direct RAM input injection (works even if DebugBridge Lua isn't loaded)
        # JOY1A (BYsSudlr) at $7E00F0/$7E00F4, JOY1B (AXLR....) at $7E00F2/$7E00F6.
        # Bits (low byte): B=0x01, Y=0x02, Select=0x04, Start=0x08,
        # Up=0x10, Down=0x20, Left=0x40, Right=0x80.
        mask_a = 0
        mask_b = 0
        for b in btn_list:
            b = b.lower()
            if b in {"b"}:
                mask_a |= 0x01
            elif b in {"y"}:
                mask_a |= 0x02
            elif b in {"select"}:
                mask_a |= 0x04
            elif b in {"start"}:
                mask_a |= 0x08
            elif b in {"up"}:
                mask_a |= 0x10
            elif b in {"down"}:
                mask_a |= 0x20
            elif b in {"left"}:
                mask_a |= 0x40
            elif b in {"right"}:
                mask_a |= 0x80
            elif b in {"a"}:
                mask_b |= 0x01
            elif b in {"x"}:
                mask_b |= 0x02
            elif b in {"l"}:
                mask_b |= 0x04
            elif b in {"r"}:
                mask_b |= 0x08

        if mask_a == 0 and mask_b == 0:
            self.last_error = "Fallback input: unknown button(s)"
            return False

        try:
            # Write to joypad mirrors: NEW at $7E00F4/$7E00F6, ALL at $7E00F0/$7E00F2
            total_frames = max(1, frames)
            for i in range(total_frames):
                new_a = mask_a if i == 0 else 0
                new_b = mask_b if i == 0 else 0
                self.bridge.write_memory(0x7E00F4, new_a)
                self.bridge.write_memory(0x7E00F6, new_b)
                self.bridge.write_memory(0x7E00F0, mask_a)
                self.bridge.write_memory(0x7E00F2, mask_b)
                self.bridge.run_frames(1)
            self.bridge.write_memory(0x7E00F4, 0)
            self.bridge.write_memory(0x7E00F6, 0)
            self.bridge.write_memory(0x7E00F0, 0)
            self.bridge.write_memory(0x7E00F2, 0)
            return True
        except Exception as exc:
            self.last_error = f"Fallback input failed: {exc}"
            return False

    def hold_direction(self, direction: str, frames: int = 30, ensure_running: bool | None = None) -> bool:
        """Hold a direction for specified frames.

        Args:
            direction: Direction to hold (up, down, left, right)
            frames: Number of frames to hold (default 30, ~500ms at 60fps)
        """
        dir_map = {"up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT"}
        if direction.lower() not in dir_map:
            raise ValueError(f"Invalid direction: {direction}")
        if ensure_running is None:
            ensure_running = _env_flag("OOS_INPUT_REQUIRE_RUNNING", True)
        if ensure_running and not self.ensure_running():
            self.last_error = "Emulator appears paused; resume before input."
            return False
        return self.bridge.press_button(dir_map[direction.lower()], frames=frames)

    # --- Pass-through to MesenBridge ---

    def pause(self):
        return self.bridge.pause()

    def resume(self):
        return self.bridge.resume()

    def reset(self):
        return self.bridge.reset()

    def screenshot(self):
        return self.bridge.screenshot()

    def save_state(self, **kw):
        path = kw.get("path")
        if path:
            path_obj = Path(str(path)).expanduser()
            allow_external = kw.pop("allow_external", None)
            if allow_external is None:
                allow_external = kw.pop("allowExternal", None)
            if allow_external is None:
                allow_external = True
            params: dict = {"path": str(path_obj)}
            if "slot" in kw:
                params["slot"] = str(kw["slot"])
            if "pause" in kw:
                params["pause"] = str(kw["pause"]).lower()
            if allow_external:
                params["allow_external"] = "true"
            res = self.bridge.send_command("SAVESTATE", params)
            if res.get("success"):
                self.last_error = ""
                return True
            self.last_error = res.get("error", "") or "SAVESTATE failed"
            return False
        self.last_error = ""
        return self.bridge.save_state(**kw)

    def save_state_label(
        self,
        action: str = "set",
        slot: int | None = None,
        path: str | None = None,
        label: str | None = None,
    ) -> dict:
        params: dict = {"action": action}
        if slot is not None:
            params["slot"] = slot
        if path:
            params["path"] = path
        if label is not None:
            params["label"] = label
        res = self.bridge.send_command("SAVESTATE_LABEL", **params)
        if res.get("success"):
            self.last_error = ""
        else:
            self.last_error = res.get("error", "") or "SAVESTATE_LABEL failed"
        return res

    def load_state(self, **kw):
        path = kw.get("path")
        if path:
            from .state_library import disallowed_state_reason, is_disallowed_state_path
            path_obj = Path(str(path)).expanduser()
            if is_disallowed_state_path(path_obj):
                self.last_error = disallowed_state_reason(path_obj)
                return False
            allow_external = kw.pop("allow_external", None)
            if allow_external is None:
                allow_external = kw.pop("allowExternal", None)
            if allow_external is None:
                allow_external = True
            params: dict = {"path": str(path_obj)}
            if "pause" in kw:
                params["pause"] = str(kw["pause"]).lower()
            if allow_external:
                params["allow_external"] = "true"
            res = self.bridge.send_command("LOADSTATE", params)
            if res.get("success"):
                self.last_error = ""
                return True
            self.last_error = res.get("error", "") or "LOADSTATE failed"
            return False
        self.last_error = ""
        return self.bridge.load_state(**kw)

    def add_breakpoint(self, **kw):
        # mesen2-mcp expects "bptype" for breakpoint kind; CLI uses "mode".
        if "mode" in kw and "bptype" not in kw:
            kw["bptype"] = kw.pop("mode")
        if "type" in kw and "bptype" not in kw:
            kw["bptype"] = kw.pop("type")
        return self.bridge.add_breakpoint(**kw)

    def get_cpu_state(self):
        """Get CPU registers and flags via Lua bridge."""
        # Try the bridge's native get_cpu_state first
        try:
            native = self.bridge.get_cpu_state()
            if native:
                # mesen2-mcp bridge returns the data dict directly (no success wrapper)
                if isinstance(native, dict) and "success" not in native:
                    return native
                if isinstance(native, dict) and native.get("success"):
                    return native.get("data")
        except Exception:
            pass
        
        # Fallback/Extended via Lua bridge REGISTERS command
        res = self.bridge.send_command("REGISTERS")
        if res.get("success"):
            return res.get("data")
        return {}

    def disassemble(self, address: int, count: int = 10) -> list:
        """Disassemble code at address."""
        try:
            if hasattr(self.bridge, "disassemble"):
                return self.bridge.disassemble(address, count)
        except Exception:
            pass
        res = self.bridge.send_command("DISASM", {"addr": f"0x{address:06X}", "count": str(count)})
        if res.get("success"):
            data = res.get("data")
            if isinstance(data, list):
                return data
        return []

    def trace(self, count: int = 1000, offset: int = 0) -> tuple[bool, list[dict]]:
        """Capture an execution trace.
        
        Args:
            count: Number of instructions to capture.
            offset: Offset into the trace buffer.
            
        Returns:
            (success, frames)
        """
        params = {"count": str(count)}
        if offset:
            params["offset"] = str(offset)
        res = self.bridge.send_command("TRACE", params)
        if res.get("success"):
            data = res.get("data")
            if isinstance(data, dict) and "entries" in data:
                return True, data["entries"]
            if isinstance(data, str):
                try:
                    return True, json.loads(data)
                except json.JSONDecodeError:
                    return False, []
            return True, data if isinstance(data, list) else []
        self.last_error = res.get("error", "Trace failed")
        return False, []

    def trace_control(
        self,
        action: str,
        *,
        format: str | None = None,
        condition: str | None = None,
        labels: bool | None = None,
        indent: bool | None = None,
        clear: bool | None = None,
    ) -> dict:
        """Control execution trace logging via socket TRACE."""
        params: dict[str, str] = {"action": action}
        if format is not None:
            params["format"] = format
        if condition is not None:
            params["condition"] = condition
        if labels is not None:
            params["labels"] = "true" if labels else "false"
        if indent is not None:
            params["indent"] = "true" if indent else "false"
        if clear is not None:
            params["clear"] = "true" if clear else "false"

        res = self.bridge.send_command("TRACE", params)
        if res.get("success") and isinstance(res.get("data"), str):
            try:
                res["data"] = json.loads(res["data"])
            except json.JSONDecodeError:
                pass
        return res

    def get_callstack(self) -> list:
        """Get the current CPU callstack."""
        res = self.bridge.send_command("CALLSTACK")
        if res.get("success"):
            return res.get("data")
        return []

    def get_labels(self, filter_str: str = "") -> dict:
        """Get labels, optionally filtered by name or address."""
        res = self.bridge.send_command("LABELS", filter_str)
        if res.get("success"):
            return res.get("data")
        return {}

    def search_memory(self, value: int, size: int = 1, start: int = 0x7E0000, end: int = 0x7FFFFF) -> list:
        """Search memory for a value."""
        res = self.bridge.send_command("MEMORY_SEARCH", value, size, start, end)
        if res.get("success"):
            return res.get("data", {}).get("addresses", [])
        return []

    def get_collision_map(self) -> bytes | None:
        """Fetch the current collision map (ColMap A) from the bridge.

        Returns:
            bytes: Collision values for the current screen. The size depends
                   on the format returned by COLLISION_DUMP.
                   Returns None on failure.

        The COLLISION_DUMP command returns a 2D array with interleaved
        [tile_id, collision_type] pairs: [tile0, col0, tile1, col1, ...]
        Each row has 64 values = 32 tile pairs (for a 32-tile wide area).
        We extract the collision types (odd indices) and flatten to bytes.
        """
        res = self.bridge.send_command("COLLISION_DUMP")
        if not res.get("success"):
            return None

        data = res.get("data", {})
        if not isinstance(data, dict):
            return None

        rows = data.get("data", [])

        # COLLISION_DUMP returns 64 rows x 64 values
        # Each row is interleaved: [tile_id, collision, tile_id, collision, ...]
        # So 64 values per row = 32 tiles, each with (tile_id, collision) pair
        # We extract collision values at odd indices (1, 3, 5, ...)
        collision_bytes = bytearray()

        for row in rows:
            # Extract collision types at odd indices
            for i in range(1, len(row), 2):
                collision_bytes.append(row[i] & 0xFF)

        return bytes(collision_bytes) if collision_bytes else None

    def get_collision_raw(self) -> dict | None:
        """Get the raw COLLISION_DUMP response for detailed analysis.

        Returns:
            dict with keys: 'colmap' (str), 'width' (int), 'height' (int),
            'data' (list of rows with interleaved tile_id, collision pairs)
        """
        res = self.bridge.send_command("COLLISION_DUMP")
        if res.get("success"):
            return res.get("data")
        return None

    def draw_path(self, points: list[tuple[int, int]]) -> bool:
        """Draw a visual path on the emulator overlay.
        
        Args:
            points: List of (x, y) coordinates
        """
        # Format as "x1,y1,x2,y2..."
        # Limit to reasonable length (CLI arg limits)
        if not points:
            return self.bridge.send_command("DRAW_PATH", "").get("success", False)
            
        # Take up to 50 points to avoid overflowing command buffer
        # Resample if path is long? For now just truncate or send sparse
        chunks = []
        for x, y in points[:50]: 
            chunks.append(f"{int(x)},{int(y)}")
        
        arg = ",".join(chunks)
        return self.bridge.send_command("DRAW_PATH", arg).get("success", False)

    def execute_lua(self, code: str) -> dict:
        """Execute arbitrary Lua code in the emulator."""
        # Use base64 to avoid issues with special characters in shell commands
        import base64
        encoded = base64.b64encode(code.encode()).decode()
        res = self.bridge.send_command("EXEC_LUA", encoded)
        if res.get("success"):
            return res.get("data")
        return {"error": "Lua execution failed", "bridge_response": res}

    def wait_for_value(self, address: int, value: int, timeout: float = 5.0, interval: float = 0.05) -> bool:
        """Wait for a memory address to hold a specific value."""
        import time
        start = time.time()
        while time.time() - start < timeout:
            if self.read_address(address) == value:
                return True
            time.sleep(interval)
        return False

    def wait_for_label(self, label_name: str, timeout: float = 5.0) -> bool:
        """Wait until the CPU PC reaches a specific symbolic label."""
        import time
        # Resolve label to address
        labels = self.get_labels(label_name)
        addr = None
        for a_str, name in labels.items():
            if name == label_name:
                addr = int(a_str.replace("$", "0x"), 16)
                break
        
        if addr is None:
            raise ValueError(f"Label not found: {label_name}")
            
        start = time.time()
        while time.time() - start < timeout:
            regs = self.get_cpu_state()
            pc = regs.get("PC")
            if pc == addr:
                return True
            time.sleep(0.01) # Poll faster for PC
        return False

    def step(self, count: int = 1, mode: str = "into"):
        return self.bridge.step(count, mode)

    def run_frames(self, count: int = 1):
        return self.bridge.run_frames(count)

    # --- State Library Integration ---

    def get_library_manifest(self) -> dict:
        """Load the save state library manifest."""
        return self.state_library.get_manifest()

    def find_library_entry(self, state_id: str) -> Optional[dict]:
        """Find a state entry by ID in the library manifest."""
        return self.state_library.find_entry(state_id)

    def list_library_entries(self, tag: Optional[str] = None) -> list[dict]:
        """List all entries in the library, optionally filtered by tag."""
        return self.state_library.list_entries(tag=tag)

    def save_library_state(
        self,
        label: str,
        metadata: Optional[dict] = None,
        tags: Optional[list[str]] = None,
        captured_by: str = "agent",
    ) -> tuple[str, list[str]]:
        """Save a labeled state to the library and return its ID and warnings."""
        if metadata is None:
            metadata = self.capture_state_metadata()
        return self.state_library.save_labeled_state(
            self.bridge, label, metadata=metadata, tags=tags, captured_by=captured_by
        )

    def load_library_state(self, state_id: str) -> bool:
        """Load a save state from the library by ID."""
        return self.state_library.load_state(self.bridge, state_id)

    def verify_library_state(self, state_id: str, verified_by: str = "scawful") -> bool:
        """Promote a draft state to canon status after verification.
        
        Loads the state and runs the StateValidator to ensure it is healthy.
        """
        # 1. Load and validate
        try:
            # Load with validation enabled
            if not self.state_library.load_state(self.bridge, state_id, validate=True, strict=True):
                self.last_error = f"Verification failed for {state_id}: Validation errors or stall detected."
                return False
        except Exception as e:
            self.last_error = f"Verification failed for {state_id}: {e}"
            return False

        # 2. Promote in manifest
        return self.state_library.verify_state(state_id, verified_by=verified_by)

    def deprecate_library_state(self, state_id: str, reason: str = "") -> bool:
        """Mark a state as deprecated."""
        return self.state_library.deprecate_state(state_id, reason=reason)

    def backfill_library_hashes(self) -> int:
        """Compute and store hashes for entries missing md5 field."""
        return self.state_library.backfill_hashes()

    def scan_library(self) -> int:
        """Scan library directory for unmanaged states and add them."""
        return self.state_library.scan_library()

    def get_library_sets(self) -> list[dict]:
        """List all state sets in the library."""
        return self.state_library.get_sets()

    def capture_state_metadata(self) -> dict:
        """Capture current game state as metadata for library entries."""
        state = self.get_oracle_state()
        story = self.get_story_state()

        return {
            "module": state["mode"],
            "room": state["room"],
            "area": state["area"],
            "indoors": bool(state["indoors"]),
            # Link state
            "link_x": state["link_x"],
            "link_y": state["link_y"],
            "link_state": state["link_state"],
            "link_form": state["link_form"],
            "link_form_name": state["link_form_name"],
            "link_dir": state["link_dir"],
            # Time system
            "time_hours": state["time_hours"],
            "time_minutes": state["time_minutes"],
            "time_speed": state["time_speed"],
            # Player stats
            "health": state["health"],
            "max_health": state["max_health"],
            "magic": state["magic"],
            "rupees": state["rupees"],
            # Story progress
            "game_state": story["game_state"],
            "oosprog": story["oosprog"],
            "oosprog2": story["oosprog2"],
            "crystals": story["crystals"],
            "pendants": story["pendants"],
            # Descriptive fields
            "location": self._describe_location(state),
            "summary": self._describe_state(state, story),
        }

    def _describe_location(self, state: dict) -> str:
        """Generate a human-readable location description."""
        # Use the pre-computed names from get_oracle_state()
        if "area_name" in state:
            return state["area_name"]

        # Fallback for older state format
        area = state["area"]
        if state["indoors"]:
            dungeon_room = state.get("dungeon_room", state["room"])
            room_name = ROOM_NAMES.get(dungeon_room, f"Room 0x{dungeon_room:02X}")
            return f"Inside: {room_name}"
        elif area in LOST_WOODS_AREAS:
            return "Lost Woods"
        else:
            return OVERWORLD_AREAS.get(area, f"Overworld Area 0x{area:02X}")

    def _describe_state(self, state: dict, story: dict) -> str:
        """Generate a summary of current game state."""
        parts = []
        parts.append(f"Mode: {MODE_NAMES.get(state['mode'], 'Unknown')}")
        parts.append(f"GameState: {story['game_state']}")
        if story["crystals"]:
            parts.append(f"Crystals: 0x{story['crystals']:02X}")
        return " | ".join(parts)
