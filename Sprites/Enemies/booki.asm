; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_Booki
!NbrTiles           = 02  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
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
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_Booki_Prep, Sprite_Booki_Long)

Sprite_Booki_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Booki_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Booki_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Booki_Prep:
{
  PHB : PHK : PLB
  LDA.l Sword : DEC A : TAY
  LDA.w .health, Y : STA.w SprHealth, X
  STZ.w SprMiscB, X
  PLB
  RTL

  .health
    db $04, $08, $10, $18
}

Sprite_Booki_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw StalkPlayer
  dw HideFromPlayer
  dw HiddenFromPlayer
  dw ApproachPlayer

  StalkPlayer:
  {
    %PlayAnimation(0,1,16)
    JSR Sprite_Booki_Move
    RTS
  }

  HideFromPlayer:
  {
    %PlayAnimation(0,4,16)
    LDA.w SprTimerA, X : BNE +
      INC.w SprAction, X
    +
    RTS
  }

  HiddenFromPlayer:
  {
    %PlayAnimation(4,4,16)
    JSR Sprite_Booki_Move
    JSL GetRandomInt : AND.b #$03 : BEQ +
      INC.w SprAction, X
    +
    RTS
  }

  ApproachPlayer:
  {
    %PlayAnimation(5,9,16)
    JSR Sprite_Booki_Move
    RTS
  }
}

Sprite_Booki_Move:
{
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_PlayerCantPassThrough
  JSL Sprite_DamageFlash_Long
  JSL Sprite_CheckIfRecoiling

  JSL Sprite_IsToRightOfPlayer : CPY.b #$01 : BNE .ToRight
    LDA.b #$01 : STA.w SprMiscC, X
    JMP .Continue
  .ToRight
  STZ.w SprMiscC, X
  .Continue

  JSL Sprite_CheckDamageToPlayer
  JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
    LDA.b #$01 : STA.w SprMiscB, X
  .no_damage

  LDA.w SprMiscB, X
  JSL JumpTableLocal

  dw SlowFloat
  dw FloatAway

  SlowFloat:
  {
    LDY #$04
    JSL GetRandomInt : AND.b #$04
    JSL Sprite_FloatTowardPlayer

    PHX
    JSL Sprite_DirectionToFacePlayer

    LDA.b $0E : CMP.b #$1A : BCS .NotTooClose
    LDA.b $0F : CMP.b #$1A : BCS .NotTooClose
      LDA.b #$01 : STA.w SprMiscB, X
      LDA.b #$20 : STA.w SprTimerA, X
      %GotoAction(1)
    .NotTooClose
    PLX

    RTS
  }

  FloatAway:
  {
    JSL GetRandomInt : AND.b #$04
    JSL Sprite_FloatAwayFromPlayer

    PHX
    JSL Sprite_DirectionToFacePlayer
    LDA.b $0E : CMP.b #$1B : BCC .NotTooClose
    LDA.b $0F : CMP.b #$1B : BCC .NotTooClose
      LDA.b #$00 : STA.w SprMiscB, X
      %GotoAction(0)
    .NotTooClose
    PLX

    RTS
  }
}


; =========================================================

Sprite_Booki_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprGfx, X : CLC : ADC.w SprFrame, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

  LDA.w SprFlash, X : STA $08
  LDA.w SprMiscC, X : STA $09

  PHX
  LDX .nbr_of_tiles, Y ; amount of tiles -1
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
  LDA $02 : STA ($90), Y
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

  LDA.b $09 : BEQ .ToRight
  LDA.b #$29 : JMP .Prop
  .ToRight
  LDA.b #$69
  .Prop
  ORA $08 : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS


  ; =========================================================

  .start_index
  db $00, $01, $02, $03, $04, $05, $06, $07, $08, $09
  .nbr_of_tiles
  db 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  .chr
  db $0E
  db $0C
  db $0A
  db $2C
  db $2E
  db $2E
  db $0A
  db $2C
  db $0C
  db $0E
}
