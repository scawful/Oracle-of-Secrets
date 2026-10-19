; Approved D3 capture/exit lines. Scene text runs only in player control;
; never enter Module0E from the middle of an indoor/outdoor loading routine.
if !ENABLE_D3_PRISON_SEQUENCE == 1

!D3Prison_ExitMessageLive = $D355

; The staged guard's gravity byte is already the scene-owned elapsed timer.
; C1 holds the pair until text closes; the next hall tick commits capture.
; Native DP=0, X=leader. Preserve full A/X/Y/DB/P, no new saved state.
D3Prison_ShowCaptureTaunt:
{
  PHP
  REP #$20
  PHA
  SEP #$20
  LDA.b #$C1 : STA.l $7E0F80, X
  REP #$20
  LDA.w #!Msg_GuardCaptureTaunt
  JSR D3Prison_ShowSceneMessage
  REP #$20
  PLA
  PLP
  RTL
}

; Called before the ZS overworld entrance/transition handlers. C=1 means
; Module0E took ownership and that caller must return immediately.
; Only an actual CompleteEscape transaction may arm this transient word.
; Native DP=0; preserve full A/X/Y/DB/P except Carry.
D3Prison_TryExitMessage:
{
  PHP
  REP #$20
  PHA
  LDA.l D3Prison_ExitMessage : CMP.w #!D3Prison_ExitMessageLive
  BNE .wait
  SEP #$20
  LDA.l $7E0010 : CMP.b #$09 : BNE .cancel
  LDA.l $7E0011 : BNE .wait
  LDA.l $7E001B : BNE .cancel
  REP #$20
  LDA.l $7E00A0 : CMP.w #$0055 : BNE .cancel
  SEP #$20
  LDA.l CastleAmbushFlags : AND.b #$0F
  CMP.b #!CastleAmbush_HasBeenCaptured|!CastleAmbush_HasEscaped|!CastleAmbush_BladeReclaimed
  BNE .cancel
  LDA.l Sword : CMP.b #$02 : BCC .cancel
  CMP.b #$05 : BCS .cancel
  LDA.l $7E005D : ORA.l $7E02E4 : ORA.l $7E0FFC : ORA.l $7E0FC1
  BNE .wait
  REP #$20
  LDA.w #$0000 : STA.l D3Prison_ExitMessage
  LDA.w #!Msg_PostEscapeFlavor
  JSR D3Prison_ShowSceneMessage
  REP #$20
  PLA
  PLP
  SEC
  RTL
  .cancel
  REP #$20
  LDA.w #$0000 : STA.l D3Prison_ExitMessage
  .wait
  REP #$20
  PLA
  PLP
  CLC
  RTL
}

; M16, A=absolute message ID. Cache the current position, not a previous
; room's hookshot return point. Minimal display does not run sprite AI or
; overwrite the scene's guard slots. Returns M8, other registers unchanged.
D3Prison_ShowSceneMessage:
{
  STA.l $7E1CF0
  LDA.l $7E0022 : STA.l $7E0FC2
  LDA.l $7E0020 : STA.l $7E0FC4
  SEP #$20
  JSL $05FA8E ; Sprite_ShowMessageMinimal
  RTS
}

endif
