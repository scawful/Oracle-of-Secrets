; =========================================================
; Dual-item prototype, menu side (!ENABLE_DUAL_ITEM_BINDING_PROTOTYPE).
; Items page:
; - Y on an item binds it to Y. Moving the cursor no longer equips: the
;   cursor stays in $0202 while the menu is open (every menu routine reads
;   it), and the Y item is kept in ItemBindingMenuY. Closing the menu writes
;   ItemBindingMenuY back to $0202 before the HUD is rebuilt.
; - X on an item binds it to X (ItemBindings_AssignX: the latchable set in
;   Items/item_bindings.asm; other items play the error sound). X on the item that
;   already holds X clears X, so the field map returns to X. X on this page
;   no longer opens the Journal; Quest and page 3 keep X: Journal.
; - A never binds. A and Start still close the menu; L/R still turn pages.
; - Markers (scawful, HUD_LAYOUT_02.md: "pressing y could do a colored
;   highlight of the item"): green corner marks around the Y item, blue
;   corner marks around the X item, from the existing cursor corner glyph
;   $060 in palettes 7 and 3. The gray navigation cursor keeps its side
;   lines; marks replace its corners on a bound item. One item on both
;   buttons: left corners green (Y), right corners blue (X). Neighbor cells
;   share one corner column, so two adjacent bound items share that corner
;   and X's color shows there.
; Assembled at the end of bank $2D, after the page 3 code, so no flag-off
; byte moves.
; =========================================================

!MB_YMarker = $3C60                 ; corner $060, palette 7 (green), priority
!MB_XMarker = $2C60                 ; corner $060, palette 3 (blue), priority

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
    STA.l ItemBindingSavedY             ; reload restores this Y item
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
if !ENABLE_HUD_LAYOUT_CODEX == 1
  ; One corner per button: Y = green top-left, X = blue bottom-right.
  ; Cells are 3 tiles apart and the brackets 4 wide, so four-corner marks
  ; of neighbour cells landed on the same tiles and blended green and blue.
  ; One fixed corner per button can only meet when the Y cell is diagonally
  ; down-right of the X cell (Y is drawn first, X wins that one tile).
  LDA.l ItemBindingMenuY : JSR .cell : BCC .cx_no_y
    LDA.w #!MB_YMarker : STA.w $1108, X
  .cx_no_y
  JSR .x_cell : BCC .cx_no_x
    LDA.w #!MB_XMarker|$C000 : STA.w $11CE, X
  .cx_no_x
  ; Redraw the gray cursor on top, so a neighbour's mark never colors it,
  ; then give back its own cell's marks. Blink-off frames ($0207 bit 5) and
  ; a mask item (no grid cursor) keep the marks only.
  SEP #$30
  LDA.b #$20 : BIT.w $0207 : BNE .cx_done
if !ENABLE_MENU_PAGE3 == 1
  LDA.w $0202 : JSR Menu_Page3_IsMaskItem : BCS .cx_done
endif
  LDA.w $0202 : BEQ .cx_done
  ASL : TAY
  REP #$10
  LDX.w Menu_ItemCursorPositions-2, Y
  JSR Menu_DrawCursor                 ; A8 in/out, keeps X
  REP #$20
  LDA.l ItemBindingMenuY : EOR.w $0202 : AND.w #$00FF : BNE .cx_own_x
    LDA.w #!MB_YMarker : STA.w $1108, X
  .cx_own_x
  LDA.l ItemBindingSavedVersion : AND.w #$00FF : CMP.w #$0001 : BNE .cx_done
  LDA.l ItemBindingSavedX : EOR.w $0202 : AND.w #$00FF : BNE .cx_done
    LDA.w #!MB_XMarker|$C000 : STA.w $11CE, X
  .cx_done
  PLP : RTS

  ; X item cell: C set and X = offset when version 1 holds a grid item.
  .x_cell
  LDA.l ItemBindingSavedVersion : AND.w #$00FF : CMP.w #$0001 : BNE .none
  LDA.l ItemBindingSavedX
  BRA .cell
endif
  LDA.l ItemBindingMenuY : JSR .cell : BCC .no_y
    LDA.w #!MB_YMarker : JSR .corners
  .no_y
  LDA.l ItemBindingSavedVersion : AND.w #$00FF : CMP.w #$0001 : BNE .done
  LDA.l ItemBindingSavedX : JSR .cell : BCC .done
    LDA.w #!MB_XMarker : JSR .corners
    ; Same item on Y: the left corners show Y again.
    LDA.l ItemBindingMenuY : EOR.l ItemBindingSavedX : AND.w #$00FF : BNE .done
      LDA.w #!MB_YMarker : STA.w $1108, X
      ORA.w #$8000 : STA.w $11C8, X
  .done
  PLP : RTS

  ; A = top-left corner word; X = cell offset. Writes the four corners.
  .corners
  STA.w $1108, X                      ; top left
  ORA.w #$4000 : STA.w $110E, X       ; top right (H flip)
  ORA.w #$8000 : STA.w $11CE, X       ; bottom right (H+V flip)
  EOR.w #$4000 : STA.w $11C8, X       ; bottom left (V flip)
  RTS

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
