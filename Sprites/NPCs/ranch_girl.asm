; =========================================================
; Ranch Girl (Chicken Easter Egg Sprite)
; Gives Link the Ocarina

org $05FA8E
Sprite_ShowMessageMinimal:

org $1AF92C
SpriteDraw_RaceGameLady:

org $1AF954
Sprite_CheckIfActive_Bank1A:

pullpc

RanchGirl:
{
  ; Play the dialogue box 
  LDA.b #$7D ; MESSAGE 017D
  STA.w $1CF0

  LDA.b #$01
  STA.w $1CF1

  JSL Sprite_ShowMessageMinimal

  ; Give Link the Ocarina 
  LDY #$14 
  ; Clear the item receipt ID 
  STZ $02E9
  PHX
  JSL Link_ReceiveItem
  PLX

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
    #_1AFED5: STA.w $0DE0,X

    #_1AFED8: JSL SpriteDraw_RaceGameLady
    #_1AFEDC: JSR Sprite_CheckIfActive_Bank1A

    #_1AFEDF: LDA.w $0DF0,X
    #_1AFEE2: CMP.b #$01
    #_1AFEE4: BNE .no_message

    JSL RanchGirl

  .no_message
    #_1AFEF4: LDA.b $1A
    #_1AFEF6: LSR A
    #_1AFEF7: LSR A
    #_1AFEF8: LSR A
    #_1AFEF9: LSR A
    #_1AFEFA: AND.b #$01
    #_1AFEFC: STA.w $0DC0,X

    #_1AFEFF: RTS
}

warnpc $01AFEFF