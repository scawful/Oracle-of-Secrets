"""Tests for game transitions and black screen detection.

These tests verify the transition handling infrastructure,
which is critical for Goal B (Black Screen Bug Resolution).

Campaign Goals Supported:
- B.1: Reproduce black screen with evidence
- B.5: Regression test all transition types
- C.3: Automated regression suite
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
    parse_state,
)


class TestTransitionTypes:
    """Tests for different transition type detection."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return GameStateParser()

    def test_overworld_to_dungeon_transition(self, parser):
        """Test detecting overworld -> dungeon transition.

        This is the most common transition and must work correctly.
        Mode changes: 0x09 -> 0x06 -> 0x07
        """
        # Start in overworld
        overworld = GameStateSnapshot(
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
        state1 = parser.parse(overworld)
        assert state1.phase == GamePhase.OVERWORLD
        assert state1.is_playing is True

        # During transition (mode 0x06)
        transition = GameStateSnapshot(
            timestamp=1001.0,
            mode=0x06,
            submode=0x08,
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
        state2 = parser.parse(transition)
        assert state2.phase == GamePhase.TRANSITION
        assert state2.is_transitioning is True
        assert state2.can_move is False

        # Arrived in dungeon
        dungeon = GameStateSnapshot(
            timestamp=1002.0,
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
        state3 = parser.parse(dungeon)
        assert state3.phase == GamePhase.DUNGEON
        assert state3.is_indoors is True
        assert state3.is_transitioning is False

    def test_dungeon_to_overworld_transition(self, parser):
        """Test detecting dungeon -> overworld transition.

        Mode changes: 0x07 -> 0x06 -> 0x09
        """
        # Start in dungeon
        dungeon = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=True,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        state1 = parser.parse(dungeon)
        assert state1.phase == GamePhase.DUNGEON

        # Arrived in overworld
        overworld = GameStateSnapshot(
            timestamp=1002.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=384,
            link_y=256,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        state2 = parser.parse(overworld)
        assert state2.phase == GamePhase.OVERWORLD
        assert state2.is_indoors is False

    def test_intraroom_transition(self, parser):
        """Test detecting intraroom transition (layer change).

        This uses submodule state machine without mode change.
        """
        # Normal dungeon state
        normal = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=True,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        state1 = parser.parse(normal)
        assert state1.is_transitioning is False

        # Submodule transition (e.g., pit fall, stair climb)
        submod_transition = GameStateSnapshot(
            timestamp=1001.0,
            mode=0x07,
            submode=0x12,  # Non-zero submodule
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x02,
            link_state=0x08,  # Falling
            indoors=True,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        state2 = parser.parse(submod_transition)
        assert state2.is_transitioning is True
        assert state2.can_move is False


class TestBlackScreenDetection:
    """Tests for black screen bug detection.

    Goal B: Black Screen Bug Resolution
    """

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_black_screen_from_inidisp(self, parser):
        """Test black screen detection from INIDISP = 0x80.

        INIDISP bit 7 = forced blanking = screen off.
        This is the primary indicator of the black screen bug.
        """
        # Mode 0x07 with INIDISP 0x80 = black screen bug
        black_screen = GameStateSnapshot(
            timestamp=1000.0,
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
            inidisp=0x80,  # FORCED BLANKING
            health=24,
            max_health=24,
        )
        state = parser.parse(black_screen)

        assert state.is_black_screen is True
        assert state.phase == GamePhase.BLACK_SCREEN
        assert state.can_move is False
        assert state.can_use_items is False

    def test_normal_screen_inidisp(self, parser):
        """Test that normal INIDISP values don't trigger black screen."""
        # INIDISP 0x0F = full brightness, screen on
        normal = GameStateSnapshot(
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
        )
        state = parser.parse(normal)

        assert state.is_black_screen is False
        assert state.phase == GamePhase.DUNGEON

    def test_black_screen_during_load_expected(self, parser):
        """Test that black screen during mode 0x06 is detected.

        During room loading (mode 0x06), INIDISP 0x80 is normal but
        the parser still detects it as black screen state.
        This is correct behavior - the caller must interpret context.
        """
        loading = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x06,  # Loading mode
            submode=0x04,
            area=0x00,
            room=0x00,
            link_x=0,
            link_y=0,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=False,
            inidisp=0x80,  # Expected during load
            health=24,
            max_health=24,
        )
        state = parser.parse(loading)

        # is_black_screen is True because INIDISP 0x80 with mode 0x06
        # The parser detects the raw state; caller interprets context
        assert state.is_black_screen is True
        # Phase is BLACK_SCREEN because black_screen check runs first
        assert state.phase == GamePhase.BLACK_SCREEN
        # But is_playing is False for mode 0x06, distinguishing from bug
        assert state.is_playing is False

    def test_black_screen_change_detection(self, parser):
        """Test detecting when black screen appears or clears."""
        # Normal state
        normal = GameStateSnapshot(
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
        )
        state1 = parser.parse(normal)

        # Black screen state (construct directly for change detection)
        black_snap = GameStateSnapshot(
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
            inidisp=0x80,
            health=24,
            max_health=24,
        )
        state2 = ParsedGameState(
            raw=black_snap,
            phase=GamePhase.BLACK_SCREEN,
            location_name="Room 0x27",
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
            is_black_screen=True,
            can_move=False,
            can_use_items=False,
            submode=0x0F,
        )

        changes = parser.detect_change(state2)
        assert any("BLACK SCREEN" in c for c in changes)


class TestTransitionScenarios:
    """Test specific transition scenarios known to cause issues."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_building_entry_scenario(self, parser):
        """Test building entry - historically problematic transition.

        This scenario has caused black screen bugs in the past.
        """
        # Outside building
        outside = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=0x00,  # Facing up (toward door)
            link_state=0x01,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        state1 = parser.parse(outside)
        assert state1.phase == GamePhase.OVERWORLD

        # Inside building (successful transition)
        inside = GameStateSnapshot(
            timestamp=1002.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x12,  # Sanctuary room
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x0F,  # Screen ON = success
            health=24,
            max_health=24,
        )
        state2 = parser.parse(inside)

        assert state2.phase == GamePhase.DUNGEON
        assert state2.is_black_screen is False
        assert state2.can_move is True

    def test_water_gate_transition(self, parser):
        """Test Water Gate room transition - known problem area.

        Room 0x27 (Zora Temple Water Gate) has had transition issues.
        """
        water_gate = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x02,
            link_state=0x02,  # Swimming
            indoors=True,
            inidisp=0x0F,
            health=24,
            max_health=24,
            raw_data={"room_id": 0x27},
        )
        state = parser.parse(water_gate)

        assert state.location_name == "Zora Temple - Water Gate"
        assert state.link_action == LinkAction.SWIMMING
        assert state.is_black_screen is False


class TestSubmoduleStateMachine:
    """Tests for submodule state machine behavior.

    The submodule ($7E0011) controls transition state machines.
    When stuck at non-zero, transitions fail.
    """

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_submodule_zero_is_normal(self, parser):
        """Test that submodule 0x00 indicates normal gameplay."""
        state_snap = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x00,  # Normal
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
        )
        state = parser.parse(state_snap)

        assert state.is_transitioning is False
        assert state.submode == 0x00

    def test_submodule_nonzero_is_transition(self, parser):
        """Test that non-zero submodule indicates transition."""
        for submod in [0x01, 0x08, 0x0F, 0x12, 0x23]:
            state_snap = GameStateSnapshot(
                timestamp=1000.0,
                mode=0x07,
                submode=submod,
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
            )
            state = parser.parse(state_snap)

            assert state.is_transitioning is True, f"Submode {submod} should be transitioning"
            assert state.submode == submod

    def test_landing_wipe_stuck_scenario(self, parser):
        """Test detecting stuck LandingWipe state (submodule 0x0F).

        Submodule 0x0F is LandingWipe. If stuck here with INIDISP 0x80,
        the fade-in never completes.
        """
        stuck = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x0F,  # LandingWipe
            area=0x00,
            room=0x12,
            link_x=0,
            link_y=0,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x80,  # Screen still off = stuck
            health=24,
            max_health=24,
        )
        state = parser.parse(stuck)

        assert state.is_black_screen is True
        assert state.is_transitioning is True
        assert state.submode == 0x0F
        assert state.can_move is False
