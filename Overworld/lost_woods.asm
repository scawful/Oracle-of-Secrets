;===========================================================
; Lost Woods Hack
;
; Area: 29
; East Exit 2A 
; North Exit 21
; South is 31
; West is 28
;
; combo is N(21), W(28), S(31), W(28)
;===========================================================

!NorthArea    = #$21
!WestArea     = #$28
!SouthArea    = #$31
!EastArea     = #$2A
!ComboCounter = $1CF7 ; ram address to store combo counter

; ==========================================================

; OverworldHandleTransitions
org $02AA7D
  JSL LOST_WOOD_HOOK

; At this stage the accumulator contains area currently in
; X contains the area you're moving to.
org $A0F000
LOST_WOOD_HOOK: 
{
  CMP #$29      ; are we in the right area?
  BEQ begincode

  normalfinish: 
  {
    ; Overworld_ActualScreenID
    ; Gets the small/large map true ID of the current screen
    LDA $02A5EC, x    ; not right area so return.
    STZ !ComboCounter
    RTL
  } ; label normalfinish

  begincode: 
  {
    CPX !EastArea
    BEQ normalfinish

    ; from here onwards, use the ram address to determine which combo you're up to
    ; this code is pretty repeatable
    LDA !ComboCounter

    CMP #$00
    BNE combo1
    CPX !NorthArea        ; did you get it right?
    BEQ UP_CORRECT
    STZ !ComboCounter
    BRA RESOLVE_INCORRECT
  } ; label begincode

  combo1: 
  {
    CMP #$01
    BNE combo2
    CPX !WestArea         ; did you get it right?
    BEQ LEFT_CORRECT
    STZ !ComboCounter
    BRA RESOLVE_INCORRECT
  } ; label comb1


  combo2: 
  {
    CMP #$02
    BNE combo3
    CPX !SouthArea        ; did you get it right?
    BEQ DOWN_CORRECT
    STZ !ComboCounter
    BRA RESOLVE_INCORRECT
  } ; label comb2


  combo3: 
  {
    CPX !WestArea         ; did you get it right?
    BNE RESOLVE_INCORRECT ; we want to load the down area, since we complete the combos
    LDA #$1B
    STA $012F             ; play fanfare
    BRA normalfinish

    RESOLVE_INCORRECT:
    CPX !NorthArea
    BEQ CASE_UP
    CPX !WestArea
    BEQ CASE_LEFT
    BRA CASE_DOWN
  } ; label combo3

  DOWN_CORRECT: 
  {
    INC !ComboCounter
    CASE_DOWN:
    DEC $21
    DEC $21
    DEC $E7
    DEC $E7
    DEC $E9
    DEC $E9
    DEC $611
    DEC $611
    DEC $613
    DEC $613
    LDA $700
    SEC
    SBC #$10
    STA $700
    BRA all
  } ; label DOWN_CORRECT


  UP_CORRECT: 
  {
    INC !ComboCounter
    CASE_UP:
    INC $21
    INC $21
    INC $E7
    INC $E7
    INC $E9
    INC $E9
    INC $611
    INC $611
    INC $613
    INC $613
    LDA $700
    CLC
    ADC #$10
    STA $700
    BRA all
  } ; label UP_CORRECT


  LEFT_CORRECT: 
  {
    INC !ComboCounter
    CASE_LEFT:
    INC $23
    INC $23
    INC $E1
    INC $E1
    INC $E3
    INC $E3
    INC $615
    INC $615
    INC $617
    INC $617
    INC $700
    INC $700
  } ; label LEFT_CORRECT

  all: 
  {
    LDA #$29 ; load the same area.
    RTL
  }

  ; TODO: Restore camera values on invalid combinations.
  RestoreCameraNorth:
  {
    LDA $700
    SEC
    SBC #$10
    STA $700
    RTS
  }

  RestoreCameraSouth:
  {
    LDA $700
    CLC
    ADC #$10
    STA $700
    RTS
  }

  RestoreCameraWest:
  {
    DEC $700
    DEC $700
    RTS
  }

  RestoreCameraEast:
  {
    INC $700
    INC $700
    RTS
  }

} ; label LOST_WOOD_HOOK