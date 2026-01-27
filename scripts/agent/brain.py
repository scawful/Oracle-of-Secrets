"""
Oracle of Secrets Agent Brain
Implements intelligent state tracking, navigation, and save state management.

Usage:
    from agent.brain import AgentBrain

    # Initialize
    agent = AgentBrain()

    # Navigate to a target tile (x, y)
    # This will use A* pathfinding and draw the path on the emulator screen
    success = agent.follow_path(target_tx=50, target_ty=60, timeout_seconds=15)

    if success:
        print("Arrived!")
        # Save safely (checks health, collision, game mode)
        agent.validate_and_save(slot=1)
    else:
        print("Failed to reach destination")
"""

import math
import heapq
import time
from typing import List, Tuple, Optional, Set, Union

try:
    from mesen2_client_lib.client import OracleDebugClient
except ImportError:
    from scripts.mesen2_client_lib.client import OracleDebugClient

# Constants
TILE_SIZE = 8  # Collision tiles are 8x8 pixels
# COLLISION_DUMP returns 64 rows x 32 collision values (interleaved format)
MAP_WIDTH = 32  # 32 tiles wide per screen
MAP_HEIGHT = 64  # 64 tiles tall per screen

# Navigation costs
COST_STRAIGHT = 10
COST_DIAGONAL = 14

class TileType:
    """Collision tile types from ALTTP/Oracle."""
    WALKABLE = 0x00
    SOLID = 0x01
    DEEP_WATER = 0x08
    SHALLOW_WATER = 0x09
    WATER_EDGE = 0x0A
    PIT = 0x20
    LADDER = 0x22
    LEDGE_UP = 0x28
    LEDGE_DOWN = 0x29
    LEDGE_LEFT = 0x2A
    LEDGE_RIGHT = 0x2B
    GRASS = 0x40
    ELEVATED_WALKABLE = 0x48
    ELEVATED_VARIANT = 0x58
    DAMAGE_FLOOR = 0x60
    SPIKE = 0x62
    WARP = 0x80

# Expanded walkable tiles from Pathfinder module + empirical data
WALKABLE_TILES = {
    TileType.WALKABLE,
    TileType.GRASS,
    TileType.SHALLOW_WATER,
    TileType.WATER_EDGE,
    TileType.LADDER,
    TileType.ELEVATED_WALKABLE,
    TileType.ELEVATED_VARIANT,
    0x08,  # Dark World floor (Oracle uses 0x08 differently from ALTTP)
    0x10, 0x15, 0x18, 0x1D, 0x28, 0x68  # Legacy empirical values
}

# Tiles that require flippers
SWIM_TILES = {
    TileType.DEEP_WATER,
}

# B008 Bug Workaround: Direction Button Rotation
# Some Mesen2 instances show a 90° clockwise rotation for directional inputs.
# To move in a desired direction, we must send the button 90° CCW from what we want:
#   To move RIGHT (increase X) → Press DOWN
#   To move DOWN  (increase Y) → Press RIGHT
#   To move LEFT  (decrease X) → Press UP
#   To move UP    (decrease Y) → Press LEFT
B008_DIRECTION_CORRECTION = {
    "right": "down",
    "down": "right",
    "left": "up",
    "up": "left",
}

class GameState:
    """Encapsulates the current state of the game."""
    def __init__(self, client: OracleDebugClient):
        self.client = client
        self.raw_oracle = {}
        self.raw_story = {}
        self.update()

    def update(self):
        """Fetch fresh state from the emulator."""
        self.raw_oracle = self.client.get_oracle_state()
        self.raw_story = self.client.get_story_state()

    @property
    def link_pos(self) -> Tuple[int, int]:
        return (self.raw_oracle.get("link_x", 0), self.raw_oracle.get("link_y", 0))

    @property
    def link_tile(self) -> Tuple[int, int]:
        """Link's world tile coordinates (for pathfinding across screens)."""
        x, y = self.link_pos
        return (x // TILE_SIZE, y // TILE_SIZE)

    @property
    def link_screen_tile(self) -> Tuple[int, int]:
        """Link's screen-relative tile coordinates (for collision map lookup).

        The collision map is 32x64 tiles for the current screen.
        We need to wrap world coordinates to screen coordinates.
        """
        x, y = self.link_pos
        # Screen is 256 pixels wide (32 tiles), 512 pixels tall (64 tiles for scrolling areas)
        screen_x = x % 256
        screen_y = y % 512
        return (screen_x // TILE_SIZE, screen_y // TILE_SIZE)

    @property
    def health(self) -> int:
        return self.raw_oracle.get("health", 0)

    @property
    def max_health(self) -> int:
        return self.raw_oracle.get("max_health", 0)

    @property
    def mode(self) -> int:
        return self.raw_oracle.get("mode", 0)

    @property
    def area(self) -> int:
        return self.raw_oracle.get("area", 0)
        
    @property
    def room(self) -> int:
        return self.raw_oracle.get("room", 0)

    @property
    def is_indoors(self) -> bool:
        return bool(self.raw_oracle.get("indoors", False))

    @property
    def is_gameplay(self) -> bool:
        """True if in standard gameplay modes (Overworld or Dungeon)."""
        return self.mode in [0x07, 0x09]

    @property
    def link_state(self) -> int:
        return self.raw_oracle.get("link_state", 0)
    
    @property
    def is_swimming(self) -> bool:
        return self.link_state == 0x04

    def __repr__(self):
        return f"<GameState Mode=0x{self.mode:02X} Pos={self.link_pos} HP={self.health}/{self.max_health}>"


class Navigator:
    """Handles pathfinding and collision checking."""
    def __init__(self, client: OracleDebugClient):
        self.client = client
        self.collision_map: Optional[bytes] = None
        self.last_map_id: Optional[str] = None # Tracks if we changed rooms
        self.known_tiles = set()

    def refresh_map(self, current_area_id: str):
        """Download new collision map if area changed."""
        if current_area_id != self.last_map_id:
            # print(f"Navigator: Refreshing collision map for {current_area_id}")
            self.collision_map = self.client.get_collision_map()
            self.last_map_id = current_area_id

    def is_walkable(self, tx: int, ty: int, is_swimming: bool = False) -> bool:
        """Check if a tile coordinate is walkable."""
        if not self.collision_map:
            return True  # Assume walkable if no map

        if tx < 0 or tx >= MAP_WIDTH or ty < 0 or ty >= MAP_HEIGHT:
            return False

        idx = ty * MAP_WIDTH + tx
        if idx >= len(self.collision_map):
            return False

        tile_type = self.collision_map[idx]

        # Debug: Log new tile types
        if tile_type not in self.known_tiles:
            self.known_tiles.add(tile_type)
            # print(f"Navigator: Discovered new tile type 0x{tile_type:02X} at ({tx},{ty})")

        if tile_type in WALKABLE_TILES:
            return True
            
        if is_swimming and tile_type in SWIM_TILES:
            return True

        return False

    def get_neighbors(self, node: Tuple[int, int], is_swimming: bool = False) -> List[Tuple[int, int]]:
        x, y = node
        neighbors = []
        # 4-directional movement (safer for SNES grid)
        # Diagonals can get stuck on corners easily without sub-pixel logic
        dirs = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny, is_swimming):
                neighbors.append((nx, ny))
        return neighbors

    def find_path(self, start: Tuple[int, int], end: Tuple[int, int], is_swimming: bool = False) -> List[Tuple[int, int]]:
        """A* Pathfinding from start tile to end tile."""
        if not self.is_walkable(end[0], end[1], is_swimming):
            # print(f"Navigator: Target {end} is not walkable (Tile: 0x{self.get_tile_at(*end):02X}).")
            return []

        start_node = start
        end_node = end
        
        open_set = []
        heapq.heappush(open_set, (0, start_node))
        
        came_from = {}
        g_score = {start_node: 0}
        f_score = {start_node: self.heuristic(start_node, end_node)}
        
        while open_set:
            current = heapq.heappop(open_set)[1]
            
            if current == end_node:
                return self.reconstruct_path(came_from, current)
            
            for neighbor in self.get_neighbors(current, is_swimming):
                tentative_g = g_score[current] + COST_STRAIGHT
                
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self.heuristic(neighbor, end_node)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
                    
        return [] # No path found

    def get_tile_at(self, tx: int, ty: int) -> int:
        if not self.collision_map or tx < 0 or tx >= MAP_WIDTH or ty < 0 or ty >= MAP_HEIGHT:
            return 0x01 # Solid
        idx = ty * MAP_WIDTH + tx
        if idx >= len(self.collision_map):
            return 0x01
        return self.collision_map[idx]

    def heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) * 10

    def reconstruct_path(self, came_from, current):
        total_path = [current]
        while current in came_from:
            current = came_from[current]
            total_path.append(current)

        path = total_path[::-1]

        # Visual debug: draw path on emulator overlay
        try:
            pixel_path = []
            for tx, ty in path:
                # Convert tile to pixel, offset to center of tile
                pixel_path.append((tx * TILE_SIZE + 4, ty * TILE_SIZE + 4))
            self.client.draw_path(pixel_path)
        except Exception:
            pass  # Non-critical - don't fail pathfinding if overlay fails

        return path


class SaveManager:
    """Manages save states with validity checking."""
    
    def __init__(self, client: OracleDebugClient, nav: Navigator, library: Optional['StateLibrary'] = None):
        self.client = client
        self.nav = nav
        # Late import to avoid circular dependency if not careful
        from mesen2_client_lib.state_library import StateLibrary
        self.library = library or StateLibrary()

    def is_state_valid(self, state: GameState) -> Tuple[bool, str]:
        """Check if the current state is safe to save."""
        # 1. Check Game Mode
        if not state.is_gameplay:
            return False, f"Invalid Mode: 0x{state.mode:02X}"

        # 2. Check Health
        if state.health <= 0:
            return False, "Link is dead (0 HP)"

        # 3. Check Link State (0=Ground, 4=Swim, others might be unsafe like falling)
        if state.link_state not in [0, 4, 0x14, 0x18]: # Ground, Swim, Bunny, Dash
            return False, f"Unsafe Action State: 0x{state.link_state:02X}"

        # 4. Check Collision (don't save inside a wall)
        # Use screen-relative tile for collision map lookup
        tx, ty = state.link_screen_tile
        # We check the center tile and adjacent tiles for robustness
        # Link's hitbox is roughly 16x16 pixels, so check a small area
        if not self.nav.is_walkable(tx, ty, state.is_swimming):
            # Try slightly offset to avoid false positives on tile edges
            if not self.nav.is_walkable(tx + 1, ty, state.is_swimming) and not self.nav.is_walkable(tx, ty + 1, state.is_swimming):
                return False, f"Link inside collision at screen tile ({tx},{ty})"

        return True, "Safe"

    def save_smart_state(self, slot: int, state: GameState) -> bool:
        """Save state only if valid."""
        is_valid, reason = self.is_state_valid(state)
        if is_valid:
            print(f"SaveManager: State valid. Saving to slot {slot}.")
            return self.client.save_state(slot=slot)
        else:
            print(f"SaveManager: Cannot save. Reason: {reason}")
            return False

    def save_labeled(self, label: str, state: GameState, tags: List[str] = None) -> bool:
        """Save a state to the library with a descriptive label and metadata."""
        is_valid, reason = self.is_state_valid(state)
        if not is_valid:
            print(f"SaveManager: Cannot save labeled state '{label}'. Reason: {reason}")
            return False

        metadata = {
            "area": state.area,
            "room": state.room,
            "mode": state.mode,
            "health": state.health,
            "link_pos": state.link_pos,
            "link_state": state.link_state,
            "indoors": state.is_indoors
        }
        
        try:
            state_id = self.library.save_labeled_state(self.client, label, metadata, tags)
            print(f"SaveManager: Saved labeled state '{label}' (ID: {state_id})")
            return True
        except Exception as e:
            print(f"SaveManager: Failed to save labeled state: {e}")
            return False


class AgentBrain:
    """Main Agent Controller."""
    def __init__(self, apply_b008_correction: Union[bool, str] = "auto"):
        self.client = OracleDebugClient()
        if not self.client.ensure_connected():
            raise ConnectionError("Could not connect to Mesen2 socket.")

        self.state = GameState(self.client)
        self.nav = Navigator(self.client)
        self.saver = SaveManager(self.client, self.nav)
        self._b008_mode = self._normalize_b008_mode(apply_b008_correction)
        self.apply_b008_correction = self._b008_mode == "on"
        self._b008_determined = self._b008_mode != "auto"
        self._b008_calibrating = False

    def _normalize_b008_mode(self, value: Union[bool, str]) -> str:
        if isinstance(value, bool):
            return "on" if value else "off"
        normalized = str(value).strip().lower()
        if normalized in {"on", "off", "auto"}:
            return normalized
        return "auto"

    def set_b008_mode(self, mode: Union[bool, str]) -> None:
        """Manually override B008 correction mode (on/off/auto)."""
        self._b008_mode = self._normalize_b008_mode(mode)
        self.apply_b008_correction = self._b008_mode == "on"
        self._b008_determined = self._b008_mode != "auto"

    def _probe_direction(self, direction: str, frames: int = 6) -> Tuple[int, int]:
        """Press a direction without correction to infer input mapping."""
        self.tick()
        start_x, start_y = self.state.link_pos
        self.client.press_button(direction, frames=frames)
        time.sleep(frames / 60.0 + 0.1)
        self.tick()
        end_x, end_y = self.state.link_pos
        return (end_x - start_x, end_y - start_y)

    def _infer_b008_mode(self, direction: str, dx: int, dy: int, threshold: int = 2) -> Optional[str]:
        if abs(dx) <= threshold and abs(dy) <= threshold:
            return None
        if direction == "right":
            if abs(dx) >= abs(dy) and dx > 0:
                return "off"
            if abs(dy) > abs(dx) and dy > 0:
                return "on"
        if direction == "down":
            if abs(dy) >= abs(dx) and dy > 0:
                return "off"
            if abs(dx) > abs(dy) and dx > 0:
                return "on"
        return None

    def _auto_detect_b008(self) -> None:
        if self._b008_determined or self._b008_calibrating or self._b008_mode != "auto":
            return
        if not self.state.is_gameplay:
            return
        self._b008_calibrating = True
        try:
            dx, dy = self._probe_direction("right")
            inferred = self._infer_b008_mode("right", dx, dy)
            if inferred is None:
                dx, dy = self._probe_direction("down")
                inferred = self._infer_b008_mode("down", dx, dy)
            if inferred is None:
                return
            self._b008_mode = inferred
            self.apply_b008_correction = inferred == "on"
            self._b008_determined = True
        finally:
            self._b008_calibrating = False

    def calibrate_b008(self) -> str:
        """Force B008 auto-detection and return the active mode ('on' or 'off')."""
        self._b008_mode = "auto"
        self._b008_determined = False
        self._auto_detect_b008()
        if not self._b008_determined:
            return "unknown"
        return "on" if self.apply_b008_correction else "off"

    def tick(self) -> bool:
        """Update loop (call this every frame or interval).

        Returns:
            True if state update succeeded, False if connection lost.
        """
        # Periodic health check - reconnect if needed
        if not self.client.ensure_connected():
            return False

        try:
            self.state.update()
        except Exception:
            return False

        # Update map if area changed
        map_id = f"{self.state.area}_{self.state.room}_{self.state.is_indoors}"
        self.nav.refresh_map(map_id)
        return True

    def _corrected_press(self, buttons: str, frames: int = 5) -> bool:
        """Press button(s) with B008 direction correction applied.

        The Mesen2 socket API has a 90° clockwise rotation bug (B008).
        This method transparently corrects directional inputs.
        """
        self._auto_detect_b008()
        if not self.apply_b008_correction:
            return self.client.press_button(buttons, frames=frames)

        # Split, correct, and rejoin button string
        corrected_parts = []
        for btn in buttons.lower().split(","):
            btn = btn.strip()
            if btn in B008_DIRECTION_CORRECTION:
                corrected_parts.append(B008_DIRECTION_CORRECTION[btn])
            else:
                corrected_parts.append(btn)

        corrected_buttons = ",".join(corrected_parts)
        return self.client.press_button(corrected_buttons, frames=frames)

    def goto(self, target_tx: int, target_ty: int):
        """High-level command to move Link one step towards target.

        Note: target_tx and target_ty are SCREEN-RELATIVE tile coordinates
        (0-31 for X, 0-63 for Y) to match the collision map coordinates.
        """
        self.tick()
        self._auto_detect_b008()
        # Use screen-relative tile for pathfinding (matches collision map)
        start_tx, start_ty = self.state.link_screen_tile
        path = self.nav.find_path((start_tx, start_ty), (target_tx, target_ty), self.state.is_swimming)
        
        if not path:
            print("No path found.")
            return

        # Simple follower: move to first node in path
        if len(path) > 1:
            next_node = path[1]  # [0] is current
            dx = next_node[0] - start_tx
            dy = next_node[1] - start_ty

            btn = ""
            if dx > 0:
                btn = "right"
            elif dx < 0:
                btn = "left"

            if dy > 0:
                btn += ",down" if btn else "down"
            elif dy < 0:
                btn += ",up" if btn else "up"

            if btn:
                self._corrected_press(btn, frames=5)

    def follow_path(self, target_tx: int, target_ty: int, timeout_seconds: int = 10, stuck_threshold: int = 5) -> bool:
        """Execute movement until target reached or timeout.

        Note: target_tx and target_ty are SCREEN-RELATIVE tile coordinates
        (0-31 for X, 0-63 for Y) to match the collision map coordinates.

        Args:
            target_tx: Target X tile coordinate (screen-relative)
            target_ty: Target Y tile coordinate (screen-relative)
            timeout_seconds: Maximum time to attempt pathfinding
            stuck_threshold: Number of consecutive ticks without movement before giving up

        Returns:
            True if target reached, False otherwise
        """
        start_time = time.time()
        last_pos = None
        stuck_count = 0

        while time.time() - start_time < timeout_seconds:
            if not self.tick():
                # Connection lost
                return False

            # Use screen-relative tile for distance checking
            curr_tx, curr_ty = self.state.link_screen_tile
            curr_pos = (curr_tx, curr_ty)

            # Stuck detection: if position hasn't changed for too many ticks
            if curr_pos == last_pos:
                stuck_count += 1
                if stuck_count >= stuck_threshold:
                    # Try to break out of stuck state
                    # Check if we're in valid gameplay mode
                    if not self.state.is_gameplay:
                        return False  # Can't navigate in non-gameplay mode
                    # Reset and try a different approach (could add evasive maneuver here)
                    stuck_count = 0
            else:
                stuck_count = 0
            last_pos = curr_pos

            # Check arrival (allow 1 tile tolerance)
            dist = abs(curr_tx - target_tx) + abs(curr_ty - target_ty)
            if dist <= 1:
                return True

            self.goto(target_tx, target_ty)

            # Yield/Wait slightly to allow physics
            time.sleep(0.1)

        return False

    def validate_and_save(self, slot: int):
        self.tick()
        self.saver.save_smart_state(slot, self.state)

    def save_labeled(self, label: str, tags: List[str] = None) -> bool:
        """Save current state with a label and metadata."""
        self.tick()
        return self.saver.save_labeled(label, self.state, tags)

    def move(self, direction: str, frames: int = 30) -> Tuple[int, int]:
        """Move Link in a direction and return displacement (dx, dy).

        Args:
            direction: "up", "down", "left", or "right"
            frames: Number of frames to hold the direction

        Returns:
            Tuple of (dx, dy) showing actual pixel displacement
        """
        self.tick()
        self._auto_detect_b008()
        self.tick()
        start_x, start_y = self.state.link_pos

        self._corrected_press(direction.lower(), frames=frames)

        # Wait for movement to complete
        time.sleep(frames / 60.0 + 0.1)

        self.tick()
        end_x, end_y = self.state.link_pos

        dx = end_x - start_x
        dy = end_y - start_y
        return (dx, dy)

    def explore_area(self, steps: int = 10, save_slot_start: int = 30) -> List[Tuple[int, int, int]]:
        """Randomly explore the current area and save at interesting positions.

        Args:
            steps: Number of exploration steps
            save_slot_start: First save slot to use

        Returns:
            List of (slot, area, (x, y)) for successful saves
        """
        import random
        directions = ["up", "down", "left", "right"]
        saves = []
        slot = save_slot_start

        for step in range(steps):
            direction = random.choice(directions)
            dx, dy = self.move(direction, frames=30)

            self.tick()
            pos = self.state.link_pos
            area = self.state.area

            # Try to save if in a new position
            if abs(dx) > 5 or abs(dy) > 5:
                is_valid, reason = self.saver.is_state_valid(self.state)
                if is_valid:
                    if self.client.save_state(slot=slot):
                        saves.append((slot, area, pos))
                        print(f"[Step {step+1}] Saved slot {slot}: Area 0x{area:02X} @ {pos}")
                        # Also save to library
                        self.save_labeled(f"explore_area_{area:02X}", tags=["exploration"])
                        slot += 1
                else:
                    print(f"[Step {step+1}] Skip save: {reason}")

        return saves


if __name__ == "__main__":
    print("AgentBrain initialized. Use interactively or import.")
    # Example usage:
    # agent = AgentBrain()
    # agent.tick()
    # print(agent.state)
