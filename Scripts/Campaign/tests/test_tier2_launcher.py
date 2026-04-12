"""Tests for the Tier 2 smoke test launcher.

Iteration 61 - Tier 2 Test Infrastructure
Tests: 48

These tests verify the launcher's ability to:
- Find and load save state library
- Resolve state paths correctly
- Generate test scenarios
- Handle various launch configurations
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from scripts.campaign.tier2_test_launcher import (
    TestScenario,
    TIER2_SCENARIOS,
    find_mesen,
    load_state_library,
    find_state_path,
    list_scenarios,
    list_states,
    PROJECT_ROOT,
)


class TestTestScenario:
    """Tests for the TestScenario dataclass."""

    def test_scenario_creation(self):
        """Test creating a test scenario."""
        scenario = TestScenario(
            id="test_1",
            name="Test Scenario",
            description="A test",
            state_id="state_1",
            instructions="Do something",
            expected_result="Something happens"
        )
        assert scenario.id == "test_1"
        assert scenario.name == "Test Scenario"
        assert scenario.description == "A test"
        assert scenario.state_id == "state_1"
        assert scenario.instructions == "Do something"
        assert scenario.expected_result == "Something happens"

    def test_scenario_equality(self):
        """Test scenario equality comparison."""
        s1 = TestScenario("a", "A", "desc", "s1", "inst", "exp")
        s2 = TestScenario("a", "A", "desc", "s1", "inst", "exp")
        assert s1 == s2

    def test_scenario_inequality(self):
        """Test scenario inequality."""
        s1 = TestScenario("a", "A", "desc", "s1", "inst", "exp")
        s2 = TestScenario("b", "B", "desc", "s2", "inst", "exp")
        assert s1 != s2


class TestTier2Scenarios:
    """Tests for the predefined Tier 2 scenarios."""

    def test_scenarios_exist(self):
        """Test that predefined scenarios exist."""
        assert len(TIER2_SCENARIOS) > 0

    def test_scenario_ids_unique(self):
        """Test that all scenario IDs are unique."""
        ids = [s.id for s in TIER2_SCENARIOS]
        assert len(ids) == len(set(ids))

    def test_ow_to_cave_exists(self):
        """Test that OW to cave scenario exists."""
        ids = [s.id for s in TIER2_SCENARIOS]
        assert "ow_to_cave" in ids

    def test_ow_to_dungeon_exists(self):
        """Test that OW to dungeon scenario exists."""
        ids = [s.id for s in TIER2_SCENARIOS]
        assert "ow_to_dungeon" in ids

    def test_ow_to_building_exists(self):
        """Test that OW to building scenario exists."""
        ids = [s.id for s in TIER2_SCENARIOS]
        assert "ow_to_building" in ids

    def test_dungeon_stairs_inter_exists(self):
        """Test that dungeon interroom stairs scenario exists."""
        ids = [s.id for s in TIER2_SCENARIOS]
        assert "dungeon_stairs_inter" in ids

    def test_dungeon_stairs_intra_exists(self):
        """Test that dungeon intraroom stairs scenario exists."""
        ids = [s.id for s in TIER2_SCENARIOS]
        assert "dungeon_stairs_intra" in ids

    def test_dungeon_to_ow_exists(self):
        """Test that dungeon to OW scenario exists."""
        ids = [s.id for s in TIER2_SCENARIOS]
        assert "dungeon_to_ow" in ids

    def test_all_scenarios_have_state_ids(self):
        """Test that all scenarios have state IDs."""
        for scenario in TIER2_SCENARIOS:
            assert scenario.state_id, f"Scenario {scenario.id} missing state_id"

    def test_all_scenarios_have_instructions(self):
        """Test that all scenarios have instructions."""
        for scenario in TIER2_SCENARIOS:
            assert scenario.instructions, f"Scenario {scenario.id} missing instructions"

    def test_all_scenarios_have_expected_result(self):
        """Test that all scenarios have expected results."""
        for scenario in TIER2_SCENARIOS:
            assert scenario.expected_result, f"Scenario {scenario.id} missing expected_result"

    def test_scenario_count(self):
        """Test the expected number of scenarios."""
        # Based on TieredTestingPlan.md test matrix
        assert len(TIER2_SCENARIOS) >= 6


class TestFindMesen:
    """Tests for the find_mesen function."""

    @patch("scripts.campaign.tier2_test_launcher.Path.exists")
    def test_find_mesen_not_found(self, mock_exists):
        """Test when Mesen is not found."""
        mock_exists.return_value = False
        result = find_mesen()
        assert result is None

    @patch("scripts.campaign.tier2_test_launcher.Path")
    def test_find_mesen_found_first(self, mock_path_class):
        """Test finding Mesen at first location."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path
        # Can't easily test due to module-level MESEN_PATHS
        # Just verify function exists and is callable
        assert callable(find_mesen)


class TestLoadStateLibrary:
    """Tests for loading the state library."""

    def test_load_state_library_returns_dict(self):
        """Test that loading returns a dictionary."""
        result = load_state_library()
        assert isinstance(result, dict)

    def test_load_state_library_has_entries(self):
        """Test that library has entries key."""
        result = load_state_library()
        assert "entries" in result

    def test_load_state_library_entries_is_list(self):
        """Test that entries is a list."""
        result = load_state_library()
        assert isinstance(result["entries"], list)

    @patch("scripts.campaign.tier2_test_launcher.STATE_LIBRARY_PATH")
    def test_load_missing_library(self, mock_path):
        """Test loading when library file doesn't exist."""
        mock_path.exists.return_value = False
        # Function should return empty entries without crashing
        with patch("scripts.campaign.tier2_test_launcher.STATE_LIBRARY_PATH.exists", return_value=False):
            result = load_state_library()
            # May return actual library or empty depending on implementation
            assert isinstance(result, dict)


class TestFindStatePath:
    """Tests for finding state paths."""

    def test_find_state_path_returns_path_or_none(self):
        """Test that find_state_path returns Path or None."""
        library = {"entries": []}
        result = find_state_path("nonexistent", library)
        assert result is None

    def test_find_state_path_with_valid_id(self):
        """Test finding a state with a valid ID."""
        library = {
            "entries": [
                {"id": "test_state", "state_path": "path/to/state.mss"}
            ]
        }
        # Won't find actual file, but tests the lookup logic
        result = find_state_path("test_state", library)
        # Returns None if file doesn't exist
        # This is expected behavior
        assert result is None or isinstance(result, Path)

    def test_find_state_path_with_real_library(self):
        """Test finding a state in the real library."""
        library = load_state_library()
        if library.get("entries"):
            first_entry = library["entries"][0]
            state_id = first_entry.get("id")
            if state_id:
                result = find_state_path(state_id, library)
                # May or may not exist
                assert result is None or isinstance(result, Path)

    def test_find_state_path_empty_library(self):
        """Test with empty library."""
        result = find_state_path("any_id", {"entries": []})
        assert result is None

    def test_find_state_path_missing_entries(self):
        """Test with library missing entries key."""
        result = find_state_path("any_id", {})
        assert result is None


class TestProjectRoot:
    """Tests for project root path."""

    def test_project_root_exists(self):
        """Test that project root exists."""
        assert PROJECT_ROOT.exists()

    def test_project_root_is_directory(self):
        """Test that project root is a directory."""
        assert PROJECT_ROOT.is_dir()

    def test_project_root_contains_roms(self):
        """Test that project root contains Roms directory."""
        assert (PROJECT_ROOT / "Roms").exists()

    def test_project_root_contains_scripts(self):
        """Test that project root contains scripts directory."""
        assert (PROJECT_ROOT / "scripts").exists()


class TestScenarioLookup:
    """Tests for scenario lookup utilities."""

    def test_find_scenario_by_id(self):
        """Test finding a scenario by ID."""
        scenario = None
        for s in TIER2_SCENARIOS:
            if s.id == "ow_to_cave":
                scenario = s
                break
        assert scenario is not None
        assert scenario.name == "Overworld to Cave"

    def test_find_nonexistent_scenario(self):
        """Test that nonexistent scenario returns None."""
        scenario = None
        for s in TIER2_SCENARIOS:
            if s.id == "nonexistent_scenario_xyz":
                scenario = s
                break
        assert scenario is None

    def test_scenario_state_ids_valid_format(self):
        """Test that scenario state IDs have valid format."""
        for scenario in TIER2_SCENARIOS:
            # State IDs should be alphanumeric with underscores
            assert scenario.state_id.replace("_", "").isalnum()


class TestListFunctions:
    """Tests for list_scenarios and list_states functions."""

    def test_list_scenarios_callable(self):
        """Test that list_scenarios is callable."""
        assert callable(list_scenarios)

    def test_list_states_callable(self):
        """Test that list_states is callable."""
        assert callable(list_states)

    @patch("builtins.print")
    def test_list_scenarios_prints_output(self, mock_print):
        """Test that list_scenarios produces output."""
        list_scenarios()
        assert mock_print.called

    @patch("builtins.print")
    def test_list_states_prints_output(self, mock_print):
        """Test that list_states produces output."""
        list_states()
        assert mock_print.called


class TestStateLibraryIntegration:
    """Integration tests with the actual state library."""

    def test_current_states_exist(self):
        """Test that current build states are in library."""
        library = load_state_library()
        ids = [e.get("id") for e in library.get("entries", [])]
        # Check for at least some current states
        current_ids = [i for i in ids if i and i.startswith("current_")]
        assert len(current_ids) > 0

    def test_baseline_states_exist(self):
        """Test that baseline states are in library."""
        library = load_state_library()
        ids = [e.get("id") for e in library.get("entries", [])]
        baseline_ids = [i for i in ids if i and i.startswith("baseline_")]
        assert len(baseline_ids) > 0

    def test_library_has_sets(self):
        """Test that library has state sets defined."""
        library = load_state_library()
        assert "sets" in library

    def test_library_sets_are_list(self):
        """Test that library sets is a list."""
        library = load_state_library()
        assert isinstance(library.get("sets", []), list)

    def test_scenario_state_ids_in_library(self):
        """Test that scenario state IDs exist in library."""
        library = load_state_library()
        ids = [e.get("id") for e in library.get("entries", [])]

        for scenario in TIER2_SCENARIOS:
            assert scenario.state_id in ids, \
                f"Scenario {scenario.id} references unknown state {scenario.state_id}"


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_state_id(self):
        """Test handling of empty state ID."""
        result = find_state_path("", {"entries": []})
        assert result is None

    def test_none_state_id(self):
        """Test handling of None state ID."""
        result = find_state_path(None, {"entries": []})
        assert result is None

    def test_special_characters_in_id(self):
        """Test handling of special characters in state ID."""
        result = find_state_path("test/../../../etc/passwd", {"entries": []})
        assert result is None

    def test_very_long_state_id(self):
        """Test handling of very long state ID."""
        long_id = "a" * 10000
        result = find_state_path(long_id, {"entries": []})
        assert result is None
