Sprite_HyruleDream_Prep:
{
  LDA.b ROOM : CMP.b #$51 : BEQ .king
               CMP.b #$60 : BEQ .soldier
               LDA.b #$00 : JMP .done
  .king
  LDA.b #$01 : JMP .done
  .soldier
  LDA.b #$02
  .done
  STA.w SprAction, X
  RTS
}

Sprite_HyruleDream_Main:
{
  %SpriteJumpTable(Zelda_Idle,
                   King_Idle,
                   Soldier_Idle)

  Zelda_Idle:
  {
    STZ.w SprFrame, X
    RTS
  }

  King_Idle:
  {
    LDA.b #$01 : STA.w SprFrame, X
    RTS
  }

  Soldier_Idle:
  {
    LDA.b #$02 : STA.w SprFrame, X
    RTS
  }
}

Sprite_HyruleDream_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
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
  db $00, $03, $07
  .nbr_of_tiles
  db 2, 3, 2
  .x_offsets
  dw -8, 8, 0
  dw -8, 8, -8, 8
  dw -4, 4, 0
  .y_offsets
  dw -4, -4, -14
  dw -16, -16, 0, 0
  dw -4, -4, -14
  .chr
  db $A8, $A8, $84
  db $8E, $8E, $AE, $AE
  db $A4, $A4, $A6
  .properties
  db $39, $79, $39
  db $39, $79, $39, $79
  db $39, $79, $39
  .sizes
  db $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02
}
