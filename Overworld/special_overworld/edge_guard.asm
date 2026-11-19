; =========================================================
; Special Overworld edge guard (native special overworld builds)
;
; Special Overworld ($80-$BF) is an 8x8 grid (rows 0-7 of the screen-id space).
; OverworldHandleTransitions (ZSCustomOverworld.asm, .transition) adds
; +2 / -2 / +$10 / -$10 to the screen id with no row, column, or region clamp,
; so an open outer edge or unlinked seam loads the wrong map or an overlay:
;   north off row 0 ($80-$87) -> Dark World ($78-$7F)
;   south off row 7 ($B8-$BF) -> $C0-$C7 (no page)
;   west off column 0         -> column 7 of the row above
;   east off column 7         -> column 0 of the row below
;   internal unlinked seams   -> overlays ($93-$97, $9C-$9F), curtain room
;                                ($88), unlinked Sky drafts ($84-$86), isolated
;                                Tail Woods ($80), walled North Reef ($92), or
;                                reserved Fortress slot ($9B).
;
; SpecialOverworldEdgeGuard replaces the JSL target at $02A9C4 (.transition).
; LyraEdgeGuard is a searchable alias and exports Oracle_LyraEdgeGuard.
; The guard runs vanilla Player_IsScreenTransitionPermitted ($07F439) first and returns its
; refusal unchanged. On any Special Overworld map ($80-$BF), it looks up the
; physical cell's 4-direction permission mask in .Permissions (indexed via
; ($7E0700 & $7E) >> 1) and refuses disallowed transitions the same way vanilla
; refuses one ($07F452-$07F469): clear Link's Y/X velocity and restore the
; position Link_Main saved at the start of the frame ($0FC2/$0FC4). Both axes
; are restored because the caller tests the vertical edge first and skips the
; horizontal test on that frame.
;
; $0700 is Link's own cell * 2, low byte (row << 4) | (column << 1), set from
; $20/$22 every frame at $02A5B1. It is not the parent area, so the guard
; holds inside large, wide, and tall areas ($8A is the parent there).
;
; Included from Overworld/overworld.asm (bank $34).
; JSL entry, RTL exit; operands are direct page, long or immediate.
; =========================================================

!EG_NONE = $00
!EG_R    = $01 ; Y = $00 (Right / East)
!EG_L    = $02 ; Y = $02 (Left / West)
!EG_D    = $04 ; Y = $04 (Down / South)
!EG_U    = $08 ; Y = $06 (Up / North)
!EG_ALL  = $0F

; ---------------------------------------------------------
; Entry:  M=8, X=8, D=$0000. Y = direction (0 right, 2 left, 4 down, 6 up).
; Exit:   M=8, X=8. X, Y, D and the data bank untouched. A, N, Z clobbered.
;         C clear = transition permitted, C set = refused.
;         On a guard refusal: $27 = $28 = 0, $22 = $0FC2, $20 = $0FC4.
; LyraEdgeGuard shares this entry. The brace binds sublabels to
; SpecialOverworldEdgeGuard. Inside namespace Oracle both entry names
; export, and ZSCustomOverworld.asm still enters through JSL.l Oracle_LyraEdgeGuard.
LyraEdgeGuard:
SpecialOverworldEdgeGuard:
{
  JSL $07F439 : BCS .done                 ; Player_IsScreenTransitionPermitted

  LDA.b $8A
  CMP.b #$80 : BCC .allow                 ; LW ($00-$3F) & DW ($40-$7F): unchecked
  CMP.b #$C0 : BCS .allow                 ; >= $C0: outside Special Overworld

  PHX
  LDA.l $7E0700                           ; ((row << 4) | (col << 1)) for $80-$BF
  AND.b #$7E                              ; 64-map offset * 2
  LSR
  TAX                                     ; X = map_id - $80 (0..63)
  LDA.l .Permissions, X
  TYX                                     ; X = Y (0, 2, 4, 6)
  AND.l .DirMask, X
  BNE .permit_pop
    PLX
    BRA .block

  .permit_pop
  PLX

  .allow
  CLC
  .done
  RTL

  .block
  STZ.b $27 : STZ.b $28                   ; Link Y / X velocity
  REP #$20
  LDA.l $7E0FC2 : STA.b $22               ; X saved at the start of Link_Main
  LDA.l $7E0FC4 : STA.b $20               ; Y saved at the start of Link_Main
  SEP #$20
  SEC
  RTL

  .DirMask
  db !EG_R, $00, !EG_L, $00, !EG_D, $00, !EG_U, $00

  ; Per-map allowed screen-transition bitmasks for Special Overworld ($80-$BF).
  ; Indexed by (physical_map_id - $80) via ($7E0700 & $7E) >> 1.
  ; Overlays ($93-$97, $9C-$9F), curtain room ($88), unlinked Sky drafts
  ; ($84-$86), isolated Tail Woods ($80), walled North Reef ($92), reserved
  ; Fortress slot ($9B), outer borders, and unlinked seams are hard-blocked.
  .Permissions
  ; Row 0 ($80-$87): Korok N ($81-$82), Garrison N ($83), Sky Tower ($87)
  db !EG_NONE                             ; $80: Tail Woods/Swamp (triggers only)
  db !EG_R|!EG_D                          ; $81: Korok Cove NW <-> $82, $89
  db !EG_R|!EG_L|!EG_D                    ; $82: Korok Cove NE <-> $81, $8A, $83 (Garrison bridge)
  db !EG_L|!EG_D                          ; $83: Garrison Top <-> $82, $8B
  db !EG_NONE                             ; $84: Sky Ice draft (unlinked)
  db !EG_NONE                             ; $85: Sky void draft (unlinked)
  db !EG_NONE                             ; $86: Sky legacy draft (unlinked)
  db !EG_D                                ; $87: Sky Tower / D8 <-> $8F

  ; Row 1 ($88-$8F): Korok S ($89-$8A), Garrison S ($8B), Sky chain ($8C-$8F)
  db !EG_NONE                             ; $88: Dark curtain indoor room
  db !EG_R|!EG_U                          ; $89: Korok Cove SW <-> $81, $8A
  db !EG_ALL                              ; $8A: Korok Cove SE <-> $82, $89, $8B (Garrison), $92 (North Reef channel)
  db !EG_L|!EG_U                          ; $8B: Garrison Bottom <-> $8A, $83 ($8C/$93 blocked)
  db !EG_R                                ; $8C: Sky West Landing <-> $8D ($94 overlay blocked)
  db !EG_R|!EG_L                          ; $8D: Sky Bridge W <-> $8C, $8E ($95 overlay blocked)
  db !EG_R|!EG_L                          ; $8E: Sky Bridge E <-> $8D, $8F ($96 overlay blocked)
  db !EG_L|!EG_U                          ; $8F: Sky East <-> $8E, $87 ($97 overlay blocked)

  ; Row 2 ($90-$97): Sea Zora N ($90), Wisdom ($91), Reef ($92), Overlays ($93-$97)
  db !EG_D                                ; $90: Sea Zora N <-> $98 ($88/$91/col 0 W blocked)
  db !EG_D                                ; $91: Shrine of Wisdom <-> $99 ($89/$90/$92 blocked)
  db !EG_U                                ; $92: North Reef <-> $8A N channel ($91 W / $9A S / $93 overlay E blocked)
  db !EG_NONE                             ; $93: Overlay (triforce curtain)
  db !EG_NONE                             ; $94: Overlay (under bridge)
  db !EG_NONE                             ; $95: Overlay (sky bg)
  db !EG_NONE                             ; $96: Overlay (pyramid bg)
  db !EG_NONE                             ; $97: Overlay (fog 1)

  ; Row 3 ($98-$9F): Sea Zora S ($98), Quay ($99), C-Island ($9A), Reserved/Overlays ($9B-$9F)
  db !EG_ALL                              ; $98: Sea Zora S <-> $90, $99, $A0, and LW $1F West cross-world
  db !EG_R|!EG_L|!EG_D|!EG_U              ; $99: Zora Quay <-> $91, $98, $9A, $A1
  db !EG_L|!EG_D                          ; $9A: C-Island <-> $99, $A2 ($92 C80 N / $9B E blocked)
  db !EG_NONE                             ; $9B: Reserved Fortress slot ($93/$9C overlays N/E)
  db !EG_NONE                             ; $9C: Overlay (lava bg / Fortress reserved)
  db !EG_NONE                             ; $9D: Overlay (fog 2 / Fortress reserved)
  db !EG_NONE                             ; $9E: Overlay (tree canopy)
  db !EG_NONE                             ; $9F: Overlay (rain)

  ; Row 4 ($A0-$A7): Zora Coast ($A0-$A1), Lyra Sea ($A2-$A7)
  db !EG_R|!EG_L|!EG_U                    ; $A0: Zora Coast W <-> $98, $A1, and LW $27 West cross-world ($A8 S blocked)
  db !EG_R|!EG_L|!EG_U                    ; $A1: Zora Coast E <-> $A0, $99, $A2 ($A9 C80 S blocked)
  db !EG_R|!EG_L|!EG_D|!EG_U              ; $A2: Lyra Sea <-> $9A, $A1, $A3, $AA
  db !EG_R|!EG_L|!EG_D                    ; $A3: Twin-Tree Island <-> $A2, $A4, $AB ($9B N blocked)
  db !EG_R|!EG_L|!EG_D                    ; $A4: Twin Sandbars <-> $A3, $A5, $AC ($9C overlay N blocked)
  db !EG_R|!EG_L|!EG_D                    ; $A5: Tiny Atoll <-> $A4, $A6, $AD ($9D overlay N blocked)
  db !EG_R|!EG_L|!EG_D                    ; $A6: Shrine of Courage NW <-> $A5, $A7, $AE ($9E overlay N blocked)
  db !EG_L|!EG_D                          ; $A7: Shrine of Courage NE <-> $A6, $AF ($9F overlay N / col 7 E blocked)

  ; Row 5 ($A8-$AF): Deku ($A8-$A9), Lyra Sea ($AA-$AF)
  db !EG_R|!EG_L|!EG_D                    ; $A8: Deku W <-> $A9, $B0, and LW $2F West cross-world
  db !EG_L|!EG_D                          ; $A9: Deku E <-> $A8, $B1 ($AA C80 wall E / $A1 N blocked)
  db !EG_R|!EG_D|!EG_U                    ; $AA: Square Island <-> $A2, $AB, $B2 ($A9 C80 W blocked)
  db !EG_R|!EG_L|!EG_D|!EG_U              ; $AB: Hut Island <-> $A3, $AA, $AC, $B3
  db !EG_R|!EG_L|!EG_D|!EG_U              ; $AC: Green Island W <-> $A4, $AB, $AD, $B4
  db !EG_R|!EG_L|!EG_D|!EG_U              ; $AD: Green Island E <-> $A5, $AC, $AE, $B5
  db !EG_R|!EG_L|!EG_D|!EG_U              ; $AE: Shrine of Courage SW <-> $A6, $AD, $AF, $B6
  db !EG_L|!EG_D|!EG_U                    ; $AF: Shrine of Courage SE <-> $A7, $AE, $B7 (col 7 E blocked)

  ; Row 6 ($B0-$B7): Goron Desert N ($B0-$B1), Lyra Sea ($B2-$B7)
  db !EG_ALL                              ; $B0: Goron Desert NW <-> $B1, $B8, $A8, and LW $37 West cross-world
  db !EG_R|!EG_L|!EG_D|!EG_U              ; $B1: Goron Desert NE <-> $B0, $B9, $A9 (road), $B2 (overlook)
  db !EG_R|!EG_L|!EG_D|!EG_U              ; $B2: Sea/Cliff <-> $AA, $B1, $B3, $BA
  db !EG_R|!EG_L|!EG_D|!EG_U              ; $B3: Crescent NW <-> $AB, $B2, $B4, $BB
  db !EG_R|!EG_L|!EG_D|!EG_U              ; $B4: Crescent NE <-> $AC, $B3, $B5, $BC
  db !EG_R|!EG_L|!EG_D|!EG_U              ; $B5: Tower Island N <-> $AD, $B4, $B6, $BD
  db !EG_R|!EG_L|!EG_D|!EG_U              ; $B6: Sandbar <-> $AE, $B5, $B7, $BE
  db !EG_L|!EG_D|!EG_U                    ; $B7: Crescent Sandbar <-> $AF, $B6, $BF (col 7 E blocked)

  ; Row 7 ($B8-$BF): Goron Desert S ($B8-$B9), Lyra Sea S ($BA-$BF)
  db !EG_R|!EG_L|!EG_U                    ; $B8: Goron Desert SW <-> $B0, $B9, and LW $3F West cross-world (row 7 S blocked)
  db !EG_R|!EG_L|!EG_U                    ; $B9: Goron Desert SE <-> $B1, $B8, $BA (Harbor stairs E)
  db !EG_R|!EG_L|!EG_U                    ; $BA: Harbor/Sea <-> $B2, $B9 (stairs W), $BB
  db !EG_R|!EG_L|!EG_U                    ; $BB: Crescent SW <-> $B3, $BA, $BC
  db !EG_R|!EG_L|!EG_U                    ; $BC: Crescent SE <-> $B4, $BB, $BD
  db !EG_R|!EG_L|!EG_U                    ; $BD: Tower Island S <-> $B5, $BC, $BE
  db !EG_R|!EG_L|!EG_U                    ; $BE: Snow Island W <-> $B6, $BD, $BF
  db !EG_L|!EG_U                          ; $BF: Snow Island E <-> $B7, $BE (col 7 E / row 7 S blocked)
}

print  "End of special_overworld/edge_guard.asm ", pc
