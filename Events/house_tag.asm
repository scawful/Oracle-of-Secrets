; ==============================================================================
; NEW: Custom Room Tag to initialize the game without the Uncle sprite.
; 

incsrc "Util/ram.asm"

org $008781
  UseImplicitRegIndexedLocalJumpTable:

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
  LDA $7EF3C6 : BNE .game_has_begun
  JSR HouseTag_Main
.game_has_begun
  ; -------------------------------
  PLX
  JML HouseTag_Return
}

; ==============================================================================

HouseTag_Main:
{
  LDA StoryState

  JSL UseImplicitRegIndexedLocalJumpTable
  
  dw HouseTag_TelepathicPlea
  dw HouseTag_WakeUpPlayer
  dw HouseTag_End
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
  INC.b StoryState

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
  
  ;LDA.b #$01 : STA $02E4

  STZ $02E4 ; awake from slumber
  INC.b StoryState 

  ; Make it so Link's uncle never respawns in the house again.
  LDA $7EF3C6 : ORA.b #$10 : STA $7EF3C6

  ; Set the game mode to part 2 
  LDA #$02
  STA $7ef3C5   ; store "part 2"
  LDA #$00
  STA $7ef3CC   ; disable telepathic message
  JSL $00FC41   ; fix monsters
  
  RTS
}

; ==============================================================================

HouseTag_End:
{
    RTS
}

; ==============================================================================