"""Oracle-specific constants for the Mesen2 client."""


# =========================================================
# Oracle RAM Addresses (from oracle_quick_reference.md)
# =========================================================


class OracleRAM:
    """Oracle of Secrets RAM address constants."""

    # Game State
    MODE = 0x7E0010  # Game mode
    SUBMODE = 0x7E0011  # Sub-mode
    AREA_ID = 0x7E008A  # Current area/room ID
    ROOM_LAYOUT = 0x7E00A0  # Room layout index
    INDOORS = 0x7E001B  # 0=outdoors, 1=indoors

    # Link Position
    LINK_Y = 0x7E0020  # Link Y (16-bit)
    LINK_X = 0x7E0022  # Link X (16-bit)
    LINK_Z = 0x7E0024  # Link Z position ($FFFF = grounded)
    LINK_DIR = 0x7E002F  # Link facing direction (0=up, 2=down, 4=left, 6=right)
    LINK_STATE = 0x7E005D  # Link state
    LINK_FORM = 0x7E02B2  # Link form/mask ID (0=normal, 3=wolf, 5=minish, 6=GBC Link)

    # Time System (Oracle custom, TimeState struct at $7EE000)
    TIME_HOURS = 0x7EE000  # Current hour (0-23)
    TIME_MINUTES = 0x7EE001  # Current minute (0-59)
    TIME_SPEED = 0x7EE002  # Time speed multiplier

    # Scroll Registers (Lost Woods issue)
    SCROLL_X_LO = 0x7E00E1  # X scroll low
    SCROLL_X_HI = 0x7E00E3  # X scroll high
    SCROLL_Y_LO = 0x7E00E7  # Y scroll low
    SCROLL_Y_HI = 0x7E00E9  # Y scroll high

    # Dungeon
    ROOM_ID = 0x7E048E  # Dungeon room ID (when in dungeon)

    # Sprite Slots (base addresses, indexed by X)
    SPR_X = 0x7E0D00  # Sprite X position low
    SPR_Y = 0x7E0D10  # Sprite Y position low
    SPR_X_HI = 0x7E0D20  # Sprite X position high
    SPR_Y_HI = 0x7E0D30  # Sprite Y position high
    SPR_STATE = 0x7E0D80  # Sprite state (vanilla probe sets this!)
    SPR_PARENT = 0x7E0DB0  # Probe parent (slot + 1)
    SPR_HEALTH = 0x7E0DC0  # Health counter
    SPR_TYPE = 0x7E0DD0  # Sprite type ID
    SPR_ACTION = 0x7E0DF0  # State machine index
    SPR_TIMER_A = 0x7E0E00  # Cooldown timer
    SPR_TIMER_B = 0x7E0E10  # Alt timer
    SPR_TIMER_D = 0x7E0EE0  # General timer (NOT probe!)

    # SRAM - Story Progress
    GAME_STATE = 0x7EF3C5  # 0=Start, 1=LoomBeach, 2=KydrogComplete, 3=FaroreRescued
    OOSPROG = 0x7EF3D6  # Main story flags
    OOSPROG2 = 0x7EF3C6  # Secondary story flags
    SIDE_QUEST = 0x7EF3D7  # Side quest progress
    SIDE_QUEST2 = 0x7EF3D8  # More side quests
    CRYSTALS = 0x7EF37A  # Dungeon completion bits
    PENDANTS = 0x7EF374  # Shrine completion bits

    # Custom Oracle RAM
    KYDROG_FARORE_REMOVED = 0x7EF300  # Removes intro NPCs after Kydrog encounter
    DEKU_MASK_QUEST_DONE = 0x7EF301  # Deku Scrub gave mask
    ZORA_MASK_QUEST_DONE = 0x7EF302  # Zora Princess gave mask
    IN_CUTSCENE = 0x7EF303  # In cutscene flag
    MAKU_TREE_QUEST = 0x7EF3D4  # Met Maku Tree
    MAP_ICON = 0x7EF3C7  # Dungeon guidance icon
    SPAWN_POINT = 0x7EF3C8  # Spawn point ID

    # Items ($7EF340-35F)
    BOW = 0x7EF340  # 1=Bow, 2=+Arrows, 3=Silver, 4=Silver+Arrows
    BOOMERANG = 0x7EF341  # 1=Blue, 2=Red
    HOOKSHOT = 0x7EF342  # 1=Hookshot, 2=Goldstar
    BOMBS = 0x7EF343  # Count
    MAGIC_POWDER = 0x7EF344  # 1=Mushroom, 2=Powder
    FIRE_ROD = 0x7EF345  # 1=Have
    ICE_ROD = 0x7EF346  # 1=Have
    ZORA_MASK = 0x7EF347  # 1=Have
    BUNNY_HOOD = 0x7EF348  # 1=Have
    DEKU_MASK = 0x7EF349  # 1=Have
    LAMP = 0x7EF34A  # 1=Have
    HAMMER = 0x7EF34B  # 1=Have
    FLUTE = 0x7EF34C  # 1=Shovel, 2=Inactive, 3=Active (Ocarina)
    ROCS_FEATHER = 0x7EF34D  # 1=Have
    BOOK = 0x7EF34E  # 1=Have (Book of Secrets)
    BOTTLE_INDEX = 0x7EF34F  # Currently selected bottle
    SOMARIA = 0x7EF350  # 1=Have
    CUSTOM_RODS = 0x7EF351  # 1=Fishing Rod, 2=Portal Rod
    STONE_MASK = 0x7EF352  # 1=Have
    MIRROR = 0x7EF353  # 1=Letter, 2=Mirror

    # Equipment ($7EF354-35B)
    GLOVES = 0x7EF354  # 0=None, 1=Power Glove, 2=Titan's Mitt
    BOOTS = 0x7EF355  # 1=Pegasus Boots
    FLIPPERS = 0x7EF356  # 1=Have
    MOON_PEARL = 0x7EF357  # 1=Have
    WOLF_MASK = 0x7EF358  # 1=Have
    SWORD = 0x7EF359  # 1=Fighter, 2=Master, 3=Tempered, 4=Golden
    SHIELD = 0x7EF35A  # 1=Fighter, 2=Fire, 3=Mirror
    ARMOR = 0x7EF35B  # 0=Green, 1=Blue, 2=Red

    # Bottles ($7EF35C-35F)
    BOTTLE_1 = 0x7EF35C
    BOTTLE_2 = 0x7EF35D
    BOTTLE_3 = 0x7EF35E
    BOTTLE_4 = 0x7EF35F

    # Player Stats ($7EF360-37B)
    RUPEES = 0x7EF360  # 16-bit
    RUPEE_GOAL = 0x7EF362  # 16-bit
    HEART_PIECES = 0x7EF36B
    HEALTH_MAX = 0x7EF36C
    HEALTH_CURRENT = 0x7EF36D
    MAGIC_POWER = 0x7EF36E
    KEYS = 0x7EF36F
    BOMB_CAPACITY = 0x7EF370
    ARROW_CAPACITY = 0x7EF371
    ARROWS = 0x7EF377
    ABILITY_FLAGS = 0x7EF379  # Pegasus boots, etc.


# =========================================================
# Game Mode Constants
# =========================================================


class GameMode:
    """Oracle game mode values."""

    TITLE_RESET = 0x00
    TRANSITION = 0x05
    DUNGEON = 0x07
    OVERWORLD = 0x09
    MENU = 0x0E


MODE_NAMES = {
    GameMode.TITLE_RESET: "Title/Reset",
    GameMode.TRANSITION: "Transition",
    GameMode.DUNGEON: "Dungeon",
    GameMode.OVERWORLD: "Overworld",
    GameMode.MENU: "Menu",
}

DIRECTION_NAMES = {
    0: "Up",
    2: "Down",
    4: "Left",
    6: "Right",
}

FORM_NAMES = {
    0x00: "Normal",
    0x03: "Wolf",
    0x05: "Minish",
    0x06: "GBC Link",
}


# =========================================================
# Item Registry
# =========================================================

ITEMS = {
    # Y-Button items
    "bow": (OracleRAM.BOW, "Bow", {0: "None", 1: "Bow", 2: "+Arrows", 3: "Silver", 4: "Silver+Arrows"}),
    "boomerang": (OracleRAM.BOOMERANG, "Boomerang", {0: "None", 1: "Blue", 2: "Red"}),
    "hookshot": (OracleRAM.HOOKSHOT, "Hookshot", {0: "None", 1: "Hookshot", 2: "Goldstar"}),
    "bombs": (OracleRAM.BOMBS, "Bombs", None),  # Count, not enum
    "powder": (OracleRAM.MAGIC_POWDER, "Magic Powder", {0: "None", 1: "Mushroom", 2: "Powder"}),
    "firerod": (OracleRAM.FIRE_ROD, "Fire Rod", {0: "None", 1: "Have"}),
    "icerod": (OracleRAM.ICE_ROD, "Ice Rod", {0: "None", 1: "Have"}),
    "lamp": (OracleRAM.LAMP, "Lamp", {0: "None", 1: "Have"}),
    "hammer": (OracleRAM.HAMMER, "Hammer", {0: "None", 1: "Have"}),
    "flute": (OracleRAM.FLUTE, "Flute/Ocarina", {0: "None", 1: "Shovel", 2: "Inactive", 3: "Active"}),
    "feather": (OracleRAM.ROCS_FEATHER, "Roc's Feather", {0: "None", 1: "Have"}),
    "book": (OracleRAM.BOOK, "Book of Secrets", {0: "None", 1: "Have"}),
    "somaria": (OracleRAM.SOMARIA, "Cane of Somaria", {0: "None", 1: "Have"}),
    "mirror": (OracleRAM.MIRROR, "Mirror", {0: "None", 1: "Letter", 2: "Mirror"}),
    # Masks
    "zoramask": (OracleRAM.ZORA_MASK, "Zora Mask", {0: "None", 1: "Have"}),
    "dekumask": (OracleRAM.DEKU_MASK, "Deku Mask", {0: "None", 1: "Have"}),
    "bunnymask": (OracleRAM.BUNNY_HOOD, "Bunny Hood", {0: "None", 1: "Have"}),
    "stonemask": (OracleRAM.STONE_MASK, "Stone Mask", {0: "None", 1: "Have"}),
    "wolfmask": (OracleRAM.WOLF_MASK, "Wolf Mask", {0: "None", 1: "Have"}),
    # Equipment
    "sword": (OracleRAM.SWORD, "Sword", {0: "None", 1: "Fighter", 2: "Master", 3: "Tempered", 4: "Golden"}),
    "shield": (OracleRAM.SHIELD, "Shield", {0: "None", 1: "Fighter", 2: "Fire", 3: "Mirror"}),
    "armor": (OracleRAM.ARMOR, "Armor", {0: "Green", 1: "Blue", 2: "Red"}),
    "gloves": (OracleRAM.GLOVES, "Gloves", {0: "None", 1: "Power", 2: "Titan"}),
    "boots": (OracleRAM.BOOTS, "Pegasus Boots", {0: "None", 1: "Have"}),
    "flippers": (OracleRAM.FLIPPERS, "Flippers", {0: "None", 1: "Have"}),
    "moonpearl": (OracleRAM.MOON_PEARL, "Moon Pearl", {0: "None", 1: "Have"}),
    # Stats
    "health": (OracleRAM.HEALTH_CURRENT, "Health", None),
    "maxhealth": (OracleRAM.HEALTH_MAX, "Max Health", None),
    "magic": (OracleRAM.MAGIC_POWER, "Magic", None),
    "rupees": (OracleRAM.RUPEES, "Rupees", None),  # 16-bit
    "arrows": (OracleRAM.ARROWS, "Arrows", None),
    "keys": (OracleRAM.KEYS, "Keys", None),
}


# =========================================================
# Story Flag Registry
# =========================================================

STORY_FLAGS = {
    # Main state
    "gamestate": (OracleRAM.GAME_STATE, "GameState", {
        0: "Start", 1: "LoomBeach", 2: "KydrogComplete", 3: "FaroreRescued"
    }),
    # Bitfield flags (OOSPROG)
    "oosprog": (OracleRAM.OOSPROG, "OOSPROG", None),
    "intro": (OracleRAM.OOSPROG, "Intro Complete", 0x01),  # bit 0
    "hall": (OracleRAM.OOSPROG, "Hall of Secrets", 0x02),  # bit 1
    "pendant": (OracleRAM.OOSPROG, "Pendant Quest", 0x04),  # bit 2
    "mastersword": (OracleRAM.OOSPROG, "Master Sword", 0x10),  # bit 4
    "fortress": (OracleRAM.OOSPROG, "Fortress Complete", 0x80),  # bit 7
    # OOSPROG2
    "oosprog2": (OracleRAM.OOSPROG2, "OOSPROG2", None),
    "impa": (OracleRAM.OOSPROG2, "Impa Intro", 0x01),  # bit 0
    "sanctuary": (OracleRAM.OOSPROG2, "Sanctuary Visit", 0x02),  # bit 1
    "kydrog": (OracleRAM.OOSPROG2, "Kydrog Encounter", 0x04),  # bit 2
    "bookflag": (OracleRAM.OOSPROG2, "Book of Secrets", 0x20),  # bit 5
    # Crystals
    "crystals": (OracleRAM.CRYSTALS, "Crystals", None),
    "d1": (OracleRAM.CRYSTALS, "D1 Mushroom Grotto", 0x01),
    "d2": (OracleRAM.CRYSTALS, "D2 Tail Palace", 0x10),
    "d3": (OracleRAM.CRYSTALS, "D3 Kalyxo Castle", 0x40),
    "d4": (OracleRAM.CRYSTALS, "D4 Zora Temple", 0x20),
    "d5": (OracleRAM.CRYSTALS, "D5 Glacia Estate", 0x04),
    "d6": (OracleRAM.CRYSTALS, "D6 Goron Mines", 0x02),
    "d7": (OracleRAM.CRYSTALS, "D7 Dragon Ship", 0x08),
    # Pendants
    "pendants": (OracleRAM.PENDANTS, "Pendants", None),
    "wisdom": (OracleRAM.PENDANTS, "Pendant of Wisdom", 0x01),
    "power": (OracleRAM.PENDANTS, "Pendant of Power", 0x02),
    "courage": (OracleRAM.PENDANTS, "Pendant of Courage", 0x04),
    # Side quests
    "sidequest": (OracleRAM.SIDE_QUEST, "SideQuest", None),
    "masksalesman": (OracleRAM.SIDE_QUEST, "Met Mask Salesman", 0x01),
    "dekufound": (OracleRAM.SIDE_QUEST, "Deku Scrub Found", 0x04),
    "goronquest": (OracleRAM.SIDE_QUEST, "Goron Quest", 0x20),
    # Quest completion flags
    "makutree": (OracleRAM.MAKU_TREE_QUEST, "Maku Tree Quest", None),
    "dekuquest": (OracleRAM.DEKU_MASK_QUEST_DONE, "Deku Quest Done", None),
    "zoraquest": (OracleRAM.ZORA_MASK_QUEST_DONE, "Zora Quest Done", None),
}


# =========================================================
# Warp Locations
# =========================================================

WARP_LOCATIONS = {
    # Villages
    "village": (0x23, 1572, 2790, "Start Village"),
    "linkshouse": (0x23, 1360, 2800, "Link's House"),
    # Key areas
    "makutree": (0x00, 2032, 272, "Maku Tree"),
    "lostwoods": (0x29, 512, 512, "Lost Woods Entry"),
    "beach": (0x35, 1800, 3200, "Loom Beach"),
    "sanctuary": (0x13, 512, 512, "Sanctuary Area"),
    "hallofsecretsow": (0x0E, 512, 512, "Hall of Secrets (OW)"),
    "kalyxofield": (0x25, 512, 512, "Kalyxo Field"),
    "mountain": (0x07, 512, 512, "Snow Mountain"),
    "ranch": (0x30, 512, 512, "Ranch"),
    "graveyard": (0x02, 512, 512, "Graveyard"),
    "river": (0x36, 512, 512, "River Area"),
    "zoradomain": (0x22, 512, 512, "Zora Domain OW"),
    "forestentrance": (0x28, 512, 512, "Forest Entrance"),
    # Shrines
    "courageshrine": (0x50, 512, 512, "Shrine of Courage"),
    "powershrine": (0x4B, 512, 512, "Shrine of Power"),
    "wisdomshrine": (0x4A, 512, 512, "Shrine of Wisdom"),
    # Dungeons (entrances)
    "d1": (0x0C, 512, 512, "D1 Mushroom Grotto"),
    "d2": (0x0A, 512, 512, "D2 Tail Palace"),
    "d3": (0x10, 512, 512, "D3 Kalyxo Castle"),
    "d4": (0x16, 512, 512, "D4 Zora Temple"),
    "d5": (0x12, 512, 512, "D5 Glacia Estate"),
    "d6": (0x0E, 512, 512, "D6 Goron Mines"),
    "d7": (0x18, 512, 512, "D7 Dragon Ship"),
}


# =========================================================
# Button Mapping
# =========================================================

BUTTONS = {
    "a": "A",
    "b": "B",
    "x": "X",
    "y": "Y",
    "l": "L",
    "r": "R",
    "up": "UP",
    "down": "DOWN",
    "left": "LEFT",
    "right": "RIGHT",
    "start": "START",
    "select": "SELECT",
}


# =========================================================
# Watch Profiles
# =========================================================

WATCH_PROFILES = {
    "overworld": {
        "description": "Overworld area transitions",
        "addresses": [
            (OracleRAM.AREA_ID, "AreaID", "hex"),
            (OracleRAM.SCROLL_X_LO, "ScrollX", "hex"),
            (OracleRAM.SCROLL_Y_LO, "ScrollY", "hex"),
            (OracleRAM.LINK_X, "LinkX", "dec16"),
            (OracleRAM.LINK_Y, "LinkY", "dec16"),
            (OracleRAM.MODE, "Mode", "hex"),
        ],
    },
    "dungeon": {
        "description": "Dungeon room navigation",
        "addresses": [
            (OracleRAM.ROOM_LAYOUT, "Layout", "hex"),
            (OracleRAM.ROOM_ID, "RoomID", "hex"),
            (OracleRAM.LINK_X, "LinkX", "dec16"),
            (OracleRAM.LINK_Y, "LinkY", "dec16"),
            (OracleRAM.INDOORS, "Indoors", "bool"),
        ],
    },
    "sprites": {
        "description": "Sprite debugging",
        "addresses": [
            (OracleRAM.SPR_STATE, "SprState[0]", "hex"),
            (OracleRAM.SPR_STATE + 1, "SprState[1]", "hex"),
            (OracleRAM.SPR_TIMER_D, "SprTimerD[0]", "hex"),
            (OracleRAM.SPR_ACTION, "SprAction[0]", "hex"),
            (OracleRAM.SPR_TYPE, "SprType[0]", "hex"),
        ],
    },
    "lost_woods": {
        "description": "Lost Woods camera issue debugging",
        "addresses": [
            (OracleRAM.AREA_ID, "AreaID", "hex"),
            (OracleRAM.SCROLL_X_LO, "E1 (ScrollX)", "hex"),
            (OracleRAM.SCROLL_X_HI, "E3 (ScrollX Hi)", "hex"),
            (OracleRAM.SCROLL_Y_LO, "E7 (ScrollY)", "hex"),
            (OracleRAM.SCROLL_Y_HI, "E9 (ScrollY Hi)", "hex"),
            (OracleRAM.LINK_X, "LinkX", "dec16"),
            (OracleRAM.LINK_Y, "LinkY", "dec16"),
        ],
    },
    "story": {
        "description": "Story progress flags",
        "addresses": [
            (OracleRAM.GAME_STATE, "GameState", "hex"),
            (OracleRAM.OOSPROG, "OOSPROG", "hex"),
            (OracleRAM.OOSPROG2, "OOSPROG2", "hex"),
            (OracleRAM.SIDE_QUEST, "SideQuest", "hex"),
            (OracleRAM.CRYSTALS, "Crystals", "hex"),
        ],
    },
    "time": {
        "description": "Time system variables",
        "addresses": [
            (OracleRAM.TIME_HOURS, "Hours", "dec"),
            (OracleRAM.TIME_MINUTES, "Minutes", "dec"),
            (OracleRAM.TIME_SPEED, "Speed", "dec"),
            (OracleRAM.LINK_FORM, "Form", "hex"),
            (OracleRAM.MODE, "Mode", "hex"),
        ],
    },
    "link": {
        "description": "Link state and form debugging",
        "addresses": [
            (OracleRAM.LINK_X, "LinkX", "dec16"),
            (OracleRAM.LINK_Y, "LinkY", "dec16"),
            (OracleRAM.LINK_Z, "LinkZ", "dec16"),
            (OracleRAM.LINK_DIR, "Direction", "hex"),
            (OracleRAM.LINK_STATE, "State", "hex"),
            (OracleRAM.LINK_FORM, "Form", "hex"),
            (OracleRAM.HEALTH_CURRENT, "Health", "dec"),
            (OracleRAM.HEALTH_MAX, "MaxHealth", "dec"),
        ],
    },
}


# =========================================================
# Room Names (from Oracle Data Sheets)
# =========================================================

ROOM_NAMES = {
    0x00: "Ganon",
    0x01: "Hyrule Castle (North Corridor)",
    0x02: "Behind Sanctuary (Switch)",
    0x03: "Houlihan",
    0x04: "Dragon Ship (Crysta-Roller)",
    0x05: "Empty",
    0x06: "Zora Temple (Arrghus[Boss])",
    0x07: "Tower of Hera (Moldorm[Boss])",
    0x08: "Cave (Healing Fairy)",
    0x09: "Mushroom Grotto",
    0x0A: "Mushroom Grotto (Stalfos Trap)",
    0x0B: "Mushroom Grotto (Turtle)",
    0x0C: "Fortress of Secrets (Entrance)",
    0x0D: "Fortress of Secrets (Agahnim2[Boss])",
    0x0E: "Tail Palace (Entrance)",
    0x0F: "Empty Clone",
    0x10: "Ganon Evacuation Route",
    0x11: "Hyrule Castle (Bombable Stock)",
    0x12: "Sanctuary",  # Hall of Secrets interior
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
    0x20: "Agahnim's Tower (Agahnim[Boss])",
    0x21: "Hyrule Castle (Key-rat)",
    0x22: "Hyrule Castle (Sewer Text Trigger)",
    0x23: "Dragon Ship (West Exit to Balcony)",
    0x24: "Dragon Ship (Double Hokku-Bokku / Big chest)",
    0x25: "Empty Clone",
    0x26: "Zora Temple (Statue)",
    0x27: "Tower of Hera (Big Chest)",
    0x28: "Zora Temple (Entrance)",
    0x29: "Kalyxo Castle (Mothula[Boss])",
    0x2A: "Mushroom Grotto (Big Hub)",
    0x2B: "Mushroom Grotto (Map Chest / Fairy)",
    0x2C: "Cave",
    0x2D: "Empty Clone",
    0x2E: "Tail Palace (Compass)",
    0x2F: "Cave (Kakariko Well HP)",
    0x30: "Agahnim's Tower (Maiden Sacrifice Chamber)",
    0x31: "Tower of Hera (Hardhat Beetles)",
    0x32: "Hyrule Castle (Sewer Key Chest)",
    0x33: "Shrine of Power (Lanmolas[Boss])",
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
    0x5A: "Mushroom Grotto (Helmasaur King[Boss])",
    0x5B: "Fortress of Secrets (Spike Pit)",
    0x5C: "Fortress of Secrets (Ganon-Ball Z)",
    0x5D: "Fortress of Secrets (Gauntlet 1/2/3)",
    0x5E: "Tail Palace (Lonely Firebar)",
    0x5F: "Tail Palace (Hidden Chest / Spike Floor)",
    0x60: "Hyrule Castle (West Entrance)",
    0x61: "Hyrule Castle (Main Entrance)",
    0x62: "Hyrule Castle (East Entrance)",
    0x63: "Shrine of Power (Final Section Entrance)",
    0x64: "Glacia Estate (West Attic)",
    0x65: "Glacia Estate (East Attic)",
    0x66: "Zora Temple (Hidden Chest / Hidden Door)",
    0x67: "Kalyxo Castle (Compass Chest)",
    0x68: "Kalyxo Castle (Key Chest / Trap)",
    0x69: "Empty Clone",
    0x6A: "Mushroom Grotto (Rupee)",
    0x6B: "Fortress of Secrets (Mimics s)",
    0x6C: "Fortress of Secrets (Lanmolas)",
    0x6D: "Fortress of Secrets (Gauntlet 4/5)",
    0x6E: "Tail Palace (Pengators)",
    0x6F: "Empty Clone",
    0x70: "Hyrule Castle (Small Corridor to Jail Cells)",
    0x71: "Hyrule Castle (Boomerang Chest)",
    0x72: "Hyrule Castle (Map Chest)",
    0x73: "Shrine of Power (Big Chest)",
    0x74: "Shrine of Power (Map Chest)",
    0x75: "Shrine of Power (Big Key Chest)",
    0x76: "Zora Temple (Water Drain)",
    0x77: "Goron Mines (Northwest Hall)",
    0x78: "Goron Mines (Lanmolas Mini-boss)",
    0x79: "Goron Mines (Northeast Hall)",
    0x7A: "Shrine of Wisdom (Pendant)",
    0x7B: "Fortress of Secrets",
    0x7C: "Fortress of Secrets (East Side Collapsing Bridge / Exploding Wall)",
    0x7D: "Fortress of Secrets (Winder / Warp Maze)",
    0x7E: "Tail Palace (Hidden Chest / Bombable Floor)",
    0x7F: "Tail Palace (Big Spike Traps)",
    0x80: "Hyrule Castle (Jail Cell)",
    0x81: "Hyrule Castle",
    0x82: "Hyrule Castle (Basement Chasm)",
    0x83: "Shrine of Power (West Entrance)",
    0x84: "Shrine of Power (Main Entrance)",
    0x85: "Shrine of Power (East Entrance)",
    0x86: "Shrine of Power (Another Entrance)",
    0x87: "Goron Mines (West Hall)",
    0x88: "Goron Mines (Hammer Chest)",
    0x89: "Goron Mines (East Hall)",
    0x8A: "Shrine of Wisdom (Penultimate)",
    0x8B: "Fortress of Secrets (Block Puzzle / Spike Skip / Map Chest)",
    0x8C: "Fortress of Secrets (East and West Downstairs / Big Chest)",
    0x8D: "Fortress of Secrets (Tile / Torch Puzzle)",
    0x8E: "Tail Palace",
    0x8F: "Empty Clone",
    0x90: "Goron Mines (Vitreous[Boss])",
    0x91: "Goron Mines (Final Switch)",
    0x92: "Goron Mines (Dark Bomb Wall / Switches)",
    0x93: "Goron Mines (Dark Cane Floor Switch Puzzle)",
    0x94: "Empty Clone",
    0x95: "Fortress of Secrets (Final Collapsing Bridge)",
    0x96: "Fortress of Secrets (Torches 1)",
    0x97: "Goron Mines (Torch Puzzle / Moving Wall)",
    0x98: "Goron Mines (Entrance)",
    0x99: "Goron Mines (Southeast Hall)",
    0x9A: "Shrine of Wisdom (Flippers)",
    0x9B: "Fortress of Secrets (Many Spikes / Warp Maze)",
    0x9C: "Fortress of Secrets (Invisible Floor Maze)",
    0x9D: "Fortress of Secrets (Compass Chest / Invisible Floor)",
    0x9E: "Glacia Estate (Big Chest Key)",
    0x9F: "Glacia Estate",
    0xA0: "Goron Mines (Pre-Vitreous)",
    0xA1: "Goron Mines (Fish)",
    0xA2: "Goron Mines (Bridge Key Chest)",
    0xA3: "Goron Mines",
    0xA4: "Dragon Ship (Trinexx[Boss])",
    0xA5: "Fortress of Secrets (Wizzrobes s)",
    0xA6: "Fortress of Secrets (Moldorm Fall)",
    0xA7: "Tower of Hera (Fairy)",
    0xA8: "Goron Mines (Stalfos Spawn)",
    0xA9: "Goron Mines (Big Chest)",
    0xAA: "Goron Mines (Map Chest)",
    0xAB: "Glacia Estate (Moving Spikes / Key Pot)",
    0xAC: "Glacia Estate (Blind The Thief[Boss])",
    0xAD: "Empty Clone",
    0xAE: "Tail Palace",
    0xAF: "Tail Palace (Ice Bridge)",
    0xB0: "Agahnim's Tower (Circle of Pots)",
    0xB1: "Goron Mines (Hourglass)",
    0xB2: "Goron Mines (Slug)",
    0xB3: "Goron Mines (Spike Key Chest)",
    0xB4: "Dragon Ship (Pre-Trinexx)",
    0xB5: "Dragon Ship (Dark Maze)",
    0xB6: "Dragon Ship (Chain Chomps)",
    0xB7: "Dragon Ship (Map Chest / Key Chest / Roller)",
    0xB8: "Goron Mines (Big Key)",
    0xB9: "Goron Mines (Lobby Cannonballs)",
    0xBA: "Goron Mines (Dark Antifairy / Key Pot)",
    0xBB: "Glacia Estate (Hellway)",
    0xBC: "Glacia Estate (Conveyor Toilet)",
    0xBD: "Empty Clone",
    0xBE: "Tail Palace (Block Puzzle)",
    0xBF: "Tail Palace Clone (Switch)",
    0xC0: "Agahnim's Tower (Dark Bridge)",
    0xC1: "Goron Mines (Compass Chest / Tile)",
    0xC2: "Goron Mines (Big Hub)",
    0xC3: "Goron Mines (Big Chest)",
    0xC4: "Dragon Ship (Final Crystal Switch Puzzle)",
    0xC5: "Dragon Ship (Laser Bridge)",
    0xC6: "Dragon Ship",
    0xC7: "Dragon Ship (Torch Puzzle)",
    0xC8: "Goron Mines (Armos Knights[Boss])",
    0xC9: "Goron Mines (Entrance)",
    0xCA: "??",
    0xCB: "Glacia Estate (North West Entrance)",
    0xCC: "Glacia Estate (North East Entrance)",
    0xCD: "Empty Clone",
    0xCE: "Tail Palace (Hole to Kholdstare)",
    0xCF: "Empty Clone",
    0xD0: "Agahnim's Tower (Dark Maze)",
    0xD1: "Goron Mines (Conveyor Slug / Big Key)",
    0xD2: "Goron Mines (Mire02 / Wizzrobes)",
    0xD3: "Empty Clone",
    0xD4: "Empty Clone",
    0xD5: "Dragon Ship (Laser Key)",
    0xD6: "Dragon Ship (Entrance)",
    0xD7: "Goron Mines (Basement West)",
    0xD8: "Goron Mines (Zeldagamer / Pre-Armos Knights)",
    0xD9: "Goron Mines (Canonball)",
    0xDA: "Goron Mines",
    0xDB: "Glacia Estate (Main (South West) Entrance)",
    0xDC: "Glacia Estate (South East Entrance)",
    0xDD: "Empty Clone",
    0xDE: "Tail Palace (Kholdstare[Boss])",
    0xDF: "Cave",
    0xE0: "Agahnim's Tower (Entrance)",
    0xE1: "Cave (Lost Woods HP)",
    0xE2: "Cave (Lumberjack's Tree HP)",
    0xE3: "Cave (1/2 Magic)",
    0xE4: "Cave (Lost Old Man Final Cave)",
    0xE5: "Cave (Lost Old Man Final Cave)",
    0xE6: "Cave",
    0xE7: "Cave",
    0xE8: "Cave",
    0xE9: "Empty Clone",
    0xEA: "Cave (Spectacle Rock HP)",
    0xEB: "Cave",
    0xEC: "Empty Clone",
    0xED: "Cave",
    0xEE: "Cave (Spiral Cave)",
    0xEF: "Cave (Crystal Switch / 5 Chests)",
    0xF0: "Cave (Lost Old Man Starting Cave)",
    0xF1: "Cave (Lost Old Man Starting Cave)",
    0xF2: "House",
    0xF3: "House (Old Woman)",
    0xF4: "House (Angry Brothers)",
    0xF5: "House (Angry Brothers)",
    0xF6: "Empty Clone",
    0xF7: "Empty Clone",
    0xF8: "Cave",
    0xF9: "Cave",
    0xFA: "Cave",
    0xFB: "Cave",
    0xFC: "Empty Clone",
    0xFD: "Cave",
    0xFE: "Cave",
    0xFF: "Cave",
}


# =========================================================
# Overworld Area Names (from Oracle Data Sheets)
# =========================================================

OVERWORLD_AREAS = {
    # Light World (Kalyxo) - Graphics IDs to Area Names
    0x20: "Loom Ranch",
    0x21: "Forest",
    0x22: "Fields",
    0x23: "Ranch",
    0x24: "Castle",
    0x25: "Zora Temple Area",
    0x26: "East Fields",
    0x27: "Ponds",
    0x28: "Underwater",
    0x29: "Church",
    0x2A: "Graveyard",
    0x2B: "Potion Shop",
    0x2C: "West Fields",
    0x2D: "Deku Pond",
    0x2E: "Tail Path",
    0x2F: "Maku Tree",
    0x30: "Beach",
    0x31: "Coast",
    0x32: "Mountain Base",
    0x33: "Lanmolas/Loom Beach",
    0x34: "South Fields",
    0x35: "Zora Domain",
    0x36: "Goron Desert",
    0x37: "Desert Edge",
    0x38: "Dragon Ship Area",
    0x39: "Dragon Ship Path",
    0x3A: "Dragon Ship Dock",
    0x3B: "Pyramid",
    0x3C: "West Coast",
    0x3D: "Volcano",
    0x3E: "Ice Mountain",
    0x3F: "Village",
    # Dark World (Eon Abyss)
    0x40: "Temporal Pyramid",
    0x41: "Pyramid / Swamp",
    0x42: "Desert",
    0x43: "Forest / Mountain Shrines",
    0x44: "Dark Castle",
    0x45: "Dark Temple",
    0x46: "Dark Forest",
    0x47: "Dark Ponds",
    0x48: "Dark Underwater",
    0x49: "Dark Church",
    0x4A: "Shrine of Wisdom",
    0x4B: "Shrine of Power",
    0x4C: "Dark West",
    0x4D: "Dark Pond",
    0x4E: "Eon Fields",
    0x4F: "Dark Maku",
    0x50: "Shrine of Courage",
    # Special areas
    0x57: "Final Area",
    0x5B: "DW Church",
    0x5E: "Fortress",
    0x70: "Underwater (Dark)",
    0x75: "Underwater Area",
    0x7A: "Deep Underwater",
}


# =========================================================
# Entrance Info (from Oracle Data Sheets)
# =========================================================

ENTRANCE_INFO = {
    0x00: {"name": "Link's House", "world": "LW", "ow": "0x33 Loom Beach"},
    0x01: {"name": "Link's House", "world": "LW", "ow": "0x33 Loom Beach"},
    0x02: {"name": "Sanctuary", "world": "LW", "ow": "0x0E Hall of Secrets"},
    0x03: {"name": "Zora Temple (Water Drain)", "world": "DW", "ow": "Shrine of Power"},
    0x04: {"name": "Hyrule Castle (Main Entrance)", "world": "N/A", "ow": ""},
    0x08: {"name": "Zora Temple (Entrance)", "world": "N/A", "ow": ""},
    0x09: {"name": "Shrine of Power (Main Entrance)", "world": "DW", "ow": "Shrine of Power"},
    0x0C: {"name": "Fortress of Secrets (Entrance)", "world": "DW", "ow": "Shrine of Courage"},
    0x25: {"name": "Zora Temple (Entrance)", "world": "LW", "ow": "0x1E Zora Sanctuary"},
    0x26: {"name": "Mushroom Grotto (Entrance)", "world": "LW", "ow": "0x10 Toadstool Woods"},
    0x27: {"name": "Goron Mines (Entrance)", "world": "LW", "ow": "0x36 Goron Desert"},
    0x34: {"name": "Glacia Estate (Main Entrance)", "world": "LW", "ow": "0x06 Snowpeak"},
    0x35: {"name": "Dragon Ship (Entrance)", "world": "LW", "ow": "0x30 Dragon Ship"},
    0x37: {"name": "Fortress of Secrets (Entrance)", "world": "DW", "ow": "0x5E Fortress"},
    0x7B: {"name": "Ganon", "world": "DW", "ow": "0x57 Final Area"},
}


# =========================================================
# Dungeon Info (from Oracle Data Sheets)
# =========================================================

DUNGEON_INFO = {
    "mushroom_grotto": {
        "name": "Mushroom Grotto",
        "blockset": 0x07,
        "palette": 0x0F,
        "spritesets": [0x08, 0x09, 0x1A],
        "item": "Bow",
        "boss": "Manhandla",
    },
    "tail_palace": {
        "name": "Tail Palace",
        "blockset": 0x05,
        "palette": 0x06,
        "spritesets": [0x19, 0x13, 0x0C],
        "item": "Roc's Feather",
        "boss": "Moldorm",
    },
    "kalyxo_castle": {
        "name": "Kalyxo Castle",
        "blockset": 0x02,
        "palette": 0x0C,
        "spritesets": [0x09],
        "item": "King's Sword",
        "boss": "Eyegore Knights",
    },
    "zora_temple": {
        "name": "Zora Temple",
        "blockset": 0x01,
        "palette": 0x09,
        "spritesets": [0x11, 0x1E, 0x14],
        "item": "Hookshot, Blue Tunic",
        "boss": "Advanced Arrghus",
    },
    "glacia_estate": {
        "name": "Glacia Estate",
        "blockset": 0x0B,
        "palette": 0x13,
        "spritesets": [0x1C],
        "item": "Fire Rod",
        "boss": "Twinrova",
    },
    "goron_mines": {
        "name": "Goron Mines",
        "blockset": 0x04,
        "palette": 0x07,
        "spritesets": [0x2B, 0x0A],
        "item": "Hammer, Fire Shield",
        "boss": "King Dodongo",
    },
    "dragon_ship": {
        "name": "Dragon Ship",
        "blockset": 0x03,  # Also 0x09
        "palette": 0x05,
        "spritesets": [0x24, 0x25, 0x18],
        "item": "Cane of Somaria",
        "boss": "Kydrog",
    },
    "fortress_of_secrets": {
        "name": "Fortress of Secrets",
        "blockset": 0x0E,
        "palette": 0x03,
        "spritesets": [0x17],
        "item": "Portal Rod",
        "boss": "Dark Link",
    },
    "hall_of_secrets": {
        "name": "Hall of Secrets",
        "blockset": 0x03,
        "palette": 0x11,
        "spritesets": [0x05],
        "item": None,
        "boss": None,
    },
}


# =========================================================
# Known Issue Patterns
# =========================================================

# Lost Woods area IDs (approximate - may need verification)
LOST_WOODS_AREAS = {0x28, 0x29, 0x2A, 0x38, 0x39, 0x3A}
