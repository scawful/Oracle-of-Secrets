Sprite_VillageElder_Main:
{
  %PlayAnimation(2,3,16)
  JSL Sprite_PlayerCantPassThrough
  REP #$30
  LDA.l MAPICON : AND.w #$00FF
  SEP #$30
  CMP.b #$02 : BCS .already_met
    %ShowSolicitedMessage($143) : BCC .no_message
      LDA.b #$02 : STA.l $7EF3C7
    .no_message
    RTS

  .already_met
  %ShowSolicitedMessage($019)
  RTS
}
