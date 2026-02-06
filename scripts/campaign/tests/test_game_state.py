"""Tests for game_state module.

These tests verify the semantic parsing of game state.
"""

import pytest
from unittest.mock import Mock

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import GameStateSnapshot
from scripts.campaign.game_state import (
    GamePhase,
    GameStateParser,
    LinkAction,
    ParsedGameState,
    get_parser,
    parse_state,
    MODE_TO_PHASE,
    LINK_STATE_TO_ACTION,
    DIRECTION_NAMES,
    OVERWORLD_AREAS,
    DUNGEON_ROOMS,
)


class TestGamePhase:
    """Tests for GamePhase enum."""

    def test_phase_values(self):
        """Test key phase values exist."""
        assert GamePhase.BOOT is not None
        assert GamePhase.TITLE_SCREEN is not None
        assert GamePhase.OVERWORLD is not None
        assert GamePhase.DUNGEON is not None
        assert GamePhase.BLACK_SCREEN is not None

    def test_mode_to_phase_mapping(self):
        """Test mode to phase mappings."""
        assert MODE_TO_PHASE[0x09] == GamePhase.OVERWORLD
        assert MODE_TO_PHASE[0x07] == GamePhase.DUNGEON
        assert MODE_TO_PHASE[0x0E] == GamePhase.MENU
        assert MODE_TO_PHASE[0x06] == GamePhase.TRANSITION


class TestLinkAction:
    """Tests for LinkAction enum."""

    def test_action_values(self):
        """Test key action values exist."""
        assert LinkAction.STANDING == 0
        assert LinkAction.WALKING is not None
        assert LinkAction.SWIMMING is not None
        assert LinkAction.ATTACKING is not None

    def test_link_state_mapping(self):
        """Test link state to action mappings."""
        assert LINK_STATE_TO_ACTION[0x00] == LinkAction.STANDING
        assert LINK_STATE_TO_ACTION[0x01] == LinkAction.WALKING
        assert LINK_STATE_TO_ACTION[0x02] == LinkAction.SWIMMING
        assert LINK_STATE_TO_ACTION[0x11] == LinkAction.ATTACKING


class TestDirectionNames:
    """Tests for direction name mappings."""

    def test_direction_mappings(self):
        """Test direction value to name mappings."""
        assert DIRECTION_NAMES[0x00] == "up"
        assert DIRECTION_NAMES[0x02] == "down"
        assert DIRECTION_NAMES[0x04] == "left"
        assert DIRECTION_NAMES[0x06] == "right"


class TestLocationDictionaries:
    """Tests for location name dictionaries."""

    def test_overworld_areas_exist(self):
        """Test that key overworld areas are defined."""
        assert 0x29 in OVERWORLD_AREAS  # Village Center
        assert 0x40 in OVERWORLD_AREAS  # Lost Woods Entrance

    def test_dungeon_rooms_exist(self):
        """Test that key dungeon rooms are defined."""
        assert 0x27 in DUNGEON_ROOMS  # Water Gate


class TestGameStateParser:
    """Tests for GameStateParser."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return GameStateParser()

    @pytest.fixture
    def overworld_snapshot(self):
        """Create an overworld game state snapshot."""
        return GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=384,
            link_y=512,
            link_z=0,
            link_direction=0x02,
            link_state=0x01,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )

    @pytest.fixture
    def dungeon_snapshot(self):
        """Create a dungeon game state snapshot."""
        return GameStateSnapshot(
            timestamp=1001.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x0F,
            health=20,
            max_health=24,
            raw_data={"room_id": 0x27},
        )

    @pytest.fixture
    def black_screen_snapshot(self):
        """Create a black screen state snapshot."""
        return GameStateSnapshot(
            timestamp=1002.0,
            mode=0x07,
            submode=0x0F,
            area=0x00,
            room=0x12,
            link_x=0,
            link_y=0,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x80,
            health=24,
            max_health=24,
        )

    def test_parse_overworld(self, parser, overworld_snapshot):
        """Test parsing overworld state."""
        state = parser.parse(overworld_snapshot)

        assert state.phase == GamePhase.OVERWORLD
        assert state.is_playing is True
        assert state.is_indoors is False
        assert state.link_action == LinkAction.WALKING
        assert state.link_direction == "down"
        assert state.link_position == (384, 512)
        assert state.location_name == "Village Center"

    def test_parse_dungeon(self, parser, dungeon_snapshot):
        """Test parsing dungeon state."""
        state = parser.parse(dungeon_snapshot)

        assert state.phase == GamePhase.DUNGEON
        assert state.is_playing is True
        assert state.is_indoors is True
        assert state.link_action == LinkAction.STANDING
        assert state.link_direction == "up"
        assert state.location_name == "Zora Temple - Water Gate"

    def test_parse_black_screen(self, parser, black_screen_snapshot):
        """Test parsing black screen state."""
        state = parser.parse(black_screen_snapshot)

        assert state.phase == GamePhase.BLACK_SCREEN
        assert state.is_black_screen is True
        assert state.can_move is False

    def test_health_percent(self, parser, overworld_snapshot, dungeon_snapshot):
        """Test health percentage calculation."""
        state = parser.parse(overworld_snapshot)
        assert state.health_percent == 1.0  # Full health

        state = parser.parse(dungeon_snapshot)
        assert abs(state.health_percent - (20/24)) < 0.01

    def test_can_move_flags(self, parser, overworld_snapshot, black_screen_snapshot):
        """Test can_move flag calculation."""
        state = parser.parse(overworld_snapshot)
        assert state.can_move is True

        state = parser.parse(black_screen_snapshot)
        assert state.can_move is False

    def test_is_safe_property(self, parser, overworld_snapshot):
        """Test is_safe property."""
        state = parser.parse(overworld_snapshot)
        assert state.is_safe is True

    def test_is_combat_property(self, parser):
        """Test is_combat property."""
        # Create attacking state
        snapshot = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=384,
            link_y=512,
            link_z=0,
            link_direction=0x02,
            link_state=0x11,  # Attacking
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        state = parser.parse(snapshot)
        assert state.is_combat is True

    def test_position_key(self, parser, overworld_snapshot):
        """Test position key generation."""
        state = parser.parse(overworld_snapshot)
        key = state.position_key
        assert "29" in key  # Area
        assert "384" in key  # X
        assert "512" in key  # Y


class TestChangeDetection:
    """Tests for state change detection."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return GameStateParser()

    def test_initial_state(self, parser):
        """Test change detection - position change.

        Note: detect_change compares a new state with the parser's _last_state.
        Since parse() updates _last_state, we construct the second state directly.
        """
        # First state - sets _last_state
        snapshot1 = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=384,
            link_y=512,
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        parser.parse(snapshot1)  # Sets _last_state

        # Second state with different position (construct directly)
        snapshot2 = GameStateSnapshot(
            timestamp=1001.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=384,
            link_y=550,  # Changed by 38 pixels (> 16 threshold)
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        state2 = ParsedGameState(
            raw=snapshot2,
            phase=GamePhase.OVERWORLD,
            location_name="Village Center",
            area_id=0x29,
            room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="down",
            link_position=(384, 550),  # Y changed
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
        changes = parser.detect_change(state2)

        assert any("Position" in c for c in changes)

    def test_detect_area_change(self, parser):
        """Test detecting area changes.

        The detect_change function compares a new state with the parser's
        _last_state. Since parse() updates _last_state, we need to
        construct the second ParsedGameState directly without parse().
        """
        # First state - sets _last_state
        snap1 = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=384,
            link_y=512,
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        parser.parse(snap1)  # This sets _last_state

        # Second state - different area (construct directly)
        snap2 = GameStateSnapshot(
            timestamp=1001.0,
            mode=0x09,
            submode=0x00,
            area=0x2A,  # Changed
            room=0x00,
            link_x=100,
            link_y=100,
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        # Parse to ParsedGameState but compare with _last_state (which is still snap1)
        state2 = ParsedGameState(
            raw=snap2,
            phase=GamePhase.OVERWORLD,
            location_name="Village East",
            area_id=0x2A,
            room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="down",
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
        changes = parser.detect_change(state2)

        assert any("Area" in c for c in changes)

    def test_detect_black_screen(self, parser):
        """Test detecting black screen transition.

        Similar to area change, we construct the second state directly
        to avoid _last_state being overwritten by parse().
        """
        # Normal state - sets _last_state
        snap1 = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x0F,
            health=24,
            max_health=24,
            raw_data={"room_id": 0x27},
        )
        parser.parse(snap1)

        # Black screen state (construct directly)
        snap2 = GameStateSnapshot(
            timestamp=1001.0,
            mode=0x07,
            submode=0x0F,
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x80,  # Screen off
            health=24,
            max_health=24,
        )
        state2 = ParsedGameState(
            raw=snap2,
            phase=GamePhase.BLACK_SCREEN,
            location_name="Zora Temple (Water Gate)",
            area_id=0x00,
            room_id=0x27,
            is_indoors=True,
            link_action=LinkAction.STANDING,
            link_direction="up",
            link_position=(256, 320),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=True,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=True,  # Black screen!
            can_move=False,
            can_use_items=False,
            submode=0x0F,
        )
        changes = parser.detect_change(state2)

        assert any("BLACK SCREEN" in c for c in changes)


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_parser_singleton(self):
        """Test that get_parser returns singleton."""
        parser1 = get_parser()
        parser2 = get_parser()
        assert parser1 is parser2

    def test_parse_state_function(self):
        """Test parse_state convenience function."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=384,
            link_y=512,
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        state = parse_state(snapshot)

        assert isinstance(state, ParsedGameState)
        assert state.phase == GamePhase.OVERWORLD
