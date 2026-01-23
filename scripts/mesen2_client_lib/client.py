"""Oracle of Secrets debugging client wrapping MesenBridge."""

from __future__ import annotations

from typing import Optional

from .bridge import MesenBridge
from .constants import (
    BUTTONS,
    DIRECTION_NAMES,
    DUNGEON_INFO,
    ENTRANCE_INFO,
    FORM_NAMES,
    ITEMS,
    LOST_WOODS_AREAS,
    MODE_NAMES,
    OracleRAM,
    OVERWORLD_AREAS,
    ROOM_NAMES,
    STORY_FLAGS,
    WARP_LOCATIONS,
    WATCH_PROFILES,
)
from .issues import KNOWN_ISSUES
from .state_library import StateLibrary


class OracleDebugClient:
    """Oracle of Secrets debugging client wrapping MesenBridge."""

    def __init__(self, socket_path: Optional[str] = None):
        self.bridge = MesenBridge(socket_path)
        self._last_area: Optional[int] = None
        self._watch_profile = "overworld"
        self.state_library = StateLibrary()

    def is_connected(self) -> bool:
        return self.bridge.is_connected()

    # --- State Reading ---

    def get_oracle_state(self) -> dict:
        """Get Oracle-specific game state."""
        mode = self.bridge.read_memory(OracleRAM.MODE)
        link_form = self.bridge.read_memory(OracleRAM.LINK_FORM)
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
            "link_dir": self.bridge.read_memory(OracleRAM.LINK_DIR),
            "link_dir_name": DIRECTION_NAMES.get(
                self.bridge.read_memory(OracleRAM.LINK_DIR), "?"
            ),
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
    ) -> bool:
        """Warp Link to a location or specific coordinates.

        NOTE: Area changes via direct memory writes are experimental and may
        cause issues. For reliable area warps, use the Lua bridge via HTTP.
        Position-only teleports (same area) work reliably.

        Args:
            location: Named location from WARP_LOCATIONS
            area: Area ID (hex) - WARNING: may not work correctly
            x, y: Coordinates
            kind: "ow" for overworld, "uw" for underworld/dungeon
        """
        target_area = area
        if location and location in WARP_LOCATIONS:
            target_area, x, y, _ = WARP_LOCATIONS[location]

        if x is None or y is None:
            raise ValueError("Must specify location name or x+y coordinates")

        success = True

        # Always set position
        success &= self.bridge.write_memory16(OracleRAM.LINK_X, x)
        success &= self.bridge.write_memory16(OracleRAM.LINK_Y, y)

        # Only change area if explicitly requested and different from current
        if target_area is not None:
            current_area = self.bridge.read_memory(OracleRAM.AREA_ID)
            if target_area != current_area:
                # WARNING: This is experimental and may not work correctly
                # For proper area transitions, use the Lua bridge HTTP server
                print(
                    f"WARNING: Area change from 0x{current_area:02X} to 0x{target_area:02X} is experimental"
                )
                success &= self.bridge.write_memory(OracleRAM.AREA_ID, target_area)

        return success

    def set_position(self, x: int, y: int) -> bool:
        """Set Link's position without changing area (instant teleport)."""
        success = True
        success &= self.bridge.write_memory16(OracleRAM.LINK_X, x)
        success &= self.bridge.write_memory16(OracleRAM.LINK_Y, y)
        return success

    # --- Input Injection ---

    def press_button(self, buttons: str, frames: int = 5) -> bool:
        """Press button(s) for specified frames.

        Args:
            buttons: Comma-separated button names (a,b,up,down,left,right,start,select,l,r,x,y)
            frames: Number of frames to hold (default 5, ~83ms at 60fps). 0 = indefinite.
        """
        # Normalize button names
        btn_list = []
        for btn in buttons.lower().replace(" ", "").split(","):
            if btn in BUTTONS:
                btn_list.append(BUTTONS[btn])
            else:
                btn_list.append(btn.upper())

        btn_str = ",".join(btn_list)
        return self.bridge.press_button(btn_str, frames=frames)

    def hold_direction(self, direction: str, frames: int = 30) -> bool:
        """Hold a direction for specified frames.

        Args:
            direction: Direction to hold (up, down, left, right)
            frames: Number of frames to hold (default 30, ~500ms at 60fps)
        """
        dir_map = {"up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT"}
        if direction.lower() not in dir_map:
            raise ValueError(f"Invalid direction: {direction}")
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
        return self.bridge.save_state(**kw)

    def load_state(self, **kw):
        return self.bridge.load_state(**kw)

    def add_breakpoint(self, **kw):
        return self.bridge.add_breakpoint(**kw)

    def get_cpu_state(self):
        return self.bridge.get_cpu_state()

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

    def load_library_state(self, state_id: str) -> bool:
        """Load a save state from the library by ID."""
        return self.state_library.load_state(self.bridge, state_id)

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
