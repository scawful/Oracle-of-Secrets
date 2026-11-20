; ==============================================================================
; World-Aware Shield Trilogy + Zero-Sword-Bleed SP-5 Color 8 (LW L2 & L3)
; ==============================================================================
; Light World ($7EF3CA != $40) & Special Overworld load sword-independent 4BPP
; shield tiles built by Scripts/Generate/build_lw_shields.py
; (Data/graphics/items/vanilla_shields_lw.4bpp, ZERO Sword C9..C11 pixels!):
;   - L1: Custom Round Blue Fighter Shield ($1BD648 untouched; {0,12..15})
;   - L2: Custom 5-Color Hylian Shield ($1BD650 + SP-5 C8 !HylianShield_Color8):
;       C8  = $275E (#F7D64A Hylian Triforce & crest gold via SP-5 C8)
;       C12 = $6947 (#3952D6 rich royal blue field)
;       C13 = $1CE7 (#393939 crisp ALTTP charcoal outline)
;       C14 = $047B (#DE1808 vibrant Crimson Loftwing emblem)
;       C15 = $6739 (#CECECE gleaming metallic silver frame)
;   - L3: Custom Mirror Shield ($1BD658 Option D + SP-5 C8 !MirrorShield_Color8)
;
; Eon Abyss / Dark World ($7EF3CA == $40) switches Link's equipped shield tiles
; ($7E9300..$7E947F, 384B; compact face-clearing 9x9 GBC art built by
; Scripts/Generate/build_gbc_shields_dw.py) and SP-5 C12..C15 palette:
;   - L1 GBC Wooden Shield (DW only):
;       C12 = $379F (#F8E068 bright golden-brass rim & emblem)
;       C13 = $0865 (#281810 deep warm umber outline)
;       C14 = $15F9 (#C87828 warm Oracle oak wood)
;       C15 = $08EF (#783810 deep walnut wood grain shadow)
;   - L2 GBC Iron Heater Shield (DW only):
;       C12 = $7BDE (#F0F0F8 gleaming silver bevel & center crest)
;       C13 = $1CA4 (#202838 deep cool navy-steel outline)
;       C14 = $6ECE (#70B0DC cool steely-blue face)
;       C15 = $4947 (#385090 deep iron-slate shadow)
;   - L3 GBC Mirror Shield (Option D 5-color palette in LW & DW; compact GBC art in DW):
;       Uses free OAM SP-5 Color 8 ($01B0 -> PALB_SPR5B $7EC4B0 / PAL_SPR5B $7EC6B0)
;       for Mirror Shield's cool steel highlight (#98C0F0 / $7B13), preserving
;       Master Sword ($1BD642):
;       C12 = $373C (#E0C868 gold bezel/trim)
;       C13 = $18A5 (#282830 cool dark outline)
;       C14 = $7FFE (#F0F8F8 white specular sheen)
;       C15 = $5589 (#4860A8 deep blue-steel shadow)
;   - Pre-decoded 4BPP tile blobs (3 x 384B = 1152B each) live in Bank $34
;     ($34F000+) so ShieldWorld_SyncTiles / ShieldWorld_SyncBoth swap LW <-> DW
;     shields in ~0.18 ms without touching $7F0000 decompression scratch or DP.
; ==============================================================================

!HylianShield_Color8 = $275E ; BGR555 #F7D64A (LW L2 Hylian Triforce Gold)
!MirrorShield_Color8 = $7B13 ; BGR555 #98C0F0 (L3 Mirror Shield Steel Highlight)

pushpc

; Shield level 1 ($1BD648) stays untouched vanilla SNES Round Blue Fighter.
; Shield level 2 (LW Hylian Shield) palette C12..C15 in PaletteData ($1BD650, 8B).
org $1BD650 ; @hook module=Items name=PaletteData_ShieldHylian kind=data protected_size=8
  dw $6947, $1CE7, $047B, $6739

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

; Entry: M=16, X=16, A = BGR555 color for SP-5 Color 8 ($7EC4B0/$7EC6B0) with day/night tint.
; Clobbers A, X; keeps Y, DBR. Returns M=16, X=16.
MirrorShield_ApplyColor8:
{
  LDX.w #$01B0
  if !DISABLE_OVERWORLD == 0
    JSL LoadDayNightPaletteEffect
  else
    STA.l PALB_SPR5B
  endif
  STA.l PAL_SPR5B
  RTS
}

; Entry: M=16, X=16, A = active shield level (1..3).
; - L3: applies Option D SP-5 Color 8 (!MirrorShield_Color8) in both LW and DW.
; - L2 in LW/Special OW ($7EF3CA != #$40): applies Hylian Gold SP-5 Color 8
;   (!HylianShield_Color8) routed cleanly through LoadDayNightPaletteEffect.
; - L1 in LW/Special OW: leaves vanilla Fighter Shield palette intact.
; - L1/L2 in Dark World ($7EF3CA == #$40): writes GBC Wooden / Iron C12..C15.
; Clobbers A, X, Y. Returns M=16, X=16.
MirrorShield_ApplyWorldPalette:
{
  CMP.w #$0003 : BNE .check_l12
    LDA.w #!MirrorShield_Color8
    JSR MirrorShield_ApplyColor8
    RTS
.check_l12
  CMP.w #$0001 : BEQ .is_l12
  CMP.w #$0002 : BNE .done
.is_l12
  PHA
  SEP #$20
  LDA.l SavedWorld : CMP.b #$40
  REP #$20
  BNE .lw_l12
  PLA
  ; Dark World ($40): pick 8-byte GBC palette table for L1 (0) or L2 (8).
  DEC A : ASL #3 : TAX ; X = 0 (Wooden) or 8 (Iron-Kite)
  LDY.w #$01B8         ; CGRAM byte offset SP-5 C12 ($7EC4B8/$7EC6B8)
.pal_loop
  LDA.l GbcShieldPal_Table,X
  PHX : PHY
  TYX                  ; X = CGRAM byte offset for LoadDayNightPaletteEffect
  if !DISABLE_OVERWORLD == 0
    JSL LoadDayNightPaletteEffect
    TYX                ; reload X = CGRAM byte offset (Y preserved)
  else
    STA.l $7EC300,X
  endif
  STA.l $7EC500,X
  PLY : PLX
  INX : INX
  INY : INY
  CPY.w #$01C0 : BCC .pal_loop
  RTS
.lw_l12
  PLA
  CMP.w #$0002 : BNE .done
    LDA.w #!HylianShield_Color8
    JSR MirrorShield_ApplyColor8
.done
  RTS
}

GbcShieldPal_Table:
  ; L1 GBC Wooden Shield (C12..C15)
  dw $379F, $0865, $15F9, $08EF
  ; L2 GBC Iron / Kite Shield (C12..C15)
  dw $7BDE, $1CA4, $6ECE, $4947

; Exit hook for Palettes_Load_Shield ($1BED4A -> M=8, X=8).
; Syncs BOTH equipped shield 4BPP tiles ($7E9300..$7E947F) and world palette so
; every LW <-> DW crossing (Mirror, Breach Portal, Vortex, Warp Pad, Dungeon Exit)
; switches between vanilla SNES shields (LW/SW) and GBC shields (DW) automatically.
MirrorShield_LoadColor8:
{
  JSL ShieldWorld_SyncTiles
  REP #$30
  LDA.l Shield : AND.w #$00FF
  JSR MirrorShield_ApplyWorldPalette
  SEP #$30
  INC.b $15
  RTL
}

; Exit hook for RefreshLinkEquipmentPalettes ($0ED73C -> M=8, X=8).
; Checks DP $0D (active shield argument loaded before RefreshLinkEquipmentPalettes)
; so electrocution zap flash ($0D != Shield) stays untouched, while shock recovery
; ($0D == Shield) restores both Option D C8 (L3) and Dark World GBC L1/L2 colors.
MirrorShield_RefreshColor8:
{
  REP #$30
  LDA.b $0D : AND.w #$00FF
  CMP.w #$0003 : BEQ .apply
  ; For L1/L2, only apply when $0D matches the player's actual equipped shield
  ; (guards against zap-flash $0D=$02 clobbering shock palette).
  PHA
  SEP #$20
  LDA.b $0D : CMP.l Shield
  REP #$20
  BNE .pop_skip
  PLA
.apply
  JSR MirrorShield_ApplyWorldPalette
  BRA .skip
.pop_skip
  PLA
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
; Always syncs $7E9300..$7E947F from our clean pre-baked 4BPP blobs via
; ShieldWorld_SyncTiles so fresh boots, file loads, and shield upgrades NEVER
; display raw Sheet $5F Sword-palette bleed pixels:
;   - Dark World ($7EF3CA == #$40): compact GBC Shield Trilogy (Option D pre-baked)
;   - Light World / Special OW:     sword-independent LW shields (L1 Fighter,
;                                   L2 Hylian with C8 gold, L3 Mirror with C8 steel)
MirrorShield_RemapEquippedWRAM:
{
  JSL ShieldWorld_SyncTiles
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

; ==============================================================================
; Bank $34 tail ($34F000-$34FFFF): Dark-World / Light-World Shield 4BPP Swapper
; Preserves all registers, P, DBR, DP, and $7F0000 scratch (safe from any hook).
; ==============================================================================
pushpc
org $34F000

; Copies the equipped shield's 12 4BPP tiles (384 bytes) into GFX_SHIELD ($7E9300):
;   SavedWorld ($7EF3CA) == #$40 -> GbcShields_4bpp (DW compact GBC Shield Trilogy)
;   otherwise                    -> VanillaShields_4bpp (LW base OoS custom shields:
;                                   L1 Round Blue Fighter, L2 Hylian, L3 Mirror)
ShieldWorld_SyncTiles:
{
  PHP : PHB : REP #$30
  PHA : PHX : PHY
  LDA.l Shield : AND.w #$00FF
  BEQ .done
  CMP.w #$0004 : BCS .done
  ; Offset = (shield - 1) * $0180 ($0000 / $0180 / $0300)
  DEC A : XBA             ; $0000 / $0100 / $0200
  PHA
  LSR A                   ; $0000 / $0080 / $0100
  CLC : ADC 1,S           ; $0000 / $0180 / $0300
  PLX                     ; discard pushed temp
  TAX
  SEP #$20
  LDA.l SavedWorld : CMP.b #$40
  REP #$20
  BNE .use_lw
    TXA : CLC : ADC.w #GbcShields_4bpp : TAX
    BRA .copy
.use_lw
  TXA : CLC : ADC.w #VanillaShields_4bpp : TAX
.copy
  ; Set DBR = $7E so STA.w $9300,Y writes directly to GFX_SHIELD ($7E9300..$7E947F).
  SEP #$20
  LDA.b #$7E : PHA : PLB
  REP #$20
  LDY.w #$0000
.loop
  LDA.l $340000,X
  STA.w $9300,Y
  INX : INX : INY : INY
  CPY.w #$0180 : BCC .loop
.done
  PLY : PLX : PLA
  PLB : PLP
  RTL
}

; Syncs BOTH equipped shield tiles ($7E9300..$7E947F) and shield palette
; (Palettes_Load_Shield -> MirrorShield_LoadColor8 -> ShieldWorld_SyncTiles +
; MirrorShield_ApplyWorldPalette). Preserves A, X, Y, P, DBR, DP $00-$07.
ShieldWorld_SyncBoth:
{
  PHP : PHB : REP #$30
  PHA : PHX : PHY
  LDA.b $00 : PHA
  LDA.b $02 : PHA
  LDA.b $04 : PHA
  LDA.b $06 : PHA
  JSL $1BED29 ; Palettes_Load_Shield (exits via MirrorShield_LoadColor8 -> tiles + palette!)
  REP #$30
  PLA : STA.b $06
  PLA : STA.b $04
  PLA : STA.b $02
  PLA : STA.b $00
  PLY : PLX : PLA
  PLB : PLP
  RTL
}

VanillaShields_4bpp:
  incbin "Data/graphics/items/vanilla_shields_lw.4bpp"

GbcShields_4bpp:
  incbin "Data/graphics/items/gbc_shields_dw.4bpp"

assert pc() <= $350000, "ShieldWorld data/routines exceeded Bank $34"
pullpc
