; Eon Abyss Leever

pushpc

Sprite_71_Leever =  $06CBA2

org $069365
  dw Sprite_71_Leever_Alt

; UNREACHABLE_06A540
org $06A540
Sprite_71_Leever_Alt:
{
  LDA.w $0FFF : BEQ +
    JSL Sprite_Leever_Long
    JMP ++
  +
  JSR Sprite_71_Leever
  ++
  RTS
}
assert pc() <= $06A5C0

pullpc

Sprite_Leever_Long:
{
  PHB : PHK : PLB
  LDA.w SprAction, X : BEQ +
    JSR Sprite_Leever_Draw
  +
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Leever_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Leever_Move:
{
  JSL Sprite_ApplySpeedTowardsPlayer
  JSL Sprite_Move
  RTS
}

Sprite_Leever_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw Leever_Underground
  dw Leever_Emerge
  dw Leever_Attack
  dw Leever_Dig

  Leever_Underground:
  {
    LDA.w SprTimerA, X : BNE +
      LDA.b #$40 : STA.w SprTimerA, X
      INC.w SprAction, X
    +
    LDA.b #$10
    JSR Sprite_Leever_Move
    RTS
  }

  Leever_Emerge:
  {
    %PlayAnimBackwards(3, 2, 10)
    LDA.w SprTimerA, X : BNE +
      JSL GetRandomInt
      AND.b #$3F
      ADC.b #$A0
      STA.w $0DF0,X
      INC.w SprAction, X
      STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    +
    RTS
  }

  Leever_Attack:
  {
    %PlayAnimation(0, 1, 10)
    LDA.w SprTimerA, X : BNE +
      LDA.b #$7F : STA.w SprTimerA, X
      INC.w SprAction, X
    +
    PHX
    JSL Sprite_CheckIfRecoiling
    JSL Sprite_CheckDamageToPlayerSameLayer
    JSL Sprite_CheckDamageFromPlayer
    PLX
    LDA.b #$0C
    JSR Sprite_Leever_Move
    RTS
  }

  Leever_Dig:
  {
    %PlayAnimation(2, 3, 10)
    LDA.w SprTimerA, X : BNE +
      JSL GetRandomInt
      AND.b #$1F
      ADC.b #$40
      STA.w $0DF0,X
      STZ.w SprAction, X
    +
    LDA.b #$08
    JSR Sprite_Leever_Move
    RTS
  }
}

Sprite_Leever_Draw:
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

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00, $01, $02, $03
  .nbr_of_tiles
  db 0, 0, 0, 0
  .x_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  .y_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  .chr
  db $E0
  db $E2
  db $C2
  db $C0
  .properties
  db $33
  db $33
  db $33
  db $33
  .sizes
  db $02
  db $02
  db $02
  db $02
}
