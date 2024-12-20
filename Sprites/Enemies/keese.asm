; Keese and Vampire Bat Sprite
; Subtype:
;  00 - Ice
;  01 - Fire
;  02 - Vampire Bat

!SPRID              = $11 ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 10  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
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
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 00  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_Keese_Prep, Sprite_Keese_Long)

Sprite_Keese_Long:
{
  PHB : PHK : PLB
  LDA.w SprSubtype, X : CMP.b #$02 : BEQ +
    JSR Sprite_Keese_Draw
    JSL Sprite_DrawShadow
    JSL Sprite_CheckActive : BCC .SpriteIsNotActive
      JSR Sprite_Keese_Main
    .SpriteIsNotActive
    JMP ++
  +
  JSR Sprite_VampireBat_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC ++
    JSR Sprite_VampireBat_Main
  ++
  PLB
  RTL
}

Sprite_Keese_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X
  LDA.w SprSubtype, X : CMP.b #$02 : BNE +
    LDA.b #$20 : STA.w SprHealth, X
    BRA ++
  +
  LDA.b #$02 : STA.w SprNbrOAM, X
  ++
  PLB
  RTL
}

Sprite_Keese_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw Keese_Idle
  dw Keese_FlyAround

  Keese_Idle:
  {
    STZ.w SprFrame, X
    ; Wait til the player is nearby then fly around
    JSL GetDistance8bit_Long : CMP.b #$20 : BCS +
      INC.w SprAction, X
      JSL GetRandomInt
      STA.w SprTimerA, X
    +
    RTS
  }

  Keese_FlyAround:
  {
    %PlayAnimation(0,5,10)
    JSL Sprite_CheckDamageToPlayer
    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_DamageFlash_Long
    JSL Sprite_BounceFromTileCollision

    JSL GetRandomInt : AND.b #$1F : BNE +
      LDA.w SprSubtype, X : BEQ ++
        JSL Sprite_Twinrova_FireAttack
        JMP +
      ++
      ; Ice Attack
    +

    LDA.w SprTimerA, X : AND.b #$10 : BNE +
      JSL Sprite_ProjectSpeedTowardsPlayer
    +

    JSL Sprite_SelectNewDirection
    JSL Sprite_Move

    LDA.w SprTimerA, X : BNE +
      STZ.w SprAction, X
    +
    RTS
  }
}

Sprite_Keese_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
  LDA .start_index, Y : STA $06
  LDA.w SprFlash, X : STA $08
  LDA.w SprSubtype, X : CMP.b #$01 : BNE +
    LDA.b #$0A : EOR $08 : STA $08
  +

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
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00, $01, $03, $04, $06, $08
  .nbr_of_tiles
  db 0, 1, 0, 1, 1, 0
  .x_offsets
  dw 0
  dw -4, 4
  dw 0
  dw -4, 4
  dw -4, 4
  dw 0
  .y_offsets
  dw 0
  dw 0, 0
  dw 0
  dw 0, 0
  dw 0, 0
  dw 0
  .chr
  db $80
  db $A2, $A2
  db $82
  db $84, $84
  db $A4, $A4
  db $A0
  .properties
  db $35
  db $35, $75
  db $35
  db $35, $75
  db $35, $75
  db $35
  .sizes
  db $02
  db $02, $02
  db $02
  db $02, $02
  db $02, $02
  db $02
}
