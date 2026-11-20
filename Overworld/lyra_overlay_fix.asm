; =========================================================
; Lyra/Sky overlay fix
;
; scawful 2026-11-08: "if Lyra sea doesn't support overlays how can we
; support song of storms ? We may need to fix that gap".
;
; Two gaps, both in how the overworld treats areas >= $80:
;
;   F1  Overworld_ReloadSubscreenOverlay (ZSCustomOverworld.asm, $02AF58)
;       tested "$8A >= $0080" and sent every such area down the special-area
;       path: exit-room overlays ($0180/$0181/$0189), then "no overlay"
;       ($8C = $FF, $1D = 0, $9A = 0). It never reached the subscreen overlay
;       table, so a reload on a tail map ($A0-$BF, Lyra_ReadOverlay /
;       descriptor family 5) or a reload during Song of Storms rain on a Sky
;       map ($80-$9F) dropped the rain picture while ActivateSubScreen
;       ($1D = 1) still enabled the empty subscreen.
;       LyraOverlay_UseTablePath replaces that test. It returns:
;         C clear: take the table path (ReadOverlayArray, weather overrides,
;                  Song of Storms rain $9F, LoadSubscreenOverlay)
;         C set:   keep the special-area path (unchanged vanilla/ZS flow)
;       Table path for:
;         $A0-$BF  tail maps, always (native builds only; legacy builds have
;                  160 overlay rows and no tail maps)
;         $80-$9F  only while Song of Storms rain ($7EE00E != 0) is active and
;                  the exit room is none of $0180/$0181/$0182/$0189 (their
;                  mist, bridge, triforce and waterfall flows stay as they are)
;         $87/$8C-$8F ordinary table clouds with ENABLE_SKY_OVERWORLD_ROUTE;
;                  the same four exit-room exceptions retain precedence.
;       Other Sky without rain and areas >= $C0 keep the special-area path.
;
;   F2a Map16 event overlay (Overworld_LoadMapData, $02EF50): a set bit $20
;       in the area's event byte calls ApplyOverworldOverlay ($0EF652), which
;       indexes a 160-entry, 3-byte vector table (dw/db at $0EF677) with
;       $8A * 3. A tail map ($A0-$BF) would read past the table and jump to
;       junk. Tail event bit $20 is set by generic routines (rock piles,
;       entrance animations), so it is reachable. LyraOverlay_ApplyOverworldOverlay
;       makes the call a no-op for $8A >= $A0; other areas are unchanged.
;       (The tail pointer table, F2b, is a separate job.)
;
; Included from Items/all_items.asm (bank $2B free space).
; The ZSCustomOverworld.asm hook site calls LyraOverlay_UseTablePath.
; =========================================================

; ---------------------------------------------------------
; F1: choose the reload path for areas >= $80.
; Hook site: Overworld_ReloadSubscreenOverlay_Interupt (ZSCustomOverworld.asm),
;   was  LDA.b $8A : CMP.w #$0080 : BCC .notExtendedArea  (7 bytes)
;   now  JSL LyraOverlay_UseTablePath : BCC .notExtendedArea : NOP  (7 bytes)
; Entry:  M=16, X/Y any width (the caller runs X=16). $8A is the area.
; Exit:   M, X, Y and the data bank untouched; A, N and Z clobbered;
;         C clear = table path, C set = special-area path.
LyraOverlay_UseTablePath:
{
  LDA.b $8A
  CMP.w #$0080 : BCC .table              ; not reached from the hook; keeps the old meaning
if !SPECIAL_OVERWORLD_NATIVE == 1
  CMP.w #$00A0 : BCC .sky
  CMP.w #$00C0 : BCC .table              ; tail maps $A0-$BF: always the table
  BRA .special                           ; >= $C0: unchanged
endif

  .sky
if !ENABLE_SKY_OVERWORLD_ROUTE == 1
  ; All 8 Sky maps ($84-$87, $8C-$8F) use the area overlay table (clouds $94
  ; or $FF when unauthored) without requiring Song of Storms.
  ; Keep the special exit-room pictures ahead of the area-table selection.
  LDA.b $8A : CMP.w #$0084 : BCC .weather
  CMP.w #$0088 : BCC .sky_host
  CMP.w #$008C : BCC .weather
  CMP.w #$0090 : BCS .weather
  .sky_host
  LDA.b $A0
  CMP.w #$0180 : BEQ .special
  CMP.w #$0181 : BEQ .special
  CMP.w #$0182 : BEQ .special
  CMP.w #$0189 : BEQ .special
  BRA .table
  .weather
endif
  LDA.l $7EE00E : AND.w #$00FF : BEQ .special   ; Song of Storms rain off
  LDA.b $A0
  CMP.w #$0180 : BEQ .special           ; master sword mist
  CMP.w #$0181 : BEQ .special           ; under the bridge
  CMP.w #$0182 : BEQ .special           ; Zora falls (waterfall SFX)
  CMP.w #$0189 : BEQ .special           ; triforce room

  .table
  CLC
  RTL

  .special
  SEC
  RTL
}


; ---------------------------------------------------------
; F2a: map16 event overlay guard.
; Hook site: $02EF50 in Overworld_LoadMapData, M=8 X=8 (SEP #$30 at $02EF40),
;   was  JSL ApplyOverworldOverlay  ($0EF652)
;   now  JSL LyraOverlay_ApplyOverworldOverlay
; ApplyOverworldOverlay clobbers A/X/Y and returns with RTL (the code after
; the hook reloads X from $8A), so the guard may clobber A the same way.
; JML (not JSR/JSL) so ApplyOverworldOverlay's RTL returns to $02EF54.
LyraOverlay_ApplyOverworldOverlay:
{
  LDA.b $8A : CMP.b #$A0 : BCS .skip     ; tail maps: no 3-byte vector row exists
  JML $0EF652
  .skip
  RTL
}

pushpc

; Overworld_LoadMapData: JSL ApplyOverworldOverlay (4 bytes: 22 52 F6 0E).
assert read4($02EF50) == $0EF65222 || read4($02EF50) == ((LyraOverlay_ApplyOverworldOverlay<<8)|$22), "LyraOverlayFix hook $02EF50: unexpected bytes"
org $02EF50 : JSL LyraOverlay_ApplyOverworldOverlay ; @hook module=Overworld kind=jsl target=LyraOverlay_ApplyOverworldOverlay expected_m=8 expected_x=8 name=LyraOverlayFix02EF50
assert pc() == $02EF54

pullpc

print  "End of lyra_overlay_fix.asm       ", pc
