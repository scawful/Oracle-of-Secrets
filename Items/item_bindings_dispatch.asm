; Dual-item binding: live dispatcher and vanilla hooks.
; Included from Items/all_items.asm after Items/item_bindings_adapter.asm.
; Hooks: CheckYButtonPress new-press read ($07B07B), both native X field-map
; reads ($0288F9 dungeon, $02A55A overworld), LinkItem_ShovelAndFlute Ocarina
; dispatch ($07A313), and Ancilla31_CaneOfByrna cancel check ($08DCBE).
; Routing joins MaskBinding_Tick's regular-item branch; reset joins LoadCheckpointOrWorld.
assert !DISABLE_ITEMS == 0, "Dual-item binding needs the item modules"
; ---------------------------------------------------------
; Live dispatcher. All entries run inside gameplay with D=0; long addressing
; for owned/WRAM bytes so caller DBR does not matter.

; Called from MaskBinding_Tick .regular (base form, GBC or Minish/Moosh, no cape)
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
  CMP.b #$02 : BNE .other
  LDA.w $0301 : AND.b #$80 : BNE .busy
  ; The throw bits clear before the flight ends; a live boomerang ancilla
  ; ($05) keeps the action owned until it returns or is destroyed.
  LDA.b #$05 : BRA .ancilla
  .other
  ; Other latchable handlers: item-use bits, a Link state (hookshot pull,
  ; feather jump, mirror warp) or a live shot/shield ancilla keep the action
  ; owned: hookshot ($1F), Fire Rod ($02), Ice Rod ($0B), Byrna ($30/$31),
  ; or active Fishing Rod ($7F5BA2). The Ice Rod water freeze (Items/ice_rod.asm)
  ; reads $0303/$0304 == 6 when the shot lands, so an X shot keeps ownership.
  PHA
  LDA.w $0301 : ORA.w $037A : ORA.b $5D
  BEQ +
    PLA : BRA .busy
  +
  PLA : CMP.b #$0E : BEQ .hookshot
  CMP.b #$06 : BEQ .ice_rod
  CMP.b #$05 : BEQ .fire_rod
  CMP.b #$0D : BNE .held
  JSR ItemBindings_RodOrByrna
  BEQ .end_latch
  CMP.b #$01 : BEQ .busy
  BRA .held
  .fire_rod
  LDA.b #$02 : BRA .ancilla
  .ice_rod
  LDA.b #$0B : BRA .ancilla
  .hookshot
  LDA.b #$1F
  .ancilla
  LDX.b #$04
  -
  CMP.w $0C4A,X : BEQ .busy
  DEX : BPL -
  .held
  LDA.b $3A : AND.b #$40 : BNE .busy
  .end_latch
  JSL ItemBindings_EndAction
  BRA .idle
  .busy
  LDA.l ItemBindingAction
  JSR ItemBindings_SyncBottle
  PLY : PLX : SEC : RTL

  .idle
  JSR ItemBindings_Admitted : BCC .decline
  ; Hydrate once per session: AdapterReset leaves the cursor at zero.
  ; Load directly (not AdapterLoad): any owned Y item still lets X route.
  ; Load never writes $0202; the lines below set saved Y and cursor from $0202.
  LDA.l ItemBindingCursor : BNE .hydrated
  LDA.l $7E0202 : BEQ .decline
  JSL ItemBindings_Load
  .hydrated
  ; The menu equips Y through $0202; keep the saved Y equal to it. Load
  ; restores $0202 from it (ItemBindings_RestoreY) before the HUD rebuild.
  LDA.l $7E0202 : BEQ .decline
  STA.l ItemBindingSavedY : STA.l ItemBindingCursor

  ; 2. Start permission: reuse the R-binding guards plus sword/bunny.
  LDA.w $0301 : ORA.w $037A : BNE .no_start
  LDA.b $3A : AND.b #$40 : BNE .no_start
  LDA.b $3C : ORA.b $46 : ORA.b $6C : ORA.b $5D : BNE .no_start
  LDA.w $0FFC : BNE .no_start
  LDA.w $02E0 : BEQ .can_start
    ; Bunny state ($02E0 != 0): only Mirror ($14) and Bottles ($0B) may start
    ; (matches vanilla Link_HandleYItem at $079B16).
    LDA.b $F4 : AND.b #$40 : BNE .bunny_y
    LDA.b $F6 : AND.b #$40 : BEQ .no_start
    LDA.l ItemBindingSavedX : BRA .bunny_chk
    .bunny_y
    LDA.l ItemBindingSavedY
    .bunny_chk
    JSR ItemBindings_MapAction
    CMP.b #$0B : BEQ .can_start
    CMP.b #$14 : BNE .no_start
  .can_start
  ; X and Y may share an action routine (Bombs/Bombchu, Hookshot/Goldstar/
  ; Switch Hook, Fishing/Portal/Byrna, Bottles 1-4): variant reads go through
  ; ItemBindings_EffectiveItem / ItemBindings_SyncBottle, so each button fires
  ; its own item.
  LDA.b #$01 : BRA .try
  .no_start
  LDA.b #$00
  .try
  JSL ItemBindings_TryBegin : BCC .decline
  BRA .busy

  .decline
  PLY : PLX : CLC : RTL
}

; M8/X8 near helper for Action == #$0D (Fishing Rod $10, Byrna $1B, Portal $19).
; Out: A = 0 -> release latch immediately, 1 -> busy, 2 -> fall through to .held.
ItemBindings_RodOrByrna:
{
  LDA.l ItemBindingLogical : CMP.b #$10 : BNE .byrna
    LDA.l $7F5BA2 : BNE .busy
    BRA .held
  .byrna
  CMP.b #$1B : BNE .held
    LDA.l ItemBindingButton : CMP.b #$02 : BNE .byrna_y
      LDA.l ItemBindingSavedX : CMP.b #$1B : BNE .release
      BRA .scan
    .byrna_y
    LDA.l $7E0202 : CMP.b #$1B : BNE .release
    .scan
    LDX.b #$04
    -
    LDA.w $0C4A,X : CMP.b #$30 : BEQ .busy
    CMP.b #$31 : BEQ .busy
    DEX : BPL -
  .held
  LDA.b #$02 : RTS
  .busy
  LDA.b #$01 : RTS
  .release
  LDA.b #$00 : RTS
}

; M8 near helper: keep BottleIndex ($7EF34F, 1..4) synced to the active bottle
; button whenever Action == #$0B ($06->1, $0C->2, $12->3, $18->4). Keeps A/X/Y.
ItemBindings_SyncBottle:
{
  CMP.b #$0B : BNE .done
  PHA
  LDA.l ItemBindingLogical
  CMP.b #$06 : BNE + : LDA.b #$01 : BRA .store
+ CMP.b #$0C : BNE + : LDA.b #$02 : BRA .store
+ CMP.b #$12 : BNE + : LDA.b #$03 : BRA .store
+ CMP.b #$18 : BNE .skip : LDA.b #$04
.store
  STA.l BottleIndex
.skip
  PLA
.done
  RTS
}

; C=1 when the prototype may route: a form whose Y uses regular items
; (MaskBinding_Tick .regular): base Link, Minish (5), GBC (6), Moosh (7),
; plus mounted Horse (9) only when X is bound to Bow (with bow/arrows/no follower).
; M8 near helper; A clobbered.
ItemBindings_Admitted:
{
  LDA.l $7E0000+!CurrentMask : BEQ .form_ok
  CMP.b #$05 : BCC .no
  CMP.b #$08 : BCC .form_ok
if !ENABLE_HORSE_FORM == 1
  CMP.b #$09 : BNE .no
  LDA.l $7EF3CC : BNE .no
  LDA.l $7EF340 : BEQ .no
  LDA.l ItemBindingSavedVersion : CMP.b #$01 : BNE .no
  LDA.l ItemBindingSavedX : CMP.b #$01 : BNE .no
  LDA.l $7EF377 : BNE .form_ok
  LDA.l ItemBindingButton : BEQ .no
  BRA .form_ok
endif
  BRA .no
  .form_ok
  SEC : RTS
  .no
  CLC : RTS
}

; Load (LoadCheckpointOrWorld, after AdapterReset): put the saved Y item back
; in $0202 before SearchForEquippedItem, which keeps an owned nonzero $0202.
; Without it the search picks the first owned item, often X's. Saved Y must
; be a grid item the file owns (masks and Garo are R bindings, not Y).
; Native, D=0, any widths; full A, X/Y and P preserved.
ItemBindings_RestoreY:
{
  PHP : REP #$30 : PHA : PHX
  SEP #$30
  LDA.l ItemBindingSavedVersion : CMP.b #$01 : BNE .done
  LDA.l ItemBindingSavedY : BEQ .done
  CMP.b #Menu_ItemIndex_End-Menu_ItemIndex : BCS .done
  CMP.b #$1E : BEQ .done
  CMP.b #$13 : BCC .grid
  CMP.b #$18 : BCC .done                ; Deku..Stone: R binding
  .grid
  TAX
  LDA.l Menu_AddressLong-1, X : PHX : TAX
  LDA.l $7EF300, X : PLX
  CPX.b #$1B : BCC .ordinary
  CMP.b #$01 : BNE .done                ; logical cells: exactly 1 owns
  .ordinary
  CMP.b #$00 : BEQ .done
  TXA : STA.l $7E0202
  .done
  REP #$30 : PLX : PLA : PLP
  RTL
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
; Returns X's new-press bit only while the X latch owns the running action
; ($0303 == latched action), so a stale latch cannot redirect other Y readers.
; Y's bit otherwise. Z/A contract of the following BEQ/TSB $3A is preserved.
ItemBindings_UsePress:
{
  LDA.l ItemBindingButton : CMP.b #$02 : BNE .y
  LDA.w $0303 : CMP.l ItemBindingAction : BNE .y
  LDA.b $F6 : AND.b #$40 : RTL
  .y
  LDA.b $F4 : AND.b #$40 : RTL
}

; R+Y/R+X form change: drop the X press only when the prototype owns X,
; so an unowned X keeps the vanilla field-map open. M8; A clobbered.
ItemBindings_ConsumeX:
{
  PHX : PHY
  JSR ItemBindings_OwnsX
  PLY : PLX
  BCC .keep
  LDA.b #$40 : TRB.b $F6
  .keep
  RTL
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

; Replaces JSL MaskBinding_IsOcarina at $07A313 (LinkItem_ShovelAndFlute), M8.
; Z set means Ocarina: active Wolf ($02B2 == 3) always digs; otherwise read
; ItemBindings_EffectiveItem so X-bound Ocarina plays even while Y holds
; another item. X/Y preserved.
ItemBindings_IsOcarina:
{
  LDA.w !CurrentMask : CMP.b #$03 : BNE .item
  LDA.b #$01 : RTL
  .item
  JSL ItemBindings_EffectiveItem
  CMP.b #$0D : RTL
}

; Replaces BIT $F4 : BVC $08DCCD at $08DCBE (Ancilla31_CaneOfByrna), M8/X8.
; Pressing the button that started Byrna (X when ItemBindingButton == 2, Y
; otherwise) toggles the barrier off. Preserves X/Y.
ItemBindings_ByrnaCancel:
{
  LDA.l ItemBindingButton : CMP.b #$02 : BNE .y
  LDA.b $F6 : BIT.b #$40 : BNE .cancel
  JML $08DCCD
  .y
  BIT.b $F4 : BVS .cancel
  JML $08DCCD
  .cancel
  JML $08DCC2
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
if !DISABLE_MASKS == 0
org $07A313 ; @hook module=Items name=ItemBindings_IsOcarina kind=jsl target=ItemBindings_IsOcarina expected_m=8
  JSL ItemBindings_IsOcarina
endif
assert read4($08DCBE) == $0B50F424, "Byrna cancel button check moved"
org $08DCBE ; @hook module=Items name=ItemBindings_ByrnaCancel kind=jml target=ItemBindings_ByrnaCancel expected_m=8 expected_x=8 protected_size=4
  JML ItemBindings_ByrnaCancel
pullpc
