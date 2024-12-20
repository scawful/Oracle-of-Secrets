
pushpc
; BottleVendor_OutOfStock
org $05EAC2 : JSL BottleVendor_MilkHandler
pullpc

BottleVendor_MilkHandler:
{
  LDA.l $7EF34C : BNE +
    LDA.b #$D4
    JSL Sprite_ShowSolicitedMessage
    RTL
  +
  JSR BottleVendor_SellMilk
  RTL
}

BottleVendor_SellMilk:
{
  LDA.w SprMiscA, X
  JSL JumpTableLocal

  dw BottleVendor_Idle
  dw BottleVendor_BoughtMilkBottle
  dw BottleVendor_NotEnoughRupees
  dw BottleVendor_HandlePlayerResponse
  dw BottleVendor_ComeBackAgain
  dw BottleVendor_NoAvailableBottles

  BottleVendor_Idle:
  {
    %PlayAnimation(0,1,16)
    JSL Sprite_PlayerCantPassThrough

    %ShowSolicitedMessage($0187) : BCC .didnt_talk
      LDA.b #$03 : STA.w SprMiscA, X
    .didnt_talk
    RTS
  }

  BottleVendor_BoughtMilkBottle:
  {
    REP #$20
    LDA.l $7EF360 : CMP.w #$1E ; 30 rupees
    SEP #$30
    BCC .not_enough_rupees

      LDA.l $7EF35C : CMP.b #$02 : BEQ .bottle1_available
      LDA.l $7EF35D : CMP.b #$02 : BEQ .bottle2_available
      LDA.l $7EF35E : CMP.b #$02 : BEQ .bottle3_available
      LDA.l $7EF35F : CMP.b #$02 : BEQ .bottle4_available
        LDA.b #$05 : STA.w SprMiscA, X
        RTS

      .bottle1_available
      LDA.b #$0A : STA.l $7EF35C : JMP .finish_storage
      .bottle2_available
      LDA.b #$0A : STA.l $7EF35D : JMP .finish_storage
      .bottle3_available
      LDA.b #$0A : STA.l $7EF35E : JMP .finish_storage
      .bottle4_available
      LDA.b #$0A : STA.l $7EF35F
      .finish_storage
      REP #$20
      LDA.l $7EF360
      SEC : SBC.w #$1E ; Subtract 30 rupees
      STA.l $7EF360
      SEP #$30

      %ShowUnconditionalMessage($0188) ; Thank you!
      STZ.w SprMiscA, X
      RTS
    .not_enough_rupees
    LDA.b #$02 : STA.w SprMiscA, X
    RTS
  }

  BottleVendor_NotEnoughRupees:
  {
    %ShowUnconditionalMessage($0189) ; You don't have enough rupees!
    STZ.w SprMiscA, X
    RTS
  }

  BottleVendor_HandlePlayerResponse:
  {
    LDA $1CE8 : BEQ .player_said_yes
      LDA.b #$04 : STA.w SprMiscA, X
      RTS
    .player_said_yes
    LDA.b #$01 : STA.w SprMiscA, X
    RTS
  }

  BottleVendor_ComeBackAgain:
  {
    %ShowUnconditionalMessage($018B) ; Come back again!
    STZ.w SprMiscA, X
    RTS
  }

  BottleVendor_NoAvailableBottles:
  {
    %ShowUnconditionalMessage($033)
    STZ.w SprMiscA, X
    SEC
    RTS
  }
}
