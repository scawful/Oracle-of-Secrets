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
!RestoreCam   = $1CF8

; ==========================================================

; Gets the small/large map true ID of the current screen
Overworld_ActualScreenID = $02A5EC

; At this stage the accumulator contains area currently in
; X contains the area you're moving to.
org $A0F000
LostWoods:
{
  ; If currently in Lost Woods, execute puzzle logic
  LDA.b $8A : CMP.b #$29 : BEQ begincode

  ; Else, return standard area ID (Allow entry)
  LDA.l Pool_Overworld_ActualScreenID_New, X
  STZ !ComboCounter
  RTL

  normalfinish:
    LDA.l Pool_Overworld_ActualScreenID_New, X
    STZ !ComboCounter
    RTL

  begincode:
    ; Return from where we came from
    CPX !EastArea : BEQ normalfinish
    ; from here onwards, use the ram address to determine which combo you're up to
    ; this code is pretty repeatable
    LDA !ComboCounter : CMP #$00 : BNE combo1
      ; did you get it right?
      CPX !NorthArea : BEQ UP_CORRECT
        STZ !ComboCounter
        BRA RESOLVE_INCORRECT

  combo1:
    CMP #$01 : BNE combo2
      CPX !WestArea : BEQ LEFT_CORRECT
        STZ !ComboCounter
        BRA RESOLVE_INCORRECT

  combo2:
    CMP #$02 : BNE combo3
      CPX !SouthArea : BEQ DOWN_CORRECT
        STZ !ComboCounter
        BRA RESOLVE_INCORRECT

  combo3:
    ; we want to load the down area, since we complete the combos
    CPX !WestArea : BNE RESOLVE_INCORRECT
      LDA #$1B : STA $012F ; play fanfare
      BRA normalfinish

    RESOLVE_INCORRECT:
    CPX !NorthArea : BEQ CASE_UP
    CPX !WestArea : BEQ CASE_LEFT
    BRA CASE_DOWN

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
    LDA.b #$01 : STA !RestoreCam
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
} ; label LOST_WOOD_HOOK
