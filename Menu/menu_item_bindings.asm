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

!MB_YPal     = $3C00                ; palette 7 (green), priority
!MB_XPal     = $2C00                ; palette 3 (blue), priority
!C4_BadgeY   = $3D2B                ; green pal 7 + priority + tile $12B
!C4_BadgeX   = $2D2C                ; blue  pal 3 + priority + tile $12C
!C4_BadgeXTR = $6D2C                ; blue  pal 3 + priority + H-flip + tile $12C
!C4_Corner   = $012D                ; thin rounded frame corner
!C4_Horiz    = $012E                ; thin horizontal frame line
!C4_Vert     = $012F                ; thin vertical frame line
!C4_ActiveL  = $353F                ; gold pal 5 + priority + active L-bracket $13F
!Menu_DivV   = $214F                ; brown wood vertical divider
!Menu_DivH   = $217A                ; brown wood horizontal divider

; Menu_InitGraphics (menu open). Saves the equipped Y item, then restores
; MenuFlow_ItemsCursor to $0202 if owned on the Items grid.
; Any widths; keeps A/X/Y and P.
Menu_Bindings_Open:
{
  PHP : SEP #$20 : PHA
  LDA.w $0202 : STA.l ItemBindingMenuY
  LDA.l MenuFlow_ItemsCursor : BEQ .keep
  CMP.b #$13 : BCC .check_garo
  CMP.b #$18 : BCC .clear
.check_garo
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
  LDA.b $F4 : BIT.b #$40 : BNE .bind_y
  LDA.b $F6 : BIT.b #$80 : BEQ .no_y
    LDA.b #$80 : TRB.b $F6            ; A binds Y here
  .bind_y
    LDA.w $0202 : STA.l ItemBindingMenuY
    LDA.b #$20 : JSR .changed         ; subtle Zelda confirm tick (SFX3.$20)
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
      LDA.b #$0C                      ; soft quiet unbind blip (SFX3.$0C)
      BRA .x_changed
    .assign
    STA.l ItemBindingCursor
    JSL ItemBindings_AssignX : BCC .refuse
    LDA.b #$20                        ; subtle Zelda confirm tick (SFX3.$20)
  .x_changed
    JSR .changed
  .done
  SEP #$30
  CLC : RTL

  .refuse
  LDA.b #$3C : STA.w $012E            ; error sound (Magic Bag)
  BRA .done

  ; Old markers are erased by repainting the page once, as a page turn does.
  ; In: A = SFX3 ID ($20 bind confirm, $0C unbind/clear).
  .changed
  PHA
  JSL Menu_RefreshInventoryScreen_Long    ; returns SEP #$30
  LDA.b #$20 : STA.w $0207            ; show the cursor on the next frame
  PLA : STA.w $012F
  RTS
}

; Menu_ItemScreen after the cursor draw, any widths. Keeps P; destroys A/X.
; Cursor C4 layering:
;   - Y-bound item: Green ($3C) thin rounded 12-tile frame + crisp Y badge at TL.
;   - X-bound item: Blue  ($2C) thin rounded 12-tile frame + crisp X badge at TL.
;   - Both on same item: left half Green (Y badge TL), right half Blue (X badge TR).
;   - Active cursor ($0202) on blink-on ($0207 bit 5 clear): bold Gold ($34)
;     L-brackets drawn last on non-badge corners so both active selection and
;     equipped Y/X badges stay crisply visible at the same time.
Menu_Bindings_DrawMarkers:
{
  PHP : SEP #$20
  LDA.w $0202 : STA.l MenuFlow_ItemsCursor
  REP #$30
  ; Always draw Y and X C4 frames first (X second if adjacent; split if same cell).
  JSR .c4_draw_y
  JSR .c4_draw_x

  ; On blink-on frames, overlay Gold active C4 L-brackets on the hovered cell
  ; (preserving any Y/X badge on that cell's TL / TR corner).
  LDA.w $0207 : AND.w #$0020 : BNE .c4_done
    SEP #$20
    LDA.w $0202 : JSL Menu_Page3_IsMaskItem_Long
    REP #$20
    BCS .c4_done
    LDA.w $0202 : JSR .cell : BCC .c4_done
    ; Always draw BL and BR Gold L-brackets on the hovered item.
    LDA.w #!C4_ActiveL|$8000 : STA.w $11C8, X
    LDA.w #!C4_ActiveL|$C000 : STA.w $11CE, X
    ; Check if hovered item == Y or X (if so, preserve TL badge!).
    LDA.w $0202 : EOR.l ItemBindingMenuY : AND.w #$00FF : BEQ .c4_hover_has_tl
    JSR .is_x_hovered : BCS .c4_hover_has_tl
      LDA.w #!C4_ActiveL : STA.w $1108, X
      LDA.w #!C4_ActiveL|$4000 : STA.w $110E, X
      BRA .c4_done
    .c4_hover_has_tl
    ; If hovered item is bound to BOTH Y and X, preserve TR X-badge too!
    LDA.w $0202 : EOR.l ItemBindingMenuY : AND.w #$00FF : BNE .c4_hover_tr
    JSR .is_x_hovered : BCS .c4_done
    .c4_hover_tr
    LDA.w #!C4_ActiveL|$4000 : STA.w $110E, X
  .c4_done
  PLP : RTL

  ; C set if version 1 X binding equals current cursor $0202. Keeps X.
  .is_x_hovered
  LDA.l ItemBindingSavedVersion : AND.w #$00FF : CMP.w #$0001 : BNE .ix_no
  LDA.l ItemBindingSavedX : EOR.w $0202 : AND.w #$00FF : BNE .ix_no
  SEC : RTS
  .ix_no
  CLC : RTS

  ; Draw Y-bound item's green thin rounded frame + Y badge at TL.
  .c4_draw_y
  LDA.l ItemBindingMenuY : JSR .cell : BCC .c4_rts
  LDA.w #!MB_YPal : JSR Menu_C4_DrawFrame_Near
  LDA.w #!C4_BadgeY : STA.w $1108, X
  .c4_rts
  RTS

  ; Draw X-bound item's blue thin rounded frame + X badge.
  ; If X == Y, keep left half green (Y badge TL) and paint right half blue (X badge TR).
  .c4_draw_x
  JSR .x_cell : BCC .c4_rts
  LDA.l ItemBindingMenuY : EOR.l ItemBindingSavedX : AND.w #$00FF : BEQ .c4_split
    LDA.w #!MB_XPal : JSR Menu_C4_DrawFrame_Near
    LDA.w #!C4_BadgeX : STA.w $1108, X
    RTS
  .c4_split
  ; Right half blue: TR = H-flipped symmetric X badge, T2/R1/R2/BR/B2 = blue.
  LDA.w #!C4_BadgeXTR : STA.w $110E, X
  LDA.w #!MB_XPal|!C4_Horiz : STA.w $110C, X
  ORA.w #$8000 : STA.w $11CC, X
  LDA.w #!MB_XPal|!C4_Vert|$4000 : STA.w $114E, X : STA.w $118E, X
  LDA.w #!MB_XPal|!C4_Corner|$C000 : STA.w $11CE, X
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

incsrc "menu_v5_ext.asm"
