; Eon Abyss Sea Zora Elder NPC

Sprite_EonZoraElder_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw EonZoraElder_Idle
  dw EonZoraElder_Surprised
  dw EonZoraElder_WithRod

  EonZoraElder_Idle:
    %PlayAnimation(0,1,10)
    RTS
  EonZoraElder_Surprised:
    %PlayAnimation(2,3,10)
    RTS
  EonZoraElder_WithRod:
    %PlayAnimation(4,4,10)
    RTS
}

; 0-1: Idle
; 2-3: Surprised
;   4: With Rod

Sprite_EonZoraElder_Draw:
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
  db $00, $02, $04, $06
  .nbr_of_tiles
  db 1, 1, 1, 2
  .x_offsets
  dw 0, 8
  dw 0, 8
  dw 0, 8
  dw 0, 8, -4
  .y_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0, 0
  .chr
  db $46, $47
  db $49, $4A
  db $66, $67
  db $69, $6A, $6C
  .properties
  db $39, $39
  db $39, $39
  db $39, $39
  db $39, $39, $39
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02, $02
}
