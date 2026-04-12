"""Tests for locations module.

Verifies location data accuracy and lookup functions.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.locations import (
    OVERWORLD_AREAS,
    ROOM_NAMES,
    ENTRANCE_NAMES,
    DUNGEONS,
    get_area_name,
    get_room_name,
    get_entrance_name,
    get_dungeon_name,
    get_location_description,
    get_coverage_stats,
)


class TestOverworldAreas:
    """Tests for overworld area data."""

    def test_village_center_exists(self):
        """Verify Village Center is defined."""
        assert 0x29 in OVERWORLD_AREAS
        assert OVERWORLD_AREAS[0x29] == "Village Center"

    def test_lost_woods_exists(self):
        """Verify Lost Woods area is properly defined at 0x40."""
        assert 0x40 in OVERWORLD_AREAS
        assert "Lost Woods" in OVERWORLD_AREAS[0x40]

    def test_temporal_pyramid_dark_world(self):
        """Verify Dark World Temporal Pyramid uses 0xC0 (0x80 | 0x40)."""
        assert 0xC0 in OVERWORLD_AREAS
        assert "Temporal Pyramid" in OVERWORLD_AREAS[0xC0]

    def test_dungeon_areas_exist(self):
        """Verify key dungeon exterior areas."""
        # Tail Palace area
        assert 0x2F in OVERWORLD_AREAS or "Tail" in str(OVERWORLD_AREAS.values())

    def test_area_count(self):
        """Verify reasonable number of areas defined."""
        # Game has ~64 overworld areas
        assert len(OVERWORLD_AREAS) >= 30


class TestRoomNames:
    """Tests for indoor room data."""

    def test_zora_temple_water_gate(self):
        """Verify Water Gate room is defined (key test room)."""
        assert 0x27 in ROOM_NAMES
        assert "Water Gate" in ROOM_NAMES[0x27]

    def test_sanctuary_exists(self):
        """Verify Sanctuary is defined."""
        assert 0x12 in ROOM_NAMES
        assert "Sanctuary" in ROOM_NAMES[0x12]

    def test_hyrule_castle_rooms(self):
        """Verify Hyrule Castle rooms are defined."""
        castle_rooms = [id for id, name in ROOM_NAMES.items() if "Castle" in name]
        assert len(castle_rooms) >= 5

    def test_room_count(self):
        """Verify reasonable number of rooms defined."""
        # Game has ~200 rooms
        assert len(ROOM_NAMES) >= 50


class TestEntranceNames:
    """Tests for entrance data."""

    def test_links_house(self):
        """Verify Link's House entrance."""
        assert 0x00 in ENTRANCE_NAMES
        assert "Link" in ENTRANCE_NAMES[0x00]

    def test_sanctuary_entrance(self):
        """Verify Sanctuary entrance."""
        assert 0x02 in ENTRANCE_NAMES
        assert "Sanctuary" in ENTRANCE_NAMES[0x02]

    def test_entrance_count(self):
        """Verify reasonable entrance count."""
        assert len(ENTRANCE_NAMES) >= 20


class TestDungeons:
    """Tests for dungeon data."""

    def test_zora_temple(self):
        """Verify Zora Temple is defined."""
        assert 0x06 in DUNGEONS
        assert "Zora Temple" in DUNGEONS[0x06]

    def test_mushroom_grotto(self):
        """Verify Mushroom Grotto is defined."""
        assert 0x0A in DUNGEONS
        assert "Mushroom Grotto" in DUNGEONS[0x0A]

    def test_all_main_dungeons(self):
        """Verify all main dungeons are defined."""
        expected = [
            "Hyrule Castle",
            "Zora Temple",
            "Kalyxo Castle",
            "Mushroom Grotto",
            "Fortress of Secrets",
            "Tail Palace",
            "Dragon Ship",
            "Shrine of Power",
        ]
        dungeon_names = list(DUNGEONS.values())
        for name in expected:
            assert any(name in d for d in dungeon_names), f"Missing: {name}"


class TestGetAreaName:
    """Tests for get_area_name function."""

    def test_known_area(self):
        """Test lookup of known area."""
        assert get_area_name(0x29) == "Village Center"

    def test_unknown_area(self):
        """Test fallback for unknown area."""
        result = get_area_name(0xFF)
        assert "0xFF" in result or "FF" in result.upper()

    def test_zero_area(self):
        """Test area ID 0x00."""
        result = get_area_name(0x00)
        # Either has a name or formatted fallback
        assert len(result) > 0


class TestGetRoomName:
    """Tests for get_room_name function."""

    def test_known_room(self):
        """Test lookup of known room."""
        result = get_room_name(0x27)
        assert "Zora Temple" in result

    def test_unknown_room(self):
        """Test fallback for unknown room."""
        result = get_room_name(0xFE)
        assert "0xFE" in result or "FE" in result.upper()


class TestGetEntranceName:
    """Tests for get_entrance_name function."""

    def test_known_entrance(self):
        """Test lookup of known entrance."""
        result = get_entrance_name(0x00)
        assert "Link" in result

    def test_unknown_entrance(self):
        """Test fallback for unknown entrance."""
        result = get_entrance_name(0xFD)
        assert "0xFD" in result or "FD" in result.upper()


class TestGetDungeonName:
    """Tests for get_dungeon_name function."""

    def test_known_dungeon(self):
        """Test lookup of known dungeon."""
        assert get_dungeon_name(0x06) == "Zora Temple"

    def test_unknown_dungeon(self):
        """Test fallback for unknown dungeon."""
        result = get_dungeon_name(0xFC)
        assert "0xFC" in result or "FC" in result.upper()


class TestGetLocationDescription:
    """Tests for get_location_description function."""

    def test_overworld_description(self):
        """Test outdoor location description."""
        result = get_location_description(0x29, 0x00, is_indoors=False)
        assert result == "Village Center"

    def test_indoor_description(self):
        """Test indoor location description."""
        result = get_location_description(0x00, 0x27, is_indoors=True)
        assert "Zora Temple" in result

    def test_indoor_uses_room_not_area(self):
        """Verify indoor mode uses room ID, not area ID."""
        result = get_location_description(0x29, 0x12, is_indoors=True)
        # Should return Sanctuary (room 0x12), not Village Center (area 0x29)
        assert "Sanctuary" in result


class TestGetCoverageStats:
    """Tests for coverage statistics."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        stats = get_coverage_stats()
        assert isinstance(stats, dict)

    def test_has_all_keys(self):
        """Test that all expected keys are present."""
        stats = get_coverage_stats()
        assert "overworld_areas" in stats
        assert "room_names" in stats
        assert "entrance_names" in stats
        assert "dungeons" in stats
        assert "total" in stats

    def test_total_is_sum(self):
        """Test that total equals sum of parts."""
        stats = get_coverage_stats()
        expected = (
            stats["overworld_areas"] +
            stats["room_names"] +
            stats["entrance_names"] +
            stats["dungeons"]
        )
        assert stats["total"] == expected

    def test_reasonable_coverage(self):
        """Test that we have reasonable coverage."""
        stats = get_coverage_stats()
        # Per the summary from earlier: ~194 entries
        assert stats["total"] >= 150
        assert stats["overworld_areas"] >= 40
        assert stats["room_names"] >= 90
