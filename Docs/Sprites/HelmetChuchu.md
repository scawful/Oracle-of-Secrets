# Helmet Chuchu Sprite Analysis

This document provides a detailed analysis of the `helmet_chuchu.asm` sprite, outlining its properties, core routines, and behavioral patterns.

## 1. Sprite Properties

The following `!SPRID` constants define Helmet Chuchu's fundamental characteristics:

```asm
!SPRID              = Sprite_HelmetChuchu
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = $10 ; Number of Health the sprite have
!Damage             = 04  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 00  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 00  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss
```
**Note:** `!Health` is initially set to `$10` but is dynamically determined during initialization based on Link's sword level.

## 2. Core Routines

### 2.1. `Sprite_HelmetChuchu_Long` (Main Loop)

This is the primary entry point for Helmet Chuchu's per-frame execution. It handles drawing, shadow rendering, and then dispatches to the main logic routine if the sprite is active.

```asm
Sprite_HelmetChuchu_Long:
{
  PHB : PHK : PLB
  JSR Sprite_HelmetChuchu_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_HelmetChuchu_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

### 2.2. `Sprite_HelmetChuchu_Prep` (Initialization)

This routine is executed once when Helmet Chuchu is first spawned. It sets its health based on Link's sword level, randomly assigns an initial `SprAction` (determining its type and initial frame), and initializes `SprMiscB` and `SprMiscD` to zero.

```asm
Sprite_HelmetChuchu_Prep:
{
  PHB : PHK : PLB
  LDA.l Sword : DEC A : TAY
  LDA.w .health, Y : STA.w SprHealth, X ; Set health based on sword level
  JSL GetRandomInt : AND.b #$02 : STA.w SprAction, X ; Randomly set initial action (0, 1, or 2)
  STZ.w SprMiscB, X
  STZ.w SprMiscD, X
  LDA.w SprAction, X : BNE +
    LDA.b #$04 : STA.w SprFrame, X ; If action 0, set frame to 4 (Helmet Green)
  +
  CMP.b #$02 : BNE +
    LDA.b #$02 : STA.w SprFrame, X ; If action 2, set frame to 2 (Mask Red)
  +
  PLB
  RTL

  .health
    db $08, $0C, $0F, $10 ; Health values for each sword level
}
```

### 2.3. `Sprite_HelmetChuchu_Main` (Behavioral State Machine)

This routine manages Helmet Chuchu's AI through a state machine, using `SprAction, X` to determine its current behavior. It includes states for different Chuchu types (Green/Red, Helmet/No Helmet, Mask/No Mask) and separate states for the detached helmet and mask.

```asm
Sprite_HelmetChuchu_Main:
{
  JSL Sprite_DamageFlash_Long
  %SpriteJumpTable(GreenChuchu_Helmet,
                  GreenChuchu_NoHelmet,
                  RedChuchu_Masked,
                  RedChuchu_NoMask,
                  HelmetSubtype,
                  MaskSubtype)

  GreenChuchu_Helmet:
  {
    %StartOnFrame(4)
    %PlayAnimation(4, 5, 16)
    JSR Sprite_CheckForHookshot : BCC +
      LDA.w SprFlash, X : BEQ +
        %GotoAction(1) ; Transition to GreenChuchu_NoHelmet if hookshot hit and not flashing
    +
    JSL Sprite_CheckDamageFromPlayer
    JSR Sprite_Chuchu_Move
    RTS
  }

  GreenChuchu_NoHelmet:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 1, 16)
    LDA.w SprMiscD, X : BNE +
      JSR HelmetChuchu_SpawnHookshotDrag ; Spawn detached helmet
      LDA.b #$01 : STA.w SprMiscD, X ; Set flag to prevent re-spawning
    +
    JSL Sprite_CheckDamageFromPlayer
    JSR Sprite_Chuchu_Move
    RTS
  }

  RedChuchu_Masked:
  {
    %StartOnFrame(2)
    %PlayAnimation(2, 3, 16)
    JSR Sprite_CheckForHookshot : BCC +
      LDA.w SprFlash, X : BEQ +
        %GotoAction(3) ; Transition to RedChuchu_NoMask if hookshot hit and not flashing
    +
    JSL Sprite_CheckDamageFromPlayer
    JSR Sprite_Chuchu_Move
    RTS
  }

  RedChuchu_NoMask:
  {
    %StartOnFrame(6)
    %PlayAnimation(6, 7, 16)
    LDA.w SprMiscD, X : BNE +
      JSR HelmetChuchu_SpawnHookshotDrag ; Spawn detached mask
      LDA.b #$01 : STA.w SprMiscD, X ; Set flag to prevent re-spawning
    +
    JSL Sprite_CheckDamageFromPlayer
    JSR Sprite_Chuchu_Move
    RTS
  }

  HelmetSubtype:
  {
    %StartOnFrame(8)
    %PlayAnimation(8, 8, 16)
    JSL Sprite_Move
    JSL Sprite_CheckIfLifted
    JSL Sprite_CheckIfRecoiling
    JSL ThrownSprite_TileAndSpriteInteraction_long
    RTS
  }

  MaskSubtype:
  {
    %StartOnFrame(8)
    %PlayAnimation(9, 9, 16)
    JSL Sprite_Move
    JSL Sprite_CheckIfLifted
    JSL Sprite_CheckIfRecoiling
    JSL ThrownSprite_TileAndSpriteInteraction_long
    RTS
  }
}
```

### 2.4. `Sprite_Chuchu_Move` (Movement and Interaction Logic)

This routine handles Helmet Chuchu's movement, which involves bouncing towards or recoiling from the player. It uses `SprMiscB, X` to switch between these two behaviors.

```asm
Sprite_Chuchu_Move:
{
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_PlayerCantPassThrough
  JSL Sprite_CheckIfRecoiling

  LDA.w SprMiscB, X
  JSL JumpTableLocal

  dw BounceTowardPlayer
  dw RecoilFromPlayer

  BounceTowardPlayer:
  {
    JSL GetRandomInt : AND.b #$02 : STA $09 ; Speed
    JSL GetRandomInt : AND.b #$07 : STA $08 ; Height

    JSL Sprite_MoveAltitude
    DEC.w $0F80,X : DEC.w $0F80,X
    LDA.w SprHeight, X : BPL .aloft
      STZ.w SprHeight, X
      LDA.b $08 : STA.w $0F80, X ; set height from 08
      LDA.b $09
      JSL Sprite_ApplySpeedTowardsPlayer
    .aloft
    LDA.w SprHeight, X : BEQ .dontmove
      JSL Sprite_Move
    .dontmove

    JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
      INC.w SprMiscB, X ; Switch to RecoilFromPlayer
      LDA.b #$20 : STA.w SprTimerB, X
    .no_damage

    JSL Sprite_CheckDamageToPlayer : BCC .no_attack
      INC.w SprMiscB, X ; Switch to RecoilFromPlayer
      LDA.b #$20 : STA.w SprTimerB, X
    .no_attack

    RTS
  }

  RecoilFromPlayer:
  {
    JSL GetRandomInt : AND.b #$02 : STA $09 ; Speed
    LDA.w SprX, X : CLC : ADC $09 : STA $04
    LDA.w SprY, X : SEC : SBC $09 : STA $06
    LDA.w SprXH, X : ADC #$00 : STA $05
    LDA.w SprYH, X : ADC #$00 : STA $07
    LDA $09 : STA $00 : STA $01
    JSL Sprite_ProjectSpeedTowardsEntityLong

    LDA.w SprTimerB, X : BNE .not_done
    JSR HelmetChuchu_SpawnHookshotDrag ; Spawn detached helmet/mask
      STZ.w SprMiscB, X ; Switch back to BounceTowardPlayer
    .not_done

    RTS
  }
}
```

### 2.5. `HelmetChuchu_SpawnHookshotDrag`

This routine is responsible for spawning the detached helmet or mask as a separate sprite when the Chuchu is hit by a hookshot. It determines whether to spawn a helmet or a mask based on the Chuchu's current `SprAction`.

```asm
HelmetChuchu_SpawnHookshotDrag:
{
  ; Based on the subtype either spawn the helmet or the mask
  PHX
  LDA.w SprAction, X : CMP.b #$01 : BEQ .spawn_helmet
                       CMP.b #$03 : BEQ .spawn_mask

  .spawn_helmet
  LDA.b #$05 ; Sprite ID for helmet/mask (assuming $05 is the ID)
  JSL Sprite_SpawnDynamically : BMI .no_space
    LDA.b #$05 : STA.w SprAction, Y ; Set action for detached helmet
    JMP .prepare_mask
  .no_space
  JMP .no_space2

  .spawn_mask
  LDA.b #$05 ; Sprite ID for helmet/mask
  JSL Sprite_SpawnDynamically : BMI .no_space2
  LDA.b #$04 : STA.w SprAction, Y ; Set action for detached mask
  .prepare_mask
    JSL Sprite_SetSpawnedCoordinates
    LDA.b #$10 : STA.w SprHealth, Y
    LDA.b #$00 : STA.w SprMiscB, Y
    LDA.b #$80 : STA.w SprTimerA, Y
    LDA.b #$01 : STA.w SprNbrOAM,  Y
    LDA.w .speed_x, X : STA.w SprXSpeed, Y
    LDA.w .speed_y, X : STA.w SprYSpeed, Y
  .no_space2
  PLX
  RTS

  .speed_x
    db  16, -11, -16, 11

  .speed_y
    db   0,  11,   0, -11
}
```

### 2.6. `Sprite_CheckForHookshot`

This routine checks if a hookshot is currently active and interacting with the Chuchu. It iterates through ancilla slots to find a hookshot (`$1F`) and returns with the carry flag set if found.

```asm
Sprite_CheckForHookshot:
{
  PHX
  LDX.b #$0A
  .next_ancilla
  LDA.w $0C4A, X : CMP.b #$1F : BNE .not_hooker ; Check ancilla type (assuming $1F is hookshot)
    PLX
    SEC ; Carry set if hookshot found
    RTS
  .not_hooker
  DEX
  BPL .next_ancilla
  PLX
  CLC ; Carry clear if no hookshot found
  RTS
}
```

### 2.7. `Sprite_HelmetChuchu_Draw` (Drawing Routine)

This routine is responsible for rendering Helmet Chuchu's graphics. It uses a custom OAM allocation and manipulation logic to handle its multi-tile appearance and animation, dynamically adjusting based on its current state (helmet/mask, color, animation frame).

```asm
Sprite_HelmetChuchu_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprGfx, X : CLC : ADC.w SprFrame, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06
  LDA.w SprFlash, X : STA $08

  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?
  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : STA ($90), Y
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
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX

  RTS


  ; =======================================================
  ;         chr     prop
  ; Mask    $04     $37
  ; Helmet  $08     $3B

  .start_index
  db $00, $02, $03, $06, $08, $0A, $0C, $0E, $0F, $10
  .nbr_of_tiles
  db 1, 0, 2, 1, 1, 1, 1, 0, 0, 0
  .y_offsets
  dw 0, -8
  dw 0
  dw 0, -8, -8
  dw 0, -4
  dw 0, -8
  dw 0, -4
  dw 0, -8
  dw 0
  dw 0
  dw 0
  .chr
  ; No Helmet Green
  db $26, $16
  db $24
  ; Mask Red
  db $26, $16, $04
  db $24, $04
  ; Helmet Green
  db $26, $08
  db $24, $08
  ; No Helmet Red
  db $26, $16
  db $24
  ; Mask
  db $04
  ; Helmet
  db $08
  .properties
  db $2B, $2B
  db $2B
  db $25, $25, $27
  db $25, $27
  db $2B, $29
  db $2B, $29
  db $25, $25
  db $25
  ; mask
  db $27
  ; helmet
  db $29
}
```

## 3. Key Behaviors and Implementation Details

*   **Dynamic Appearance and State:** Helmet Chuchu is a highly dynamic sprite that changes its appearance and behavior based on whether it has a helmet/mask and its color (green/red). This is managed through its `SprAction` and `SprFrame` values.
*   **Conditional Damage Handling:** The Chuchu's vulnerability to damage is tied to the presence of its helmet or mask. When hit by a hookshot, the helmet/mask detaches, making the Chuchu vulnerable.
*   **Hookshot Interaction:** Special logic (`Sprite_CheckForHookshot`) is implemented to detect interaction with Link's hookshot, which triggers the detachment of the helmet/mask.
*   **Detached Helmet/Mask as Separate Sprites:** When the helmet or mask is detached, it is spawned as an independent sprite (`HelmetSubtype` or `MaskSubtype`) with its own movement (`Sprite_Move`), collision (`ThrownSprite_TileAndSpriteInteraction_long`), and interaction logic. This demonstrates a sophisticated use of child sprites.
*   **Movement Patterns:** The Chuchu moves by bouncing towards (`BounceTowardPlayer`) and recoiling from (`RecoilFromPlayer`) the player, with randomness introduced in speed and height. This creates a distinct and challenging movement pattern.
*   **Custom OAM Drawing:** The `Sprite_HelmetChuchu_Draw` routine is a complex example of custom OAM manipulation. It dynamically selects tiles and properties based on the Chuchu's current state, allowing for seamless transitions between helmeted, masked, and vulnerable forms.
*   **`SprMiscB` Usage:** This variable controls the Chuchu's movement sub-states (`BounceTowardPlayer` and `RecoilFromPlayer`). It also plays a role in the detached helmet/mask sprites.
*   **`SprMiscD` Usage:** This variable acts as a flag to ensure that the `HelmetChuchu_SpawnHookshotDrag` routine is called only once when the helmet/mask is detached.
*   **`SprTimerB` Usage:** Used to control the duration of the recoil state.
