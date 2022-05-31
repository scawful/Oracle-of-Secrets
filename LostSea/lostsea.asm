;===========================================================
; Lost Sea Hack
;
; Area: 3A
; East Exit 3B (or 33)
; North Exit 32
; South is 42
; West is 39
; combo is N (32),W (39),S (42),N (32)
;===========================================================

namespace LostSea 
{
  Main: {
    lorom
    org $A0F000 ; Note at this stage the accumulator contains area currently in, and X contains the area you're moving to.

    LOST_WOOD_HOOK: {
      CMP #$3A ; are we in the right area?
      BEQ begincode

      normalfinish: {
        LDA $02A5EC,x ; not right area so return.
        STZ $1CF7
        RTL
      }  ; label normalfinish

      begincode: {
        CPX #$3B
        BEQ normalfinish

        ; from here onwards, use the ram address to determine which combo you're up to
        ; this code is pretty repeatable
        LDA $1CF7

        CMP #$00
        BNE combo1
        CPX #$32 ; did you get it right?
        BEQ UP_CORRECT
        STZ $1CF7
        BRA RESOLVE_INCORRECT
      }  ; label begincode

      combo1: {
        CMP #$01
        BNE combo2
        CPX #$39 ; did you get it right?
        BEQ LEFT_CORRECT
        STZ $1CF7
        BRA RESOLVE_INCORRECT
      }  ; label comb1


      combo2: {
        CMP #$02
        BNE combo3
        CPX #$42 ; did you get it right?
        BEQ DOWN_CORRECT
        STZ $1CF7
        BRA RESOLVE_INCORRECT
      }  ; label comb2


      combo3: {
        CPX #$32; did you get it right?
        BNE RESOLVE_INCORRECT ; we want to load the down area, since we complete the combos
        LDA #$1B
        STA $012F ; play fanfare
        BRA normalfinish
        RESOLVE_INCORRECT:
        CPX #$39
        BEQ CASE_LEFT
        CPX #$32
        BEQ CASE_UP
        BRA CASE_DOWN
      }  ; label combo3

      DOWN_CORRECT: {
        INC $1CF7
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
      }  ; label DOWN_CORRECT


      UP_CORRECT: {
        INC $1CF7
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
      }  ; label UP_CORRECT


      LEFT_CORRECT: {
        INC $1CF7
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
      }  ; label LEFT_CORRECT

      all: {
        LDA #$3A  ; load the same area.
        RTL
      }

      .end 
      ORG $02AA7D
      JSL LOST_WOOD_HOOK
    }  ; label LOST_WOOD_HOOK
  }  ; label Main
}  ; namespace LostSea
