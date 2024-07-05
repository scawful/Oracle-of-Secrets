; =========================================================
; Old Man Follower Sprite 
; 

LoadFollowerGraphics = $00D423

; org $099F99
; #Follower_AIVectors:
;   #_099F99: dw Follower_BasicMover   ; 0x01 - Zelda (Impa)
;   #_099F9B: dw Follower_OldMan       ; 0x02 - Old man that stops following you
;   #_099F9D: dw Follower_OldManUnused ; 0x03 - Unused old man
;   #_099F9F: dw Follower_OldMan       ; 0x04 - Normal old man
;   #_099FA1: dw Follower_Telepathy    ; 0x05 - Zelda rescue telepathy
;   #_099FA3: dw Follower_BasicMover   ; 0x06 - Blind maiden
;   #_099FA5: dw Follower_BasicMover   ; 0x07 - Frogsmith
;   #_099FA7: dw Follower_BasicMover   ; 0x08 - Smithy
;   #_099FA9: dw Follower_BasicMover   ; 0x09 - Locksmith
;   #_099FAB: dw Follower_BasicMover   ; 0x0A - Kiki
;   #_099FAD: dw Follower_OldManUnused ; 0x0B - Minecart Follower
;   #_099FAF: dw Follower_BasicMover   ; 0x0C - Purple chest
;   #_099FB1: dw Follower_BasicMover   ; 0x0D - Super bomb
;   #_099FB3: dw Follower_Telepathy    ; 0x0E - Master Sword telepathy

; ---------------------------------------------------------

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


org $09A4C8
Follower_HandleTriggerData:
{
  .room_id
  #_09A4C8: dw $00D1 ; ROOM 00D1 - old man cave
  #_09A4CA: dw $00FE ; ROOM 0061 - castle lobby
  #_09A4CC: dw $00FD ; ROOM 0051 - castle throne room
  #_09A4CE: dw $00FD ; ROOM 0002 - pre-sanc
  #_09A4D0: dw $00DB ; ROOM 00DB - TT entrance
  #_09A4D2: dw $00AB ; ROOM 00AB - to TT attic
  #_09A4D4: dw $0022 ; ROOM 0022 - sewer rats

  .coordinates_uw
  #_09A4D6: dw $1A78, $0233, $0001, $0099, $0004 ; Old man - MESSAGE 0099
  #_09A4E0: dw $1BC0, $0378, $0002, $009A, $0004 ; Old man - MESSAGE 009A
  #_09A4EA: dw $1A78, $0334, $0004, $009B, $0004 ; Old man - MESSAGE 009B

  #_09A4F4: dw $1FF8, $039D, $0001, $0021, $0001 ; Zelda - MESSAGE 0021
  #_09A4FE: dw $1FF8, $039D, $0002, $0021, $0001 ; Zelda - MESSAGE 0021
  #_09A508: dw $1FF8, $0238, $0004, $0021, $0001 ; Zelda - MESSAGE 0021

  #_09A512: dw $1D78, $1F7F, $0001, $0022, $0001 ; Zelda - MESSAGE 0022

  #_09A51C: dw $1D78, $1F7F, $0001, $0023, $0001 ; Zelda - MESSAGE 0023
  #_09A526: dw $1D78, $1F7F, $0002, $002A, $0001 ; Zelda - MESSAGE 002A

  #_09A530: dw $1BD8, $16FC, $0001, $0124, $0006 ; Blind maiden - MESSAGE 0124

  #_09A53A: dw $1520, $167C, $0001, $0124, $0006 ; Blind maiden - MESSAGE 0124

  #_09A544: dw $05AC, $04FC, $0001, $0029, $0001 ; Zelda - MESSAGE 0029

  ; ---------------------------------------------------------

  .overworld_id
  #_09A54E: dw $0005 ; OW 05 - West DM (Updated)
  #_09A550: dw $002F ; OW 2F - Tail Palace
  #_09A552: dw $0000 ; OW 00 - Lost woods

  .coordinates_ow
  #_09A554: dw $0178, $0A63, $0001, $009D, $0004 ; Old man - MESSAGE 009D
  ;              Y      X
  #_09A55E: dw $0A88, $0F41, $0000, $FFFF, $000A ; Kiki
  #_09A568: dw $0B37, $0F40, $0001, $FFFF, $000A ; Kiki
  #_09A572: dw $0A62, $0E5B, $0002, $FFFF, $000A ; Kiki

  #_09A57C: dw $00E8, $0090, $0000, $0028, $000E ; MS telepathy - MESSAGE 0028

  ; ---------------------------------------------------------

  .room_boundaries_check
  #_09A586: dw $0000, $001E, $003C, $0046
  #_09A58E: dw $005A, $0064, $006E, $0078

  .ow_boundaries_check
  #_09A596: dw $0000, $000A, $0028, $0032
}

