# Oracle of Secrets: 65816 ASM Style Guide

**Version**: 1.0
**Purpose**: Reduce AI errors and ensure consistent code quality across the codebase.

---

## Quick Reference Card

### Label Naming

| Type | Pattern | Example |
|------|---------|---------|
| Sprite function | `Sprite_{Name}_{Type}` | `Sprite_Booki_Main`, `Sprite_Darknut_Draw` |
| Menu function | `Menu_{Purpose}` | `Menu_InitGraphics`, `Menu_DrawBackground` |
| Link/Player | `Link_{Action}` | `Link_ConsumeMagicBagItem`, `Link_HandleYItem` |
| Oracle namespace | `Oracle_{Function}` | `Oracle_CheckIfNight`, `Oracle_MainEntry` |
| Local labels | `.lowercase_with_underscores` | `.not_being_pushed`, `.nextTile` |
| Constants (macro) | `!UPPERCASE` | `!SPRID`, `!Health`, `!Damage` |
| Memory addresses | `CamelCase` | `SprAction`, `LinkState`, `OOSPROG` |

### Processor State Checklist

- [ ] Always use size suffixes (`.b`, `.w`, `.l`) for ambiguous operations
- [ ] Use `PHP`/`PLP` for functions called from unknown context
- [ ] `REP #$30` = 16-bit A and X/Y, `SEP #$30` = 8-bit
- [ ] `REP #$20` / `SEP #$20` = A only
- [ ] `REP #$10` / `SEP #$10` = X/Y only

### Call Convention Checklist

- [ ] `JSL`/`RTL` for cross-bank calls (3-byte return address)
- [ ] `JSR`/`RTS` for same-bank calls (2-byte return address)
- [ ] **NEVER MIX** - mismatch causes crashes
- [ ] External hooks use `JSL`, internal helpers use `JSR`

---

## 1. File Structure

### 1.1 File Header (Required for new files)

```asm
; =========================================================
; File: sprites/enemies/my_enemy.asm
; Purpose: [Brief description of what this file implements]
; Author: [Your name or handle]
; =========================================================
```

### 1.2 Section Organization

```asm
; =========================================================
; Sprite Properties
; =========================================================
!SPRID              = $XX
!NbrTiles           = 02
; ... (30 properties in standard order)

; =========================================================
; Entry Points
; =========================================================
Sprite_MyEnemy_Long:
{ ... }

Sprite_MyEnemy_Prep:
{ ... }

; =========================================================
; Main Logic
; =========================================================
Sprite_MyEnemy_Main:
{ ... }

; =========================================================
; Drawing
; =========================================================
Sprite_MyEnemy_Draw:
{ ... }
```

---

## 2. Naming Conventions

### 2.1 Labels

**PascalCase with underscores for hierarchy:**

```asm
; Good
Sprite_Booki_Main
Menu_InitGraphics
Link_ConsumeMagicBagItem
Oracle_CheckIfNight

; Bad
spriteBookiMain        ; No underscores
sprite_booki_main      ; All lowercase
SPRITE_BOOKI_MAIN      ; All uppercase
```

### 2.2 Local Labels

**Lowercase with dot prefix:**

```asm
Sprite_Move:
{
  LDA.w SprAction, X : BNE .already_moving
    ; Start movement
    INC.w SprAction, X
  .already_moving
  RTS
}
```

### 2.3 Constants and Macros

```asm
; Macro parameters: !UPPERCASE
!SPRID              = $D5
!Health             = 08
!Damage             = 02

; Debug flags: !UPPERCASE with LOG prefix
!DEBUG              = 1
!LOG_MUSIC          = 1
!LOG_SPRITES        = 0

; Memory addresses: CamelCase (matching vanilla convention)
SprAction           = $0D80
LinkState           = $5D
OOSPROG             = $7EF3D6
```

### 2.4 Sprite Property Standard Order

All sprites MUST define properties in this order:

```asm
!SPRID              = Sprite_MyEnemyID
!NbrTiles           = 02
!Harmless           = 00
!Health             = 08
!Damage             = 02
!DeathAnimation     = 00
!ImperviousArrow    = 00
!ImperviousSword    = 00
!Boss               = 00
!Shadow             = 01
!Palette            = 00
!Hitbox             = $00
!Persist            = 00
!Statis             = 00
!CollisionLayer     = 00
!CanFall            = 01
!DeflectProjectiles = 00
!WaterSprite        = 00
!Blockable          = 00
!Prize              = 00
!Sound              = $00
!Interaction        = $00
!Subtype2           = 00
%Set_Sprite_Properties(Sprite_MyEnemy_Prep, Sprite_MyEnemy_Long)
```

---

## 3. Scoping and Indentation

### 3.1 Bracket Scoping

**ALL functions use `{ }` brackets** (NOT `subroutine`/`endsubroutine`):

```asm
Sprite_Booki_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal
  dw StalkPlayer
  dw HideFromPlayer
  dw ApproachPlayer

  StalkPlayer:
  {
    %PlayAnimation(0,1,16)
    JSR Sprite_Booki_Move
    RTS
  }

  HideFromPlayer:
  {
    ; Nested content indented 2 spaces
    LDA.b #$00
    STA.w SprAction, X
    RTS
  }
}
```

### 3.2 Indentation Rules

- **2-space indentation** for all nested content
- Local labels at same indentation as containing block
- Conditional code indented under branch:

```asm
  JSL Sprite_CheckActive : BCC .inactive
    ; Active sprite code (indented)
    JSR DoActiveStuff
  .inactive
  PLB
  RTL
```

---

## 4. Processor State Management

### 4.1 Size Suffixes (REQUIRED)

Always use explicit size suffixes when processor state matters:

```asm
; Good - explicit sizes
LDA.w #$1234          ; 16-bit load
LDA.b #$12            ; 8-bit load
STA.l $7E0000         ; Long address

; Bad - ambiguous
LDA #$12              ; Is this 8-bit or 16-bit?
```

### 4.2 State Preservation

```asm
; Functions called from unknown context
SomePublicFunction:
{
  PHP                   ; Save caller's state
  SEP #$30              ; Set known state (8-bit A, X/Y)

  ; ... function body ...

  PLP                   ; Restore caller's state
  RTL
}

; Internal helpers can assume state from caller
.helper:
  ; Assume 8-bit A from caller
  LDA.b #$00
  RTS
```

### 4.3 Processor Mode Macros

Use these macros for clarity:

```asm
%m8()                   ; SEP #$20 - 8-bit accumulator
%m16()                  ; REP #$20 - 16-bit accumulator
%a8()                   ; SEP #$20 - 8-bit A (alias)
%a16()                  ; REP #$20 - 16-bit A (alias)
%index8()               ; SEP #$10 - 8-bit X/Y
%index16()              ; REP #$10 - 16-bit X/Y
```

---

## 5. Hook and Patch Patterns

### 5.1 Small Patches (pushpc/pullpc)

```asm
pushpc
org $1EF27D
ShopItem_Banana:
{
  JSR $F4CE             ; SpriteDraw_ShopItem
  ; Custom code here
  RTS
}
assert pc() <= $1EF2AB  ; Ensure we fit
pullpc
```

### 5.2 Hook Pattern

```asm
; In patches.asm or near related code
pushpc
org $02XXXX             ; Vanilla address
  JSL MyCustomHook      ; 4-byte JSL
  NOP                   ; Pad if needed
pullpc

; The hook implementation
MyCustomHook:
{
  ; Preserve any clobbered code
  JSL OriginalRoutine

  ; Add custom logic
  LDA.w CustomFlag : BEQ .skip
    JSL DoCustomThing
  .skip

  RTL
}
```

### 5.3 Hook Documentation

```asm
; =========================================================
; Hook: $02XXXX - Link's Y-Button Handler
; Purpose: Add custom item handling for Magic Bag
; Vanilla Code Replaced: JSL $07F44C
; Side Effects: Clobbers A
; =========================================================
```

---

## 6. Comments and Documentation

### 6.1 Section Dividers

Use exactly 57 equal signs:

```asm
; =========================================================
; Section Name
; =========================================================
```

### 6.2 Bitfield Documentation

```asm
; Bitfield: hmwo oooo
;   o - OAM slot count (bits 0-4)
;   w - Wall-seeking behavior
;   m - Master sword ceremony flag
;   h - Harmless (no contact damage)
SprNbrOAM    = $0E40
```

### 6.3 TODO Comments

```asm
; TODO: Add chase animation when player is detected
; TODO(scawful): Refactor this to use lookup table
```

### 6.4 Magic Number Documentation

```asm
LDA.b #$08              ; 8-frame animation delay
CMP.w #$0100            ; Check if past screen boundary (256px)
```

---

## 7. Memory and Data Structures

### 7.1 Struct Definitions

```asm
struct TimeState $7EE000
{
  .Hours:     skip 1
  .Minutes:   skip 1
  .Speed:     skip 1
  .Padding:   skip 13
  .BlueVal:   skip 2
  .GreenVal:  skip 2
  .RedVal:    skip 2
}
endstruct
```

### 7.2 Inline Data Tables

```asm
Sprite_Draw:
{
  ; ... draw code ...
  RTS

  ; Data tables use dot notation
  .start_index
    db $00, $04, $08, $0C
  .nbr_of_tiles
    db 3, 3, 3, 3
  .x_offsets
    dw 4, -4, 4, -4
}
```

---

## 8. Error Prevention Checklist

### Before Submitting Code

- [ ] All labels use correct PascalCase_With_Underscores
- [ ] All local labels use .dot_notation
- [ ] Size suffixes on all ambiguous loads/stores
- [ ] JSL/RTL and JSR/RTS pairs matched correctly
- [ ] Hooks have `assert` statements to prevent overflow
- [ ] Magic numbers have inline comments explaining purpose
- [ ] Sprite properties in standard order
- [ ] Section dividers between major code blocks

### Common Crash Causes

1. **JSL/JSR mismatch** - Using RTL with JSR or RTS with JSL
2. **Bank crossing** - Forgetting to set DBR with PHK:PLB
3. **Processor state** - Assuming 8-bit when 16-bit or vice versa
4. **Hook overflow** - Patch exceeds available space
5. **Missing pullpc** - Stack imbalance from pushpc

---

## 9. Oracle of Secrets Specific Patterns

### 9.1 Sprite Entry Point Pattern

```asm
Sprite_MyEnemy_Long:
{
  PHB : PHK : PLB       ; Set data bank to current bank
  JSR Sprite_MyEnemy_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .inactive
    JSR Sprite_MyEnemy_Main
  .inactive
  PLB
  RTL
}
```

### 9.2 State Machine Pattern

```asm
Sprite_MyEnemy_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal
  dw State_Idle
  dw State_Chase
  dw State_Attack
  dw State_Retreat

  State_Idle:
  {
    %PlayAnimation(0,1,16)
    ; Check for player proximity
    JSL Sprite_CheckDamageToLink
    BCC .stay_idle
      INC.w SprAction, X    ; Transition to Chase
    .stay_idle
    RTS
  }
  ; ... more states ...
}
```

### 9.3 SRAM Flag Checking

```asm
; Check Oracle progression flag
LDA.l OOSPROG : AND.b #$01 : BEQ .not_complete
  ; Player has completed this milestone
.not_complete

; Bitfield reference for OOSPROG ($7EF3D6):
; .fmp h.i.
;   i = Intro complete
;   h = Hall of Secrets visited
;   p = Pendant progress
;   m = Master Sword acquired
;   f = Fortress of Secrets
```

---

## 10. AI Agent Instructions

### 10.1 Before Writing Code

1. **Read existing patterns** - Search for similar implementations
2. **Check memory map** - Verify address usage won't conflict
3. **Identify hook points** - Use Hyrule Historian to find vanilla code
4. **Verify bank space** - Check MemoryMap.md for free space

### 10.2 When Modifying Code

1. **Always read the file first** - Never assume structure
2. **Match existing style** - Follow patterns in the same file
3. **Use explicit sizes** - Never rely on assumed processor state
4. **Add assert statements** - Prevent silent overflow errors

### 10.3 After Writing Code

1. **Run build** - Use `mcp__book-of-mudora__run_build()`
2. **Run lint** - Use `mcp__book-of-mudora__lint_asm()`
3. **Verify in emulator** - Test before marking complete

---

## Appendix: Common Macro Reference

### Animation and Drawing
- `%PlayAnimation(start, end, speed)` - Animate sprite frames
- `%DrawSprite(...)` - Draw sprite OAM
- `%SetFrame(n)` - Set current animation frame

### Sprite Control
- `%GotoAction(n)` - Change sprite state
- `%SetTimer*(n)` - Set various timers
- `%SetSpriteSpeed*(n)` - Set movement speed
- `%SetHarmless()` / `%SetImpervious()` - Damage flags

### Player
- `%PreventPlayerMovement()` / `%AllowPlayerMovement()`
- `%GetPlayerRupees()` - Return rupee count
- `%ShowUnconditionalMessage(id)` - Display dialogue
- `%ShowSolicitedMessage(id)` - Display on interaction

### Audio
- `%PlaySFX1(id)` / `%PlaySFX2(id)` - Sound effects
- `%PlayMusic(id)` - Change music

### Debugging
- `%print_debug(msg)` - Build-time debug output
- `%log_section(name, flag)` - Conditional section logging
