; =========================================================
; Ranch Girl (Chicken Easter Egg Sprite)
; Gives Link the Ocarina

pushpc
org $05FA8E
Sprite_ShowMessageMinimal:

org $1AF92C
SpriteDraw_RaceGameLady:

org $1AF954
Sprite_CheckIfActive_Bank1A:

pullpc

RanchGirl_Message:
{
  LDA $7EF34C : CMP.b #$01 : BCS .has_ocarina
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
  #_1AFEF4: LDA.b $1A
  #_1AFEF6: LSR A
  #_1AFEF7: LSR A
  #_1AFEF8: LSR A
  #_1AFEF9: LSR A
  #_1AFEFA: AND.b #$01
  #_1AFEFC: STA.w $0DC0,X

  RTL
}



pushpc

org $01AFECF
ChickenLady:
{
  #_1AFECF: JSR .main

  #_1AFED2: RTL

  .main
  #_1AFED3: LDA.b #$01
  #_1AFED5: STA.w SprMiscC,X

  #_1AFED8: JSL SpriteDraw_RaceGameLady
  #_1AFEDC: JSR Sprite_CheckIfActive_Bank1A

  #_1AFEDF: LDA.w SprTimerA,X
  #_1AFEE2: CMP.b #$01
  #_1AFEE4: BNE .no_message

  JSL RanchGirl_Message

  .no_message
  JSL RanchGirl_TeachSong
  .return
  #_1AFEFF: RTS
}

assert pc() <= $01AFEFF
pullpc
