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
!RestoreCam   = $7E1CF8  ; Must use full address for cross-bank access

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
      ; Note: Camera drift fix was attempted here but broke small-to-large transitions.
      ; The scroll drift from wrong puzzle moves persists until Link moves enough
      ; in the new area for the camera to catch up naturally.
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
      ; Note: !RestoreCam is now set at normalfinish for all exits
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
  
  LostWoods_ResetCoordinates:
  {
      ; Only run if we are in area 0x29
      LDA.b $8A : CMP.b #$29 : BNE .done
  
      REP #$20
      
      ; Check Target Area (in X register)
      CPX !EastArea : BEQ .snap_east
      CPX !WestArea : BEQ .snap_west
      CPX !NorthArea : BEQ .snap_north
      CPX !SouthArea : BEQ .snap_south
      BRA .done_coords ; Fallback if unknown exit
  
      .snap_east ; Target 0x2A (Right)
          ; Snap X to Right Edge of 0x29 (0x0400)
          LDA.w #$0400 : STA.b $22
          ; Modulo Y to 0x29 Base (0x0A00)
          LDA.b $20 : AND.w #$01FF : ORA.w #$0A00 : STA.b $20
          BRA .reset_scroll
  
      .snap_west ; Target 0x28 (Left)
          ; Snap X to Left Edge of 0x29 (0x0200)
          LDA.w #$0200 : STA.b $22
          ; Modulo Y to 0x29 Base (0x0A00)
          LDA.b $20 : AND.w #$01FF : ORA.w #$0A00 : STA.b $20
          BRA .reset_scroll
  
      .snap_north ; Target 0x21 (Up)
          ; Snap Y to Top Edge of 0x29 (0x0A00)
          LDA.w #$0A00 : STA.b $20
          ; Modulo X to 0x29 Base (0x0200)
          LDA.b $22 : AND.w #$01FF : ORA.w #$0200 : STA.b $22
          BRA .reset_scroll
  
      .snap_south ; Target 0x31 (Down)
          ; Snap Y to Bottom Edge of 0x29 (0x0C00)
          LDA.w #$0C00 : STA.b $20
          ; Modulo X to 0x29 Base (0x0200)
          LDA.b $22 : AND.w #$01FF : ORA.w #$0200 : STA.b $22
          BRA .reset_scroll
  
      .done_coords
      ; If we didn't match an exit, fallback to just modulo-ing both
      LDA.b $20 : AND.w #$01FF : ORA.w #$0A00 : STA.b $20
      LDA.b $22 : AND.w #$01FF : ORA.w #$0200 : STA.b $22
  
      .reset_scroll
      SEP #$20

      ; Reset Overlay Scroll Drifts introduced by puzzle
      STZ.b $E1
      STZ.b $E3
      STZ.b $E7
      STZ.b $E9

      .done
      RTL
  }

; =============================================================================
; LostWoods_RecalculateScroll
; =============================================================================
; Recalculates camera scroll position based on Link's current coordinates.
; Called AFTER transition completes to fix scroll drift from Lost Woods puzzle.
;
; The camera scroll should center Link on screen:
;   Scroll_X = Link_X - 128 (half of 256px screen width)
;   Scroll_Y = Link_Y - 112 (half of 224px screen height)
;
; The result is clamped to camera boundaries ($0600-$0606) to prevent
; showing areas outside the valid map region.
;
; Registers modified:
;   A - Used for calculations
;   $00-$01 - Temp storage for calculated scroll
;
; Scroll register layout:
;   $E0/$E2 - BG1 scroll X (lo/hi) - parallax/overlay layer
;   $E1/$E3 - BG2 scroll X (lo/hi) - main gameplay layer
;   $E6/$E8 - BG1 scroll Y (lo/hi)
;   $E7/$E9 - BG2 scroll Y (lo/hi)
;
; Camera boundary layout:
;   $0600 - Camera Y minimum (top edge of scrollable area)
;   $0602 - Camera Y maximum (bottom edge)
;   $0604 - Camera X minimum (left edge)
;   $0606 - Camera X maximum (right edge)
; =============================================================================
LostWoods_RecalculateScroll:
{
    PHB : PHK : PLB

    REP #$20  ; 16-bit accumulator

    ; --- Calculate Y scroll ---
    ; Ideal scroll Y = Link Y - 112 (center vertically)
    LDA.b $20           ; Link Y position (16-bit)
    SEC
    SBC.w #$0070        ; Subtract 112 (0x70) for vertical centering

    ; Clamp to camera Y boundaries
    CMP.w $0600         ; Compare to Y minimum
    BCS .y_above_min
        LDA.w $0600     ; Use minimum if below
    .y_above_min

    CMP.w $0602         ; Compare to Y maximum
    BCC .y_below_max
        LDA.w $0602     ; Use maximum if above
    .y_below_max

    ; Store Y scroll (split into lo/hi bytes)
    STA.b $00           ; Temp store full value
    SEP #$20            ; 8-bit for byte operations
    LDA.b $00 : STA.b $E7   ; Y scroll low byte
    LDA.b $01 : STA.b $E9   ; Y scroll high byte

    REP #$20  ; Back to 16-bit

    ; --- Calculate X scroll ---
    ; Ideal scroll X = Link X - 128 (center horizontally)
    LDA.b $22           ; Link X position (16-bit)
    SEC
    SBC.w #$0080        ; Subtract 128 (0x80) for horizontal centering

    ; Clamp to camera X boundaries
    CMP.w $0604         ; Compare to X minimum
    BCS .x_above_min
        LDA.w $0604     ; Use minimum if below
    .x_above_min

    CMP.w $0606         ; Compare to X maximum
    BCC .x_below_max
        LDA.w $0606     ; Use maximum if above
    .x_below_max

    ; Store X scroll (split into lo/hi bytes)
    STA.b $00           ; Temp store full value
    SEP #$20            ; 8-bit for byte operations
    LDA.b $00 : STA.b $E1   ; X scroll low byte
    LDA.b $01 : STA.b $E3   ; X scroll high byte

    PLB
    RTL
}
