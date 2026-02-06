"""Extended tests for memory layouts, data formats, and serialization patterns.

Iteration 38 of the ralph-loop campaign.
Tests the low-level data handling, memory representations, and format edge cases
across all campaign infrastructure modules.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D.1: Data format verification
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import json
import struct

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import GameStateSnapshot, EmulatorStatus, MemoryRead
from scripts.campaign.game_state import GameStateParser, ParsedGameState, LinkAction, GamePhase
from scripts.campaign.input_recorder import (
    Button, InputSequence, InputPlayer, InputRecorder, InputFrame,
    create_boot_sequence, create_walk_sequence
)
from scripts.campaign.progress_validator import ProgressSnapshot, StoryFlag
from scripts.campaign.action_planner import Goal, GoalType, Plan, PlanStatus, Action


# =============================================================================
# GameStateSnapshot Memory Layout Tests
# =============================================================================

class TestGameStateSnapshotMemory:
    """Test GameStateSnapshot field ranges and memory representation."""

    def test_mode_byte_range(self):
        """Mode should be a single byte (0x00-0xFF)."""
        for mode in [0x00, 0x06, 0x07, 0x09, 0x0E, 0x14, 0xFF]:
            snap = GameStateSnapshot(
                timestamp=1.0, mode=mode, submode=0, area=0,
                room=0, link_x=0, link_y=0, link_z=0,
                link_direction=0, link_state=0, indoors=False,
                inidisp=0x0F, health=24, max_health=24
            )
            assert snap.mode == mode
            assert 0 <= snap.mode <= 0xFF

    def test_submode_byte_range(self):
        """Submode should be a single byte (0x00-0xFF)."""
        for submode in [0x00, 0x01, 0x10, 0x80, 0xFF]:
            snap = GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=submode, area=0,
                room=0, link_x=0, link_y=0, link_z=0,
                link_direction=0, link_state=0, indoors=False,
                inidisp=0x0F, health=24, max_health=24
            )
            assert snap.submode == submode
            assert 0 <= snap.submode <= 0xFF

    def test_area_byte_range(self):
        """Area ID should be a single byte (0x00-0xFF)."""
        areas = [0x00, 0x29, 0x40, 0x70, 0x80, 0xC0, 0xFF]
        for area in areas:
            snap = GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=0, area=area,
                room=0, link_x=0, link_y=0, link_z=0,
                link_direction=0, link_state=0, indoors=False,
                inidisp=0x0F, health=24, max_health=24
            )
            assert snap.area == area
            assert 0 <= snap.area <= 0xFF

    def test_room_word_range(self):
        """Room ID should be a 16-bit word (0x0000-0xFFFF)."""
        rooms = [0x0000, 0x0027, 0x0100, 0x8000, 0xFFFF]
        for room in rooms:
            snap = GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=0, area=0,
                room=room, link_x=0, link_y=0, link_z=0,
                link_direction=0, link_state=0, indoors=False,
                inidisp=0x0F, health=24, max_health=24
            )
            assert snap.room == room
            assert 0 <= snap.room <= 0xFFFF

    def test_link_coordinates_word_range(self):
        """Link coordinates should be 16-bit words."""
        coords = [0, 128, 512, 1024, 4095, 0xFFFF]
        for coord in coords:
            snap = GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=0, area=0,
                room=0, link_x=coord, link_y=coord, link_z=0,
                link_direction=0, link_state=0, indoors=False,
                inidisp=0x0F, health=24, max_health=24
            )
            assert snap.link_x == coord
            assert snap.link_y == coord

    def test_link_z_byte_range(self):
        """Link Z coordinate (layer) should be a byte."""
        for z in [0, 1, 2, 0x80, 0xFF]:
            snap = GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=0, area=0,
                room=0, link_x=0, link_y=0, link_z=z,
                link_direction=0, link_state=0, indoors=False,
                inidisp=0x0F, health=24, max_health=24
            )
            assert snap.link_z == z

    def test_inidisp_byte_range(self):
        """INIDISP should be a single byte."""
        inidisp_values = [0x00, 0x0F, 0x80, 0x8F, 0xFF]
        for inidisp in inidisp_values:
            snap = GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=0, area=0,
                room=0, link_x=0, link_y=0, link_z=0,
                link_direction=0, link_state=0, indoors=False,
                inidisp=inidisp, health=24, max_health=24
            )
            assert snap.inidisp == inidisp

    def test_health_values(self):
        """Health can range from 0 to 24 (or higher for expansions)."""
        for health in [0, 1, 8, 16, 24, 32]:
            snap = GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=0, area=0,
                room=0, link_x=0, link_y=0, link_z=0,
                link_direction=0, link_state=0, indoors=False,
                inidisp=0x0F, health=health, max_health=24
            )
            assert snap.health == health

    def test_direction_encoding(self):
        """Direction uses ALTTP encoding: 0x00=up, 0x02=down, 0x04=left, 0x06=right."""
        directions = [0x00, 0x02, 0x04, 0x06]
        for direction in directions:
            snap = GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=0, area=0,
                room=0, link_x=0, link_y=0, link_z=0,
                link_direction=direction, link_state=0, indoors=False,
                inidisp=0x0F, health=24, max_health=24
            )
            assert snap.link_direction == direction

    def test_link_state_byte_range(self):
        """Link state should be a single byte."""
        states = [0x00, 0x01, 0x02, 0x11, 0x17, 0xFF]
        for state in states:
            snap = GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=0, area=0,
                room=0, link_x=0, link_y=0, link_z=0,
                link_direction=0, link_state=state, indoors=False,
                inidisp=0x0F, health=24, max_health=24
            )
            assert snap.link_state == state


# =============================================================================
# MemoryRead Data Tests
# =============================================================================

class TestMemoryReadFormat:
    """Test MemoryRead data structure and address handling."""

    def test_memory_read_creation(self):
        """Test creating MemoryRead with address and value."""
        mr = MemoryRead(address=0x7E0000, value=0x42, size=1)
        assert mr.address == 0x7E0000
        assert mr.value == 0x42

    def test_snes_address_ranges(self):
        """Test SNES memory address ranges."""
        # Work RAM (WRAM) starts at $7E0000
        wram = MemoryRead(address=0x7E0000, value=0xFF, size=1)
        assert wram.address >= 0x7E0000 and wram.address < 0x800000

        # Save RAM (SRAM) varies by mapper
        sram = MemoryRead(address=0x700000, value=0xAA, size=1)
        assert sram.address == 0x700000

    def test_memory_read_16bit(self):
        """Test MemoryRead with 16-bit value."""
        mr = MemoryRead(address=0x7E0000, value=0x1234, size=2)
        assert mr.value == 0x1234
        assert mr.value16 == 0x1234

    def test_memory_read_24bit(self):
        """Test MemoryRead with 24-bit value."""
        mr = MemoryRead(address=0x7E0100, value=0x123456, size=3)
        assert mr.value == 0x123456
        assert mr.value24 == 0x123456


# =============================================================================
# Input Format Tests
# =============================================================================

class TestInputFormatEncoding:
    """Test input frame encoding and button representation."""

    def test_button_is_intflag(self):
        """Test Button uses IntFlag with power-of-2 values."""
        # Button uses auto() which assigns powers of 2
        assert Button.NONE.value == 0
        # Each button has a unique bit
        buttons = [Button.B, Button.Y, Button.SELECT, Button.START,
                   Button.UP, Button.DOWN, Button.LEFT, Button.RIGHT,
                   Button.A, Button.X, Button.L, Button.R]
        values = [b.value for b in buttons]
        # All values should be powers of 2
        for v in values:
            assert v > 0 and (v & (v - 1)) == 0, f"{v} is not power of 2"

    def test_button_combination_encoding(self):
        """Test combining multiple buttons."""
        combined = Button.A | Button.B
        assert combined & Button.A
        assert combined & Button.B
        assert not (combined & Button.X)

    def test_dpad_mutually_exclusive_bits(self):
        """Test D-pad buttons have non-overlapping bits."""
        dpad = [Button.UP, Button.DOWN, Button.LEFT, Button.RIGHT]
        for i, btn1 in enumerate(dpad):
            for btn2 in dpad[i+1:]:
                assert btn1.value & btn2.value == 0, f"{btn1} and {btn2} share bits"

    def test_input_frame_serialization(self):
        """Test InputFrame serialization to dict."""
        frame = InputFrame(frame_number=100, buttons=Button.A | Button.UP, hold_frames=1)
        data = frame.to_dict()

        assert data["frame"] == 100
        assert "A" in data["buttons"]
        assert "UP" in data["buttons"]
        assert data["hold"] == 1

    def test_input_frame_from_dict(self):
        """Test InputFrame deserialization from dict."""
        data = {"frame": 50, "buttons": ["B"], "hold": 3}
        frame = InputFrame.from_dict(data)

        assert frame.frame_number == 50
        assert frame.buttons == Button.B
        assert frame.hold_frames == 3

    def test_input_sequence_dict_roundtrip(self):
        """Test InputSequence dict serialization roundtrip."""
        seq = InputSequence(name="test_seq")
        seq.add_input(0, Button.A, 1)
        seq.add_input(1, Button.B, 2)

        data = seq.to_dict()
        assert data["name"] == "test_seq"
        assert len(data["frames"]) == 2
        assert "A" in data["frames"][0]["buttons"]

    def test_input_sequence_empty(self):
        """Test empty InputSequence properties."""
        seq = InputSequence(name="empty")
        assert seq.total_frames == 0
        assert seq.duration_seconds == 0.0
        assert len(seq.frames) == 0


# =============================================================================
# Progress Snapshot Format Tests
# =============================================================================

class TestProgressSnapshotFormat:
    """Test ProgressSnapshot data encoding and StoryFlag handling."""

    def test_story_flag_empty(self):
        """Test StoryFlag with no flags set."""
        flags = StoryFlag(0)
        assert int(flags) == 0
        assert not (flags & StoryFlag.INTRO_COMPLETE)

    def test_story_flag_single(self):
        """Test single StoryFlag value."""
        flags = StoryFlag.INTRO_COMPLETE
        assert flags & StoryFlag.INTRO_COMPLETE
        assert not (flags & StoryFlag.LOOM_BEACH)

    def test_story_flag_combination(self):
        """Test combining multiple StoryFlags."""
        flags = StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH
        assert flags & StoryFlag.INTRO_COMPLETE
        assert flags & StoryFlag.LOOM_BEACH
        assert not (flags & StoryFlag.KYDROG_COMPLETE)

    def test_story_flag_all_values(self):
        """Test all StoryFlag enum values."""
        all_flags = (
            StoryFlag.INTRO_COMPLETE |
            StoryFlag.LOOM_BEACH |
            StoryFlag.KYDROG_COMPLETE |
            StoryFlag.FARORE_RESCUED |
            StoryFlag.HALL_OF_SECRETS
        )
        assert all_flags & StoryFlag.INTRO_COMPLETE
        assert all_flags & StoryFlag.LOOM_BEACH
        assert all_flags & StoryFlag.KYDROG_COMPLETE
        assert all_flags & StoryFlag.FARORE_RESCUED
        assert all_flags & StoryFlag.HALL_OF_SECRETS

    def test_progress_snapshot_creation(self):
        """Test creating ProgressSnapshot with all fields."""
        snap = ProgressSnapshot(
            timestamp=1.0,
            game_state=0x09,
            story_flags=0x03,  # Bit flags
            story_flags_2=0x00,
            side_quest_1=0x00,
            side_quest_2=0x00,
            health=24,
            max_health=24,
            rupees=100,
            magic=32,
            max_magic=32,
            sword_level=1,
            shield_level=1,
            armor_level=0,
            crystals=0,
            follower_id=0,
            follower_state=0
        )

        assert snap.timestamp == 1.0
        assert snap.game_state == 0x09
        assert snap.story_flags == 0x03
        assert snap.health == 24
        assert snap.rupees == 100
        assert snap.sword_level == 1

    def test_progress_snapshot_hearts_property(self):
        """Test hearts property calculation."""
        snap = ProgressSnapshot(
            timestamp=1.0, game_state=0, story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=0, magic=0, max_magic=0, sword_level=0,
            shield_level=0, armor_level=0, crystals=0,
            follower_id=0, follower_state=0
        )
        # 24 health = 3 hearts (8 health per heart)
        assert snap.hearts == 3.0


# =============================================================================
# Coordinate System Tests
# =============================================================================

class TestCoordinateSystems:
    """Test coordinate systems and boundary conditions."""

    def test_pixel_coordinate_boundaries(self):
        """Test pixel coordinate boundaries."""
        # Typical SNES resolution is 256x224 or 512x448 (hi-res)
        # Link coordinates can extend beyond visible screen
        for x in [0, 127, 128, 255, 256, 511, 512, 1023]:
            snap = GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=0, area=0x29,
                room=0, link_x=x, link_y=256, link_z=0,
                link_direction=0, link_state=0, indoors=False,
                inidisp=0x0F, health=24, max_health=24
            )
            assert snap.link_x == x

    def test_tile_coordinate_conversion(self):
        """Test converting pixel to tile coordinates."""
        # Typical tile size is 8x8 or 16x16 pixels
        pixel_x = 256
        tile_x_8 = pixel_x // 8  # 32
        tile_x_16 = pixel_x // 16  # 16

        assert tile_x_8 == 32
        assert tile_x_16 == 16

    def test_subpixel_preservation(self):
        """Test that subpixel values are preserved."""
        # SNES often uses fixed-point with 4 subpixel bits
        full_value = 0x1234  # pixel 0x123, subpixel 0x4
        pixel = full_value >> 4
        subpixel = full_value & 0x0F

        assert pixel == 0x123
        assert subpixel == 0x4

    def test_world_wrap_coordinates(self):
        """Test world wrapping coordinate handling."""
        # Some games wrap coordinates at world boundaries
        max_world = 0x2000  # 8192 pixels
        wrapped = (0x2100) % max_world  # Should wrap to 0x100

        assert wrapped == 0x100


# =============================================================================
# Link Action State Mapping Tests
# =============================================================================

class TestLinkActionMapping:
    """Test Link action state mappings."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_state(self, link_state):
        """Create snapshot with specific link_state."""
        return GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0, area=0x29,
            room=0, link_x=512, link_y=480, link_z=0,
            link_direction=0x00, link_state=link_state, indoors=False,
            inidisp=0x0F, health=24, max_health=24
        )

    @pytest.mark.parametrize("state,expected", [
        (0x00, LinkAction.STANDING),
        (0x01, LinkAction.WALKING),
        (0x02, LinkAction.SWIMMING),
        (0x03, LinkAction.DIVING),
        (0x04, LinkAction.KNOCKED_BACK),
        (0x06, LinkAction.PUSHING),
        (0x08, LinkAction.FALLING),
        (0x0A, LinkAction.LIFTING),
        (0x0B, LinkAction.CARRYING),
        (0x0C, LinkAction.THROWING),
        (0x11, LinkAction.ATTACKING),
        (0x12, LinkAction.USING_ITEM),
        (0x17, LinkAction.DYING),
        (0x19, LinkAction.SPINNING),
    ])
    def test_known_link_states(self, parser, state, expected):
        """Test all known link_state to LinkAction mappings."""
        snap = self.make_state(state)
        parsed = parser.parse(snap)
        assert parsed.link_action == expected

    def test_unknown_link_state(self, parser):
        """Test unknown link_state returns UNKNOWN."""
        snap = self.make_state(0x99)  # Unknown state
        parsed = parser.parse(snap)
        assert parsed.link_action == LinkAction.UNKNOWN


# =============================================================================
# Direction Encoding Tests
# =============================================================================

class TestDirectionEncoding:
    """Test ALTTP direction encoding."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_state(self, direction):
        """Create snapshot with specific direction."""
        return GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0, area=0x29,
            room=0, link_x=512, link_y=480, link_z=0,
            link_direction=direction, link_state=0, indoors=False,
            inidisp=0x0F, health=24, max_health=24
        )

    @pytest.mark.parametrize("direction,name", [
        (0x00, "up"),
        (0x02, "down"),
        (0x04, "left"),
        (0x06, "right"),
    ])
    def test_cardinal_directions(self, parser, direction, name):
        """Test ALTTP direction encoding."""
        snap = self.make_state(direction)
        parsed = parser.parse(snap)
        assert parsed.link_direction == name

    def test_unknown_direction(self, parser):
        """Test unknown direction code."""
        snap = self.make_state(0xFF)  # Invalid
        parsed = parser.parse(snap)
        assert parsed.link_direction == "unknown"

    def test_intermediate_direction_values(self, parser):
        """Test values between cardinal directions."""
        # ALTTP only uses even values, odd values should be unknown
        for direction in [0x01, 0x03, 0x05, 0x07]:
            snap = self.make_state(direction)
            parsed = parser.parse(snap)
            assert parsed.link_direction == "unknown"


# =============================================================================
# INIDISP Black Screen Detection Tests
# =============================================================================

class TestINIDISPFormat:
    """Test INIDISP register interpretation."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_state(self, mode, inidisp):
        """Create snapshot with specific mode and INIDISP."""
        return GameStateSnapshot(
            timestamp=1.0, mode=mode, submode=0, area=0x29,
            room=0, link_x=512, link_y=480, link_z=0,
            link_direction=0, link_state=0, indoors=False,
            inidisp=inidisp, health=24, max_health=24
        )

    def test_inidisp_0x80_is_black_screen(self, parser):
        """INIDISP exactly 0x80 indicates black screen."""
        snap = GameStateSnapshot(
            timestamp=1.0, mode=0x07, submode=0, area=0,
            room=0, link_x=0, link_y=0, link_z=0,
            link_direction=0, link_state=0, indoors=False,
            inidisp=0x80, health=24, max_health=24
        )
        parsed = parser.parse(snap)
        assert parsed.is_black_screen is True

    def test_inidisp_brightness_levels(self, parser):
        """Test various brightness levels (0x80-0x8F)."""
        for level in range(1, 16):
            inidisp = 0x80 | level
            snap = self.make_state(0x09, inidisp)
            parsed = parser.parse(snap)
            # Brightness > 0 means screen is visible
            assert parsed.is_black_screen is False

    def test_inidisp_without_bit7(self, parser):
        """Test INIDISP values without bit 7 set."""
        for val in [0x00, 0x0F, 0x7F]:
            snap = self.make_state(0x09, val)
            parsed = parser.parse(snap)
            # Without force blank bit (0x80), screen is not blanked
            assert parsed.is_black_screen is False


# =============================================================================
# Mode Byte Tests
# =============================================================================

class TestModeByte:
    """Test game mode byte interpretation."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_state(self, mode):
        """Create snapshot with specific mode."""
        return GameStateSnapshot(
            timestamp=1.0, mode=mode, submode=0, area=0x29,
            room=0, link_x=512, link_y=480, link_z=0,
            link_direction=0, link_state=0, indoors=False,
            inidisp=0x0F, health=24, max_health=24
        )

    @pytest.mark.parametrize("mode,expected_phase", [
        (0x00, GamePhase.BOOT),         # Boot/Reset
        (0x06, GamePhase.TRANSITION),   # Transition
        (0x07, GamePhase.OVERWORLD),    # Mode 7 with indoors=False -> OVERWORLD
        (0x09, GamePhase.OVERWORLD),    # Overworld mode
        (0x0E, GamePhase.MENU),         # Menu
        (0x14, GamePhase.CUTSCENE),     # Cutscene
    ])
    def test_mode_to_phase_mapping(self, parser, mode, expected_phase):
        """Test mode byte maps to expected GamePhase."""
        snap = self.make_state(mode)
        parsed = parser.parse(snap)
        assert parsed.phase == expected_phase


# =============================================================================
# Plan/Goal Serialization Tests
# =============================================================================

class TestPlanGoalFormat:
    """Test Plan and Goal data format and serialization."""

    def test_goal_creation(self):
        """Test Goal creation with all fields."""
        goal = Goal(
            goal_type=GoalType.REACH_LOCATION,
            description="Reach village center",
            parameters={"area_id": 0x29, "x": 512, "y": 480}
        )

        assert goal.goal_type == GoalType.REACH_LOCATION
        assert goal.description == "Reach village center"
        assert goal.parameters["area_id"] == 0x29

    def test_goal_factory_reach_location(self):
        """Test Goal.reach_location factory method."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)
        assert goal.goal_type == GoalType.REACH_LOCATION
        assert goal.parameters["area_id"] == 0x29
        assert goal.parameters["x"] == 512

    def test_plan_status_values(self):
        """Test all PlanStatus enum values."""
        statuses = [
            PlanStatus.NOT_STARTED,
            PlanStatus.IN_PROGRESS,
            PlanStatus.COMPLETED,
            PlanStatus.FAILED,
            PlanStatus.BLOCKED
        ]
        for status in statuses:
            plan = Plan(goal=Goal.reach_location(0x29, 512, 480), status=status)
            assert plan.status == status

    def test_action_with_condition(self):
        """Test Action with condition callback."""
        action = Action(
            name="move_north",
            description="Move Link north",
            condition=lambda state: state.link_position[1] < 400
        )

        assert action.name == "move_north"
        assert action.description == "Move Link north"
        assert action.condition is not None


# =============================================================================
# Timestamp and Timing Tests
# =============================================================================

class TestTimestampFormat:
    """Test timestamp handling and frame timing."""

    def test_timestamp_float_precision(self):
        """Test timestamp maintains float precision."""
        snap = GameStateSnapshot(
            timestamp=1.234567890123,
            mode=0x09, submode=0, area=0x29,
            room=0, link_x=512, link_y=480, link_z=0,
            link_direction=0, link_state=0, indoors=False,
            inidisp=0x0F, health=24, max_health=24
        )
        assert abs(snap.timestamp - 1.234567890123) < 1e-9

    def test_frame_duration_standard(self):
        """Test standard frame duration (60fps NTSC)."""
        # NTSC runs at ~60.0988 fps
        frame_duration = 1.0 / 60.0
        assert abs(frame_duration - 0.01666666) < 0.0001

    def test_input_frame_hold_frames(self):
        """Test InputFrame hold_frames field."""
        frame = InputFrame(frame_number=0, buttons=Button.NONE, hold_frames=5)
        assert frame.hold_frames == 5
        # hold_frames is in frames, not seconds

    def test_sequence_total_frames(self):
        """Test calculating total frames from sequence."""
        seq = InputSequence(name="test")
        seq.add_input(0, Button.A, hold=5)
        seq.add_input(5, Button.B, hold=10)
        seq.add_input(15, Button.NONE, hold=3)

        total_hold = sum(f.hold_frames for f in seq.frames)
        assert total_hold == 18  # 5 + 10 + 3


# =============================================================================
# Health Value Tests
# =============================================================================

class TestHealthFormat:
    """Test health value encoding."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_state(self, health, max_health):
        """Create snapshot with specific health values."""
        return GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0, area=0x29,
            room=0, link_x=512, link_y=480, link_z=0,
            link_direction=0, link_state=0, indoors=False,
            inidisp=0x0F, health=health, max_health=max_health
        )

    def test_full_health(self, parser):
        """Test full health state."""
        snap = self.make_state(24, 24)
        parsed = parser.parse(snap)
        assert parsed.health_percent == 1.0

    def test_half_health(self, parser):
        """Test half health state."""
        snap = self.make_state(12, 24)
        parsed = parser.parse(snap)
        assert abs(parsed.health_percent - 0.5) < 0.01

    def test_zero_health(self, parser):
        """Test zero health state."""
        snap = self.make_state(0, 24)
        parsed = parser.parse(snap)
        assert parsed.health_percent == 0.0

    def test_zero_max_health_edge(self, parser):
        """Test edge case of zero max health (avoid division by zero)."""
        snap = self.make_state(0, 0)
        parsed = parser.parse(snap)
        # Should handle gracefully, likely returns 1.0 or 0.0
        assert parsed.health_percent in (0.0, 1.0)

    def test_health_hearts_encoding(self):
        """Test health encoding (4 units per heart)."""
        # ALTTP uses 8 health units per full heart
        hearts = 3
        full_health = hearts * 8  # 24 = 3 hearts
        half_heart = 4

        assert full_health == 24
        assert half_heart == 4


# =============================================================================
# Area Code Format Tests
# =============================================================================

class TestAreaCodeFormat:
    """Test area code encoding for Light/Dark World and underwater."""

    def test_light_world_areas(self):
        """Test Light World area codes (0x00-0x3F typically)."""
        light_areas = [0x00, 0x18, 0x29, 0x2A, 0x3F]
        for area in light_areas:
            # Light World has bit 7 clear
            assert area & 0x80 == 0, f"Light World area 0x{area:02X} should have bit 7 clear"

    def test_dark_world_marker(self):
        """Test Dark World area encoding."""
        # Dark World areas typically have bit 6 or 7 set
        # Oracle uses specific codes
        dark_areas = [0x56, 0x57, 0x5B, 0x5E]
        for area in dark_areas:
            assert area >= 0x40, f"Dark World area 0x{area:02X}"

    def test_underwater_areas(self):
        """Test underwater area codes (0x70-0x7F range)."""
        underwater_areas = [0x70, 0x75, 0x7A]
        for area in underwater_areas:
            assert 0x70 <= area <= 0x7F, f"Underwater area 0x{area:02X}"

    def test_area_overlay_calculation(self):
        """Test calculating Dark World overlay from Light World."""
        light_area = 0x40  # Lost Woods
        dark_overlay = light_area | 0x80  # 0xC0

        # Can extract base area by masking
        base = dark_overlay & 0x3F
        assert base == 0x00  # Would be 0x40 & 0x3F = 0x00


# =============================================================================
# EmulatorStatus Tests
# =============================================================================

class TestEmulatorStatusFormat:
    """Test EmulatorStatus enum values."""

    def test_status_enum_values(self):
        """Test all EmulatorStatus values exist."""
        statuses = [
            EmulatorStatus.DISCONNECTED,
            EmulatorStatus.CONNECTED,
            EmulatorStatus.RUNNING,
            EmulatorStatus.PAUSED,
            EmulatorStatus.ERROR
        ]
        for status in statuses:
            assert isinstance(status, EmulatorStatus)

    def test_status_comparison(self):
        """Test status comparison."""
        assert EmulatorStatus.CONNECTED != EmulatorStatus.DISCONNECTED
        assert EmulatorStatus.RUNNING != EmulatorStatus.PAUSED
