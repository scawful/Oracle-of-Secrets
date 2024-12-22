MapleHandler:
{
  %PlayAnimation(0,1,16)
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Maple_Idle
  dw Maple_FirstResponse
  dw Maple_ExplainHut
  dw Maple_ExplainPendants
  dw Maple_CheckForPendant
  dw Maple_NoNewPendant

; LDA.l $7EF351 : BEQ +
; LDA.b #$02 : STA.l $7EF351
; LDA.b #$1B : STA.w $012F
; STZ.w SprAction, X
; +

  Maple_Idle:
  {
    %ShowSolicitedMessage($01B3) : BCC +
      LDA.w $1CE8 : BEQ .next_response
                    CMP.b #$01 : BNE +
        LDA.b #$02 : STA.w SprAction, X
        RTS
      .next_response
      INC.w SprAction, X
    +
    RTS
  }

  Maple_FirstResponse:
  {
    %ShowUnconditionalMessage($01B4)
    LDA.w $1CE8 : BEQ .check_for_pendant
                  CMP.b #$01 : BNE .another_time
      LDA.b #$03 : STA.w SprAction, X
      RTS
    .check_for_pendant
    LDA.b #$04 : STA.w SprAction, X
    RTS

    .another_time
    STZ.w SprAction, X
    RTS
  }

  Maple_ExplainHut:
  {
    %ShowUnconditionalMessage($01B5)
    STZ.w SprAction, X
    RTS
  }

  Maple_ExplainPendants:
  {
    %ShowUnconditionalMessage($01B8)
    STZ.w SprAction, X
    RTS
  }

  Maple_CheckForPendant:
  {
    ; Check for pendant
    %ShowUnconditionalMessage($01B6)
    RTS
  }

  Maple_NoNewPendant:
  {
    %ShowUnconditionalMessage($01B7)
    STZ.w SprAction, X
    RTS
  }
}

Sprite_PutLinkToSleep:
{
  PHX
  LDA.b #$16 : STA.b $5D ; Set Link to sleeping
  LDA.b #$20 : JSL AncillaAdd_Blanket
  LDA.b $20 : CLC : ADC.b #$04 : STA.w $0BFA,X
  LDA.b $21 : STA.w $0C0E,X
  LDA.b $22 : SEC : SBC.b #$08 : STA.w $0C04,X
  LDA.b $23 : STA.w $0C18,X
  JSL PaletteFilter_StartBlindingWhite
  JSL ApplyPaletteFilter
  PLX
  RTS
}

Link_HandleDreams:
{
  LDA.w CurrentDream
  JSL JumpTableLocal

  dw Dream_Wisdom
  dw Dream_Power
  dw Dream_Courage

  Dream_Wisdom:
  {
    LDA.l DREAMS : ORA.b #%00000001 : STA.l DREAMS
    LDX.b #$00
    JSR Link_FallIntoDungeon
    RTS
  }

  Dream_Power:
  {
    LDA.l DREAMS : ORA.b #%00000010 : STA.l DREAMS
    LDX.b #$01
    JSR Link_FallIntoDungeon
    RTS
  }

  Dream_Courage:
  {
    LDA.l DREAMS : ORA.b #%00000100 : STA.l DREAMS
    RTS
  }
}

; Takes X as argument for the entrance ID
Link_FallIntoDungeon:
{
  LDA.w .entrance, X
  STA.w $010E
  STZ.w $010F

  LDA.b #$20 : STA.b $5C
  LDA.b #$01 : STA.b LinkState
  LDA.b #$11 : STA.b $10
  STZ.b $11 : STZ.b $B0

  RTS
  .entrance
  db $78 ; 0x00 - Deku Dream
  db $79 ; 0x01 - Castle Dream
  db $7A ; 0x02 -
  db $81 ; 0x03
}
