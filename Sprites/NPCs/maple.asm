MapleHandler:
{
  %PlayAnimation(0,1,16)
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Maple_Idle
  dw Maple_HandleFirstResponse
  dw Maple_DreamOrExplain
  dw Maple_ExplainHut
  dw Maple_ExplainPendants
  dw Maple_CheckForPendant
  dw Maple_NoNewPendant
  dw Maple_PutLinkToSleep
  dw Maple_HandleDreams

; LDA.l $7EF351 : BEQ +
; LDA.b #$02 : STA.l $7EF351
; LDA.b #$1B : STA.w $012F
; STZ.w SprAction, X
; +

  Maple_Idle:
  {
    %ShowSolicitedMessage($01B3) : BCC +
      INC.w SprAction, X
    +
    RTS
  }

  Maple_HandleFirstResponse:
  {
    LDA.w $1CE8 : CMP.b #$02 : BNE +
      STZ.w SprAction, X
      RTS
    +
    CMP.b #$01 : BNE .next_response
      LDA.b #$03 : STA.w SprAction, X
      RTS
    .next_response
    INC.w SprAction, X
    RTS
  }

  Maple_DreamOrExplain:
  {
    %ShowUnconditionalMessage($01B4)
    LDA.w $1CE8 : BEQ .check_for_pendant
                  CMP.b #$01 : BNE .another_time
      LDA.b #$04 : STA.w SprAction, X
      RTS
    .check_for_pendant
    LDA.b #$05 : STA.w SprAction, X
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
    print pc
    ; Check for pendant
    LDA.l PENDANTS : AND.b #$04 : BNE .courage
    LDA.l PENDANTS : AND.b #$02 : BNE .power
    LDA.l PENDANTS : AND.b #$01 : BNE .wisdom
                     JMP .none
    .courage
    LDA.l Dreams : AND.b #$04 : BNE .power
      LDA.b #$02 : STA.w CurrentDream : BRA +
    .power
    LDA.l Dreams : AND.b #$02 : BNE .wisdom
      LDA.b #$01 : STA.w CurrentDream : BRA +
    .wisdom
    LDA.l Dreams : AND.b #$01 : BNE .none
      STZ.w CurrentDream
    +
    %ShowUnconditionalMessage($01B6)
    LDA.b #$07 : STA.w SprAction, X
    LDA.b #$40 : STA.w SprTimerA, X
    RTS
    .none
    INC.w SprAction, X
    RTS
  }

  Maple_NoNewPendant:
  {
    %ShowUnconditionalMessage($01B7)
    STZ.w SprAction, X
    RTS
  }

  Maple_PutLinkToSleep:
  {
    JSR Sprite_PutLinkToSleep
    INC.w SprAction, X
    RTS
  }

  Maple_HandleDreams:
  {
    LDA.w SprTimerA, X : BNE +
      JSR Link_HandleDreams
    +
    RTS
  }
}

Sprite_PutLinkToSleep:
{
  PHX
  LDA.b $20 : SEC : SBC.b #$14 : STA.b $20
  LDA.b $22 : CLC : ADC.b #$18 : STA.b $22

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
    LDA.l Dreams : ORA.b #%00000001 : STA.l Dreams
    LDX.b #$00
    JSR Link_WarpToRoom
    RTS
  }

  Dream_Power:
  {
    LDA.l Dreams : ORA.b #%00000010 : STA.l Dreams
    LDX.b #$01
    JSR Link_WarpToRoom
    RTS
  }

  Dream_Courage:
  {
    LDA.l Dreams : ORA.b #%00000100 : STA.l Dreams
    LDX.b #$02
    JSR Link_WarpToRoom
    RTS
  }
}

Link_WarpToRoom:
{
  LDA.b #$20 : STA.b $5C
  LDA.b #$01 : STA.b LinkState

  LDA.b #$15 : STA.b $11
  LDA.b $A0  : STA.b $A2
  STZ.b $A1
  LDA.w .room, X : STA.b $A0
  ; STA.l $7EC000
  RTS

  .room
  db $61
  db $00
  db $31
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

pushpc
org $068C9C
db $0F
pullpc
