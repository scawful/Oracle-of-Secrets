# System Refactoring Plan: Time, Weather, and Overworld

## 1. Palette System Conflict Analysis & Fix

### The Conflict
The `RunClock` routine in `Overworld/time_system.asm` triggers a full palette reload from ROM (`JSL RomToPaletteBuffer`) every in-game hour to apply the day/night tint. This is redundant and expensive because `ZSCustomOverworld.asm` has already loaded the correct area-specific palettes into WRAM. This causes a conflict where the time system overwrites any custom palette operations performed by the ZS overworld engine.

### The Fix (Lightweight Tinting)
Instead of reloading from ROM, the time system should modify the *existing* palette buffer in WRAM.

### Proposed Architecture
1.  **Remove** calls to `RomToPaletteBuffer` in `RunClock`.
2.  **Create** a new routine `ApplyTimeTintToBuffer` that:
    *   Reads the current palette from the WRAM buffer (`$7EC500` range).
    *   Applies the subtraction logic (RGB modification) directly to these values.
    *   Writes them back to the buffer.
    *   Triggers `PaletteBufferToEffective` to transfer WRAM -> CGRAM.
3.  **Hook Location:** Call this new routine in `RunClock` instead of the heavy reload sequence.

## 2. Ocarina Rain State Consistency

### The Bug
The `ActivateSubScreen` routine in `Overworld/ZSCustomOverworld.asm` determines if the rain overlay should be active when the menu is opened/closed. It currently checks for:
1.  Misery Mire Event
2.  Beginning Game Phase
3.  Master Sword Forest Area

It **fails** to check the dynamic rain flag `$7EE00E` which is set by the Ocarina's Song of Storms. Consequently, opening the menu clears the custom rain effect.

### The Fix
Update `ActivateSubScreen` to check `$7EE00E` first.

```asm
; In Overworld/ZSCustomOverworld.asm :: ActivateSubScreen

ActivateSubScreen:
{
    PHB : PHK : PLB
    STZ.b $1D
    PHX
    REP #$20

    ; [NEW] Check Ocarina Rain Flag
    LDA.l $7EE00E : BNE .forceRainOverlay

    ; ... existing checks for Forest, Mire, etc ...

    .forceRainOverlay
    SEP #$20
    LDA.b #$01 : STA.b $1D ; Enable Subscreen
    LDA.b #$9F : STA.b $8C ; Set overlay ID to Rain
    ; ... continue ...
}
```

## 3. Nighttime Sprite Hook Placement

### The Goal
Enable different sprite sets (peacetime vs. enemies) based on the time of day. The hooks in `time_system.asm` were commented out because `ZSCustomOverworld.asm` completely replaces the routine that contained the original hooks.

### The Fix
Inject the check into the custom loading routine in `Overworld/ZSCustomOverworld.asm`.

### Target Location
*   **File:** `Overworld/ZSCustomOverworld.asm`
*   **Routine:** `PreOverworld_LoadProperties_Interupt`

### Implementation
```asm
    ; ... existing code ...
    
    ; 0x0B is the SW overworld $10 module.
    LDX.b #$0B
    
    .notSWArea
    
    ; Cache the overworld mode.
    STX.w $010C

    ; [NEW] Inject Nighttime Check Here
    ; This modifies GameState/Spriteset before reload
    JSL Oracle_CheckIfNight16Bit 

    JSL.l Sprite_OverworldReloadAll
    
    ; ... existing code ...
```

## 4. Overlay Animation Refactoring (Data-Driven)

### The Problem
Current animations in `Overworld/overlays.asm` are hardcoded assembly routines (`Frame0`, `Frame1`...) containing raw `Overworld_DrawMap16_Persist` calls. This is rigid and consumes excessive ROM space.

### The Fix
Implement a script interpreter that reads from a data table.

### Proposed Data Structure

```asm
; Animation Header
ZoraEntrance_Script:
    dw .Frame0, .Frame1, .Frame2, $FFFF (End)

.Frame0:
    db $1E        ; Duration (30 frames)
    db $01        ; Flags (01 = Shake Screen)
    ; Tile Updates: [Count] [Address] [TileID]
    db $04        ; Count
    dw $0490, $0965
    dw $0492, $0175
    dw $049C, $0965
    dw $049E, $0175
    db $00        ; End of Frame Data
```

### Interpreter Logic (`PlayOverlayAnimation`)
1.  Check `AnimationTimer`. If > 0, decrement and return.
2.  If 0, load `FramePointer` index.
3.  Read `Duration`, set `AnimationTimer`.
4.  Read `Flags`. If bit 0 set, call `ShakeScreen`.
5.  Loop through `Tile Updates`, calling `Overworld_DrawMap16_Persist` for each.
6.  Increment `FramePointer`.

## Summary of Required Actions

1.  **Modify** `Overworld/ZSCustomOverworld.asm`:
    *   Patch `ActivateSubScreen` to include `$7EE00E` check.
    *   Patch `PreOverworld_LoadProperties_Interupt` to call `Oracle_CheckIfNight16Bit`.
2.  **Modify** `Overworld/time_system.asm`:
    *   Rewrite `RunClock` to use the new `ApplyTimeTintToBuffer` method instead of `RomToPaletteBuffer`.
3.  **Refactor** `Overworld/overlays.asm`:
    *   Implement the interpreter routine.
    *   Convert `ZoraTemple` and `Castle` animations to the new data format.
