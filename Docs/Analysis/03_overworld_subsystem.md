# Oracle of Secrets — Overworld Subsystem

**Generated:** 2026-03-21
**Scope:** ZSCustomOverworld data-driven engine, time system, world layout, and region definitions.

---

## Overworld Engine Architecture

```mermaid
graph TB
    subgraph "ZSCustomOverworld (Bank $28)"
        ZSOW["ZSCustomOverworld.asm<br/>(171KB — primary overworld logic)"]

        subgraph "Data Tables (starting $288000)"
            BG[".BGColorTable<br/>BG color per screen"]
            PAL[".MainPaletteTable<br/>Palette index (0-5)"]
            GFX[".OWGFXGroupTable<br/>8 GFX sheet IDs per screen"]
            OVL[".OverlayTable<br/>Weather/effects overlay"]
            SPR_PTR[".Overworld_SpritePointers<br/>Sprite sets (state-dependent)"]
            CAM[".ByScreen*_New (4 tables)<br/>Camera boundaries"]
        end

        subgraph "Critical Hooks"
            H1["$0283EE — Load Properties"]
            H2["$02C692 — Load Palettes"]
            H3["$02A9C4 — Handle Transitions"]
            H4["$09C4C7 — Load Sprites"]
        end
    end

    subgraph "Oracle Integration"
        TIME["Time System<br/>(time_system.asm)"]
        NIGHT["Oracle_CheckIfNight"]
        OW_ASM["overworld.asm<br/>entrances.asm<br/>special_areas.asm"]
    end

    H1 --> BG & PAL & GFX
    H2 --> PAL
    H3 --> CAM
    H4 --> SPR_PTR
    TIME --> NIGHT --> H4
    OW_ASM --> ZSOW
```

---

## World Map Layout

### Light World (Kalyxo)

```mermaid
graph TB
    subgraph "Kalyxo Overworld (Maps 0x00-0x3F)"
        NW["Northwest<br/>Lost Woods<br/>Maku Tree"]
        NE["Northeast<br/>Village<br/>Shops"]
        SW["Southwest<br/>Ranch<br/>Graveyard"]
        SE["Southeast<br/>Lake<br/>Zora Domain"]
        CENTER["Central<br/>Castle (D3)<br/>Hall of Secrets"]

        NW --- NE
        NW --- CENTER
        NE --- CENTER
        SW --- CENTER
        SE --- CENTER
        SW --- SE
    end
```

### Dark World (Eon Abyss)

```mermaid
graph TB
    subgraph "Eon Abyss (Maps 0x40-0x7F)"
        EA_NW["Northwest<br/>Corrupted Forest"]
        EA_NE["Northeast<br/>Eon Village"]
        EA_SW["Southwest<br/>Lava Lands<br/>(Ganondorf)"]
        EA_SE["Southeast<br/>Eon Zora Domain"]
        EA_CENTER["Central<br/>Fortress of Secrets (D8)"]

        EA_NW --- EA_NE
        EA_NW --- EA_CENTER
        EA_NE --- EA_CENTER
        EA_SW --- EA_CENTER
        EA_SE --- EA_CENTER
        EA_SW --- EA_SE
    end
```

### Special Overworld (Maps 0x80-0x9F)

```
     81  82  83  84  85  86  87
     ├───┼───┼───┼───┼───┼───┤
  80 │ K │ K │ E │ S │ S │ S │ S │
     ├───┼───┼───┼───┼───┼───┼───┤
  88 │ K │ K │ E │ S │ S │ S │ S │
     ├───┼───┼───┼───┼───┼───┼───┤
  90 │ E │ E │ E │ E │   │   │   │
     ├───┼───┼───┼───┼───┼───┼───┤
  98 │ E │ E │ E │ E │   │   │   │
     └───┴───┴───┴───┴───┴───┴───┘

K = Korok Cove (81, 82, 89, 8A)
E = East Kalyxo (83, 8B, 90-93, 98-9B)
S = Sky Islands (84-87, 8C-8F)
```

---

## Time System

```mermaid
stateDiagram-v2
    [*] --> Dawn: Hours=6
    Dawn --> Day: Hours=8
    Day --> Dusk: Hours=17
    Dusk --> Night: Hours=19
    Night --> Dawn: Hours=6

    state "RunClock (per frame)" as RC
    state "IncrementTime" as IT
    state "UpdatePalettes" as UP

    RC --> IT: Time should run
    IT --> UP: Hours/Minutes changed
```

**Structure at $7EE000:**
```
TimeState.Hours    — Current hour (0-23)
TimeState.Minutes  — Current minute (0-59)
TimeState.Speed    — Clock rate multiplier
TimeState.BlueVal  — Blue palette subtraction
TimeState.GreenVal — Green palette subtraction
TimeState.RedVal   — Red palette subtraction
```

**Integration:**
- `Oracle_CheckIfNight` — Called by ZSOW for sprite loading decisions
- Palette tinting — Subtracts RGB values from overworld palettes based on hour
- NPC behavior — Some NPCs check time for dialogue/presence changes

---

## Overworld Files

| File | Size | Purpose |
|------|------|---------|
| `ZSCustomOverworld.asm` | 171KB | Primary data-driven overworld engine |
| `overworld.asm` | — | Oracle overworld extensions |
| `entrances.asm` | — | Dungeon/building entrance definitions |
| `lost_woods.asm` | — | Lost Woods transition logic |
| `overlays.asm` | — | Weather/effect overlays |
| `special_areas.asm` | — | Unique area logic |
| `time_system.asm` | — | Day/night cycle |
| `weathervane.asm` | — | Weathervane teleport points |
| `world_map.asm` | — | World map screen data |
| `custom_gfx.asm` | — | Custom graphics loading |
| `HardwareRegisters.asm` | — | SNES register definitions |

---

## Region Access Progression

```mermaid
flowchart TD
    START["Game Start"] --> VILLAGE["Village + Surrounds"]
    VILLAGE --> D1["D1: Mushroom Grotto"]
    D1 --> D2["D2: Tail Palace"]
    D2 --> D3["D3: Kalyxo Castle"]
    D3 --> D4["D4: Zora Temple"]
    D4 --> ZORA_FALLS["Zora Falls<br/>(Song of Storms)"]
    D4 --> D5["D5: Glacia Estate"]
    D5 --> LAVA_VIS["Lava Lands<br/>(visible, not enterable)"]
    D5 --> D6["D6: Goron Mines"]
    D6 -->|Hammer| KOROK["Korok Cove"]
    KOROK --> EAST["East Kalyxo<br/>(River Zora Village)"]
    D6 --> SHRINES["Shrines S1-S3"]
    SHRINES -->|Master Sword| SKY["Sky Islands"]
    SHRINES --> D7["D7: Dragon Ship"]
    D7 -->|GameState=3| D8["D8: Fortress of Secrets"]
    D8 --> KYDREEOK["Kydreeok Boss"]
    KYDREEOK -->|Master Sword| LAVA["Lava Lands<br/>(Ganondorf)"]
```

---

## Known Issues

### Day/Night Sprite Conflict
ZSOW's `.Overworld_SpritePointers_state_..._New` tables are static per-area, compiled at build time. Oracle's `Oracle_CheckIfNight` runs at runtime to swap sprite sets for day/night. Labels from Oracle namespace are not visible to ZSOW during assembly, creating a disconnect.

### Lost Woods Logic
Custom transition logic in `lost_woods.asm` controls the Lost Woods maze sequence. If the player enters from an unexpected direction or with certain masks active, the transition state may not reset properly.

### Overworld → Dungeon Transition Black Screen
Fixed in commit `ebb03d3` (orphaned PHX removed from overworld reload), but the broader transition path should be regression-tested after any hook changes.
