"""Game state parsing and awareness for Oracle of Secrets.

This module provides semantic interpretation of raw game state,
converting memory values into meaningful game concepts.

Campaign Goals Supported:
- D.1: Game state parser (mode, area, inventory)
- D.3: NPC/sprite awareness system (partial)

Usage:
    from scripts.campaign.game_state import GameStateParser

    parser = GameStateParser()
    state = parser.parse(raw_snapshot)
    print(f"Location: {state.location_name}")
    print(f"Is combat: {state.is_combat}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Dict, List, Optional, Tuple

from .emulator_abstraction import GameStateSnapshot


class GamePhase(IntEnum):
    """High-level game phase."""
    UNKNOWN = 0
    BOOT = auto()
    TITLE_SCREEN = auto()
    FILE_SELECT = auto()
    INTRO = auto()
    OVERWORLD = auto()
    DUNGEON = auto()
    CAVE = auto()
    BUILDING = auto()
    CUTSCENE = auto()
    MENU = auto()
    DIALOGUE = auto()
    TRANSITION = auto()
    BLACK_SCREEN = auto()
    GAME_OVER = auto()


class LinkAction(IntEnum):
    """Link's current action state."""
    STANDING = 0
    WALKING = auto()
    RUNNING = auto()
    SWIMMING = auto()
    DIVING = auto()
    CLIMBING = auto()
    FALLING = auto()
    ATTACKING = auto()
    USING_ITEM = auto()
    KNOCKED_BACK = auto()
    SPINNING = auto()
    PUSHING = auto()
    PULLING = auto()
    LIFTING = auto()
    CARRYING = auto()
    THROWING = auto()
    TALKING = auto()
    READING = auto()
    DYING = auto()
    UNKNOWN = 255


# Mode values to GamePhase mapping
MODE_TO_PHASE = {
    0x00: GamePhase.BOOT,
    0x01: GamePhase.TITLE_SCREEN,
    0x02: GamePhase.FILE_SELECT,
    0x05: GamePhase.INTRO,
    0x06: GamePhase.TRANSITION,  # Room loading
    0x07: GamePhase.DUNGEON,     # Indoor/dungeon
    0x09: GamePhase.OVERWORLD,
    0x0E: GamePhase.MENU,
    0x0F: GamePhase.DIALOGUE,
    0x14: GamePhase.CUTSCENE,
    0x17: GamePhase.GAME_OVER,
}

# Link state to action mapping (from $5D)
LINK_STATE_TO_ACTION = {
    0x00: LinkAction.STANDING,
    0x01: LinkAction.WALKING,
    0x02: LinkAction.SWIMMING,
    0x03: LinkAction.DIVING,
    0x04: LinkAction.KNOCKED_BACK,
    0x06: LinkAction.PUSHING,
    0x08: LinkAction.FALLING,
    0x0A: LinkAction.LIFTING,
    0x0B: LinkAction.CARRYING,
    0x0C: LinkAction.THROWING,
    0x11: LinkAction.ATTACKING,
    0x12: LinkAction.USING_ITEM,
    0x17: LinkAction.DYING,
    0x19: LinkAction.SPINNING,
}

# Direction names
DIRECTION_NAMES = {
    0x00: "up",
    0x02: "down",
    0x04: "left",
    0x06: "right",
}

# Overworld area names (Oracle-specific)
OVERWORLD_AREAS = {
    0x18: "Link's House Area",
    0x28: "Village South",
    0x29: "Village Center",
    0x2A: "Village East",
    0x38: "Ranch Area",
    0x39: "Ranch Path",
    0x40: "Lost Woods Entrance",
    0x41: "Lost Woods Interior",
    0x42: "Lost Woods Deep",
    0x48: "Beach North",
    0x49: "Beach South",
    0x50: "Mountain Path",
    0x51: "Mountain Summit",
    # Add more as discovered
}

# Dungeon room names (common ones)
DUNGEON_ROOMS = {
    0x12: "Hall of Secrets",
    0x27: "Zora Temple - Water Gate",
    # Add more as discovered
}


@dataclass
class ParsedGameState:
    """Semantically interpreted game state."""
    # Raw snapshot reference
    raw: GameStateSnapshot

    # Phase and location
    phase: GamePhase
    location_name: str
    area_id: int
    room_id: int
    is_indoors: bool

    # Link state
    link_action: LinkAction
    link_direction: str
    link_position: Tuple[int, int]
    link_layer: int  # Z position
    health_percent: float

    # Flags
    is_playing: bool
    is_transitioning: bool
    is_menu_open: bool
    is_dialogue_open: bool
    is_black_screen: bool
    can_move: bool
    can_use_items: bool

    # Extended data
    submode: int
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_safe(self) -> bool:
        """Check if Link is in a safe state (can act freely)."""
        return (
            self.can_move and
            self.link_action in (LinkAction.STANDING, LinkAction.WALKING) and
            not self.is_transitioning and
            not self.is_black_screen
        )

    @property
    def is_combat(self) -> bool:
        """Check if in combat (attacking or knocked back)."""
        return self.link_action in (
            LinkAction.ATTACKING,
            LinkAction.KNOCKED_BACK,
            LinkAction.SPINNING,
        )

    @property
    def position_key(self) -> str:
        """Generate position key for state comparison."""
        return f"{self.area_id:02x}:{self.room_id:02x}:{self.link_position[0]}:{self.link_position[1]}"


class GameStateParser:
    """Parse raw game state into semantic form.

    This parser converts low-level memory values into high-level
    game concepts that agents can reason about.
    """

    def __init__(self):
        """Initialize parser with default configurations."""
        self._last_state: Optional[ParsedGameState] = None

    def parse(self, snapshot: GameStateSnapshot) -> ParsedGameState:
        """Parse raw snapshot into semantic state.

        Args:
            snapshot: Raw game state from emulator

        Returns:
            ParsedGameState with semantic interpretation
        """
        # Determine phase from mode
        phase = self._determine_phase(snapshot)

        # Get location name
        location_name = self._get_location_name(snapshot)

        # Parse Link action
        link_action = LINK_STATE_TO_ACTION.get(
            snapshot.link_state, LinkAction.UNKNOWN
        )

        # Parse direction
        link_direction = DIRECTION_NAMES.get(
            snapshot.link_direction, "unknown"
        )

        # Calculate health percent
        if snapshot.max_health > 0:
            health_percent = snapshot.health / snapshot.max_health
        else:
            health_percent = 1.0

        # Determine flags
        is_playing = snapshot.mode in (0x07, 0x09)
        is_transitioning = snapshot.mode == 0x06 or snapshot.submode != 0
        is_menu_open = snapshot.mode == 0x0E
        is_dialogue_open = snapshot.mode == 0x0F
        is_black_screen = snapshot.is_black_screen

        # Can move/use items depends on action and phase
        can_move = (
            is_playing and
            not is_transitioning and
            not is_black_screen and
            link_action in (LinkAction.STANDING, LinkAction.WALKING, LinkAction.RUNNING)
        )
        can_use_items = can_move and not is_menu_open and not is_dialogue_open

        state = ParsedGameState(
            raw=snapshot,
            phase=phase,
            location_name=location_name,
            area_id=snapshot.area,
            room_id=snapshot.room,
            is_indoors=snapshot.indoors,
            link_action=link_action,
            link_direction=link_direction,
            link_position=(snapshot.link_x, snapshot.link_y),
            link_layer=snapshot.link_z,
            health_percent=health_percent,
            is_playing=is_playing,
            is_transitioning=is_transitioning,
            is_menu_open=is_menu_open,
            is_dialogue_open=is_dialogue_open,
            is_black_screen=is_black_screen,
            can_move=can_move,
            can_use_items=can_use_items,
            submode=snapshot.submode,
            extra=snapshot.raw_data,
        )

        self._last_state = state
        return state

    def _determine_phase(self, snapshot: GameStateSnapshot) -> GamePhase:
        """Determine game phase from mode and context."""
        # Check for black screen first
        if snapshot.is_black_screen:
            return GamePhase.BLACK_SCREEN

        # Map mode to phase
        base_phase = MODE_TO_PHASE.get(snapshot.mode, GamePhase.UNKNOWN)

        # Refine DUNGEON phase based on context
        if base_phase == GamePhase.DUNGEON:
            # Could be cave, building, or actual dungeon
            # For now, use indoor flag
            if not snapshot.indoors:
                return GamePhase.OVERWORLD  # Edge case
            # Could add more heuristics here based on room IDs

        return base_phase

    def _get_location_name(self, snapshot: GameStateSnapshot) -> str:
        """Get human-readable location name."""
        if snapshot.indoors:
            # Check dungeon rooms first
            room_id = snapshot.raw_data.get("room_id", snapshot.room)
            if room_id in DUNGEON_ROOMS:
                return DUNGEON_ROOMS[room_id]
            return f"Room 0x{room_id:02X}"
        else:
            # Overworld
            if snapshot.area in OVERWORLD_AREAS:
                return OVERWORLD_AREAS[snapshot.area]
            return f"Overworld Area 0x{snapshot.area:02X}"

    def detect_change(
        self,
        new_state: ParsedGameState
    ) -> List[str]:
        """Detect significant changes from last state.

        Args:
            new_state: Newly parsed state

        Returns:
            List of change descriptions
        """
        if self._last_state is None:
            return ["Initial state"]

        old = self._last_state
        changes = []

        if old.phase != new_state.phase:
            changes.append(f"Phase: {old.phase.name} -> {new_state.phase.name}")

        if old.area_id != new_state.area_id:
            changes.append(f"Area: 0x{old.area_id:02X} -> 0x{new_state.area_id:02X}")

        if old.room_id != new_state.room_id:
            changes.append(f"Room: 0x{old.room_id:02X} -> 0x{new_state.room_id:02X}")

        if old.link_action != new_state.link_action:
            changes.append(f"Action: {old.link_action.name} -> {new_state.link_action.name}")

        if old.is_black_screen != new_state.is_black_screen:
            if new_state.is_black_screen:
                changes.append("BLACK SCREEN DETECTED")
            else:
                changes.append("Black screen cleared")

        # Position change (only if significant, >16 pixels)
        dx = abs(old.link_position[0] - new_state.link_position[0])
        dy = abs(old.link_position[1] - new_state.link_position[1])
        if dx > 16 or dy > 16:
            changes.append(
                f"Position: ({old.link_position[0]},{old.link_position[1]}) -> "
                f"({new_state.link_position[0]},{new_state.link_position[1]})"
            )

        return changes


# Singleton parser for convenience
_default_parser: Optional[GameStateParser] = None


def get_parser() -> GameStateParser:
    """Get default parser instance."""
    global _default_parser
    if _default_parser is None:
        _default_parser = GameStateParser()
    return _default_parser


def parse_state(snapshot: GameStateSnapshot) -> ParsedGameState:
    """Convenience function to parse state with default parser."""
    return get_parser().parse(snapshot)
