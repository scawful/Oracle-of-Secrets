; =========================================================
; 2-item HUD layout (HUD_LAYOUT_02/03).
; Included from Items/all_items.asm (assembled at $548800+; Menu bank $2E
; has no room before the D8 boss slot ($2EB800) and bank $2B is full). Template,
; cell defines, floor spot and the $008B82 NMI hook live in Menu/menu_hud.asm.
;
; Claims:
;   WRAM HudCornerBuffer $7EC84A-$7EC857 (14 bytes, Core/symbols.asm;
;     vanilla-free gap after the RebuildHUD copy, usdasm UNUSED_7EC84A).
;   BG3 CHR tile $014 = VRAM word $70A0-$70A7 (blank in the HUD sheet; no
;     HUD or menu tilemap uses it). Re-uploaded on every HUD NMI upload, so
;     sheet reloads (menu, transitions) cannot leave it stale.

; ---------------------------------------------------------
; Cells HUD_Update cannot reach without the template: the X item icon and
; X count in the wide item box, and the rupee and key icons of the bottom
; corners (HUD_Update writes the digits and blanks the key icon when Link
; has no keys, after this call).
; X is valid only when ItemBindingSavedVersion == 1 and the saved X item is
; owned and latchable (ItemBindings_IsLatchable). The icon comes from the
; same HudItems tables as the Y box ($0DFA93 pointer per item; entry = 4
; words: top-left, top-right, bottom-left, bottom-right), indexed by the
; ownership level like HUD_UpdateItemBox (Bombs level 1, Hookshot level 0).
; Bow shows the arrow count, Bombs the bomb count and Bombchu its ammo
; (two digits, like the Y count) in the box's bottom border. Portal,
; Goldstar, Bombchu and Switch Hook use the Y box's icon choices.
; In: A/X/Y 16-bit, any DBR. Out: A/X/Y 16-bit, A and X clobbered.
HUD_CodexCells:
{
  LDA.w #$3CA8 : STA.l HudCornerBuffer          ; rupee icon, bottom left
  LDA.w #$FCA8 : STA.l HudCornerBuffer+2
  LDA.w #$2071 : STA.l HudCornerBuffer+$0A      ; key icon, bottom right

  PHY
  ; Forms ItemBindings_Admitted rejects (Deku/Zora/Wolf/Goron, Garo,
  ; Horse without mounted bow) route X to the field map, so the X box stays
  ; empty under them. Mounted Horse ($09) keeps Bow ($01) visible when no
  ; follower rides along, matching ItemBindings_Admitted.
  LDA.l $7E0000+!CurrentMask : AND.w #$00FF : BEQ .form_ok
  CMP.w #$0005 : BCC .empty
  CMP.w #$0008 : BCC .form_ok
if !ENABLE_HORSE_FORM == 1
  CMP.w #$0009 : BNE .empty
  LDA.l $7EF3CC : AND.w #$00FF : BNE .empty
  LDA.l ItemBindingSavedX : AND.w #$00FF : CMP.w #$0001 : BEQ .form_ok
endif
  BRA .empty
  .form_ok
  LDA.l ItemBindingSavedVersion : AND.w #$00FF : CMP.w #$0001 : BNE .empty
  LDA.l ItemBindingSavedX : AND.w #$00FF : BEQ .empty
  JSL ItemBindings_IsLatchable : BCS .icon

  .empty
    LDA.w #$20AA                                ; item box background
    STA.l $7EC770 : STA.l $7EC772 : STA.l $7EC7B0 : STA.l $7EC7B2
  .no_count
    LDA.w #$207D : STA.l $7EC7F0                ; box bottom under the X icon
    LDA.w #$A014 : STA.l $7EC7F2
    PLY
    RTL

  .icon
    TAY                                         ; Y = item ID
    CPY.w #$000D : BEQ .ocarina_icon
if !ENABLE_GOLDSTAR_CELL == 1
    CPY.w #$001B : BCS .new_icon                ; Byrna, Bombchu, Gust Jar / Switch Hook
endif
    ; Logical cells draw like the Y box: Portal = rod entry level 1,
    ; Goldstar = hookshot entry level 1. Neither has a count.
    CPY.w #$0019 : BNE +
      LDY.w #$0010 : LDA.w #$0001 : BRA .level
    +
if !ENABLE_GOLDSTAR_CELL == 1
    CPY.w #$001A : BNE +
      LDY.w #$0003 : LDA.w #$0001 : BRA .level
    +
endif
    TAX
    LDA.l Menu_AddressIndex-1, X : AND.w #$00FF : TAX
    LDA.l $7EF300, X : AND.w #$00FF             ; ownership level
    CPY.w #$0004 : BNE +
      LDA.w #$0001                              ; Bombs: count, one icon
    +
    CPY.w #$0010 : BNE +
      LDA.w #$0000                              ; Fishing Rod: entry 0 at $0DF8A9
    +
    CPY.w #$0003 : BNE +
if !ENABLE_GOLDSTAR_CELL == 1
      CMP.w #$0002 : BNE .x_hookshot_icon
        LDY.w #$001F : BRA .new_icon            ; Switch Hook ($7EF342 == 2)
      .x_hookshot_icon
      LDA.w #$0000                              ; Hookshot cell: hookshot icon
else
      LDA.w GoldstarOrHookshot : AND.w #$00FF : DEC
endif
    +
    .level
    ASL #3 : PHA
    TYA : DEC : ASL : TAX
    LDA.l $0DFA93, X : CLC : ADC 1,S : TAX
    PLA
    LDA.w #$000D
    BRA .blit_bank
if !ENABLE_GOLDSTAR_CELL == 1
  ; Prototype cells past vanilla's pointer table: the Y box's own icons
  ; (HUD_DrawItem .new_icons, 4 words per item from Byrna $1B).
  .new_icon
    TYA : SEC : SBC.w #$001B : ASL #3           ; values 0..4: ASL #3 clears C
    ADC.w #HUD_DrawItem_new_icons&$FFFF : TAX
    BRA .blit_bank2e
endif
  ; Ocarina ($0D): dynamic song-colored icon from HUD_OcarinaIcons (grey + 6 songs).
  .ocarina_icon
    SEP #$20
    JSL Ocarina_ValidSong_Long
    REP #$20
    AND.w #$00FF : ASL #3                       ; values 0..6: ASL #3 clears C
    ADC.w #HUD_OcarinaIcons&$FFFF : TAX
  .blit_bank2e
if !ENABLE_GOLDSTAR_CELL == 1
    assert (HUD_DrawItem_new_icons>>16) == (HUD_OcarinaIcons>>16)
endif
    LDA.w #HUD_OcarinaIcons>>16
  .blit_bank
    PHB
    SEP #$20 : PHA : PLB : REP #$20
    LDA.w $0000, X : STA.l $7EC770
    LDA.w $0002, X : STA.l $7EC772
    LDA.w $0004, X : STA.l $7EC7B0
    LDA.w $0006, X : STA.l $7EC7B2
    PLB

    CPY.w #$0001 : BNE +
      LDA.l $7EF377 : BRA .count                ; arrows
    +
    CPY.w #$0004 : BNE +
      LDA.l $7EF343 : BRA .count                ; bombs
    +
if !ENABLE_GOLDSTAR_CELL == 1
    CPY.w #$001C : BEQ +
      JMP .no_count
    +
    LDA.l BombchuAmmo : AND.w #$00FF            ; same cap as the Y count
    CMP.w #!BOMBCHU_AMMO_MAX+1 : BCC .count
      LDA.w #$0000
else
    JMP .no_count
endif
    .count
    ; Two digits (tiles $2490-$2499, as HexToDecimal draws).
    AND.w #$00FF
    CMP.w #100 : BCC .count_ok
      LDA.w #99
    .count_ok
    LDX.w #$0000
    .tens
      CMP.w #10 : BCC .ones
      SBC.w #10 : INX
      BRA .tens
    .ones
    ORA.w #$2490 : STA.l $7EC7F2
    TXA : ORA.w #$2490 : STA.l $7EC7F0
    PLY
    RTL
}

; ---------------------------------------------------------
; NMI: after the HUD rows 0-4 DMA, copy the bottom-corner cells (rupees
; bottom left, keys bottom right) and the item-box border strip glyph.
; The HUD buffer upload stops at row 4 (blocker 1 of HUD_LAYOUT_02), so the
; corners have two short DMAs of their own from HudCornerBuffer.
; Hidden HUD (row 0, col 29 low byte $7F: Opening_HideHUD, Dream Wisdom):
; blank $207F cells from the HUD buffer instead, and no glyph upload.
; In: from $008B82, A 8-bit, X/Y 16-bit, DBR $00, DMA0 mode $01 -> $2118,
; VMAIN $80. Out: A = $01; X/Y clobbered (the NMI reloads them).
HUD_NMIUpload:
{
  LDA.b #$01 : STA.w $420B                      ; replaced: HUD rows 0-4

  LDX.w #HudCornerBuffer&$FFFF
  LDA.l $7EC73A : CMP.b #$7F : BNE .shown
    LDX.w #$C700                                ; hidden HUD: blank cells
  .shown
  STX.w $4302
  LDA.b #$7E : STA.w $4304
  LDY.w #$6342 : STY.w $2116                    ; BG3 row 26, col 2
  LDY.w #$000A : STY.w $4305
  LDA.b #$01 : STA.w $420B
  LDY.w #$635C : STY.w $2116                    ; BG3 row 26, col 28
  LDY.w #$0004 : STY.w $4305                    ; source continues at +$0A
  STA.w $420B

  CPX.w #$C700 : BEQ .done
    LDY.w #$70A0 : STY.w $2116                  ; HUD CHR tile $014
    LDY.w #HUD_StripTile&$FFFF : STY.w $4302
    LDA.b #HUD_StripTile>>16 : STA.w $4304
    LDY.w #$0010 : STY.w $4305
    LDA.b #$01 : STA.w $420B
  .done
  RTL
}

; 2bpp item-box border strip: one tile serves the top edge ($2014) and,
; V-flipped, the bottom edge ($A014) of the widened box. Rows 4-7 repeat the
; line rows of the original box border pieces.
HUD_StripTile:
  db $00, $00, $00, $00, $00, $00, $00, $00
  db $FF, $FF, $00, $FF, $FF, $00, $00, $FF
