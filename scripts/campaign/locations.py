"""Location data for Oracle of Secrets.

Comprehensive mapping of area IDs and room IDs to human-readable names.
Derived from Docs/Technical/Sheets/Oracle of Secrets Data Sheet - Rooms and Entrances.csv

Campaign Goals Supported:
- D.1: Game state parser (location awareness)
- E.1: Dense knowledge graph

Usage:
    from scripts.campaign.locations import get_area_name, get_room_name

    area_name = get_area_name(0x29)  # "Village Center"
    room_name = get_room_name(0x27)  # "Zora Temple (Water Gate)"
"""

from typing import Dict, Optional


# =============================================================================
# Overworld Area Names
# =============================================================================
# Format: area_id -> area_name
# Area IDs are 8-bit values from $7E008A

OVERWORLD_AREAS: Dict[int, str] = {
    # Light World - Ranch/Village Region
    0x00: "Loom Ranch",
    0x01: "Loom Ranch East",
    0x02: "Hyrule Castle Grounds",
    0x03: "Hyrule Castle North",
    0x04: "Snowpeak West",
    0x05: "Snowpeak Central",
    0x06: "Snowpeak (Glacia Estate)",
    0x07: "Snowpeak East",

    # Light World - Forest/Pond Region
    0x0A: "Hotel Area",
    0x0B: "Kalyxo Castle Area",
    0x0D: "Witch Forest",
    0x0E: "Hall of Secrets Area",
    0x0F: "Southern Forest",

    0x10: "Toadstool Woods (Mushroom Grotto)",
    0x11: "Ranch Fields",
    0x15: "Kalyxo Pond",
    0x16: "Dragon Ship Cliff",
    0x18: "Toadstool Woods",

    # Light World - Main Areas
    0x1D: "East Castle Field",
    0x1E: "Zora Sanctuary",
    0x23: "Wayward Village",
    0x25: "Kalyxo River",

    0x28: "Village South",
    0x29: "Village Center",
    0x2A: "Village East",
    0x2D: "Tail Pond",
    0x2E: "Tail Path",
    0x2F: "Tail Palace Area",

    0x30: "Dragon Ship Harbor",
    0x32: "Maku Beach",
    0x33: "Loom Beach",
    0x36: "Goron Desert",

    0x38: "Ranch Area",
    0x39: "Ranch Path",

    # Light World - Lost Woods/Mountain
    0x40: "Lost Woods Entrance",
    0x41: "Lost Woods Interior",
    0x42: "Lost Woods Deep",

    0x43: "Temporal Pyramid East",

    0x48: "Beach North",
    0x49: "Beach South",

    0x4B: "Shrine of Power Exterior",

    0x50: "Mountain Path",
    0x51: "Mountain Summit",

    # Dark World
    0x56: "Dark World (Angry Brothers)",
    0x57: "Final Area (Dragon Ship DW)",
    0x5B: "Dark World Church Area",
    0x5E: "Fortress Area",

    # Note: 0x40 is Lost Woods Entrance in Light World
    # Dark World areas use different bits - checking game data
    0x80 | 0x40: "Temporal Pyramid (DW)",  # DW 0x40 area
    0x80 | 0x44: "Dark World Conveyor Area",  # DW 0x44
    0x80 | 0x46: "Dark World Maze Area",  # DW 0x46

    0x70: "Underwater West",
    0x75: "Underwater (Tail Palace)",
    0x7A: "Underwater (Kalyxo)",
}


# =============================================================================
# Indoor Room Names
# =============================================================================
# Format: room_id -> room_name
# Room IDs are typically from $7E00A4 (16-bit) or $7E00A0 (layout)

ROOM_NAMES: Dict[int, str] = {
    # Special/System Rooms
    0x00: "Ganon's Room",
    0x01: "Hyrule Castle (North Corridor)",
    0x02: "Behind Sanctuary (Switch)",
    0x03: "Houlihan",
    0x04: "Dragon Ship (Crysta-Roller)",
    0x05: "Empty",

    # Dungeon/Temple Rooms
    0x06: "Zora Temple (Arrghus Boss)",
    0x07: "Tower of Hera (Moldorm Boss)",
    0x08: "Cave (Healing Fairy)",
    0x09: "Mushroom Grotto",
    0x0A: "Mushroom Grotto (Stalfos Trap)",
    0x0B: "Mushroom Grotto (Turtle)",
    0x0C: "Fortress of Secrets (Entrance)",
    0x0D: "Fortress of Secrets (Agahnim2 Boss)",
    0x0E: "Tail Palace (Entrance)",
    0x0F: "Empty Clone",

    0x10: "Ganon Evacuation Route",
    0x11: "Hyrule Castle (Bombable Stock)",
    0x12: "Sanctuary",
    0x13: "Dragon Ship (Hokku-Bokku Key 2)",
    0x14: "Dragon Ship (Big Key)",
    0x15: "Dragon Ship",
    0x16: "Zora Temple (Swimming Treadmill)",
    0x17: "Tower of Hera (Moldorm Fall)",
    0x18: "Cave",
    0x19: "Mushroom Grotto (Dark Maze)",
    0x1A: "Mushroom Grotto (Big Chest)",
    0x1B: "Mushroom Grotto (Mimics / Moving Wall)",
    0x1C: "Fortress of Secrets (Ice Armos)",
    0x1D: "Fortress of Secrets (Final Hallway)",
    0x1E: "Tail Palace (Bomb Floor / Bari)",
    0x1F: "Tail Palace (Pengator / Big Key)",

    0x20: "Agahnim's Tower (Agahnim Boss)",
    0x21: "Hyrule Castle (Key-rat)",
    0x22: "Hyrule Castle (Sewer Text Trigger)",
    0x23: "Dragon Ship (West Exit to Balcony)",
    0x24: "Dragon Ship (Double Hokku-Bokku / Big Chest)",
    0x25: "Empty Clone",
    0x26: "Zora Temple (Statue)",
    0x27: "Zora Temple (Water Gate)",  # Key room for water collision testing
    0x28: "Zora Temple (Entrance)",
    0x29: "Kalyxo Castle (Mothula Boss)",
    0x2A: "Mushroom Grotto (Big Hub)",
    0x2B: "Mushroom Grotto (Map Chest / Fairy)",
    0x2C: "Cave",
    0x2D: "Empty Clone",
    0x2E: "Tail Palace (Compass)",
    0x2F: "Cave (Kakariko Well HP)",

    0x30: "Agahnim's Tower (Maiden Sacrifice Chamber)",
    0x31: "Tower of Hera (Hardhat Beetles)",
    0x32: "Hyrule Castle (Sewer Key Chest)",
    0x33: "Shrine of Power (Lanmolas Boss)",
    0x34: "Zora Temple (Push Block Puzzle / Pre-Big Key)",
    0x35: "Zora Temple (Big Key / BS)",
    0x36: "Zora Temple (Big Chest)",
    0x37: "Zora Temple (Map Chest / Water Fill)",
    0x38: "Zora Temple (Key Pot)",
    0x39: "Kalyxo Castle (Gibdo Key / Mothula Hole)",
    0x3A: "Mushroom Grotto (Bombable Floor)",
    0x3B: "Mushroom Grotto (Spike Block / Conveyor)",
    0x3C: "Cave",
    0x3D: "Fortress of Secrets (Torch 2)",
    0x3E: "Tail Palace (Stalfos Knights / Conveyor Hellway)",
    0x3F: "Tail Palace (Map Chest)",

    0x40: "Agahnim's Tower (Final Bridge)",
    0x41: "Hyrule Castle (First Dark)",
    0x42: "Hyrule Castle (6 Ropes)",
    0x43: "Shrine of Power (Torch Puzzle / Moving Wall)",
    0x44: "Glacia Estate (Big Chest)",
    0x45: "Glacia Estate (Jail Cells)",
    0x46: "Zora Temple (Compass Chest)",
    0x47: "Empty Clone",
    0x48: "Empty Clone",
    0x49: "Kalyxo Castle (Gibdo Torch Puzzle)",
    0x4A: "Mushroom Grotto (Entrance)",
    0x4B: "Mushroom Grotto (Warps / South Mimics)",
    0x4C: "Fortress of Secrets (Mini-Helmasaur Conveyor)",
    0x4D: "Fortress of Secrets (Moldorm)",
    0x4E: "Tail Palace (Bomb-Jump)",
    0x4F: "Tail Palace Clone (Fairy)",

    0x50: "Hyrule Castle (West Corridor)",
    0x51: "Hyrule Castle (Throne)",
    0x52: "Hyrule Castle (East Corridor)",
    0x53: "Shrine of Power (Popos 2 / Beamos Hellway)",
    0x54: "Zora Temple (Upstairs Pits)",
    0x55: "Castle Secret Entrance / Uncle Death",
    0x56: "Kalyxo Castle (Key Pot / Trap)",
    0x57: "Kalyxo Castle (Big Key)",
    0x58: "Kalyxo Castle (Big Chest)",
    0x59: "Kalyxo Castle (Final Section Entrance)",
    0x5A: "Mushroom Grotto (Helmasaur King Boss)",
    0x5B: "Fortress of Secrets (Spike Pit)",
    0x5C: "Fortress of Secrets (Ganon-Ball Z)",
    0x5D: "Fortress of Secrets (Gauntlet 1/2/3)",
    0x5E: "Tail Palace (Lonely Firebar)",
    0x5F: "Tail Palace (Hidden Chest / Spike Floor)",

    0x60: "Hyrule Castle (West Entrance)",
    0x61: "Hyrule Castle (Main Entrance)",
    0x62: "Hyrule Castle (East Entrance)",
}


# =============================================================================
# Entrance Names
# =============================================================================
# Maps entrance IDs to location names (for transition tracking)

ENTRANCE_NAMES: Dict[int, str] = {
    0x00: "Link's House",
    0x01: "Link's House (Alternate)",
    0x02: "Sanctuary",
    0x03: "Zora Temple (Water Drain)",
    0x04: "Hyrule Castle (Main Entrance)",
    0x05: "Shrine of Power (Another Entrance)",
    0x06: "Cave (Lost Old Man Starting Cave)",
    0x08: "Zora Temple (Entrance)",
    0x09: "Shrine of Power (Main Entrance)",
    0x0A: "Kalyxo Castle (Key Chest / Trap)",
    0x0B: "Mushroom Grotto (Turtle)",
    0x0C: "Fortress of Secrets (Entrance)",
    0x0D: "House (Toadstool Woods)",
    0x0E: "House (Old Woman)",
    0x0F: "House (Angry Brothers)",

    0x10: "House (Angry Brothers 2)",
    0x11: "Cave (1/2 Magic)",
    0x12: "Hyrule Castle (Bombable Stock)",
    0x14: "Dragon Ship (Big Key)",
    0x15: "Tail Palace (Hidden Chest)",
    0x16: "Cave (Snowpeak)",
    0x25: "Zora Temple (Entrance)",
    0x26: "Mushroom Grotto (Entrance)",
    0x27: "Goron Mines (Entrance)",
    0x34: "Glacia Estate (Main Entrance)",
    0x35: "Dragon Ship (Entrance)",
    0x37: "Fortress of Secrets (Entrance)",
    0x38: "Cave (Healing Fairy)",
}


# =============================================================================
# Dungeon Identifiers
# =============================================================================
# Maps dungeon/area IDs to names

DUNGEONS: Dict[int, str] = {
    0x00: "Hyrule Castle",
    0x02: "Sanctuary",
    0x04: "Tower of Hera",
    0x06: "Zora Temple",
    0x08: "Kalyxo Castle",
    0x0A: "Mushroom Grotto",
    0x0C: "Fortress of Secrets",
    0x0E: "Tail Palace",
    0x10: "Dragon Ship",
    0x12: "Shrine of Power",
    0x14: "Shrine of Wisdom",
    0x16: "Shrine of Courage",
    0x18: "Glacia Estate",
    0x1A: "Goron Mines",
    0x1C: "Agahnim's Tower",
}


# =============================================================================
# Lookup Functions
# =============================================================================

def get_area_name(area_id: int) -> str:
    """Get human-readable name for an overworld area.

    Args:
        area_id: Area ID from $7E008A

    Returns:
        Area name or formatted hex ID if unknown
    """
    if area_id in OVERWORLD_AREAS:
        return OVERWORLD_AREAS[area_id]
    return f"Overworld Area 0x{area_id:02X}"


def get_room_name(room_id: int) -> str:
    """Get human-readable name for an indoor room.

    Args:
        room_id: Room ID from $7E00A4

    Returns:
        Room name or formatted hex ID if unknown
    """
    if room_id in ROOM_NAMES:
        return ROOM_NAMES[room_id]
    return f"Room 0x{room_id:02X}"


def get_entrance_name(entrance_id: int) -> str:
    """Get human-readable name for an entrance.

    Args:
        entrance_id: Entrance ID

    Returns:
        Entrance name or formatted hex ID if unknown
    """
    if entrance_id in ENTRANCE_NAMES:
        return ENTRANCE_NAMES[entrance_id]
    return f"Entrance 0x{entrance_id:02X}"


def get_dungeon_name(dungeon_id: int) -> str:
    """Get human-readable name for a dungeon.

    Args:
        dungeon_id: Dungeon identifier

    Returns:
        Dungeon name or formatted hex ID if unknown
    """
    if dungeon_id in DUNGEONS:
        return DUNGEONS[dungeon_id]
    return f"Dungeon 0x{dungeon_id:02X}"


def get_location_description(
    area_id: int,
    room_id: int,
    is_indoors: bool
) -> str:
    """Get full location description.

    Args:
        area_id: Current area ID
        room_id: Current room ID (if indoors)
        is_indoors: Whether player is indoors

    Returns:
        Full location description string
    """
    if is_indoors:
        return get_room_name(room_id)
    else:
        return get_area_name(area_id)


# =============================================================================
# Statistics
# =============================================================================

def get_coverage_stats() -> dict:
    """Get coverage statistics for location data.

    Returns:
        Dictionary with counts of defined locations
    """
    return {
        "overworld_areas": len(OVERWORLD_AREAS),
        "room_names": len(ROOM_NAMES),
        "entrance_names": len(ENTRANCE_NAMES),
        "dungeons": len(DUNGEONS),
        "total": (
            len(OVERWORLD_AREAS) +
            len(ROOM_NAMES) +
            len(ENTRANCE_NAMES) +
            len(DUNGEONS)
        ),
    }
