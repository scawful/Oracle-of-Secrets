; =========================================================
; Special Overworld Unified Transitions, Cross-World Boundary Crossings &
; Special Overworld Mode 7 World Map Helpers (Bank $5F tail: $5FD200-$5FFFFF)
;
; Implements QUEUE322:
;   1. Bidirectional Cross-World Mosaic Crossings (LW Col 7 <-> SW Col 0):
;      $1F <-> $98 (row 3), $27 <-> $A0 (row 4), $2F <-> $A8 (row 5),
;      $37 <-> $B0 (row 6), $3F <-> $B8 (row 7)
;   2. Unified Module $09 ($10 = $09) on Special Overworld ($80-$BF)
;   3. Dynamic exact mixed-size ByScreen1..4 calculation for all 64 Special
;      Overworld maps ($80-$BF), across Small/Large/Wide/Tall combinations
;   4. Two-sided symmetric Mosaic decision (all worlds $00-$BF) plus
;      Special Overworld overlay / main-palette / main-BG-sheet compatibility
;   5. Special Overworld Mode 7 World Map palette, Link dot save/restore,
;      and landmark icon helpers
;
; Volatile WRAM (7 bytes inside unused $7EC132-$7EC13F):
;   $7EC132: SpecialOverworld_CrossWorldDest (1B; $00 = idle)
;   $7EC133..$7EC136: SpecialOverworld_MapSavedPos (4B; $7EC108..$7EC10B backup)
;   $7EC137: SpecialOverworld_MapSavedFlag (1B; $01 while map backup active)
;   $7EC138: SpecialOverworld_VortexWorld (1B; $00=none, $01=LW, $40=DW Abyss, $FF=just returned DW->LW)
; =========================================================

SpecialOverworld_CrossWorldDest = $7EC132
SpecialOverworld_MapSavedPos    = $7EC133
SpecialOverworld_MapSavedFlag   = $7EC137
SpecialOverworld_VortexWorld    = $7EC138

pushpc
org $5FD200
SpecialOverworld_TransitionsCodeStart:

; ---------------------------------------------------------
; World Map Helpers (always available regardless of native flag)
; ---------------------------------------------------------

; Hook at $0AB9F0 (WorldMap_FadeOut, M=16, X=8, DBR=$0A).
; Copies Link's live $20/$22 into $7EC108/$7EC10A for LW ($00-$3F), DW ($40-$7F),
; AND Special Overworld ($80-$BF). On $80-$BF, backs up $7EC108..$7EC10B first
; so SpecialOverworld return triggers ($81->$0F, $80->$2A, $91->$33) keep their
; saved Light World return coordinates intact after closing the World Map.
; Exit: M=16, X=8, DBR preserved; A clobbered.
SpecialOverworld_SaveAndSetMapPos:
{
  LDX.b $8A
  CPX.b #$C0 : BCS .skip
  CPX.b #$80 : BCC .copy_live
    LDA.l $7EC108 : STA.l SpecialOverworld_MapSavedPos
    LDA.l $7EC10A : STA.l SpecialOverworld_MapSavedPos+2
    SEP #$20
    LDA.b #$01 : STA.l SpecialOverworld_MapSavedFlag
    REP #$20
  .copy_live
  LDA.b $20 : STA.l $7EC108
  LDA.b $22 : STA.l $7EC10A
  .skip
  RTL
}

; Called by FixMaskPaletteOnExit ($0ABC76, WorldMap_ExitMap).
; Restores backed-up $7EC108..$7EC10B if Special Overworld World Map ran.
; Entry/Exit: preserves A/X/Y/P/DBR.
SpecialOverworld_RestoreMapPos:
{
  PHP : REP #$20 : PHA
  SEP #$20
  LDA.l SpecialOverworld_MapSavedFlag : BEQ .done
    LDA.b #$00 : STA.l SpecialOverworld_MapSavedFlag
    REP #$20
    LDA.l SpecialOverworld_MapSavedPos   : STA.l $7EC108
    LDA.l SpecialOverworld_MapSavedPos+2 : STA.l $7EC10A
  .done
  REP #$20 : PLA : PLP
  RTL
}

; Hook at $0ABA40 (WorldMap_LoadLightWorldMap palette copy, M=8, X=8, DBR=$0A).
; 3-way dispatch:
;   $80-$BF -> SWPalettes ($5FD000)
;   $40-$7F -> DWPalettes ($0ADC27)
;   $00-$3F -> Palettes_OWMAP ($0ADB27)
; Exit: M=8, X=8, DBR preserved; A/X/Y clobbered.
SpecialOverworld_LoadWorldMapPalette:
{
  PHB
  REP #$30
  LDA.b $8A : AND.w #$00FF
  CMP.w #$0080 : BCC .lw_or_dw
  CMP.w #$00C0 : BCS .lw_or_dw
    ; Special Overworld ($80-$BF) palette in Bank $42
    SEP #$20
    LDA.b #SWPalettes>>16 : PHA : PLB
    REP #$20
    LDX.w #$00FE
    .copy_sw
      LDA.w SWPalettes, X
      STA.l $7EC500, X
      DEX #2
    BPL .copy_sw
    BRA .done
  .lw_or_dw
  SEP #$20
  LDA.b #$0A : PHA : PLB
  REP #$20
  LDX.w #$00FE
  LDY.w #$00FE
  LDA.b $8A : AND.w #$0040 : BEQ .copy_lw_dw
    LDY.w #$01FE
  .copy_lw_dw
    LDA.w $DB27, Y
    STA.l $7EC500, X
    DEY #2 : DEX #2
  BPL .copy_lw_dw
  .done
  SEP #$30
  PLB
  RTL
}

; Special Overworld World Map landmark icons ($80-$BF).
; Coordinates aligned pixel-for-pixel to pirate05 Lyra Sea Mode 7 map
; (central 256x256 geography at x128..383, y128..383, 1:16 world scale;
; ZERO icons under the $84-$87/$8C-$8F/$94-$97/$9C-$9F cloud bank).
; Entry: M=8, X=8, A = icon index (0..3).
; Sets $7EC108..$7EC10B (Y/X), $0B..$0D (size/props/tile), $7EC025 (OAM slot).
; Exit: C set = draw icon, C clear = already collected (skip).
SpecialOverworld_SetupMapIcon:
{
  PHX
  TAX
  ; Check progression/collection bit so cleared shrines/tower hide cleanly
  CPX.b #$03 : BEQ .check_sky
    LDA.l Pendants
    AND.l .CollectMask, X
    BNE .hide
    BRA .populate
  .check_sky
  LDA.l Crystals
  AND.b #!Crystal_D8_Sky
  BNE .hide

  .populate
  LDA.l .PosXHi, X : STA.l $7EC10B
  LDA.l .PosXLo, X : STA.l $7EC10A
  LDA.l .PosYHi, X : STA.l $7EC109
  LDA.l .PosYLo, X : STA.l $7EC108
  LDA.l .Tile, X   : STA.b $0D
  LDA.l .Props, X  : STA.b $0C
  LDA.b #$02       : STA.b $0B       ; 16x16 icon
  LDA.l .OamSlot, X : STA.l $7EC025
  PLX
  SEC
  RTL

  .hide
  PLX
  CLC
  RTL

  ; 0: Shrine of Wisdom ($91 plateau, px 174,205 -> $02E0,$04D0)
  ; 1: Shrine of Courage ($A6/$AE temple box, px 362,296 -> $0EA0,$0A80)
  ; 2: Shrine of Power ($B0 Goron Coast, px 143,335 -> $00F0,$0CF0)
  ; 3: Sky Tower / D8 ($83/$8B visible spire outside clouds, px 239,152 -> $06F0,$0180)
  .CollectMask: db !Pendant_Wisdom, !Pendant_Courage, !Pendant_Power, !Crystal_D8_Sky
  .PosXHi:      db $02, $0E, $00, $06
  .PosXLo:      db $E0, $A0, $F0, $F0
  .PosYHi:      db $04, $0A, $0C, $01
  .PosYLo:      db $D0, $80, $F0, $80
  .Tile:        db $60, $60, $60, $66
  .Props:       db $34, $38, $32, $34
  .OamSlot:     db $0D, $0A, $08, $0B
}

; ---------------------------------------------------------
; Unified Module $09 ($10 = $09) Transitions
; ---------------------------------------------------------

; Hook at $02B1B4 (Module09_1C_02_HandleMusic end, M=8, X=8).
; Unifies Special Overworld entry ($17..$1C) into Module $09 before
; Overworld_FinalizeEntryOntoScreen ($08) hands control to the player, and
; restores Special Overworld area music/ambience (vanilla $02B1A0 skips $8A >= $80).
SpecialOverworld_FinishSpecialEntry:
{
  LDA.b $8A : CMP.b #$80 : BCC .done_music
    PHX
    TAX
    LDA.l !OverworldMusicCache, X : LSR #4 : BNE .has_amb
      LDA.b #$05
    .has_amb
    STA.w $012D
    LDA.l !OverworldMusicCache, X : AND.b #$0F : BEQ .keep_song
      CMP.w $0130 : BEQ .keep_song
        STA.w $012C
    .keep_song
    PLX
  .done_music
  LDA.b #$09 : STA.b $10
  LDA.b #$08 : STA.b $11
  STZ.b $B0
  RTL
}

; Called at Overworld_PlayerControl_Interupt ($02A5D3, M=8, X=8).
; Guarantees Module $0B never persists into player control (e.g. after
; canceling Special Soaring), without colliding with Boat_BoardGate ($02A53C).
SpecialOverworld_NormalizeModule09:
{
  LDA.b $10 : CMP.b #$0B : BNE .ok
    LDA.b #$09 : STA.b $10
  .ok
  RTL
}

if !SPECIAL_OVERWORLD_NATIVE == 1

; ---------------------------------------------------------
; Cross-World Boundary Crossing (LW Col 7 <-> SW Col 0)
; ---------------------------------------------------------

; Called from OverworldHandleTransitions (.transition, M=8, X=8, DBR=$02)
; right after LyraEdgeGuard permits the transition and ancillae are cleared.
; Input: $02 = direction (0=R, 2=L, 4=D, 6=U), $8A = current parent,
;        $0700 = current physical cell * 2.
; Exit:  C set = cross-world mosaic started (caller must RTS immediately);
;        C clear = normal same-world transition (X/Y/DBR preserved).
SpecialOverworld_TryCrossWorld:
{
  PHX : PHY
  ; Compute physical cell = ($8A & $C0) | (($0700 & $7E) >> 1)
  LDA.l $7E0700 : AND.b #$7E : LSR
  STA.b $04
  LDA.b $8A : AND.b #$C0 : ORA.b $04
  STA.b $04                           ; $04 = physical cell

  LDA.b $02                           ; direction
  BEQ .try_east
  CMP.b #$02 : BEQ .try_west
  BRA .not_cross

  .try_east
  ; LW Col 7 ($1F, $27, $2F, $37, $3F) going East -> SW Col 0 ($98, $A0, $A8, $B0, $B8)
  LDA.b $8A : CMP.b #$40 : BCS .not_cross
  LDA.b $04
  AND.b #$07 : CMP.b #$07 : BNE .not_cross
  LDA.b $04
  CMP.b #$1F : BCC .not_cross
  CMP.b #$40 : BCS .not_cross
  CLC : ADC.b #$79                    ; dst_cell = cell + $80 - 7
  BRA .start_cross

  .try_west
  ; SW Col 0 ($98, $A0, $A8, $B0, $B8) going West -> LW Col 7 ($1F, $27, $2F, $37, $3F)
  LDA.b $8A : CMP.b #$80 : BCC .not_cross
  CMP.b #$C0 : BCS .not_cross
  LDA.b $04
  AND.b #$07 : BNE .not_cross
  LDA.b $04
  CMP.b #$98 : BCC .not_cross
  CMP.b #$B9 : BCS .not_cross
  SEC : SBC.b #$79                    ; dst_cell = cell - $80 + 7

  .start_cross
  STA.l SpecialOverworld_CrossWorldDest
  TAX
  JSL Lyra_ReadParent                 ; A = destination parent area
  TAX
  ; Fade music if destination area uses a different track
  LDA.l !OverworldMusicCache, X : AND.b #$0F
  CMP.w $0130 : BEQ .same_song
    LDA.b #$F1 : STA.w $012C
  .same_song

  ; Launch clean full-screen mosaic rebuild via Submodule $24 in Module $09
  LDA.b #$09 : STA.b $10
  LDA.b #$24 : STA.b $11
  LDA.b #$00 : STA.b $95
               STA.l $7EC011
               STA.b $B0
  STZ.w $0410
  STZ.w $0416

  PLY : PLX
  SEC
  RTL

  .not_cross
  PLY : PLX
  CLC
  RTL
}

; Hook at $02AE98 (OverworldMosaicTransition_HandleScreensAndLoadShroom,
; M=8, X=8, DBR=$02, FBlank $13=$80 active, $B0=0).
; Replaces 5 bytes: LDA.w $040A : BEQ $02AEB6.
SpecialOverworld_MosaicFBlankHook:
{
  LDA.l SpecialOverworld_CrossWorldDest : BNE .cross_world
    LDA.w $040A : BEQ .vanilla_zero
      JML $02AE9D
    .vanilla_zero
    JML $02AEB6

  .cross_world
  PHA                                 ; save dst_cell
  LDA.b #$00 : STA.l SpecialOverworld_CrossWorldDest
  PLA : PHA                           ; A = dst_cell (also kept on stack)
  TAX
  JSL Lyra_ReadParent                 ; A = dst_parent
  STA.b $8A
  STA.w $040A
  STZ.b $8B
  STZ.w $040B

  ; Clear stale special-exit room ID ($A0) and Korok custom-sheet flag ($0AA5)
  STZ.b $A0 : STZ.b $A1
  STZ.w $0AA5
  ; Keep SavedWorld = $00 (Light World / East Kalyxo, never Dark World $40)
  LDA.b #$00 : STA.l SavedWorld

  ; Select landing X, facing ($2F), and finalize direction ($069C/$0418)
  PLA                                 ; A = dst_cell
  CMP.b #$80 : BCS .land_east
    ; West crossing into LW Col 7: land at $0FE2 -> 1 frame finalize -> $0FE0
    REP #$20
    LDA.w #$0FE2 : STA.b $22
    SEP #$20
    LDA.b #$04 : STA.b $2F            ; Face Left
    LDA.b #$02 : STA.w $069C : STA.w $0418
    BRA .coords_set
  .land_east
    ; East crossing into SW Col 0: land at $000E -> 1 frame finalize -> $0010
    REP #$20
    LDA.w #$000E : STA.b $22
    SEP #$20
    LDA.b #$06 : STA.b $2F            ; Face Right
    LDA.b #$03 : STA.w $069C : STA.w $0418

  .coords_set
  ; Clear scrolling, door, and scroll-modifier state
  STZ.w $0410 : STZ.w $0416
  STZ.w $0696 : STZ.w $0697
  STZ.w $0698 : STZ.w $0699
  STZ.w $04AC : STZ.w $04AD
  STZ.w $0126

  REP #$20
  STZ.w $0624 : STZ.w $0626
  STZ.w $0628 : STZ.w $062A
  LDA.w #$FFF8 : STA.b $EC

  ; Recompute physical cell offset $0700 from new ($20, $22)
  LDA.b $20 : AND.w #$1E00 : ASL #3 : STA.w $0700
  LDA.b $22 : AND.w #$1E00 : ORA.w $0700 : XBA : STA.w $0700
  SEP #$20

  ; Load destination GFX indices, screen size, $0708-$070E, $0716-$0719, $0600-$0616
  PHB : PEA.w $0202 : PLB : PLB
  JSL Overworld_LoadMapProperties_Long
  PLB
  JSL Copy0716
  STZ.w $0713

  REP #$20
  JSL NewOverworld_SetCameraBounds

  ; Camera Y = clamp($20 - $0060, $0600, $0602)
  LDA.b $20 : SEC : SBC.w #$0060 : BCS .y_nonneg
    LDA.w #$0000
  .y_nonneg
  CMP.w $0600 : BCS .y_ge_min
    LDA.w $0600
  .y_ge_min
  CMP.w $0602 : BCC .y_ok
    LDA.w $0602
  .y_ok
  STA.b $E8 : STA.b $E6 : STA.w $0122 : STA.w $0124
  CLC : ADC.w #$006F : STA.w $0618
  DEC #2 : STA.w $061A

  ; Camera X = clamp($22 - $0078, $0604, $0606)
  LDA.b $22 : SEC : SBC.w #$0078 : BCS .x_nonneg
    LDA.w #$0000
  .x_nonneg
  CMP.w $0604 : BCS .x_ge_min
    LDA.w $0604
  .x_ge_min
  CMP.w $0606 : BCC .x_ok
    LDA.w $0606
  .x_ok
  STA.b $E2 : STA.b $E0 : STA.w $011E : STA.w $0120
  CLC : ADC.w #$007F : STA.w $061C
  DEC #2 : STA.w $061E

  ; Compute BG2 map16 buffer offset $84, $88, $86 matching Overworld_LoadAndBuildScreen
  ; $84 = (((cam_y - $0708) & $03F0) << 3) | (((cam_x - ($070C << 3)) & $03F0) >> 3)
  LDA.b $E8 : SEC : SBC.w $0708 : AND.w #$03F0 : ASL #3 : STA.b $00
  LDA.w $070C : ASL #3 : STA.b $02
  LDA.b $E2 : SEC : SBC.b $02 : AND.w #$03F0 : LSR #3 : ORA.b $00
  STA.b $84
  SEC : SBC.w #$0400 : AND.w #$0F80 : ASL : XBA : STA.b $88
  LDA.b $84
  SEC : SBC.w #$0010 : AND.w #$003E : LSR : STA.b $86

  SEP #$30

  ; Layer / collision defaults (matching LoadOverworldFromSpecialOverworld,
  ; intentionally preserving Link's swimming state $5D for $1F <-> $98!)
  STZ.b $A9
  LDA.b #$02 : STA.b $AA : STA.b $A6 : STA.b $A7
  LDA.b #$80 : STA.b $45 : STA.b $44
  LDA.b #$0F : STA.b $42 : STA.b $43

  ; Reload destination Main BG + Sprite + HUD palettes & backdrop into $7EC300 buffer
  PHB : PEA.w $0202 : PLB : PLB
  JSL Overworld_LoadAreaPalettes_Long
  PLB
  JSL $0ED61D                         ; Overworld_SetScreenBGColorCacheOnly

  ; Advance Submodule $24 -> $25 (Module09_25: reload sprites + BG1 overlay -> $26..$29)
  INC.b $11
  JML $02AEB5
}

; ---------------------------------------------------------
; Dynamic Exact Mixed-Size ByScreen1..4 for Special Overworld ($80-$BF)
; ---------------------------------------------------------
; Replaces Lyra_ReadByScreen at OverworldHandleTransitions ($02A9C4).
; Entry: M=16, X=16, A = destination_cell * 2, X = direction (0=R, 2=L, 4=D, 6=U),
;        $8A = old parent, $0700 = old physical cell * 2.
; Exit:  A = exact ByScreen delta, X/Y/D/DB and caller C/V preserved; zero DP scratch.
;
; Exact closed-form ZSCustomOverworld v3 law:
;   Right (0): $0060 + (dst_qy - src_qy) * $1000
;   Left  (2): ($0080 if dst_size in {Large,Wide} else $0040) + (dst_qy - src_qy) * $1000
;   Down  (4): $1800 + (dst_qx - src_qx) * $0040
;   Up    (6): ($2000 if dst_size in {Large,Tall} else $1000) + (dst_qx - src_qx) * $0040
SpecialOverworld_ReadByScreen:
{
  CMP.w #$0100 : BCC .go_legacy
  CMP.w #$0180 : BCC .in_special
  .go_legacy
  JML Lyra_ReadByScreen
  .in_special

  PHP : REP #$30 : PHX : PHY
  ; Stack frame (offsets from S as we push):
  ;   push dst_cell, dir, base_delta -> use stack-relative addressing (zero DP writes!)
  LSR                                 ; A = dst_cell ($80..$BF)
  PHA                                 ; 07,S (after 3 more pushes) = dst_cell

  ; Compute src_cell = ($8A & $00C0) | (($0700 & $007E) >> 1)
  LDA.l $7E0700 : AND.w #$007E : LSR
  PHA                                 ; temp
  LDA.b $8A : AND.w #$00C0 : ORA $01,S
  STA $01,S                           ; stack: [src_cell (1,S), dst_cell (3,S), Y, X, P]

  ; src_off = src_cell - parent[src_cell]
  TAX
  JSL Lyra_ReadParent : AND.w #$00FF
  EOR.w #$FFFF : INC : CLC : ADC $01,S ; src_cell - src_parent
  STA $01,S                           ; [src_off (1,S), dst_cell (3,S)]

  ; dst_parent = parent[dst_cell], dst_off = dst_cell - dst_parent, dst_size = size[dst_parent]
  LDA $03,S : TAX
  JSL Lyra_ReadParent : AND.w #$00FF
  PHA                                 ; [dst_parent (1,S), src_off (3,S), dst_cell (5,S)]
  EOR.w #$FFFF : INC : CLC : ADC $05,S ; dst_cell - dst_parent
  STA $05,S                           ; [dst_parent (1,S), src_off (3,S), dst_off (5,S)]

  LDA $01,S : TAX
  JSL Lyra_ReadSize : AND.w #$00FF
  STA $01,S                           ; [dst_size (1,S), src_off (3,S), dst_off (5,S), Y (7,S), X/dir (9,S), P (11,S)]

  ; Dispatch on direction X (saved at $09,S)
  LDA $09,S
  CMP.w #$0004 : BCS .vertical

  ; --- Horizontal: Right (0) or Left (2) ---
  CMP.w #$0000 : BNE .left
    LDA.w #$0060
    BRA .h_adjust
  .left
    LDA $01,S                         ; dst_size: 1=Large, 2=Wide -> $0080; 0=Small, 3=Tall -> $0040
    CMP.w #$0001 : BEQ .left_wide
    CMP.w #$0002 : BEQ .left_wide
      LDA.w #$0040
      BRA .h_adjust
    .left_wide
      LDA.w #$0080
  .h_adjust
  ; Check dst_qy (bit 3 of dst_off) vs src_qy (bit 3 of src_off)
  TAY                                 ; Y = base
  LDA $05,S : AND.w #$0008            ; dst_qy << 3 (0 or 8)
  CMP.w #$0000 : BNE .dst_qy_1
    ; dst_qy == 0: if src_qy == 1 -> subtract $1000
    LDA $03,S : AND.w #$0008 : BEQ .done_y
      TYA : SEC : SBC.w #$1000
      BRA .finish
  .dst_qy_1
    ; dst_qy == 1: if src_qy == 0 -> add $1000
    LDA $03,S : AND.w #$0008 : BNE .done_y
      TYA : CLC : ADC.w #$1000
      BRA .finish
  .done_y
  TYA
  BRA .finish

  ; --- Vertical: Down (4) or Up (6) ---
  .vertical
  CMP.w #$0004 : BNE .up
    LDA.w #$1800
    BRA .v_adjust
  .up
    LDA $01,S                         ; dst_size: 1=Large, 3=Tall -> $2000; 0=Small, 2=Wide -> $1000
    BIT.w #$0001 : BNE .up_tall
      LDA.w #$1000
      BRA .v_adjust
    .up_tall
      LDA.w #$2000
  .v_adjust
  ; Check dst_qx (bit 0 of dst_off) vs src_qx (bit 0 of src_off)
  TAY                                 ; Y = base
  LDA $05,S : AND.w #$0001            ; dst_qx (0 or 1)
  BNE .dst_qx_1
    ; dst_qx == 0: if src_qx == 1 -> subtract $0040
    LDA $03,S : AND.w #$0001 : BEQ .done_x
      TYA : SEC : SBC.w #$0040
      BRA .finish
  .dst_qx_1
    ; dst_qx == 1: if src_qx == 0 -> add $0040
    LDA $03,S : AND.w #$0001 : BNE .done_x
      TYA : CLC : ADC.w #$0040
      BRA .finish
  .done_x
  TYA

  .finish
  ; Pop 3 temp words (dst_size, src_off, dst_off), then restore Y, X, P
  PLY : PLY : PLY                     ; discard temps (A untouched)
  PLY : PLX : PLP
  RTL
}

; ---------------------------------------------------------
; Two-Sided Mosaic Decision (All Worlds + Special OW Compatibility)
; ---------------------------------------------------------
; Called from OverworldHandleTransitions (ZSCustomOverworld.asm) with:
;   M=8, X=8, X = old_parent, $8A = new_parent,
;   $0416 = outgoing dir bit ($01/$02/$04/$08), $0418 = dir index (0=U,1=D,2=L,3=R).
; Exit: M=8, X=8, A = $01 (Z=0) if Mosaic needed, A = $00 (Z=1) for smooth scroll.
;       X, Y, DBR preserved.
SpecialOverworld_ShouldMosaic:
{
  PHX : PHY
  ; 1. Source map requests mosaic in outgoing direction (all worlds $00-$BF)
  JSL Lyra_ReadMosaic
  AND.w $0416 : BEQ .check_dest_mosaic
    JMP .yes
  .check_dest_mosaic

  ; 2. Destination map requests mosaic in opposite direction (all worlds $00-$BF)
  LDX.b $8A
  JSL Lyra_ReadMosaic
  LDX.w $0418
  AND.l .OppDirBit, X : BEQ .check_special
    JMP .yes
  .check_special

  ; 2b. Light/Dark World ($00-$7F) Snowpeak overlay-mismatch guard:
  ; Smooth scroll ($11=$01-$08) never calls Overworld_ReloadSubscreenOverlay,
  ; so crossing into/out of Tree-Snow ($0095) or Falling Snow ($009D) must
  ; mosaic even when Pool_MosaicTable omits the edge bit (without disturbing
  ; Docks $28/$29<->$30<->$32 or other non-Snowpeak smooth scrolls).
  ; Stack top: 1,S = saved Y, 2,S = saved X (old_parent).
  LDA $02,S                           ; old_parent
  CMP.b #$80 : BCS .check_sw_bounds
  LDA.b $8A
  CMP.b #$80 : BCS .ret_no
  CMP $02,S : BEQ .ret_no             ; same parent: always smooth scroll
  REP #$30
  LDA $02,S : AND.w #$00FF : ASL : TAX
  JSL Lyra_ReadOverlay
  PHA                                 ; 1,S = old_ov
  LDA.b $8A : AND.w #$00FF : ASL : TAX
  JSL Lyra_ReadOverlay                ; A = new_ov
  CMP $01,S : BEQ .lw_same_ov
    CMP.w #$0095 : BEQ .lw_force_mosaic
    CMP.w #$009D : BEQ .lw_force_mosaic
    LDA $01,S
    CMP.w #$0095 : BEQ .lw_force_mosaic
    CMP.w #$009D : BEQ .lw_force_mosaic
  .lw_same_ov
  PLA
  SEP #$30
  JMP .no
  .lw_force_mosaic
  PLA
  SEP #$30
  JMP .yes

  .check_sw_bounds
  ; 3. Special Overworld ($80-$BF) graphic/overlay compatibility check
  ; Stack top: 1,S = saved Y, 2,S = saved X (old_parent)
  LDA $02,S                           ; old_parent
  CMP.b #$80 : BCC .ret_no
  CMP.b #$C0 : BCS .ret_no
  LDA.b $8A
  CMP.b #$80 : BCC .ret_no
  CMP.b #$C0 : BCS .ret_no

  ; Same parent area? Always smooth scroll
  CMP $02,S : BNE .diff_parent
  .ret_no
    JMP .no
  .diff_parent

  ; Check Overlay word mismatch (normal scroll cannot load/unload BG1 overlays)
  REP #$30
  LDA $02,S : AND.w #$00FF : ASL : TAX
  JSL Lyra_ReadOverlay
  PHA                                 ; old overlay
  LDA.b $8A : AND.w #$00FF : ASL : TAX
  JSL Lyra_ReadOverlay
  CMP $01,S : BEQ .same_overlay
    PLA
    SEP #$30
    JMP .yes
  .same_overlay
  PLA
  SEP #$30

  ; Sky-to-Sky chain ($87, $8C-$8F): keep smooth scroll (handled by sky_overlay_transition.asm)
  LDA $02,S : JSR .is_sky : BCC .not_both_sky
  LDA.b $8A : JSR .is_sky : BCS .ret_no

  .not_both_sky
  ; Check Main Palette mismatch
  LDA $02,S : TAX
  JSL Lyra_ReadMainPalette
  PHA
  LDX.b $8A
  JSL Lyra_ReadMainPalette
  CMP $01,S : BEQ .same_main_pal
    PLA
    JMP .yes
  .same_main_pal
  PLA

  ; Check Main BG GFX sheets 0, 1, 2, 7 (slots 3..6 are Aux, swapped cleanly by normal scroll)
  REP #$30
  LDA $02,S : AND.w #$00FF : ASL #3 : TAX   ; X = old_parent * 8
  LDA.b $8A : AND.w #$00FF : ASL #3 : TAY   ; Y = new_parent * 8

  SEP #$20
  JSL Lyra_ReadGfx0 : PHA
  TYX : JSL Lyra_ReadGfx0 : CMP $01,S : BNE .gfx_diff
  PLA

  REP #$20
  LDA $02,S : AND.w #$00FF : ASL #3 : TAX
  SEP #$20
  JSL Lyra_ReadGfx1 : PHA
  TYX : JSL Lyra_ReadGfx1 : CMP $01,S : BNE .gfx_diff
  PLA

  REP #$20
  LDA $02,S : AND.w #$00FF : ASL #3 : TAX
  SEP #$20
  JSL Lyra_ReadGfx2 : PHA
  TYX : JSL Lyra_ReadGfx2 : CMP $01,S : BNE .gfx_diff
  PLA

  REP #$20
  LDA $02,S : AND.w #$00FF : ASL #3 : TAX
  SEP #$20
  JSL Lyra_ReadGfx7 : PHA
  TYX : JSL Lyra_ReadGfx7 : CMP $01,S : BNE .gfx_diff
  PLA
  SEP #$30
  BRA .check_resident

  .gfx_diff
  PLA
  SEP #$30
  JMP .yes

  .check_resident
if defined("SPECIAL_OVERWORLD_RESOURCES_ENABLED")
if !SPECIAL_OVERWORLD_RESOURCES_ENABLED == 1
  ; Resident Main-VRAM tile atlases pack each map's unique tiles from $2000+,
  ; so smooth-scrolling across two different resident Transfer pointers would
  ; overwrite the outgoing screen's live tiles mid-scroll -> force clean Mosaic.
  REP #$30
  LDA $02,S : AND.w #$00FF : ASL : TAX
  LDA.l !SPECIAL_OVERWORLD_TRANSFER_DIRECTORY, X : PHA
  LDA.b $8A : AND.w #$00FF : ASL : TAX
  LDA.l !SPECIAL_OVERWORLD_TRANSFER_DIRECTORY, X
  CMP $01,S : BEQ .same_transfer
    PLA
    SEP #$30
    JMP .yes
  .same_transfer
  PLA
  SEP #$30
endif
endif

if defined("SPECIAL_OVERWORLD_PALETTE_ENABLED")
if !SPECIAL_OVERWORLD_PALETTE_ENABLED == 1
  ; Resident packed 256B palettes differ across biomes (Deku/Goron/Sea/Snow),
  ; so smooth-scrolling across different palette pointers flashes wrong BG colors.
  REP #$30
  LDA $02,S : AND.w #$00FF : SEC : SBC.w #$0080 : PHA
  ASL : CLC : ADC $01,S : TAX : PLA
  LDA.l !SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY, X : PHA
  LDA.l !SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY+2, X : AND.w #$00FF : PHA
  LDA.b $8A : AND.w #$00FF : SEC : SBC.w #$0080 : PHA
  ASL : CLC : ADC $01,S : TAX : PLA
  LDA.l !SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY+2, X : AND.w #$00FF
  CMP $01,S : BNE .respal_diff
  LDA.l !SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY, X
  CMP $03,S : BEQ .same_respal
  .respal_diff
    PLA : PLA
    SEP #$30
    JMP .yes
  .same_respal
  PLA : PLA
  SEP #$30
endif
endif

  .no
  PLY : PLX
  LDA.b #$00
  RTL

  .yes
  PLY : PLX
  LDA.b #$01
  RTL

  ; Returns C set if A is a Sky route host ($87 or $8C-$8F), M=8.
  .is_sky
  CMP.b #$87 : BEQ .sky_yes
  CMP.b #$8C : BCC .sky_no
  CMP.b #$90 : BCC .sky_yes
  .sky_no
  CLC : RTS
  .sky_yes
  SEC : RTS

  ; Opposite direction bit indexed by $0418 (0=Up->$04, 1=Down->$08, 2=Left->$01, 3=Right->$02)
  .OppDirBit:
  db $04, $08, $01, $02
}

endif ; !SPECIAL_OVERWORLD_NATIVE == 1

SpecialOverworld_TransitionsCodeEnd:
print "Bank42 Transition Code End:       ", pc, " (", dec($42FFFF-pc()), " B free)"
assert pc() <= $5FFFFF, "Special Overworld transition code exceeds bank $5F"

; ---------------------------------------------------------
; Fixed Bank $02 / Bank $0A Hooks
; ---------------------------------------------------------

; Unify Module $0B -> Module $09 after special-area entry ($17..$1C)
assert read4($02B1B4) == $118508A9 && read2($02B1B8) == $B064, "Module09_1C_02_HandleMusic tail moved"
org $02B1B4 ; @hook module=Overworld name=SpecialOverworld_FinishSpecialEntry kind=jsl target=Oracle_SpecialOverworld_FinishSpecialEntry expected_m=8 expected_x=8 protected_size=6
  JSL SpecialOverworld_FinishSpecialEntry
  NOP #2
assert pc() == $02B1BA

if !SPECIAL_OVERWORLD_NATIVE == 1
; Hook OverworldMosaicTransition_HandleScreensAndLoadShroom FBlank dispatch
assert read4($02AE98) == $F0040AAD && read1($02AE9C) == $19, "Mosaic FBlank dispatch moved"
org $02AE98 ; @hook module=Overworld name=SpecialOverworld_MosaicFBlankHook kind=jml target=Oracle_SpecialOverworld_MosaicFBlankHook expected_m=8 expected_x=8 protected_size=5
  JML SpecialOverworld_MosaicFBlankHook
  NOP
assert pc() == $02AE9D
endif

; World Map Link dot coordinate capture (enables $80-$BF with return-cache backup)
assert read4($0AB9F0) == $80E08AA6 && read2($0AB9F4) == $0CB0, "WorldMap_FadeOut Link pos check moved"
org $0AB9F0 ; @hook module=Overworld name=SpecialOverworld_SaveAndSetMapPos kind=jsl target=Oracle_SpecialOverworld_SaveAndSetMapPos expected_m=16 expected_x=8 protected_size=18
  JSL SpecialOverworld_SaveAndSetMapPos
  BRA .world_map_pos_done
  NOP #12
.world_map_pos_done:
assert pc() == $0ABA02

; World Map 3-way palette loader (LW / DW / Special Overworld)
assert read4($0ABA40) == $480AA98B && read2($0ABA44) == $C2AB, "WorldMap_LoadLightWorldMap palette copy moved"
org $0ABA40 ; @hook module=Overworld name=SpecialOverworld_LoadWorldMapPalette kind=jsl target=Oracle_SpecialOverworld_LoadWorldMapPalette expected_m=8 expected_x=8 protected_size=39
  JSL SpecialOverworld_LoadWorldMapPalette
  BRA .world_map_pal_done
  NOP #33
.world_map_pal_done:
assert pc() == $0ABA67

pullpc
