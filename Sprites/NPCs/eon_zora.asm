; Eon Abyss Sea Zora NPC

Sprite_EonZora_Main:
{
  JSR EonZora_HandleDialogue
  JSR EonZora_Walk

  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision

  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw EonZora_Forward
  dw EonZora_Left
  dw EonZora_Right
  dw EonZora_Back

  EonZora_Forward:
    %PlayAnimation(0,1,10)
    RTS
  EonZora_Left:
    %PlayAnimation(2,3,10)
    RTS
  EonZora_Right:
    %PlayAnimation(4,5,10)
    RTS
  EonZora_Back:
    %PlayAnimation(6,7,10)
    RTS
}

EonZora_Walk:
{
  LDA.w SprTimerA, X : BNE +
    JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X : TAY
    LDA.w .speed_x, Y : STA.w SprXSpeed, X
    LDA.w .speed_y, Y : STA.w SprYSpeed, X
    LDA.b #$6A : STA.w SprTimerA, X
  +
  RTS

  .speed_x
  db 0, -4, 4, 0
  .speed_y
  db 4, 0, 0, -4
}

EonZora_HandleDialogue:
{
  LDA.w AreaIndex : CMP.b #$63 : BNE .not_wisdom
    %ShowSolicitedMessage($01AC)
    JMP ++
  .not_wisdom
  CMP.b #$5B : BNE .not_power
    %ShowSolicitedMessage($01AB)
    JMP ++
  .not_power
  CMP.b #$40 : BNE .not_pyramid
    %ShowSolicitedMessage($01AA)
    JMP ++
  .not_pyramid
  CMP.b #$70 : BNE .not_underwater
    %ShowSolicitedMessage($01AD)
    JMP ++
  .not_underwater
  CMP.b #$42 : BNE .not_portal
    %ShowSolicitedMessage($01AF)
    JMP ++
  .not_portal
  %ShowSolicitedMessage($01AE) : BCC .no_talk
    JSL GetRandomInt : AND.b #$06 : STA.l FOUNDRINGS
  .no_talk
  ++
  RTS
}

; 0-1 : Forward
; 2-3 : Left
; 4-5 : Right
; 6-7 : Back

Sprite_EonZora_Draw:
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
  db $00, $02, $04, $06, $08, $0A, $0C, $0D
  .nbr_of_tiles
  db 1, 1, 1, 1, 1, 1, 0, 0
  .x_offsets
  dw 0, 16
  dw 0, -16
  dw 0, 8
  dw 0, 8
  dw 0, -8
  dw 0, -8
  dw 0
  dw 0
  .y_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0
  dw 0
  .chr
  db $60, $62
  db $60, $62
  db $40, $41
  db $43, $44
  db $40, $41
  db $43, $44
  db $64
  db $64
  .properties
  db $39, $39
  db $79, $79
  db $39, $39
  db $39, $39
  db $79, $79
  db $79, $79
  db $39
  db $79
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02
  db $02
}
