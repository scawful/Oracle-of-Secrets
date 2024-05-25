; =========================================================
; Old Man Follower Sprite 
; 


; SpritePrep_OldMan
org $1EE910
  LDA.l $7EF342
  CMP.b #$02

; Old man gives link the "shovel" 
org $1EE9FF
  LDY.b #$13 ; ITEMGET 1A
  STZ.w $02E9

; FindEntrance
org $1BBD3C
  CMP.w #$04

; Underworld_LoadEntrance
org $02D98B
  CMP.w #$02