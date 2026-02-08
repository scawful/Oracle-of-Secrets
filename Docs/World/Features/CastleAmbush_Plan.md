# Castle Ambush & Guard Capture System - Implementation Plan

**Status:** 🚧 Planning Phase  
**Created:** October 3, 2025  
**Target:** Future Update  
**Related Files:** `Core/capture.asm`, `Sprites/Enemies/custom_guard.asm`, `Sprites/overlord_ref.asm`

---

## Overview

The **Castle Ambush System** will create a dynamic encounter where Link is detected by guards in the castle, captured, and warped to a dungeon. This combines:

1. **Probe Detection System** - Guards detect Link entering restricted areas
2. **Guard Capture Mechanics** - Guards surround and capture Link
3. **Warp System** - Link is transported to a dungeon entrance
4. **Overlord Management** - Multi-screen guard coordination

---

## Current State Analysis

### Existing Components

#### ✅ Core/capture.asm
**Status:** Implemented but untested

```asm
Oracle_CaptureAndWarp:
{
  STA.w $010E        ; Set the target entrance ID
  LDA.b #$05         ; Game Mode 05: (hole/whirlpool transition)
  STA.b $10          ; Set the game mode
  STZ.b $2F          ; Clear Link's action state
  STZ.b $5D          ; Clear Link's state
  LDA.b #$02 : STA.b $71  ; Set transition flag
  RTL
}
```

**Purpose:** Warps Link to a specific dungeon entrance (like WallMaster)

**Issues to Address:**
- [ ] Test entrance ID values (need to determine correct dungeon entrance)
- [ ] Verify game mode $05 works for this use case
- [ ] Add screen fade/transition effect
- [ ] Play capture sound effect
- [ ] Store pre-capture location for potential escape sequence

#### 🚧 Sprites/Enemies/custom_guard.asm
**Status:** Prototype with duplicate code

**Contains:**
1. `Oracle_CaptureAndWarp` (DUPLICATE - already in Core/capture.asm)
2. `Hooked_Guard_Main` - Modified guard behavior

**Issues:**
- [ ] Remove duplicate `Oracle_CaptureAndWarp` function
- [ ] Complete `Hooked_Guard_Main` implementation
- [ ] Test guard capture trigger conditions
- [ ] Integrate with vanilla guard sprites (ID $41, $42, $43)

#### 📚 Sprites/overlord_ref.asm
**Status:** Reference material (now in experimental/)

**Purpose:** Documents overlord path patterns for crumbling tiles

**Relevance:** Can be adapted for guard patrol paths

---

## System Architecture

### Phase 1: Detection (Probe System)

```
┌─────────────────────────────────────────────────┐
│ Link enters castle restricted area              │
│ SRAM flag: $7EF??? = Castle infiltration active │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ Guard spawns probe sprites every 32 frames      │
│ Probe checks:                                   │
│  - Link within 16px radius                      │
│  - Same floor layer ($0F20)                     │
│  - Not invisible/bunny                          │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
          ┌────────┴────────┐
          │  Probe Hit?     │
          └────────┬────────┘
                   │
      ┌────────────┼────────────┐
      │ YES                     │ NO
      ▼                         ▼
┌──────────────┐        ┌──────────────┐
│ Trigger      │        │ Continue     │
│ Alert State  │        │ Patrol       │
└──────┬───────┘        └──────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Play alert sound ($1D)               │
│ Set SprTimerD = $B0 (176 frames)    │
│ Spawn reinforcement guards           │
└──────────────────────────────────────┘
```

### Phase 2: Pursuit & Capture

```
┌─────────────────────────────────────────────────┐
│ Alert state active (SprTimerD > 0)              │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ Guards converge on Link's position              │
│  - Use Guard_ChaseLinkOnOneAxis                 │
│  - Spawn additional guards from off-screen      │
│  - Maximum 4 guards active                      │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ Check capture conditions (every frame)          │
│  - Link is surrounded (guards on 3+ sides)      │
│  - Link is not moving (speed = 0)               │
│  - Link has taken damage from guard             │
└──────────────────┬──────────────────────────────┘
                   │
          ┌────────┴────────┐
          │  Captured?      │
          └────────┬────────┘
                   │
      ┌────────────┼────────────┐
      │ YES                     │ NO
      ▼                         ▼
┌──────────────┐        ┌──────────────┐
│ Initiate     │        │ Continue     │
│ Capture      │        │ Chase        │
└──────┬───────┘        └──────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Phase 3: Warp Sequence               │
└──────────────────────────────────────┘
```

### Phase 3: Warp Sequence

```
┌─────────────────────────────────────────────────┐
│ Freeze Link (disable input)                     │
│ Play capture animation                          │
│  - Link's sprite changes to "captured" pose     │
│  - Guards move to surround positions            │
│  - Screen shake effect (3 frames)               │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ Fade out screen ($0012 = $01)                   │
│ Wait 32 frames                                  │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ Call Oracle_CaptureAndWarp                      │
│  - A register = Dungeon entrance ID             │
│  - Sets game mode to $05 (transition)           │
│  - Clears Link state                            │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ Link spawns in dungeon cell                     │
│  - Set SRAM flag: $7EF??? = Captured            │
│  - Play jingle ($06)                            │
│  - Trigger escape sequence                      │
└──────────────────────────────────────────────────┘
```

---

## File Consolidation Plan

### Step 1: Organize Core Utilities

**Keep in `Core/capture.asm`:**
```asm
; Core warp functionality
Oracle_CaptureAndWarp:
{
  ; (existing implementation)
}

; NEW: Enhanced version with effects
Oracle_CaptureAndWarp_Enhanced:
{
  PHP
  
  ; Store entrance ID
  STA.w $010E
  
  ; Store capture flag in SRAM
  LDA.b #$01
  STA.l $7EF3D8  ; Custom flag: Has been captured
  
  ; Play capture sound
  LDA.b #$1D  ; Alert/Capture sound
  STA.w $012E
  
  ; Fade out screen
  LDA.b #$01
  STA.w $0012  ; Request fade
  
  ; Set up timer for transition
  LDA.b #$40  ; Wait 64 frames
  STA.b $00
  
  .wait_fade
    LDA.b $00 : BNE .wait_fade
  
  ; Execute warp
  LDA.w $010E  ; Get entrance ID back
  STA.w $010E
  
  LDA.b #$05   ; Game Mode 05
  STA.b $10
  STZ.b $2F
  STZ.b $5D
  
  LDA.b #$02
  STA.b $71
  
  PLP
  RTL
}
```

### Step 2: Create Unified Guard Sprite

**New file: `Sprites/Enemies/castle_guard.asm`**

This will replace `Sprites/Enemies/custom_guard.asm` with a complete implementation:

```asm
; =========================================================
; Castle Guard - Ambush & Capture Variant
; =========================================================

!SPRID = Sprite_CastleGuard  ; Use new sprite ID or override vanilla
!NbrTiles = 02
!Health = 08
!Damage = 04
; ... other properties ...

%Set_Sprite_Properties(Sprite_CastleGuard_Prep, Sprite_CastleGuard_Long)

; States
!STATE_PATROL = 0
!STATE_ALERT = 1
!STATE_CHASE = 2
!STATE_CAPTURE = 3

Sprite_CastleGuard_Long:
{
  PHB : PHK : PLB
  JSR Sprite_CastleGuard_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .inactive
    JSR Sprite_CastleGuard_Main
  .inactive
  PLB
  RTL
}

Sprite_CastleGuard_Prep:
{
  PHB : PHK : PLB
  
  ; Check if castle ambush is active
  LDA.l $7EF3D7 : BEQ .no_ambush  ; Custom flag: Castle ambush active
    ; Enable enhanced AI
    LDA.b #$01 : STA.w $0E80, X  ; Custom flag for this guard
  .no_ambush
  
  ; Standard health based on sword level
  LDA.l $7EF359 : TAY
  LDA.w .health, Y : STA.w SprHealth, X
  
  ; Enable parrying
  LDA.b #$80 : STA.w SprDefl, X
  
  PLB
  RTL
  
  .health
    db $04, $06, $08, $0A
}

Sprite_CastleGuard_Main:
{
  ; State machine
  LDA.w SprAction, X
  JSL JumpTableLocal
  
  dw CastleGuard_Patrol
  dw CastleGuard_Alert
  dw CastleGuard_Chase
  dw CastleGuard_Capture
}

CastleGuard_Patrol:
{
  ; Check if castle ambush should activate
  LDA.l $7EF3D7 : BEQ .normal_patrol
  
  ; Check distance to Link
  JSL GetDistance8bit_Long : CMP.b #$80 : BCS .no_probe
  
  ; Spawn probe for detection
  LDA.w SprTimerA, X : BNE .no_probe
    LDA.b #$20 : STA.w SprTimerA, X  ; Spawn every 32 frames
    JSL Sprite_SpawnProbeAlways_long
  .no_probe
  
  ; Check if probe triggered alert
  LDA.w SprTimerD, X : BEQ .normal_patrol
    ; Probe detected Link!
    LDA.b #!STATE_ALERT : STA.w SprAction, X
    
    ; Play alert sound
    LDA.b #$1D : STA.w $012E
    
    ; Spawn reinforcements
    JSR CastleGuard_SpawnReinforcements
    
    RTS
  
  .normal_patrol
  ; Standard patrol behavior
  JSR Guard_StandardPatrol
  RTS
}

CastleGuard_Alert:
{
  ; Transition to chase after alert plays
  LDA.w SprTimerD, X : CMP.b #$A0 : BCS .stay_alert
    LDA.b #!STATE_CHASE : STA.w SprAction, X
  .stay_alert
  
  ; Face Link
  JSL Sprite_DirectionToFacePlayer : TYA : STA.w SprMiscC, X
  
  ; Draw with alert animation
  LDA.b #$08 : STA.w SprGfx, X
  RTS
}

CastleGuard_Chase:
{
  ; Move toward Link
  LDA.b #$0C : JSL Sprite_ApplySpeedTowardsPlayer
  JSL Guard_ChaseLinkOnOneAxis
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  
  ; Check if Link is surrounded
  JSR CastleGuard_CheckSurrounded : BCC .not_surrounded
    ; Capture Link!
    LDA.b #!STATE_CAPTURE : STA.w SprAction, X
    LDA.b #$60 : STA.w SprTimerC, X  ; Capture animation duration
    
    ; Freeze Link
    LDA.b #$17 : STA.b $5D  ; Link state: captured
    STZ.b $67  ; Stop Link's movement
    RTS
  
  .not_surrounded
  ; Continue chase
  JSL Guard_ParrySwordAttacks
  JSL Sprite_CheckDamageFromPlayer
  RTS
}

CastleGuard_Capture:
{
  ; Animate capture sequence
  LDA.w SprTimerC, X : BNE .animating
    ; Capture complete - warp Link
    LDA.b #$42  ; Entrance ID for dungeon cell
    JSL Oracle_CaptureAndWarp_Enhanced
    RTS
  
  .animating
  ; Guards surround Link
  ; ... capture animation logic ...
  RTS
}

CastleGuard_CheckSurrounded:
{
  ; Count guards within range in each direction
  ; Return carry set if Link is surrounded
  ; (3+ guards within 32px, covering different quadrants)
  
  ; ... implementation ...
  
  CLC  ; Not surrounded
  RTS
}

CastleGuard_SpawnReinforcements:
{
  ; Spawn additional castle guards off-screen
  LDY.b #$00
  LDX.b #$0F
  
  .spawn_loop
  LDA.w $0DD0, X : BEQ .found_slot
    DEX : BPL .spawn_loop
    RTS  ; No free slots
  
  .found_slot
  ; Spawn guard sprite
  LDA.b #Sprite_CastleGuard : STA.w $0E20, X
  LDA.b #$09 : STA.w $0DD0, X  ; Active state
  
  ; Position off-screen based on Link's position
  ; ... positioning logic ...
  
  ; Set to chase state immediately
  LDA.b #!STATE_CHASE : STA.w SprAction, X
  
  INY
  CPY.b #$03 : BCC .spawn_loop  ; Spawn up to 3 reinforcements
  
  RTS
}

; ... drawing routine ...
```

### Step 3: Integrate with Existing Systems

**Modify `Sprites/all_sprites.asm`:**
```asm
org $318000
%log_start("castle_guard", !LOG_SPRITES)
incsrc "Sprites/Enemies/castle_guard.asm"
%log_end("castle_guard", !LOG_SPRITES)
```

**Add SRAM Flags to `Core/sram.asm`:**
```asm
; Castle Ambush System
$7EF3D7 = CastleAmbushActive    ; 01 = ambush scenario active
$7EF3D8 = HasBeenCaptured       ; 01 = player has been captured before
$7EF3D9 = CaptureCount          ; Number of times captured
```

**Add Constants to `Core/symbols.asm`:**
```asm
; Castle Ambush
CastleAmbushActive = $7EF3D7
HasBeenCaptured = $7EF3D8
CaptureCount = $7EF3D9
```

---

## Testing Plan

### Test Case 1: Detection
- [ ] Enter castle area with ambush flag set
- [ ] Walk near guard
- [ ] Verify probe spawns every 32 frames
- [ ] Walk into probe's path
- [ ] Verify alert sound plays
- [ ] Verify guard enters alert state

### Test Case 2: Chase
- [ ] Continue from Test Case 1
- [ ] Verify guard chases Link
- [ ] Verify reinforcements spawn
- [ ] Verify multiple guards coordinate
- [ ] Verify guards use parrying

### Test Case 3: Capture
- [ ] Let guards surround Link
- [ ] Verify capture check works
- [ ] Verify Link is frozen
- [ ] Verify capture animation plays
- [ ] Verify screen fades out

### Test Case 4: Warp
- [ ] Continue from Test Case 3
- [ ] Verify Link warps to dungeon
- [ ] Verify SRAM flag is set
- [ ] Verify Link spawns in correct room
- [ ] Verify capture count increments

### Test Case 5: Escape
- [ ] Escape from dungeon cell
- [ ] Return to castle
- [ ] Verify guards remember previous capture
- [ ] Verify harder difficulty on subsequent captures

---

## Implementation Phases

### Phase A: Core Functionality (Week 1)
- [ ] Clean up `Core/capture.asm`
- [ ] Add `Oracle_CaptureAndWarp_Enhanced`
- [ ] Test basic warp functionality
- [ ] Determine correct entrance ID for dungeon cell

### Phase B: Guard AI (Week 2)
- [ ] Create `Sprites/Enemies/castle_guard.asm`
- [ ] Implement probe detection
- [ ] Implement state machine
- [ ] Test patrol → alert → chase transitions

### Phase C: Capture Mechanics (Week 3)
- [ ] Implement surround check
- [ ] Implement capture animation
- [ ] Test capture trigger conditions
- [ ] Add sound effects

### Phase D: Integration (Week 4)
- [ ] Add SRAM flags
- [ ] Integrate with quest system
- [ ] Create dungeon escape sequence
- [ ] Test full cycle

### Phase E: Polish (Week 5)
- [ ] Add dialogue/cutscenes
- [ ] Add visual effects
- [ ] Balance difficulty
- [ ] Add achievements/tracking

---

## Entrance IDs Reference

Need to determine correct entrance for dungeon cell:

```asm
; Common dungeon entrances
$00 = Hyrule Castle (main entrance)
$04 = Hyrule Castle (throne room)
$0E = Hyrule Castle (dark passage)
$20 = Eastern Palace
$42 = Dark Palace
$?? = Custom dungeon cell (TBD)
```

**Action Required:** Find or create appropriate dungeon cell entrance

---

## Files to Create/Modify

### Create:
- [ ] `Sprites/Enemies/castle_guard.asm` - Main guard implementation
- [ ] `Docs/Features/CastleAmbush.md` - System documentation
- [ ] `Docs/Sprites/Enemies/CastleGuard.md` - Sprite documentation

### Modify:
- [ ] `Core/capture.asm` - Add enhanced version
- [ ] `Core/sram.asm` - Add SRAM flags
- [ ] `Core/symbols.asm` - Add constants
- [ ] `Sprites/all_sprites.asm` - Include castle_guard.asm

### Delete/Consolidate:
- [ ] `Sprites/Enemies/custom_guard.asm` - Consolidate into castle_guard.asm
- [ ] Remove duplicate `Oracle_CaptureAndWarp` from custom_guard.asm

---

## Questions to Resolve

1. **Entrance ID:** Which dungeon entrance should be used for the cell?
2. **Quest Integration:** When should castle ambush activate?
   - After certain quest milestone?
   - When Link enters specific castle area?
   - Triggered by dialogue/cutscene?
3. **Difficulty Scaling:** Should capture difficulty increase after first capture?
4. **Escape Sequence:** How should the escape play out?
   - Find key item?
   - Stealth section?
   - Fight way out?
5. **Sprite Slot:** New sprite ID or override vanilla guard ($41/$42/$43)?

---

## See Also

- `Docs/Sprites/ProbeSprites.md` - Probe detection system
- `Docs/Sprites/Enemies/Darknut.md` - Similar guard-type enemy
- `Docs/Guides/SpriteCreationGuide.md` - Sprite creation reference
- `Core/capture.asm` - Core warp functionality
- `Sprites/experimental/probe.asm` - Probe system reference
