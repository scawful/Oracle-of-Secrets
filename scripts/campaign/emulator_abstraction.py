"""Unified emulator interface for Oracle of Secrets testing.

This module provides an abstraction layer over different emulators,
with Mesen2 as the primary supported backend.

Campaign Goals Supported:
- C.1: Unified emulator abstraction
- D.1: Game state parser
- D.4: Input sequence recorder and playback

Usage:
    from scripts.campaign.emulator_abstraction import Mesen2Emulator

    emu = Mesen2Emulator()
    if emu.connect():
        state = emu.read_state()
        emu.inject_input(["RIGHT"], frames=30)
        emu.save_state("test_state")
"""

from __future__ import annotations

import os
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class EmulatorStatus(IntEnum):
    """Emulator connection status."""
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    RUNNING = 3
    PAUSED = 4
    ERROR = 5


@dataclass
class MemoryRead:
    """Result of a memory read operation."""
    address: int
    value: int
    size: int = 1

    @property
    def value16(self) -> int:
        """Interpret as 16-bit little-endian."""
        return self.value if self.size >= 2 else self.value

    @property
    def value24(self) -> int:
        """Interpret as 24-bit little-endian."""
        return self.value if self.size >= 3 else self.value


@dataclass
class GameStateSnapshot:
    """Snapshot of game state at a point in time."""
    timestamp: float
    mode: int
    submode: int
    area: int
    room: int
    link_x: int
    link_y: int
    link_z: int
    link_direction: int
    link_state: int
    indoors: bool
    inidisp: int
    health: int
    max_health: int
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_playing(self) -> bool:
        """Check if in playable state (mode 0x07 or 0x09)."""
        return self.mode in (0x07, 0x09)

    @property
    def is_overworld(self) -> bool:
        """Check if on overworld (mode 0x09)."""
        return self.mode == 0x09

    @property
    def is_dungeon(self) -> bool:
        """Check if in dungeon/indoor (mode 0x07)."""
        return self.mode == 0x07

    @property
    def is_black_screen(self) -> bool:
        """Check for black screen condition (INIDISP = 0x80)."""
        return self.inidisp == 0x80 and self.mode in (0x06, 0x07)

    @property
    def position(self) -> Tuple[int, int]:
        """Return (x, y) position tuple."""
        return (self.link_x, self.link_y)


class EmulatorInterface(ABC):
    """Abstract interface for emulator control.

    All emulator backends (Mesen2) must implement this interface.
    """

    @abstractmethod
    def connect(self, timeout: float | None = None) -> bool:
        """Establish connection to emulator.

        Returns:
            True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to emulator."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if emulator is connected and responsive."""
        pass

    @abstractmethod
    def get_status(self) -> EmulatorStatus:
        """Get current emulator status."""
        pass

    # Memory operations
    @abstractmethod
    def read_memory(self, address: int, size: int = 1) -> MemoryRead:
        """Read bytes from memory.

        Args:
            address: Memory address (SNES address space)
            size: Number of bytes to read (1, 2, or 3)

        Returns:
            MemoryRead object with value
        """
        pass

    @abstractmethod
    def write_memory(self, address: int, value: int, size: int = 1) -> bool:
        """Write bytes to memory.

        Args:
            address: Memory address
            value: Value to write
            size: Number of bytes (1, 2, or 3)

        Returns:
            True if write successful
        """
        pass

    # State operations
    @abstractmethod
    def read_state(self) -> GameStateSnapshot:
        """Read current game state.

        Returns:
            GameStateSnapshot with all game state values
        """
        pass

    @abstractmethod
    def save_state(self, name: str) -> Optional[str]:
        """Save emulator state to file.

        Args:
            name: State name/identifier

        Returns:
            Path to saved state file, or None on failure
        """
        pass

    @abstractmethod
    def load_state(self, path: str) -> bool:
        """Load emulator state from file.

        Args:
            path: Path to state file

        Returns:
            True if load successful
        """
        pass

    # Control operations
    @abstractmethod
    def pause(self) -> bool:
        """Pause emulation."""
        pass

    @abstractmethod
    def resume(self) -> bool:
        """Resume emulation."""
        pass

    @abstractmethod
    def step_frame(self, count: int = 1) -> bool:
        """Advance specified number of frames.

        Args:
            count: Number of frames to advance

        Returns:
            True if successful
        """
        pass

    # Input operations
    @abstractmethod
    def inject_input(
        self,
        buttons: List[str],
        frames: int = 1,
        release: bool = True
    ) -> bool:
        """Inject controller input.

        Args:
            buttons: List of button names (A, B, X, Y, L, R, UP, DOWN, LEFT, RIGHT, START, SELECT)
            frames: Number of frames to hold
            release: Whether to release buttons after frames

        Returns:
            True if injection successful
        """
        pass

    # Screenshot
    @abstractmethod
    def screenshot(self, path: Optional[str] = None) -> Optional[str]:
        """Capture screenshot.

        Args:
            path: Optional output path. If None, generates path.

        Returns:
            Path to screenshot file, or None on failure
        """
        pass


class Mesen2Emulator(EmulatorInterface):
    """Mesen2 emulator backend using socket API.

    This is the primary emulator for Oracle of Secrets debugging.
    Requires the Mesen2-OOS fork with socket server enabled.
    """

    # Key RAM addresses for Oracle of Secrets
    RAM_MODE = 0x7E0010
    RAM_SUBMODE = 0x7E0011
    RAM_INIDISP = 0x7E001A
    RAM_INDOORS = 0x7E001B
    RAM_AREA_ID = 0x7E008A
    RAM_ROOM_LAYOUT = 0x7E00A0
    RAM_ROOM_ID = 0x7E00A4
    RAM_LINK_X = 0x7E0022
    RAM_LINK_Y = 0x7E0020
    RAM_LINK_Z = 0x7E0024
    RAM_LINK_DIR = 0x7E002F
    RAM_LINK_STATE = 0x7E005D
    RAM_HEALTH = 0x7EF36D
    RAM_MAX_HEALTH = 0x7EF36C

    def __init__(self, socket_path: Optional[str] = None):
        """Initialize Mesen2 backend.

        Args:
            socket_path: Explicit socket path. If None, auto-discovers.
        """
        self._socket_path = socket_path
        self._bridge = None
        self._status = EmulatorStatus.DISCONNECTED

    def _get_bridge(self):
        """Lazy-load bridge to avoid import errors when not needed."""
        if self._bridge is None:
            try:
                from scripts.mesen2_client_lib.bridge import MesenBridge
                self._bridge = MesenBridge(self._socket_path)
            except ImportError as e:
                raise RuntimeError(
                    f"Cannot import MesenBridge. Ensure oracle-of-secrets scripts are available: {e}"
                )
        return self._bridge

    def connect(self, timeout: float | None = None) -> bool:
        """Connect to Mesen2 socket server.

        Args:
            timeout: Optional maximum time (seconds) to wait for connection.
        """
        try:
            self._status = EmulatorStatus.CONNECTING
            bridge = self._get_bridge()

            if timeout is None:
                ok = bridge.is_connected()
            else:
                deadline = time.time() + max(0.0, float(timeout))
                ok = False
                while time.time() < deadline:
                    if bridge.is_connected():
                        ok = True
                        break
                    time.sleep(0.1)

            if ok:
                self._status = EmulatorStatus.CONNECTED
                return True

            self._status = EmulatorStatus.ERROR
            return False

        except Exception as e:
            self._status = EmulatorStatus.ERROR
            return False

    def disconnect(self) -> None:
        """Disconnect from Mesen2."""
        self._bridge = None
        self._status = EmulatorStatus.DISCONNECTED

    def is_connected(self) -> bool:
        """Check Mesen2 connection."""
        try:
            return self._get_bridge().is_connected()
        except Exception:
            return False

    def get_status(self) -> EmulatorStatus:
        """Get current status."""
        if self.is_connected():
            # Could check if paused via socket command
            return EmulatorStatus.CONNECTED
        return self._status

    def read_memory(self, address: int, size: int = 1) -> MemoryRead:
        """Read memory via socket API."""
        bridge = self._get_bridge()

        if size == 1:
            value = bridge.read_memory(address)
        elif size == 2:
            value = bridge.read_memory16(address)
        elif size == 3:
            value = bridge.read_memory24(address)
        else:
            raise ValueError(f"Invalid size {size}, must be 1, 2, or 3")

        return MemoryRead(address=address, value=value, size=size)

    def write_memory(self, address: int, value: int, size: int = 1) -> bool:
        """Write memory via socket API."""
        bridge = self._get_bridge()

        try:
            if size == 1:
                bridge.write_memory(address, value)
            elif size == 2:
                bridge.write_memory(address, value & 0xFF)
                bridge.write_memory(address + 1, (value >> 8) & 0xFF)
            elif size == 3:
                bridge.write_memory(address, value & 0xFF)
                bridge.write_memory(address + 1, (value >> 8) & 0xFF)
                bridge.write_memory(address + 2, (value >> 16) & 0xFF)
            else:
                return False
            return True
        except Exception:
            return False

    def read_state(self) -> GameStateSnapshot:
        """Read comprehensive game state."""
        bridge = self._get_bridge()

        return GameStateSnapshot(
            timestamp=time.time(),
            mode=bridge.read_memory(self.RAM_MODE),
            submode=bridge.read_memory(self.RAM_SUBMODE),
            area=bridge.read_memory(self.RAM_AREA_ID),
            room=bridge.read_memory(self.RAM_ROOM_LAYOUT),
            link_x=bridge.read_memory16(self.RAM_LINK_X),
            link_y=bridge.read_memory16(self.RAM_LINK_Y),
            link_z=bridge.read_memory16(self.RAM_LINK_Z),
            link_direction=bridge.read_memory(self.RAM_LINK_DIR),
            link_state=bridge.read_memory(self.RAM_LINK_STATE),
            indoors=bridge.read_memory(self.RAM_INDOORS) != 0,
            inidisp=bridge.read_memory(self.RAM_INIDISP),
            health=bridge.read_memory(self.RAM_HEALTH),
            max_health=bridge.read_memory(self.RAM_MAX_HEALTH),
            raw_data={
                "room_id": bridge.read_memory16(self.RAM_ROOM_ID),
            }
        )

    def save_state(self, name: str) -> Optional[str]:
        """Save a state file via the socket API.

        If `name` looks like a filesystem path, it is used directly. Otherwise,
        a deterministic path under /tmp is chosen.
        """
        bridge = self._get_bridge()

        if name.endswith(".mss") or "/" in name or ("\\" in name):
            path = name
        else:
            state_dir = Path(tempfile.gettempdir()) / "oos_campaign" / "states"
            state_dir.mkdir(parents=True, exist_ok=True)
            path = str(state_dir / f"{name}.mss")

        try:
            if bridge.save_state(path=path):
                return path
        except Exception:
            pass
        return None

    def load_state(self, path: str) -> bool:
        """Load state via socket command.

        Args:
            path: Absolute path to .mss state file

        Returns:
            True if state loaded successfully
        """
        bridge = self._get_bridge()

        try:
            # Use LOADSTATE (no underscore) - the correct Mesen2 command
            result = bridge.send_command("LOADSTATE", {"path": path})
            return result.get("success", False)
        except Exception:
            return False

    def load_state_by_id(self, state_id: str) -> bool:
        """Load state from the state library by ID.

        Args:
            state_id: State ID from save_state_library.json (e.g., 'baseline_1')

        Returns:
            True if state loaded successfully
        """
        try:
            from scripts.mesen2_client_lib.state_library import StateLibrary

            library = StateLibrary()
            entry = library.find_entry(state_id)
            if not entry:
                return False

            state_path = library.resolve_path(entry)
            return self.load_state(str(state_path))
        except Exception:
            return False

    def pause(self) -> bool:
        """Pause emulation."""
        bridge = self._get_bridge()

        try:
            result = bridge.send_command("PAUSE")
            return result.get("success", False)
        except Exception:
            return False

    def resume(self) -> bool:
        """Resume emulation."""
        bridge = self._get_bridge()

        try:
            result = bridge.send_command("RESUME")
            return result.get("success", False)
        except Exception:
            return False

    def step_frame(self, count: int = 1) -> bool:
        """Step forward specified frames."""
        bridge = self._get_bridge()

        try:
            result = bridge.send_command("STEP", {"frames": count})
            return result.get("success", False)
        except Exception:
            return False

    def inject_input(
        self,
        buttons: List[str],
        frames: int = 1,
        release: bool = True
    ) -> bool:
        """Inject controller input.

        Args:
            buttons: List of button names. Valid: A, B, X, Y, L, R,
                     Up, Down, Left, Right, Start, Select
            frames: Number of frames to hold (default 1)
            release: Whether to release after (ignored, always releases)

        Returns:
            True if input injected successfully
        """
        bridge = self._get_bridge()

        # Normalize button names to Mesen2 format (Title case)
        button_map = {
            'UP': 'Up', 'DOWN': 'Down', 'LEFT': 'Left', 'RIGHT': 'Right',
            'A': 'A', 'B': 'B', 'X': 'X', 'Y': 'Y',
            'L': 'L', 'R': 'R', 'START': 'Start', 'SELECT': 'Select'
        }
        normalized = []
        for b in buttons:
            normalized.append(button_map.get(b.upper(), b.title()))

        try:
            # Use bridge.press_button which sends correct format
            button_str = ','.join(normalized)
            return bool(bridge.press_button(button_str, frames=frames))
        except Exception:
            return False

    def screenshot(self, path: Optional[str] = None) -> Optional[str]:
        """Capture screenshot."""
        bridge = self._get_bridge()

        try:
            params = {}
            if path:
                params["path"] = path

            result = bridge.send_command("SCREENSHOT", params)
            if result.get("success"):
                return result.get("data", {}).get("path")
            return None
        except Exception:
            return None

    # Mesen2-specific methods

    def p_watch_start(self, depth: int = 100) -> bool:
        """Start P register logging (Mesen2-OOS extension)."""
        bridge = self._get_bridge()

        try:
            result = bridge.send_command("P_WATCH_START", {"depth": depth})
            return result.get("success", False)
        except Exception:
            return False

    def p_watch_stop(self) -> Optional[List[Dict]]:
        """Stop P register logging and return log."""
        bridge = self._get_bridge()

        try:
            result = bridge.send_command("P_WATCH_STOP")
            if result.get("success"):
                return result.get("data", {}).get("log", [])
            return None
        except Exception:
            return None

    def mem_blame(self, address: int) -> Optional[Dict]:
        """Get info about last write to address (Mesen2-OOS extension)."""
        bridge = self._get_bridge()

        try:
            result = bridge.send_command("MEM_BLAME", {"address": address})
            if result.get("success"):
                return result.get("data")
            return None
        except Exception:
            return None


def get_emulator(backend: str = "mesen2", **kwargs) -> EmulatorInterface:
    """Factory function to create emulator instance.

    Args:
        backend: Emulator type ("mesen2" currently supported)
        **kwargs: Backend-specific arguments

    Returns:
        EmulatorInterface implementation

    Raises:
        ValueError: If backend is not supported
    """
    if backend == "mesen2":
        return Mesen2Emulator(**kwargs)
    else:
        raise ValueError(f"Unknown emulator backend: {backend}")
