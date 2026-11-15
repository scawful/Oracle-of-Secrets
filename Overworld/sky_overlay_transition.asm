; Ordinary Sky BG1 rebinding lives in the existing resident graphics code
; reservation, directly after its existing upload routines.
; No new ROM reservation or WRAM state is introduced.
LyraOverlay_TransitionCodeStart:
; C set only while a selected Sky host is waiting for its own BG1 rebuild.
; M16; A/flags clobbered, X/Y/DBR untouched. Special-exit pictures retain
; their original policy. This is a transition gate, not an overlay policy.
LyraOverlay_StaleHost:
{
  LDA.b $1B : AND.w #$00FF : BNE .no
  LDA.b $10 : AND.w #$00FF : CMP.w #$0009 : BNE .no
  LDA.b $11 : AND.w #$00FF : BEQ .no
  CMP.w #$0009 : BCS .no
  LDA.b $8A : CMP.w #$0087 : BEQ .host
  CMP.w #$008C : BCC .no
  CMP.w #$0090 : BCS .no
.host:
  CMP.l $7EC213 : BEQ .no
  LDA.b $A0
  CMP.w #$0180 : BEQ .no
  CMP.w #$0181 : BEQ .no
  CMP.w #$0182 : BEQ .no
  CMP.w #$0189 : BEQ .no
  SEC : RTL
.no:
  CLC : RTL
}

; Same M16 interface as the existing Docks predicate. Keep its result first.
LyraOverlay_ShouldHideSubscreen:
{
  JSL Docks_ShouldHideSubscreen : BCS .done
  JSL LyraOverlay_StaleHost
.done:
  RTL
}

; Called before the first destination CHR upload. Preserve caller widths and
; registers; the later fixed-color path observes the same stale-host gate.
LyraOverlay_HideStale:
{
  PHP : REP #$20 : PHA
  JSL LyraOverlay_StaleHost : BCC .done
  SEP #$20 : STZ.b $1D
.done:
  REP #$20 : PLA : PLP : RTL
}

; Stage08 begins after scroll uploads finish. Reuse the complete native reload
; (02AF1E, reached through02B1F4), including the host save/restore and upload04.
; Reload even when old/new pictures are both9C: their resident CHR differs.
; The maintained wrapper balances its own INC11; camera movement remains in
; the original finalize-entry caller. No fresh WRAM allocation or state flag.
!LyraOverlayFinishOriginal = read3($02C243)
LyraOverlay_FinishTransition:
{
  PHP : PHB : PHD : REP #$30 : PHA : PHX : PHY
  PEA.w $0000 : PLD
  LDA.b $11 : AND.w #$00FF : CMP.w #$0008 : BNE .done
  JSL LyraOverlay_StaleHost : BCC .done
  LDA.b $17 : AND.w #$00FF : BNE .uploadPending
  LDA.w $0710 : AND.w #$00FF : BNE .uploadPending
  ; The native JSR callee uses bank02 absolute data references.
  PEA.w $0202 : PLB : PLB
  SEP #$30
  JSL $02B1F4
  ; Stage04 hid the old host and left neutral fixed color. Restore the normal
  ; profile/blend and BG1 scroll after C213 identifies the new host. This
  ; existing routine reads BG2 camera E2/E8; it never moves that camera.
  JSL $0BFE70
.done:
  REP #$30 : PLY : PLX : PLA : PLD : PLB : PLP
  JSL !LyraOverlayFinishOriginal
  JML $02C246
.uploadPending:
  ; Keep stage08 and its walking position until the previous NMI completes.
  ; Otherwise the original caller could finish the transition without a reload.
  REP #$30 : PLY : PLX : PLA : PLD : PLB : PLP
  JML $02C2A3
}

pushpc
assert read1($02C242) == $22, "Sky finalize-entry animation call moved"
org $02C242 ; @hook module=Overworld name=SkyOverlayFinishTransition kind=jml target=LyraOverlay_FinishTransition expected_m=8 expected_x=8 protected_size=4
  JML LyraOverlay_FinishTransition
assert pc() == $02C246
pullpc
LyraOverlay_TransitionCodeEnd:
assert pc() <= !SPECIAL_OVERWORLD_RESOURCE_CODE_END, "Sky overlay transition exceeds resident graphics reservation"
