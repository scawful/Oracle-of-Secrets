; Vampire Bat Mini boss
; Sprite 0x11 Custom Keese Subtype 02

Sprite_VampireBat_Main:
{
  JSL Sprite_CheckDamageToPlayer
  JSL Sprite_CheckDamageFromPlayer
  JSL Sprite_DamageFlash_Long
  JSL Sprite_BounceFromTileCollision

  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw VampireBat_Idle
  dw VampireBat_Ascend
  dw VampireBat_FlyAround
  dw VampireBat_Descend

  VampireBat_Idle:
  {
    STZ.w SprFrame, X
    JSL GetDistance8bit_Long : CMP.b #$24 : BCS +
      INC.w SprAction, X
      LDA.b #$40 : STA.w SprTimerA, X
    +
    RTS
  }

  VampireBat_Ascend:
  {
    %PlayAnimation(1,2,5)
    LDA.w SprTimerA, X : AND.b #$02 : BNE +
      LDA.w SprHeight, X : CMP.b #$50 : BEQ +
        INC.w SprHeight, X
    +

    LDA.w SprTimerA, X : BNE +
      INC.w SprAction, X
      LDA.b #$50 : STA.w SprTimerC, X
      JSL GetRandomInt : AND.b #$3F : BNE +
        JSL Sprite_SpawnFireKeese
    +
    RTS
  }

  VampireBat_FlyAround:
  {
    %PlayAnimation(1,2,10)
    JSL Sprite_ProjectSpeedTowardsPlayer
    JSL GetRandomInt : AND.b #$1F : BNE +
      JSL Sprite_SelectNewDirection
    +
    JSL Sprite_Move

    LDA.w SprTimerC, X : BNE +
      INC.w SprAction, X
      LDA.b #$40 : STA.w SprTimerC, X
    +

    RTS
  }

  VampireBat_Descend:
  {
    %PlayAnimation(3,4,5)
    LDA.w SprHeight, X : BEQ +
      DEC.w SprHeight, X
    +
    JSL Sprite_ProjectSpeedTowardsPlayer
    JSL Sprite_Move

    JSL GetRandomInt : AND.b #$0F : BNE +
      JSL Sprite_Twinrova_FireAttack
    +

    LDA.w SprTimerC, X : BNE +
      STZ.w SprAction, X
    +
    RTS
  }
}

Sprite_SpawnFireKeese:
{
  LDA.b #$11
  JSL Sprite_SpawnDynamically : BMI .spawn_failed
    LDA.b #$01 : STA.w SprSubtype, Y ; Fire Keese
    JSL Sprite_SetSpawnedCoords
  .spawn_failed
  RTL
}

Sprite_SpawnIceKeese:
{
  LDA.b #$11
  JSL Sprite_SpawnDynamically : BMI +
    JSL Sprite_SetSpawnedCoords
  +
  RTL
}

Sprite_VampireBat_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
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
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS
  .start_index
  db $00, $04, $0A, $12, $18
  .nbr_of_tiles
  db 3, 5, 7, 5, 7
  .x_offsets
  dw -8, -8, 8, 8
  dw -8, -8, -24, 8, 8, 24
  dw -8, -8, -24, -24, 8, 8, 24, 24
  dw -8, -8, -24, 8, 8, 24
  dw -8, -8, -24, 8, 8, 24, 0, 8
  .y_offsets
  dw -16, 0, -16, 0
  dw 0, -16, 0, 0, -16, 0
  dw -16, 0, 0, -16, -16, 0, 0, -16
  dw 0, -16, 0, 0, -16, 0
  dw 0, -16, 0, 0, -16, 0, 0, 0
  .chr
  db $8E, $AE, $8E, $AE
  db $A8, $88, $A6, $A8, $88, $A6
  db $8C, $AC, $AA, $8A, $8C, $AC, $AA, $8A
  db $A8, $88, $A6, $A8, $88, $A6
  db $A8, $88, $A6, $A8, $88, $A6, $87, $87
  .properties
  db $33, $33, $73, $73
  db $33, $33, $33, $73, $73, $73
  db $33, $33, $33, $33, $73, $73, $73, $73
  db $33, $33, $33, $73, $73, $73
  db $33, $33, $33, $73, $73, $73, $33, $73
  .sizes
  db $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02, $00, $00

}
