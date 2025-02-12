; Sick Kid - Bug Net Kid
; Gives the Boots if the player plays the Song of Healing

SickKid_CheckForSongOfHealing:
{
  LDA.b SongFlag : CMP.b #$01 : BNE .no_song
    INC $0D80, X
    INC $02E4
    STZ.b SongFlag
  .no_song
  RTL
}

pushpc

Sprite_CheckIfPlayerPreoccupied = $07F4D0
Sprite_CheckDamageToPlayer_same_layer = $06F154

org $068D7F
SpritePrep_SickKid:
{
  LDA.l $7EF355 : BEQ .no_boots
    LDA.b #$03 : STA $0D80, X
  .no_boots
  INC.w SprBulletproof, X
  RTS
}

org $06B962
BugNetKid_Resting:
{
  JSL Sprite_CheckIfPlayerPreoccupied : BCS .dont_awaken
    JSR Sprite_CheckDamageToPlayer_same_layer : BCC .dont_awaken
      JSL SickKid_CheckForSongOfHealing
        LDA.l $7EF355
        CMP.b #$01 : BCC .no_boots
  .dont_awaken
  RTS

    .no_boots
    LDA.b #$04
    LDY.b #$01
    JSL Sprite_ShowSolicitedMessageIfPlayerFacing
    RTS
}

org $06B9C6
BugNetKid_GrantBugNet:
{
  ; Give Link the Boots
  LDY.b #$4B
  STZ $02E9
  PHX
  JSL Link_ReceiveItem
  PLX
  INC $0D80, X
  STZ $02E4
  RTS
}

pullpc

