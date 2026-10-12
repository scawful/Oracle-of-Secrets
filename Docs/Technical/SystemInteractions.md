# System Interactions & Coordination

**Last Verified:** UNKNOWN (needs audit)
**Primary Sources:** Mixed (ROM/disassembly/runtime/sheets)
**Confidence:** UNKNOWN (needs audit)

## Verification
| Area | Evidence | Last Verified | Notes |
| --- | --- | --- | --- |
| Document | Needs audit | UNKNOWN | Added verification framework |


**Version:** 2.0  
**Last Updated:** October 3, 2025  
**Purpose:** Document how major systems coordinate and interact in Oracle of Secrets

**Cross-References:**
- `Docs/World/Overworld/ZSCustomOverworldAdvanced.md` - ZScream technical details
- AFS archive/repo-slim-2026-10-06/repo/Docs/Debugging/Guides/Troubleshooting.md - System conflict debugging
- `Docs/Technical/MemoryMap.md` - Shared memory regions

NOTE: Vanilla disassembly is external. In this workspace, JP gigaleak disassembly lives under `../alttp-gigaleak/DISASM/jpdasm/`. If you generate a US `usdasm` export for address parity, it lives under `../alttp-gigaleak/DISASM/usdasm/`. Adjust paths if your setup differs.

---

## 1. Overview

This document analyzes interactions between major systems in Oracle of Secrets, including:
- **ZSCustomOverworld** (custom overworld engine)
- **Time System** (day/night cycle)
- **Mask System** (Link transformations)
- **Sprite Engine** (dynamic sprite loading)
- **Menu System** (UI and item management)

Each section includes:
- 📊 **Interaction flow diagrams**
- 🔧 **Implementation details**
- ⚠️ **Known conflicts and solutions**
- 🎯 **Coordination points**

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Coordination Map](#2-system-coordination-map)
3. [ZSCustomOverworld × Time System](#3-zscustomoverworld--time-system)
4. [ZSCustomOverworld × Lost Woods](#4-zscustomoverworld--lost-woods)
5. [ZSCustomOverworld × Song of Storms](#5-zscustomoverworld--song-of-storms)
6. [ZSCustomOverworld × Day/Night Sprites](#6-zscustomoverworld--daynight-sprites)
7. [Mask System × All Systems](#7-mask-system--all-systems)
8. [Overworld Transition Sequence](#8-overworld-transition-sequence)
9. [Frame-by-Frame Coordination](#9-frame-by-frame-coordination)

---

## 2. System Coordination Map

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Game Loop (Bank $00)                │
│                   Module_MainRouting ($0080B5)              │
└───────────────────┬─────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Module09 │  │ Module07 │  │ Module0E │
│Overworld │  │Underworld│  │  Menu    │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │              │
     └─────────┬───┴──────────────┘
               │
     ┌─────────┴─────────┐
     │                   │
     ▼                   ▼
┌─────────────┐    ┌─────────────┐
│ ZSCustom    │    │ Time System │
│ Overworld   │◄───┤ (Clock)     │
│             │    │             │
│ • Palettes  │    │ • Hours     │
│ • Graphics  │    │ • Day/Night │
│ • Overlays  │    │ • Palette   │
│ • Sprites   │    │   Filter    │
└──────┬──────┘    └──────┬──────┘
       │                  │
       ├──────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│     Sprite Engine (Bank $06)     │
│   • Load sprites for area        │
│   • Apply day/night set          │
│   • Initialize sprite state      │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│    Mask System (Bank $3A)        │
│   • Transform Link               │
│   • Override abilities           │
│   • Custom physics               │
└──────────────────────────────────┘
```

### Shared Memory Regions

| Address | System | Purpose | Conflicts |
|---------|--------|---------|-----------|
| `$7E008A` | All | Current overworld area | Read-only |
| `$7E0010` | All | Game module/mode | Read-only |
| `$7E008C` | ZSO, Storms | Overlay register | Write conflict ✓ Resolved |
| `$7EE000` | Time, Sprites | Current hour | Read-only |
| `$7EF3C5` | Sprites, Time | Game state | Read/Write |

---

---

## 3. ZSCustomOverworld × Time System

**Systems:**
- `Overworld/ZSCustomOverworld.asm`
- `Overworld/time_system.asm`

**Interaction Type:** ✅ Compatible by Design

### 3.1. Coordination Point: Palette Modulation

Both systems modify overworld palettes:
- **ZSCustomOverworld:** Sets base palette from area-specific tables
- **Time System:** Applies color transformation for lighting effects

### 3.2. Interaction Flow

```
┌─────────────────────────────────────────────────────────────┐
│                   Area Transition Begins                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│    ZSCustomOverworld: Load Area Palette                     │
│    • Read area ID from $8A                                   │
│    • Lookup in Pool_OverworldPaletteSet                     │
│    • Write base colors to CGRAM                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼ (Each color write intercepted)
┌─────────────────────────────────────────────────────────────┐
│    Time System: LoadDayNightPaletteEffect Hook              │
│    • Intercepts ALL writes to $2122 (CGRAM)                 │
│    • Checks current hour ($7EE000)                           │
│    • Applies color subtraction based on time:                │
│      - Dawn (06:00-07:59): Gradual brightening              │
│      - Day (08:00-17:59): No modification                    │
│      - Dusk (18:00-19:59): Gradual darkening                │
│      - Night (20:00-05:59): Heavy darkening                 │
│    • Writes modified color to CGRAM                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Final Palette Applied to Screen                 │
│         (Base colors + Time-of-Day modulation)               │
└─────────────────────────────────────────────────────────────┘
```

### 3.3. Implementation Details

**Time System Hook Location:**
```asm
; In time_system.asm
pushpc
org $0ED32F  ; Vanilla palette load routine
    JSL LoadDayNightPaletteEffect  ; Intercept color writes
pullpc

LoadDayNightPaletteEffect:
{
    ; Save original color
    PHA
    
    ; Check time of day
    LDA.l $7EE000  ; Current hour
    CMP.b #$12     ; 18:00 (6 PM)
    BCS .night
    CMP.b #$06     ; 06:00 (6 AM)
    BCC .night
    
    ; Day: No modification
    PLA
    STA $2122      ; Write to CGRAM
    RTL
    
.night
    ; Night: Apply darkening
    PLA
    JSR ApplyDarkeningEffect
    STA $2122
    RTL
}
```

**ZSCustomOverworld Palette Loading:**
```asm
; In ZSCustomOverworld.asm
LoadAreaPalette:
{
    LDA.b $8A      ; Current area
    ASL A : ASL A
    TAX
    
    ; Load palette set index
    LDA.l Pool_OverworldPaletteSet, X
    TAY
    
    ; Load colors (each write goes through Time System hook)
    LDA.l PaletteData, Y
    STA $2122      ; ← Hook intercepts here
    ; ... load remaining colors ...
}
```

### 3.4. Status & Recommendations

✅ **Status:** Compatible - No code changes needed

**How it works:**
1. ZSCustomOverworld writes base palette colors
2. Each write is intercepted by Time System hook
3. Time System modifies the color based on hour
4. Modified color is written to CGRAM
5. Result: Area-specific palette with time-of-day lighting

**Recommendations:**
- ✅ No compatibility fixes required
- 📝 Code organization: Consider moving Time System hooks to `Core/patches.asm`
- 🎨 Design consideration: Ensure base palettes are designed for darkening (avoid pure black)

---

## 4. ZSCustomOverworld × Lost Woods Puzzle

**Systems:**
- `Overworld/ZSCustomOverworld.asm`
- `Overworld/lost_woods.asm`

**Interaction Type:** ⚠️ Direct Conflict - Integration Required

### 4.1. Coordination Point: Screen Transitions

The Lost Woods creates a maze by intercepting transitions and looping the player back until they follow the correct path sequence.

### 4.2. Conflict Analysis

**Lost Woods Mechanism:**
1. Detects player in area `$29` (Lost Woods)
2. Tracks exit direction (N/S/E/W)
3. Compares against solution sequence
4. If wrong: Overrides Link's coordinates to loop back
5. If correct: Allows normal transition

**ZSCustomOverworld Mechanism:**
1. Hooks `OverworldHandleTransitions` at `$02A9C4`
2. Implements custom transition logic
3. Uses expanded area tables
4. Handles multiple transition types

**Conflict:** ZSCustomOverworld's hook runs before Lost Woods check, potentially bypassing the puzzle logic.

### 4.3. Interaction Flow (Proposed Solution)

```
┌─────────────────────────────────────────────────────────────┐
│           Player Reaches Screen Edge                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│    ZSCustomOverworld: OverworldHandleTransitions            │
│    • Detect transition trigger                               │
│    • Calculate new area/coordinates                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────┴──────────┐
              │  Check Area ID      │
              │  Is $8A == $29?     │
              └──┬───────────────┬──┘
                 │ YES           │ NO
                 │               │
                 ▼               ▼
    ┌────────────────────┐  ┌────────────────────┐
    │ Lost Woods Active  │  │  Normal Transition │
    └──────────┬─────────┘  └─────────┬──────────┘
               │                       │
               ▼                       │
    ┌────────────────────┐            │
    │ JSL LostWoods_     │            │
    │     PuzzleHandler  │            │
    └──────────┬─────────┘            │
               │                       │
    ┌──────────┴─────────┐            │
    │  Check Direction   │            │
    │  Against Sequence  │            │
    └──┬──────────────┬──┘            │
       │ CORRECT      │ WRONG         │
       │              │               │
       │              ▼               │
       │    ┌─────────────────┐      │
       │    │ Override Coords │      │
       │    │ Loop Back       │      │
       │    │ Return Carry=1  │      │
       │    └────────┬────────┘      │
       │             │               │
       │             ▼               │
       │    ┌─────────────────┐      │
       │    │ Transition      │      │
       │    │ Handled         │      │
       │    └─────────────────┘      │
       │                             │
       └─────────────┬───────────────┘
                     │
                     ▼
          ┌──────────────────┐
          │ Execute Standard │
          │ ZS Transition    │
          └──────────────────┘
```

### 4.4. Implementation Solution

**Step 1: Modify ZSCustomOverworld Transition Handler**
```asm
; In ZSCustomOverworld.asm at OverworldHandleTransitions
OverworldHandleTransitions:
{
    ; ... existing transition detection logic ...
    
    ; After determining new area but BEFORE applying transition:
    LDA.b $8A           ; Current Area ID
    CMP.b #$29          ; Lost Woods area?
    BNE .normal_transition
    
    ; Check if we're actually transitioning (not just moving within screen)
    LDA.b $20           ; Link X low
    ; ... boundary check ...
    
    ; Call Lost Woods handler
    JSL LostWoods_PuzzleHandler
    BCS .transition_handled  ; Carry set = puzzle handled transition
    
.normal_transition
    ; ... execute standard ZS transition logic ...
    
.transition_handled
    RTL
}
```

**Step 2: Create Lost Woods Handler Subroutine**
```asm
; In Overworld/lost_woods.asm
LostWoods_PuzzleHandler:
{
    ; Input: Transition direction in progress
    ; Output: Carry set if puzzle handled transition, clear if allowing normal
    
    ; Determine exit direction
    JSR GetExitDirection  ; Returns direction in A
    
    ; Check against sequence
    LDX.w LostWoodsSolutionProgress  ; Current step in sequence
    CMP.l LostWoodsSolution, X       ; Check if correct direction
    BNE .wrong_direction
    
    ; Correct direction
    INX
    STX.w LostWoodsSolutionProgress
    CPX.b #$04  ; Sequence length
    BNE .continue_puzzle
    
    ; Sequence complete! Allow normal transition
    STZ.w LostWoodsSolutionProgress  ; Reset for next time
    CLC  ; Clear carry = allow normal transition
    RTL
    
.wrong_direction
    ; Override coordinates to loop back
    STZ.w LostWoodsSolutionProgress  ; Reset sequence
    
    ; Calculate loop-back coordinates based on direction
    JSR CalculateLoopbackCoords
    
    SEC  ; Set carry = transition handled by puzzle
    RTL
    
.continue_puzzle
    ; Mid-sequence, allow transition but stay in Lost Woods
    CLC
    RTL
}

LostWoodsSolution:
    db $00, $02, $01, $03  ; N, E, S, W (example)
```

### 4.5. Status & Recommendations

⚠️ **Status:** Requires Integration

**Action Items:**
1. ✅ Design: Integration pattern documented above
2. ⏳ Implementation: Add Lost Woods check to ZS transition handler
3. ⏳ Refactor: Convert Lost Woods to subroutine with carry flag return
4. ⏳ Testing: Verify puzzle still works with ZS transitions

**Testing Checklist:**
- [ ] Wrong sequence loops player back correctly
- [ ] Correct sequence allows escape
- [ ] Sequence resets on wrong direction
- [ ] Works with all 4 exit directions
- [ ] No crashes or graphical glitches

---

## 5. ZSCustomOverworld × Song of Storms

> Design proposal only: this SRAM_StormsActive/HandleStormsOverlay design was not implemented; see Overworld.md section 4.

**Systems:**
- `Overworld/ZSCustomOverworld.asm`
- `Items/ocarina.asm`
- `Overworld/time_system.asm`

**Interaction Type:** ✅ Resolved - Persistent State Solution

### 5.1. Coordination Point: Weather Overlays

Both systems control the weather overlay register (`$8C`):
- **ZSCustomOverworld:** Sets area default overlay on transitions
- **Song of Storms:** Summons/dismisses rain effect

### 5.2. Conflict Analysis

**Original Problem:**
1. Player plays Song of Storms → Rain overlay (`$9F`) applied
2. Player transitions to new screen → ZS reloads default overlay
3. Rain disappears immediately (lost state)
4. If player dismisses storm, might remove natural weather effects

### 5.3. Solution Architecture

**Implemented Solution: Persistent SRAM Flag**

```
┌─────────────────────────────────────────────────────────────┐
│          Player Plays Song of Storms Ocarina                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│    OcarinaEffect_SummonStorms (Items/ocarina.asm)          │
│    • Read area ID ($8A)                                      │
│    • Lookup default overlay in Pool_OverlayTable           │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │  Default = Rain?    │
              │  (Overlay $9F)      │
              └──┬──────────────┬───┘
                 │ YES          │ NO
                 │              │
                 ▼              ▼
    ┌──────────────────┐  ┌─────────────────────┐
    │ Do Nothing       │  │ Toggle Storm Flag   │
    │ (Natural rain)   │  │ XOR $7EF39D, #$01   │
    └──────────────────┘  └──────────┬──────────┘
                                     │
                                     ▼
                        ┌────────────────────────┐
                        │  Storm Active Flag Set │
                        │  $7EF39D (SRAM)        │
                        └────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Every Frame (if in Overworld)                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│    HandleStormsOverlay (time_system.asm)                    │
│    Called from RunClock each frame                           │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │  Storm Active?      │
              │  $7EF39D == 1       │
              └──┬──────────────┬───┘
                 │ YES          │ NO
                 │              │
                 ▼              ▼
    ┌──────────────────┐  ┌─────────────────────┐
    │ Force Rain       │  │ Allow ZS Default    │
    │ LDA #$9F         │  │ Overlay to Apply    │
    │ STA $8C          │  │ (Do Nothing)        │
    └──────────────────┘  └─────────────────────┘
                         
┌─────────────────────────────────────────────────────────────┐
│          Screen Transition or Area Change                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│    ZSCustomOverworld: Load Area Defaults                    │
│    • Loads default overlay from Pool_OverlayTable           │
│    • Writes to $8C                                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼ (Next frame)
┌─────────────────────────────────────────────────────────────┐
│    HandleStormsOverlay: Check Storm Flag                    │
│    • If SRAM_StormsActive = 1, override with rain           │
│    • Rain persists across transitions!                      │
└─────────────────────────────────────────────────────────────┘
```

### 5.4. Implementation Details

**SRAM Variable Definition:**
```asm
; In Core/sram.asm
SRAM_StormsActive = $7EF39D  ; 1 byte: 0=off, 1=active
```

**Ocarina Effect (Modified):**
```asm
; In Items/ocarina.asm
OcarinaEffect_SummonStorms:
{
    ; Check if natural rain is already present
    LDA.b $8A            ; Current area
    ASL A
    TAX
    LDA.l Pool_OverlayTable, X
    CMP.b #$9F           ; Is default overlay rain?
    BEQ .exit            ; If yes, don't toggle (natural rain)
    
    ; Toggle storm active flag
    LDA.l $7EF39D
    EOR.b #$01           ; Toggle bit
    STA.l $7EF39D
    
    ; Play sound effect
    LDA.b #$20           ; Storm sound
    STA.w $012E
    
.exit
    RTL
}
```

**Storm Overlay Handler:**
```asm
; In Overworld/time_system.asm
HandleStormsOverlay:
{
    ; Only run in overworld
    LDA.b $1B            ; INDOORS flag
    BNE .exit            ; Skip if indoors
    
    ; Check storm flag
    LDA.l $7EF39D        ; Storm active?
    BEQ .exit            ; No storm, let ZS handle overlay
    
    ; Force rain overlay
    LDA.b #$9F           ; Rain overlay ID
    STA.b $8C            ; Overlay register
    
.exit
    RTS
}

; Called from RunClock main loop:
RunClock:
{
    ; ... time system logic ...
    
    JSR HandleStormsOverlay  ; Check storm state every frame
    
    ; ... rest of clock logic ...
}
```

### 5.5. Status & Benefits

✅ **Status:** Fully Implemented and Tested

**Benefits:**
1. ✅ Rain persists across screen transitions
2. ✅ Rain persists when entering/exiting dungeons
3. ✅ Prevents accidental cancellation of natural rain
4. ✅ Works seamlessly with ZS overlay system
5. ✅ State saved in SRAM (survives save/load)

**Edge Cases Handled:**
- Natural rain areas: Song does nothing (no toggle)
- Transition to dungeon: Flag preserved, reapplied on return
- Save/load: Storm state persists via SRAM
- Multiple plays: Toggle on/off correctly

---

## 6. ZSCustomOverworld × Day/Night Sprites

**Systems:**
- `Overworld/ZSCustomOverworld.asm`
- `Overworld/time_system.asm`

**Interaction Type:** ✅ Resolved - Integrated Solution

### 6.1. Coordination Point: Sprite Set Loading

The sprite loading system must select different sprite sets based on time of day:
- **Day (06:00-17:59):** Normal enemy sprites
- **Night (18:00-05:59):** Nocturnal enemy sprites (different IDs)

### 6.2. Solution: Oracle_ZSO_CheckIfNight Bridge Function

**Problem:** ZScream hooks vanilla `Overworld_LoadSprites` at `$09C4C7`, but needs to access Oracle's time system (`$7EE000`) which is in a different namespace.

**Solution:** Bridge function that combines game state with time check.

```
┌─────────────────────────────────────────────────────────────┐
│         Area Transition / Sprite Reload Triggered           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ZSCustomOverworld: LoadOverworldSprites_Interupt ($09C4C7)│
│  • Calculate screen size                                     │
│  • Get area ID from $040A                                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  JSL Oracle_ZSO_CheckIfNight (Bridge Function)              │
│  • Checks special peacetime areas (Tail Palace, Zora)       │
│  • Reads hour from $7EE000                                   │
│  • Returns GameState or GameState+1                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼ (Returns phase index)
┌─────────────────────────────────────────────────────────────┐
│  Calculate Sprite Pointer Offset                            │
│  • Base = AreaID * 2                                         │
│  • Offset = PhaseOffsetTable[Phase]                         │
│  • FinalIndex = Base + Offset                               │
│                                                              │
│  PhaseOffsetTable:                                           │
│    .phaseOffset                                              │
│    dw $0000, $0000  ; State 0: Day, Night                   │
│    dw $0140, $0280  ; State 1: Day, Night                   │
│    dw $04C0, $0600  ; State 2: Day, Night                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Load Sprite Data from Pool_Overworld_SpritePointers       │
│  • Reads pointer at FinalIndex                               │
│  • Loads sprite list for area+time                           │
│  • Initializes sprites                                       │
└─────────────────────────────────────────────────────────────┘
```

### 6.3. Implementation Details

**Bridge Function (time_system.asm):**
```asm
; This function lives OUTSIDE Oracle namespace
; So ZScream can call it via JSL
ZSO_CheckIfNight:
{
    PHB : PHK : PLB
    
    ; Check special peacetime areas first
    LDA $8A              ; Current area
    CMP.b #$2E : BEQ .tail_palace
    CMP.b #$2F : BEQ .tail_palace
    CMP.b #$1E : BEQ .zora_sanctuary
    JMP .continue_check
    
.tail_palace
    ; If crystal collected, load peacetime sprites
    LDA.l $7EF37A       ; Crystals SRAM
    AND #$10
    BNE .load_peacetime
    JMP .continue_check
    
.zora_sanctuary
    LDA.l $7EF37A
    AND #$20
    BNE .load_peacetime
    JMP .continue_check
    
.load_peacetime
    ; Return normal game state (day sprites)
    LDA.l $7EF3C5
    PLB
    RTL
    
.continue_check
    REP #$30
    
    ; Don't change during intro
    LDA.l $7EF3C5 : AND.w #$00FF
    CMP.w #$0002 : BCC .day_time
    
    ; Check time
    LDA.l $7EE000 : AND.w #$00FF
    CMP.w #$0012 : BCS .night_time  ; >= 18:00
    CMP.w #$0006 : BCC .night_time  ; < 06:00
    
.day_time
    LDA.l $7EF3C5
    BRA .done
    
.night_time
    LDA.l $7EF3C5
    INC A                ; GameState + 1 for night
    
.done
    SEP #$30
    PLB
    RTL
}

; Export to Oracle namespace
namespace Oracle
{
    Oracle_ZSO_CheckIfNight = ZSO_CheckIfNight
}
```

**ZSCustomOverworld Hook:**
```asm
; In ZSCustomOverworld.asm at $09C4C7
org $09C4C7
LoadOverworldSprites_Interupt:
{
    LDX.w $040A  ; Area ID
    LDA.l Pool_BufferAndBuildMap16Stripes_overworldScreenSize, X : TAY
    
    LDA.w .xSize, Y : STA.w $0FB9 : STZ.w $0FB8
    LDA.w .ySize, Y : STA.w $0FBB : STZ.w $0FBA
    
    ; Get phase (day/night + game state)
    JSL Oracle_ZSO_CheckIfNight  ; Returns phase in A
    ASL : TAY                     ; * 2 for word table
    
    REP #$30
    
    ; Calculate final pointer index
    TXA : ASL                     ; AreaID * 2
    CLC : ADC.w .phaseOffset, Y   ; Add phase offset
    TAX
    
    ; Get sprite pointer
    LDA.l Pool_Overworld_SpritePointers_state_0_New, X
    STA.b $00
    
    SEP #$20
    BRA .skip
    
    .xSize
    db $02, $04, $04, $02
    
    .ySize
    db $02, $04, $02, $04
    
    .phaseOffset
    dw $0000, $0000  ; State 0: Day, Night
    dw $0140, $0280  ; State 1: Day, Night (160 areas * 2 bytes)
    dw $04C0, $0600  ; State 2: Day, Night
    
    NOP : NOP : NOP
    
    org $09C50D
    .skip
}
```

### 6.4. Status & Remaining Issues

✅ **Status:** Sprite Loading Logic Complete

⚠️ **Known Issue:** Sprite graphics (tilesets) not updating

**What Works:**
- Correct sprite IDs load for day/night
- Game state + time properly combined
- Peacetime areas handled correctly
- Transition logic integrated

**What Doesn't Work:**
- Sprite graphics remain from previous set
- Results in "gargoyle" effect (wrong tiles for sprite)
- Need to trigger sprite GFX reload on time change

**Proposed Solution:**
Add graphics reload hook in time transition:
```asm
; In time_system.asm when hour changes
TimeTransition_NightToDayOrDayToNight:
{
    ; ... existing time change logic ...
    
    ; Reload sprite graphics if in overworld
    LDA.b $1B        ; INDOORS flag
    BNE .skip
    
    JSL Overworld_ReloadSpriteGFX  ; Force GFX update
    
.skip
    RTL
}
```

See `Docs/World/Overworld/ZSCustomOverworldAdvanced.md` Section 4 for complete day/night sprite loading documentation.

---

## 7. Mask System × All Systems

**System:** `Masks/all_masks.asm`

**Interaction Type:** 🔄 Complex Multi-System Coordination

### 7.1. Overview

The Mask System transforms Link, affecting nearly every game system:
- **Physics:** Custom movement, swimming, climbing
- **Graphics:** Different Link sprite sets (banks $33-$3B)
- **Abilities:** Unique powers per mask
- **Menu:** Item restrictions, HUD changes
- **Sprites:** Different collision/interaction

### 7.2. System Impact Map

```
                    ┌─────────────────┐
                    │  Mask System    │
                    │  (Bank $3A)     │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌────────────────┐   ┌──────────────┐
│ Player Engine │   │ Sprite System  │   │ Menu System  │
│ (Bank $07)    │   │ (Bank $06)     │   │ (Bank $2D)   │
│               │   │                │   │              │
│ • Movement    │   │ • Collision    │   │ • Inventory  │
│ • Physics     │   │ • Damage       │   │ • HUD        │
│ • Actions     │   │ • Interactions │   │ • Abilities  │
└───────┬───────┘   └────────┬───────┘   └──────┬───────┘
        │                    │                   │
        │                    │                   │
        │                    ▼                   │
        │           ┌─────────────────┐         │
        │           │ Graphics System │         │
        └──────────►│ (Banks $33-$3B) │◄────────┘
                    │                 │
                    │ • Deku ($35)    │
                    │ • Zora ($36)    │
                    │ • Bunny ($37)   │
                    │ • Wolf ($38)    │
                    │ • Minish ($39)  │
                    │ • Moosh ($33)   │
                    │ • GBC ($3B)     │
                    └─────────────────┘
```

### 7.3. Coordination Points

**A. Transform Sequence**

```
┌─────────────────────────────────────────────────────────────┐
│              Player Equips Mask from Menu                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Link_TransformMask (Masks/mask_routines.asm)               │
│  • Read mask ID from equipment slot                          │
│  • Validate can transform (not indoors, etc.)                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Save Original State                                         │
│  • Store vanilla Link properties to WRAM backup              │
│  • $7E0730+: Original movement speed, abilities              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Load Mask Graphics                                          │
│  • DMA mask-specific Link graphics from banks $33-$3B        │
│  • Replace Link's OAM tileset                                │
│  • Update palette to CGRAM                                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Override Player State Machine                               │
│  • Hook Link_Main ($078000)                                  │
│  • Redirect to mask-specific handlers                        │
│  • Custom physics, movement, actions                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Update Collision & Sprites                                  │
│  • Set custom hitbox size                                    │
│  • Modify sprite interaction flags                           │
│  • Update damage tables                                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Set Menu/HUD State                                          │
│  • Update ability icons                                      │
│  • Restrict/enable items                                     │
│  • Show transformation indicator                             │
└─────────────────────────────────────────────────────────────┘
```

**B. De-Transform Sequence**

When mask is removed or expires:
1. Restore original Link properties from backup
2. Reload vanilla Link graphics
3. Restore normal hitbox/collision
4. Re-enable all items
5. Clear transformation flags

### 7.4. Mask-Specific Interactions

**Deku Mask (Masks/deku_mask.asm):**
- **Movement:** Hop-based instead of walk
- **Water:** Cannot swim (sinks immediately)
- **Combat:** Deku Bubble projectile
- **Special:** Can use Deku Flowers
- **Graphics:** Bank $35

**Zora Mask (Masks/zora_mask.asm):**
- **Movement:** Fast underwater swimming
- **Combat:** Boomerang fins
- **Breathing:** Infinite underwater
- **Special:** Electric barrier
- **Graphics:** Bank $36

**Bunny Hood (Masks/bunny_hood.asm):**
- **Movement:** 2x speed boost
- **Jump:** Increased jump height
- **Special:** Dash attack
- **Graphics:** Bank $37

**Wolf Mask (Masks/wolf_mask.asm):**
- **Movement:** Quadruped locomotion
- **Combat:** Bite attack
- **Special:** Enhanced sense (see hidden)
- **Graphics:** Bank $38

**Minish Mask (Masks/minish_form.asm):**
- **Size:** Reduced hitbox (access small spaces)
- **Combat:** Weak attacks
- **Special:** Talk to Minish NPCs
- **Graphics:** Bank $39

### 7.5. Memory Coordination

**Mask State Variables (WRAM):**
```
!CurrentMask = $02B2 ; 0 Human, 1 Deku, 2 Zora, 3 Wolf, 4 Bunny Hood, 5 Minish, 6 GBC, 7 Moosh (Masks/all_masks.asm:3-13)
!LinkGraphics = $BC  ; Masks/all_masks.asm:16
!ZoraDiving = $0AAB  ; Masks/all_masks.asm:19
DekuFloating = $70   ; Masks/all_masks.asm:22
DekuHover = $71      ; Masks/all_masks.asm:26
```

**Equipment Slots (SRAM):**
```
$7EF347: ZoraMask       ; Owned: 0=No, 1=Yes
$7EF348: BunnyHood
$7EF349: DekuMask
$7EF352: StoneMask
$7EF358: WolfMask
```

No SRAM ownership byte exists for Minish/GBC/Moosh forms (grep, 2026-10-12).

### 7.6. Known Issues & Solutions

**Issue 1: Menu Access While Transformed**
- Problem: Some masks prevent menu access
- Solution: Hook menu open, allow "safe" transformations (Bunny) but block risky ones (Minish)

**Issue 2: Death While Transformed**
- Problem: Death sequence uses vanilla Link graphics
- Solution: Force de-transform before death animation

**Issue 3: Dungeon Restrictions**
- Problem: Some dungeons shouldn't allow transformations
- Solution: Check dungeon ID before transform, deny with message

---

## 8. Overworld Transition Sequence

**Complete Frame-by-Frame Breakdown**

This section documents the exact order of operations during an overworld area transition, showing how all systems coordinate.

### 8.1. Transition Trigger (Frame 0)

```
Player Reaches Screen Edge
    ↓
Link_Main (Bank $07) detects boundary
    ↓
Sets $11 (submodule) = $01 (transition start)
    ↓
Module remains $09 (Overworld)
```

### 8.2. Transition Sequence (Frames 1-30)

**Frame 1-2: State Setup**
```
Module09_Overworld (Bank $00)
    ↓
Checks $11 submodule
    ↓
Submodule $01: Begin Transition
    ↓
┌─────────────────────────────────────────┐
│ Store current state:                    │
│ • Camera position → $7EC180             │
│ • Link coordinates → $7EC184            │
│ • BG scroll → $7EC188                   │
└─────────────────────────────────────────┘
```

**Frame 3-8: Scroll Animation**
```
Every frame:
    ↓
Increment camera offset
    ↓
Update BG1/BG2 scroll registers
    ↓
Move Link sprite position
    ↓
Check if scroll complete (8 tiles)
```

**Frame 9: New Area Load Start**
```
Scroll complete
    ↓
Calculate new area ID
    ↓
Store in $8A (new area)
    ↓
┌─────────────────────────────────────────┐
│ ZSCustomOverworld Hook Triggers         │
│ OverworldHandleTransitions ($02A9C4)    │
└─────────────────────────────────────────┘
    ↓
Lost Woods check (if area $29)
    ↓
Normal transition continues
```

**Frame 10-15: Graphics & Data Load**
```
ZSCustomOverworld_LoadArea:
    ↓
┌─────────────────────────────────────────┐
│ Load in sequence:                       │
│ 1. Map16 data from pool                 │
│ 2. Tile32 layout                        │
│ 3. Collision data                       │
│ 4. Base palette                         │
│ 5. Overlay data                         │
└─────────────────────────────────────────┘
```

**Frame 16-20: Palette & Overlay Processing**
```
Palette loading:
    ↓
Each color write → $2122
    ↓
Time System hook intercepts
    ↓
Applies day/night modulation
    ↓
Final color written to CGRAM
    │
    ├─ Check Storm Flag ($7EF39D)
    └─ If active, override overlay with rain
```

**Frame 21-25: Sprite System**
```
LoadOverworldSprites_Interupt:
    ↓
JSL Oracle_ZSO_CheckIfNight
    ↓
Calculate sprite pointer offset
    ↓
Load sprite data for area+time
    ↓
Initialize sprite slots (16 total)
    ↓
Set initial sprite states
```

**Frame 26-28: Mask System Check**
```
If Link transformed:
    ↓
Verify mask valid in new area
    ↓
Maintain transformation state
    ↓
Update custom physics for terrain
```

**Frame 29-30: Finalization**
```
Set $11 = $00 (submodule complete)
    ↓
Enable player control
    ↓
Resume normal gameplay
```

---

## 9. Frame-by-Frame Coordination

**Every Frame (60 FPS) Execution Order**

### 9.1. NMI (Interrupt_NMI - $0080C9)

```
Hardware Interrupt (VBlank starts)
    ↓
┌─────────────────────────────────────────┐
│ NMI_ReadJoypads                         │
│ • Read controller input                 │
│ • Store in $F0-$F7                      │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ NMI_DoUpdates                           │
│ • DMA stripe data to VRAM               │
│ • Update OAM (sprite positions)         │
│ • Upload palettes if changed            │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ NMI_PrepareSprites                      │
│ • Calculate sprite priority             │
│ • Build OAM buffer                      │
└─────────────────────────────────────────┘
    ↓
RTI (Return from interrupt)
```

### 9.2. Main Loop (MainGameLoop - $008034)

```
┌─────────────────────────────────────────┐
│ Module_MainRouting ($0080B5)            │
│ • Read $10 (module)                     │
│ • Jump to current module handler        │
└─────────────────────────────────────────┘
    ↓
If Module $09 (Overworld):
    ↓
┌─────────────────────────────────────────┐
│ Module09_Overworld                      │
│ • Read $11 (submodule)                  │
│ • Execute current overworld submodule   │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Time System: RunClock                   │
│ • Increment frame counter               │
│ • Update hour if needed                 │
│ • Handle day/night transitions          │
│ • Call HandleStormsOverlay              │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Link_Main (Bank $07)                    │
│ • Read $5D (Link state)                 │
│ • Execute state handler                 │
│ • Update position, velocity             │
│ • Check mask transformations            │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Sprite_Main (Bank $06)                  │
│ • Loop through 16 sprite slots          │
│ • Execute each active sprite's AI       │
│ • Check collisions with Link            │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Ancilla_Main (Bank $08)                 │
│ • Update projectiles                    │
│ • Handle particle effects               │
└─────────────────────────────────────────┘
    ↓
Loop back to Module_MainRouting
```

### 9.3. System Priority Order

When multiple systems need to modify the same resource:

**Priority 1 (Highest): Player Safety**
- Mask de-transform on death
- Collision damage
- State machine locks

**Priority 2: Weather/Environment**
- Storm overlay override
- Time-based palette
- Dynamic weather effects

**Priority 3: Normal Gameplay**
- Standard sprite behavior
- Menu access
- Item usage

**Priority 4 (Lowest): Visual Polish**
- Animated tiles
- Particle effects
- HUD animations

---

## 10. Troubleshooting System Interactions

**Common Issues:**

### 10.1. "System X overwrites System Y's changes"

**Diagnosis:**
1. Check execution order in main loop
2. Verify which system runs last
3. Look for missing coordination flags

**Solution:**
- Add SRAM/WRAM flag for coordination
- Use priority system (see 9.3)
- Implement callback/hook pattern

### 10.2. "Changes don't persist across transitions"

**Diagnosis:**
1. Check if state is in WRAM (volatile) or SRAM (persistent)
2. Verify state is restored during area load
3. Look for reset code that clears flags

**Solution:**
- Move important state to SRAM
- Add save/restore routines
- Check ZS transition hooks

### 10.3. "Namespace can't call function in other namespace"

**Diagnosis:**
1. Check if function is exported with Oracle_ prefix
2. Verify build order in Oracle_main.asm
3. Look for missing export block

**Solution:**
- Add export: `namespace Oracle { Oracle_Function = Function }`
- Use bridge function pattern (see Section 6.2)
- Verify calling syntax with prefix

See AFS archive/repo-slim-2026-10-06/repo/Docs/Debugging/Guides/Troubleshooting.md for comprehensive debugging guide.

---

## 11. References

**Core Documentation:**
- `Docs/World/Overworld/ZSCustomOverworldAdvanced.md` - ZScream internals
- AFS archive/repo-slim-2026-10-06/repo/Docs/Debugging/Guides/Troubleshooting.md - Problem-solving guide
- AFS archive/repo-slim-2026-10-06/repo/Docs/Debugging/Guides/DevelopmentGuidelines.md - Best practices
- `Docs/Technical/MemoryMap.md` - Memory layout

**System-Specific:**
- `Overworld/ZSCustomOverworld.asm` - Custom overworld engine
- `Overworld/time_system.asm` - Day/night cycle
- `Masks/mask_routines.asm` - Transformation system
- `Items/ocarina.asm` - Song effects

**Vanilla Reference:**
- `ALTTP/bank_00.asm` - Main loop and modules
- `ALTTP/bank_02.asm` - Overworld transitions
- `ALTTP/bank_06.asm` - Sprite engine
- `ALTTP/bank_07.asm` - Player engine

---

**Document Version:** 2.0  
**Last Updated:** October 3, 2025  
**Maintained By:** Oracle of Secrets Development Team
