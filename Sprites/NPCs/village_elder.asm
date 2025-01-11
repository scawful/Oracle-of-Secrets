Sprite_VillageElder_Main:
{
  %PlayAnimation(2,3,16)
  JSL Sprite_PlayerCantPassThrough
  REP #$30
  LDA.l OOSPROG : AND.w #$00FF
  SEP #$30
  AND.b #$10 : BNE .already_met
    %ShowSolicitedMessage($143) : BCC .no_message
      LDA.l OOSPROG : ORA.b #$10 : STA.l OOSPROG
    .no_message
    RTS

  .already_met
  %ShowSolicitedMessage($019)
  RTS
}
