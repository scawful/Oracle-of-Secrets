; =========================================================
; Lyra edge guard (native special overworld builds)
;
; Tail maps $A0-$BF are an 8x4 grid (rows 4-7 of the screen-id space).
; OverworldHandleTransitions (ZSCustomOverworld.asm, .transition) adds
; +2 / -2 / +$10 / -$10 to the screen id with no row or column clamp, so an
; open outer edge loads the wrong map:
;   west off column 0   -> column 7 of the row above
;   east off column 7   -> column 0 of the row below
;   north off $A2-$A7   -> Sky $9A-$9F
;   south off $B8-$BF   -> $C0-$C7 (no page)
; North off $A0 and $A1 stays open: $A0 <-> $98 and $A1 <-> $99 are routes.
;
; LyraEdgeGuard replaces the JSL target at that call site. It runs the
; vanilla Player_IsScreenTransitionPermitted ($07F439) first and returns its
; refusal unchanged. On a tail map it then refuses a transition across a
; guarded outer edge the same way vanilla refuses one ($07F452-$07F469):
; clear Link's Y/X velocity and put him back on the position Link_Main saved
; at the start of the frame ($0FC2/$0FC4). Both axes are restored because the
; caller tests the vertical edge first and skips the horizontal test on that
; frame.
;
; $0700 is Link's own cell * 2, low byte (row << 4) | (column << 1), set from
; $20/$22 every frame at $02A5B1. It is not the parent area, so the guard
; holds inside large areas ($8A is the parent there).
;
; Included from Items/all_items.asm (bank $2B free space): bank $34 is full.
; JSL entry, RTL exit; operands are direct page, long or immediate.
; =========================================================

; ---------------------------------------------------------
; Entry:  M=8, X=8, D=$0000. Y = direction (0 right, 2 left, 4 down, 6 up).
; Exit:   M=8, X=8. X, Y, D and the data bank untouched. A, N, Z clobbered.
;         C clear = transition permitted, C set = refused.
;         On a guard refusal: $27 = $28 = 0, $22 = $0FC2, $20 = $0FC4.
LyraEdgeGuard:
{
  JSL $07F439 : BCS .done                 ; Player_IsScreenTransitionPermitted

  LDA.b $8A
  CMP.b #!LYRA_CURRENT_FIRST : BCC .allow ; below $A0: not a tail map
  CMP.b #!LYRA_CURRENT_END : BCS .allow   ; $C0 and up: not a tail map

  LDA.l $7E0700                           ; (row << 4) | (column << 1)
  CPY.b #$04 : BCS .vertical
    AND.b #$0E                            ; column * 2
    CPY.b #$02 : BEQ .left
      CMP.b #$0E : BEQ .block             ; east off column 7
      BRA .allow
    .left
    CMP.b #$00 : BEQ .block               ; west off column 0
    BRA .allow

  .vertical
  CPY.b #$06 : BEQ .up
    AND.b #$F0 : CMP.b #$70 : BEQ .block  ; south off row 7
    BRA .allow

  .up
  ; North off row 4, columns 2-7. $40 ($A0) and $42 ($A1) stay open.
  CMP.b #$44 : BCC .allow
  CMP.b #$50 : BCS .allow                 ; rows 5-7: inner edge

  .block
  STZ.b $27 : STZ.b $28                   ; Link Y / X velocity
  REP #$20
  LDA.l $7E0FC2 : STA.b $22               ; X saved at the start of Link_Main
  LDA.l $7E0FC4 : STA.b $20               ; Y saved at the start of Link_Main
  SEP #$20
  SEC
  RTL

  .allow
  CLC
  .done
  RTL
}

print  "End of lyra_edge_guard.asm        ", pc
