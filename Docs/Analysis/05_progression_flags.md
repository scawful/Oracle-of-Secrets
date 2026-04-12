# Oracle of Secrets — Progression & Flags Subsystem

**Generated:** 2026-03-21
**Scope:** Quest state management, SRAM layout, progression helpers, MapIcon system, and NPC conversion status.

---

## Progression Architecture

```mermaid
graph TB
    subgraph "SRAM Persistent State ($7EF000+)"
        GS["$7EF3C5 GameState<br/>0=start, 1=intro,<br/>2=Kydrog done, 3=endgame"]
        PROG1["$7EF3D6 OOSPROG<br/>Quest milestones bitfield"]
        PROG2["$7EF3C6 OOSPROG2<br/>Secondary progression"]
        ICON["$7EF3C7 MapIcon<br/>Quest marker (0-9)"]
        CRYS["$7EF37A Crystals<br/>Dungeon completion bitfield (7 dungeons)"]
        PEND["$7EF374 Pendants<br/>Shrine completion (3 bits)"]
        DREAMS["$7EF410 Dreams<br/>Dream seen bitfield"]
        WATER["$7EF411 WaterGateStates<br/>Zora Temple persistence"]
    end

    subgraph "Progression Helpers (Core/progression.asm)"
        GCC["GetCrystalCount<br/>Popcount of crystal bitfield → 0-7"]
        UMI["UpdateMapIcon<br/>MapIcon = crystal_count + 1"]
        SRM["SelectReactionMessage<br/>Table-walker for NPC responses"]
    end

    CRYS --> GCC
    GCC --> UMI --> ICON
    GCC --> SRM

    subgraph "Consumers"
        MAKU["Maku Tree<br/>(hint cascade D7→D1)"]
        ZORA["Zora NPCs<br/>(Crystals AND #$20, post-D4)"]
        ELDER_NPC["Village Elder<br/>(ElderGuideStage + MapIcon)"]
        DEKU["Deku Scrub<br/>(Crystals AND #$10, despawn)"]
        OWL["Eon Owl<br/>(exact bitmask #$77)"]
    end

    SRM --> MAKU
    GCC --> ZORA
    UMI --> ELDER_NPC
    CRYS --> DEKU
    CRYS --> OWL
```

---

## GameState Progression

```mermaid
stateDiagram-v2
    [*] --> GS0: New game
    GS0 --> GS1: Intro complete
    GS1 --> GS1: D1 through D6 + Shrines
    GS1 --> GS2: Kydrog defeated (D7)
    GS2 --> GS3: Farore rescued (D7 post-boss)
    GS3 --> GS3: D8, Kydreeok, Ganondorf
    GS3 --> PostGame: Ganondorf defeated

    state "GameState=0 (Start)" as GS0
    state "GameState=1 (Adventure)" as GS1
    state "GameState=2 (Kydrog Done)" as GS2
    state "GameState=3 (Endgame)" as GS3
```

---

## MapIcon Values

| Value | Location | Trigger |
|-------|----------|---------|
| $00 | Maku Tree (start) | Game start |
| $01 | D1 Mushroom Grotto | After intro |
| $02 | D2 Tail Palace | D1 crystal |
| $03 | D3 Kalyxo Castle | D2 crystal |
| $04 | D4 Zora Temple | D3 crystal |
| $05 | D5 Glacia Estate | D4 crystal |
| $06 | D6 Goron Mines | D5 crystal |
| $07 | D7 Dragon Ship | D6 crystal |
| $08 | Fortress of Secrets | D7 crystal |
| $09 | Tail Pond | Special |

---

## Crystal Bitfield ($7EF37A)

```
Bit 0 = D1 (Mushroom Grotto)
Bit 1 = D2 (Tail Palace)
Bit 2 = D3 (Kalyxo Castle)
Bit 3 = D4 (Zora Temple)
Bit 4 = D5 (Glacia Estate)
Bit 5 = D6 (Goron Mines)
Bit 6 = D7 (Dragon Ship)
```

---

## NPC Conversion Status

The progression infrastructure provides shared helpers (`GetCrystalCount`, `UpdateMapIcon`, `SelectReactionMessage`) to replace per-NPC hardcoded checks. Current conversion status:

```mermaid
graph LR
    subgraph "Converted to Helpers"
        C1["Maku Tree ✅<br/>Complete cascade (D7→D1)"]
    end

    subgraph "Using Direct Checks"
        D1["Zora NPCs<br/>Crystals AND #$20"]
        D2["Village Elder<br/>ElderGuideStage + MapIcon"]
        D3["Deku Scrub<br/>Crystals AND #$10"]
        D4["Eon Owl<br/>Bitmask #$77"]
    end

    subgraph "Unknown Pattern"
        U1["Ranch Girl"]
        U2["Bug Net Kid"]
        U3["Bottle Vendor"]
    end

    style C1 fill:#51cf66,color:#fff
    style D1 fill:#ffd43b,color:#000
    style D2 fill:#ffd43b,color:#000
    style D3 fill:#ffd43b,color:#000
    style D4 fill:#ffd43b,color:#000
    style U1 fill:#ff6b6b,color:#fff
    style U2 fill:#ff6b6b,color:#fff
    style U3 fill:#ff6b6b,color:#fff
```

---

## Progression Gating (Full Chain)

```mermaid
flowchart TD
    NEW["New Game<br/>GameState=0, MapIcon=0"]
    NEW --> INTRO["Intro sequence<br/>GameState=1"]

    INTRO --> D1["D1: Mushroom Grotto<br/>Crystal bit 0"]
    D1 --> MUSHROOM["Mushroom → Magic Powder<br/>(Deku Scrub quest)"]
    MUSHROOM --> D2["D2: Tail Palace<br/>Crystal bit 1"]
    D2 --> DREAM1["Dream 1: Sealing War"]
    DREAM1 --> D3["D3: Kalyxo Castle<br/>Crystal bit 2<br/>King's Sword obtained"]

    D3 --> D4["D4: Zora Temple<br/>Crystal bit 3<br/>Zora Mask obtained"]
    D4 --> SOH["Song of Healing<br/>Princess revelation"]
    SOH --> FALLS["Zora Falls<br/>(Song of Storms → Blue Tunic)"]

    D4 --> D5["D5: Glacia Estate<br/>Crystal bit 4<br/>Fire Rod obtained"]
    D5 --> DREAM2["Dream 2: Ranch Girl curse"]
    D5 --> LAVA_VIS["Lava Lands visible<br/>(not enterable)"]

    D5 --> D6["D6: Goron Mines<br/>Crystal bit 5<br/>Hammer obtained"]
    D6 --> KOROK["Korok Cove<br/>(Hammer required)"]
    KOROK --> EAST["East Kalyxo<br/>River Zora reconciliation"]

    D6 --> S1["Shrine S1"]
    D6 --> S2["Shrine S2"]
    D6 --> S3["Shrine S3 (Vaati boss)"]
    S1 & S2 & S3 --> SWORD["Master Sword forged"]

    SWORD --> SKY["Sky Islands<br/>Dream 3: Observatory"]
    SWORD --> D7["D7: Dragon Ship<br/>Crystal bit 6"]
    D7 --> KYDROG_DEFEAT["Kydrog defeated<br/>GameState=2"]
    KYDROG_DEFEAT --> FARORE_RESCUE["Farore rescued<br/>GameState=3"]

    FARORE_RESCUE --> D8["D8: Fortress of Secrets<br/>Voice encounters (4x)"]
    D8 --> PYRAMID["Temporal Pyramid<br/>3 visions"]
    PYRAMID --> KYDREEOK["Kydreeok boss<br/>Song of Healing → Kydrog Mask"]
    KYDREEOK --> GANONDORF["Ganondorf<br/>3-phase final boss"]
    GANONDORF --> POSTGAME["Post-game<br/>Healing Abyss"]
```

---

## Feature-Gated Progression Code

| Feature | Gate | Status | Risk |
|---------|------|--------|------|
| D3 Prison capture/escape | `!ENABLE_D3_PRISON_SEQUENCE` = 0 | OFF, untested | Progression desync |
| D7 Farore rescue pipeline | `!ENABLE_D7_FARORE_RESCUE_SEQUENCE` = 0 | OFF, untested | GameState transition |
| Minecart cart-required shutters | `!ENABLE_MINECART_CART_SHUTTERS` = 0 | OFF, untested | Dungeon soft-lock |
| Water gate room-entry restore | `!ENABLE_WATER_GATE_ROOMENTRY_RESTORE` = 0 | OFF, untested | Save corruption |
