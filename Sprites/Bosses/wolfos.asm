; =========================================================
; Wolfos Sprite Properties
; =========================================================

!SPRID              = Sprite_Wolfos
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 30  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
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
!ImperviousArrow    = 01  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss
%Set_Sprite_Properties(Sprite_Wolfos_Prep, Sprite_Wolfos_Long)

; =========================================================

Sprite_Wolfos_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Wolfos_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Wolfos_CheckIfDefeated
    JSR Sprite_Wolfos_Main
  .SpriteIsNotActive
  PLB
  RTL
}

WolfosDialogue = SprMiscD

Sprite_Wolfos_CheckIfDefeated:
{
  LDA.b $1B : BNE .indoors
    LDA.w SprHealth, X : CMP.b #$04 : BCS .not_defeated
      LDA.b #$06 : STA.w SprAction, X ; Set to defeated action
      LDA.b #$09 : STA.w SprState, X  ; Set to normal state, avoid death
      LDA.b #$40 : STA.w SprHealth, X ; Refill the health of the sprite
      STZ.w WolfosDialogue, X
    .not_defeated
  .indoors
  RTS
}

; =========================================================

Sprite_Wolfos_Prep:
{
  PHB : PHK : PLB
  LDA.b $1B : BNE .spawn_wolfos
    ; Outdoors
    ; Check if the wolfos has been defeated
    LDA.l $7EF303 : CMP.b #$01 : BNE .spawn_wolfos
      STZ.w SprState, X ; Don't spawn the sprite
      PLB
      RTL
  .spawn_wolfos
  LDA.b #$40 : STA.w SprTimerA, X
  LDA.b #$82 : STA.w SprDefl, X ; persist, impervious to arrows
  LDA.b #$08 : STA.w SprNbrOAM, X ; Nbr Oam Entries
  STZ.w SprMiscG, X
  PLB
  RTL
}

; =========================================================

macro AttackForward()
  %GotoAction($00)
endmacro

macro AttackBack()
  %GotoAction($01)
endmacro

macro WalkRight()
  %GotoAction($02)
endmacro

macro WalkLeft()
  %GotoAction($03)
endmacro

macro AttackRight()
  %GotoAction($04)
endmacro

macro AttackLeft()
  %GotoAction($05)
endmacro

macro Subdued()
  %GotoAction($06)
endmacro

macro GrantMask()
  %GotoAction($07)
endmacro

macro Dismiss()
  %GotoAction($08)
endmacro

!NormalSpeed = $08
!AttackSpeed = $0F

Sprite_Wolfos_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Wolfos_AttackForward ; 0x00
  dw Wolfos_AttackBack    ; 0x01
  dw Wolfos_WalkRight     ; 0x02
  dw Wolfos_WalkLeft      ; 0x03
  dw Wolfos_AttackRight   ; 0x04
  dw Wolfos_AttackLeft    ; 0x05
  dw Wolfos_Subdued       ; 0x06
  dw Wolfos_GrantMask     ; 0x07
  dw Wolfos_Dismiss       ; 0x08

  Wolfos_AttackForward:
  {
    %PlayAnimation(0, 2, 10)
    JSR Wolfos_Move
    JSR Wolfos_DecideAction
    %SetSpriteSpeedY(!NormalSpeed)
    %SetTimerA($30)
    RTS
  }

  Wolfos_AttackBack:
  {
    %PlayAnimation(3, 5, 10)
    JSR Wolfos_Move
    %SetSpriteSpeedY(-!NormalSpeed)
    %SetTimerA($30)
    RTS
  }

  Wolfos_WalkRight:
  {
    %StartOnFrame(6)
    %PlayAnimation(6, 8, 10)
    JSR Wolfos_Move
    LDA #!NormalSpeed : STA.w SprXSpeed, X
    STZ.w SprYSpeed, X

    JSL GetRandomInt : AND.b #$3F : BNE +
      %AttackRight()
    +
    %SetTimerA($30)
    RTS
  }

  Wolfos_WalkLeft:
  {
    %StartOnFrame(9)
    %PlayAnimation(9, 11, 10)
    JSR Wolfos_Move
    LDA #-!NormalSpeed : STA.w SprXSpeed, X
    STZ.w SprYSpeed, X

    JSL GetRandomInt : AND.b #$3F : BNE +
      %AttackLeft()
    +
    %SetTimerA($30)
    RTS
  }

  Wolfos_AttackRight:
  {
    %StartOnFrame(12)
    %PlayAnimation(12, 13, 10)
    LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X
    JSL Sprite_Move
    LDA #!AttackSpeed : STA.w SprXSpeed, X
    LDA.w SprTimerA, X : BNE +
      LDA.w SprGfxProps, X : AND.b #$40 : STA.w SprGfxProps, X
      %WalkRight()
    +
    RTS
  }

  Wolfos_AttackLeft:
  {
    %StartOnFrame(14)
    %PlayAnimation(14, 15, 10)
    JSL Sprite_Move
    LDA #-!AttackSpeed : STA.w SprXSpeed, X
    LDA.w SprTimerA, X : BNE +
      %WalkLeft()
    +
    RTS
  }

  Wolfos_Subdued:
  {
    %PlayAnimation(0, 0, 10)
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X

    ; Run the Wolfos dialogue once.
    LDA.w WolfosDialogue, X : BNE .wait
      %ShowUnconditionalMessage($23)
      LDA.b #$01 : STA.w WolfosDialogue, X
    .wait

    ; Wait for Song of Healing before granting the mask.
    LDA.b SongFlag : CMP.b #$01 : BNE .ninguna_cancion
      STZ.b SongFlag
      LDA.b #$20 : STA.w SprTimerD, X
      LDA.w POSX : STA.w SprX, X
      LDA.w POSXH : STA.w SprXH, X
      LDA.w POSY : SEC : SBC.b #$08 : STA.w SprY, X
      LDA.w POSYH : STA.w SprYH, X
      %GrantMask()
    .ninguna_cancion
    RTS
  }

  Wolfos_GrantMask:
  {
    ; Set the sprite frame to the Wolfos mask gfx.
    LDA.b #16 : STA.w SprFrame, X

    ; Homemade Link_ReceiveItem
    LDA.w SprTimerD, X : BNE .wait
      LDA.b #$01 : STA.w BRANDISH
      %ShowUnconditionalMessage($10F)
      LDA.b #$01 : STA.l WolfMask
      %Dismiss()
    .wait
    RTS
  }

  Wolfos_Dismiss:
  {
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X

    LDA.w SprTimerD, X : BNE .dismiss
      LDA.b #$00 : STA.w SprState, X ; kill sprite normal style
      STZ.w SprAction, X
      STZ.w SprHealth, X
      STZ.w BRANDISH ; Stop Link from holding his hands up.
      RTS
    .dismiss
    RTS
  }
}

Wolfos_Move:
{
  JSL Sprite_DamageFlash_Long
  JSL Sprite_CheckDamageFromPlayer : BCC +
    LDA.b #$01 : STA.w SprMiscF, X
  +
  JSL Sprite_PlayerCantPassThrough
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_CheckIfRecoiling
  JSL Sprite_Move
  JSR Wolfos_DecideAction
  RTS
}

Wolfos_DecideAction:
{
  LDA.w SprTimerA, X : BNE .decide_new_action
    JSL GetRandomInt : AND #$02 : STA.w SprMiscG, X
    RTS
  .decide_new_action

  LDA.w SprMiscG, X
  JSL JumpTableLocal

  dw Wolfos_MoveAction_Basic
  dw Wolfos_MoveAction_CirclePlayer
  dw Wolfos_MoveAction_Dodge
}

Wolfos_MoveAction_Basic:
{
  JSL Sprite_DirectionToFacePlayer
  ; y distance from player
  LDA $0E : STA.w SprMiscC, X
  ; x distance from player
  LDA $0F : STA.w SprMiscB, X

  ; Check if y distance is significant
  LDA.w SprMiscC, X : CMP #$10 : BCS .adjust_y
  ; Check if x distance is significant
  LDA.w SprMiscB, X : CMP #$10 : BCS .adjust_x
    RTS ; No adjustments

  .adjust_y
  JSL Sprite_IsBelowPlayer : TYA : BEQ .above_player
    %AttackBack()
    RTS
  .above_player
  %AttackForward()
  RTS

  .adjust_x
  JSL Sprite_IsToRightOfPlayer : TYA : BEQ .right
    %WalkLeft()
    RTS
  .right
  %WalkRight()
  RTS
}

Wolfos_MoveAction_CirclePlayer:
{
  ; Get the direction to the player
  JSL Sprite_DirectionToFacePlayer

  ; Check if the player is close
  LDA.b $0E : CMP #$10 : BCS .too_far_y
  LDA.b $0F : CMP #$10 : BCS .too_far_x
    RTS
  .too_far_y

  ; clockwise:  X' = Y, Y' = -X
  LDA.w SprXSpeed, X : PHA
  LDA.w SprYSpeed, X : STA.w SprXSpeed, X
  PLA : EOR #$FF : INC : STA.w SprYSpeed, X

  RTS

  .too_far_x
  LDA.w SprXSpeed, X : EOR #$FF : INC : STA.w SprXSpeed, X
  RTS
}

Wolfos_MoveAction_Dodge:
{
  JSL Sprite_ApplySpeedTowardsPlayer
  JSL Sprite_InvertSpeed_XY
  RTS
}

; =========================================================
; Animation Frame
; 0-2 Attack Forward
; 3-5 Attack Back
; 6-8 Walk Right
; 9-11 Walk Left
; 12-13 Attack Right
; 14-15 Attack Left

Sprite_Wolfos_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY ;Animation Frame
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
  ; Set palette flash modifier
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA.b #02 : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00, $02, $04, $06, $08, $0A, $0C, $10, $14, $18, $1C, $20, $24, $28, $2B, $2F, $32
  .nbr_of_tiles
  db 1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 2, 3, 2, 1
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 8, -8, -8, 8
  dw -8, 8, 8, -8
  dw -8, 8, -8, 8
  dw -8, 8, 8, -8
  dw 8, -8, -8, 8
  dw 8, -8, 8, -8
  dw -8, 8, 8, -8
  dw -8, 8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8
  dw 0
  .y_offsets
  dw 0, -16
  dw 0, -16
  dw 0, -16
  dw 0, -16
  dw 0, -16
  dw 0, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw -16, -16, 0, 0
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw -16, -16, 0, 0
  dw 0, 0, -16, -16
  dw 0, 0, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16
  dw 0
  .chr
  db $E0, $C0
  db $E4, $C4
  db $E6, $C6
  db $E2, $C2
  db $E8, $C8
  db $EA, $CA
  db $A2, $A0, $80, $82
  db $A4, $A6, $86, $84
  db $88, $8A, $A8, $AA
  db $A2, $A0, $80, $82
  db $A4, $A6, $86, $84
  db $88, $8A, $A8, $AA
  db $AC, $AE, $8E, $8C
  db $EC, $EE, $CE
  db $AC, $AE, $8E, $8C
  db $EC, $EE, $CE
  db $CC ; Wolf Mask
  .properties
  db $29, $29
  db $29, $29
  db $29, $29
  db $29, $29
  db $29, $29
  db $29, $29
  db $29, $29, $29, $29
  db $29, $29, $29, $29
  db $29, $29, $29, $29
  db $69, $69, $69, $69
  db $69, $69, $69, $69
  db $69, $69, $69, $69
  db $29, $29, $29, $29
  db $29, $29, $29
  db $69, $69, $69, $69
  db $69, $69, $69
  db $29
}
