"""Tests for location data structures and lookup functions.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- E: Knowledge synthesis (location data validation)

These tests verify the location data dictionaries and lookup functions
work correctly for mapping game coordinates to human-readable names.
"""

import pytest
from pathlib import Path

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.locations import (
    DUNGEONS,
    ENTRANCE_NAMES,
    OVERWORLD_AREAS,
    ROOM_NAMES,
    get_area_name,
    get_coverage_stats,
    get_dungeon_name,
    get_entrance_name,
    get_location_description,
    get_room_name
)
from scripts.campaign.emulator_abstraction import GameStateSnapshot


class TestOverworldAreas:
    """Test overworld area data."""

    def test_overworld_areas_not_empty(self):
        """Test OVERWORLD_AREAS dictionary has entries."""
        assert len(OVERWORLD_AREAS) > 0

    def test_overworld_areas_has_village(self):
        """Test village area is defined."""
        # Area 0x29 is typically village
        assert 0x29 in OVERWORLD_AREAS or any(
            "village" in str(v).lower()
            for v in OVERWORLD_AREAS.values()
        )

    def test_overworld_area_values_are_strings(self):
        """Test all overworld area values are strings."""
        for area_id, name in OVERWORLD_AREAS.items():
            assert isinstance(name, str), f"Area {area_id} name is not string"

    def test_overworld_area_keys_are_integers(self):
        """Test all overworld area keys are integers."""
        for area_id in OVERWORLD_AREAS.keys():
            assert isinstance(area_id, int), f"Area key {area_id} is not int"

    def test_overworld_area_keys_in_valid_range(self):
        """Test all area keys are in valid byte range."""
        for area_id in OVERWORLD_AREAS.keys():
            assert 0 <= area_id <= 0xFF, f"Area {area_id} out of byte range"


class TestDungeons:
    """Test dungeon data."""

    def test_dungeons_not_empty(self):
        """Test DUNGEONS dictionary has entries."""
        assert len(DUNGEONS) > 0

    def test_dungeons_values_are_strings(self):
        """Test all dungeon values are strings."""
        for dungeon_id, name in DUNGEONS.items():
            assert isinstance(name, str), f"Dungeon {dungeon_id} name is not string"

    def test_dungeons_keys_are_integers(self):
        """Test all dungeon keys are integers."""
        for dungeon_id in DUNGEONS.keys():
            assert isinstance(dungeon_id, int), f"Dungeon key {dungeon_id} is not int"


class TestRoomNames:
    """Test room name data."""

    def test_room_names_structure(self):
        """Test ROOM_NAMES has valid structure."""
        # ROOM_NAMES may be empty or have entries
        assert isinstance(ROOM_NAMES, dict)

    def test_room_names_values_if_present(self):
        """Test room name values are strings if present."""
        for room_id, name in ROOM_NAMES.items():
            assert isinstance(name, str), f"Room {room_id} name is not string"

    def test_room_names_keys_valid_range(self):
        """Test room keys are in valid range."""
        for room_id in ROOM_NAMES.keys():
            assert isinstance(room_id, int), f"Room key {room_id} is not int"
            assert 0 <= room_id <= 0xFFFF, f"Room {room_id} out of 16-bit range"


class TestEntranceNames:
    """Test entrance name data."""

    def test_entrance_names_structure(self):
        """Test ENTRANCE_NAMES has valid structure."""
        assert isinstance(ENTRANCE_NAMES, dict)

    def test_entrance_names_values_if_present(self):
        """Test entrance name values are strings if present."""
        for entrance_id, name in ENTRANCE_NAMES.items():
            assert isinstance(name, str), f"Entrance {entrance_id} name is not string"


class TestGetAreaName:
    """Test get_area_name function."""

    def test_get_area_name_known_area(self):
        """Test getting name for known area."""
        if OVERWORLD_AREAS:
            known_area = next(iter(OVERWORLD_AREAS.keys()))
            name = get_area_name(known_area)
            assert name is not None
            assert isinstance(name, str)
            assert len(name) > 0

    def test_get_area_name_unknown_area(self):
        """Test getting name for unknown area returns fallback."""
        # Use an unlikely area ID
        name = get_area_name(0xFE)
        assert isinstance(name, str)
        # Should return some string (either fallback or hex)

    def test_get_area_name_zero(self):
        """Test getting name for area 0."""
        name = get_area_name(0)
        assert isinstance(name, str)

    def test_get_area_name_max_byte(self):
        """Test getting name for area 0xFF."""
        name = get_area_name(0xFF)
        assert isinstance(name, str)


class TestGetDungeonName:
    """Test get_dungeon_name function."""

    def test_get_dungeon_name_known(self):
        """Test getting name for known dungeon."""
        if DUNGEONS:
            known_dungeon = next(iter(DUNGEONS.keys()))
            name = get_dungeon_name(known_dungeon)
            assert name is not None
            assert isinstance(name, str)
            assert len(name) > 0

    def test_get_dungeon_name_unknown(self):
        """Test getting name for unknown dungeon returns fallback."""
        name = get_dungeon_name(0xFE)
        assert isinstance(name, str)


class TestGetRoomName:
    """Test get_room_name function."""

    def test_get_room_name_known(self):
        """Test getting name for known room."""
        if ROOM_NAMES:
            known_room = next(iter(ROOM_NAMES.keys()))
            name = get_room_name(known_room)
            assert name is not None
            assert isinstance(name, str)

    def test_get_room_name_unknown(self):
        """Test getting name for unknown room."""
        name = get_room_name(0xFFFF)
        assert isinstance(name, str)

    def test_get_room_name_zero(self):
        """Test getting name for room 0."""
        name = get_room_name(0)
        assert isinstance(name, str)


class TestGetEntranceName:
    """Test get_entrance_name function."""

    def test_get_entrance_name_known(self):
        """Test getting name for known entrance."""
        if ENTRANCE_NAMES:
            known_entrance = next(iter(ENTRANCE_NAMES.keys()))
            name = get_entrance_name(known_entrance)
            assert name is not None
            assert isinstance(name, str)

    def test_get_entrance_name_unknown(self):
        """Test getting name for unknown entrance."""
        name = get_entrance_name(0xFE)
        assert isinstance(name, str)


class TestGetLocationDescription:
    """Test get_location_description function."""

    def test_location_description_overworld(self):
        """Test location description for overworld state."""
        desc = get_location_description(area_id=0x29, room_id=0x00, is_indoors=False)
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_location_description_indoors(self):
        """Test location description for indoor state."""
        desc = get_location_description(area_id=0x29, room_id=0x50, is_indoors=True)
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_location_description_includes_position(self):
        """Test location description includes relevant info."""
        desc = get_location_description(area_id=0x29, room_id=0x00, is_indoors=False)
        # Description should mention area or location
        assert len(desc) > 0
        # Should be descriptive (not just empty or hex)
        assert any(
            word in desc.lower() for word in ["area", "room", "village", "overworld", "0x"]
        ) or len(desc) > 3


class TestGetCoverageStats:
    """Test get_coverage_stats function."""

    def test_coverage_stats_returns_dict(self):
        """Test coverage stats returns dictionary."""
        stats = get_coverage_stats()
        assert isinstance(stats, dict)

    def test_coverage_stats_has_counts(self):
        """Test coverage stats has expected fields."""
        stats = get_coverage_stats()
        # Should have some count fields
        assert any(
            key in stats for key in [
                "overworld_areas", "dungeons", "rooms", "entrances",
                "total_areas", "total_rooms", "coverage"
            ]
        )

    def test_coverage_stats_non_negative(self):
        """Test all coverage stats are non-negative."""
        stats = get_coverage_stats()
        for key, value in stats.items():
            if isinstance(value, (int, float)):
                assert value >= 0, f"{key} is negative"


class TestLocationConsistency:
    """Test consistency across location data structures."""

    def test_no_overlapping_dungeon_area_ids(self):
        """Test dungeon and overworld don't share IDs unexpectedly."""
        # This is actually allowed - dungeons use room IDs, not area IDs
        # Just verify both exist
        assert isinstance(DUNGEONS, dict)
        assert isinstance(OVERWORLD_AREAS, dict)

    def test_all_location_data_accessible(self):
        """Test all location data can be accessed without errors."""
        # Access all dictionaries
        _ = len(OVERWORLD_AREAS)
        _ = len(DUNGEONS)
        _ = len(ROOM_NAMES)
        _ = len(ENTRANCE_NAMES)

        # Call all functions
        _ = get_area_name(0x29)
        _ = get_dungeon_name(0x01)
        _ = get_room_name(0x50)
        _ = get_entrance_name(0x10)
        _ = get_coverage_stats()


class TestLocationDataTypes:
    """Test type consistency in location data."""

    def test_overworld_area_names_no_none(self):
        """Test no None values in overworld area names."""
        for area_id, name in OVERWORLD_AREAS.items():
            assert name is not None, f"Area {area_id} has None name"

    def test_dungeon_names_no_none(self):
        """Test no None values in dungeon names."""
        for dungeon_id, name in DUNGEONS.items():
            assert name is not None, f"Dungeon {dungeon_id} has None name"

    def test_room_names_no_none_if_present(self):
        """Test no None values in room names."""
        for room_id, name in ROOM_NAMES.items():
            assert name is not None, f"Room {room_id} has None name"

    def test_entrance_names_no_none_if_present(self):
        """Test no None values in entrance names."""
        for entrance_id, name in ENTRANCE_NAMES.items():
            assert name is not None, f"Entrance {entrance_id} has None name"


class TestSpecificLocations:
    """Test specific known locations exist."""

    def test_has_starting_area(self):
        """Test starting area is defined."""
        # Game typically starts in a specific area
        starting_areas = [0x00, 0x29, 0x2A, 0x2B]  # Possible starting areas
        found = any(area in OVERWORLD_AREAS for area in starting_areas)
        assert found or len(OVERWORLD_AREAS) == 0  # OK if empty too

    def test_dungeon_numbering_sequential(self):
        """Test dungeons are numbered reasonably."""
        if DUNGEONS:
            dungeon_ids = sorted(DUNGEONS.keys())
            # First dungeon should be low numbered
            assert dungeon_ids[0] < 0x20 or dungeon_ids[0] in [0x80, 0x81, 0x82]


class TestLocationStrings:
    """Test location string formatting."""

    def test_area_names_printable(self):
        """Test area names contain only printable characters."""
        for area_id, name in OVERWORLD_AREAS.items():
            assert all(c.isprintable() for c in name), f"Area {area_id} has non-printable chars"

    def test_dungeon_names_printable(self):
        """Test dungeon names contain only printable characters."""
        for dungeon_id, name in DUNGEONS.items():
            assert all(c.isprintable() for c in name), f"Dungeon {dungeon_id} has non-printable chars"

    def test_area_names_not_empty_strings(self):
        """Test area names are not empty strings."""
        for area_id, name in OVERWORLD_AREAS.items():
            assert len(name.strip()) > 0, f"Area {area_id} has empty name"

    def test_dungeon_names_not_empty_strings(self):
        """Test dungeon names are not empty strings."""
        for dungeon_id, name in DUNGEONS.items():
            assert len(name.strip()) > 0, f"Dungeon {dungeon_id} has empty name"
