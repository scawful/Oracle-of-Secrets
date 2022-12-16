; ==============================================================================
; NEW: Custom Room Tag to initialize the game without the Uncle sprite.
; 

org $05E219
  Sprite_ShowMessageUnconditional:

org $01CC18 ; override routine 0x39 "Holes(7)"
  JML HouseTag

org $01CC5A 
  HouseTag_Return:

org $228000
HouseTag:
{
  PHX 
  ; -------------------------------
  
  LDA StoryState : BNE .has_begun 
  INC.b StoryState
  JSR HouseTag_TelepathicPlea
  JSR HouseTag_WakeUpPlayer

  STZ $02E4 ; awake from slumber 
.has_begun

  ; -------------------------------
  PLX
  JML HouseTag_Return
}

; ==============================================================================


HouseTag_TelepathicPlea:
{
  ; -------------------------------
  ; Set Link's coordinates to this specific position.
  LDA.b #$40 : STA $0FC2
  LDA.b #$09 : STA $0FC3
  
  LDA.b #$5A : STA $0FC4
  LDA.b #$21 : STA $0FC5
      
  ; "Accept our quest, Link!"
  LDA.b #$1F : LDY.b #$00
  JSL Sprite_ShowMessageUnconditional
  INC $0D80, X

  RTS
}

; ==============================================================================

HouseTag_WakeUpPlayer:
{
  ; Lighten the screen gradually and then wake Link up partially
  
  LDA $1A : AND.b #$03 : BNE .delay
  
  LDA $9C : CMP.b #$20 : BEQ .colorTargetReached
  
  DEC $9C
  DEC $9D

.delay

  RTS

.colorTargetReached

  INC $0D80, X
  
  INC $037D
  INC $037C
  
  LDA.b #$57 : STA $20
  LDA.b #$21 : STA $21
  
  LDA.b #$01 : STA $02E4
  
  RTS
}