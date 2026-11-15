; =========================================================
; Dual-item prototype, menu side (!ENABLE_DUAL_ITEM_BINDING_PROTOTYPE).
; Items page:
; - Y on an item binds it to Y. Moving the cursor no longer equips: the
;   cursor stays in $0202 while the menu is open (every menu routine reads
;   it), and the Y item is kept in ItemBindingMenuY. Closing the menu writes
;   ItemBindingMenuY back to $0202 before the HUD is rebuilt.
; - X on an item binds it to X (ItemBindings_AssignX: Bow or Boomerang in
;   this prototype; other items play the error sound). X on the item that
;   already holds X clears X, so the field map returns to X. X on this page
;   no longer opens the Journal; Quest and page 3 keep X: Journal.
; - A never binds. A and Start still close the menu; L/R still turn pages.
; - Markers sit in the two blank tiles under each cell's frame: a green chip
;   under the left half of the Y item, a blue chip under the right half of
;   the X item (the SFC face-button colors and sides). One item on both
;   buttons shows both chips side by side. The menu font draws letters in
;   color 2, which is white in palettes 1-3 and 7, so a letter cannot carry
;   the button color; BG3 tile $004 is a 4-pixel bar in color 1.
; Assembled at the end of bank $2D, after the page 3 code, so no flag-off
; byte moves.
; =========================================================

!MB_YMarker = $3C04                 ; tile $004 bar, palette 7 (green), priority
!MB_XMarker = $2C04                 ; tile $004 bar, palette 3 (blue), priority

; Menu_InitGraphics (menu open). Any widths; keeps A/X/Y and P.
Menu_Bindings_Open:
{
  PHP : SEP #$20 : PHA
  LDA.w $0202 : STA.l ItemBindingMenuY
  PLA : PLP : RTS
}

; Menu_InitiateScrollDown and Menu_Exit (menu close). The Y item returns to
; $0202 before RebuildHUD_long and the $0303 copy read it. A zero Y item
; (menu opened with none) keeps the cursor item, as before. Keeps A/X/Y, P.
Menu_Bindings_Close:
{
  PHP : SEP #$20 : PHA
  LDA.l ItemBindingMenuY : BEQ .keep
    STA.w $0202
  .keep
  PLA : PLP : RTS
}

; Menu_ItemScreen, after the page turn/close check, M/X=8, DBR=$2D.
; Destroys A. C clear on return.
Menu_Bindings_Input:
{
  LDA.w $0202 : BEQ .done             ; empty grid: nothing to bind
  LDA.b $F4 : BIT.b #$40 : BEQ .no_y
    LDA.w $0202 : STA.l ItemBindingMenuY
    JSR .changed
  .no_y
  LDA.b $F6 : BIT.b #$40 : BEQ .done
    LDA.b #$40 : TRB.b $F6            ; X binds here; no Journal shortcut
    ; First assignment on this file: run the binding migration once, so the
    ; gameplay hydrate (version 1) keeps X instead of clearing it.
    LDA.l ItemBindingSavedVersion : CMP.b #$01 : BEQ .versioned
      JSL ItemBindings_Load
    .versioned
    LDA.w $0202 : CMP.l ItemBindingSavedX : BNE .assign
      LDA.b #$00 : STA.l ItemBindingSavedX ; same item again: clear X
      BRA .x_changed
    .assign
    STA.l ItemBindingCursor
    JSL ItemBindings_AssignX : BCC .refuse
  .x_changed
    JSR .changed
  .done
  SEP #$30
  CLC : RTS

  .refuse
  LDA.b #$3C : STA.w $012E            ; error sound (Magic Bag)
  BRA .done

  ; Old markers are erased by repainting the page once, as a page turn does.
  .changed
  JSR Menu_RefreshInventoryScreen     ; returns SEP #$30
  LDA.b #$20 : STA.w $0207            ; show the cursor on the next frame
  LDA.b #$22 : STA.w $012F            ; equip sound (page 3)
  RTS
}

; Menu_ItemScreen after the cursor draw, any widths. Keeps P; destroys A/X.
Menu_Bindings_DrawMarkers:
{
  PHP : REP #$30
  LDA.l ItemBindingMenuY : JSR .cell : BCC .no_y
    LDA.w #!MB_YMarker : STA.w $11CA, X
  .no_y
  LDA.l ItemBindingSavedVersion : AND.w #$00FF : CMP.w #$0001 : BNE .done
  LDA.l ItemBindingSavedX : JSR .cell : BCC .done
    LDA.w #!MB_XMarker : STA.w $11CC, X
  .done
  PLP : RTS

  ; A low byte = item ID. C set: X = Menu_ItemCursorPositions offset.
  .cell
  AND.w #$00FF : BEQ .none
  CMP.w #((Menu_ItemCursorPositions_End-Menu_ItemCursorPositions)/2)+1 : BCS .none
  ASL : TAX
  LDA.w Menu_ItemCursorPositions-2, X : TAX
  SEC : RTS
  .none
  CLC : RTS
}
