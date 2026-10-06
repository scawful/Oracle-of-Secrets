; =========================================================
; Menu page 3 "Masks & Rings" (!ENABLE_MENU_PAGE3)
;
; Hub layout: Masks&Rings <- Items -> Quest.
; Docs/Planning/Reviews/audit_2026-09-26/menu_page3_feasibility.md (Plan A)
;
; Items page (flag on):
; - The five masks leave the item grid (row 4 keeps only Bottle 4).
;   Grid navigation treats the mask cells as empty; while a mask is the
;   Y item ($0202 = $13-$17) the grid draws no cursor and the name bar
;   shows the mask's name.
; - L: page 3, cursor on the equipped mask (else the first owned mask,
;   else the first owned ring). Y ("Y:RINGS"): page 3, cursor on the
;   rings (the rings left the Ring Box submenu). R: Quest page.
;
; Page 3 (state $06 while MenuScrollLevelH != 0):
; - Rings in two rows of three (ring-box order), masks in one row of five.
; - D-pad moves the cursor over all 11 slots.
; - A or Y on an owned mask: equip it. The mask stays an ordinary Y item:
;   $0202 = its item ID ($13-$17), exactly as picking it in the grid;
;   Menu_Exit copies it to $0303 when the menu closes.
; - A or Y on an owned ring: equip it (RingMenu_StoreRingToSlotStack,
;   the Ring Box rule), or unequip it when it is already equipped.
; - Red brackets mark the equipped mask and the equipped rings; the
;   blinking white bracket is the cursor. The name bar shows the item
;   under the cursor; row 11 shows the ring's effect.
; - X: Journal (its A returns to page 3). L/R: back to Items. Start: close.
;
; The page is redrawn into the $1000 buffer and uploaded to the right
; screen ($0116 = $23, VRAM $6C00) every frame, as the Ring Box does.
;
; RAM: MenuScrollLevelH ($7E0731) = target of the last page turn from
; Items: $00 Quest, $20 page 3 (L), $21 page 3 (Y). $020B = page-3
; cursor slot: 0-5 rings (Power, Armor, Heart, Light, Blast, Steadfast),
; 6-10 masks (Deku, Zora, Wolf, Bunny, Stone).
;
; Assembled at the end of bank $2D (after menu_map_names.asm) and reached
; through the Menu_Entry vectors $04-$06, so no flag-off code moves.
;
; M2 (2026-09-28, decisions.org "layout A, one ring"; each part default off):
; - !ENABLE_MENU_PAGE3_LAYOUT_A: Items/Quest frame, masks on grid row 1
;   (+ an empty spare cell), rings on grid row 3, red brackets on the worn
;   mask/ring, no "A:EQUIP  X:LOG" prompt (X still opens the Journal).
;   Slot numbers stay: 0-5 rings, 6-10 masks; the spare cell is no slot.
; - !ENABLE_ONE_RING: one worn ring (RingSlot1); A on it takes it off.
; - !ENABLE_MENU_PAGE_LOOP: Masks&Rings <- Items -> Quest, wrapping. Items
;   stays on the left BG3 half, Quest and page 3 on the right one. A Quest
;   <-> page 3 turn draws the target into the left half, scrolls there in
;   the button's direction, then uploads it to the right half and sets
;   $E4 = $0100 in one frame (Menu_Page3_ScrollTo). Leaving for Items redraws
;   Items first (Menu_Page3_ScrollFrom). No Y shortcut to the rings.
; - !ENABLE_PORTAL_ROD_CELL: the Deku cell ($13, empty in the grid) shows
;   the Portal Rod, whose Y-item value is $19 (Menu_PortalRod_*).
; =========================================================

if !ENABLE_RING_SRAM_RELOCATE == 0
  error "!ENABLE_MENU_PAGE3 needs !ENABLE_RING_SRAM_RELOCATE = 1 (legacy ring bytes alias side-quest data)"
endif

!P3_FirstMaskSlot = $06
!P3_SlotCount     = $0B
if !ENABLE_MENU_PAGE3_LAYOUT_A == 1
!P3_EffectRow     = 21        ; ring effect line: below ring row 3
else
!P3_EffectRow     = 11
endif

; ---------------------------------------------------------
; State $04 wrapper: record the L/R target, Y opens page 3 on the rings,
; then run the item screen.
; In: DBR = $2D.
Menu_Page3_ItemScreen:
{
  SEP #$30
  LDA.b $F6 : BIT.b #$30 : BEQ .no_lr   ; L = $20, R = $10
    AND.b #$20 : STA.w MenuScrollLevelH ; L wins, as in Menu_CheckHScroll
    JMP Menu_ItemScreen
  .no_lr

if !ENABLE_MENU_PAGE_LOOP == 0
  ; Y without Start or A: page 3, cursor on the rings.
  LDA.b $F4 : AND.b #$50 : CMP.b #$40 : BNE .no_y
  BIT.b $F6 : BMI .no_y                 ; A closes the menu first
if !ENABLE_MENU_HIDE_RINGS_JOURNAL_EARLY == 1
  JSR Menu_CheckRingsUnlocked : BCC .no_y
endif
    LDA.b #$21 : STA.w MenuScrollLevelH
    REP #$20
    LDA.w #$FFF8 : STA.w MenuScrollHDirection
    SEP #$20
    LDA.b #!MENU_STATE_SCROLL_TO : STA.w $0200
    LDA.b #$06 : STA.w $012F            ; same sound as Menu_CheckHScroll
    RTS
  .no_y
endif

  ; No owned item left in the grid (masks only): ignore the D-pad, or
  ; Menu_FindNext*Item would stop on an empty cell.
  LDA.b $F4 : AND.b #$0F : BEQ .items
if !ENABLE_PORTAL_ROD_CELL == 1
    JSR Menu_Page3_GridHasItem : BCS .grid_move
else
    JSR Menu_Page3_GridHasItem : BCS .items
endif
      LDA.b $F4 : AND.b #$F0 : STA.b $F4
if !ENABLE_PORTAL_ROD_CELL == 1
      BRA .items
    .grid_move
    ; From the Portal Rod ($19) search from its cell ($13), so the move
    ; follows the grid; Menu_ItemScreen turns a $13 result back into $19.
    LDA.w $0202 : CMP.b #$19 : BNE .items
      LDA.b #$13 : STA.w $0202
endif
  .items
  JMP Menu_ItemScreen
}

; ---------------------------------------------------------
; State $05 wrapper: repaint the right screen on the first frame.
; $E4 low byte is 0 only on that frame: the scroll starts at $0000 and
; the state changes on the frame it reaches $0100.
Menu_Page3_ScrollTo:
{
  SEP #$20
  LDA.b $E4 : BNE .scrolling
    LDA.w MenuScrollLevelH : BEQ .quest
      JSR Menu_Page3_InitCursor
      JSR Menu_Page3_Draw
      BRA .upload
    .quest
    JSR Menu_RefreshQuestScreen
    .upload
    SEP #$30
if !ENABLE_MENU_PAGE_LOOP == 1
    ; From Items: the right half. From Quest or page 3 ($E5 = 1): the left
    ; half, which the scroll reaches by wrapping.
    LDA.b #$23
    LDX.b $E5 : BEQ .half
      LDA.b #$22
    .half
    STA.w $0116
else
    LDA.b #$23 : STA.w $0116             ; right screen ($6C00)
endif
    LDA.b #$01 : STA.b $17
  .scrolling
  SEP #$20
if !ENABLE_MENU_PAGE_LOOP == 1
  JSR Menu_ScrollHorizontal : BCC .loop_not_done ; returns with 16-bit A
    SEP #$30
    LDA.b $E5 : BNE .home
      ; A Quest <-> page 3 turn ends on the left half ($E4 = 0). The buffer
      ; still holds the page: upload it to the right half and set $E4 =
      ; $0100 in the same frame, so Items keeps the left half.
      LDA.b #$23 : STA.w $0116
      LDA.b #$01 : STA.b $17
      STA.b $E5
    .home
    INC.w $0200                          ; $06: Menu_Page3_StatsScreen
  .loop_not_done
  SEP #$30
  RTS
else
  LDA.w MenuScrollLevelH : BNE .page3
    JMP Menu_ScrollTo                    ; Quest: unchanged path

  .page3
  JSR Menu_ScrollHorizontal : BCC .not_done   ; returns with 16-bit A
    SEP #$20
    INC.w $0200                          ; $06: Menu_Page3_StatsScreen
  .not_done
  SEP #$20
  RTS
endif
}

; ---------------------------------------------------------
; State $06 wrapper: page 3, or the Quest screen.
Menu_Page3_StatsScreen:
{
  SEP #$30
  LDA.w MenuScrollLevelH : BNE .page3
if !ENABLE_MENU_PAGE_LOOP == 1
    ; Quest. R goes on to page 3; Start, L and A as before (same order as
    ; Menu_CheckHScroll: Start, L, R).
    LDA.b $F4 : BIT.b #$10 : BNE .quest
    LDA.b $F6 : BIT.b #$20 : BNE .quest
    BIT.b #$10 : BEQ .quest
      LDA.b #$20 : STA.w MenuScrollLevelH ; target: page 3
      REP #$20
      LDA.w #$0008                        ; R: it comes in from the right
      BRA .turn_to_right_page
    .quest
endif
    JMP Menu_StatsScreen

  .page3
  LDA.b $F4 : BIT.b #$10 : BEQ .no_start
    LDA.b #!MENU_STATE_INIT_SCROLL_DOWN : STA.w $0200
    RTS
  .no_start

  LDA.b $F6 : BIT.b #$20 : BNE .left
  BIT.b #$10 : BEQ .no_lr
    REP #$20
    LDA.w #$0008
    BRA .scroll
  .left
if !ENABLE_MENU_PAGE_LOOP == 1
    ; L: Quest, coming in from the left (state $05 draws it).
    STZ.w MenuScrollLevelH
    REP #$20
    LDA.w #$FFF8
  .turn_to_right_page
    STA.w MenuScrollHDirection
    SEP #$30
    LDA.b #!MENU_STATE_SCROLL_TO : STA.w $0200
    LDA.b #$06 : STA.w $012F
    RTS
else
    REP #$20
    LDA.w #$FFF8
endif
  .scroll
  STA.w MenuScrollHDirection
  SEP #$30
  LDA.b #!MENU_STATE_SCROLL_FROM : STA.w $0200
  LDA.b #$06 : STA.w $012F
  RTS
  .no_lr

  ; X: Journal. Its A returns here (Menu_Page3_JournalReturn).
  LDA.b $F6 : BIT.b #$40 : BEQ .no_x
if !ENABLE_MENU_HIDE_RINGS_JOURNAL_EARLY == 1
    JSR Menu_CheckJournalUnlocked : BCC .no_x
endif
    LDA.b #!MENU_STATE_JOURNAL : STA.w $0200
    REP #$20
    LDA.w #$0000 : STA.l JournalState    ; first page
    JSL Menu_DrawJournal
    SEP #$30
    LDA.b #$23 : STA.w $0116
    LDA.b #$01 : STA.b $17
    LDA.b #$11 : STA.w $012F
    RTS
  .no_x

  JSR Menu_Page3_Move
  JSR Menu_Page3_Select
  INC.w $0207                            ; cursor blink
  JSR Menu_Page3_Draw
  LDA.b #$23 : STA.w $0116
  LDA.b #$01 : STA.b $17
  RTS
}

; ---------------------------------------------------------
; Journal A on the right side: redraw page 3 or the Quest page.
; Called by Menu_Journal. Out: SEP #$30.
Menu_Page3_JournalReturn:
{
  SEP #$30
  LDA.w MenuScrollLevelH : BNE .page3
    JMP Menu_RefreshQuestScreen
  .page3
  JMP Menu_Page3_Draw
}

; ---------------------------------------------------------
; In: A = item ID, 8-bit A. Out: C set = mask ($13-$17). Keeps A, X, Y.
Menu_Page3_IsMaskItem:
{
  CMP.b #$13 : BCC .no
  CMP.b #$18 : BCS .no_c
    SEC
    RTS
  .no_c
  CLC
  .no
  RTS
}

; ---------------------------------------------------------
; Item-grid filter for Menu_FindNext*Item (Menu/menu_select_item.asm).
; In: A = owned value of item $0202, 8-bit A.
; Out: A = 0 when $0202 is a mask, else A unchanged; N/Z follow A.
Menu_Page3_GridFilter:
{
  PHA
  LDA.w $0202
if !ENABLE_PORTAL_ROD_CELL == 1
  CMP.b #$13 : BNE .not_portal_cell
    PLA
    LDA.l PortalRodOwned                 ; cell $13 holds the Portal Rod
    RTS
  .not_portal_cell
endif
  JSR Menu_Page3_IsMaskItem
  PLA
  BCC .keep
    LDA.b #$00
  .keep
  RTS
}

; ---------------------------------------------------------
; Out: C set = the player owns an item that the grid shows (not a mask).
; 8-bit A/X/Y. Keeps X, Y.
Menu_Page3_GridHasItem:
{
  PHX : PHY
if !ENABLE_PORTAL_ROD_CELL == 1
  LDA.l PortalRodOwned : BNE .found
endif
  LDY.b #$17                   ; table index (item ID - 1)
  .loop
    CPY.b #$12 : BCC .check
    CPY.b #$17 : BCC .next     ; $12-$16 = masks $13-$17
    .check
    TYX
    LDA.l Menu_AddressLong, X : TAX
    LDA.l $7EF300, X : BNE .found
    .next
    DEY : BPL .loop
  PLY : PLX
  CLC
  RTS
  .found
  PLY : PLX
  SEC
  RTS
}

; ---------------------------------------------------------
; Cursor slot when page 3 opens. Out: $020B, $0207 = 0, SEP #$30.
Menu_Page3_InitCursor:
{
  SEP #$30
  STZ.w $0207
  LDA.w MenuScrollLevelH : LSR : BCS .rings  ; opened with Y

  LDA.w $0202 : JSR Menu_Page3_IsMaskItem : BCC .first_mask
    SEC : SBC.b #$13-!P3_FirstMaskSlot
    STA.w $020B
    RTS

  .first_mask
  LDY.b #$00
  .mask_loop
    TYX
    LDA.l Menu_AddressLong+$12, X : TAX
    LDA.l $7EF300, X : BNE .mask_found
    INY : CPY.b #$05 : BCC .mask_loop
  BRA .rings
  .mask_found
  TYA : CLC : ADC.b #!P3_FirstMaskSlot
  STA.w $020B
  RTS

  .rings
  LDY.b #$00
  .ring_loop
    LDA.w Menu_Page3_RingBits, Y : AND.l MAGICRINGS : BNE .ring_found
    INY : CPY.b #$06 : BCC .ring_loop
  LDY.b #$00
  .ring_found
  STY.w $020B
  RTS
}

; ---------------------------------------------------------
; D-pad: move the cursor with Menu_Page3_Nav. 8-bit A/X/Y.
Menu_Page3_Move:
{
  LDA.b $F4 : AND.b #$0F : BEQ .done
  LDX.b #$00
  LSR : BCS .go                ; right
  INX : LSR : BCS .go          ; left
  INX : LSR : BCS .go          ; down
  INX                          ; up
  .go
  STX.b $00
  LDA.w $020B : CMP.b #!P3_SlotCount : BCC .slot_ok
    LDA.b #$00
  .slot_ok
  ASL : ASL : ORA.b $00 : TAX
  LDA.w Menu_Page3_Nav, X : STA.w $020B
  STZ.w $0207                  ; show the cursor at once
  LDA.b #$20 : STA.w $012F     ; cursor move sound, as in the grid
  .done
  RTS
}

; ---------------------------------------------------------
; A or Y: equip the mask, or toggle the ring, under the cursor.
; 8-bit A/X/Y.
Menu_Page3_Select:
{
  BIT.b $F6 : BMI .pressed               ; A
  LDA.b $F4 : BIT.b #$40 : BEQ .done     ; Y
  .pressed
  LDA.w $020B : CMP.b #!P3_FirstMaskSlot : BCS .mask
    TAY
    LDA.w Menu_Page3_RingBits, Y : AND.l MAGICRINGS : BEQ .error
    TYA : INC : INC                      ; ring ID = slot + 2
    JMP Menu_Page3_ToggleRing

  .mask
  CMP.b #!P3_SlotCount : BCS .error
  SEC : SBC.b #!P3_FirstMaskSlot : TAX
  LDA.l Menu_AddressLong+$12, X : TAX
  LDA.l $7EF300, X : BEQ .error
    LDA.w $020B : CLC : ADC.b #$13-!P3_FirstMaskSlot
    STA.w $0202                          ; the Y item, as in the grid
    LDA.b #$20 : STA.w $0207             ; show the new marker first
    LDA.b #$22 : STA.w $012F             ; equip sound (Ring Box)
    RTS

  .error
  LDA.b #$3C : STA.w $012E               ; error sound (Magic Bag)
  .done
  RTS
}

; ---------------------------------------------------------
; In: A = ring ID (2-7), 8-bit A. Unequips the ring when it is in a
; slot, else equips it with the Ring Box rule (first free slot, or push
; out slot 1 when all three are full).
Menu_Page3_ToggleRing:
{
if !ENABLE_ONE_RING == 1
  ; One ring: A on the worn ring takes it off; another ring replaces it.
  CMP.l RingSlot1 : BNE .wear
    LDA.b #$00 : STA.l RingSlot1
    LDA.b #$20 : STA.w $012F
    STZ.w $0207
    RTS
  .wear
  STA.l RingSlot1
  LDA.b #$22 : STA.w $012F
  LDA.b #$20 : STA.w $0207               ; show the new marker first
  RTS
else
  CMP.l RingSlot1 : BNE .not_1
    LDA.b #$00 : STA.l RingSlot1
    BRA .off
  .not_1
  CMP.l RingSlot2 : BNE .not_2
    LDA.b #$00 : STA.l RingSlot2
    BRA .off
  .not_2
  CMP.l RingSlot3 : BNE .on
    LDA.b #$00 : STA.l RingSlot3
  .off
  LDA.b #$20 : STA.w $012F
  STZ.w $0207
  RTS

  .on
  JSR RingMenu_StoreRingToSlotStack
  SEP #$30
  LDA.b #$22 : STA.w $012F
  LDA.b #$20 : STA.w $0207               ; show the new marker first
  RTS
endif
}

; ---------------------------------------------------------
; Layout A: draw page 3 into the $1000-$17FF buffer. Items/Quest frame and
; tabs (menu_frame), title, masks on grid row 1 (Deku Zora Wolf Bunny Stone;
; the 6th cell stays empty for a future bonus mask), rings on grid row 3,
; red brackets on the worn mask and the worn ring, then the white cursor,
; the name bar and the ring effect line. Rows 1 and 3 each hold one red
; bracket at most and are two rows apart, so red brackets never touch.
; Out: SEP #$30.
if !ENABLE_MENU_PAGE3_LAYOUT_A == 1
Menu_Page3_Draw:
{
  JSR Menu_DrawBackground                ; menu_frame (single border, tabs)
  SEP #$30
  LDA.b #$7E : STA.b $0A                 ; bank of DrawMenuItem's [$08]
  REP #$30

  LDX.w #$16                             ; 12 tiles
  .title
    LDA.w .title_txt, X : STA.w $1000+menu_offset(6,10), X
    DEX : DEX
  BPL .title

  ; Masks: grid row 1, icons r11-12 (blank when not owned).
  LDA.w #$7EF349
  LDX.w #menu_offset(7,3)
  LDY.w #DekuMaskGFX
  JSR DrawMenuItem

  LDA.w #$7EF347
  LDX.w #menu_offset(7,6)
  LDY.w #ZoraMaskGFX
  JSR DrawMenuItem

  LDA.w #$7EF358
  LDX.w #menu_offset(7,9)
  LDY.w #WolfMaskGFX
  JSR DrawMenuItem

  LDA.w #$7EF348
  LDX.w #menu_offset(7,13)
  LDY.w #BunnyHoodGFX
  JSR DrawMenuItem

  LDA.w #$7EF352
  LDX.w #menu_offset(7,16)
  LDY.w #StoneMaskGFX
  JSR DrawMenuItem

  ; Rings: grid row 3, icons r17-18, ring order. Owned: RingGFX entry
  ; slot + 2; not owned: the grey ring (entry 1), as in the Ring Box.
  LDY.w #$0000
  .ring
    PHY
    SEP #$20
    LDA.w Menu_Page3_RingBits, Y : AND.l MAGICRINGS
    REP #$20
    AND.w #$00FF : BEQ .grey_ring
      TYA : INC : INC
      BRA .ring_value
    .grey_ring
    LDA.w #$0001
    .ring_value
    STA.w MenuItemValueSpoof
    TYA : ASL : TAX
    LDA.w .ring_pos, X : TAX
    LDA.w #MenuItemValueSpoof
    LDY.w #RingGFX
    JSR DrawMenuItem
    PLY
    INY : CPY.w #$0006
  BCC .ring

  ; Red brackets: the worn mask (the Y item), then the worn ring.
  SEP #$30
  LDA.w $0202 : JSR Menu_Page3_IsMaskItem : BCC .no_mask
    SEC : SBC.b #$13-!P3_FirstMaskSlot
    JSR .marker
  .no_mask
  LDA.l RingSlot1 : SEC : SBC.b #$02 : CMP.b #$06 : BCS .no_ring
    JSR .marker
  .no_ring

  ; Cursor: white bracket, hidden every other 32 frames. Drawn last, so it
  ; shows on a worn cell; a neighbour's red bracket shares one edge column
  ; with it (Items-grid spacing), as grid neighbours do on the Items page.
  LDA.w $0207 : AND.b #$20 : BNE .no_cursor
    LDA.w $020B : CMP.b #!P3_SlotCount : BCS .no_cursor
    ASL : TAX
    REP #$30
    LDA.w Menu_Page3_CursorPos, X : TAX
    LDA.w #$3060
    JSR Menu_Page3_Bracket
  .no_cursor

  JSR Menu_Page3_DrawNames
  SEP #$30
  RTS

  ; In: A = slot (0-10), 8-bit. Red bracket (palette 1).
  .marker
  ASL : TAX
  REP #$30
  LDA.w Menu_Page3_CursorPos, X : TAX
  LDA.w #$2460
  JSR Menu_Page3_Bracket
  SEP #$30
  RTS

  .title_txt
    dw "MASKS"
    dw $2017, $2017
    dw "RINGS"

  ; Ring icon offsets: grid row 3, Items-page columns.
  .ring_pos
    dw menu_offset(13,3), menu_offset(13,6), menu_offset(13,9)
    dw menu_offset(13,13), menu_offset(13,16), menu_offset(13,19)
}
else
; ---------------------------------------------------------
; Draw page 3 into the $1000-$17FF buffer: ring-box frame, side tabs,
; title, prompt, rings, masks, equipped markers, cursor, names.
; Out: SEP #$30.
Menu_Page3_Draw:
{
  JSR Menu_DrawRingBox                   ; ring_box.tilemap
  JSR Menu_DrawMagicRingsInBox           ; sets $0A = $7E for DrawMenuItem

  REP #$30
  ; L/R tabs from the Items/Quest frame (rows 15-17, columns 1-3, 28-30).
  LDX.w #$0004
  .tabs
    LDA.w menu_frame+menu_offset(15,1), X  : STA.w $1000+menu_offset(15,1), X
    LDA.w menu_frame+menu_offset(16,1), X  : STA.w $1000+menu_offset(16,1), X
    LDA.w menu_frame+menu_offset(17,1), X  : STA.w $1000+menu_offset(17,1), X
    LDA.w menu_frame+menu_offset(15,28), X : STA.w $1000+menu_offset(15,28), X
    LDA.w menu_frame+menu_offset(16,28), X : STA.w $1000+menu_offset(16,28), X
    LDA.w menu_frame+menu_offset(17,28), X : STA.w $1000+menu_offset(17,28), X
    DEX : DEX
  BPL .tabs

  LDX.w #$16                             ; 12 tiles
  .title
    LDA.w .title_txt, X : STA.w $1000+menu_offset(6,10), X
    DEX : DEX
  BPL .title

  LDX.w #$0C                             ; "A:EQUIP" = 7 tiles
  .equip
    LDA.w .equip_txt, X : STA.w $1000+menu_offset(10,8), X
    DEX : DEX
  BPL .equip

if !ENABLE_MENU_HIDE_RINGS_JOURNAL_EARLY == 1
  JSR Menu_CheckJournalUnlocked : BCC .no_log
endif
  LDX.w #$08                             ; "X:LOG" = 5 tiles
  .log
    LDA.w .log_txt, X : STA.w $1000+menu_offset(10,19), X
    DEX : DEX
  BPL .log
  .no_log

  ; Masks: icon rows 20-21, columns 9/12/15/18/21 (blank when not owned).
  LDA.w #$7EF349
  LDX.w #menu_offset(16,5)
  LDY.w #DekuMaskGFX
  JSR DrawMenuItem

  LDA.w #$7EF347
  LDX.w #menu_offset(16,8)
  LDY.w #ZoraMaskGFX
  JSR DrawMenuItem

  LDA.w #$7EF358
  LDX.w #menu_offset(16,11)
  LDY.w #WolfMaskGFX
  JSR DrawMenuItem

  LDA.w #$7EF348
  LDX.w #menu_offset(16,14)
  LDY.w #BunnyHoodGFX
  JSR DrawMenuItem

  LDA.w #$7EF352
  LDX.w #menu_offset(16,17)
  LDY.w #StoneMaskGFX
  JSR DrawMenuItem

  ; Red brackets: equipped rings, then the equipped mask.
  SEP #$30
  LDA.l RingSlot1 : JSR .ring_marker
if !ENABLE_ONE_RING == 0
  LDA.l RingSlot2 : JSR .ring_marker
  LDA.l RingSlot3 : JSR .ring_marker
endif
  LDA.w $0202 : JSR Menu_Page3_IsMaskItem : BCC .no_mask
    SEC : SBC.b #$13-!P3_FirstMaskSlot
    JSR .equipped_marker
  .no_mask

  ; Cursor: white bracket, hidden every other 32 frames.
  SEP #$30
  LDA.w $0207 : AND.b #$20 : BNE .no_cursor
    LDA.w $020B : CMP.b #!P3_SlotCount : BCS .no_cursor
    ASL : TAX
    REP #$30
    LDA.w Menu_Page3_CursorPos, X : TAX
    LDA.w #$3060
    JSR Menu_Page3_Bracket
  .no_cursor

  JSR Menu_Page3_DrawNames
  SEP #$30
  RTS

  ; In: A = ring ID from a ring slot, 8-bit. Draws nothing for 0 or a bad ID.
  .ring_marker
  SEC : SBC.b #$02 : CMP.b #$06 : BCS .marker_done
  ; In: A = slot (0-10), 8-bit.
  .equipped_marker
  ASL : TAX
  REP #$30
  LDA.w Menu_Page3_CursorPos, X : TAX
  LDA.w #$2460
  JSR Menu_Page3_Bracket
  SEP #$30
  .marker_done
  RTS

  .title_txt
    dw "MASKS"
    dw $2017, $2017
    dw "RINGS"
  .equip_txt
    dw "A:EQUIP"
  .log_txt
    dw "X:LOG"
}
endif

; ---------------------------------------------------------
; Bracket (cursor shape) around one icon.
; In: X = cursor offset (as Menu_ItemCursorPositions), A = corner tile
; ($3060 white, palette 4; $2460 red, palette 1). 16-bit A/X. Keeps X.
Menu_Page3_Bracket:
{
  PHA
  STA.w $1108, X                         ; top left
  ORA.w #$8000 : STA.w $11C8, X          ; bottom left (V flip)
  ORA.w #$4000 : STA.w $11CE, X          ; bottom right (HV flip)
  EOR.w #$8000 : STA.w $110E, X          ; top right (H flip)
  CLC : ADC.w #$0010
  STA.w $114E, X : STA.w $118E, X        ; right edge
  PLA
  CLC : ADC.w #$0010
  STA.w $1148, X : STA.w $1188, X        ; left edge
  RTS
}

; ---------------------------------------------------------
; Name bar ($1692, 14 tiles) and ring effect (!P3_EffectRow, 16 tiles) for the
; slot under the cursor. Unowned slots leave the frame as drawn.
Menu_Page3_DrawNames:
{
  SEP #$30
  LDA.w $020B : CMP.b #!P3_SlotCount : BCC .slot_ok
    JMP .done
  .slot_ok
  CMP.b #!P3_FirstMaskSlot : BCS .mask

  TAY
  LDA.w Menu_Page3_RingBits, Y : STA.b $00
  AND.l MAGICRINGS : BNE .ring_owned
    LDA.l FOUNDRINGS : AND.b $00 : BEQ .done
      REP #$30
      LDX.w #Menu_RingsFound             ; found, not appraised yet
      BRA .name
  .ring_owned
  REP #$30
  LDA.w $020B : AND.w #$00FF : ASL #5 : TAX
  LDY.w #$0000
  .desc
    LDA.w Menu_RingDescriptions, X : STA.w $1000+menu_offset(!P3_EffectRow,8), Y
    INX #2 : INY #2
  CPY.w #$0020 : BCC .desc
  LDA.w $020B : AND.w #$00FF : ASL #5
  CLC : ADC.w #Menu_RingNames : TAX
  BRA .name

  .mask
  SEC : SBC.b #!P3_FirstMaskSlot : TAX
  LDA.l Menu_AddressLong+$12, X : TAX
  LDA.l $7EF300, X : BEQ .done
  REP #$30
  LDA.w $020B : AND.w #$00FF
  CLC : ADC.w #$13-1-!P3_FirstMaskSlot   ; Menu_ItemNames row of the mask
  ASL #5
  CLC : ADC.w #Menu_ItemNames : TAX

  .name
  LDY.w #$0000
  .name_loop
    LDA.w $0000, X : STA.w $1692, Y
    INX #2 : INY #2
  CPY.w #$001C : BCC .name_loop

  .done
  SEP #$30
  RTS
}

; Ring bits in slot order (MAGICRINGS ..pa hlbs; as RingMenu_Controls).
Menu_Page3_RingBits:
  db $20, $10, $08, $04, $02, $01

; Cursor offsets per slot (bracket top-left = icon - 1 row - 1 column).
Menu_Page3_CursorPos:
if !ENABLE_MENU_PAGE3_LAYOUT_A == 1
  ; Layout A: the Items grid cursor positions (Menu_ItemCursorPositions).
  dw menu_offset(12,2), menu_offset(12,5), menu_offset(12,8)      ; rings, row 3
  dw menu_offset(12,12), menu_offset(12,15), menu_offset(12,18)
  dw menu_offset(6,2), menu_offset(6,5), menu_offset(6,8)         ; Deku Zora Wolf, row 1
  dw menu_offset(6,12), menu_offset(6,15)                         ; Bunny Stone
else
  dw menu_offset(8,6), menu_offset(8,10), menu_offset(8,14)       ; rings 1-3
  dw menu_offset(12,6), menu_offset(12,10), menu_offset(12,14)    ; rings 4-6
  dw menu_offset(15,4), menu_offset(15,7), menu_offset(15,10)     ; Deku Zora Wolf
  dw menu_offset(15,13), menu_offset(15,16)                       ; Bunny Stone
endif

; Next slot per direction: right, left, down, up.
;   0 1 2         rings
;   3 4 5
;  6 7 8 9 10     masks
Menu_Page3_Nav:
if !ENABLE_MENU_PAGE3_LAYOUT_A == 1
; Layout A:
;   6 7 8 9 10 .    masks, grid row 1 (the spare cell is no slot)
;   0 1 2 3 4  5    rings, grid row 3
; Rows wrap; Up and Down both switch rows; Steadfast pairs with Stone.
  db $01, $05, $06, $06   ; 0 Power
  db $02, $00, $07, $07   ; 1 Armor
  db $03, $01, $08, $08   ; 2 Heart
  db $04, $02, $09, $09   ; 3 Light
  db $05, $03, $0A, $0A   ; 4 Blast
  db $00, $04, $0A, $0A   ; 5 Steadfast
  db $07, $0A, $00, $00   ; 6 Deku
  db $08, $06, $01, $01   ; 7 Zora
  db $09, $07, $02, $02   ; 8 Wolf
  db $0A, $08, $03, $03   ; 9 Bunny
  db $06, $09, $04, $04   ; 10 Stone
else
  db $01, $02, $03, $07   ; 0 Power
  db $02, $00, $04, $08   ; 1 Armor
  db $00, $01, $05, $09   ; 2 Heart
  db $04, $05, $07, $00   ; 3 Light
  db $05, $03, $08, $01   ; 4 Blast
  db $03, $04, $09, $02   ; 5 Steadfast
  db $07, $0A, $00, $03   ; 6 Deku
  db $08, $06, $00, $03   ; 7 Zora
  db $09, $07, $01, $04   ; 8 Wolf
  db $0A, $08, $02, $05   ; 9 Bunny
  db $06, $09, $02, $05   ; 10 Stone
endif

if !ENABLE_MENU_PAGE_LOOP == 1
; ---------------------------------------------------------
; State $07 wrapper (page loop): a Quest <-> page 3 turn leaves a copy of
; that page on the left half, so draw Items there on the first frame
; ($E4 = $0100, low byte 0), before any of it scrolls into view.
Menu_Page3_ScrollFrom:
{
  SEP #$20
  LDA.b $E4 : BNE .scrolling
    JSR Menu_RefreshInventoryScreen      ; returns SEP #$30
    LDA.b #$22 : STA.w $0116             ; left half
    LDA.b #$01 : STA.b $17
  .scrolling
  JMP Menu_ScrollFrom
}
endif

if !ENABLE_PORTAL_ROD_CELL == 1
; ---------------------------------------------------------
; Menu open (Menu_InitGraphics): PortalRodOwned follows Maple's upgrade
; (CustomRods $7EF351 1 -> 2), so saves from before the cell show it.
; 8-bit A. Keeps X, Y.
Menu_PortalRod_SyncOwned:
{
  LDA.l $7EF351 : CMP.b #$02 : BCC .done
    LDA.b #$01 : STA.l PortalRodOwned
  .done
  RTS
}

; ---------------------------------------------------------
; After a grid move (Menu_ItemScreen .draw_cursor): the search visits the
; Deku cell $13 only when it holds the Portal Rod (Menu_Page3_GridFilter),
; so $0202 = $13 there means the Portal Rod ($19). 8-bit A.
Menu_PortalRod_CellToItem:
{
  LDA.w $0202 : CMP.b #$13 : BNE .done
    LDA.b #$19 : STA.w $0202
  .done
  RTS
}
endif

assert pc() <= $2E8000, "Menu/menu_page3.asm overflows bank $2D"
