"""Extended tests for game state parsing.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D.1: Game state parser validation

These tests verify the game state parser handles all edge cases,
computed properties, and state transitions correctly.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.game_state import (
    GamePhase, LinkAction, ParsedGameState, GameStateParser,
    MODE_TO_PHASE, LINK_STATE_TO_ACTION, DIRECTION_NAMES,
    OVERWORLD_AREAS, DUNGEON_ROOMS, get_parser, parse_state
)
from scripts.campaign.emulator_abstraction import GameStateSnapshot


class TestGamePhaseEnum:
    """Test GamePhase enum values."""

    def test_all_phases_exist(self):
        """Test all expected phases exist."""
        expected = [
            "UNKNOWN", "BOOT", "TITLE_SCREEN", "FILE_SELECT", "INTRO",
            "OVERWORLD", "DUNGEON", "CAVE", "BUILDING", "CUTSCENE",
            "MENU", "DIALOGUE", "TRANSITION", "BLACK_SCREEN", "GAME_OVER"
        ]
        for name in expected:
            assert hasattr(GamePhase, name), f"Missing GamePhase.{name}"

    def test_phases_have_distinct_values(self):
        """Test all phases have distinct values."""
        values = [p.value for p in GamePhase]
        assert len(values) == len(set(values))

    def test_unknown_is_zero(self):
        """Test UNKNOWN has value 0."""
        assert GamePhase.UNKNOWN.value == 0

    def test_phases_are_comparable(self):
        """Test phases can be compared."""
        assert GamePhase.OVERWORLD != GamePhase.DUNGEON
        assert GamePhase.MENU == GamePhase.MENU

    def test_phase_name_access(self):
        """Test phase name property."""
        assert GamePhase.OVERWORLD.name == "OVERWORLD"
        assert GamePhase.BLACK_SCREEN.name == "BLACK_SCREEN"


class TestLinkActionEnum:
    """Test LinkAction enum values."""

    def test_all_actions_exist(self):
        """Test all expected actions exist."""
        expected = [
            "STANDING", "WALKING", "RUNNING", "SWIMMING", "DIVING",
            "CLIMBING", "FALLING", "ATTACKING", "USING_ITEM",
            "KNOCKED_BACK", "SPINNING", "PUSHING", "PULLING",
            "LIFTING", "CARRYING", "THROWING", "TALKING", "READING",
            "DYING", "UNKNOWN"
        ]
        for name in expected:
            assert hasattr(LinkAction, name), f"Missing LinkAction.{name}"

    def test_standing_is_zero(self):
        """Test STANDING has value 0."""
        assert LinkAction.STANDING.value == 0

    def test_unknown_is_255(self):
        """Test UNKNOWN has value 255."""
        assert LinkAction.UNKNOWN.value == 255

    def test_actions_are_comparable(self):
        """Test actions can be compared."""
        assert LinkAction.WALKING != LinkAction.RUNNING
        assert LinkAction.ATTACKING == LinkAction.ATTACKING


class TestModeToPhaseMapping:
    """Test mode to phase mapping dictionary."""

    def test_mapping_not_empty(self):
        """Test mapping has entries."""
        assert len(MODE_TO_PHASE) > 0

    def test_boot_mode_mapped(self):
        """Test boot mode maps to BOOT."""
        assert MODE_TO_PHASE.get(0x00) == GamePhase.BOOT

    def test_title_screen_mapped(self):
        """Test title screen mode maps correctly."""
        assert MODE_TO_PHASE.get(0x01) == GamePhase.TITLE_SCREEN

    def test_overworld_mapped(self):
        """Test overworld mode maps correctly."""
        assert MODE_TO_PHASE.get(0x09) == GamePhase.OVERWORLD

    def test_dungeon_mapped(self):
        """Test dungeon mode maps correctly."""
        assert MODE_TO_PHASE.get(0x07) == GamePhase.DUNGEON

    def test_menu_mapped(self):
        """Test menu mode maps correctly."""
        assert MODE_TO_PHASE.get(0x0E) == GamePhase.MENU

    def test_dialogue_mapped(self):
        """Test dialogue mode maps correctly."""
        assert MODE_TO_PHASE.get(0x0F) == GamePhase.DIALOGUE

    def test_unknown_mode_returns_none(self):
        """Test unmapped mode returns None."""
        assert MODE_TO_PHASE.get(0xFF) is None


class TestLinkStateToActionMapping:
    """Test link state to action mapping."""

    def test_mapping_not_empty(self):
        """Test mapping has entries."""
        assert len(LINK_STATE_TO_ACTION) > 0

    def test_standing_state(self):
        """Test state 0 maps to STANDING."""
        assert LINK_STATE_TO_ACTION.get(0x00) == LinkAction.STANDING

    def test_walking_state(self):
        """Test walking state maps correctly."""
        assert LINK_STATE_TO_ACTION.get(0x01) == LinkAction.WALKING

    def test_attacking_state(self):
        """Test attacking state maps correctly."""
        assert LINK_STATE_TO_ACTION.get(0x11) == LinkAction.ATTACKING

    def test_dying_state(self):
        """Test dying state maps correctly."""
        assert LINK_STATE_TO_ACTION.get(0x17) == LinkAction.DYING


class TestDirectionNames:
    """Test direction name mapping."""

    def test_all_directions_exist(self):
        """Test all four directions exist."""
        assert 0x00 in DIRECTION_NAMES  # up
        assert 0x02 in DIRECTION_NAMES  # down
        assert 0x04 in DIRECTION_NAMES  # left
        assert 0x06 in DIRECTION_NAMES  # right

    def test_direction_values(self):
        """Test direction values."""
        assert DIRECTION_NAMES[0x00] == "up"
        assert DIRECTION_NAMES[0x02] == "down"
        assert DIRECTION_NAMES[0x04] == "left"
        assert DIRECTION_NAMES[0x06] == "right"


class TestOverworldAreas:
    """Test overworld area mapping."""

    def test_areas_not_empty(self):
        """Test areas dictionary has entries."""
        assert len(OVERWORLD_AREAS) > 0

    def test_village_center_exists(self):
        """Test village center is mapped."""
        assert 0x29 in OVERWORLD_AREAS
        assert "village" in OVERWORLD_AREAS[0x29].lower()

    def test_all_values_are_strings(self):
        """Test all area values are strings."""
        for area_id, name in OVERWORLD_AREAS.items():
            assert isinstance(name, str)
            assert len(name) > 0


class TestDungeonRooms:
    """Test dungeon room mapping."""

    def test_rooms_dict_exists(self):
        """Test dungeon rooms dictionary exists."""
        assert isinstance(DUNGEON_ROOMS, dict)

    def test_room_values_are_strings(self):
        """Test all room values are strings."""
        for room_id, name in DUNGEON_ROOMS.items():
            assert isinstance(name, str)


class TestParsedGameStateProperties:
    """Test ParsedGameState computed properties."""

    @pytest.fixture
    def safe_state(self):
        """Create a safe game state."""
        raw = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        return ParsedGameState(
            raw=raw,
            phase=GamePhase.OVERWORLD,
            location_name="Village Center",
            area_id=0x29, room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="down",
            link_position=(512, 480),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=True,
            can_use_items=True,
            submode=0x00
        )

    @pytest.fixture
    def combat_state(self):
        """Create a combat game state."""
        raw = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x11,  # attacking
            indoors=False, inidisp=0x0F,
            health=20, max_health=24
        )
        return ParsedGameState(
            raw=raw,
            phase=GamePhase.OVERWORLD,
            location_name="Village Center",
            area_id=0x29, room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.ATTACKING,
            link_direction="down",
            link_position=(512, 480),
            link_layer=0,
            health_percent=20/24,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=False,
            can_use_items=False,
            submode=0x00
        )

    def test_is_safe_when_standing(self, safe_state):
        """Test is_safe is True when standing and can move."""
        assert safe_state.is_safe is True

    def test_is_safe_false_when_attacking(self, combat_state):
        """Test is_safe is False when attacking."""
        assert combat_state.is_safe is False

    def test_is_safe_false_when_transitioning(self, safe_state):
        """Test is_safe is False when transitioning."""
        safe_state.is_transitioning = True
        assert safe_state.is_safe is False

    def test_is_safe_false_when_black_screen(self, safe_state):
        """Test is_safe is False on black screen."""
        safe_state.is_black_screen = True
        assert safe_state.is_safe is False

    def test_is_combat_when_attacking(self, combat_state):
        """Test is_combat is True when attacking."""
        assert combat_state.is_combat is True

    def test_is_combat_when_knocked_back(self, safe_state):
        """Test is_combat is True when knocked back."""
        safe_state.link_action = LinkAction.KNOCKED_BACK
        assert safe_state.is_combat is True

    def test_is_combat_when_spinning(self, safe_state):
        """Test is_combat is True when spinning."""
        safe_state.link_action = LinkAction.SPINNING
        assert safe_state.is_combat is True

    def test_is_combat_false_when_standing(self, safe_state):
        """Test is_combat is False when standing."""
        assert safe_state.is_combat is False

    def test_position_key_format(self, safe_state):
        """Test position_key has correct format."""
        key = safe_state.position_key
        assert isinstance(key, str)
        # Format: "area:room:x:y"
        parts = key.split(":")
        assert len(parts) == 4


class TestGameStateParserBasic:
    """Test basic GameStateParser functionality."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return GameStateParser()

    @pytest.fixture
    def overworld_snapshot(self):
        """Create overworld snapshot."""
        return GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

    def test_parser_creation(self, parser):
        """Test parser can be created."""
        assert parser is not None

    def test_parse_returns_parsed_state(self, parser, overworld_snapshot):
        """Test parse returns ParsedGameState."""
        state = parser.parse(overworld_snapshot)
        assert isinstance(state, ParsedGameState)

    def test_parse_overworld_mode(self, parser, overworld_snapshot):
        """Test parsing overworld mode."""
        state = parser.parse(overworld_snapshot)
        assert state.phase == GamePhase.OVERWORLD

    def test_parse_dungeon_mode(self, parser):
        """Test parsing dungeon mode."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x07, submode=0x00,
            area=0x29, room=0x50,
            link_x=128, link_y=128, link_z=0,
            link_direction=0, link_state=0x00,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.phase == GamePhase.DUNGEON

    def test_parse_menu_mode(self, parser):
        """Test parsing menu mode."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x0E, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.phase == GamePhase.MENU
        assert state.is_menu_open is True


class TestGameStateParserHealth:
    """Test health calculation in parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return GameStateParser()

    def test_full_health(self, parser):
        """Test full health calculation."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.health_percent == 1.0

    def test_half_health(self, parser):
        """Test half health calculation."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=12, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.health_percent == 0.5

    def test_zero_health(self, parser):
        """Test zero health calculation."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=0, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.health_percent == 0.0

    def test_zero_max_health_handled(self, parser):
        """Test zero max health doesn't divide by zero."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=0, max_health=0
        )
        state = parser.parse(snapshot)
        assert state.health_percent == 1.0  # Defaults to 1.0


class TestGameStateParserBlackScreen:
    """Test black screen detection in parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return GameStateParser()

    def test_black_screen_detected(self, parser):
        """Test black screen is detected."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x07, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=True, inidisp=0x80,  # Black screen
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.is_black_screen is True
        assert state.phase == GamePhase.BLACK_SCREEN

    def test_normal_screen_not_black(self, parser):
        """Test normal screen is not black."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.is_black_screen is False


class TestGameStateParserFlags:
    """Test flag calculation in parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return GameStateParser()

    def test_is_playing_overworld(self, parser):
        """Test is_playing True in overworld."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.is_playing is True

    def test_is_playing_dungeon(self, parser):
        """Test is_playing True in dungeon."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x07, submode=0x00,
            area=0x29, room=0x50,
            link_x=128, link_y=128, link_z=0,
            link_direction=0, link_state=0x00,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.is_playing is True

    def test_is_playing_false_in_menu(self, parser):
        """Test is_playing False in menu."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x0E, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.is_playing is False

    def test_is_transitioning_with_submode(self, parser):
        """Test is_transitioning when submode nonzero."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x10,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.is_transitioning is True

    def test_is_transitioning_in_mode_6(self, parser):
        """Test is_transitioning in mode 0x06."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x06, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.is_transitioning is True

    def test_can_move_true_when_standing(self, parser):
        """Test can_move True when standing in gameplay."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.can_move is True

    def test_can_move_false_when_attacking(self, parser):
        """Test can_move False when attacking."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x11,  # attacking
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.can_move is False


class TestGameStateParserChangeDetection:
    """Test change detection in parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return GameStateParser()

    def test_initial_state_detection(self, parser):
        """Test initial state returns initial message when no last state."""
        # Create a state directly without using parser
        raw = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = ParsedGameState(
            raw=raw,
            phase=GamePhase.OVERWORLD,
            location_name="Village Center",
            area_id=0x29, room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="down",
            link_position=(512, 480),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=True,
            can_use_items=True,
            submode=0x00
        )
        # Parser has no last state, so should detect initial
        changes = parser.detect_change(state)
        assert "Initial state" in changes

    def test_phase_change_detected(self, parser):
        """Test phase change is detected."""
        # Parse first state to set _last_state
        snapshot1 = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        parser.parse(snapshot1)  # Sets _last_state

        # Create second state manually to avoid overwriting _last_state
        raw2 = GameStateSnapshot(
            timestamp=2.0, mode=0x0E, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state2 = ParsedGameState(
            raw=raw2,
            phase=GamePhase.MENU,
            location_name="Village Center",
            area_id=0x29, room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="down",
            link_position=(512, 480),
            link_layer=0,
            health_percent=1.0,
            is_playing=False,
            is_transitioning=False,
            is_menu_open=True,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=False,
            can_use_items=False,
            submode=0x00
        )
        changes = parser.detect_change(state2)

        assert any("Phase" in c for c in changes)

    def test_area_change_detected(self, parser):
        """Test area change is detected."""
        snapshot1 = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        parser.parse(snapshot1)

        raw2 = GameStateSnapshot(
            timestamp=2.0, mode=0x09, submode=0x00,
            area=0x28, room=0x00,  # Different area
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state2 = ParsedGameState(
            raw=raw2,
            phase=GamePhase.OVERWORLD,
            location_name="Village South",
            area_id=0x28, room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="down",
            link_position=(512, 480),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=True,
            can_use_items=True,
            submode=0x00
        )
        changes = parser.detect_change(state2)

        assert any("Area" in c for c in changes)

    def test_black_screen_change_detected(self, parser):
        """Test black screen change is detected."""
        snapshot1 = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        parser.parse(snapshot1)

        raw2 = GameStateSnapshot(
            timestamp=2.0, mode=0x07, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=True, inidisp=0x80,  # Black screen
            health=24, max_health=24
        )
        state2 = ParsedGameState(
            raw=raw2,
            phase=GamePhase.BLACK_SCREEN,
            location_name="Room 0x00",
            area_id=0x29, room_id=0x00,
            is_indoors=True,
            link_action=LinkAction.STANDING,
            link_direction="down",
            link_position=(512, 480),
            link_layer=0,
            health_percent=1.0,
            is_playing=False,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=True,
            can_move=False,
            can_use_items=False,
            submode=0x00
        )
        changes = parser.detect_change(state2)

        assert any("BLACK SCREEN" in c for c in changes)

    def test_position_change_detected(self, parser):
        """Test significant position change is detected."""
        snapshot1 = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=100, link_y=100, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        parser.parse(snapshot1)

        raw2 = GameStateSnapshot(
            timestamp=2.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=200, link_y=200, link_z=0,  # >16 pixel change
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state2 = ParsedGameState(
            raw=raw2,
            phase=GamePhase.OVERWORLD,
            location_name="Village Center",
            area_id=0x29, room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="down",
            link_position=(200, 200),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=True,
            can_use_items=True,
            submode=0x00
        )
        changes = parser.detect_change(state2)

        assert any("Position" in c for c in changes)

    def test_small_position_change_not_detected(self, parser):
        """Test small position change is not detected."""
        snapshot1 = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=100, link_y=100, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        parser.parse(snapshot1)

        raw2 = GameStateSnapshot(
            timestamp=2.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=105, link_y=105, link_z=0,  # <16 pixel change
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state2 = ParsedGameState(
            raw=raw2,
            phase=GamePhase.OVERWORLD,
            location_name="Village Center",
            area_id=0x29, room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="down",
            link_position=(105, 105),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=True,
            can_use_items=True,
            submode=0x00
        )
        changes = parser.detect_change(state2)

        assert not any("Position" in c for c in changes)


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_parser_returns_parser(self):
        """Test get_parser returns GameStateParser."""
        parser = get_parser()
        assert isinstance(parser, GameStateParser)

    def test_get_parser_returns_singleton(self):
        """Test get_parser returns same instance."""
        parser1 = get_parser()
        parser2 = get_parser()
        assert parser1 is parser2

    def test_parse_state_function(self):
        """Test parse_state convenience function."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parse_state(snapshot)
        assert isinstance(state, ParsedGameState)
        assert state.phase == GamePhase.OVERWORLD


class TestLocationNameGeneration:
    """Test location name generation."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return GameStateParser()

    def test_known_overworld_area_name(self, parser):
        """Test known overworld area gets proper name."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,  # Village Center
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert "Village" in state.location_name

    def test_unknown_overworld_area_hex_fallback(self, parser):
        """Test unknown area gets hex fallback."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0xFF, room=0x00,  # Unknown area
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert "0xFF" in state.location_name or "FF" in state.location_name.upper()

    def test_indoor_room_hex_fallback(self, parser):
        """Test indoor room gets appropriate name."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x07, submode=0x00,
            area=0x29, room=0x99,  # Unknown room
            link_x=128, link_y=128, link_z=0,
            link_direction=0, link_state=0x00,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert "Room" in state.location_name


class TestEdgeCaseParsing:
    """Test edge case parsing scenarios."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return GameStateParser()

    def test_unknown_mode_handled(self, parser):
        """Test unknown mode returns UNKNOWN phase."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0xFF, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.phase == GamePhase.UNKNOWN

    def test_unknown_link_state_handled(self, parser):
        """Test unknown link state returns UNKNOWN action."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0xFF,  # Unknown state
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.link_action == LinkAction.UNKNOWN

    def test_unknown_direction_handled(self, parser):
        """Test unknown direction returns 'unknown'."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=0xFF,  # Invalid direction
            link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.link_direction == "unknown"

    def test_extreme_position_values(self, parser):
        """Test extreme position values handled."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=0xFFFF, link_y=0xFFFF, link_z=0xFF,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.link_position == (0xFFFF, 0xFFFF)
        assert state.link_layer == 0xFF

    def test_zero_position_values(self, parser):
        """Test zero position values handled."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=0, link_y=0, link_z=0,
            link_direction=2, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        state = parser.parse(snapshot)
        assert state.link_position == (0, 0)
