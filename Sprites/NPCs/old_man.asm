; =========================================================
; Old Man Follower Sprite 
; 

LoadFollowerGraphics = $00D423

print "OldMan_ExpandedPrep ", pc
; Old man sprite wont spawn in his home room 
; if you have the follower 
OldMan_ExpandedPrep:
{
  ; ROOM 00E4
  LDA.l $7EF3CC : CMP.b #$04 : BEQ .not_home
    LDA.b $A0 : CMP.b #$E4 : BNE .not_home
      CLC 
      RTL
  .not_home
  SEC
  RTL
}

; Old man gives link the "shovel" 
; Now the goldstar hookshot upgrade
org $1EE9FF
  LDY.b #$13 ; ITEMGET 1A
  STZ.w $02E9

; FindEntrance
org $1BBD3C
  CMP.w #$04

; Underworld_LoadEntrance
org $02D98B
  CMP.w #$02

; Module05_LoadFile
; Check for goldstar instead of mirror for mountain spawn option
org $0281E2
  LDA.l $7EF342 : CMP.b #$02

org $1EE8F1
SpritePrep_OldMan:
{
  PHB
  PHK
  PLB
  JSR .main
  PLB
  RTL

  .main
  INC.w $0BA0,X

  
  ; LDA.b $A0 : CMP.b #$E4 ; ROOM 00E4
  JSL OldMan_ExpandedPrep : BCS .not_home
    LDA.b #$02 : STA.w $0E80,X
    RTS

  .not_home
  LDA.l $7EF3CC : CMP.b #$00 : BNE .dont_spawn

  ; Check for lv2 hookshot instead of mirror
  LDA.l $7EF342 : CMP.b #$02 : BNE .spawn

  STZ.w $0DD0,X

  .spawn
  ; FOLLOWER 04
  LDA.b #$04 : STA.l $7EF3CC

  PHX
  JSL LoadFollowerGraphics
  PLX

  LDA.b #$00
  STA.l $7EF3CC

  RTS
  .dont_spawn
  STZ.w $0DD0,X

  PHX
  JSL LoadFollowerGraphics
  PLX

  RTS
}