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
# Known Issue Patterns
# =========================================================

# Lost Woods area IDs (approximate - may need verification)
LOST_WOODS_AREAS = {0x28, 0x29, 0x2A, 0x38, 0x39, 0x3A}
