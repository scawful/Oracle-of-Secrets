; =========================================================
; Dual-item binding, menu side.
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
; Assembled at $548800+ from Items/all_items.asm (banks $2B/$2D are full); entries
; are JSL/RTL. Menu/menu.asm keeps two long wrappers for the $2D calls.
; =========================================================

!MB_YMarker = $3C60                 ; corner $060, palette 7 (green), priority
!MB_XMarker = $2C60                 ; corner $060, palette 3 (blue), priority

; Menu_InitGraphics (menu open). Saves the equipped Y item, then restores
; MenuFlow_ItemsCursor to $0202 if owned on the Items grid.
; Any widths; keeps A/X/Y and P.
Menu_Bindings_Open:
{
  PHP : SEP #$20 : PHA
  LDA.w $0202 : STA.l ItemBindingMenuY
  LDA.l MenuFlow_ItemsCursor : BEQ .keep
if !ENABLE_MENU_PAGE3 == 1 || !ENABLE_GOLDSTAR_CELL == 1
  CMP.b #$13 : BCC .check_garo
  CMP.b #$18 : BCC .clear
.check_garo
endif
if !ENABLE_GOLDSTAR_CELL == 1
  CMP.b #$1E : BEQ .clear
endif
  JSR ItemBindings_ValidateY : BCC .clear
  STA.w $0202
  BRA .keep
.clear
  LDA.b #$00 : STA.l MenuFlow_ItemsCursor
.keep
  PLA : PLP : RTL
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
  PLA : PLP : RTL
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
  CLC : RTL

  .refuse
  LDA.b #$3C : STA.w $012E            ; error sound (Magic Bag)
  BRA .done

  ; Old markers are erased by repainting the page once, as a page turn does.
  .changed
  JSL Menu_RefreshInventoryScreen_Long    ; returns SEP #$30
  LDA.b #$20 : STA.w $0207            ; show the cursor on the next frame
  LDA.b #$22 : STA.w $012F            ; equip sound (page 3)
  RTS
}

; Menu_ItemScreen after the cursor draw, any widths. Keeps P; destroys A/X.
Menu_Bindings_DrawMarkers:
{
  PHP : SEP #$20
  LDA.w $0202 : STA.l MenuFlow_ItemsCursor
  REP #$30
  ; Full brackets (corners + side lines, like the gray cursor): Y green,
  ; X blue. Cells are 3 tiles apart across and down and the brackets 4x4,
  ; so neighbour cells share a column or row of tiles; whichever mark is
  ; drawn last owns them. Menu_DrawCursor already ran: gray on blink-on
  ; frames ($0207 bit 5 clear), erased on blink-off frames.
  ;   blink-on:  the cursor cell's marks are skipped (it stays gray);
  ;              the other mark is drawn after it and is whole.
  ;   blink-off: the cursor cell's mark is drawn last and is whole.
  ;   cursor on neither mark: X last on blink-off, Y last on blink-on.
  ; Y = item whose marks are skipped (0 = none). A mask Y item has no grid
  ; cursor, so nothing is skipped.
  LDY.w #$0000
  LDA.w $0207 : AND.w #$0020 : BNE .cx_off
if !ENABLE_MENU_PAGE3 == 1
    SEP #$20
    LDA.w $0202 : JSL Menu_Page3_IsMaskItem_Long
    REP #$20
    BCS .cx_on_draw
endif
    LDA.w $0202 : AND.w #$00FF : TAY
    .cx_on_draw
    JSR .cx_draw_x : JSR .cx_draw_y
    BRA .cx_done
  .cx_off
  LDA.w $0202 : EOR.l ItemBindingMenuY : AND.w #$00FF : BNE .cx_x_last
    JSR .cx_draw_x : JSR .cx_draw_y
    BRA .cx_done
  .cx_x_last
  JSR .cx_draw_y : JSR .cx_draw_x
  .cx_done
  PLP : RTL

  ; Same item on both buttons: X draws it (left half green, right half blue).
  .cx_draw_y
  LDA.l ItemBindingMenuY : EOR.l ItemBindingSavedX : AND.w #$00FF : BNE .cx_y_own
    JSR .x_cell : BCS .cx_draw_x
  .cx_y_own
  TYA : EOR.l ItemBindingMenuY : AND.w #$00FF : BEQ .cx_rts
  LDA.l ItemBindingMenuY : JSR .cell : BCC .cx_rts
  LDA.w #!MB_YMarker : JMP .bracket

  .cx_draw_x
  TYA : EOR.l ItemBindingSavedX : AND.w #$00FF : BEQ .cx_rts
  JSR .x_cell : BCC .cx_rts
  LDA.w #!MB_XMarker : JSR .bracket
  LDA.l ItemBindingMenuY : EOR.l ItemBindingSavedX : AND.w #$00FF : BNE .cx_rts
    LDA.w #!MB_YMarker : STA.w $1108, X
    ORA.w #$8000 : STA.w $11C8, X
    LDA.w #!MB_YMarker+$0010 : STA.w $1148, X : STA.w $1188, X
  .cx_rts
  RTS

  ; A = top-left corner word; X = cell offset. Corners plus side lines
  ; (side glyph = corner + $10), the same 8 tiles as Menu_DrawCursor.
  .bracket
  STA.w $1108, X                      ; top left
  ORA.w #$8000 : STA.w $11C8, X       ; bottom left (V flip)
  ORA.w #$4000 : STA.w $11CE, X       ; bottom right (H+V flip)
  EOR.w #$8000 : STA.w $110E, X       ; top right (H flip)
  CLC : ADC.w #$0010
  STA.w $114E, X : STA.w $118E, X     ; right side (H flip)
  EOR.w #$4000
  STA.w $1148, X : STA.w $1188, X     ; left side
  RTS

  ; X item cell: C set and X = offset when version 1 holds a grid item.
  .x_cell
  LDA.l ItemBindingSavedVersion : AND.w #$00FF : CMP.w #$0001 : BNE .none
  LDA.l ItemBindingSavedX
  BRA .cell

  ; A low byte = item ID. C set: X = Menu_ItemCursorPositions offset.
  .cell
  AND.w #$00FF : BEQ .none
  CMP.w #((Menu_ItemCursorPositions_End-Menu_ItemCursorPositions)/2)+1 : BCS .none
  ASL : TAX
  LDA.l Menu_ItemCursorPositions-2, X : TAX
  SEC : RTS
  .none
  CLC : RTS
}
