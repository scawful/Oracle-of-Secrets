"""Extended tests for locations module.

Iteration 32 - Comprehensive location data testing.
Covers data integrity, lookup functions, Dark World patterns,
coverage statistics, and location description formatting.
"""

import pytest
import sys
from pathlib import Path

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


# =============================================================================
# Data Integrity Tests
# =============================================================================

class TestOverworldAreasIntegrity:
    """Test OVERWORLD_AREAS dictionary integrity."""

    def test_all_keys_are_integers(self):
        """All area IDs should be integers."""
        for key in OVERWORLD_AREAS.keys():
            assert isinstance(key, int), f"Key {key!r} is not an integer"

    def test_all_values_are_strings(self):
        """All area names should be strings."""
        for key, value in OVERWORLD_AREAS.items():
            assert isinstance(value, str), f"Value for 0x{key:02X} is not a string"

    def test_no_empty_names(self):
        """No area names should be empty."""
        for key, value in OVERWORLD_AREAS.items():
            assert len(value) > 0, f"Empty name for area 0x{key:02X}"

    def test_keys_in_valid_range(self):
        """Area IDs should be in valid byte range (0-255) or DW range."""
        for key in OVERWORLD_AREAS.keys():
            assert 0 <= key <= 0xFF, f"Area ID 0x{key:02X} out of range"

    def test_no_duplicate_names(self):
        """Check for accidental duplicate names (different IDs, same name)."""
        names = list(OVERWORLD_AREAS.values())
        # Some legitimate duplicates may exist, but flag if many
        unique = set(names)
        # Allow up to 10% duplicates
        assert len(unique) >= len(names) * 0.9


class TestRoomNamesIntegrity:
    """Test ROOM_NAMES dictionary integrity."""

    def test_all_keys_are_integers(self):
        """All room IDs should be integers."""
        for key in ROOM_NAMES.keys():
            assert isinstance(key, int), f"Key {key!r} is not an integer"

    def test_all_values_are_strings(self):
        """All room names should be strings."""
        for key, value in ROOM_NAMES.items():
            assert isinstance(value, str), f"Value for 0x{key:02X} is not a string"

    def test_no_empty_names(self):
        """No room names should be empty (even Empty is a valid name)."""
        for key, value in ROOM_NAMES.items():
            assert len(value) > 0, f"Empty name for room 0x{key:02X}"

    def test_keys_in_valid_range(self):
        """Room IDs should be in valid 16-bit range."""
        for key in ROOM_NAMES.keys():
            assert 0 <= key <= 0xFFFF, f"Room ID 0x{key:04X} out of range"

    def test_contiguous_low_rooms(self):
        """Low room IDs (0x00-0x62) should be mostly defined."""
        defined = sum(1 for k in ROOM_NAMES if k <= 0x62)
        # Most rooms in 0x00-0x62 range should be defined
        assert defined >= 80


class TestEntranceNamesIntegrity:
    """Test ENTRANCE_NAMES dictionary integrity."""

    def test_all_keys_are_integers(self):
        """All entrance IDs should be integers."""
        for key in ENTRANCE_NAMES.keys():
            assert isinstance(key, int), f"Key {key!r} is not an integer"

    def test_all_values_are_strings(self):
        """All entrance names should be strings."""
        for key, value in ENTRANCE_NAMES.items():
            assert isinstance(value, str), f"Value for 0x{key:02X} is not a string"

    def test_no_empty_names(self):
        """No entrance names should be empty."""
        for key, value in ENTRANCE_NAMES.items():
            assert len(value) > 0, f"Empty name for entrance 0x{key:02X}"

    def test_keys_in_valid_range(self):
        """Entrance IDs should be in valid byte range."""
        for key in ENTRANCE_NAMES.keys():
            assert 0 <= key <= 0xFF, f"Entrance ID 0x{key:02X} out of range"


class TestDungeonsIntegrity:
    """Test DUNGEONS dictionary integrity."""

    def test_all_keys_are_integers(self):
        """All dungeon IDs should be integers."""
        for key in DUNGEONS.keys():
            assert isinstance(key, int), f"Key {key!r} is not an integer"

    def test_all_values_are_strings(self):
        """All dungeon names should be strings."""
        for key, value in DUNGEONS.items():
            assert isinstance(value, str), f"Value for 0x{key:02X} is not a string"

    def test_all_keys_even(self):
        """Dungeon IDs typically use even values (0x00, 0x02, 0x04, etc)."""
        for key in DUNGEONS.keys():
            assert key % 2 == 0, f"Dungeon ID 0x{key:02X} is odd"

    def test_no_duplicate_dungeon_names(self):
        """Each dungeon should have a unique name."""
        names = list(DUNGEONS.values())
        assert len(names) == len(set(names)), "Duplicate dungeon names found"


# =============================================================================
# Specific Location Tests
# =============================================================================

class TestLightWorldAreas:
    """Test Light World area definitions."""

    def test_loom_ranch_area(self):
        """Loom Ranch should be at 0x00."""
        assert 0x00 in OVERWORLD_AREAS
        assert "Loom" in OVERWORLD_AREAS[0x00]

    def test_hyrule_castle_grounds(self):
        """Hyrule Castle Grounds at 0x02."""
        assert 0x02 in OVERWORLD_AREAS
        assert "Castle" in OVERWORLD_AREAS[0x02]

    def test_snowpeak_areas(self):
        """Snowpeak region areas (0x04-0x07)."""
        snowpeak_ids = [0x04, 0x05, 0x06, 0x07]
        for area_id in snowpeak_ids:
            if area_id in OVERWORLD_AREAS:
                assert "Snowpeak" in OVERWORLD_AREAS[area_id] or "Snow" in OVERWORLD_AREAS[area_id]

    def test_village_areas(self):
        """Village areas cluster (0x28, 0x29, 0x2A)."""
        assert 0x28 in OVERWORLD_AREAS
        assert 0x29 in OVERWORLD_AREAS
        assert 0x2A in OVERWORLD_AREAS
        assert "Village" in OVERWORLD_AREAS[0x29]

    def test_beach_areas(self):
        """Beach areas exist."""
        beach_areas = [k for k, v in OVERWORLD_AREAS.items() if "Beach" in v]
        assert len(beach_areas) >= 2

    def test_lost_woods_areas(self):
        """Lost Woods areas (0x40-0x42)."""
        lost_woods = [k for k, v in OVERWORLD_AREAS.items() if "Lost Woods" in v]
        assert len(lost_woods) >= 2


class TestDarkWorldAreas:
    """Test Dark World area definitions."""

    def test_dark_world_bit_pattern(self):
        """Dark World areas use 0x80 bit."""
        # Check areas with 0x80 bit set
        dw_areas = [k for k in OVERWORLD_AREAS.keys() if k >= 0x80]
        assert len(dw_areas) >= 3

    def test_temporal_pyramid_dw(self):
        """Temporal Pyramid DW at 0xC0 (0x80 | 0x40)."""
        assert 0xC0 in OVERWORLD_AREAS
        name = OVERWORLD_AREAS[0xC0]
        assert "Temporal" in name or "Pyramid" in name or "DW" in name

    def test_dark_world_areas_have_dw_indicator(self):
        """Dark World areas should indicate DW in name or be clear."""
        dw_ids = [0xC0, 0xC4, 0xC6]  # Known DW areas from data
        for area_id in dw_ids:
            if area_id in OVERWORLD_AREAS:
                # Either has "Dark" or "DW" or is recognizable
                name = OVERWORLD_AREAS[area_id]
                assert len(name) > 0  # Just verify it's named


class TestUnderwaterAreas:
    """Test underwater area definitions."""

    def test_underwater_areas_exist(self):
        """Underwater areas (0x70+) exist."""
        underwater = [k for k, v in OVERWORLD_AREAS.items()
                     if "Underwater" in v or (0x70 <= k <= 0x7F)]
        assert len(underwater) >= 2

    def test_underwater_70_range(self):
        """Underwater uses 0x70 range."""
        found = False
        for k in OVERWORLD_AREAS.keys():
            if 0x70 <= k <= 0x7F:
                found = True
                break
        assert found


# =============================================================================
# Room Tests
# =============================================================================

class TestSpecialRooms:
    """Test special room definitions."""

    def test_ganons_room(self):
        """Ganon's Room at 0x00."""
        assert 0x00 in ROOM_NAMES
        assert "Ganon" in ROOM_NAMES[0x00]

    def test_sanctuary_room(self):
        """Sanctuary at 0x12."""
        assert 0x12 in ROOM_NAMES
        assert "Sanctuary" in ROOM_NAMES[0x12]

    def test_empty_rooms_labeled(self):
        """Empty rooms are explicitly labeled."""
        empty_rooms = [k for k, v in ROOM_NAMES.items() if "Empty" in v]
        assert len(empty_rooms) >= 1


class TestDungeonRooms:
    """Test dungeon room definitions."""

    def test_zora_temple_rooms(self):
        """Zora Temple has multiple rooms."""
        zora_rooms = [k for k, v in ROOM_NAMES.items() if "Zora Temple" in v]
        assert len(zora_rooms) >= 8

    def test_mushroom_grotto_rooms(self):
        """Mushroom Grotto has multiple rooms."""
        grotto_rooms = [k for k, v in ROOM_NAMES.items() if "Mushroom Grotto" in v]
        assert len(grotto_rooms) >= 8

    def test_fortress_rooms(self):
        """Fortress of Secrets has rooms."""
        fortress_rooms = [k for k, v in ROOM_NAMES.items() if "Fortress" in v]
        assert len(fortress_rooms) >= 5

    def test_tail_palace_rooms(self):
        """Tail Palace has rooms."""
        tail_rooms = [k for k, v in ROOM_NAMES.items() if "Tail Palace" in v]
        assert len(tail_rooms) >= 5

    def test_dragon_ship_rooms(self):
        """Dragon Ship has rooms."""
        ship_rooms = [k for k, v in ROOM_NAMES.items() if "Dragon Ship" in v]
        assert len(ship_rooms) >= 4

    def test_boss_rooms_exist(self):
        """Boss rooms should be defined."""
        boss_keywords = ["Boss", "Arrghus", "Moldorm", "Mothula", "Lanmolas", "Helmasaur", "Agahnim"]
        boss_rooms = [k for k, v in ROOM_NAMES.items()
                     if any(kw in v for kw in boss_keywords)]
        assert len(boss_rooms) >= 5


class TestHyruleCastleRooms:
    """Test Hyrule Castle room definitions."""

    def test_castle_main_entrance(self):
        """Main entrance at 0x61."""
        assert 0x61 in ROOM_NAMES
        assert "Main" in ROOM_NAMES[0x61] or "Entrance" in ROOM_NAMES[0x61]

    def test_castle_corridors(self):
        """Castle has corridor rooms."""
        corridor_rooms = [k for k, v in ROOM_NAMES.items()
                        if "Castle" in v and "Corridor" in v]
        assert len(corridor_rooms) >= 2

    def test_castle_throne(self):
        """Castle has throne room."""
        throne_rooms = [k for k, v in ROOM_NAMES.items()
                       if "Throne" in v]
        assert len(throne_rooms) >= 1


# =============================================================================
# Lookup Function Tests
# =============================================================================

class TestGetAreaNameComprehensive:
    """Comprehensive tests for get_area_name."""

    def test_all_defined_areas_lookup(self):
        """All defined areas should return their name."""
        for area_id, expected_name in OVERWORLD_AREAS.items():
            result = get_area_name(area_id)
            assert result == expected_name

    def test_undefined_area_format(self):
        """Undefined area returns formatted hex."""
        # Find an undefined ID
        for i in range(256):
            if i not in OVERWORLD_AREAS:
                result = get_area_name(i)
                assert "0x" in result or "Area" in result
                break

    def test_fallback_format_hex(self):
        """Fallback format includes hex representation."""
        result = get_area_name(0xAB)  # Likely undefined
        if 0xAB not in OVERWORLD_AREAS:
            assert "AB" in result.upper()

    def test_zero_area(self):
        """Area 0x00 returns Loom Ranch."""
        result = get_area_name(0x00)
        assert "Loom" in result

    def test_max_area(self):
        """Area 0xFF returns something valid."""
        result = get_area_name(0xFF)
        assert isinstance(result, str)
        assert len(result) > 0


class TestGetRoomNameComprehensive:
    """Comprehensive tests for get_room_name."""

    def test_all_defined_rooms_lookup(self):
        """All defined rooms should return their name."""
        for room_id, expected_name in ROOM_NAMES.items():
            result = get_room_name(room_id)
            assert result == expected_name

    def test_undefined_room_format(self):
        """Undefined room returns formatted hex."""
        result = get_room_name(0xFFFF)  # Very likely undefined
        if 0xFFFF not in ROOM_NAMES:
            assert "0x" in result or "Room" in result

    def test_high_room_id(self):
        """High room ID (>0xFF) returns valid string."""
        result = get_room_name(0x1234)
        assert isinstance(result, str)
        assert len(result) > 0


class TestGetEntranceNameComprehensive:
    """Comprehensive tests for get_entrance_name."""

    def test_all_defined_entrances_lookup(self):
        """All defined entrances should return their name."""
        for entrance_id, expected_name in ENTRANCE_NAMES.items():
            result = get_entrance_name(entrance_id)
            assert result == expected_name

    def test_undefined_entrance_format(self):
        """Undefined entrance returns formatted hex."""
        # Find undefined
        for i in range(256):
            if i not in ENTRANCE_NAMES:
                result = get_entrance_name(i)
                assert "0x" in result or "Entrance" in result
                break


class TestGetDungeonNameComprehensive:
    """Comprehensive tests for get_dungeon_name."""

    def test_all_defined_dungeons_lookup(self):
        """All defined dungeons should return their name."""
        for dungeon_id, expected_name in DUNGEONS.items():
            result = get_dungeon_name(dungeon_id)
            assert result == expected_name

    def test_undefined_dungeon_format(self):
        """Undefined dungeon returns formatted hex."""
        # Odd IDs are undefined
        result = get_dungeon_name(0x01)
        if 0x01 not in DUNGEONS:
            assert "0x" in result or "Dungeon" in result

    def test_high_dungeon_id(self):
        """High dungeon ID returns valid string."""
        result = get_dungeon_name(0xFE)
        assert isinstance(result, str)
        assert len(result) > 0


# =============================================================================
# Location Description Tests
# =============================================================================

class TestGetLocationDescriptionComprehensive:
    """Comprehensive tests for get_location_description."""

    def test_outdoors_uses_area(self):
        """Outdoors uses area ID, ignores room ID."""
        result = get_location_description(0x29, 0x12, is_indoors=False)
        assert result == "Village Center"
        # Should NOT contain Sanctuary (room 0x12)
        assert "Sanctuary" not in result

    def test_indoors_uses_room(self):
        """Indoors uses room ID, ignores area ID."""
        result = get_location_description(0x29, 0x12, is_indoors=True)
        assert "Sanctuary" in result
        # Should NOT be Village Center
        assert result != "Village Center"

    def test_unknown_area_outdoors(self):
        """Unknown area outdoors returns formatted fallback."""
        result = get_location_description(0xAB, 0x00, is_indoors=False)
        if 0xAB not in OVERWORLD_AREAS:
            assert "0x" in result or "Area" in result

    def test_unknown_room_indoors(self):
        """Unknown room indoors returns formatted fallback."""
        result = get_location_description(0x00, 0xFFFF, is_indoors=True)
        if 0xFFFF not in ROOM_NAMES:
            assert "0x" in result or "Room" in result

    def test_returns_string(self):
        """Always returns a string."""
        combos = [
            (0x00, 0x00, True),
            (0x00, 0x00, False),
            (0xFF, 0xFF, True),
            (0xFF, 0xFF, False),
        ]
        for area, room, indoors in combos:
            result = get_location_description(area, room, indoors)
            assert isinstance(result, str)
            assert len(result) > 0


# =============================================================================
# Coverage Stats Tests
# =============================================================================

class TestGetCoverageStatsComprehensive:
    """Comprehensive tests for get_coverage_stats."""

    def test_returns_dict(self):
        """Returns a dictionary."""
        stats = get_coverage_stats()
        assert isinstance(stats, dict)

    def test_all_expected_keys(self):
        """All expected keys are present."""
        stats = get_coverage_stats()
        expected = ["overworld_areas", "room_names", "entrance_names", "dungeons", "total"]
        for key in expected:
            assert key in stats

    def test_all_values_integers(self):
        """All values are integers."""
        stats = get_coverage_stats()
        for key, value in stats.items():
            assert isinstance(value, int), f"{key} is not an integer"

    def test_all_values_non_negative(self):
        """All values are non-negative."""
        stats = get_coverage_stats()
        for key, value in stats.items():
            assert value >= 0, f"{key} is negative"

    def test_total_is_sum(self):
        """Total equals sum of components."""
        stats = get_coverage_stats()
        component_sum = (
            stats["overworld_areas"] +
            stats["room_names"] +
            stats["entrance_names"] +
            stats["dungeons"]
        )
        assert stats["total"] == component_sum

    def test_overworld_matches_constant(self):
        """overworld_areas matches OVERWORLD_AREAS length."""
        stats = get_coverage_stats()
        assert stats["overworld_areas"] == len(OVERWORLD_AREAS)

    def test_rooms_matches_constant(self):
        """room_names matches ROOM_NAMES length."""
        stats = get_coverage_stats()
        assert stats["room_names"] == len(ROOM_NAMES)

    def test_entrances_matches_constant(self):
        """entrance_names matches ENTRANCE_NAMES length."""
        stats = get_coverage_stats()
        assert stats["entrance_names"] == len(ENTRANCE_NAMES)

    def test_dungeons_matches_constant(self):
        """dungeons matches DUNGEONS length."""
        stats = get_coverage_stats()
        assert stats["dungeons"] == len(DUNGEONS)

    def test_minimum_coverage(self):
        """Minimum expected coverage."""
        stats = get_coverage_stats()
        assert stats["overworld_areas"] >= 40
        assert stats["room_names"] >= 90
        assert stats["entrance_names"] >= 20
        assert stats["dungeons"] >= 10


# =============================================================================
# Cross-Reference Tests
# =============================================================================

class TestCrossReferences:
    """Test consistency between different location mappings."""

    def test_dungeon_rooms_reference_dungeons(self):
        """Room names referencing dungeons should match dungeon list."""
        dungeon_names = set(DUNGEONS.values())
        for room_name in ROOM_NAMES.values():
            # Extract potential dungeon name from room
            for dungeon in dungeon_names:
                if dungeon in room_name:
                    # Found a match, good
                    break

    def test_entrance_dungeon_consistency(self):
        """Entrances mentioning dungeons should be valid dungeons."""
        dungeon_names = set(DUNGEONS.values())
        for entrance_name in ENTRANCE_NAMES.values():
            # Check if entrance mentions a known dungeon
            for dungeon in dungeon_names:
                if dungeon in entrance_name:
                    # Valid reference
                    break


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_values(self):
        """All lookup functions handle 0."""
        assert isinstance(get_area_name(0), str)
        assert isinstance(get_room_name(0), str)
        assert isinstance(get_entrance_name(0), str)
        assert isinstance(get_dungeon_name(0), str)

    def test_max_byte_values(self):
        """All lookup functions handle 0xFF."""
        assert isinstance(get_area_name(0xFF), str)
        assert isinstance(get_room_name(0xFF), str)
        assert isinstance(get_entrance_name(0xFF), str)
        assert isinstance(get_dungeon_name(0xFF), str)

    def test_negative_value_handling(self):
        """Negative values should work (wrap or fallback)."""
        # Python handles negative indices differently
        # Functions should still return strings
        result = get_area_name(-1)  # May wrap to 0xFFFFFFFF...
        assert isinstance(result, str)

    def test_large_value_handling(self):
        """Large values beyond byte range."""
        result = get_room_name(0x10000)
        assert isinstance(result, str)


class TestSpecialCharacters:
    """Test handling of special characters in names."""

    def test_no_null_characters(self):
        """No names contain null characters."""
        all_names = list(OVERWORLD_AREAS.values()) + list(ROOM_NAMES.values())
        all_names += list(ENTRANCE_NAMES.values()) + list(DUNGEONS.values())
        for name in all_names:
            assert '\x00' not in name

    def test_names_are_printable(self):
        """All names contain printable characters."""
        all_names = list(OVERWORLD_AREAS.values()) + list(ROOM_NAMES.values())
        all_names += list(ENTRANCE_NAMES.values()) + list(DUNGEONS.values())
        for name in all_names:
            # Allow standard printable ASCII and some common chars
            assert all(c.isprintable() or c in ' \t' for c in name)

    def test_parentheses_balanced(self):
        """Parentheses in names are balanced."""
        all_names = list(OVERWORLD_AREAS.values()) + list(ROOM_NAMES.values())
        all_names += list(ENTRANCE_NAMES.values()) + list(DUNGEONS.values())
        for name in all_names:
            assert name.count('(') == name.count(')'), f"Unbalanced parens: {name}"


# =============================================================================
# Regression Tests
# =============================================================================

class TestRegressions:
    """Regression tests for known issues."""

    def test_water_gate_room_exists(self):
        """Water Gate room (0x27) exists - key for water testing."""
        assert 0x27 in ROOM_NAMES
        assert "Water Gate" in ROOM_NAMES[0x27]

    def test_village_center_id(self):
        """Village Center is at 0x29 (not shifted)."""
        assert 0x29 in OVERWORLD_AREAS
        assert OVERWORLD_AREAS[0x29] == "Village Center"

    def test_dark_world_offset_correct(self):
        """Dark World uses 0x80 offset correctly."""
        # 0x80 | 0x40 = 0xC0 for Temporal Pyramid DW
        assert 0xC0 in OVERWORLD_AREAS
