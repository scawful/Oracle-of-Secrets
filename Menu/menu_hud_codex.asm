; =========================================================
; Codex HUD layout (HUD_LAYOUT_02/03), !ENABLE_HUD_LAYOUT_CODEX.
; Included from Items/all_items.asm (bank $2B items stream): Menu bank $2E
; has no room before the D8 boss slot ($2EB800). Template, cell defines,
; floor spot and the $008B82 NMI hook live in Menu/menu_hud.asm.
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
; the Bow (1) or the Boomerang (2), the two X-bindable items. The icons use
; the Y box tables ($0DF629 bow, $0DF651 boomerang; entry = 4 words:
; top-left, top-right, bottom-left, bottom-right). The Bow shows the arrow
; count (two digits, like the Y count) in the box's bottom border.
; In: A/X/Y 16-bit, any DBR. Out: A/X/Y 16-bit, A and X clobbered.
HUD_CodexCells:
{
  LDA.w #$3CA8 : STA.l HudCornerBuffer          ; rupee icon, bottom left
  LDA.w #$FCA8 : STA.l HudCornerBuffer+2
  LDA.w #$2071 : STA.l HudCornerBuffer+$0A      ; key icon, bottom right

  LDA.l ItemBindingSavedVersion : AND.w #$00FF : CMP.w #$0001 : BNE .empty
  LDA.l ItemBindingSavedX : AND.w #$00FF
  CMP.w #$0001 : BEQ .bow
  CMP.w #$0002 : BEQ .boomerang

  .empty
    LDA.w #$20AA                                ; item box background
    STA.l $7EC770 : STA.l $7EC772 : STA.l $7EC7B0 : STA.l $7EC7B2
  .no_count
    LDA.w #$207D : STA.l $7EC7F0                ; box bottom under the X icon
    LDA.w #$A014 : STA.l $7EC7F2
    RTL

  .boomerang
    LDA.l $7EF341 : AND.w #$00FF : BEQ .empty
    CMP.w #$0003 : BCS .empty
    ASL #3 : TAX
    LDA.l $0DF651+0, X : STA.l $7EC770
    LDA.l $0DF651+2, X : STA.l $7EC772
    LDA.l $0DF651+4, X : STA.l $7EC7B0
    LDA.l $0DF651+6, X : STA.l $7EC7B2
    BRA .no_count

  .bow
    LDA.l $7EF340 : AND.w #$00FF : BEQ .empty
    CMP.w #$0005 : BCS .empty
    ASL #3 : TAX
    LDA.l $0DF629+0, X : STA.l $7EC770
    LDA.l $0DF629+2, X : STA.l $7EC772
    LDA.l $0DF629+4, X : STA.l $7EC7B0
    LDA.l $0DF629+6, X : STA.l $7EC7B2

    ; Arrow count, two digits (tiles $2490-$2499, as HexToDecimal draws).
    LDA.l $7EF377 : AND.w #$00FF
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
