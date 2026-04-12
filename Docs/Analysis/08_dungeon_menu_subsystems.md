# Oracle of Secrets — Dungeon & Menu Subsystems

**Generated:** 2026-03-21
**Scope:** Dungeon architecture, collision system, water gates, minecart mechanics, and menu system layout.

---

## Dungeon Architecture (Bank $2C)

```mermaid
graph TB
    subgraph "Dungeon System"
        DNG_ASM["Dungeons/dungeons.asm<br/>(master include)"]
        COLLISION["Collision/<br/>water_collision.asm<br/>custom collision data"]
        OBJECTS["Objects/<br/>floor_puzzle.asm<br/>keyblock.asm<br/>crumblefloor.asm<br/>spikes.asm"]
        ASSETS["Assets/<br/>dungeon_maps.bin<br/>tilesets, palettes"]
        CUSTOM["custom_tag.asm<br/>D3 prison hooks"]
        ATTRACT["attract_scenes.asm (36KB)<br/>Dream sequence base"]
        GENERATED["generated/<br/>Procedural content"]
    end

    DNG_ASM --> COLLISION & OBJECTS & ASSETS & CUSTOM & ATTRACT & GENERATED

    subgraph "Yaze Integration"
        YAZE["Oracle-of-Secrets.yaze<br/>Project file"]
        ZRD["592 .zrd files<br/>(room data exports)"]
        EXPORT["ExportedDungeons/<br/>ExportedRooms/"]
    end

    YAZE --> ZRD --> EXPORT
    EXPORT -.->|"room data"| DNG_ASM
```

---

## Dungeon Roster

```mermaid
graph LR
    subgraph "Act I"
        D1["D1 Mushroom Grotto<br/>Theme: Nature corruption<br/>Boss: Manhandla"]
        D2["D2 Tail Palace<br/>Theme: Ancient temple<br/>Boss: Moldorm"]
        D3["D3 Kalyxo Castle<br/>Theme: Occupied fortress<br/>Boss: Eyegore Knights<br/>⚠️ Prison gated OFF"]
    end

    subgraph "Act II"
        D4["D4 Zora Temple<br/>Theme: Underwater ruins<br/>Boss: Arrghus<br/>⚠️ Water gates active"]
        D5["D5 Glacia Estate<br/>Theme: Frozen manor<br/>Boss: Twinrova"]
        D6["D6 Goron Mines<br/>Theme: Minecart dungeon<br/>Boss: King Dodongo<br/>⚠️ Minecart WIP"]
    end

    subgraph "Act III"
        D7["D7 Dragon Ship<br/>Theme: Pirate vessel<br/>Boss: Kydrog<br/>⚠️ Rescue gated OFF"]
        D8["D8 Fortress of Secrets<br/>Theme: Dark fortress<br/>Boss: Kydreeok<br/>⚠️ Skeleton status"]
    end

    subgraph "Special"
        S1["S1 Shrine"]
        S2["S2 Shrine"]
        S3["S3 Shrine<br/>Boss: Vaati<br/>⚠️ Not implemented"]
    end
```

---

## Water Gate System (D4 Zora Temple)

```mermaid
stateDiagram-v2
    [*] --> Drained: Room entered
    Drained --> Filling: Trigger switch
    Filling --> Filled: Animation complete
    Filled --> Drained: Re-trigger switch

    state "Persistence" as P {
        Filled --> SavedFilled: Write $7EF411
        SavedFilled --> Filled: Room re-entry (reads $7EF411)
    }

    note right of P
        ENABLE_WATER_GATE_HOOKS = ON
        ENABLE_WATER_GATE_OVERLAY_REDIRECT = ON
        ENABLE_WATER_GATE_ROOMENTRY_RESTORE = OFF (untested)
    end note
```

**Key rooms:** 0x27 (main water area), 0x25 (gate control)

**Active hooks:** Fill/drain system and overlay redirect are ON. Room-entry restore (persistence on re-entry) is gated OFF.

---

## Minecart System (D6 Goron Mines)

```mermaid
flowchart LR
    subgraph "Track System"
        TABLE["Planned Track Table<br/>(ENABLED)"]
        STOP["Stop tiles<br/>(room invariants)"]
        SWITCH["Switch-corner<br/>tiles"]
    end

    subgraph "Cart Mechanics"
        RIDE["Ride (active)"]
        LIFT["Lift/Toss<br/>(GATED OFF)"]
        SHUTTER["Cart-Required Shutters<br/>(GATED OFF)"]
    end

    subgraph "Room Data (Yaze)"
        R_A8["Room 0xA8"]
        R_B8["Room 0xB8"]
        R_D8["Room 0xD8"]
        R_DA["Room 0xDA"]
    end

    TABLE --> RIDE
    STOP --> RIDE
    SWITCH --> RIDE
    R_A8 & R_B8 & R_D8 & R_DA --> TABLE
```

**Status:** Basic ride mechanics work. Track table is enabled. Room invariants fixed in commit 0342300. Lift/toss physics and cart-required shutters are gated OFF and untested.

---

## Menu System Architecture (Banks $2D-$2E)

```mermaid
graph TB
    subgraph "Menu Entry Point"
        ENTRY["Menu_Entry<br/>(state machine dispatcher)"]
        VECTORS[".vectors<br/>(jump table)"]
    end

    subgraph "Menu States"
        S00["$00 — Init"]
        S04["$04 — Item Select<br/>(left page)"]
        S06["$06 — Quest Status<br/>(right page)"]
        S09["$09 — Ring Box"]
        S0C["$0C — Magic Bag<br/>Submenu"]
        S0D["$0D — Song Menu"]
        S0E["$0E — Journal"]
    end

    ENTRY --> VECTORS
    VECTORS --> S00 & S04 & S06 & S09 & S0C & S0D & S0E

    subgraph "Menu Files"
        M_MAIN["menu.asm (23KB)"]
        M_DRAW["menu_draw.asm (18KB)"]
        M_HUD["menu_hud.asm"]
        M_JOURNAL["menu_journal.asm (16KB)"]
        M_GFX["menu_gfx_table.asm"]
        M_PAL["menu_palette.asm"]
        M_SCROLL["menu_scroll.asm"]
        M_SELECT["menu_select_item.asm"]
        M_TEXT["menu_text.asm (13KB)"]
    end

    subgraph "Data-Driven Design"
        CURSOR["Menu_ItemCursorPositions"]
        ADDR["Menu_AddressIndex<br/>(SRAM address per item)"]
        ICONS["menu_gfx_table.asm<br/>(icon graphics lookup)"]
        NAMES["menu_map_names.asm<br/>(location name lookup)"]
    end
```

---

## HUD System

```mermaid
flowchart LR
    HUD["HUD_Update<br/>(called per frame)"]
    HUD --> HEARTS["HUD_UpdateHearts<br/>(reads SRAM health)"]
    HUD --> MAGIC["HUD_UpdateMagic<br/>(reads SRAM magic)"]
    HUD --> COUNT["HUD_UpdateCounters<br/>(rupees, keys, bombs)"]
    HUD --> ITEM["HUD_UpdateItemBox<br/>(equipped item icon)"]

    subgraph "Known AI-Fixed Issues"
        FIX1["FloorIndicator overflow<br/>(1c19788 - Claude)"]
        FIX2["ActivateSubScreen fallthrough<br/>(d01a4b8 - Claude)"]
        FIX3["Menu navigation up/down<br/>(791ebaf - Claude)"]
        FIX4["Menu crashes/stability<br/>(8b23049 - Claude)"]
    end

    HUD -.-> FIX1
```

---

## Item System (Bank $2B)

```mermaid
graph TB
    subgraph "Items (Bank $2B)"
        ALL["Items/all_items.asm"]
        ALL --> OCARINA["ocarina.asm (13KB)<br/>Songs, Song of Storms, Tint (gated)"]
        ALL --> GOLDSTAR["goldstar.asm (22KB)<br/>Hookshot variant, L/R swap"]
        ALL --> FISHING["fishing_rod.asm (10KB)<br/>Fishing minigame"]
        ALL --> BOOK["book_of_secrets.asm"]
        ALL --> BOTTLE["bottle_net.asm"]
        ALL --> ICE["ice_rod.asm"]
        ALL --> PORTAL["portal_rod.asm"]
        ALL --> RINGS["magic_rings.asm"]
        ALL --> JUMP["jump_feather.asm"]
        ALL --> SWORD["sword_collect.asm"]
        ALL --> FIST["fist_damage.asm"]
    end

    subgraph "Item Differentiation (WRAM $7E0730+)"
        DIFF1["Goldstar vs Hookshot"]
        DIFF2["Fishing Rod vs Portal Rod"]
    end
```

---

## Yaze Workflow

Yaze is the dungeon editor. Changes to dungeon rooms require Yaze, and Yaze changes must be synced back to the ASM source.

```mermaid
flowchart TD
    YAZE_EDIT["Edit in Yaze<br/>(Oracle-of-Secrets.yaze)"]
    YAZE_EDIT --> EXPORT["Export .zrd files<br/>(592 room data files)"]
    EXPORT --> SYNC["yaze_sync.py<br/>(sync to ASM)"]
    SYNC --> ASM["Dungeon ASM files<br/>(room data updated)"]
    ASM --> BUILD["build_rom.sh 168"]
    BUILD --> TEST["Test in Mesen2"]

    subgraph "Safety"
        SAFE["yaze_service.sh<br/>yaze safe-edit workflow<br/>(ai-infra-architect, untested)"]
    end

    YAZE_EDIT -.-> SAFE
```

**Key files requiring Yaze:**
- All dungeon room layouts and tile data
- Sprite placement within dungeon rooms
- Minecart track tile positions (must match ASM track table)
- Boss room dimensions and camera bounds
- Collision map data (water tiles, pits, etc.)
