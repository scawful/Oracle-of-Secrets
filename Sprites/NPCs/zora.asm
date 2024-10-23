; Sea Zora NPC Handler

Sprite_Zora_Long:
{
  PHB : PHK : PLB
  print "Sea Zora NPC Handler", pc
  ; Check what Zora we are drawing
  REP #$30
  LDA.w ROOM : CMP.w #$0105 : BNE .not_princess
    SEP #$30
    JSR Sprite_ZoraPrincess_Draw
    LDA.b #$01 : STA.w SprMiscG, X      
    JMP +
  .not_princess
  LDA.w WORLDFLAG : AND.w #$00FF : BEQ .eon_draw
    SEP #$30
    JSR Sprite_EonZora_Draw
    LDA.b #$02 : STA.w SprMiscG, X
    JMP +
  .eon_draw
  SEP #$30
  LDA.w SprSubtype, X : BNE .special_zora
    JSR Sprite_Zora_Draw
    JSL Sprite_DrawShadow
    STZ.w SprMiscG, X
    JMP +
  .special_zora
  JSR Sprite_EonZoraElder_Draw
  LDA.b #$03 : STA.w SprMiscG, X
  +
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Zora_Handler
  .SpriteIsNotActive

  PLB
  RTL
}

Sprite_Zora_Prep:
{
  PHB : PHK : PLB
  PLB
  RTL
}

Sprite_Zora_Handler:
{
  LDA.w SprMiscG, X
  CMP.b #$02 : BNE .not_princess
    JSR Sprite_ZoraPrincess_Main
    RTS
  .not_princess

  JSL UseImplicitRegIndexedLocalJumpTable

  dw Sprite_Zora_Main
  dw Sprite_ZoraPrincess_Main
  dw Sprite_EonZora_Main
  dw Sprite_EonZoraElder_Main
}

Sprite_Zora_Main:
{
  JSR Zora_TrackHeadToPlayer
  JSL Sprite_PlayerCantPassThrough

  %ShowSolicitedMessage($01A4)

  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw Zora_Forward
  dw Zora_Right
  dw Zora_Left

  Zora_Forward:
  {
    %PlayAnimation(0,0,10)
    RTS
  }

  Zora_Right:
  {
    %PlayAnimation(1,1,10)
    RTS
  }

  Zora_Left:
  {
    %PlayAnimation(1,1,10)
    RTS
  }
}

Zora_TrackHeadToPlayer:
{
  JSL Sprite_IsToRightOfPlayer : TAY : BEQ .right
    LDA.b #$00 : STA.w SprAction, X
    RTS
  .right
  LDA.b #$01 : STA.w SprAction, X
  RTS
}

Sprite_Zora_Draw:
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
  db $00, $02, $04
  .nbr_of_tiles
  db 1, 1, 1
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  .y_offsets
  dw -8, 0
  dw -8, 0
  dw -8, 0
  .chr
  db $DE, $EE
  db $DC, $EC
  db $DC, $EC
  .properties
  db $35, $35
  db $35, $35
  db $75, $75
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02
}

