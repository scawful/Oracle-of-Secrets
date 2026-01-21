; =========================================================
; Ranch Girl (Chicken Easter Egg Sprite)
; Gives Link the Ocarina

Sprite_ShowMessageMinimal = $05FA8E
SpriteDraw_RaceGameLady =  $1AF92C
Sprite_CheckIfActive_Bank1A = $1AF954

RanchGirl_Message:
{
  LDA $7EF34C : CMP.b #$01 : BCS .has_ocarina
    ; Set journal flag: Ranch Girl transformed back (curse broken)
    LDA.l SideQuestProg2 : ORA.b #$01 : STA.l SideQuestProg2
    %ShowUnconditionalMessage($017D)
    LDA #$01 : STA.w SprMiscD, X
    RTL
  .has_ocarina
  %ShowUnconditionalMessage($010E)
  RTL
}

RanchGirl_TeachSong:
{
  LDA.w SprMiscD, X : CMP.b #$01 : BNE .not_started
  LDA $10 : CMP.b #$0E : BEQ .running_dialog
  LDA $7EF34C : CMP.b #$01 : BCS .has_song

  ; Play the song of storms
  LDA.b #$2F
  STA.w $0CF8
  JSL $0DBB67 ;  Link_CalculateSFXPan
  ORA.w $0CF8
  STA $012E ; Play the song learned sound

  ; Give Link the Ocarina
  LDY #$14
  ; Clear the item receipt ID
  STZ $02E9
  PHX
  JSL Link_ReceiveItem
  PLX

  LDA #$01 : STA $7EF34C ; The item gives 02 by default, so decrement that for now

  .not_started
  .running_dialog
  .has_song
  LDA.b $1A : LSR #4 : AND.b #$01 : STA.w $0DC0,X

  RTL
}

pushpc

org $1AFECF
ChickenLady:
{
  JSR .main
  RTL

  .main
  LDA.b #$01 : STA.w SprMiscC, X

  JSL SpriteDraw_RaceGameLady
  JSR Sprite_CheckIfActive_Bank1A

  LDA.w SprTimerA, X : CMP.b #$01 : BNE .no_message
    JSL RanchGirl_Message
  .no_message
  JSL RanchGirl_TeachSong
  .return
  RTS
}

assert pc() <= $1AFEFF
pullpc
