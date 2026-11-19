; =========================================================
; 2-item HUD layout (HUD_LAYOUT_02/03).
; Included from Items/all_items.asm (assembled at $548800+; Menu bank $2E
; has no room before the D8 boss slot ($2EB800) and bank $2B is full). Template,
; cell defines, floor spot and the $008B82 NMI hook live in Menu/menu_hud.asm.
; HUD_NMIUpload and the 2bpp HUD strip/sun/moon tiles live in
; Overworld/time_system.asm (bank $34) so this file stays within its $200 span.
;
; Claims:
;   WRAM HudCornerBuffer $7EC84A-$7EC857 (14 bytes, Core/symbols.asm;
;     vanilla-free gap after the RebuildHUD copy, usdasm UNUSED_7EC84A).
;   WRAM HudClockBuffer $7EC858-$7EC865 (14 bytes, Core/symbols.asm;
;     contiguous after HudCornerBuffer for row-26 center 12h clock).
;   BG3 CHR tiles $014-$015 = VRAM words $70A0-$70AF (blank in the HUD sheet;
;     no HUD or menu tilemap uses them). Re-uploaded on every HUD NMI upload.

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
    CPY.w #$001B : BCS .new_icon                ; Byrna, Bombchu, Gust Jar / Switch Hook
    ; Logical cells draw like the Y box: Portal = rod entry level 1,
    ; Goldstar = hookshot entry level 1. Neither has a count.
    CPY.w #$0019 : BNE +
      LDY.w #$0010 : LDA.w #$0001 : BRA .level
    +
    CPY.w #$001A : BNE +
      LDY.w #$0003 : LDA.w #$0001 : BRA .level
    +
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
      CMP.w #$0002 : BNE .x_hookshot_icon
        LDY.w #$001F : BRA .new_icon            ; Switch Hook ($7EF342 == 2)
      .x_hookshot_icon
      LDA.w #$0000                              ; Hookshot cell: hookshot icon
    +
    .level
    ASL #3 : PHA
    TYA : DEC : ASL : TAX
    LDA.l $0DFA93, X : CLC : ADC 1,S : TAX
    PLA
    LDA.w #$000D
    BRA .blit_bank
  ; Prototype cells past vanilla's pointer table: the Y box's own icons
  ; (HUD_DrawItem .new_icons, 4 words per item from Byrna $1B).
  .new_icon
    TYA : SEC : SBC.w #$001B : ASL #3           ; values 0..4: ASL #3 clears C
    ADC.w #HUD_DrawItem_new_icons&$FFFF : TAX
    BRA .blit_bank2e
  ; Ocarina ($0D): dynamic song-colored icon from HUD_OcarinaIcons (grey + 6 songs).
  .ocarina_icon
    SEP #$20
    JSL Ocarina_ValidSong_Long
    REP #$20
    AND.w #$00FF : ASL #3                       ; values 0..6: ASL #3 clears C
    ADC.w #HUD_OcarinaIcons&$FFFF : TAX
  .blit_bank2e
    assert (HUD_DrawItem_new_icons>>16) == (HUD_OcarinaIcons>>16)
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
    CPY.w #$001C : BEQ +
      JMP .no_count
    +
    LDA.l BombchuAmmo : AND.w #$00FF            ; same cap as the Y count
    CMP.w #!BOMBCHU_AMMO_MAX+1 : BCC .count
      LDA.w #$0000
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
; HUD_NMIUpload and HUD_StripAndSunTiles / HUD_StripAndMoonTiles live in
; Overworld/time_system.asm (bank $34).
