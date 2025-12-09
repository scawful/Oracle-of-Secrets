# Oracle of Secrets: System Architecture

**Purpose**: Document how major systems interact to help AI agents understand the codebase structure.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Oracle_main.asm                          │
│  (Master include file - controls ROM layout and build order)   │
└─────────────────────────────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐        ┌───────────────┐        ┌───────────────┐
│  Core/        │        │  Sprites/     │        │  Overworld/   │
│  - link.asm   │        │  - all_sprites│        │  - ZSCustomOW │
│  - sram.asm   │        │  - Bosses/    │        │  - time_system│
│  - symbols.asm│        │  - NPCs/      │        │  - overlays   │
│  - patches.asm│        │  - Enemies/   │        │  - lost_woods │
│  - message.asm│        │  - Objects/   │        └───────────────┘
└───────────────┘        └───────────────┘
        │                         │
        ▼                         ▼
┌───────────────┐        ┌───────────────┐
│  Items/       │        │  Menu/        │
│  - all_items  │        │  - menu.asm   │
│  - ocarina    │        │  - menu_select│
│  - magic_bag  │        │  - menu_journal│
└───────────────┘        └───────────────┘
```

---

## 2. Namespace Organization

### 2.1 Oracle Namespace

All custom Oracle of Secrets code lives inside the `Oracle` namespace:

```asm
namespace Oracle
{
  ; Core systems
  incsrc "Core/link.asm"
  incsrc "Core/sram.asm"
  incsrc "Core/symbols.asm"

  ; Content
  incsrc "Music/all_music.asm"
  incsrc "Sprites/all_sprites.asm"
  incsrc "Items/all_items.asm"

  ; Patches go last
  incsrc "Core/patches.asm"
}
namespace off

; ZScream code is OUTSIDE the namespace
incsrc "Overworld/ZSCustomOverworld.asm"
```

### 2.2 Why This Matters

- Labels inside `namespace Oracle` become `Oracle.LabelName`
- ZScream uses its own conventions and must be outside
- Patches at end to ensure all labels are defined

---

## 3. Memory Map Overview

### 3.1 Bank Organization

| Bank Range | Purpose | Notes |
|------------|---------|-------|
| $00-$1F | Vanilla ALTTP + small patches | Limited free space |
| $20-$29 | ZScream Overworld Data | ~1.5MB reserved |
| $30 | Sprite prep/initialization | Oracle sprites start here |
| $31 | Main sprite logic | Enemy/NPC behavior |
| $32 | Boss logic | Complex sprite code |
| $33-$3F | Free space | Available for expansion |

### 3.2 RAM Regions

| Region | Purpose |
|--------|---------|
| $7E0000-$7E1FFF | Scratch RAM (volatile) |
| $7E2000-$7EFFFF | Game state RAM |
| $7EE000-$7EE0FF | TimeState struct |
| $7EF000-$7EFFFF | SRAM (saved data) |
| $7EF3C5-$7EF3D6 | Oracle progression flags |
| $7EF410 | Dreams bitfield |

### 3.3 Key SRAM Variables

```asm
; GameState ($7EF3C5) - Overall progression
;   0x00 = Very start
;   0x01 = Uncle reached
;   0x02 = Zelda rescued / Farore intro
;   0x03 = Agahnim defeated

; OOSPROG ($7EF3D6) - Oracle progression bitfield
; .fmp h.i.
;   i = Intro complete, Maku Tree met
;   h = Hall of Secrets visited
;   p = Pendant quest progress
;   m = Master Sword acquired
;   f = Fortress of Secrets

; OOSPROG2 ($7EF3C6) - Secondary progression
; .fbh .zsu
;   u = Uncle visited
;   s = Priest visited in sanctuary
;   z = Zelda brought to sanctuary
;   h = Uncle left house
;   b = Book of Mudora obtained
;   f = Fortune teller flag

; Dreams ($7EF410) - Dream sequence tracking
; .dts fwpb
;   (Individual dream completion flags)
```

---

## 4. System Interactions

### 4.1 ZScream Custom Overworld (ZSOW) Integration

ZSOW manages:
- Overworld map transitions
- Palette events
- Overlay data
- Custom collision

**Hook Points**:
```
OverworldHandleTransitions ($028000 area)
  └── Oracle_CheckIfNight (time-based sprite loading)
  └── LostWoods_PuzzleHandler (navigation puzzle)
  └── SongOfStorms overlay effects
```

**Known Conflicts**:
- Lost Woods puzzle directly modifies transition logic
- Day/Night sprites must check `Oracle_CheckIfNight`
- Song of Storms overlays need coordination with ZSOW

### 4.2 Time System

**File**: `Overworld/time_system.asm`

**Structure**:
```asm
struct TimeState $7EE000
{
  .Hours, .Minutes, .Speed
  .BlueVal, .GreenVal, .RedVal
  .TempColor, .SubColor
}
```

**Flow**:
```
RunClock (called each frame)
  ├── TimeSystem_CheckCanRun
  │     └── Check game mode, indoors status
  ├── TimeSystem_IncrementTime
  │     └── Update Hours/Minutes based on Speed
  └── TimeSystem_UpdatePalettes
        └── Apply color tinting based on time
```

**Integration Points**:
- `Oracle_CheckIfNight` - Called by ZSOW for sprite loading
- Palette system - Affects overworld colors
- NPC behavior - Some NPCs react to time

### 4.3 Sprite System

**Entry Points** (standard pattern):

```
Sprite_*_Long (JSL entry from sprite table)
  ├── PHB : PHK : PLB  (set data bank)
  ├── Sprite_*_Draw    (JSR - render)
  ├── Sprite_CheckActive (JSL - is active?)
  │     └── Sprite_*_Main  (JSR - if active)
  ├── PLB
  └── RTL
```

**State Machine**:
```
SprAction (per-sprite state variable)
  └── JumpTableLocal dispatches to state handlers
      ├── State_Idle
      ├── State_Chase
      ├── State_Attack
      └── State_Retreat
```

**Key Variables** (indexed by X):
| Address | Name | Purpose |
|---------|------|---------|
| $0D00 | SprY | Y position (low byte) |
| $0D10 | SprX | X position (low byte) |
| $0D80 | SprAction | Current state |
| $0DA0 | SprHealth | Hit points remaining |
| $0E40 | SprNbrOAM | OAM slot count |

### 4.4 Menu System

**File**: `Menu/menu.asm`

**State Machine**:
```
MenuMode ($0200) - Current menu state
  ├── $00 = Not in menu
  ├── $01 = Opening animation
  ├── $02 = Item select
  ├── $0C = Magic Bag submenu
  ├── $0D = Ring Box submenu
  └── $0E = Song select submenu
```

**Flow**:
```
Menu_Entry (from pause input)
  ├── Menu_InitGraphics
  ├── Menu_Upload* (VRAM transfers)
  └── Menu_MainLoop
        ├── Handle input
        ├── Update selection
        └── Menu_Draw*
```

### 4.5 Dialogue System

**Files**: `Core/message.asm`, `Core/messages.org`

**Message Format** (in messages.org):
```
** 20 - Maku Tree Part1
[W:02][S:03]Ah, [L]!
[2]Thank the Goddesses you are
[3]alright. I feared the worst.
[V]A dark shadow has befallen us.[K]
```

**Control Codes**:
| Code | Meaning |
|------|---------|
| `[2]`, `[3]` | Line 2, Line 3 |
| `[K]` | Wait for button press |
| `[V]` | Continue on same line |
| `[W:XX]` | Wait time |
| `[S:XX]` | Text speed |
| `[SFX:XX]` | Play sound effect |
| `[CH2I]` | 2-choice prompt |
| `[CH3]` | 3-choice prompt |
| `[L]` | Player name |

**Display Macros**:
```asm
%ShowUnconditionalMessage($20)  ; Force display
%ShowSolicitedMessage($20)      ; On interaction only
```

---

## 5. Hook Architecture

### 5.1 Hook Types

**Type 1: Inline Patch** (replace vanilla code)
```asm
pushpc
org $02XXXX           ; Vanilla address
  JSL MyHook          ; Replace original instruction
  NOP : NOP           ; Pad to match original size
pullpc
```

**Type 2: Table Override** (jump table entry)
```asm
pushpc
org $07F000+($ID*2)   ; Jump table for sprite $ID
  dw Sprite_Custom_Prep
pullpc
```

**Type 3: Extended Logic** (call original + extend)
```asm
MyHook:
{
  JSL OriginalRoutine ; Preserve original behavior
  ; Add custom logic
  LDA.w CustomFlag
  BEQ .skip
    JSL CustomHandler
  .skip
  RTL
}
```

### 5.2 Hook Documentation Pattern

Every hook should document:

```asm
; =========================================================
; Hook: $XXBANK:ADDR
; Purpose: [What this hook adds/changes]
; Vanilla Code: [What original code did]
; Clobbered: [Registers modified]
; Dependencies: [Other systems affected]
; =========================================================
```

---

## 6. Build System

### 6.1 Build Order (Critical)

```
1. Core/symbols.asm      - Memory declarations
2. Core/sram.asm         - SRAM layout
3. Core/link.asm         - Player modifications
4. Music/all_music.asm   - SPC700 data
5. Sprites/all_sprites.asm - All sprite code
6. Items/all_items.asm   - Item handlers
7. Menu/menu.asm         - Menu system
8. Dungeons/             - Dungeon-specific code
9. Core/patches.asm      - Vanilla patches (LAST)
10. Overworld/ZSCustomOverworld.asm - ZSOW (OUTSIDE namespace)
```

### 6.2 Build Commands

```bash
# Fast build
./run.sh

# MCP tools
mcp__book-of-mudora__run_build()   # Build ROM
mcp__book-of-mudora__lint_asm()    # Check style
mcp__book-of-mudora__analyze_patches()  # Review patches
```

---

## 7. Debugging Workflow

### 7.1 Common Debug Points

| Symptom | Check First |
|---------|-------------|
| Crash on room enter | Sprite prep routine, invalid JSL target |
| Wrong graphics | SprGfx assignment, DMA timing |
| Frozen game | Infinite loop in Main, missing RTS/RTL |
| Black screen | Palette loading, HDMA setup |
| Corrupt saves | SRAM address conflict, missing bank setup |

### 7.2 Debug Tools

**Yaze MCP** (in-development):
```python
mcp__yaze_mcp__read_memory("7E0010", 2)   # Read RAM
mcp__yaze_mcp__add_breakpoint("02XXXX")    # Set breakpoint
mcp__yaze_mcp__get_game_state()            # Dump current state
```

**Hyrule Historian**:
```python
mcp__hyrule-historian__lookup_address("02XXXX")
mcp__hyrule-historian__search_oracle_code("Sprite_Booki")
mcp__hyrule-historian__get_ram_info("SprAction")
```

### 7.3 Logging

```asm
; Build-time logging
%log_section("Sprites", !LOG_SPRITES)

; Enable in build:
!LOG_SPRITES = 1  ; Set in config

; Output appears in build log
```

---

## 8. Common Integration Patterns

### 8.1 Adding a New Sprite

1. Create file: `Sprites/Enemies/my_sprite.asm`
2. Define properties using standard order
3. Implement `_Long`, `_Prep`, `_Main`, `_Draw`
4. Add include to `Sprites/all_sprites.asm`
5. Add to sprite table with `org` directive
6. Build and test

### 8.2 Adding a Quest Flag

1. Find free bit in OOSPROG/OOSPROG2
2. Document in `Core/sram.asm`
3. Update this file's SRAM section
4. Use in code:
   ```asm
   LDA.l OOSPROG : ORA.b #$XX : STA.l OOSPROG
   ```

### 8.3 Adding a New Hook

1. Find vanilla address with Hyrule Historian
2. Document what original code does
3. Create hook with `pushpc`/`pullpc`
4. Add `assert` to verify space
5. Test vanilla behavior still works

---

## 9. System Dependency Graph

```
                    ┌─────────────┐
                    │ TimeSystem  │
                    └──────┬──────┘
                           │ Oracle_CheckIfNight
                           ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Lost Woods  │────▶│    ZSOW     │◀────│  Overlays   │
│   Puzzle    │     │ Transitions │     │   System    │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
       ┌─────────────┐           ┌─────────────┐
       │   Sprites   │           │   Events    │
       │  (Loading)  │           │  (Triggers) │
       └──────┬──────┘           └──────┬──────┘
              │                         │
              └───────────┬─────────────┘
                          ▼
                   ┌─────────────┐
                   │   Player    │
                   │   (Link)    │
                   └─────────────┘
```

---

## 10. AI Agent Checklist

When working on Oracle of Secrets:

1. [ ] Check `oracle.org` for related tasks
2. [ ] Read existing code in affected files
3. [ ] Verify memory map for conflicts
4. [ ] Use Hyrule Historian for vanilla lookups
5. [ ] Follow StyleGuide.md conventions
6. [ ] Run build after changes
7. [ ] Document any new hooks
8. [ ] Update this file if adding new systems
