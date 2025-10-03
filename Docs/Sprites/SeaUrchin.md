# Sea Urchin Sprite Analysis

This document provides a detailed analysis of the `sea_urchin.asm` sprite, outlining its properties, core routines, and behavioral patterns.

## 1. Sprite Properties

The following `!SPRID` constants define Sea Urchin's fundamental characteristics:

```asm
!SPRID              = Sprite_SeaUrchin
!NbrTiles           = 04  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 06  ; Number of Health the sprite have
!Damage             = 04  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 00  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 01  ; 01 = can be blocked by link's shield?
!Prize              = 03  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss
```
**Note:** `!Health` is fixed at `06` and `!Damage` is `04` (half a heart).

## 2. Core Routines

### 2.1. `Sprite_SeaUrchin_Long` (Main Loop)

This is the primary entry point for Sea Urchin's per-frame execution. It handles drawing, shadow rendering, and then dispatches to the main logic routine if the sprite is active.

```asm
Sprite_SeaUrchin_Long:
{
  PHB : PHK : PLB
  JSR Sprite_SeaUrchin_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_SeaUrchin_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

### 2.2. `Sprite_SeaUrchin_Prep` (Initialization)

This routine is executed once when Sea Urchin is first spawned. It sets the initial prize and conditionally modifies its imperviousness and prize based on the `WORLDFLAG` (likely for different game states or areas, such as the Eon Sea).

```asm
Sprite_SeaUrchin_Prep:
{
  PHB : PHK : PLB
  LDA #$01 : STA.w SprPrize, X ; Default prize
  LDA.w WORLDFLAG : BEQ +     ; Check WORLDFLAG
    ; Eon Sea Urchin impervious to sword
    LDA.b #%10000100 : STA.w SprDefl, X ; Set imperviousness flags
    LDA.b #$07 : STA.w SprPrize, X ; Change prize for Eon Sea
  +
  PLB
  RTL
}
```

### 2.3. `Sprite_SeaUrchin_Main` (Behavioral State Machine)

This routine manages Sea Urchin's AI through a simple state machine, using `SprAction, X` to determine its current behavior. It includes `Idle` and `Death` states.

```asm
Sprite_SeaUrchin_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Idle
  dw Death

  Idle:
  {
    %PlayAnimation(0,3,8)
    %PlayerCantPassThrough()
    %DoDamageToPlayerSameLayerOnContact()
    JSL Sprite_CheckDamageFromPlayer : BCC .NoDamage
      %GotoAction(1) ; Transition to Death state if damaged
    .NoDamage
    RTS
  }

  Death:
  {
    LDA.b #$06 : STA.w SprState, X ; Set sprite state to despawn
    LDA.b #$0A : STA.w SprTimerA, X
    STZ.w SprPrize,X
    JSL ForcePrizeDrop_long ; Force prize drop
    LDA.b #$09 : JSL SpriteSFX_QueueSFX3WithPan ; Play sound effect
    RTS
  }
}
```

### 2.4. `Sprite_SeaUrchin_Draw` (Drawing Routine)

This routine is responsible for rendering Sea Urchin's graphics. It uses a custom OAM allocation and manipulation logic to handle its multi-tile appearance and animation.

```asm
Sprite_SeaUrchin_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?
  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX

  RTS


  .start_index
    db $00, $01, $02, $03, $04, $05, $06, $07
  .nbr_of_tiles
    db 0, 0, 0, 0, 0, 0, 0, 0
  .x_offsets
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
  .y_offsets
    dw 0
    dw -1
    dw 0
    dw -1
    dw 0
    dw -1
    dw 0
    dw -1
  .chr
    db $EA
    db $EC
    db $EA
    db $EC
    db $EA
    db $EC
    db $EA
    db $EC
  .properties
    db $29
    db $29
    db $69
    db $69
    db $29
    db $29
    db $69
    db $69
}
```

## 3. Key Behaviors and Implementation Details

*   **Fixed Health:** Sea Urchin has a fixed health of `06` and its health is not dynamically scaled based on Link's sword level.
*   **Dynamic Prize Drop and Imperviousness:** A notable feature is its conditional behavior based on the `WORLDFLAG`. If this flag is set (e.g., indicating a specific game area like the Eon Sea), the Sea Urchin becomes impervious to sword attacks (`SprDefl`) and drops a different prize. This demonstrates how global game state variables can influence individual sprite properties.
*   **State Management:** Sea Urchin uses a simple state machine with `Idle` and `Death` states, managed by `SprAction, X` and `JumpTableLocal`.
*   **Movement Patterns:** The Sea Urchin has a simple idle animation (`%PlayAnimation(0,3,8)`) and does not exhibit complex movement behaviors. It remains stationary but can be pushed by Link (`%PlayerCantPassThrough()`).
*   **Damage Handling:** Upon taking damage from Link (`Sprite_CheckDamageFromPlayer`), the Sea Urchin transitions to its `Death` state. In this state, it despawns (`STZ.w SprState, X`), forces a prize drop (`ForcePrizeDrop_long`), and plays a sound effect (`SpriteSFX_QueueSFX3WithPan`).
*   **Custom OAM Drawing:** Sea Urchin utilizes a custom OAM drawing routine to render its multi-tile appearance and animation. The drawing logic includes coordinate calculations with `REP`/`SEP` for 16-bit operations.
