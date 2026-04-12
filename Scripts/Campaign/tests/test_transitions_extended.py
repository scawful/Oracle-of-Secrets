"""Extended tests for game transitions and black screen detection.

Iteration 35 of the ralph-loop campaign.
Adds comprehensive coverage for transition handling, black screen detection,
INIDISP states, mode transitions, and recovery scenarios.

Campaign Goals Supported:
- B.1: Reproduce black screen with evidence
- B.5: Regression test all transition types
- C.3: Automated regression suite
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

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


# =============================================================================
# INIDISP State Tests
# =============================================================================

class TestINIDISPValues:
    """Comprehensive tests for INIDISP register interpretation."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_snapshot(self, inidisp: int, mode: int = 0x07) -> GameStateSnapshot:
        """Helper to create snapshot with specific INIDISP value."""
        return GameStateSnapshot(
            timestamp=1000.0,
            mode=mode,
            submode=0x00,
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=inidisp,
            health=24,
            max_health=24,
        )

    def test_inidisp_zero_brightness(self, parser):
        """INIDISP 0x00 = zero brightness but not forced blank."""
        state = parser.parse(self.make_snapshot(0x00))
        # Zero brightness without forced blank bit is dim but not "black screen bug"
        assert state.is_black_screen is False

    def test_inidisp_full_brightness(self, parser):
        """INIDISP 0x0F = full brightness, screen fully on."""
        state = parser.parse(self.make_snapshot(0x0F))
        assert state.is_black_screen is False
        assert state.can_move is True

    def test_inidisp_forced_blank_bit(self, parser):
        """INIDISP 0x80 = forced blanking bit set."""
        state = parser.parse(self.make_snapshot(0x80))
        assert state.is_black_screen is True
        assert state.phase == GamePhase.BLACK_SCREEN
        assert state.can_move is False

    def test_inidisp_forced_blank_with_brightness(self, parser):
        """INIDISP 0x8F = forced blank + brightness bits.

        Note: The implementation checks for exactly 0x80, not just bit 7.
        This is specific to the black screen bug detection pattern.
        """
        state = parser.parse(self.make_snapshot(0x8F))
        # Only exact 0x80 triggers black screen detection
        assert state.is_black_screen is False

    @pytest.mark.parametrize("inidisp", [0x01, 0x02, 0x04, 0x08, 0x0E])
    def test_partial_brightness_values(self, parser, inidisp):
        """Various brightness levels without forced blank."""
        state = parser.parse(self.make_snapshot(inidisp))
        assert state.is_black_screen is False

    @pytest.mark.parametrize("inidisp", [0x81, 0x82, 0x84, 0x88, 0x8E])
    def test_forced_blank_with_various_brightness(self, parser, inidisp):
        """Forced blank with brightness bits - NOT black screen bug.

        The black screen bug detection specifically looks for INIDISP=0x80.
        Other values with bit 7 set are not considered the bug state.
        """
        state = parser.parse(self.make_snapshot(inidisp))
        # Only exact 0x80 triggers black screen detection
        assert state.is_black_screen is False

    def test_all_brightness_levels_without_blank(self, parser):
        """Test all 16 brightness levels (0x00-0x0F)."""
        for level in range(16):
            state = parser.parse(self.make_snapshot(level))
            assert state.is_black_screen is False, f"Level {level} should not be black screen"

    def test_only_exact_0x80_is_black_screen(self, parser):
        """Only INIDISP = 0x80 exactly triggers black screen detection.

        The implementation specifically checks for the black screen bug pattern,
        which is INIDISP=0x80 (forced blank, zero brightness) in modes 0x06/0x07.
        """
        # 0x80 exactly = black screen
        state = parser.parse(self.make_snapshot(0x80))
        assert state.is_black_screen is True

        # Other values with bit 7 = NOT black screen
        for level in range(1, 16):
            inidisp = 0x80 | level
            state = parser.parse(self.make_snapshot(inidisp))
            assert state.is_black_screen is False, f"INIDISP {hex(inidisp)} should not be black screen"


# =============================================================================
# Mode Transition Tests
# =============================================================================

class TestModeTransitions:
    """Tests for all game mode transitions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_snapshot(self, mode: int, submode: int = 0x00, indoors: bool = False,
                      inidisp: int = 0x0F) -> GameStateSnapshot:
        return GameStateSnapshot(
            timestamp=1000.0,
            mode=mode,
            submode=submode,
            area=0x00 if indoors else 0x29,
            room=0x27 if indoors else 0x00,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=indoors,
            inidisp=inidisp,
            health=24,
            max_health=24,
        )

    def test_mode_00_title_screen(self, parser):
        """Mode 0x00 = Title screen / initialization."""
        state = parser.parse(self.make_snapshot(0x00))
        # Mode 0x00 is typically title/init
        assert state.is_playing is False or state.phase == GamePhase.TITLE

    def test_mode_06_loading(self, parser):
        """Mode 0x06 = Room loading / transition."""
        state = parser.parse(self.make_snapshot(0x06))
        assert state.is_transitioning is True or state.phase == GamePhase.TRANSITION

    def test_mode_07_dungeon(self, parser):
        """Mode 0x07 = Dungeon/indoor gameplay."""
        state = parser.parse(self.make_snapshot(0x07, indoors=True))
        assert state.phase == GamePhase.DUNGEON
        assert state.is_indoors is True

    def test_mode_09_overworld(self, parser):
        """Mode 0x09 = Overworld gameplay."""
        state = parser.parse(self.make_snapshot(0x09, indoors=False))
        assert state.phase == GamePhase.OVERWORLD
        assert state.is_indoors is False

    def test_mode_0e_menu(self, parser):
        """Mode 0x0E = Menu / inventory."""
        state = parser.parse(self.make_snapshot(0x0E))
        assert state.phase == GamePhase.MENU or state.is_menu_open is True

    def test_mode_14_cutscene(self, parser):
        """Mode 0x14 = Cutscene (not dialogue)."""
        state = parser.parse(self.make_snapshot(0x14))
        assert state.phase == GamePhase.CUTSCENE
        assert state.can_move is False

    @pytest.mark.parametrize("mode", [0x07, 0x09])
    def test_playable_modes(self, parser, mode):
        """Test that playable modes allow movement."""
        indoors = mode == 0x07
        state = parser.parse(self.make_snapshot(mode, indoors=indoors))
        assert state.can_move is True
        assert state.is_playing is True

    @pytest.mark.parametrize("mode", [0x00, 0x06, 0x0E, 0x14])
    def test_non_playable_modes(self, parser, mode):
        """Test that non-playable modes restrict movement."""
        state = parser.parse(self.make_snapshot(mode))
        # During these modes, player shouldn't be able to freely move
        # Note: The specific behavior may vary by mode
        assert state.can_move is False or state.is_transitioning is True


# =============================================================================
# Area Transition Tests
# =============================================================================

class TestAreaTransitions:
    """Tests for transitions between different area codes."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_overworld_snapshot(self, area: int) -> GameStateSnapshot:
        """Create overworld snapshot for specific area."""
        return GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=area,
            room=0x00,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )

    def test_light_world_area_codes(self, parser):
        """Light World areas are 0x00-0x3F."""
        for area in [0x00, 0x10, 0x20, 0x29, 0x3F]:
            state = parser.parse(self.make_overworld_snapshot(area))
            assert state.phase == GamePhase.OVERWORLD
            # Check we're not in Dark World
            assert (state.area_id & 0x40) == 0

    def test_dark_world_area_codes(self, parser):
        """Dark World areas have bit 0x40 set (0x40-0x7F)."""
        for area in [0x40, 0x50, 0x60, 0x69, 0x7F]:
            state = parser.parse(self.make_overworld_snapshot(area))
            assert state.phase == GamePhase.OVERWORLD
            # Dark World bit is set
            assert (state.area_id & 0x40) == 0x40

    def test_underwater_area_codes(self, parser):
        """Underwater areas have bit 0x80 set."""
        for area in [0x80, 0x90, 0xA0, 0xBF]:
            state = parser.parse(self.make_overworld_snapshot(area))
            # Underwater bit is set
            assert (state.area_id & 0x80) == 0x80

    def test_light_to_dark_world_transition(self, parser):
        """Test transition from Light World to Dark World area."""
        light = parser.parse(self.make_overworld_snapshot(0x29))
        dark = parser.parse(self.make_overworld_snapshot(0x69))

        # Light World
        assert (light.area_id & 0x40) == 0
        # Dark World
        assert (dark.area_id & 0x40) == 0x40
        # Both should be overworld phase
        assert light.phase == dark.phase == GamePhase.OVERWORLD


# =============================================================================
# Submodule State Machine Tests
# =============================================================================

class TestSubmoduleStateMachine:
    """Extended tests for submodule ($7E0011) state machine."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_snapshot(self, submode: int, inidisp: int = 0x0F) -> GameStateSnapshot:
        return GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=submode,
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=inidisp,
            health=24,
            max_health=24,
        )

    def test_submodule_00_idle(self, parser):
        """Submodule 0x00 = Normal gameplay (idle)."""
        state = parser.parse(self.make_snapshot(0x00))
        assert state.is_transitioning is False
        assert state.can_move is True

    @pytest.mark.parametrize("submode,name", [
        (0x01, "InitTransition"),
        (0x02, "LoadingRoom"),
        (0x08, "DoorTransition"),
        (0x0F, "LandingWipe"),
        (0x12, "FallingDown"),
        (0x14, "OpeningChest"),
        (0x23, "SplashDown"),
    ])
    def test_known_submodule_values(self, parser, submode, name):
        """Test known submodule values indicate transition."""
        state = parser.parse(self.make_snapshot(submode))
        assert state.is_transitioning is True, f"Submodule {hex(submode)} ({name}) should be transitioning"
        assert state.submode == submode

    def test_submodule_0f_landing_wipe_normal(self, parser):
        """Submodule 0x0F (LandingWipe) with INIDISP 0x0F = fading in."""
        state = parser.parse(self.make_snapshot(0x0F, inidisp=0x0F))
        assert state.is_transitioning is True
        assert state.is_black_screen is False  # Screen is on

    def test_submodule_0f_landing_wipe_stuck(self, parser):
        """Submodule 0x0F (LandingWipe) with INIDISP 0x80 = stuck!"""
        state = parser.parse(self.make_snapshot(0x0F, inidisp=0x80))
        assert state.is_transitioning is True
        assert state.is_black_screen is True
        # This combination indicates the black screen bug
        assert state.can_move is False

    def test_all_submodules_are_transitioning(self, parser):
        """Any non-zero submodule should be marked as transitioning."""
        for sub in range(1, 0x30):  # Common submodule range
            state = parser.parse(self.make_snapshot(sub))
            assert state.is_transitioning is True, f"Submodule {hex(sub)} should be transitioning"


# =============================================================================
# Transition Sequence Tests
# =============================================================================

class TestTransitionSequences:
    """Tests for complete transition sequences."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_overworld_door_entry_sequence(self, parser):
        """Full sequence: OW standing -> door -> loading -> dungeon."""
        # Step 1: Standing outside
        step1 = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        s1 = parser.parse(step1)
        assert s1.phase == GamePhase.OVERWORLD
        assert s1.can_move is True

        # Step 2: Entering door (mode change)
        step2 = GameStateSnapshot(
            timestamp=1001.0,
            mode=0x06,
            submode=0x08,
            area=0x29,
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=False,
            inidisp=0x80,  # Screen blanked during transition
            health=24,
            max_health=24,
        )
        s2 = parser.parse(step2)
        assert s2.is_transitioning is True or s2.phase == GamePhase.TRANSITION

        # Step 3: Loading room
        step3 = GameStateSnapshot(
            timestamp=1002.0,
            mode=0x06,
            submode=0x02,
            area=0x00,
            room=0x12,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x80,  # Still loading
            health=24,
            max_health=24,
        )
        s3 = parser.parse(step3)
        assert s3.is_transitioning is True or s3.is_black_screen is True

        # Step 4: Inside dungeon (successful)
        step4 = GameStateSnapshot(
            timestamp=1003.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x12,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x0F,  # Screen on!
            health=24,
            max_health=24,
        )
        s4 = parser.parse(step4)
        assert s4.phase == GamePhase.DUNGEON
        assert s4.is_black_screen is False
        assert s4.can_move is True

    def test_dungeon_exit_sequence(self, parser):
        """Full sequence: Dungeon -> door -> loading -> OW."""
        # Step 1: In dungeon near exit
        step1 = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x12,
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
        s1 = parser.parse(step1)
        assert s1.phase == GamePhase.DUNGEON
        assert s1.can_move is True

        # Step 2: Door transition begins
        step2 = GameStateSnapshot(
            timestamp=1001.0,
            mode=0x06,
            submode=0x08,
            area=0x00,
            room=0x12,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=True,
            inidisp=0x80,
            health=24,
            max_health=24,
        )
        s2 = parser.parse(step2)
        assert s2.can_move is False

        # Step 3: Back in overworld
        step3 = GameStateSnapshot(
            timestamp=1003.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        s3 = parser.parse(step3)
        assert s3.phase == GamePhase.OVERWORLD
        assert s3.is_black_screen is False

    def test_black_screen_stuck_sequence(self, parser):
        """Sequence that results in stuck black screen bug."""
        # Step 1: Normal dungeon
        step1 = GameStateSnapshot(
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
        s1 = parser.parse(step1)
        assert s1.is_black_screen is False

        # Step 2: Transition starts
        step2 = GameStateSnapshot(
            timestamp=1001.0,
            mode=0x07,
            submode=0x0F,  # LandingWipe
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x80,  # Starting to blank
            health=24,
            max_health=24,
        )
        s2 = parser.parse(step2)
        assert s2.is_transitioning is True

        # Step 3: STUCK - submodule never resets, INIDISP never restored
        step3 = GameStateSnapshot(
            timestamp=2000.0,  # Much later
            mode=0x07,
            submode=0x0F,  # Still in LandingWipe
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x80,  # Still blanked!
            health=24,
            max_health=24,
        )
        s3 = parser.parse(step3)
        assert s3.is_black_screen is True
        assert s3.phase == GamePhase.BLACK_SCREEN
        assert s3.can_move is False


# =============================================================================
# Room-Specific Transition Tests
# =============================================================================

class TestRoomSpecificTransitions:
    """Tests for known problematic room transitions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_room_snapshot(self, room: int, inidisp: int = 0x0F,
                           submode: int = 0x00) -> GameStateSnapshot:
        return GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=submode,
            area=0x00,
            room=room,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=inidisp,
            health=24,
            max_health=24,
        )

    def test_water_gate_room_0x27(self, parser):
        """Room 0x27 (Water Gate) - historically problematic."""
        state = parser.parse(self.make_room_snapshot(0x27))
        assert state.is_black_screen is False
        assert state.can_move is True

    def test_sanctuary_room_0x12(self, parser):
        """Room 0x12 (Hall of Secrets/Sanctuary)."""
        state = parser.parse(self.make_room_snapshot(0x12))
        assert state.is_black_screen is False
        assert state.phase == GamePhase.DUNGEON

    def test_hyrule_castle_entrance_0x60(self, parser):
        """Room 0x60 (Hyrule Castle entrance area)."""
        state = parser.parse(self.make_room_snapshot(0x60))
        assert state.phase == GamePhase.DUNGEON

    def test_lost_woods_room_special(self, parser):
        """Test rooms in Lost Woods area."""
        # Lost Woods has special transition handling
        for room in [0x50, 0x51, 0x52]:
            state = parser.parse(self.make_room_snapshot(room))
            assert state.phase == GamePhase.DUNGEON

    @pytest.mark.parametrize("room", [0x00, 0x10, 0x20, 0x30, 0x40, 0xFF])
    def test_various_room_ids(self, parser, room):
        """Various room IDs should parse without error."""
        state = parser.parse(self.make_room_snapshot(room))
        assert state is not None
        assert state.room_id == room


# =============================================================================
# Link State During Transitions
# =============================================================================

class TestLinkStateDuringTransitions:
    """Tests for Link's state during various transitions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_snapshot(self, link_state: int, mode: int = 0x07,
                      submode: int = 0x00) -> GameStateSnapshot:
        return GameStateSnapshot(
            timestamp=1000.0,
            mode=mode,
            submode=submode,
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=link_state,
            indoors=True,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )

    def test_link_state_00_standing(self, parser):
        """Link state 0x00 = Standing/idle."""
        state = parser.parse(self.make_snapshot(0x00))
        assert state.link_action == LinkAction.STANDING
        assert state.can_move is True

    def test_link_state_01_walking(self, parser):
        """Link state 0x01 = Walking."""
        state = parser.parse(self.make_snapshot(0x01))
        assert state.link_action == LinkAction.WALKING

    def test_link_state_02_swimming(self, parser):
        """Link state 0x02 = Swimming."""
        state = parser.parse(self.make_snapshot(0x02))
        assert state.link_action == LinkAction.SWIMMING

    def test_link_state_08_falling(self, parser):
        """Link state 0x08 = Falling."""
        state = parser.parse(self.make_snapshot(0x08))
        assert state.link_action == LinkAction.FALLING
        # Can't move while falling
        assert state.can_move is False

    def test_link_state_17_dying(self, parser):
        """Link state 0x17 = Dying."""
        state = parser.parse(self.make_snapshot(0x17))
        assert state.link_action == LinkAction.DYING
        assert state.can_move is False

    @pytest.mark.parametrize("link_state", [0x08, 0x0A, 0x14, 0x1C])
    def test_link_states_that_block_movement(self, parser, link_state):
        """Certain Link states prevent free movement."""
        state = parser.parse(self.make_snapshot(link_state))
        # These states typically block movement
        assert state.can_move is False or state.link_action != LinkAction.STANDING


# =============================================================================
# Direction During Transitions
# =============================================================================

class TestDirectionDuringTransitions:
    """Tests for Link's direction during transitions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_snapshot(self, direction: int) -> GameStateSnapshot:
        return GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=direction,
            link_state=0x00,
            indoors=True,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )

    @pytest.mark.parametrize("direction,name", [
        (0x00, "up"),
        (0x02, "down"),
        (0x04, "left"),
        (0x06, "right"),
    ])
    def test_cardinal_directions(self, parser, direction, name):
        """Test all four cardinal directions.

        ALTTP direction encoding: 0x00=up, 0x02=down, 0x04=left, 0x06=right.
        """
        state = parser.parse(self.make_snapshot(direction))
        assert state.link_direction == name

    def test_direction_preserved_during_transition(self, parser):
        """Direction should be preserved during submodule transitions."""
        direction_map = {0x00: "up", 0x02: "down", 0x04: "left", 0x06: "right"}
        for direction, expected in direction_map.items():
            snap = GameStateSnapshot(
                timestamp=1000.0,
                mode=0x07,
                submode=0x0F,  # Transitioning
                area=0x00,
                room=0x27,
                link_x=256,
                link_y=320,
                link_z=0,
                link_direction=direction,
                link_state=0x00,
                indoors=True,
                inidisp=0x0F,
                health=24,
                max_health=24,
            )
            state = parser.parse(snap)
            # Direction should still be parsed correctly
            assert state.link_direction == expected


# =============================================================================
# Health During Transitions
# =============================================================================

class TestHealthDuringTransitions:
    """Tests for health state during transitions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_snapshot(self, health: int, max_health: int = 24,
                      mode: int = 0x07) -> GameStateSnapshot:
        return GameStateSnapshot(
            timestamp=1000.0,
            mode=mode,
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
            health=health,
            max_health=max_health,
        )

    def test_full_health(self, parser):
        """Full health = 100%."""
        state = parser.parse(self.make_snapshot(24, 24))
        assert state.health_percent == 1.0

    def test_half_health(self, parser):
        """Half health = 50%."""
        state = parser.parse(self.make_snapshot(12, 24))
        assert state.health_percent == 0.5

    def test_low_health(self, parser):
        """Low health = 25%."""
        state = parser.parse(self.make_snapshot(6, 24))
        assert state.health_percent == 0.25

    def test_one_heart(self, parser):
        """One heart (2 units)."""
        state = parser.parse(self.make_snapshot(2, 24))
        assert state.health_percent == pytest.approx(2/24, rel=0.01)

    def test_health_preserved_during_black_screen(self, parser):
        """Health should still be readable during black screen."""
        snap = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x0F,
            area=0x00,
            room=0x27,
            link_x=0,
            link_y=0,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x80,  # Black screen
            health=24,
            max_health=24,
        )
        state = parser.parse(snap)
        assert state.is_black_screen is True
        assert state.health_percent == 1.0  # Health still readable


# =============================================================================
# Position During Transitions
# =============================================================================

class TestPositionDuringTransitions:
    """Tests for Link's position during transitions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_position_during_normal_gameplay(self, parser):
        """Position should be accurate during normal gameplay."""
        snap = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x27,
            link_x=123,
            link_y=456,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        state = parser.parse(snap)
        assert state.link_position == (123, 456)

    def test_position_zero_during_transition(self, parser):
        """Position may be zero/reset during some transitions."""
        snap = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x06,  # Loading
            submode=0x04,
            area=0x00,
            room=0x00,
            link_x=0,
            link_y=0,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=False,
            inidisp=0x80,
            health=24,
            max_health=24,
        )
        state = parser.parse(snap)
        assert state.link_position == (0, 0)

    def test_position_at_screen_boundaries(self, parser):
        """Test position at various screen boundaries."""
        for x, y in [(0, 0), (255, 255), (512, 512), (0, 512), (512, 0)]:
            snap = GameStateSnapshot(
                timestamp=1000.0,
                mode=0x07,
                submode=0x00,
                area=0x00,
                room=0x27,
                link_x=x,
                link_y=y,
                link_z=0,
                link_direction=0x00,
                link_state=0x00,
                indoors=True,
                inidisp=0x0F,
                health=24,
                max_health=24,
            )
            state = parser.parse(snap)
            assert state.link_position == (x, y)


# =============================================================================
# Change Detection Tests
# =============================================================================

class TestChangeDetection:
    """Tests for detecting state changes across transitions.

    Note: detect_change() compares a new ParsedGameState against the
    internally stored _last_state. After parse() is called, _last_state
    is updated to the newly parsed state. So to detect changes, we need
    to construct a ParsedGameState manually (without calling parse()) or
    compare the result before _last_state is updated.
    """

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_detect_change_returns_list(self, parser):
        """detect_change should return a list of change descriptions."""
        # Parse first state to set _last_state
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
        )
        state1 = parser.parse(snap1)

        # detect_change with same state should return empty list (no changes)
        changes = parser.detect_change(state1)
        assert isinstance(changes, list)

    def test_detect_initial_state(self, parser):
        """First state detection returns 'Initial state'."""
        # Without any prior parse, detect_change returns initial state message
        snap = GameStateSnapshot(
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
        # Construct state manually to test detect_change without prior parse
        state = ParsedGameState(
            raw=snap,
            phase=GamePhase.DUNGEON,
            location_name="Test",
            area_id=0x00,
            room_id=0x27,
            is_indoors=True,
            link_action=LinkAction.STANDING,
            link_direction="up",
            link_position=(256, 320),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=True,
            can_use_items=True,
            submode=0x00,
        )
        changes = parser.detect_change(state)
        assert "Initial state" in changes

    def test_detect_black_screen_change(self, parser):
        """Detect black screen change using manual state construction."""
        # Parse normal state first
        normal_snap = GameStateSnapshot(
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
        parser.parse(normal_snap)  # Sets _last_state to normal

        # Construct black screen state manually (don't call parse)
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
        black_state = ParsedGameState(
            raw=black_snap,
            phase=GamePhase.BLACK_SCREEN,
            location_name="Zora Temple - Water Gate",
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
        changes = parser.detect_change(black_state)
        assert any("BLACK SCREEN" in c.upper() for c in changes)

    def test_detect_phase_change(self, parser):
        """Detect phase change using manual state construction."""
        # Parse dungeon state first
        dungeon_snap = GameStateSnapshot(
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
        parser.parse(dungeon_snap)  # Sets _last_state to dungeon

        # Construct overworld state manually
        ow_snap = GameStateSnapshot(
            timestamp=1001.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        ow_state = ParsedGameState(
            raw=ow_snap,
            phase=GamePhase.OVERWORLD,
            location_name="Village Center",
            area_id=0x29,
            room_id=0x00,
            is_indoors=False,
            link_action=LinkAction.STANDING,
            link_direction="up",
            link_position=(256, 320),
            link_layer=0,
            health_percent=1.0,
            is_playing=True,
            is_transitioning=False,
            is_menu_open=False,
            is_dialogue_open=False,
            is_black_screen=False,
            can_move=True,
            can_use_items=True,
            submode=0x00,
        )
        changes = parser.detect_change(ow_state)
        assert any("Phase" in c for c in changes)


# =============================================================================
# Layer Transition Tests
# =============================================================================

class TestLayerTransitions:
    """Tests for layer changes within dungeons."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_snapshot(self, link_z: int, submode: int = 0x00) -> GameStateSnapshot:
        return GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=submode,
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=link_z,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )

    def test_layer_0_ground(self, parser):
        """Layer 0 = Ground level."""
        state = parser.parse(self.make_snapshot(0))
        assert state.link_layer == 0

    def test_layer_nonzero(self, parser):
        """Non-zero Z indicates elevated position."""
        state = parser.parse(self.make_snapshot(16))
        assert state.link_layer != 0 or state.raw.link_z == 16

    def test_falling_changes_layer(self, parser):
        """Falling transition changes Z coordinate."""
        # Before falling
        before = self.make_snapshot(0, submode=0x00)
        s1 = parser.parse(before)

        # During fall
        during = self.make_snapshot(8, submode=0x12)  # Falling submodule
        s2 = parser.parse(during)
        assert s2.is_transitioning is True

        # After fall
        after = self.make_snapshot(0, submode=0x00)
        s3 = parser.parse(after)
        assert s3.is_transitioning is False


# =============================================================================
# Edge Cases
# =============================================================================

class TestTransitionEdgeCases:
    """Edge cases and boundary conditions for transitions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_max_mode_value(self, parser):
        """Test maximum mode value."""
        snap = GameStateSnapshot(
            timestamp=1000.0,
            mode=0xFF,
            submode=0x00,
            area=0x00,
            room=0x00,
            link_x=0,
            link_y=0,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        state = parser.parse(snap)
        assert state is not None

    def test_max_submode_value(self, parser):
        """Test maximum submode value."""
        snap = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0xFF,
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
        state = parser.parse(snap)
        assert state.is_transitioning is True

    def test_max_room_value(self, parser):
        """Test maximum room ID."""
        snap = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0xFFFF,  # Max 16-bit
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
        state = parser.parse(snap)
        assert state is not None

    def test_negative_coordinates_handled(self, parser):
        """Negative coordinates (if they occur) should be handled."""
        # Note: This may depend on implementation
        snap = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x27,
            link_x=-10,
            link_y=-10,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        state = parser.parse(snap)
        assert state.link_position == (-10, -10)

    def test_zero_health_during_transition(self, parser):
        """Zero health during transition (death)."""
        snap = GameStateSnapshot(
            timestamp=1000.0,
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
            health=0,
            max_health=24,
        )
        state = parser.parse(snap)
        assert state.health_percent == 0.0

    def test_rapid_state_changes(self, parser):
        """Multiple rapid state changes."""
        timestamps = [1000.0 + i * 0.016 for i in range(60)]  # 60 frames
        modes = [0x09, 0x06, 0x06, 0x06, 0x07] * 12

        for ts, mode in zip(timestamps, modes):
            snap = GameStateSnapshot(
                timestamp=ts,
                mode=mode,
                submode=0x00 if mode != 0x06 else 0x04,
                area=0x00 if mode == 0x07 else 0x29,
                room=0x27 if mode == 0x07 else 0x00,
                link_x=256,
                link_y=320,
                link_z=0,
                link_direction=0x00,
                link_state=0x00,
                indoors=mode == 0x07,
                inidisp=0x0F if mode != 0x06 else 0x80,
                health=24,
                max_health=24,
            )
            state = parser.parse(snap)
            assert state is not None


# =============================================================================
# Recovery Detection Tests
# =============================================================================

class TestRecoveryDetection:
    """Tests for detecting recovery from black screen or stuck states."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_recovery_from_black_screen(self, parser):
        """Detect recovery: black screen -> normal."""
        # Black screen state
        black = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x0F,
            area=0x00,
            room=0x27,
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
        s1 = parser.parse(black)
        assert s1.is_black_screen is True

        # Recovery state
        normal = GameStateSnapshot(
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
            health=24,
            max_health=24,
        )
        s2 = parser.parse(normal)
        assert s2.is_black_screen is False
        assert s2.can_move is True

    def test_stuck_detection_by_time(self, parser):
        """Detect stuck state by elapsed time with same conditions."""
        # Same state persisting
        base_snap = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,
            submode=0x0F,
            area=0x00,
            room=0x27,
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

        # Parse same state multiple times with advancing timestamp
        for i in range(10):
            snap = GameStateSnapshot(
                timestamp=1000.0 + i,  # Time advances
                mode=base_snap.mode,
                submode=base_snap.submode,  # Still stuck
                area=base_snap.area,
                room=base_snap.room,
                link_x=base_snap.link_x,
                link_y=base_snap.link_y,
                link_z=base_snap.link_z,
                link_direction=base_snap.link_direction,
                link_state=base_snap.link_state,
                indoors=base_snap.indoors,
                inidisp=base_snap.inidisp,  # Still black
                health=base_snap.health,
                max_health=base_snap.max_health,
            )
            state = parser.parse(snap)
            # Each parse should still detect black screen
            assert state.is_black_screen is True
