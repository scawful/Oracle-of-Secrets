"""Tests for boundary conditions and edge values.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D: Robust handling of edge cases

These tests verify behavior at boundary conditions:
- Maximum and minimum values
- Empty vs populated collections
- Zero/null conditions
- Overflow potential
"""

import pytest
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime
import tempfile

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import GameStateSnapshot, EmulatorStatus
from scripts.campaign.game_state import GamePhase, GameStateParser
from scripts.campaign.input_recorder import (
    Button, InputSequence, InputFrame, InputRecorder,
    create_walk_sequence
)
from scripts.campaign.action_planner import Goal, GoalType, Plan, PlanStatus, Action
from scripts.campaign.campaign_orchestrator import (
    CampaignOrchestrator, CampaignPhase, CampaignProgress,
    CampaignMilestone, MilestoneStatus
)
from scripts.campaign.visual_verifier import VerificationResult, Screenshot


class TestCoordinateBoundaries:
    """Test coordinate value boundaries."""

    def test_minimum_coordinates(self):
        """Test minimum coordinate values (0, 0)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x00, room=0x00,
            link_x=0, link_y=0, link_z=0,
            link_direction=0, link_state=0,
            indoors=False, inidisp=0x0F,
            health=1, max_health=24
        )
        assert state.link_x == 0
        assert state.link_y == 0
        assert state.position == (0, 0)

    def test_maximum_coordinates(self):
        """Test maximum reasonable coordinate values."""
        # SNES screen is 256x224, but overworld is larger
        max_x = 4096  # 16 tiles * 256 pixels
        max_y = 4096

        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x00, room=0x00,
            link_x=max_x, link_y=max_y, link_z=0,
            link_direction=0, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.link_x == max_x
        assert state.link_y == max_y

    def test_negative_z_coordinate(self):
        """Test negative Z coordinate (falling)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=-16,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.link_z == -16

    def test_large_positive_z_coordinate(self):
        """Test large positive Z coordinate (jumping)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=128,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.link_z == 128


class TestHealthBoundaries:
    """Test health value boundaries."""

    def test_zero_health(self):
        """Test zero health (dead)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=0, max_health=24
        )
        assert state.health == 0

    def test_max_health_reached(self):
        """Test health equals max health."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.health == state.max_health

    def test_one_health(self):
        """Test minimum non-zero health."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=1, max_health=24
        )
        assert state.health == 1

    def test_maximum_possible_health(self):
        """Test maximum possible health (20 hearts = 160 quarter hearts)."""
        max_hearts = 160  # 20 hearts * 8 (full hearts in quarter-heart units)

        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=max_hearts, max_health=max_hearts
        )
        assert state.health == max_hearts


class TestAreaAndRoomBoundaries:
    """Test area and room ID boundaries."""

    def test_minimum_area_id(self):
        """Test minimum area ID (0x00)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x00, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.area == 0x00

    def test_maximum_area_id(self):
        """Test maximum area ID (0xFF)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0xFF, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.area == 0xFF

    def test_maximum_room_id(self):
        """Test maximum room ID (0xFF)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0xFF,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.room == 0xFF


class TestModeAndSubmodeBoundaries:
    """Test game mode and submode boundaries."""

    def test_minimum_mode(self):
        """Test minimum mode value (0x00)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x00, submode=0x00,
            area=0x00, room=0x00,
            link_x=0, link_y=0, link_z=0,
            link_direction=0, link_state=0,
            indoors=False, inidisp=0x00,
            health=0, max_health=0
        )
        assert state.mode == 0x00

    def test_maximum_mode(self):
        """Test maximum mode value (0xFF)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0xFF, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.mode == 0xFF

    def test_maximum_submode(self):
        """Test maximum submode value (0xFF)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0xFF,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.submode == 0xFF


class TestInputSequenceBoundaries:
    """Test input sequence boundary conditions."""

    def test_empty_sequence(self):
        """Test empty sequence has zero frames."""
        seq = InputSequence(name="empty")
        assert seq.total_frames == 0
        assert len(seq.frames) == 0

    def test_single_frame_sequence(self):
        """Test single frame sequence."""
        seq = InputSequence(name="single")
        seq.add_input(0, Button.A, hold=1)

        assert seq.total_frames == 1
        assert len(seq.frames) == 1

    def test_maximum_button_combination(self):
        """Test all buttons pressed simultaneously."""
        all_buttons = (
            Button.A | Button.B | Button.X | Button.Y |
            Button.L | Button.R | Button.START | Button.SELECT |
            Button.UP | Button.DOWN | Button.LEFT | Button.RIGHT
        )

        frame = InputFrame(frame_number=0, buttons=all_buttons, hold_frames=1)
        assert frame.buttons == all_buttons

    def test_zero_button_frame(self):
        """Test frame with no buttons pressed."""
        frame = InputFrame(frame_number=0, buttons=Button(0), hold_frames=1)
        assert frame.buttons == Button(0)

    def test_large_frame_number(self):
        """Test large frame numbers (1 hour at 60fps)."""
        large_frame = 216000  # 1 hour

        seq = InputSequence(name="large")
        seq.add_input(large_frame, Button.A, hold=1)

        assert seq.total_frames == large_frame + 1

    def test_large_hold_duration(self):
        """Test large hold duration."""
        seq = InputSequence(name="long_hold")
        seq.add_input(0, Button.A, hold=36000)  # 10 minutes

        assert seq.total_frames == 36000

    def test_walk_zero_tiles(self):
        """Test walk sequence with zero tiles."""
        seq = create_walk_sequence("UP", tiles=0)
        assert seq.total_frames == 0

    def test_walk_one_tile(self):
        """Test walk sequence with one tile."""
        seq = create_walk_sequence("UP", tiles=1)
        assert seq.total_frames > 0


class TestGoalBoundaries:
    """Test goal parameter boundaries."""

    def test_goal_zero_tolerance(self):
        """Test goal with zero tolerance (exact position)."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480, tolerance=0)
        assert goal.parameters["tolerance"] == 0

    def test_goal_large_tolerance(self):
        """Test goal with large tolerance."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480, tolerance=1000)
        assert goal.parameters["tolerance"] == 1000

    def test_goal_zero_coordinates(self):
        """Test goal at origin."""
        goal = Goal.reach_location(area_id=0x00, x=0, y=0)
        assert goal.parameters["x"] == 0
        assert goal.parameters["y"] == 0


class TestProgressBoundaries:
    """Test campaign progress boundaries."""

    def test_empty_progress(self):
        """Test progress with no milestones."""
        progress = CampaignProgress()
        progress.milestones.clear()

        assert len(progress.milestones) == 0
        assert progress.iterations_completed == 0

    def test_single_milestone_progress(self):
        """Test progress with single milestone."""
        progress = CampaignProgress()
        progress.milestones.clear()

        progress.add_milestone(CampaignMilestone(
            id="only_one",
            description="The only milestone",
            goal="T.1"
        ))

        assert len(progress.milestones) == 1

    def test_many_milestones(self):
        """Test progress with many milestones."""
        progress = CampaignProgress()
        progress.milestones.clear()

        for i in range(100):
            progress.add_milestone(CampaignMilestone(
                id=f"milestone_{i}",
                description=f"Milestone {i}",
                goal="T.1"
            ))

        assert len(progress.milestones) == 100

    def test_zero_frames_played(self):
        """Test initial zero frames."""
        progress = CampaignProgress()
        assert progress.total_frames_played == 0

    def test_large_frames_played(self):
        """Test large frame count."""
        progress = CampaignProgress()
        progress.total_frames_played = 1_000_000_000  # Very long campaign

        assert progress.total_frames_played == 1_000_000_000


class TestTimestampBoundaries:
    """Test timestamp value boundaries."""

    def test_zero_timestamp(self):
        """Test zero timestamp."""
        state = GameStateSnapshot(
            timestamp=0.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.timestamp == 0.0

    def test_large_timestamp(self):
        """Test large timestamp (days of gameplay)."""
        days = 7 * 24 * 60 * 60  # 7 days in seconds

        state = GameStateSnapshot(
            timestamp=float(days), mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.timestamp == float(days)

    def test_fractional_timestamp(self):
        """Test fractional timestamp (sub-frame precision)."""
        state = GameStateSnapshot(
            timestamp=1.000001, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert abs(state.timestamp - 1.000001) < 1e-9


class TestDirectionBoundaries:
    """Test direction value boundaries."""

    def test_all_directions(self):
        """Test all four direction values."""
        directions = [0, 1, 2, 3]  # UP, DOWN, LEFT, RIGHT typically

        for direction in directions:
            state = GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=0x00,
                area=0x29, room=0x00,
                link_x=512, link_y=480, link_z=0,
                link_direction=direction, link_state=0,
                indoors=False, inidisp=0x0F,
                health=24, max_health=24
            )
            assert state.link_direction == direction

    def test_maximum_direction(self):
        """Test maximum direction value (for extended states)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=255, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.link_direction == 255


class TestINIDISPBoundaries:
    """Test INIDISP register boundaries."""

    def test_zero_inidisp(self):
        """Test INIDISP = 0 (screen off)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x00,
            health=24, max_health=24
        )
        assert state.inidisp == 0x00

    def test_full_brightness_inidisp(self):
        """Test INIDISP = 0x0F (full brightness)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        assert state.inidisp == 0x0F

    def test_force_blank_inidisp(self):
        """Test INIDISP = 0x80 (force blank)."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x80,
            health=24, max_health=24
        )
        assert state.inidisp == 0x80

    def test_maximum_inidisp(self):
        """Test INIDISP = 0xFF."""
        state = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0xFF,
            health=24, max_health=24
        )
        assert state.inidisp == 0xFF


class TestMilestoneNoteBoundaries:
    """Test milestone note boundaries."""

    def test_empty_note(self):
        """Test milestone with empty note."""
        milestone = CampaignMilestone(
            id="test",
            description="Test milestone",
            goal="T.1"
        )
        milestone.notes.append("")

        assert "" in milestone.notes

    def test_long_note(self):
        """Test milestone with very long note."""
        milestone = CampaignMilestone(
            id="test",
            description="Test milestone",
            goal="T.1"
        )
        long_note = "A" * 10000
        milestone.notes.append(long_note)

        assert long_note in milestone.notes

    def test_many_notes(self):
        """Test milestone with many notes."""
        milestone = CampaignMilestone(
            id="test",
            description="Test milestone",
            goal="T.1"
        )
        for i in range(1000):
            milestone.notes.append(f"Note {i}")

        assert len(milestone.notes) == 1000


class TestPlanBoundaries:
    """Test plan action boundaries."""

    def test_empty_plan(self):
        """Test plan with no actions."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)
        plan = Plan(goal=goal)

        assert len(plan.actions) == 0

    def test_plan_with_many_actions(self):
        """Test plan with many actions."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)
        plan = Plan(goal=goal)

        for i in range(100):
            plan.actions.append(Action(
                name=f"walk_{i}",
                description=f"Walk step {i}"
            ))

        assert len(plan.actions) == 100
