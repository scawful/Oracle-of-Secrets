; Dual-item binding prototype. Default off.
; Core + load/reset adapter; ORG-free so the compiled fixture can assemble it
; alone. Live routing and the three vanilla hooks are in
; Items/item_bindings_dispatch.asm, included right after this file.
assert defined("ENABLE_DUAL_ITEM_BINDING_PROTOTYPE"), "Use canonical feature defaults"

if !ENABLE_DUAL_ITEM_BINDING_PROTOTYPE == 1
assert ItemBindingSavedVersion == $7EF3B9
assert ItemBindingSavedY == $7EF3BA && ItemBindingSavedX == $7EF3BB
assert ItemBindingCursor == $7E02B3 && ItemBindingButton == $7E02B6

incsrc "item_bindings.asm"

; Native, D=0, arbitrary M/X/DBR. Full A, X/Y, DBR and P preserved.
; Clear only our four bytes; no ferry, original symbols, inventory or saved
; binding writes. An eventual owner calls this on load/context cancellation,
; not each button-release frame of an active action.
ItemBindings_AdapterReset:
{
  PHP : REP #$20 : PHA : SEP #$20
  LDA.b #$00
  STA.l ItemBindingCursor : STA.l ItemBindingLogical
  STA.l ItemBindingAction : STA.l ItemBindingButton
  REP #$20 : PLA : PLP : RTL
}

; Admitted prototype load only. Preserve full A and P except C=admitted.
; Current vanilla Y must already be an owned latchable item (Validate).
; Otherwise leave ALL saved bytes unchanged, reset transient prototype state,
; and return C=0. This prevents the core's fallback migration from changing
; unsupported existing assignments. $0202 and physical controls never change.
; No automatic call from the live file-load or menu path exists in this slice.
ItemBindings_AdapterLoad:
{
  PHP : REP #$20 : PHA : SEP #$20
  JSL ItemBindings_AdapterReset
  LDA.l $7E0202 : JSR ItemBindings_Validate : BCC .refuse
  JSL ItemBindings_Load
  REP #$20 : PLA : PLP : SEC : RTL
.refuse
  REP #$20 : PLA : PLP : CLC : RTL
}

endif
