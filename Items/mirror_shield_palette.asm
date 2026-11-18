; ==============================================================================
; Mirror Shield Option D: 5-color palette via free OAM SP-5 Color 8
; ==============================================================================
; Uses free OAM SP-5 Color 8 ($01B0 -> PALB_SPR5B $7EC4B0 / PAL_SPR5B $7EC6B0)
; for Mirror Shield's cool steel highlight (#98C0F0 / $7B13), preserving
; Master Sword ($1BD642) and keeping base Sheets $5F/$5C unedited:
;   - PaletteData_shield_02 ($1BD658, C12..C15):
;       C12 = $373C (#E0C868 gold bezel/emblem)
;       C13 = $18A5 (#282830 cool dark outline)
;       C14 = $7FFE (#F0F8F8 white specular sheen)
;       C15 = $5589 (#4860A8 deep blue-steel shadow)
;   - Sheet $5F (front tiles 32,33,48,49 -> $7E9300/$7E93C0) and Sheet $5C
;     ($2E tiles 36,37,52,53 -> $7EBD40) encode 3bpp color 2 as 4BPP 1010b (C10,
;     Sword mid) while shading uses 1100b..1111b (bp2=1). Remapping bp1 &= bp2
;     converts only 1010b -> 1000b (C8) and leaves 0000b and 1100b..1111b intact.
; ==============================================================================

!MirrorShield_Color8 = $7B13 ; BGR555 #98C0F0

pushpc

; Shield level 3 (Mirror Shield) palette C12..C15 in PaletteData ($1BD658, 8B).
org $1BD658 ; @hook module=Items name=PaletteData_ShieldMirror kind=data protected_size=8
  dw $373C, $18A5, $7FFE, $5589

; Palettes_Load_Shield ($1BED29) exit at $1BED4A (5B: SEP #$30 : INC $15 : RTL).
org $1BED4A ; @hook module=Items name=MirrorShield_LoadColor8 kind=jml target=MirrorShield_LoadColor8 expected_m=16 expected_x=16 protected_size=5
  JML MirrorShield_LoadColor8
  NOP

; RefreshLinkEquipmentPalettes ($0ED6E8) exit at $0ED73C (5B: SEP #$30 : INC $15 : RTL; keeps $0ED745 FixShockPalette intact).
org $0ED73C ; @hook module=Items name=MirrorShield_RefreshColor8 kind=jml target=MirrorShield_RefreshColor8 expected_m=16 expected_x=16 protected_size=5
  JML MirrorShield_RefreshColor8
  NOP

; DecompressShieldGraphics ($00D308) exit at $00D333 (4B: SEP #$30 : PLB : RTL).
org $00D333 ; @hook module=Items name=MirrorShield_RemapEquippedWRAM kind=jml target=MirrorShield_RemapEquippedWRAM expected_m=16 expected_x=16 protected_size=4
  JML MirrorShield_RemapEquippedWRAM

; WriteTo4BPPBuffer ($00D50F) after PLA: capture item_id into DP $0A (5B: REP #$21 : AND.w #$00FF).
org $00D510 ; @hook module=Items name=MirrorShield_CaptureItemId kind=jsl target=MirrorShield_CaptureItemId expected_m=8 expected_x=8 expected_exit_m=16 expected_exit_x=8 protected_size=5
  JSL MirrorShield_CaptureItemId
  NOP

; WriteTo4BPPBuffer ($00D50F) exit at $00D533 (4B: SEP #$30 : PLB : RTL).
org $00D533 ; @hook module=Items name=MirrorShield_RemapPickupWRAM kind=jml target=MirrorShield_RemapPickupWRAM expected_m=16 expected_x=16 protected_size=4
  JML MirrorShield_RemapPickupWRAM

pullpc

; Entry: M=16, X=16. Sets SP-5 Color 8 ($7EC4B0/$7EC6B0) with day/night tint.
; Clobbers A, X; keeps Y, DBR. Returns M=16, X=16.
MirrorShield_ApplyColor8:
{
  LDA.w #!MirrorShield_Color8
  LDX.w #$01B0
  if !DISABLE_OVERWORLD == 0
    JSL LoadDayNightPaletteEffect
  else
    STA.l PALB_SPR5B
  endif
  STA.l PAL_SPR5B
  RTS
}

; Exit hook for Palettes_Load_Shield ($1BED4A -> M=8, X=8).
MirrorShield_LoadColor8:
{
  REP #$30
  LDA.l Shield : AND.w #$00FF : CMP.w #$0003 : BNE .skip
    JSR MirrorShield_ApplyColor8
.skip
  SEP #$30
  INC.b $15
  RTL
}

; Exit hook for RefreshLinkEquipmentPalettes ($0ED73C -> M=8, X=8).
; Checks DP $0D (active shield argument loaded before RefreshLinkEquipmentPalettes)
; so zap flash ($0D=$02) stays untouched and shock recovery ($0D=$7EF35A=3) restores C8.
MirrorShield_RefreshColor8:
{
  REP #$30
  LDA.b $0D : AND.w #$00FF : CMP.w #$0003 : BNE .skip
    JSR MirrorShield_ApplyColor8
.skip
  SEP #$30
  INC.b $15
  RTL
}

; Remap Y contiguous 4BPP tiles starting at $7E0000+X: bp1 &= bp2 (1010b -> 1000b).
; Entry: M=16, X=16, X=WRAM offset, Y=tile count. Clobbers A, X, Y. Returns M=16, X=16.
MirrorShield_RemapTilesC10ToC8:
{
.tile_loop
  PHY
  LDY.w #$0008
.row_loop
  LDA.l $7E0010,X               ; bp3:bp2
  XBA                           ; bp2:bp3
  ORA.w #$00FF                  ; bp2:$FF (keep bp0 unchanged)
  AND.l $7E0000,X               ; (bp1 & bp2):bp0
  STA.l $7E0000,X
  INX
  INX
  DEY
  BNE .row_loop
  TXA
  CLC
  ADC.w #$0010                  ; advance past bp2/bp3 bytes (+16..+31)
  TAX
  PLY
  DEY
  BNE .tile_loop
  RTS
}

; Exit hook for DecompressShieldGraphics ($00D333 -> M=8, X=8, restores caller DBR).
; Remaps equipped front shield top ($7E9300, tiles 32..33) & bottom ($7E93C0, tiles 48..49).
MirrorShield_RemapEquippedWRAM:
{
  REP #$30
  LDA.l Shield : AND.w #$00FF : CMP.w #$0003 : BNE .done
  LDX.w #$9300 : LDY.w #$0002 : JSR MirrorShield_RemapTilesC10ToC8
  LDX.w #$93C0 : LDY.w #$0002 : JSR MirrorShield_RemapTilesC10ToC8
.done
  SEP #$30
  PLB
  RTL
}

; Entry hook at $00D510 (M=8, X=8, A=8-bit item_id from PLA).
; Exit: M=16, X=8, C=0, A=item_id, $0A=item_id (replacing REP #$21 : AND.w #$00FF).
MirrorShield_CaptureItemId:
{
  REP #$21
  AND.w #$00FF
  STA.b $0A
  RTL
}

; Exit hook for WriteTo4BPPBuffer ($00D533 -> M=8, X=8, restores caller DBR).
; Remaps Mirror Shield item receipt tiles ($2E -> $7EBD40..BF, 4 contiguous tiles).
MirrorShield_RemapPickupWRAM:
{
  REP #$30
  LDA.b $0A : CMP.w #$002E : BNE .done
  LDX.w #$BD40 : LDY.w #$0004 : JSR MirrorShield_RemapTilesC10ToC8
.done
  SEP #$30
  PLB
  RTL
}
