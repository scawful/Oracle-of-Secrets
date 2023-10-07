org $07F4D0
Sprite_CheckIfPlayerPreoccupied:

org $06F154
Sprite_CheckDamageToPlayer_same_layer:

org $06B962
BugNetKid_Resting:
{
    JSL Sprite_CheckIfPlayerPreoccupied : BCS .dont_awaken
    
    JSR Sprite_CheckDamageToPlayer_same_layer : BCC .dont_awaken
    
    LDA.l $7EF34C
    
    CMP.b #$01 : BCC .no_ocarina
    
    INC $0D80, X
    
    INC $02E4

.dont_awaken

    RTS

.no_ocarina

    ; "... Do you have a bottle to keep a bug in? ... I see. You don't..."
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