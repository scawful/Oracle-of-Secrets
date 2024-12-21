MapleHandler:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Maple_Idle
  dw Maple_HandleDreams

  Maple_Idle:
  {
    %PlayAnimation(0,1,16)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($01B3) : BCC +
      INC.w SprAction, X
    +
    RTS
  }

  Maple_HandleDreams:
  {
    LDA.l $7EF351 : BEQ +
      LDA.b #$02 : STA.l $7EF351
      LDA.b #$1B : STA.w $012F
      STZ.w SprAction, X
    +
    RTS
  }
}
