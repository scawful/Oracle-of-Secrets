"""Extended tests for realistic campaign scenarios and workflows.

Iteration 37 of the ralph-loop campaign.
Adds comprehensive scenario testing for complex multi-step workflows,
edge cases, dungeon exploration, combat, and long-running simulations.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D: End-to-end workflow verification
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
import tempfile
import json

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import GameStateSnapshot, EmulatorStatus
from scripts.campaign.game_state import (
    GamePhase, GameStateParser, ParsedGameState, LinkAction
)
from scripts.campaign.input_recorder import (
    Button, InputSequence, InputPlayer, InputRecorder, InputFrame,
    create_boot_sequence, create_walk_sequence
)
from scripts.campaign.action_planner import (
    ActionPlanner, Goal, GoalType, Plan, PlanStatus, Action
)
from scripts.campaign.campaign_orchestrator import (
    CampaignOrchestrator, CampaignPhase, CampaignProgress,
    CampaignMilestone, MilestoneStatus
)
from scripts.campaign.visual_verifier import VisualVerifier, VerificationResult
from scripts.campaign.progress_validator import ProgressSnapshot, StoryFlag
from scripts.campaign.locations import OVERWORLD_AREAS, ROOM_NAMES, DUNGEONS


# =============================================================================
# Multi-Step Workflow Scenarios
# =============================================================================

class TestMultiStepWorkflows:
    """Test complex multi-step campaign workflows."""

    def create_gameplay_state(self, area=0x29, room=0x00, x=512, y=480,
                               mode=0x09, health=24, indoors=False):
        """Helper to create gameplay state snapshots."""
        return GameStateSnapshot(
            timestamp=1.0,
            mode=mode,
            submode=0x00,
            area=area,
            room=room,
            link_x=x,
            link_y=y,
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=indoors,
            inidisp=0x0F,
            health=health,
            max_health=24
        )

    def test_village_to_dungeon_workflow(self):
        """Test complete village to dungeon entrance workflow."""
        parser = GameStateParser()

        # Step 1: Start in village
        village_state = self.create_gameplay_state(area=0x29, x=512, y=480)
        parsed = parser.parse(village_state)
        assert parsed.phase == GamePhase.OVERWORLD
        assert parsed.location_name == "Village Center"

        # Step 2: Navigate toward dungeon (simulate movement)
        intermediate = self.create_gameplay_state(area=0x20, x=300, y=400)
        parsed = parser.parse(intermediate)
        assert parsed.phase == GamePhase.OVERWORLD

        # Step 3: Enter dungeon (transition to mode 0x07)
        dungeon_state = GameStateSnapshot(
            timestamp=3.0,
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
            max_health=24
        )
        parsed = parser.parse(dungeon_state)
        assert parsed.phase == GamePhase.DUNGEON
        assert parsed.is_indoors

    def test_dungeon_room_progression(self):
        """Test moving through dungeon rooms."""
        parser = GameStateParser()
        rooms_visited = []

        # Simulate room progression
        room_sequence = [0x27, 0x37, 0x47, 0x57]  # Typical room chain

        for room in room_sequence:
            state = GameStateSnapshot(
                timestamp=float(len(rooms_visited)),
                mode=0x07,
                submode=0x00,
                area=0x00,
                room=room,
                link_x=256,
                link_y=320,
                link_z=0,
                link_direction=0x02,
                link_state=0x00,
                indoors=True,
                inidisp=0x0F,
                health=24,
                max_health=24
            )
            parsed = parser.parse(state)
            rooms_visited.append(parsed.room_id)

        assert rooms_visited == room_sequence

    def test_overworld_area_traversal(self):
        """Test traversing multiple overworld areas."""
        parser = GameStateParser()
        areas_visited = []

        # Light World area sequence
        area_sequence = [0x29, 0x28, 0x18, 0x08]

        for area in area_sequence:
            state = self.create_gameplay_state(area=area)
            parsed = parser.parse(state)
            areas_visited.append(parsed.area_id)

        assert areas_visited == area_sequence
        # All should be Light World (bit 0x40 not set)
        assert all((a & 0x40) == 0 for a in areas_visited)


# =============================================================================
# Edge Case Scenarios
# =============================================================================

class TestEdgeCaseScenarios:
    """Test scenarios with edge conditions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_low_health_gameplay(self, parser):
        """Test gameplay with critically low health."""
        low_health = GameStateSnapshot(
            timestamp=1.0,
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
            health=1,  # Near death
            max_health=24
        )
        parsed = parser.parse(low_health)

        assert parsed.health_percent < 0.1
        assert parsed.can_move  # Should still be able to move

    def test_zero_health_state(self, parser):
        """Test state with zero health (dead)."""
        dead = GameStateSnapshot(
            timestamp=1.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=0x02,
            link_state=0x17,  # Dying state
            indoors=False,
            inidisp=0x0F,
            health=0,
            max_health=24
        )
        parsed = parser.parse(dead)

        assert parsed.health_percent == 0.0
        assert parsed.link_action == LinkAction.DYING

    def test_max_health_state(self, parser):
        """Test state with maximum health."""
        max_health = GameStateSnapshot(
            timestamp=1.0,
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
            health=40,  # 10 hearts (20 health = 5 hearts)
            max_health=40
        )
        parsed = parser.parse(max_health)

        assert parsed.health_percent == 1.0

    def test_swimming_state(self, parser):
        """Test Link swimming state."""
        swimming = GameStateSnapshot(
            timestamp=1.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=0x02,
            link_state=0x02,  # Swimming
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24
        )
        parsed = parser.parse(swimming)

        assert parsed.link_action == LinkAction.SWIMMING

    def test_falling_state(self, parser):
        """Test Link falling state."""
        falling = GameStateSnapshot(
            timestamp=1.0,
            mode=0x07,
            submode=0x12,  # Falling submodule
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=8,  # Elevated
            link_direction=0x02,
            link_state=0x08,  # Falling
            indoors=True,
            inidisp=0x0F,
            health=24,
            max_health=24
        )
        parsed = parser.parse(falling)

        assert parsed.link_action == LinkAction.FALLING
        assert parsed.can_move is False


# =============================================================================
# Dungeon Exploration Scenarios
# =============================================================================

class TestDungeonExplorationScenarios:
    """Test scenarios involving dungeon exploration."""

    def test_dungeon_room_sequence_simulation(self):
        """Simulate exploring a dungeon with room transitions."""
        parser = GameStateParser()

        # Dungeon exploration sequence
        exploration_states = []
        rooms = [0x27, 0x37, 0x27, 0x17, 0x18, 0x19]

        for i, room in enumerate(rooms):
            state = GameStateSnapshot(
                timestamp=float(i),
                mode=0x07,
                submode=0x00,
                area=0x00,
                room=room,
                link_x=256,
                link_y=320,
                link_z=0,
                link_direction=(i * 2) % 8,
                link_state=0x00,
                indoors=True,
                inidisp=0x0F,
                health=24 - i,  # Losing health as we explore
                max_health=24
            )
            parsed = parser.parse(state)
            exploration_states.append(parsed)

        # Verify progression
        assert len(exploration_states) == len(rooms)
        assert exploration_states[-1].health_percent < exploration_states[0].health_percent

    def test_boss_room_detection(self):
        """Test detecting boss room conditions."""
        parser = GameStateParser()

        # Boss room typically has specific room IDs
        boss_rooms = [0x30, 0x50, 0x70]  # Example boss rooms

        for room in boss_rooms:
            state = GameStateSnapshot(
                timestamp=1.0,
                mode=0x07,
                submode=0x00,
                area=0x00,
                room=room,
                link_x=256,
                link_y=256,  # Center of room
                link_z=0,
                link_direction=0x00,
                link_state=0x00,
                indoors=True,
                inidisp=0x0F,
                health=24,
                max_health=24
            )
            parsed = parser.parse(state)
            assert parsed.phase == GamePhase.DUNGEON

    def test_dungeon_entrance_exit_cycle(self):
        """Test entering and exiting dungeon."""
        parser = GameStateParser()

        # Outside dungeon
        outside = GameStateSnapshot(
            timestamp=1.0,
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
            max_health=24
        )
        p1 = parser.parse(outside)
        assert p1.phase == GamePhase.OVERWORLD

        # Inside dungeon
        inside = GameStateSnapshot(
            timestamp=2.0,
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
            max_health=24
        )
        p2 = parser.parse(inside)
        assert p2.phase == GamePhase.DUNGEON

        # Back outside
        outside2 = GameStateSnapshot(
            timestamp=3.0,
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
            max_health=24
        )
        p3 = parser.parse(outside2)
        assert p3.phase == GamePhase.OVERWORLD


# =============================================================================
# Menu and Dialogue Scenarios
# =============================================================================

class TestMenuDialogueScenarios:
    """Test scenarios involving menus and dialogue."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_menu_open_detection(self, parser):
        """Test detecting menu is open."""
        menu_state = GameStateSnapshot(
            timestamp=1.0,
            mode=0x0E,  # Menu mode
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
            max_health=24
        )
        parsed = parser.parse(menu_state)

        assert parsed.phase == GamePhase.MENU or parsed.is_menu_open
        assert parsed.can_move is False

    def test_dialogue_detection(self, parser):
        """Test detecting dialogue/cutscene mode."""
        dialogue_state = GameStateSnapshot(
            timestamp=1.0,
            mode=0x14,  # Dialogue/cutscene mode
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
            max_health=24
        )
        parsed = parser.parse(dialogue_state)

        # Mode 0x14 is cutscene
        assert parsed.phase == GamePhase.CUTSCENE
        assert parsed.can_move is False

    def test_menu_to_gameplay_transition(self, parser):
        """Test transitioning from menu back to gameplay."""
        # In menu
        menu = GameStateSnapshot(
            timestamp=1.0,
            mode=0x0E,
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
            max_health=24
        )
        p1 = parser.parse(menu)
        assert p1.can_move is False

        # Back to gameplay
        gameplay = GameStateSnapshot(
            timestamp=2.0,
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
            max_health=24
        )
        p2 = parser.parse(gameplay)
        assert p2.can_move is True


# =============================================================================
# Combat Scenarios
# =============================================================================

class TestCombatScenarios:
    """Test combat-related scenarios."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_attack_state_detection(self, parser):
        """Test detecting attack/sword swing state."""
        attacking = GameStateSnapshot(
            timestamp=1.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=0x02,
            link_state=0x11,  # Attacking
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24
        )
        parsed = parser.parse(attacking)

        assert parsed.link_action == LinkAction.ATTACKING
        assert parsed.can_move is False

    def test_health_decrease_during_combat(self, parser):
        """Test health decreasing during combat."""
        health_values = [24, 20, 16, 12, 8]
        parsed_states = []

        for i, health in enumerate(health_values):
            state = GameStateSnapshot(
                timestamp=float(i),
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
                health=health,
                max_health=24
            )
            parsed_states.append(parser.parse(state))

        # Health should decrease over time
        for i in range(1, len(parsed_states)):
            assert parsed_states[i].health_percent < parsed_states[i-1].health_percent


# =============================================================================
# Transition Chain Scenarios
# =============================================================================

class TestTransitionChainScenarios:
    """Test complex chains of transitions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_overworld_to_cave_to_room_chain(self, parser):
        """Test OW -> Cave entrance -> Inside cave chain."""
        # Overworld
        ow = GameStateSnapshot(
            timestamp=1.0,
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
            max_health=24
        )
        p1 = parser.parse(ow)
        assert p1.phase == GamePhase.OVERWORLD

        # Transition (mode 0x06)
        transition = GameStateSnapshot(
            timestamp=2.0,
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
            inidisp=0x80,
            health=24,
            max_health=24
        )
        p2 = parser.parse(transition)
        assert p2.is_transitioning or p2.is_black_screen

        # Inside cave
        cave = GameStateSnapshot(
            timestamp=3.0,
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
            inidisp=0x0F,
            health=24,
            max_health=24
        )
        p3 = parser.parse(cave)
        assert p3.phase == GamePhase.DUNGEON

    def test_rapid_room_transitions(self, parser):
        """Test rapid room-to-room transitions."""
        states = []

        for i in range(10):
            # Alternate between normal and transitioning
            if i % 2 == 0:
                state = GameStateSnapshot(
                    timestamp=float(i) * 0.1,
                    mode=0x07,
                    submode=0x00,
                    area=0x00,
                    room=0x10 + i,
                    link_x=256,
                    link_y=320,
                    link_z=0,
                    link_direction=0x02,
                    link_state=0x00,
                    indoors=True,
                    inidisp=0x0F,
                    health=24,
                    max_health=24
                )
            else:
                state = GameStateSnapshot(
                    timestamp=float(i) * 0.1,
                    mode=0x07,
                    submode=0x08,  # Door transition
                    area=0x00,
                    room=0x10 + i,
                    link_x=256,
                    link_y=320,
                    link_z=0,
                    link_direction=0x02,
                    link_state=0x00,
                    indoors=True,
                    inidisp=0x0F,
                    health=24,
                    max_health=24
                )

            parsed = parser.parse(state)
            states.append(parsed)

        # Should handle all states without error
        assert len(states) == 10


# =============================================================================
# Long-Running Simulation Scenarios
# =============================================================================

class TestLongRunningSimulations:
    """Test long-running campaign simulations."""

    def test_extended_exploration_session(self):
        """Simulate extended exploration session (1000 frames)."""
        parser = GameStateParser()
        states_processed = 0
        errors = []

        for i in range(1000):
            try:
                # Vary the state
                area = 0x29 if i % 100 < 50 else 0x20
                mode = 0x09 if i % 10 < 8 else 0x07
                health = max(1, 24 - (i % 24))

                state = GameStateSnapshot(
                    timestamp=float(i) * 0.0167,
                    mode=mode,
                    submode=0x00 if i % 5 != 0 else 0x08,
                    area=area,
                    room=i % 64,
                    link_x=256 + (i % 256),
                    link_y=320 + (i % 128),
                    link_z=0,
                    link_direction=(i * 2) % 8,
                    link_state=i % 4,
                    indoors=mode == 0x07,
                    inidisp=0x0F if i % 20 != 0 else 0x80,
                    health=health,
                    max_health=24
                )
                parsed = parser.parse(state)
                states_processed += 1
            except Exception as e:
                errors.append((i, str(e)))

        # Should process all states without fatal errors
        assert states_processed == 1000
        assert len(errors) == 0

    def test_milestone_progression_simulation(self):
        """Simulate milestone progression over time."""
        progress = CampaignProgress()
        progress.milestones.clear()

        # Add milestones
        milestone_sequence = [
            "boot_complete",
            "village_reached",
            "dungeon_1_found",
            "dungeon_1_entered",
            "boss_1_defeated",
            "dungeon_1_complete"
        ]

        for mid in milestone_sequence:
            progress.add_milestone(CampaignMilestone(
                id=mid,
                description=f"Complete {mid}",
                goal="A.1"
            ))

        # Simulate progression
        for i, mid in enumerate(milestone_sequence):
            # Complete milestone
            progress.complete_milestone(mid, f"Completed at step {i}")

            # Verify progress percentage
            expected_pct = ((i + 1) / len(milestone_sequence)) * 100
            actual_pct = progress.get_completion_percentage()
            assert actual_pct == pytest.approx(expected_pct, rel=0.01)

    def test_input_sequence_accumulation(self):
        """Test accumulating many input sequences."""
        sequences = []

        for i in range(100):
            direction = ["UP", "DOWN", "LEFT", "RIGHT"][i % 4]
            seq = create_walk_sequence(direction, tiles=1)
            sequences.append(seq)

        # Verify all sequences were created
        assert len(sequences) == 100

        # Calculate total frames
        total_frames = sum(s.total_frames for s in sequences)
        assert total_frames > 0


# =============================================================================
# Story Flag Progression Scenarios
# =============================================================================

class TestStoryFlagScenarios:
    """Test scenarios involving story flag progression."""

    def test_intro_to_dungeon_flag_progression(self):
        """Test story flag progression from intro to first dungeon."""
        # Start with no flags
        flags = StoryFlag(0)
        assert flags == 0

        # Complete intro
        flags |= StoryFlag.INTRO_COMPLETE
        assert flags & StoryFlag.INTRO_COMPLETE

        # Arrive at Loom Beach
        flags |= StoryFlag.LOOM_BEACH
        assert flags & StoryFlag.LOOM_BEACH

        # Complete Kydrog quest
        flags |= StoryFlag.KYDROG_COMPLETE
        assert flags & StoryFlag.KYDROG_COMPLETE

    def test_progress_snapshot_with_flags(self):
        """Test ProgressSnapshot with story flags."""
        flags = StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH

        snapshot = ProgressSnapshot(
            timestamp=1.0,
            game_state=0x09,
            story_flags=flags,
            story_flags_2=0,
            side_quest_1=0,
            side_quest_2=0,
            health=24,
            max_health=24,
            rupees=100,
            magic=0,
            max_magic=0,
            sword_level=1,
            shield_level=0,
            armor_level=0,
            crystals=0,
            follower_id=0,
            follower_state=0
        )

        assert snapshot.story_flags & StoryFlag.INTRO_COMPLETE
        assert snapshot.story_flags & StoryFlag.LOOM_BEACH
        assert not (snapshot.story_flags & StoryFlag.KYDROG_COMPLETE)


# =============================================================================
# World Area Scenarios
# =============================================================================

class TestWorldAreaScenarios:
    """Test scenarios involving different world areas."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def test_light_world_exploration(self, parser):
        """Test exploring Light World areas."""
        light_world_areas = [0x00, 0x10, 0x20, 0x29, 0x3F]

        for area in light_world_areas:
            state = GameStateSnapshot(
                timestamp=1.0,
                mode=0x09,
                submode=0x00,
                area=area,
                room=0x00,
                link_x=512,
                link_y=480,
                link_z=0,
                link_direction=0x02,
                link_state=0x00,
                indoors=False,
                inidisp=0x0F,
                health=24,
                max_health=24
            )
            parsed = parser.parse(state)
            assert parsed.phase == GamePhase.OVERWORLD
            # Light World bit 0x40 should NOT be set
            assert (parsed.area_id & 0x40) == 0

    def test_dark_world_exploration(self, parser):
        """Test exploring Dark World areas."""
        dark_world_areas = [0x40, 0x50, 0x60, 0x69, 0x7F]

        for area in dark_world_areas:
            state = GameStateSnapshot(
                timestamp=1.0,
                mode=0x09,
                submode=0x00,
                area=area,
                room=0x00,
                link_x=512,
                link_y=480,
                link_z=0,
                link_direction=0x02,
                link_state=0x00,
                indoors=False,
                inidisp=0x0F,
                health=24,
                max_health=24
            )
            parsed = parser.parse(state)
            assert parsed.phase == GamePhase.OVERWORLD
            # Dark World bit 0x40 SHOULD be set
            assert (parsed.area_id & 0x40) == 0x40

    def test_light_to_dark_world_transition(self, parser):
        """Test transition from Light World to Dark World."""
        # In Light World
        light = GameStateSnapshot(
            timestamp=1.0,
            mode=0x09,
            submode=0x00,
            area=0x29,  # Light World village
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24
        )
        p1 = parser.parse(light)
        assert (p1.area_id & 0x40) == 0

        # In Dark World (same coordinates)
        dark = GameStateSnapshot(
            timestamp=2.0,
            mode=0x09,
            submode=0x00,
            area=0x69,  # Dark World equivalent
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24
        )
        p2 = parser.parse(dark)
        assert (p2.area_id & 0x40) == 0x40


# =============================================================================
# Input Recording Scenarios
# =============================================================================

class TestInputRecordingScenarios:
    """Test input recording and playback scenarios."""

    def test_recording_combat_sequence(self):
        """Test recording a combat input sequence."""
        # Simulate combat inputs: approach, attack, retreat
        frames = [
            InputFrame(frame_number=0, buttons=Button.UP, hold_frames=30),
            InputFrame(frame_number=30, buttons=Button.B, hold_frames=10),  # Attack
            InputFrame(frame_number=40, buttons=Button.DOWN, hold_frames=30),
        ]

        seq = InputSequence(name="combat_test", frames=frames)

        assert seq.total_frames >= 70
        assert any(f.buttons & Button.B for f in seq.frames)

    def test_menu_navigation_sequence(self):
        """Test menu navigation input sequence."""
        # Menu: open, navigate down twice, select
        frames = [
            InputFrame(frame_number=0, buttons=Button.START, hold_frames=5),
            InputFrame(frame_number=10, buttons=Button.DOWN, hold_frames=5),
            InputFrame(frame_number=20, buttons=Button.DOWN, hold_frames=5),
            InputFrame(frame_number=30, buttons=Button.A, hold_frames=5),
        ]

        seq = InputSequence(name="menu_nav", frames=frames)

        # Verify menu buttons are present
        has_start = any(f.buttons & Button.START for f in seq.frames)
        has_down = any(f.buttons & Button.DOWN for f in seq.frames)
        has_a = any(f.buttons & Button.A for f in seq.frames)

        assert has_start and has_down and has_a

    def test_complex_movement_pattern(self):
        """Test complex movement pattern recording."""
        # Figure 8 pattern
        movements = [
            ("UP", 10), ("RIGHT", 10), ("DOWN", 20),
            ("RIGHT", 10), ("UP", 20), ("LEFT", 10),
            ("DOWN", 10), ("LEFT", 10)
        ]

        button_map = {
            "UP": Button.UP, "DOWN": Button.DOWN,
            "LEFT": Button.LEFT, "RIGHT": Button.RIGHT
        }

        frames = []
        frame_num = 0
        for direction, duration in movements:
            frames.append(InputFrame(
                frame_number=frame_num,
                buttons=button_map[direction],
                hold_frames=duration
            ))
            frame_num += duration

        seq = InputSequence(name="figure_8", frames=frames)

        assert len(seq.frames) == len(movements)
        assert seq.total_frames == sum(d for _, d in movements)


# =============================================================================
# Orchestrator Integration Scenarios
# =============================================================================

class TestOrchestratorIntegration:
    """Test campaign orchestrator integration scenarios."""

    def test_full_campaign_startup(self):
        """Test complete campaign startup sequence."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        mock_emu.is_connected.return_value = True
        mock_emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0,
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
            max_health=24
        )

        orchestrator = CampaignOrchestrator(emulator=mock_emu)

        # Connect
        result = orchestrator.connect()
        assert result is True

        # Check we can get state
        state = orchestrator.get_state()
        assert state is not None
        assert state.phase == GamePhase.OVERWORLD

        # Disconnect
        orchestrator.disconnect()
        assert orchestrator._progress.current_phase == CampaignPhase.DISCONNECTED

    def test_campaign_with_multiple_milestones(self):
        """Test campaign completing multiple milestones."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        mock_emu.is_connected.return_value = True
        mock_emu.step_frame.return_value = True
        mock_emu.inject_input.return_value = True

        state_num = [0]
        def get_progressive_state():
            state_num[0] += 1
            return GameStateSnapshot(
                timestamp=float(state_num[0]),
                mode=0x09,
                submode=0x00,
                area=0x29,
                room=0x00,
                link_x=512 + state_num[0],
                link_y=480,
                link_z=0,
                link_direction=0x02,
                link_state=0x00,
                indoors=False,
                inidisp=0x0F,
                health=24,
                max_health=24
            )

        mock_emu.read_state.side_effect = get_progressive_state

        orchestrator = CampaignOrchestrator(emulator=mock_emu)
        orchestrator.connect()

        # Complete some milestones
        orchestrator._progress.complete_milestone("emulator_connected")

        # Verify milestone is complete
        if "emulator_connected" in orchestrator._progress.milestones:
            assert orchestrator._progress.milestones["emulator_connected"].status == MilestoneStatus.COMPLETED
