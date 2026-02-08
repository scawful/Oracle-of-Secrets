# Oracle of Secrets - Troubleshooting Guide

**Version:** 1.0  
**Last Updated:** October 3, 2025  
**Audience:** ALTTP ROM hack developers, ZScream users, Oracle of Secrets contributors

---

## Table of Contents

1. [Introduction](#introduction)
2. [BRK Crashes](#brk-crashes)
3. [Stack Corruption](#stack-corruption)
4. [Processor Status Register Issues](#processor-status-register-issues)
5. [Cross-Namespace Calling](#cross-namespace-calling)
6. [Memory Conflicts](#memory-conflicts)
7. [Graphics and DMA Issues](#graphics-and-dma-issues)
8. [ZScream-Specific Issues](#zscream-specific-issues)
9. [Build Errors](#build-errors)
10. [Debugging Tools and Techniques](#debugging-tools-and-techniques)

---

## Introduction

This guide covers common issues encountered when developing ALTTP ROM hacks, particularly for the Oracle of Secrets project which uses:
- **65816 Assembly** (SNES processor)
- **Asar v1.9+** (assembler)
- **ZScream Custom Overworld System**
- **Mixed namespace architecture** (Oracle{} and ZScream)

Understanding the root causes of these issues will help you debug faster and write more stable code.

---

## BRK Crashes

### What is a BRK Crash?

A **BRK crash** occurs when the SNES executes a `BRK` instruction (`$00` opcode), triggering a software interrupt. In ALTTP, this is used as an error handler that:
1. Halts game execution
2. Displays a debug screen (if enabled)
3. Shows the crash location in ROM

### Common Causes

#### 1. **Jumping to Invalid Memory**
```asm
; BAD: $00 is typically uninitialized ROM space
JMP $0000

; GOOD: Jump to known valid code
JMP $008000
```

#### 2. **RTL/RTS Without Matching JSL/JSR**
```asm
SomeFunction:
{
    ; ... code ...
    RTL  ; ← Pops garbage from stack, jumps to random location
}

; Later, execution hits $00 (BRK) in uninitialized space
```

**Solution:** Always ensure subroutines are called before returning:
```asm
MainCode:
    JSL SomeFunction  ; ← Must call it!
    
SomeFunction:
    ; ... code ...
    RTL  ; ← Now safe
```

#### 3. **Incorrect Bank Byte**
```asm
; BAD: Bank $00 doesn't contain code at $C000
JML $00C000

; GOOD: Use correct bank
JML $02C000  ; Bank $02 contains overworld code
```

#### 4. **Data Corruption**
If RAM locations `$00-$01` (used for indirect addressing) get corrupted:
```asm
LDA.b ($00)  ; If $00/$01 = $0000, reads from $00:0000 (likely BRK)
```

### How to Find the Crash Location

#### In Mesen-S (Recommended):
1. **Enable "Break on BRK"**: Debugger → Settings → Break on BRK
2. When crash occurs, debugger shows:
   - **PC (Program Counter)**: Address where BRK was executed
   - **Stack contents**: Shows return addresses (where you came from)
3. **Read the stack** to trace back:
   ```
   Stack at $01F0: 82 9A 02  ← Came from $029A82
   Stack at $01ED: 45 C4 09  ← Came from $09C445
   ```

#### In BSNES-Plus:
1. Tools → Debugger
2. Set breakpoint on `$000000` (BRK opcode)
3. When triggered, examine:
   - S register (Stack Pointer)
   - Memory viewer at `$7E0100 + S` to see stack contents

#### Manual Method:
1. Note the **last known good action** (e.g., "crashed when entering area $2B")
2. Search codebase for hooks in that area:
   ```bash
   grep -r "0283EE\|02A9C4" Overworld/
   ```
3. Add temporary tracking code:
   ```asm
   LDA.b #$42 : STA.l $7F5000  ; Breadcrumb marker
   ```

### Prevention Strategies

1. **Initialize jump tables properly**:
   ```asm
   JumpTable:
       dw Function1  ; ← Must be valid addresses
       dw Function2
       dw Function3
   ```

2. **Validate indices before using jump tables**:
   ```asm
   LDA.b $00       ; Index
   CMP.b #$06      ; Max entries
   BCC .valid
   LDA.b #$00      ; Default to 0
   .valid
   ASL A           ; * 2 for word table
   TAX
   JMP (JumpTable, X)
   ```

3. **Use assertions** (Asar):
   ```asm
   assert pc() <= $09C50D  ; Ensure code doesn't overflow
   ```

---

## Stack Corruption

### Understanding the 65816 Stack

The stack on SNES:
- Lives at `$7E0100-$7E01FF` (256 bytes)
- **Grows downward** (S register decrements)
- Used for:
  - JSR/JSL (pushes return address)
  - PHA/PHX/PHY (pushes registers)
  - Interrupts (NMI pushes PC, Status)

### Common Issues

#### 1. **Unbalanced Push/Pop**
```asm
; BAD: 3 pushes, 2 pops
PHX
PHY
PHA
PLA
PLY
; ← Missing PLX! Stack is now corrupted (+1 byte)
RTL  ; Returns to wrong address
```

**Solution:** Always balance:
```asm
PHX
PHY
PHA
; ... code ...
PLA
PLY
PLX  ; ← Now balanced
RTL
```

#### 2. **JSR/JSL vs RTS/RTL Mismatch**
```asm
; BAD: JSL pushes 3 bytes, RTS pops 2 bytes
MainFunction:
    JSL SubFunction  ; Pushes $02 $C4 $09 (3 bytes)
    
SubFunction:
    ; ... code ...
    RTS  ; ← Pops only 2 bytes! Stack corrupted
```

**Solution:** Match call/return types:
```asm
MainFunction:
    JSL SubFunction  ; JSL (long call)
    
SubFunction:
    ; ... code ...
    RTL  ; ← RTL (long return) - matches!
```

**Memory Map:**
- **JSR**: Pushes 2 bytes (PC - 1), within same bank
- **JSL**: Pushes 3 bytes (PBR, PC - 1), cross-bank
- **RTS**: Pops 2 bytes, increments, continues
- **RTL**: Pops 3 bytes (bank + address), increments, continues

#### 3. **Stack Overflow**
If S register goes below `$0100`, stack wraps to page $00 (Direct Page), corrupting variables:
```asm
; Example: Deep recursion
RecursiveFunction:
    JSL RecursiveFunction  ; ← Each call uses 3 bytes
    RTL
; Eventually: S < $0100, corrupts $7E0000+ variables
```

**Solution:**
- Limit recursion depth
- Use iteration instead of recursion when possible
- Check S register if suspicious:
  ```asm
  TSC              ; Transfer Stack to C (16-bit accumulator)
  CMP.w #$01C0     ; Check if below safe threshold
  BCS .safe
  ; Handle stack overflow
  .safe
  ```

### Debugging Stack Issues

1. **Set watchpoint on stack pointer**:
   - Mesen-S: Debugger → Add Breakpoint → Type: Execute → Address: `S < $01C0`

2. **Track stack manually**:
   ```asm
   ; Add to suspicious functions:
   PHP : PLA : STA.l $7F5000  ; Save processor status
   TSC : STA.l $7F5002        ; Save stack pointer
   ```

3. **Check stack balance** in emulator:
   - Note S register before JSL: `S = $01F3`
   - After RTL, S should be: `S = $01F3` (same value)
   - If different, you have unbalanced stack operations

---

## Processor Status Register Issues

### Understanding the P Register

The **Processor Status Register (P)** controls 65816 behavior:

```
P = [N V M X D I Z C]
     │ │ │ │ │ │ │ └─ Carry flag
     │ │ │ │ │ │ └─── Zero flag
     │ │ │ │ │ └───── IRQ disable
     │ │ │ │ └─────── Decimal mode
     │ │ │ └───────── Index register size (X/Y): 0=16-bit, 1=8-bit
     │ │ └─────────── Memory/Accumulator size (A): 0=16-bit, 1=8-bit
     │ └───────────── Overflow flag
     └─────────────── Negative flag
```

**Most critical:** **M flag** (bit 5) and **X flag** (bit 4)

### Common Issues

#### 1. **Wrong Accumulator Size**
```asm
REP #$20        ; A = 16-bit (M flag = 0)
LDA.w #$1234    ; A = $1234

SEP #$20        ; A = 8-bit (M flag = 1)
LDA.w #$1234    ; ← ERROR: Assembler generates LDA #$34, $12 becomes opcode!
```

**Correct:**
```asm
SEP #$20        ; A = 8-bit
LDA.b #$12      ; Load 8-bit value only
```

#### 2. **Mismatched Index Sizes**
```asm
REP #$30        ; A=16-bit, X/Y=16-bit
LDX.w #$0120    ; X = $0120

SEP #$10        ; X/Y now 8-bit!
LDX.b #$20      ; X = $0020 (high byte cleared!)

LDA $7E0000, X  ; ← Reads from $7E0020, not $7E0120!
```

**Solution:** Be explicit about sizes:
```asm
REP #$30              ; Both A and X/Y are 16-bit
LDX.w #$0120
LDA.l $7E0000, X      ; Explicit long addressing
SEP #$30              ; Back to 8-bit for safety
```

#### 3. **Missing SEP/REP After JSL**
```asm
MainFunction:
    REP #$30        ; Set 16-bit mode
    JSL SubFunction ; Call other function
    ; What mode are we in now? We don't know!
    LDA.w $1234     ; ← May fail if SubFunction left us in 8-bit mode
```

**Best Practice:**
```asm
MainFunction:
    REP #$30        ; Set 16-bit mode
    JSL SubFunction
    SEP #$30        ; ← Always reset to known state!
    ; Now we know we're in 8-bit mode
```

Or use calling conventions:
```asm
SubFunction:
    ; Save processor status on entry
    PHP
    ; ... do work ...
    PLP             ; Restore processor status on exit
    RTL
```

#### 4. **Cross-Bank Processor State**
ZScream operates in different contexts than Oracle code:
```asm
namespace Oracle
{
    MainCode:
        REP #$20    ; Oracle code uses 16-bit
        JSL ZScreamFunction  ; ← Crosses namespace!
        ; ZScream may leave us in 8-bit mode
        LDA.w $1234 ; ← Potential error
}

; In ZScream (no namespace)
ZScreamFunction:
    SEP #$20        ; ZScream uses 8-bit
    ; ... work ...
    RTL             ; ← Doesn't restore Oracle's 16-bit mode
```

**Solution:** Use PHP/PLP or establish conventions:
```asm
namespace Oracle
{
    MainCode:
        PHP         ; Save current mode
        JSL ZScreamFunction
        PLP         ; Restore Oracle's mode
}
```

### Prevention

1. **Always initialize at function start**:
   ```asm
   MyFunction:
       PHP         ; Save caller's state
       SEP #$30    ; Set to known 8-bit state
       ; ... code ...
       PLP         ; Restore caller's state
       RTL
   ```

2. **Use Asar's rep/sep warnings**:
   ```asm
   rep #$20  ; Lowercase = warning if you use 8-bit operations next
   lda.w #$1234
   ```

3. **Document function register sizes** in comments:
   ```asm
   ; Function: CalculateOffset
   ; Inputs: A=16-bit (offset), X=8-bit (index)
   ; Outputs: A=16-bit (result)
   ; Clobbers: None
   ; Status: Returns with P unchanged (uses PHP/PLP)
   ```

---

## Cross-Namespace Calling

### Oracle of Secrets Namespace Architecture

```asm
namespace Oracle  ; Most custom code
{
    ; Oracle code here
}

; ZScream code is NOT in a namespace (vanilla bank space)
```

### The Visibility Problem

**From inside `Oracle{}` namespace:**
- ✅ Can call Oracle labels directly: `JSL OracleFunction`
- ❌ **Cannot** call ZScream labels directly: `JSL ZScreamFunction` fails
- ✅ **Must use** `Oracle_` prefix: `JSL Oracle_ZScreamFunction`

**Why?** Asar namespaces create separate symbol tables. ZScream labels must be explicitly exported to Oracle namespace.

### Common Errors

#### 1. **Calling ZScream from Oracle Without Prefix**
```asm
namespace Oracle
{
    MainCode:
        JSL LoadOverworldSprites_Interupt  ; ← ERROR: Label not found
}
```

**Error Message:**
```
error: (MainCode.asm:45): label "LoadOverworldSprites_Interupt" not found
```

**Solution:**
```asm
namespace Oracle
{
    MainCode:
        JSL Oracle_LoadOverworldSprites_Interupt  ; ← Use Oracle_ prefix
}
```

#### 2. **Forgetting to Export ZScream Label**
In `ZSCustomOverworld.asm`, labels must be exported:
```asm
; Define ZScream function
LoadOverworldSprites_Interupt:
{
    ; ... code ...
    RTL
}

; Export to Oracle namespace
namespace Oracle
{
    Oracle_LoadOverworldSprites_Interupt = LoadOverworldSprites_Interupt
}
```

If missing the export, Oracle code can't call it!

#### 3. **Wrong Call Direction**
```asm
; ZScream code (no namespace)
ZScreamFunction:
    JSL Oracle_SomeFunction  ; ← ERROR: ZScream isn't in Oracle namespace!
```

**Solution:** Exit Oracle namespace first:
```asm
namespace Oracle
{
    SomeFunction:
        ; ... code ...
        RTL
}

; Export Oracle function for ZScream
Oracle_SomeFunction = Oracle_SomeFunction  ; Make visible outside namespace

; Now ZScream can call it
ZScreamFunction:
    JSL Oracle_SomeFunction  ; ← Works!
```

### The Bridge Function Pattern

When you need ZScream to call Oracle code (e.g., day/night check for sprite loading):

```asm
namespace Oracle
{
    CheckIfNight:
        ; Main implementation (uses Oracle WRAM variables)
        LDA.l $7EE000  ; Custom time system
        CMP.w #$0012
        BCS .night
        ; ... logic ...
        RTL
}

; Bridge function (no namespace = accessible to ZScream)
ZSO_CheckIfNight:
{
    PHB
    PHK
    PLB
    
    ; Call Oracle function
    JSL Oracle_CheckIfNight  ; Can call INTO Oracle namespace
    
    PLB
    RTL
}

; Now ZScream hooks can use it
org $09C4C7
LoadOverworldSprites_Interupt:
{
    ; ... code ...
    JSL Oracle_ZSO_CheckIfNight  ; ← Bridge function name uses Oracle_ for exports
    ; ... code ...
}
```

### Best Practices

1. **Naming Convention:**
   - `Oracle_` prefix = Exported from any namespace for Oracle to use
   - `ZSO_` prefix = Bridge function for ZScream-to-Oracle calls
   - Combine: `Oracle_ZSO_CheckIfNight` = Bridge exported to Oracle

2. **Export Block Pattern:**
   ```asm
   namespace Oracle
   {
       ; All Oracle code here
   }
   
   ; Export block at end of file
   namespace Oracle
   {
       Oracle_ExportedFunction1 = ExportedFunction1
       Oracle_ExportedFunction2 = ExportedFunction2
       Oracle_ZSO_BridgeFunction = ZSO_BridgeFunction
   }
   ```

3. **Check Build Order:**
   In `Oracle_main.asm` or `Meadow_main.asm`:
   ```asm
   incsrc "Core/symbols.asm"        ; Define symbols first
   incsrc "Overworld/ZSCustomOverworld.asm"  ; ZScream next
   incsrc "Items/all_items.asm"     ; Oracle code after
   ```
   
   If Oracle code is included before ZScream defines exports, you'll get "label not found" errors!

---

## Memory Conflicts

### Bank Collisions

#### Understanding LoROM Mapping
ALTTP uses **LoROM** memory mapping:
- `$008000-$00FFFF` → ROM $000000-$007FFF (Bank $00)
- `$018000-$01FFFF` → ROM $008000-$00FFFF (Bank $01)
- `$028000-$02FFFF` → ROM $010000-$017FFF (Bank $02)
- ...
- `$208000-$20FFFF` → ROM $100000-$107FFF (Bank $20 / Custom)

**Oracle of Secrets uses banks $20-$41** for custom code (33 banks).

#### Common Collision Errors

##### 1. **Overlapping ORG Statements**
```asm
; File1.asm
org $288000
CustomFunction1:
    ; 200 bytes of code
    
; File2.asm  
org $288000  ; ← ERROR: Same address!
CustomFunction2:
    ; Overwrites CustomFunction1!
```

**Asar Error:**
```
warning: (File2.asm:10): overwrote some code here with org/pushpc command
```

**Solution:** Use `assert` to protect boundaries:
```asm
org $288000
CustomFunction1:
    ; ... code ...
    
assert pc() <= $288100  ; Reserve space

org $288100  ; Start next function safely
CustomFunction2:
    ; ... code ...
```

##### 2. **Freespace Conflicts**
```asm
; File1.asm
freecode  ; Asar auto-allocates at $208000

; File2.asm
freecode  ; ← May allocate at same location if not careful!
```

**Solution:** Use explicit banks:
```asm
; File1.asm
org $208000  ; Explicit bank $20

; File2.asm
org $218000  ; Explicit bank $21
```

##### 3. **Data Pool Overflow**
ZScream uses `$288000-$289938` for data pool (6456 bytes). If you add too much data:
```asm
org $288000
Pool_SpritePointers:
    dw SpritesArea00, SpritesArea01, ...  ; 160 areas * 6 states * 2 bytes = 1920 bytes
    
Pool_MapData:
    ; 5000 bytes
    
; Total: 6920 bytes - OVERFLOW! Crosses into $289938
```

**Check with:**
```asm
org $288000
; ... all pool data ...
assert pc() <= $289938  ; Verify within bounds
```

### WRAM Conflicts

#### Custom WRAM Region ($7E0730+)
Oracle of Secrets uses `$7E0730-$7E078F` (96 bytes in MAP16OVERFLOW region).

##### Common Issue: Variable Overlap
```asm
; Core/ram.asm
Oracle_FairyCounter = $7E0730  ; 1 byte

; Items/all_items.asm
Oracle_ItemEffect = $7E0730    ; ← ERROR: Same address!
```

**Solution:** Maintain central registry in `Core/ram.asm`:
```asm
; Custom WRAM Block
Oracle_FairyCounter = $7E0730     ; 1 byte - Fairy spawn counter
Oracle_ItemEffect = $7E0731       ; 1 byte - Current item effect
Oracle_BossHealth = $7E0732       ; 2 bytes - Boss HP (16-bit)
; ... continue registry ...

; Always check before adding new:
; Last used: $7E0733
; Available: $7E0734-$7E078F (91 bytes free)
```

### SRAM Conflicts

#### Repurposed Blocks
Oracle of Secrets repurposes vanilla SRAM:
- `$7EF38A-$7EF3C4`: Collectibles (59 bytes)
- `$7EF410-$7EF41F`: Dreams + WaterGateStates (16 bytes)

##### Issue: Vanilla Code Still Writes
Some vanilla functions may write to repurposed SRAM. Example:
```asm
; Vanilla function writes to $7EF38A (old value)
; Now you use $7EF38A for masks collected
; Vanilla write corrupts your data!
```

**Solution:** Hook and redirect vanilla writes:
```asm
; Find vanilla write
org $01D234  ; Example address
    JSL Oracle_RedirectedSave
    NOP

; Your redirect
namespace Oracle
{
    RedirectedSave:
        ; Don't write to $7EF38A anymore
        ; Or write to new location $7EF500
        STA.l $7EF500
        RTL
}
```

### Build Errors from Memory Issues

#### "No freespace large enough"
```
error: no freespace large enough found
```

**Cause:** Tried to use `freecode` but all banks are full.

**Solution:**
1. Check bank usage: `grep -r "org \$2[0-9]8000" .`
2. Add new bank range in Asar (if using freespace manager)
3. Use explicit `org` in unused bank

#### "PC out of bounds"
```
error: (file.asm:45): PC $29A000 is out of bounds
```

**Cause:** Code exceeded bank boundary ($xx8000-$xxFFFF in LoROM).

**Solution:**
```asm
; Check PC before running out of space
org $298000
LargeFunction:
    ; ... lots of code ...
    
assert pc() < $2A0000  ; Would fail and show where overflow happens

; Split across banks instead:
org $298000
LargeFunction_Part1:
    ; ... code ...
    JML LargeFunction_Part2

org $2A8000
LargeFunction_Part2:
    ; ... more code ...
```

---

## Graphics and DMA Issues

### Blank Screen

#### Symptoms
- Game boots, music plays, but screen is black
- Or screen is garbled/corrupted

#### Common Causes

##### 1. **Force Blank Not Released**
```asm
LDA.b #$80
STA $2100  ; Force blank (screen off)

; ... forgot to turn it back on ...
```

**Solution:** Always release force blank:
```asm
LDA.b #$80
STA $2100  ; Force blank ON

; ... do VRAM updates ...

LDA.b #$0F
STA $2100  ; Force blank OFF, brightness 15
```

##### 2. **VRAM Upload During Active Display**
```asm
; BAD: Writing to VRAM while screen is on
LDA.b #$80
STA $2115  ; VRAM port control

LDA.b #$00
STA $2116  ; VRAM address low
LDA.b #$20
STA $2117  ; VRAM address high

LDA.b #$FF
STA $2118  ; ← CORRUPTS VRAM if screen is on!
```

**Solution:** Use NMI or force blank:
```asm
; Method 1: During NMI
NMI_Handler:
    ; Screen is in VBlank, safe to write
    LDA.b #$FF
    STA $2118

; Method 2: Force blank
LDA.b #$80 : STA $2100  ; Screen off
LDA.b #$FF : STA $2118  ; Write to VRAM
LDA.b #$0F : STA $2100  ; Screen on
```

##### 3. **Corrupted Stripe Data**
ZScream uses stripe system for VRAM uploads. If stripe data is malformed:
```asm
; Stripe format: [Size] [Address Low] [Address High] [Data...] [00=End]

; BAD: Missing terminator
.stripe_data
    db $04, $00, $20  ; Upload 4 bytes to $2000
    db $FF, $FF, $FF, $FF
    ; ← Missing $00 terminator! Continues reading garbage
```

**Solution:**
```asm
.stripe_data
    db $04, $00, $20  ; Upload 4 bytes to $2000
    db $FF, $FF, $FF, $FF
    db $00            ; ← Terminator
```

### Flickering Graphics

#### Cause: DMA During Active Display
```asm
; BAD: DMA while screen is active causes flickering
LDA.b #$01
STA $4300  ; DMA mode
; ... setup DMA ...
LDA.b #$01
STA $420B  ; ← Trigger DMA mid-frame = flicker
```

**Solution:** Only DMA during VBlank (NMI):
```asm
NMI_Handler:
    ; Safe: We're in VBlank period
    LDA.b #$01
    STA $420B  ; Trigger DMA
    RTI
```

### Missing Tiles / Wrong Graphics

#### Symptoms
- Link appears as wrong sprite
- Enemies are garbled
- Tileset is corrupted

#### Common Causes

##### 1. **Wrong Graphics Slot**
ZScream uses 7 graphics slots:
- Slot 0-2: Static (BG graphics)
- Slot 3-6: Variable (Sprite graphics)

```asm
; BAD: Loading Link graphics to wrong slot
LDA.b #$05  ; Slot 5
LDX.w #LinkGFX
JSL LoadGraphicsSlot  ; ← Overwrites enemy sprites!
```

**Solution:** Follow slot conventions:
```asm
; Slot 3: Usually Link graphics
; Slot 4: Enemy set 1
; Slot 5: Enemy set 2
; Slot 6: Special sprites

LDA.b #$03  ; Slot 3 = Link
LDX.w #LinkGFX
JSL LoadGraphicsSlot
```

Refer to `Docs/World/Overworld/ZSCustomOverworldAdvanced.md` Section 3 for detailed slot assignments.

##### 2. **Sprite Pointer Table Corruption**
```asm
; Sprite pointer table must be valid addresses
Pool_Overworld_SpritePointers_state_0_New:
    dw Area00_Sprites, Area01_Sprites, ...
    dw $0000  ; ← BAD: Null pointer causes crash
```

**Solution:**
```asm
Pool_Overworld_SpritePointers_state_0_New:
    dw Area00_Sprites, Area01_Sprites, ...
    dw EmptySprites  ; ← Valid empty list

EmptySprites:
    db $FF  ; Terminator (no sprites)
```

### Palette Issues

#### Wrong Colors

##### Cause: Palette Not Updated
```asm
; Changed area but didn't reload palettes
LDA.b #$2B  ; New area
STA.w $040A

; ← Missing: JSL OverworldPalettesLoader
```

**Solution:**
```asm
LDA.b #$2B
STA.w $040A
JSL OverworldPalettesLoader  ; Load palettes for area $2B
```

#### Day/Night Palette Mismatch

If day/night transition doesn't update palettes:
```asm
; In time system transition
.switch_to_night
    LDA.b #$01
    STA.l $7EE001  ; Set night flag
    
    ; ← Missing: Reload palettes
    JSL Oracle_LoadTimeBasedPalettes
```

---

## ZScream-Specific Issues

### Sprite Loading Fails

#### Symptom
- Sprites don't appear in custom overworld area
- Error: "No sprites loaded"

#### Cause 1: Missing Sprite Pointer Entry
```asm
Pool_Overworld_SpritePointers_state_0_New:
    dw Area00_Sprites, Area01_Sprites, ...
    ; Only 80 entries, but you added area $81
```

**Solution:** Extend table:
```asm
Pool_Overworld_SpritePointers_state_0_New:
    dw Area00_Sprites, Area01_Sprites, ...
    ; ... (0x00-0x7F) ...
    dw Area80_Sprites, Area81_Sprites  ; Add new entries
```

#### Cause 2: Day/Night State Not Handled
```asm
; Sprite loading checks day/night with Oracle_ZSO_CheckIfNight
; If that function doesn't exist or returns wrong value:

ZSO_CheckIfNight:
    LDA.l $7EF3C5  ; Always returns day state
    RTL            ; ← Forgets to check $7EE000 (time)
```

**Solution:** Verify `ZSO_CheckIfNight` implementation (see Troubleshooting Section 5).

### Map16 Stripes Fail

#### Symptom
- Custom tiles don't appear
- Map16 changes aren't visible

#### Cause: Stripe Buffer Overflow
```asm
; ZScream uses 3 stripe buffers: $7EC800, $7ED800, $7EE800
; Each 2048 bytes

.generate_stripes
    LDX.w #$0000
    .loop
        ; Generate 1 tile worth of stripes (9 bytes)
        ; Loop 300 times = 2700 bytes
        ; ← OVERFLOWS! Corrupts other memory
```

**Solution:** Check buffer size:
```asm
.generate_stripes
    LDX.w #$0000
    .loop
        ; Generate stripe
        INX #9
        
        CPX.w #$0800  ; Check if buffer full (2048 bytes)
        BCS .buffer_full
        
        ; Continue...
        BRA .loop
        
    .buffer_full
        ; Stop generating
```

### Transition Hangs

#### Symptom
- Game freezes when transitioning between areas
- Music continues but screen is stuck

#### Cause 1: Infinite Loop in Hook
```asm
org $0283EE  ; Overworld transition hook
Oracle_CustomTransition:
    JSL SomeFunction
    JMP Oracle_CustomTransition  ; ← Infinite loop!
```

**Solution:**
```asm
org $0283EE
Oracle_CustomTransition:
    JSL SomeFunction
    JMP $0283F3  ; Jump to vanilla code after hook
```

#### Cause 2: Module Not Advanced
```asm
Oracle_TransitionHook:
    ; ... custom transition logic ...
    
    ; ← Forgot to increment $10 (module)
    RTL
```

**Solution:**
```asm
Oracle_TransitionHook:
    ; ... custom transition logic ...
    
    INC.b $10  ; Advance module
    RTL
```

### Missing Day/Night Graphics

#### Symptom
- Day sprites show at night
- Night enemies appear during day

#### Cause: Sprite Pointer Table Only Has 3 States
```asm
; You only defined 3 game states:
Pool_Overworld_SpritePointers_state_0_New:
    dw Area00_Day, Area01_Day, ...

; But Oracle_ZSO_CheckIfNight returns state 4-5 for night!
```

**Solution:** Define all 6 states (day + night):
```asm
Pool_Overworld_SpritePointers_state_0_New:
    ; State 0 day (entries $00-$9F)
    dw Area00_Day, Area01_Day, ...
    
    ; State 0 night (entries $A0-$13F)
    dw Area00_Night, Area01_Night, ...
    
    ; State 1 day (entries $140-$1DF)
    dw Area00_Day, Area01_Day, ...
    
    ; State 1 night (entries $1E0-$27F)
    dw Area00_Night, Area01_Night, ...
    
    ; State 2 day/night (similar structure)
```

See `Docs/World/Overworld/ZSCustomOverworldAdvanced.md` Section 4.3 for phase offset calculation.

---

## Build Errors

### Asar Assembler Errors

#### "label not found"
```
error: (file.asm:42): label "CustomFunction" not found
```

**Causes:**
1. **Typo in label name**
2. **Label defined after use** (in some cases)
3. **Namespace issue** (see Section 5)
4. **File not included** in main assembly file

**Solutions:**
```asm
; 1. Check spelling
JMP CustomFunction  ; ← Check this matches definition

CustomFunction:  ; ← Must be exact match (case-sensitive)

; 2. Move definition before use (if forward reference fails)

; 3. Check namespace
namespace Oracle
{
    JSL Oracle_CustomFunction  ; ← Need prefix
}

; 4. Include file
; In Oracle_main.asm:
incsrc "Custom/file.asm"  ; ← Make sure file is included
```

#### "redefined label"
```
error: (file.asm:100): label "CustomFunction" redefined
```

**Cause:** Same label defined twice.

**Solution:**
```asm
; BAD: Two definitions
CustomFunction:
    RTL

CustomFunction:  ; ← ERROR
    RTL

; GOOD: Use sublabels
CustomFunction:
    .entry_point1
        RTL
    
    .entry_point2
        RTL
```

#### "org or pushpc/pullpc not at start of line"
```
error: (file.asm:50): org or pushpc/pullpc not at start of line
```

**Cause:** Asar requires `org`, `pushpc`, `pullpc` as first statement on line.

**Solution:**
```asm
; BAD
    org $288000  ; ← Indented

; GOOD
org $288000  ; ← Column 1
```

#### "assertion failed"
```
error: (file.asm:200): assertion failed: pc() <= $09C50D
note: (file.asm:200): expanded from: 04C510 <= 04C50D
```

**Meaning:** Your code exceeded allowed space.

**Solution:**
```asm
org $09C4C7
CustomHook:
    ; ... 300 bytes of code ...
    ; PC is now at $09C55F

assert pc() <= $09C50D  ; FAILS: $09C55F > $09C50D

; Fix: Move some code elsewhere
org $09C4C7
CustomHook:
    ; Minimal hook
    JSL CustomHook_Main  ; Jump to freespace
    NOP : NOP
    
assert pc() <= $09C50D  ; ← Now passes

org $288000
CustomHook_Main:
    ; Main implementation in freespace
    ; ... 300 bytes ...
    RTL
```

---

## Debugging Tools and Techniques

### Emulator Debuggers

#### Mesen-S (Recommended)
**Features:**
- Powerful CPU debugger with execution breakpoints
- Memory viewer with live updates
- Conditional breakpoints: `A == #$42`
- Stack viewer
- Event viewer (shows NMI, IRQ timing)

**Usage:**
1. Tools → Debugger (F7)
2. Set breakpoint: Click line number in disassembly
3. Run until breakpoint hit
4. Examine registers (A, X, Y, P, S, PC, DB, PB)

**Advanced:**
```
Conditional breakpoint examples:
- Break when A equals value: A == #$0F
- Break when memory changes: [W]$7E0730
- Break when PC in range: PC >= $288000 && PC < $289000
- Break on BRK: PC == $000000
```

#### BSNES-Plus
**Features:**
- Cycle-accurate emulation (best for timing-sensitive debugging)
- Memory editor with search
- Tilemap viewer
- VRAM viewer

**Usage:**
1. Tools → Debugger
2. Set breakpoint: Right-click address
3. Memory search: Tools → Memory Editor → Search

### Manual Debugging Techniques

#### 1. **Breadcrumb Tracking**
```asm
; Add at suspected crash location
LDA.b #$01 : STA.l $7F5000  ; Breadcrumb 1

JSL SuspiciousFunction

LDA.b #$02 : STA.l $7F5000  ; Breadcrumb 2

; If crash occurs between breadcrumbs, $7F5000 = $01
; After crash, check $7F5000 in memory viewer
```

#### 2. **Register Logging**
```asm
; Log registers to RAM
Oracle_DebugLog:
    STA.l $7F5000    ; Save A
    PHX
    TXA
    STA.l $7F5001    ; Save X
    PLX
    PHY
    TYA
    STA.l $7F5002    ; Save Y
    PLY
    RTL

; Use it:
JSL Oracle_DebugLog  ; Snapshot registers
JSL ProblematicFunction
JSL Oracle_DebugLog  ; Snapshot again - compare
```

#### 3. **Assertion Macros**
```asm
; Define assertion macro
macro assert_equals(address, expected)
    PHA
    LDA.l <address>
    CMP.b #<expected>
    BEQ .ok
    BRK  ; Trigger crash if mismatch
    .ok
    PLA
endmacro

; Use it:
%assert_equals($7E0730, $05)  ; Check variable is expected value
```

#### 4. **PC Tracking**
```asm
; At critical points, save PC to RAM
LDA.b #$01 : STA.l $7F5010  ; Mark "entered function 1"
JSL Function1

LDA.b #$02 : STA.l $7F5010  ; Mark "entered function 2"
JSL Function2

; After crash, $7F5010 shows last function entered
```

### Common Debug Checklist

When encountering an issue:

1. ✅ **Check error message** carefully - Asar errors are usually precise
2. ✅ **Verify namespace** - Is label prefixed correctly?
3. ✅ **Check stack balance** - Equal push/pop counts?
4. ✅ **Verify processor state** - REP/SEP correct for operation?
5. ✅ **Check memory bounds** - Assertions in place?
6. ✅ **Test in Mesen-S first** - Best debugger for SNES
7. ✅ **Use breadcrumbs** - Narrow down crash location
8. ✅ **Check build order** - Files included in correct order?
9. ✅ **Review recent changes** - Compare with known working version
10. ✅ **Read vanilla code** - Understand what you're hooking

---

## Conclusion

This guide covers the most common issues encountered in ALTTP ROM hacking, particularly for Oracle of Secrets. Key takeaways:

- **BRK crashes** are usually caused by invalid jumps or corrupted return addresses
- **Stack corruption** comes from unbalanced push/pop or JSR/JSL vs RTS/RTL mismatches
- **Processor status** (M/X flags) must be carefully managed across function boundaries
- **Namespace issues** require proper exports and `Oracle_` prefixes
- **Memory conflicts** need assertions and careful space management
- **Graphics issues** stem from VRAM timing or corrupted data
- **ZScream issues** often relate to sprite loading tables and day/night state

When stuck:
1. Use Mesen-S debugger
2. Add breadcrumb tracking
3. Verify processor state
4. Check assertions
5. Review vanilla code

For further help:
- Read `Docs/World/Overworld/ZSCustomOverworldAdvanced.md` for ZScream details
- Check `Docs/Technical/Core/Ram.md` for memory map
- Review `Docs/Debugging/Guides/DevelopmentGuidelines.md` for best practices

Happy debugging! 🎮
