; Dual-item binding prototype: live dispatcher and vanilla hooks. Default off.
; Included from Items/all_items.asm after Items/item_bindings_adapter.asm.
; Hooks: CheckYButtonPress new-press read ($07B07B) and both native X field-map
; reads ($0288F9 dungeon, $02A55A overworld). Routing joins MaskBinding_Tick's
; regular-item branch; reset joins LoadCheckpointOrWorld.
if !ENABLE_DUAL_ITEM_BINDING_PROTOTYPE == 1
assert !DISABLE_ITEMS == 0, "Dual-item prototype needs the item modules"
assert !ENABLE_MASK_R_BINDING == 1, "Dual-item prototype routes through MaskBinding_Tick"
; ---------------------------------------------------------
; Live dispatcher. All entries run inside gameplay with D=0; long addressing
; for owned/WRAM bytes so caller DBR does not matter.

; Called from MaskBinding_Tick .regular (base form or Minish/Moosh, no cape)
; with M8/X8. C=1: A = effective action the caller stores in $0303.
; C=0: caller keeps its original $0202 routing. X/Y preserved.
ItemBindings_Route:
{
  PHX : PHY
  ; 1. An active latch is serviced first, admitted or not, so a menu or
  ;    form change can never strand it. It ends only when the owned action's
  ;    real busy bits clear (handler completion, refusal or engine cancel).
  LDA.l ItemBindingButton : BEQ .idle
  LDA.l ItemBindingAction : CMP.b #$03 : BNE .boomerang
  LDA.w $0301 : AND.b #$10 : BNE .busy
  BRA .held
  .boomerang
  LDA.w $0301 : AND.b #$80 : BNE .busy
  .held
  LDA.b $3A : AND.b #$40 : BNE .busy
  JSL ItemBindings_EndAction
  BRA .idle
  .busy
  LDA.l ItemBindingAction
  PLY : PLX : SEC : RTL

  .idle
  JSR ItemBindings_Admitted : BCC .decline
  ; Hydrate once per session: AdapterReset leaves the cursor at zero.
  LDA.l ItemBindingCursor : BNE .hydrated
  JSL ItemBindings_AdapterLoad : BCC .decline
  .hydrated
  ; The existing menu equips Y through $0202; mirror it as saved Y.
  LDA.l $7E0202 : STA.l ItemBindingSavedY : STA.l ItemBindingCursor

  ; 2. Start permission: reuse the R-binding guards plus sword/bunny.
  LDA.w $0301 : ORA.w $037A : BNE .no_start
  LDA.b $3A : AND.b #$40 : BNE .no_start
  LDA.b $3C : ORA.b $46 : ORA.b $6C : ORA.b $5D : BNE .no_start
  LDA.w $0FFC : ORA.w $02E0 : BNE .no_start
  LDA.b #$01 : BRA .try
  .no_start
  LDA.b #$00
  .try
  JSL ItemBindings_TryBegin : BCC .decline
  LDA.l ItemBindingAction
  PLY : PLX : SEC : RTL

  .decline
  PLY : PLX : CLC : RTL
}

; C=1 when the prototype may route: base Link or GBC form, current $0202 is
; an owned Bow/Boomerang. M8 near helper; A clobbered.
ItemBindings_Admitted:
{
  LDA.l $7E0000+!CurrentMask : BEQ .form_ok
  CMP.b #$06 : BNE .no
  .form_ok
  LDA.l $7E0202 : JSR ItemBindings_Validate : RTS
  .no
  CLC : RTS
}

; C=1 when X belongs to the second item: admitted, hydrated, X assigned.
ItemBindings_OwnsX:
{
  JSR ItemBindings_Admitted : BCC .no
  LDA.l ItemBindingSavedVersion : CMP.b #$01 : BNE .no
  LDA.l ItemBindingSavedX : JSR ItemBindings_Validate : RTS
  .no
  CLC : RTS
}

; Replaces LDA $F4 : AND #$40 in CheckYButtonPress ($07B07B), M8.
; Returns the latched initiating button's new-press bit; Y otherwise.
; Z/A contract of the following BEQ/TSB $3A is preserved.
ItemBindings_UsePress:
{
  LDA.l ItemBindingButton : CMP.b #$02 : BEQ .x
  LDA.b $F4 : AND.b #$40 : RTL
  .x
  LDA.b $F6 : AND.b #$40 : RTL
}

; Replaces LDA $F6 : AND #$40 at both native X field-map reads, M8.
; Zero while the prototype owns X; the original bit otherwise.
ItemBindings_MapPress:
{
  PHX : PHY
  JSR ItemBindings_OwnsX
  PLY : PLX
  BCS .owned
  LDA.b $F6 : AND.b #$40 : RTL
  .owned
  LDA.b #$00 : RTL
}

pushpc
assert read4($07B07B) == $4029F4A5, "CheckYButtonPress new-press read moved"
org $07B07B ; @hook module=Items name=ItemBindings_UsePress kind=jsl target=ItemBindings_UsePress expected_m=8
  JSL ItemBindings_UsePress
assert read4($0288F9) == $4029F6A5, "Dungeon X map read moved"
org $0288F9 ; @hook module=Items name=ItemBindings_DungeonMapPress kind=jsl target=ItemBindings_MapPress expected_m=8
  JSL ItemBindings_MapPress
assert read4($02A55A) == $4029F6A5, "Overworld X map read moved"
org $02A55A ; @hook module=Items name=ItemBindings_OverworldMapPress kind=jsl target=ItemBindings_MapPress expected_m=8
  JSL ItemBindings_MapPress
pullpc
endif
