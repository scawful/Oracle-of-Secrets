"""Integration tests for campaign module interactions.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D: Integration between campaign components

These tests verify that modules work correctly together,
simulating end-to-end workflows without a live emulator.
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tempfile

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import GameStateSnapshot, Mesen2Emulator
from scripts.campaign.game_state import GamePhase, GameStateParser, ParsedGameState
from scripts.campaign.input_recorder import (
    Button, InputSequence, InputPlayer, create_boot_sequence, create_walk_sequence
)
from scripts.campaign.action_planner import (
    ActionPlanner, Goal, GoalType, Plan, PlanStatus
)
from scripts.campaign.campaign_orchestrator import (
    CampaignOrchestrator, CampaignPhase, MilestoneStatus
)
from scripts.campaign.visual_verifier import (
    VisualVerifier, Screenshot, VerificationResult
)


class TestParserToOrchestratorIntegration:
    """Test game_state.py → campaign_orchestrator.py integration."""

    @pytest.fixture
    def mock_emulator(self):
        """Create mock emulator with realistic state progression."""
        emu = Mock()
        emu.connect.return_value = True
        emu.is_connected.return_value = True
        emu.disconnect.return_value = None
        emu.step_frame.return_value = True
        emu.inject_input.return_value = True

        # Start with boot state, then playable
        self.call_count = 0
        def get_state():
            self.call_count += 1
            if self.call_count < 5:
                # Boot/transition state
                return GameStateSnapshot(
                    timestamp=float(self.call_count),
                    mode=0x06, submode=0x00,
                    area=0x00, room=0x00,
                    link_x=0, link_y=0, link_z=0,
                    link_direction=0, link_state=0,
                    indoors=False, inidisp=0x80,
                    health=0, max_health=0
                )
            else:
                # Playable overworld state
                return GameStateSnapshot(
                    timestamp=float(self.call_count),
                    mode=0x09, submode=0x00,
                    area=0x29, room=0x00,
                    link_x=512, link_y=480, link_z=0,
                    link_direction=2, link_state=0,
                    indoors=False, inidisp=0x0F,
                    health=24, max_health=24
                )

        emu.read_state.side_effect = get_state
        return emu

    def test_parser_detects_phase_changes(self, mock_emulator):
        """Test parser correctly identifies phase transitions."""
        parser = GameStateParser()

        # Boot state
        state1 = mock_emulator.read_state()
        parsed1 = parser.parse(state1)
        assert parsed1.phase in (GamePhase.TRANSITION, GamePhase.BLACK_SCREEN)

        # Skip to playable
        for _ in range(5):
            mock_emulator.read_state()

        state2 = mock_emulator.read_state()
        parsed2 = parser.parse(state2)
        assert parsed2.phase == GamePhase.OVERWORLD

    def test_orchestrator_uses_parser_correctly(self, mock_emulator):
        """Test orchestrator delegates to parser properly."""
        orchestrator = CampaignOrchestrator(emulator=mock_emulator)
        orchestrator.connect()

        # First state read
        state = orchestrator.get_state()
        assert state is not None
        assert isinstance(state, ParsedGameState)

        # Verify parser is being used
        assert hasattr(state, 'phase')
        assert hasattr(state, 'link_position')


class TestInputToActionIntegration:
    """Test input_recorder.py → action_planner.py integration."""

    @pytest.fixture
    def mock_emulator(self):
        """Create mock emulator."""
        emu = Mock()
        emu.inject_input.return_value = True
        emu.step_frame.return_value = True
        emu.is_connected.return_value = True
        emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        return emu

    def test_walk_sequence_used_in_plan(self, mock_emulator):
        """Test walk sequences integrate with action plans."""
        planner = ActionPlanner(mock_emulator)
        goal = Goal.enter_building(0x12)
        plan = planner.create_plan(goal)

        # Plan should include actions with input sequences
        has_input = False
        for action in plan.actions:
            if action.input_sequence is not None:
                has_input = True
                assert len(action.input_sequence.frames) > 0

        assert has_input, "Enter building plan should include input sequences"

    def test_boot_sequence_frame_count(self):
        """Test boot sequence has reasonable frame count."""
        boot_seq = create_boot_sequence()

        # Boot should take ~270+ frames (4.5+ seconds at 60fps)
        assert boot_seq.total_frames > 200
        assert boot_seq.total_frames < 500

        # Should have multiple input frames
        assert len(boot_seq.frames) >= 2

    def test_walk_sequence_direction_mapping(self):
        """Test all directions create valid sequences."""
        directions = ["UP", "DOWN", "LEFT", "RIGHT"]

        for direction in directions:
            seq = create_walk_sequence(direction, 3)
            assert len(seq.frames) == 1

            # Verify correct button
            expected_button = getattr(Button, direction)
            assert seq.frames[0].buttons & expected_button


class TestVerifierToOrchestratorIntegration:
    """Test visual_verifier.py → campaign_orchestrator.py integration."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_dir = Path(tmpdir) / "baseline"
            capture_dir = Path(tmpdir) / "captures"
            baseline_dir.mkdir()
            capture_dir.mkdir()
            yield baseline_dir, capture_dir

    def test_verifier_black_screen_detection_matches_parser(self, temp_dirs):
        """Test verifier and parser agree on black screen detection."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)
        parser = GameStateParser()

        # Create a simulated black screen state
        black_state = GameStateSnapshot(
            timestamp=1.0, mode=0x07, submode=0x0F,
            area=0x00, room=0x00,
            link_x=0, link_y=0, link_z=0,
            link_direction=0, link_state=0,
            indoors=True, inidisp=0x80,  # Black screen
            health=24, max_health=24
        )

        parsed = parser.parse(black_state)
        assert parsed.is_black_screen, "Parser should detect black screen"

        # Create a small file (simulates black screen)
        black_file = capture_dir / "black.png"
        black_file.write_bytes(b"\x89PNG" + b"\x00" * 100)

        screenshot = Screenshot(
            path=black_file,
            timestamp=datetime.now(),
            frame_number=0
        )

        assert verifier.is_black_screen(screenshot), "Verifier should detect black screen"

    def test_transition_verification_area_tracking(self, temp_dirs):
        """Test verifier tracks area changes correctly."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        # Create before/after screenshots with different areas
        before_path = capture_dir / "before.png"
        before_path.write_bytes(b"x" * 5000)

        after_path = capture_dir / "after.png"
        after_path.write_bytes(b"y" * 5000)

        before = Screenshot(
            path=before_path,
            timestamp=datetime.now(),
            frame_number=0,
            area_id=0x09  # Overworld
        )

        after = Screenshot(
            path=after_path,
            timestamp=datetime.now(),
            frame_number=100,
            area_id=0x29  # Village
        )

        # Verify transition to expected area
        report = verifier.verify_transition(before, after, expected_area=0x29)
        assert report.result == VerificationResult.PASS

        # Verify transition to wrong area fails
        report = verifier.verify_transition(before, after, expected_area=0x1E)
        assert report.result == VerificationResult.FAIL


class TestGoalToMilestoneIntegration:
    """Test action_planner.py → campaign_orchestrator.py goal/milestone integration."""

    @pytest.fixture
    def orchestrator_with_mock(self):
        """Create orchestrator with mock emulator."""
        emu = Mock()
        emu.connect.return_value = True
        emu.is_connected.return_value = True
        emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        orchestrator = CampaignOrchestrator(emulator=emu)
        return orchestrator

    def test_prebuilt_goals_match_milestones(self, orchestrator_with_mock):
        """Test prebuilt goals correspond to milestone tracking."""
        orchestrator = orchestrator_with_mock

        # Check milestones exist for key goals
        assert "reach_village" in orchestrator._progress.milestones
        assert "reach_dungeon1" in orchestrator._progress.milestones

        # Verify goal parameters match expected areas
        from scripts.campaign.action_planner import (
            goal_reach_village_center,
            goal_reach_dungeon1_entrance
        )

        village_goal = goal_reach_village_center()
        assert village_goal.parameters["area_id"] == 0x29

        dungeon_goal = goal_reach_dungeon1_entrance()
        assert dungeon_goal.parameters["area_id"] == 0x1E

    def test_milestone_completion_on_goal_achievement(self, orchestrator_with_mock):
        """Test completing a goal updates corresponding milestone."""
        orchestrator = orchestrator_with_mock
        orchestrator.connect()

        # Manually complete a milestone (simulating goal achievement)
        success = orchestrator._progress.complete_milestone(
            "emulator_connected",
            "Connected via test"
        )

        assert success
        assert orchestrator._progress.milestones["emulator_connected"].status == MilestoneStatus.COMPLETED


class TestEndToEndWorkflow:
    """Test complete workflows across all modules."""

    def test_campaign_infrastructure_loads(self):
        """Test all campaign modules can be imported together."""
        from scripts.campaign import (
            # Emulator
            EmulatorInterface, Mesen2Emulator, GameStateSnapshot,
            # Parsing
            GamePhase, GameStateParser, ParsedGameState,
            # Input
            Button, InputSequence, InputPlayer,
            # Planning
            ActionPlanner, Goal, Plan,
            # Orchestration
            CampaignOrchestrator, create_campaign,
            # Verification
            VisualVerifier, VerificationResult
        )

        # All imports successful
        assert True

    def test_quick_status_reports_all_modules(self):
        """Test quick_status shows all infrastructure."""
        from scripts.campaign import quick_status

        status = quick_status()

        assert "EmulatorInterface" in status
        assert "GameStateParser" in status
        assert "InputRecorder" in status
        assert "ActionPlanner" in status
        assert "CampaignOrchestrator" in status

    def test_create_campaign_factory(self):
        """Test campaign factory creates functional orchestrator."""
        from scripts.campaign import create_campaign

        orchestrator = create_campaign()

        assert orchestrator is not None
        assert hasattr(orchestrator, 'connect')
        assert hasattr(orchestrator, 'run_campaign')
        assert hasattr(orchestrator, 'get_status_report')
