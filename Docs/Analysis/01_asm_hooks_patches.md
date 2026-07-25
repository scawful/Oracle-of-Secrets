# Oracle of Secrets — ASM Hooks & Patches Subsystem

**Generated:** 2026-03-21
**Scope:** Hook architecture, ABI conventions, patch safety patterns, and known risk areas.

---

## Hook Architecture Overview

```mermaid
graph TB
    subgraph "Vanilla ROM (Banks $00-$07)"
        V1["$0283EE<br/>PreOverworld_LoadProperties"]
        V2["$02C692<br/>Overworld_LoadAreaPalettes"]
        V3["$02A9C4<br/>OverworldHandleTransitions"]
        V4["$09C4C7<br/>LoadOverworldSprites"]
        V5["$0289BF<br/>Intraroom transition"]
        V6["$07D077<br/>TileDetect_MainHandler"]
        V7["$07:82DA<br/>BunnyTransformation"]
        V8["$07:83D0<br/>Moon Pearl check"]
    end

    subgraph "Custom Code"
        C1["ZSCustomOverworld<br/>(Bank $28)"]
        C2["Follower hooks<br/>(followers.asm)"]
        C3["Water collision<br/>(water_collision.asm)"]
        C4["Dream triggers<br/>(attract_scenes.asm)"]
        C5["Mask transforms<br/>(mask_routines.asm)"]
    end

    V1 -->|JSL| C1
    V2 -->|JSL| C1
    V3 -->|JSL| C1
    V4 -->|JSL| C1
    V5 -->|JSL| C2
    V6 -->|JSL| C3
    V7 -->|JSL| C4
    V8 -->|JSL| C5
```

---

## 65816 ABI Standard

```mermaid
flowchart TD
    ENTRY["Hook Entry<br/>(JSL from vanilla)"]
    ENTRY --> CHECK{"Know caller's<br/>P register state?"}

    CHECK -->|Yes| DIRECT["Set expected width<br/>SEP/REP as needed"]
    CHECK -->|No| SAVE["PHP (save caller state)"]

    SAVE --> SET["SEP #$20 or REP #$20<br/>(set our width)"]
    SET --> WORK["Do work<br/>(operand sizes match P state)"]
    WORK --> RESTORE["PLP (restore caller state)"]
    RESTORE --> EXIT["RTL"]

    DIRECT --> WORK2["Do work"]
    WORK2 --> RESTORE2["Restore caller width<br/>SEP/REP to match"]
    RESTORE2 --> EXIT

    style SAVE fill:#ff6b6b,color:#fff
    style RESTORE fill:#ff6b6b,color:#fff
```

**Critical rules:**
1. M flag (bit 5) controls A size: 1=8-bit, 0=16-bit
2. X flag (bit 4) controls X/Y size: 1=8-bit, 0=16-bit
3. Mismatch causes BRK (crash) or silent register corruption
4. Long-entry routines (`*_Long`, `*_LongEntry`) are self-normalizing
5. Alternate hooks MUST preserve caller P state via PHP/PLP

---

## Hook Categories

### Overworld Hooks (ZSCustomOverworld)

| Address | Hook Name | Purpose | Feature Gate |
|---------|-----------|---------|-------------|
| $0283EE | PreOverworld_LoadProperties_Interupt | Load palettes/GFX per screen | Always ON |
| $02C692 | Overworld_LoadAreaPalettes | Palette swapping | Always ON |
| $02A9C4 | OverworldHandleTransitions | Screen-to-screen logic | Always ON |
| $09C4C7 | LoadOverworldSprites_Interupt | Sprite population (day/night) | Always ON |

### Follower Hooks

| Address | Hook Name | Purpose | Feature Gate |
|---------|-----------|---------|-------------|
| $0289BF | CheckForFollowerIntraroomTransition | Intraroom stairs/layers | `!ENABLE_FOLLOWER_TRANSITION_HOOKS` |
| (inter-room) | CheckForFollowerInterroomTransition | Door/room transitions | `!ENABLE_FOLLOWER_TRANSITION_HOOKS` |

### Dungeon Hooks

| Address | Hook Name | Purpose | Feature Gate |
|---------|-----------|---------|-------------|
| (water) | Custom water collision | Deep water tile checks | `!ENABLE_CUSTOM_ROOM_COLLISION` |
| (gates) | Water gate fill/drain | Zora Temple gates | `!ENABLE_WATER_GATE_HOOKS` |
| (gates) | Water gate overlay | Visual overlay redirect | `!ENABLE_WATER_GATE_OVERLAY_REDIRECT` |
| (gates) | Water gate room-entry | Persistence on re-entry | `!ENABLE_WATER_GATE_ROOMENTRY_RESTORE` |
| (prison) | D3 prison capture | Guard subtype gating | `!ENABLE_D3_PRISON_SEQUENCE` |

### Dream/Transform Hooks

| Address | Hook Name | Purpose | Feature Gate |
|---------|-----------|---------|-------------|
| $07:82DA | BunnyTransformation override | Dream sequence trigger | Always ON (prototype) |
| $07:83D0 | Moon Pearl check | Mask system integration | Always ON |

---

## Patch Safety Pattern

```mermaid
flowchart LR
    subgraph "Safe Patch Pattern"
        ORG1["org $XXXXXX<br/>(vanilla address)"]
        JSL1["JSL CustomRoutine"]
        NOP1["NOP (pad remaining bytes)"]

        ORG1 --> JSL1 --> NOP1
    end

    subgraph "Custom Routine"
        ENTRY1["CustomRoutine:"]
        WORK1["Custom logic"]
        VANILLA1["Execute displaced<br/>vanilla instruction(s)"]
        RTL1["RTL"]

        ENTRY1 --> WORK1 --> VANILLA1 --> RTL1
    end

    JSL1 -.->|calls| ENTRY1
```

**Validation commands:**
```bash
Scripts/Build/build_rom.sh 168                    # Build
python3 Scripts/Build/check_zscream_overlap.py      # Check for address conflicts
python3 Scripts/Generate/generate_hooks_json.py        # Regenerate hook manifest
python3 Scripts/Validate/verify_hooks_json.py          # Verify hook integrity
```

---

## Known Risk Areas

### Register-Width Bugs (Fixed but verify)

The commit `d30fb96` (2026-02-07) applied register-width safety patches across 8 files touching hooks, sprites, and transitions. This is a broad change that could introduce subtle regressions if any operand size was misjudged.

**Files affected:** hooks, sprites, transitions (8 files total)

### Stack Corruption (Fixed)

Commit `ebb03d3` (2026-02-25) removed an orphaned PHX in the Overworld reload path. An unmatched push would corrupt the stack on every overworld reload, leading to eventual crashes.

**Risk:** If any other path depends on the extra stack byte, removing it could shift return addresses.

### Day/Night Sprite Conflict

The `LoadOverworldSprites_Interupt` hook at $09C4C7 conflicts with Oracle's night check system. The ZSOW sprite tables are static per-area, but Oracle's `Oracle_CheckIfNight` tries to swap sprite sets at runtime. Labels from Oracle namespace are not visible to ZSOW during build.

**Status:** Known limitation, not yet resolved.
