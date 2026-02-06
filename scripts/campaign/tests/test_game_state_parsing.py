"""Iteration 53 - Game State Parsing Tests.

Tests for GamePhase, LinkAction, ParsedGameState, GameStateParser,
mode mappings, and utility functions.

Focus: Phase detection, action interpretation, flag computation,
change detection, location naming, health calculation.
"""

import pytest
import time
from dataclasses import dataclass
from typing import Dict, Any
from unittest.mock import MagicMock

from scripts.campaign.game_state import (
    GamePhase,
    LinkAction,
    MODE_TO_PHASE,
    LINK_STATE_TO_ACTION,
    DIRECTION_NAMES,
    OVERWORLD_AREAS,
    DUNGEON_ROOMS,
    ParsedGameState,
    GameStateParser,
    get_parser,
    parse_state,
)


# =============================================================================
# Helper to create mock snapshots
# =============================================================================

def _snapshot(**overrides) -> MagicMock:
    """Create mock GameStateSnapshot with defaults."""
    defaults = {
        'mode': 0x09,  # Overworld
        'submode': 0x00,
        'area': 0x29,  # Village center
        'room': 0x00,
        'link_x': 100,
        'link_y': 100,
        'link_z': 0,
        'link_direction': 0x00,  # Up
        'link_state': 0x00,  # Standing
        'indoors': False,
        'inidisp': 0x0F,  # Screen on
        'health': 24,
        'max_health': 24,
        'timestamp': time.time(),
        'raw_data': {},
    }
    defaults.update(overrides)

    snapshot = MagicMock()
    for key, value in defaults.items():
        setattr(snapshot, key, value)

    # Property for black screen
    snapshot.is_black_screen = defaults.get('is_black_screen', False)

    return snapshot


# =============================================================================
# GamePhase Enum Tests
# =============================================================================

class TestGamePhase:
    """Tests for GamePhase enum."""

    def test_unknown_is_zero(self):
        """UNKNOWN is 0."""
        assert GamePhase.UNKNOWN == 0

    def test_all_phases_exist(self):
        """All expected phases exist."""
        phases = [
            GamePhase.UNKNOWN,
            GamePhase.BOOT,
            GamePhase.TITLE_SCREEN,
            GamePhase.FILE_SELECT,
            GamePhase.INTRO,
            GamePhase.OVERWORLD,
            GamePhase.DUNGEON,
            GamePhase.CAVE,
            GamePhase.BUILDING,
            GamePhase.CUTSCENE,
            GamePhase.MENU,
            GamePhase.DIALOGUE,
            GamePhase.TRANSITION,
            GamePhase.BLACK_SCREEN,
            GamePhase.GAME_OVER,
        ]
        assert len(phases) == 15
        assert len(set(phases)) == 15

    def test_phase_values_sequential(self):
        """Phase values are sequential from UNKNOWN."""
        phases = list(GamePhase)
        for i, phase in enumerate(phases):
            assert phase.value == i

    def test_phase_from_name(self):
        """Phases can be accessed by name."""
        assert GamePhase["OVERWORLD"] == GamePhase.OVERWORLD
        assert GamePhase["DUNGEON"] == GamePhase.DUNGEON


# =============================================================================
# LinkAction Enum Tests
# =============================================================================

class TestLinkAction:
    """Tests for LinkAction enum."""

    def test_standing_is_zero(self):
        """STANDING is 0."""
        assert LinkAction.STANDING == 0

    def test_all_actions_exist(self):
        """All expected actions exist."""
        actions = [
            LinkAction.STANDING,
            LinkAction.WALKING,
            LinkAction.RUNNING,
            LinkAction.SWIMMING,
            LinkAction.DIVING,
            LinkAction.CLIMBING,
            LinkAction.FALLING,
            LinkAction.ATTACKING,
            LinkAction.USING_ITEM,
            LinkAction.KNOCKED_BACK,
            LinkAction.SPINNING,
            LinkAction.PUSHING,
            LinkAction.PULLING,
            LinkAction.LIFTING,
            LinkAction.CARRYING,
            LinkAction.THROWING,
            LinkAction.TALKING,
            LinkAction.READING,
            LinkAction.DYING,
            LinkAction.UNKNOWN,
        ]
        assert len(actions) == 20

    def test_unknown_is_255(self):
        """UNKNOWN action is 255."""
        assert LinkAction.UNKNOWN == 255


# =============================================================================
# Mode to Phase Mapping Tests
# =============================================================================

class TestModeToPhase:
    """Tests for MODE_TO_PHASE mapping."""

    def test_boot_mode(self):
        """Mode 0x00 is BOOT."""
        assert MODE_TO_PHASE[0x00] == GamePhase.BOOT

    def test_title_screen_mode(self):
        """Mode 0x01 is TITLE_SCREEN."""
        assert MODE_TO_PHASE[0x01] == GamePhase.TITLE_SCREEN

    def test_file_select_mode(self):
        """Mode 0x02 is FILE_SELECT."""
        assert MODE_TO_PHASE[0x02] == GamePhase.FILE_SELECT

    def test_overworld_mode(self):
        """Mode 0x09 is OVERWORLD."""
        assert MODE_TO_PHASE[0x09] == GamePhase.OVERWORLD

    def test_dungeon_mode(self):
        """Mode 0x07 is DUNGEON."""
        assert MODE_TO_PHASE[0x07] == GamePhase.DUNGEON

    def test_menu_mode(self):
        """Mode 0x0E is MENU."""
        assert MODE_TO_PHASE[0x0E] == GamePhase.MENU

    def test_dialogue_mode(self):
        """Mode 0x0F is DIALOGUE."""
        assert MODE_TO_PHASE[0x0F] == GamePhase.DIALOGUE

    def test_transition_mode(self):
        """Mode 0x06 is TRANSITION."""
        assert MODE_TO_PHASE[0x06] == GamePhase.TRANSITION


# =============================================================================
# Link State to Action Mapping Tests
# =============================================================================

class TestLinkStateToAction:
    """Tests for LINK_STATE_TO_ACTION mapping."""

    def test_standing_state(self):
        """State 0x00 is STANDING."""
        assert LINK_STATE_TO_ACTION[0x00] == LinkAction.STANDING

    def test_walking_state(self):
        """State 0x01 is WALKING."""
        assert LINK_STATE_TO_ACTION[0x01] == LinkAction.WALKING

    def test_swimming_state(self):
        """State 0x02 is SWIMMING."""
        assert LINK_STATE_TO_ACTION[0x02] == LinkAction.SWIMMING

    def test_attacking_state(self):
        """State 0x11 is ATTACKING."""
        assert LINK_STATE_TO_ACTION[0x11] == LinkAction.ATTACKING

    def test_dying_state(self):
        """State 0x17 is DYING."""
        assert LINK_STATE_TO_ACTION[0x17] == LinkAction.DYING


# =============================================================================
# Direction Names Tests
# =============================================================================

class TestDirectionNames:
    """Tests for DIRECTION_NAMES mapping."""

    def test_up_direction(self):
        """Direction 0x00 is up."""
        assert DIRECTION_NAMES[0x00] == "up"

    def test_down_direction(self):
        """Direction 0x02 is down."""
        assert DIRECTION_NAMES[0x02] == "down"

    def test_left_direction(self):
        """Direction 0x04 is left."""
        assert DIRECTION_NAMES[0x04] == "left"

    def test_right_direction(self):
        """Direction 0x06 is right."""
        assert DIRECTION_NAMES[0x06] == "right"


# =============================================================================
# Location Names Tests
# =============================================================================

class TestLocationNames:
    """Tests for location name mappings."""

    def test_village_center_area(self):
        """Area 0x29 is Village Center."""
        assert OVERWORLD_AREAS[0x29] == "Village Center"

    def test_links_house_area(self):
        """Area 0x18 is Link's House Area."""
        assert OVERWORLD_AREAS[0x18] == "Link's House Area"

    def test_hall_of_secrets_room(self):
        """Room 0x12 is Hall of Secrets."""
        assert DUNGEON_ROOMS[0x12] == "Hall of Secrets"


# =============================================================================
# ParsedGameState Tests
# =============================================================================

class TestParsedGameState:
    """Tests for ParsedGameState dataclass."""

    def test_is_safe_standing(self):
        """is_safe when standing and can move."""
        snapshot = _snapshot()
        state = ParsedGameState(
            raw=snapshot,
            phase=GamePhase.OVERWORLD,
            location_name="Village",
            area_id=0x29,
            room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="up",
            link_position=(100, 100),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=True,
            can_use_items=True,
            submode=0,
        )
        assert state.is_safe is True

    def test_is_safe_transitioning(self):
        """Not safe when transitioning."""
        snapshot = _snapshot()
        state = ParsedGameState(
            raw=snapshot,
            phase=GamePhase.TRANSITION,
            location_name="Transition",
            area_id=0x29,
            room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="up",
            link_position=(100, 100),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=True,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=False,
            can_use_items=False,
            submode=0,
        )
        assert state.is_safe is False

    def test_is_safe_black_screen(self):
        """Not safe during black screen."""
        snapshot = _snapshot()
        state = ParsedGameState(
            raw=snapshot,
            phase=GamePhase.BLACK_SCREEN,
            location_name="Unknown",
            area_id=0x00,
            room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="up",
            link_position=(0, 0),
            link_layer=0,
            health_percent=1.0,
            is_playing=False,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=True,
            can_move=False,
            can_use_items=False,
            submode=0,
        )
        assert state.is_safe is False

    def test_is_combat_attacking(self):
        """is_combat when attacking."""
        snapshot = _snapshot()
        state = ParsedGameState(
            raw=snapshot,
            phase=GamePhase.OVERWORLD,
            location_name="Village",
            area_id=0x29,
            room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.ATTACKING,
            link_direction="up",
            link_position=(100, 100),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=False,
            can_use_items=False,
            submode=0,
        )
        assert state.is_combat is True

    def test_is_combat_knocked_back(self):
        """is_combat when knocked back."""
        snapshot = _snapshot()
        state = ParsedGameState(
            raw=snapshot,
            phase=GamePhase.OVERWORLD,
            location_name="Village",
            area_id=0x29,
            room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.KNOCKED_BACK,
            link_direction="up",
            link_position=(100, 100),
            link_layer=0,
            health_percent=0.5,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=False,
            can_use_items=False,
            submode=0,
        )
        assert state.is_combat is True

    def test_is_combat_spinning(self):
        """is_combat when spinning."""
        snapshot = _snapshot()
        state = ParsedGameState(
            raw=snapshot,
            phase=GamePhase.OVERWORLD,
            location_name="Village",
            area_id=0x29,
            room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.SPINNING,
            link_direction="up",
            link_position=(100, 100),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=False,
            can_use_items=False,
            submode=0,
        )
        assert state.is_combat is True

    def test_is_combat_standing(self):
        """Not in combat when standing."""
        snapshot = _snapshot()
        state = ParsedGameState(
            raw=snapshot,
            phase=GamePhase.OVERWORLD,
            location_name="Village",
            area_id=0x29,
            room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="up",
            link_position=(100, 100),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=True,
            can_use_items=True,
            submode=0,
        )
        assert state.is_combat is False

    def test_position_key(self):
        """Position key format."""
        snapshot = _snapshot()
        state = ParsedGameState(
            raw=snapshot,
            phase=GamePhase.OVERWORLD,
            location_name="Village",
            area_id=0x29,
            room_id=0x10,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="up",
            link_position=(128, 256),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=True,
            can_use_items=True,
            submode=0,
        )
        assert state.position_key == "29:10:128:256"


# =============================================================================
# GameStateParser Tests
# =============================================================================

class TestGameStateParser:
    """Tests for GameStateParser class."""

    def test_parser_creation(self):
        """Create parser."""
        parser = GameStateParser()
        assert parser._last_state is None

    def test_parse_overworld(self):
        """Parse overworld state."""
        parser = GameStateParser()
        snapshot = _snapshot(mode=0x09, area=0x29)

        state = parser.parse(snapshot)

        assert state.phase == GamePhase.OVERWORLD
        assert state.area_id == 0x29

    def test_parse_dungeon(self):
        """Parse dungeon state."""
        parser = GameStateParser()
        snapshot = _snapshot(mode=0x07, indoors=True, room=0x12)

        state = parser.parse(snapshot)

        assert state.phase == GamePhase.DUNGEON
        assert state.is_indoors is True

    def test_parse_menu(self):
        """Parse menu state."""
        parser = GameStateParser()
        snapshot = _snapshot(mode=0x0E)

        state = parser.parse(snapshot)

        assert state.phase == GamePhase.MENU
        assert state.is_menu_open is True

    def test_parse_dialogue(self):
        """Parse dialogue state."""
        parser = GameStateParser()
        snapshot = _snapshot(mode=0x0F)

        state = parser.parse(snapshot)

        assert state.phase == GamePhase.DIALOGUE
        assert state.is_dialogue_open is True

    def test_parse_black_screen(self):
        """Parse black screen state."""
        parser = GameStateParser()
        snapshot = _snapshot(is_black_screen=True)

        state = parser.parse(snapshot)

        assert state.phase == GamePhase.BLACK_SCREEN
        assert state.is_black_screen is True

    def test_parse_health_percent_full(self):
        """Parse full health."""
        parser = GameStateParser()
        snapshot = _snapshot(health=24, max_health=24)

        state = parser.parse(snapshot)

        assert state.health_percent == 1.0

    def test_parse_health_percent_half(self):
        """Parse half health."""
        parser = GameStateParser()
        snapshot = _snapshot(health=12, max_health=24)

        state = parser.parse(snapshot)

        assert state.health_percent == 0.5

    def test_parse_health_percent_zero_max(self):
        """Health percent with zero max defaults to 1.0."""
        parser = GameStateParser()
        snapshot = _snapshot(health=0, max_health=0)

        state = parser.parse(snapshot)

        assert state.health_percent == 1.0

    def test_parse_link_direction(self):
        """Parse Link direction."""
        parser = GameStateParser()

        for dir_value, dir_name in DIRECTION_NAMES.items():
            snapshot = _snapshot(link_direction=dir_value)
            state = parser.parse(snapshot)
            assert state.link_direction == dir_name

    def test_parse_link_action(self):
        """Parse Link action."""
        parser = GameStateParser()

        for state_value, action in LINK_STATE_TO_ACTION.items():
            snapshot = _snapshot(link_state=state_value)
            state = parser.parse(snapshot)
            assert state.link_action == action

    def test_parse_link_position(self):
        """Parse Link position."""
        parser = GameStateParser()
        snapshot = _snapshot(link_x=256, link_y=128)

        state = parser.parse(snapshot)

        assert state.link_position == (256, 128)

    def test_parse_can_move_overworld(self):
        """Can move in overworld when standing."""
        parser = GameStateParser()
        snapshot = _snapshot(mode=0x09, link_state=0x00, submode=0x00)

        state = parser.parse(snapshot)

        assert state.can_move is True

    def test_parse_cannot_move_menu(self):
        """Cannot move in menu."""
        parser = GameStateParser()
        snapshot = _snapshot(mode=0x0E)

        state = parser.parse(snapshot)

        assert state.can_move is False

    def test_parse_cannot_move_attacking(self):
        """Cannot move when attacking."""
        parser = GameStateParser()
        snapshot = _snapshot(link_state=0x11)  # ATTACKING

        state = parser.parse(snapshot)

        assert state.can_move is False


# =============================================================================
# Location Name Tests
# =============================================================================

class TestLocationName:
    """Tests for location name resolution."""

    def test_known_overworld_area(self):
        """Known overworld area has name."""
        parser = GameStateParser()
        snapshot = _snapshot(area=0x29, indoors=False)

        state = parser.parse(snapshot)

        assert state.location_name == "Village Center"

    def test_unknown_overworld_area(self):
        """Unknown area gets hex name."""
        parser = GameStateParser()
        snapshot = _snapshot(area=0xFF, indoors=False)

        state = parser.parse(snapshot)

        assert "0xFF" in state.location_name or "0xff" in state.location_name.lower()

    def test_known_dungeon_room(self):
        """Known dungeon room has name."""
        parser = GameStateParser()
        snapshot = _snapshot(indoors=True, room=0x12)
        snapshot.raw_data = {"room_id": 0x12}

        state = parser.parse(snapshot)

        assert state.location_name == "Hall of Secrets"

    def test_unknown_room(self):
        """Unknown room gets hex name."""
        parser = GameStateParser()
        snapshot = _snapshot(indoors=True, room=0xAB)
        snapshot.raw_data = {"room_id": 0xAB}

        state = parser.parse(snapshot)

        assert "0xAB" in state.location_name or "0xab" in state.location_name.lower()


# =============================================================================
# Change Detection Tests
# =============================================================================

def _parsed_state(snapshot, **overrides) -> ParsedGameState:
    """Create ParsedGameState directly for testing without using parser.parse().

    This allows testing detect_change() without parse() updating _last_state.
    """
    defaults = {
        'phase': MODE_TO_PHASE.get(snapshot.mode, GamePhase.UNKNOWN),
        'location_name': "Test Location",
        'area_id': snapshot.area,
        'room_id': snapshot.room,
        'is_indoors': snapshot.indoors,
        'link_action': LINK_STATE_TO_ACTION.get(snapshot.link_state, LinkAction.UNKNOWN),
        'link_direction': DIRECTION_NAMES.get(snapshot.link_direction, "unknown"),
        'link_position': (snapshot.link_x, snapshot.link_y),
        'link_layer': snapshot.link_z,
        'health_percent': snapshot.health / snapshot.max_health if snapshot.max_health > 0 else 1.0,
        'is_playing': snapshot.mode in (0x07, 0x09),
        'is_transitioning': snapshot.mode == 0x06 or snapshot.submode != 0,
        'is_menu_open': snapshot.mode == 0x0E,
        'is_dialogue_open': snapshot.mode == 0x0F,
        'is_black_screen': snapshot.is_black_screen,
        'can_move': True,
        'can_use_items': True,
        'submode': snapshot.submode,
    }
    defaults.update(overrides)
    return ParsedGameState(raw=snapshot, **defaults)


class TestChangeDetection:
    """Tests for change detection."""

    def test_detect_initial_state(self):
        """Initial state returns 'Initial state' when _last_state is None."""
        parser = GameStateParser()
        # Don't call parse() - that sets _last_state
        snapshot = _snapshot()
        state = _parsed_state(snapshot)

        # detect_change with _last_state=None should return "Initial state"
        changes = parser.detect_change(state)

        assert "Initial state" in changes

    def test_detect_phase_change(self):
        """Detect phase change."""
        parser = GameStateParser()

        # First state - set _last_state directly
        snapshot1 = _snapshot(mode=0x09)  # Overworld
        state1 = _parsed_state(snapshot1, phase=GamePhase.OVERWORLD)
        parser._last_state = state1

        # Second state with phase change
        snapshot2 = _snapshot(mode=0x0E)  # Menu
        state2 = _parsed_state(snapshot2, phase=GamePhase.MENU)
        changes = parser.detect_change(state2)

        phase_changes = [c for c in changes if "Phase" in c]
        assert len(phase_changes) > 0

    def test_detect_area_change(self):
        """Detect area change."""
        parser = GameStateParser()

        # First state
        snapshot1 = _snapshot(area=0x29)
        state1 = _parsed_state(snapshot1)
        parser._last_state = state1

        # Second state with area change
        snapshot2 = _snapshot(area=0x30)
        state2 = _parsed_state(snapshot2)
        changes = parser.detect_change(state2)

        area_changes = [c for c in changes if "Area" in c]
        assert len(area_changes) > 0

    def test_detect_black_screen(self):
        """Detect black screen."""
        parser = GameStateParser()

        # First state - normal
        snapshot1 = _snapshot(is_black_screen=False)
        state1 = _parsed_state(snapshot1, is_black_screen=False)
        parser._last_state = state1

        # Second state - black screen
        snapshot2 = _snapshot(is_black_screen=True)
        state2 = _parsed_state(snapshot2, is_black_screen=True)
        changes = parser.detect_change(state2)

        black_screen_changes = [c for c in changes if "BLACK SCREEN" in c]
        assert len(black_screen_changes) > 0

    def test_detect_position_change_significant(self):
        """Detect significant position change (>16 pixels)."""
        parser = GameStateParser()

        snapshot1 = _snapshot(link_x=100, link_y=100)
        state1 = _parsed_state(snapshot1)
        parser._last_state = state1

        snapshot2 = _snapshot(link_x=150, link_y=100)  # 50 pixel move
        state2 = _parsed_state(snapshot2)
        changes = parser.detect_change(state2)

        pos_changes = [c for c in changes if "Position" in c]
        assert len(pos_changes) > 0

    def test_no_change_small_position(self):
        """Small position change (<16 pixels) not reported."""
        parser = GameStateParser()

        snapshot1 = _snapshot(link_x=100, link_y=100)
        state1 = _parsed_state(snapshot1)
        parser._last_state = state1

        snapshot2 = _snapshot(link_x=105, link_y=100)  # 5 pixel move
        state2 = _parsed_state(snapshot2)
        changes = parser.detect_change(state2)

        pos_changes = [c for c in changes if "Position" in c]
        assert len(pos_changes) == 0


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestUtilityFunctions:
    """Tests for module-level utility functions."""

    def test_get_parser_singleton(self):
        """get_parser returns singleton."""
        import scripts.campaign.game_state as gs_module
        gs_module._default_parser = None  # Reset

        parser1 = get_parser()
        parser2 = get_parser()

        assert parser1 is parser2

    def test_parse_state_convenience(self):
        """parse_state convenience function."""
        import scripts.campaign.game_state as gs_module
        gs_module._default_parser = None  # Reset

        snapshot = _snapshot(mode=0x09, area=0x29)
        state = parse_state(snapshot)

        assert state.phase == GamePhase.OVERWORLD
        assert state.area_id == 0x29


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge case tests."""

    def test_unknown_mode(self):
        """Unknown mode returns UNKNOWN phase."""
        parser = GameStateParser()
        snapshot = _snapshot(mode=0xFF)

        state = parser.parse(snapshot)

        assert state.phase == GamePhase.UNKNOWN

    def test_unknown_link_state(self):
        """Unknown link state returns UNKNOWN action."""
        parser = GameStateParser()
        snapshot = _snapshot(link_state=0xFF)

        state = parser.parse(snapshot)

        assert state.link_action == LinkAction.UNKNOWN

    def test_unknown_direction(self):
        """Unknown direction returns 'unknown'."""
        parser = GameStateParser()
        snapshot = _snapshot(link_direction=0xFF)

        state = parser.parse(snapshot)

        assert state.link_direction == "unknown"

    def test_parse_transitioning_submode(self):
        """Non-zero submode indicates transitioning."""
        parser = GameStateParser()
        snapshot = _snapshot(submode=0x01)

        state = parser.parse(snapshot)

        assert state.is_transitioning is True

    def test_parse_extra_data(self):
        """Extra data is stored."""
        parser = GameStateParser()
        snapshot = _snapshot()
        snapshot.raw_data = {"custom": "value"}

        state = parser.parse(snapshot)

        assert state.extra.get("custom") == "value"
