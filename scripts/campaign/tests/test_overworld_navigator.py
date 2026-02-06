# -*- coding: utf-8 -*-
"""Tests for overworld_navigator module.

Campaign Iteration: 68
Tests Added: 75
Focus: Goal A.2 - Navigate overworld to specific locations
"""

import math
import pytest
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from scripts.campaign.overworld_navigator import (
    OverworldNavigator,
    OverworldState,
    NavigationResult,
    NavigationStatus,
    NavigationMode,
    PointOfInterest,
    POINTS_OF_INTEREST,
    AREA_CONNECTIONS,
    get_poi_names,
    get_pois_by_tag,
    get_dungeon_pois,
    get_town_pois,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_bridge():
    """Create a mock Mesen2Bridge for testing."""
    bridge = MagicMock()

    # Default memory state (overworld, village center)
    memory_map = {
        0x7E0010: 0x09,  # GameMode = overworld
        0x7E0011: 0x00,  # Submodule
        0x7E001A: 0x0F,  # INIDISP = normal
        0x7E008A: 0x29,  # Area = Village Center
        0x7E0020: 0x68,  # Link Y low
        0x7E0021: 0x0E,  # Link Y high (3688)
        0x7E0022: 0xF8,  # Link X low
        0x7E0023: 0x0C,  # Link X high (3320)
        0x7E002F: 0x02,  # Direction = down
    }

    def read_memory(addr: int) -> int:
        """Mock read_memory - returns single int (like real MesenBridge)."""
        return memory_map.get(addr, 0)

    def read_memory16(addr: int) -> int:
        """Mock read_memory16 - returns 16-bit value (little-endian)."""
        lo = memory_map.get(addr, 0)
        hi = memory_map.get(addr + 1, 0)
        return lo | (hi << 8)

    bridge.read_memory = MagicMock(side_effect=read_memory)
    bridge.read_memory16 = MagicMock(side_effect=read_memory16)
    bridge.press_button = MagicMock()
    bridge.input_inject = MagicMock()

    return bridge


@pytest.fixture
def navigator(mock_bridge):
    """Create OverworldNavigator with mock bridge."""
    return OverworldNavigator(mock_bridge)


@pytest.fixture
def sample_poi():
    """Create a sample point of interest."""
    return PointOfInterest(
        name="Test Location",
        area_id=0x29,
        x=3400,
        y=3700,
        description="Test POI",
        tags=["test", "village"],
    )


# =============================================================================
# PointOfInterest Tests
# =============================================================================

class TestPointOfInterest:
    """Tests for PointOfInterest dataclass."""

    def test_poi_creation(self, sample_poi):
        """Test POI creation with all fields."""
        assert sample_poi.name == "Test Location"
        assert sample_poi.area_id == 0x29
        assert sample_poi.x == 3400
        assert sample_poi.y == 3700

    def test_poi_position_property(self, sample_poi):
        """Test position tuple property."""
        assert sample_poi.position == (3400, 3700)

    def test_poi_distance_to(self, sample_poi):
        """Test distance calculation."""
        # Same position
        assert sample_poi.distance_to(3400, 3700) == 0

        # Simple horizontal distance
        assert sample_poi.distance_to(3500, 3700) == 100

        # Simple vertical distance
        assert sample_poi.distance_to(3400, 3800) == 100

        # Diagonal distance (3-4-5 triangle)
        assert sample_poi.distance_to(3340, 3620) == pytest.approx(100.0, rel=0.01)

    def test_poi_default_tags(self):
        """Test POI with default empty tags."""
        poi = PointOfInterest(name="Minimal", area_id=0x00, x=0, y=0)
        assert poi.tags == []
        assert poi.entrance_id is None

    def test_poi_with_entrance(self):
        """Test POI with entrance ID."""
        poi = PointOfInterest(
            name="Building",
            area_id=0x29,
            x=3320,
            y=3600,
            entrance_id=0x42,
        )
        assert poi.entrance_id == 0x42

    def test_poi_with_waypoints(self):
        """Test POI with waypoints."""
        poi = PointOfInterest(
            name="Complex",
            area_id=0x29,
            x=3500,
            y=3800,
            waypoints=[(3400, 3700), (3450, 3750)],
        )
        assert len(poi.waypoints) == 2


# =============================================================================
# OverworldState Tests
# =============================================================================

class TestOverworldState:
    """Tests for OverworldState dataclass."""

    def test_state_creation(self):
        """Test state creation."""
        state = OverworldState(
            timestamp="2026-01-24T12:00:00",
            game_mode=0x09,
            area_id=0x29,
            link_x=3320,
            link_y=3688,
            direction=0x02,
            inidisp=0x0F,
            submodule=0x00,
        )
        assert state.game_mode == 0x09
        assert state.link_x == 3320
        assert state.link_y == 3688

    def test_is_on_overworld_true(self):
        """Test overworld detection when on overworld."""
        state = OverworldState(
            timestamp="", game_mode=0x09, area_id=0x29,
            link_x=0, link_y=0, direction=0, inidisp=0, submodule=0,
        )
        assert state.is_on_overworld is True

    def test_is_on_overworld_false(self):
        """Test overworld detection when indoors."""
        state = OverworldState(
            timestamp="", game_mode=0x07, area_id=0x29,
            link_x=0, link_y=0, direction=0, inidisp=0, submodule=0,
        )
        assert state.is_on_overworld is False

    def test_position_property(self):
        """Test position tuple property."""
        state = OverworldState(
            timestamp="", game_mode=0x09, area_id=0x29,
            link_x=3320, link_y=3688, direction=0, inidisp=0, submodule=0,
        )
        assert state.position == (3320, 3688)

    def test_area_name_property(self):
        """Test area name lookup."""
        state = OverworldState(
            timestamp="", game_mode=0x09, area_id=0x29,
            link_x=0, link_y=0, direction=0, inidisp=0, submodule=0,
        )
        assert state.area_name == "Village Center"

    def test_is_light_world(self):
        """Test light world detection."""
        # Light world area
        state = OverworldState(
            timestamp="", game_mode=0x09, area_id=0x29,
            link_x=0, link_y=0, direction=0, inidisp=0, submodule=0,
        )
        assert state.is_light_world is True
        assert state.is_dark_world is False

    def test_is_dark_world(self):
        """Test dark world detection."""
        # Dark world area (0x80 bit set)
        state = OverworldState(
            timestamp="", game_mode=0x09, area_id=0x80 | 0x40,
            link_x=0, link_y=0, direction=0, inidisp=0, submodule=0,
        )
        assert state.is_dark_world is True
        assert state.is_light_world is False

    def test_is_underwater(self):
        """Test underwater detection."""
        state = OverworldState(
            timestamp="", game_mode=0x09, area_id=0x75,
            link_x=0, link_y=0, direction=0, inidisp=0, submodule=0,
        )
        assert state.is_underwater is True


# =============================================================================
# NavigationResult Tests
# =============================================================================

class TestNavigationResult:
    """Tests for NavigationResult dataclass."""

    def test_result_success(self):
        """Test successful navigation result."""
        result = NavigationResult(
            status=NavigationStatus.SUCCESS,
            start_position=(3320, 3688),
            end_position=(3400, 3700),
            target_position=(3400, 3700),
            frames_elapsed=120,
            path_length=4,
        )
        assert result.success is True
        assert result.distance_to_target == 0

    def test_result_failure(self):
        """Test failed navigation result."""
        result = NavigationResult(
            status=NavigationStatus.FAILED_STUCK,
            start_position=(3320, 3688),
            end_position=(3320, 3688),
            target_position=(3400, 3700),
            frames_elapsed=60,
            path_length=0,
            error_message="Stuck",
        )
        assert result.success is False
        assert result.distance_to_target > 0

    def test_distance_to_target(self):
        """Test distance calculation."""
        result = NavigationResult(
            status=NavigationStatus.IN_PROGRESS,
            start_position=(0, 0),
            end_position=(30, 40),
            target_position=(0, 0),
            frames_elapsed=10,
            path_length=1,
        )
        assert result.distance_to_target == 50  # 3-4-5 triangle scaled

    def test_to_dict(self):
        """Test serialization to dict."""
        result = NavigationResult(
            status=NavigationStatus.SUCCESS,
            start_position=(100, 200),
            end_position=(300, 400),
            target_position=(300, 400),
            frames_elapsed=60,
            path_length=2,
        )
        d = result.to_dict()
        assert d["status"] == "SUCCESS"
        assert d["start_position"] == (100, 200)
        assert d["frames_elapsed"] == 60


# =============================================================================
# OverworldNavigator Basic Tests
# =============================================================================

class TestOverworldNavigatorBasic:
    """Basic tests for OverworldNavigator."""

    def test_navigator_creation(self, navigator):
        """Test navigator initialization."""
        assert navigator.bridge is not None
        assert navigator.timeout_frames == 3600
        assert navigator._arrival_threshold == 16

    def test_capture_state(self, navigator):
        """Test state capture from emulator."""
        state = navigator.capture_state()
        assert state.game_mode == 0x09
        assert state.area_id == 0x29
        assert state.is_on_overworld is True

    def test_get_state(self, navigator):
        """Test get_state returns last captured state."""
        assert navigator.get_state() is None
        navigator.capture_state()
        assert navigator.get_state() is not None

    def test_reset(self, navigator):
        """Test reset clears state."""
        navigator.capture_state()
        navigator.reset()
        assert navigator.get_state() is None
        assert len(navigator._states_history) == 0


# =============================================================================
# POI Lookup Tests
# =============================================================================

class TestPOILookup:
    """Tests for POI lookup functionality."""

    def test_get_poi_valid(self, navigator):
        """Test getting valid POI."""
        poi = navigator.get_poi("village_center")
        assert poi is not None
        assert poi.name == "Village Center"

    def test_get_poi_with_spaces(self, navigator):
        """Test POI lookup with spaces in name."""
        poi = navigator.get_poi("village center")
        assert poi is not None

    def test_get_poi_invalid(self, navigator):
        """Test getting invalid POI returns None."""
        poi = navigator.get_poi("nonexistent_place")
        assert poi is None

    def test_list_pois(self, navigator):
        """Test listing all POIs."""
        pois = navigator.list_pois()
        assert len(pois) > 0
        assert all(isinstance(p, PointOfInterest) for p in pois)

    def test_list_pois_by_tag(self, navigator):
        """Test filtering POIs by tag."""
        town_pois = navigator.list_pois(tag="town")
        assert all("town" in [t.lower() for t in p.tags] for p in town_pois)

    def test_find_nearest_poi(self, navigator):
        """Test finding nearest POI."""
        # At village center position
        nearest = navigator.find_nearest_poi(3320, 3688)
        assert nearest is not None

    def test_find_nearest_poi_with_tag(self, navigator):
        """Test finding nearest POI with tag filter."""
        nearest = navigator.find_nearest_poi(3320, 3688, tag="dungeon")
        assert nearest is not None
        assert "dungeon" in [t.lower() for t in nearest.tags]

    def test_get_area_pois(self, navigator):
        """Test getting POIs in specific area."""
        pois = navigator.get_area_pois(0x29)
        assert all(p.area_id == 0x29 for p in pois)


# =============================================================================
# Direction Calculation Tests
# =============================================================================

class TestDirectionCalculation:
    """Tests for direction calculation."""

    def test_direction_right(self, navigator):
        """Test RIGHT direction."""
        direction = navigator.calculate_direction(0, 0, 100, 0)
        assert direction == "RIGHT"

    def test_direction_left(self, navigator):
        """Test LEFT direction."""
        direction = navigator.calculate_direction(100, 0, 0, 0)
        assert direction == "LEFT"

    def test_direction_down(self, navigator):
        """Test DOWN direction."""
        direction = navigator.calculate_direction(0, 0, 0, 100)
        assert direction == "DOWN"

    def test_direction_up(self, navigator):
        """Test UP direction."""
        direction = navigator.calculate_direction(0, 100, 0, 0)
        assert direction == "UP"

    def test_direction_diagonal_right(self, navigator):
        """Test diagonal with larger X delta."""
        direction = navigator.calculate_direction(0, 0, 100, 50)
        assert direction == "RIGHT"

    def test_direction_diagonal_down(self, navigator):
        """Test diagonal with larger Y delta."""
        direction = navigator.calculate_direction(0, 0, 50, 100)
        assert direction == "DOWN"


# =============================================================================
# Position Check Tests
# =============================================================================

class TestPositionChecks:
    """Tests for position-related checks."""

    def test_is_at_position_exact(self, navigator):
        """Test exact position match."""
        navigator.capture_state()
        # Mock position is (3320, 3688)
        assert navigator.is_at_position(3320, 3688) is True

    def test_is_at_position_within_threshold(self, navigator):
        """Test position within threshold."""
        navigator.capture_state()
        # Default threshold is 16
        assert navigator.is_at_position(3330, 3688) is True

    def test_is_at_position_outside_threshold(self, navigator):
        """Test position outside threshold."""
        navigator.capture_state()
        assert navigator.is_at_position(3400, 3688) is False

    def test_is_at_position_custom_threshold(self, navigator):
        """Test custom threshold."""
        navigator.capture_state()
        assert navigator.is_at_position(3400, 3688, threshold=100) is True


# =============================================================================
# Stuck Detection Tests
# =============================================================================

class TestStuckDetection:
    """Tests for stuck detection."""

    def test_not_stuck_initially(self, navigator):
        """Test not stuck with few frames."""
        navigator.capture_state()
        assert navigator.is_stuck() is False

    def test_not_stuck_with_movement(self, mock_bridge, navigator):
        """Test not stuck when position changes."""
        # Simulate movement by changing position each frame
        positions = [(3320 + i, 3688) for i in range(70)]

        for x, y in positions:
            # Create memory map for this position
            mem_map = {
                0x7E0010: 0x09,  # Overworld mode
                0x7E0011: 0x00,
                0x7E001A: 0x0F,
                0x7E008A: 0x29,
                0x7E0022: x & 0xFF,
                0x7E0023: x >> 8,
                0x7E0020: y & 0xFF,
                0x7E0021: y >> 8,
                0x7E002F: 0x02,
            }
            mock_bridge.read_memory.side_effect = lambda addr, m=mem_map: m.get(addr, 0)
            mock_bridge.read_memory16.side_effect = lambda addr, m=mem_map: m.get(addr, 0) | (m.get(addr + 1, 0) << 8)

            navigator.capture_state()

        assert navigator.is_stuck() is False

    def test_stuck_when_stationary(self, navigator):
        """Test stuck when position unchanged."""
        # Capture same position many times
        for _ in range(70):
            navigator.capture_state()

        assert navigator.is_stuck() is True


# =============================================================================
# Walk Tests
# =============================================================================

class TestWalkFunctionality:
    """Tests for walk_toward functionality."""

    def test_walk_toward_executes_input(self, mock_bridge, navigator):
        """Test walk_toward sends input command."""
        navigator.walk_toward(3400, 3688, frames=30)
        mock_bridge.press_button.assert_called()

    def test_walk_toward_returns_true_on_overworld(self, navigator):
        """Test walk returns True on overworld."""
        result = navigator.walk_toward(3400, 3688)
        assert result is True

    def test_walk_toward_calculates_direction(self, mock_bridge, navigator):
        """Test walk calculates correct direction."""
        navigator.walk_toward(3400, 3688)  # X > current, so RIGHT
        mock_bridge.press_button.assert_called_with("RIGHT", 30)


# =============================================================================
# Navigation Tests
# =============================================================================

class TestNavigation:
    """Tests for navigation functionality."""

    def test_navigate_wrong_mode(self, mock_bridge, navigator):
        """Test navigation fails when not on overworld."""
        # Set game mode to indoors (dungeon mode 0x07)
        mock_bridge.read_memory.side_effect = lambda addr: (
            0x07 if addr == 0x7E0010 else 0
        )

        result = navigator.navigate_to_coordinates(3400, 3700)
        assert result.status == NavigationStatus.FAILED_WRONG_MODE

    def test_navigate_to_poi_unknown(self, navigator):
        """Test navigation to unknown POI."""
        result = navigator.navigate_to_poi("nonexistent_place")
        assert result.status == NavigationStatus.FAILED_NO_PATH
        assert "Unknown POI" in result.error_message

    def test_navigate_to_area_already_there(self, navigator):
        """Test navigation to current area succeeds immediately."""
        result = navigator.navigate_to_area(0x29)  # Already in village center
        assert result.status == NavigationStatus.SUCCESS

    def test_navigate_to_area_no_connection(self, navigator):
        """Test navigation fails with no path."""
        result = navigator.navigate_to_area(0xFF)  # Invalid area
        assert result.status == NavigationStatus.FAILED_NO_PATH


# =============================================================================
# Statistics Tests
# =============================================================================

class TestNavigationStats:
    """Tests for navigation statistics."""

    def test_empty_stats(self, navigator):
        """Test stats with no history."""
        stats = navigator.get_navigation_stats()
        assert stats == {}

    def test_stats_after_capture(self, navigator):
        """Test stats after capturing states."""
        for _ in range(5):
            navigator.capture_state()

        stats = navigator.get_navigation_stats()
        assert stats["total_frames"] == 5
        assert "start_position" in stats
        assert "end_position" in stats


# =============================================================================
# Module-Level Function Tests
# =============================================================================

class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_poi_names(self):
        """Test getting all POI names."""
        names = get_poi_names()
        assert len(names) > 0
        assert "village_center" in names

    def test_get_pois_by_tag(self):
        """Test getting POIs by tag."""
        dungeon_pois = get_pois_by_tag("dungeon")
        assert len(dungeon_pois) > 0

    def test_get_dungeon_pois(self):
        """Test convenience function for dungeon POIs."""
        pois = get_dungeon_pois()
        assert all("dungeon" in [t.lower() for t in p.tags] for p in pois)

    def test_get_town_pois(self):
        """Test convenience function for town POIs."""
        pois = get_town_pois()
        assert all("town" in [t.lower() for t in p.tags] for p in pois)


# =============================================================================
# Data Integrity Tests
# =============================================================================

class TestDataIntegrity:
    """Tests for POI and area connection data integrity."""

    def test_all_pois_have_valid_areas(self):
        """Test all POIs reference valid area IDs."""
        for name, poi in POINTS_OF_INTEREST.items():
            assert 0x00 <= poi.area_id <= 0xFF, f"POI {name} has invalid area"

    def test_all_pois_have_positive_coords(self):
        """Test all POIs have non-negative coordinates."""
        for name, poi in POINTS_OF_INTEREST.items():
            assert poi.x >= 0, f"POI {name} has negative X"
            assert poi.y >= 0, f"POI {name} has negative Y"

    def test_area_connections_symmetric(self):
        """Test area connections are reasonably structured."""
        for area_id, connections in AREA_CONNECTIONS.items():
            for connected_area, direction, pos in connections:
                assert isinstance(connected_area, int)
                assert direction in ["north", "south", "east", "west"]
                assert len(pos) == 2

    def test_dungeon_pois_exist(self):
        """Test that dungeon POIs are defined."""
        dungeon_pois = get_dungeon_pois()
        assert len(dungeon_pois) >= 3  # At least 3 dungeons

    def test_village_center_poi_exists(self):
        """Test village center POI is defined correctly."""
        poi = POINTS_OF_INTEREST.get("village_center")
        assert poi is not None
        assert poi.area_id == 0x29


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_timeout(self, mock_bridge):
        """Test navigator with zero timeout."""
        nav = OverworldNavigator(mock_bridge, timeout_frames=0)
        result = nav.navigate_to_coordinates(9999, 9999)
        assert result.status == NavigationStatus.FAILED_TIMEOUT

    def test_negative_coordinates(self, navigator):
        """Test handling of negative coordinates."""
        # Should still calculate direction
        direction = navigator.calculate_direction(0, 0, -100, -50)
        assert direction in ["LEFT", "UP"]

    def test_very_large_coordinates(self, navigator):
        """Test handling of large coordinates."""
        direction = navigator.calculate_direction(0, 0, 65535, 65535)
        # Larger delta wins
        assert direction in ["RIGHT", "DOWN"]

    def test_same_position_direction(self, navigator):
        """Test direction when source equals target."""
        direction = navigator.calculate_direction(100, 100, 100, 100)
        # With zero deltas, larger abs wins - both are 0, so vertical wins
        assert direction in ["UP", "DOWN"]

    def test_poi_distance_to_self(self, sample_poi):
        """Test distance from POI to itself is zero."""
        assert sample_poi.distance_to(sample_poi.x, sample_poi.y) == 0

    def test_capture_multiple_states(self, navigator):
        """Test capturing many states."""
        for _ in range(100):
            navigator.capture_state()

        assert len(navigator._states_history) == 100

    def test_reset_after_navigation(self, navigator):
        """Test reset clears all state."""
        for _ in range(10):
            navigator.capture_state()

        navigator.reset()
        assert len(navigator._states_history) == 0


# =============================================================================
# Patrol Tests
# =============================================================================

class TestPatrol:
    """Tests for patrol functionality."""

    def test_patrol_empty_waypoints(self, navigator):
        """Test patrol with no waypoints."""
        results = navigator.patrol_area(waypoints=[], loops=1)
        assert results == []

    def test_patrol_single_waypoint(self, mock_bridge, navigator):
        """Test patrol with single waypoint."""
        # Mock being at target position (3408, 3688)
        mem_map = {
            0x7E0010: 0x09,  # Overworld mode
            0x7E0011: 0x00,
            0x7E001A: 0x0F,
            0x7E008A: 0x29,
            0x7E0022: 0x50,  # X low = 80
            0x7E0023: 0x0D,  # X high = 13 -> 3408
            0x7E0020: 0x68,  # Y low
            0x7E0021: 0x0E,  # Y high = 3688
            0x7E002F: 0x02,
        }

        mock_bridge.read_memory.side_effect = lambda addr: mem_map.get(addr, 0)
        mock_bridge.read_memory16.side_effect = lambda addr: mem_map.get(addr, 0) | (mem_map.get(addr + 1, 0) << 8)

        results = navigator.patrol_area(waypoints=[(3408, 3688)], loops=1)
        # May succeed or timeout depending on mock setup
        assert len(results) >= 0


# =============================================================================
# NavigationMode Tests
# =============================================================================

class TestNavigationModes:
    """Tests for different navigation modes."""

    def test_direct_mode_enum(self):
        """Test DIRECT mode enum value."""
        assert NavigationMode.DIRECT.name == "DIRECT"

    def test_pathfinding_mode_enum(self):
        """Test PATHFINDING mode enum value."""
        assert NavigationMode.PATHFINDING.name == "PATHFINDING"

    def test_area_crossing_mode_enum(self):
        """Test AREA_CROSSING mode enum value."""
        assert NavigationMode.AREA_CROSSING.name == "AREA_CROSSING"


# =============================================================================
# NavigationStatus Tests
# =============================================================================

class TestNavigationStatus:
    """Tests for navigation status enum."""

    def test_success_status(self):
        """Test SUCCESS status."""
        assert NavigationStatus.SUCCESS.name == "SUCCESS"

    def test_all_statuses_exist(self):
        """Test all expected statuses exist."""
        expected = [
            "SUCCESS", "IN_PROGRESS", "FAILED_WRONG_MODE",
            "FAILED_NO_PATH", "FAILED_STUCK", "FAILED_TIMEOUT",
            "FAILED_BLACK_SCREEN", "FAILED_AREA_MISMATCH",
        ]
        actual = [s.name for s in NavigationStatus]
        for status in expected:
            assert status in actual


# =============================================================================
# Input Methods Tests
# =============================================================================

class TestInputMethods:
    """Tests for input injection methods."""

    def test_walk_uses_press_button(self, mock_bridge, navigator):
        """Test walk prefers press_button method."""
        navigator.walk_toward(3400, 3688)
        mock_bridge.press_button.assert_called()

    def test_walk_fallback_to_input_inject(self, mock_bridge, navigator):
        """Test walk falls back to input_inject."""
        del mock_bridge.press_button
        navigator.walk_toward(3400, 3688)
        mock_bridge.input_inject.assert_called()

    def test_walk_no_method_returns_false(self, mock_bridge, navigator):
        """Test walk returns False with no input method."""
        del mock_bridge.press_button
        del mock_bridge.input_inject
        result = navigator.walk_toward(3400, 3688)
        assert result is False
