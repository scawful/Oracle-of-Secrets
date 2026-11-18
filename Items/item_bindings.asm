; Dual-item binding core.
; Integrator must provide seven granted long-address symbols:
; ItemBindingSavedVersion, ItemBindingSavedY, ItemBindingSavedX (saved bytes);
; ItemBindingCursor, ItemBindingLogical, ItemBindingAction, ItemBindingButton
; (volatile bytes). No fallback addresses, ORG, hooks, or feature activation.
;
; Long-entry ABI: native mode, D=0, any M/X and DBR; X/Y, DBR, D and widths
; preserved. A low byte is output/scratch; A high byte is preserved. C is
; output only where documented; other P flags restored. Binary arithmetic.
; IDs are menu grid indices; ItemBindings_Owner lists the latchable set.
; Button 0=idle, 1=Y, 2=X. Caller owns gameplay eligibility/completion.
; No physical input, $0202, $0303/$0304, HUD, mask, sword or map writes.

; C=owned and latchable, A unchanged. M8 near helper; any X width, X/Y/P
; kept except C. Latchable items start on one new press. Handlers that pick
; a variant by item ID (bomb/Bombchu, rod/Portal, chain/Goldstar/Switch Hook)
; read ItemBindings_EffectiveItem, so X sees the X item.
; Bottles, Mirror, Ocarina, Book, Fishing Rod, Byrna (held button), masks and
; Garo stay Y-only: they own a menu, song, fishing or held state.
ItemBindings_Validate:
{
  PHX : PHY : PHP : SEP #$30            ; SEP #$10 clears X/Y high bytes
  PHA
  CMP.b #ItemBindings_Owner_End-ItemBindings_Owner : BCS ItemBindings_CheckFail
  TAX
  LDA.l ItemBindings_ActionTable, X : BEQ ItemBindings_CheckFail
  BRA ItemBindings_CheckOwner
}

; C=owned (any grid/Y item, including Y-only items), A unchanged.
ItemBindings_ValidateY:
{
  PHX : PHY : PHP : SEP #$30
  PHA
  CMP.b #ItemBindings_Owner_End-ItemBindings_Owner : BCS ItemBindings_CheckFail
  TAX
ItemBindings_CheckOwner:
  LDA.l ItemBindings_Max, X : PHA        ; ownership upper bound, 0 = none
  LDA.l ItemBindings_Owner, X : BEQ ItemBindings_CheckDrop
  TAX
  LDA.l $7EF300, X : BEQ ItemBindings_CheckDrop
  CMP 1,S : BCC ItemBindings_CheckKeep
  LDA 1,S : BNE ItemBindings_CheckDrop
ItemBindings_CheckKeep:
  PLA : PLA : PLP : PLY : PLX : SEC : RTS
ItemBindings_CheckDrop:
  PLA
ItemBindings_CheckFail:
  PLA : PLP : PLY : PLX : CLC : RTS
}

; Logical-to-action mapping (Menu_ItemIndex values). Unsupported -> 0.
; M8 near helper; X/Y and P kept.
ItemBindings_MapAction:
{
  PHX : PHY : PHP : SEP #$30
  CMP.b #ItemBindings_Owner_End-ItemBindings_Owner : BCS .none
  TAX
  LDA.l ItemBindings_ActionTable, X
  PLP : PLY : PLX : RTS
.none
  LDA.b #$00
  PLP : PLY : PLX : RTS
}

; Long wrapper for HUD/menu callers: A low = ID, C = owned and latchable.
; Any widths; A, X/Y and P kept except C.
ItemBindings_IsLatchable:
{
  PHP : SEP #$20
  JSR ItemBindings_Validate : BCC .no
  PLP : SEC : RTL
.no
  PLP : CLC : RTL
}

; Indexed by logical ID (= menu grid index). Owner: offset into $7EF300.
; Logical cells own exactly 1 (Max $02); entries follow Menu_ItemIndex,
; including its cell flags. ActionTable == $00 marks Y-only items.
ItemBindings_Owner:
  db $00
  db $40, $41, $42, $43, $44, $5C       ; Bow Boomerang Hookshot Bombs Powder Bottle1
  db $4B, $4A, $45, $46, $53, $5D       ; Hammer Lamp FireRod IceRod Mirror Bottle2
  db $4C, $4E, $50, $51, $4D, $5E       ; Ocarina Book Somaria FishingRod Feather Bottle3
  db $49, $47, $58, $48, $52, $5F       ; Deku Zora Wolf Bunny Stone Bottle4
  db PortalRodOwned&$FF                 ; $19 Portal Rod
if !ENABLE_GOLDSTAR_CELL == 1
  db GoldstarOwned&$FF, ByrnaOwned&$FF  ; $1A Goldstar, $1B Byrna (Y only)
  db BombchuOwned&$FF, SwitchHookOwned&$FF ; $1C Bombchu, $1D Switch Hook
  db GaroMaskOwned&$FF                  ; $1E Garo Mask (Y only)
endif
ItemBindings_Owner_End:
ItemBindings_Max:
  db $00
  db $05, $03, $00, $00, $03, $00
  db $00, $00, $00, $00, $00, $00
  db $00, $00, $00, $00, $00, $00
  db $00, $00, $00, $00, $00, $00
  db $02
if !ENABLE_GOLDSTAR_CELL == 1
  db $02, $02, $02, $02, $02
endif
ItemBindings_ActionTable:
  db $00
  db $03, $02, $0E, $01, $0A, $00
  db $04, $09, $05, $06, $00, $00
  db $00, $00, $12, $00, $07, $00
  db $00, $00, $00, $00, $00, $00
  db $0D                                ; Portal: rod routine
if !ENABLE_GOLDSTAR_CELL == 1
  db $0E, $00, $01, $0E, $00            ; Goldstar chain, -, Bombchu bomb, Switch Hook chain, -
endif

; Item the running action belongs to, for handlers that pick a variant by
; item ID. X latch owning $0303: the X item. Otherwise $0202 (Y, unchanged).
; Called by %SelectedItem() (Items/all_items.asm). M8, any DBR/X width;
; A, N/Z and C out; X/Y kept.
ItemBindings_EffectiveItem:
{
  LDA.l ItemBindingButton : CMP.b #$02 : BNE .y
  LDA.l $7E0303 : CMP.l ItemBindingAction : BNE .y
  LDA.l ItemBindingLogical : RTL
.y
  LDA.l $7E0202 : RTL
}

; Load/new-file migration, only after inventory and saved bytes are loaded.
; Unknown version: retain any owned Y selection ($01-$1E), otherwise choose
; Bow then Boomerang; X starts empty. Recognized version revalidates ownership.
; Version is committed last. No grant, refill, or in-flight action survives.
ItemBindings_Load:
{
  PHP : SEP #$20
  LDA.l ItemBindingSavedVersion : CMP.b #$01 : BEQ .current
  LDA.b #$00 : STA.l ItemBindingSavedX
  LDA.l $7E0202 : BRA .validate_y
.current
  LDA.l ItemBindingSavedX : JSR ItemBindings_Validate : BCS .valid_x
  LDA.b #$00 : STA.l ItemBindingSavedX
.valid_x
  LDA.l ItemBindingSavedY
.validate_y
  JSR ItemBindings_ValidateY : BCS .store_y
  LDA.b #$01 : JSR ItemBindings_ValidateY : BCS .store_y
  LDA.b #$02 : JSR ItemBindings_ValidateY : BCS .store_y
  LDA.b #$00
.store_y
  STA.l ItemBindingSavedY : STA.l ItemBindingCursor
  LDA.b #$00
  STA.l ItemBindingLogical : STA.l ItemBindingAction : STA.l ItemBindingButton
  LDA.b #$01 : STA.l ItemBindingSavedVersion
  PLP : RTL
}

; A low = supported owned logical ID. C=accepted. Browsing never equips.
ItemBindings_SetCursor:
{
  PHP : SEP #$20
  JSR ItemBindings_Validate : BCC .no
  STA.l ItemBindingCursor
  PLP : SEC : RTL
.no
  PLP : CLC : RTL
}

; Assign current cursor to named button. C=accepted. Neither mutates an active
; action or other binding. Duplicate assignments intentionally allowed.
ItemBindings_AssignY:
{
  PHP : SEP #$20
  LDA.l ItemBindingCursor : JSR ItemBindings_Validate : BCC .no
  STA.l ItemBindingSavedY
  PLP : SEC : RTL
.no
  PLP : CLC : RTL
}
ItemBindings_AssignX:
{
  PHP : SEP #$20
  LDA.l ItemBindingCursor : JSR ItemBindings_Validate : BCC .no
  STA.l ItemBindingSavedX
  PLP : SEC : RTL
.no
  PLP : CLC : RTL
}

; A low must be exactly 1: current dispatcher grants starting a new action.
; It must already have applied form/R/cutscene/damage/doorway/sword/state gates.
; C=new action latched; false leaves all state untouched, including busy latch.
; Y wins simultaneous new presses; an invalid Y press cannot start X instead.
ItemBindings_TryBegin:
{
  PHP : SEP #$20
  CMP.b #$01 : BNE .no
  LDA.l ItemBindingButton : BNE .no
  LDA.b $F4 : AND.b #$40 : BNE .y
  LDA.b $F6 : AND.b #$40 : BEQ .no
  LDA.l ItemBindingSavedX : JSR ItemBindings_Validate : BCC .no
  STA.l ItemBindingLogical
  JSR ItemBindings_MapAction : STA.l ItemBindingAction
  LDA.b #$02 : BRA .commit
.y
  LDA.l ItemBindingSavedY : JSR ItemBindings_Validate : BCC .no
  STA.l ItemBindingLogical
  JSR ItemBindings_MapAction : STA.l ItemBindingAction
  LDA.b #$01
.commit
  STA.l ItemBindingButton
  PLP : SEC : RTL
.no
  PLP : CLC : RTL
}

; Explicit dispatcher completion/cancel/reset, NEVER simply button release.
; A projectile may outlive Link's action. Caller must use handler completion,
; not all-ancilla occupancy. Saved assignments and cursor remain unchanged.
ItemBindings_EndAction:
{
  PHP : SEP #$20
  LDA.b #$00
  STA.l ItemBindingButton : STA.l ItemBindingLogical : STA.l ItemBindingAction
  PLP : RTL
}

; Logical identity for runtime variants; menu/HUD use saved bindings instead.
ItemBindings_GetLogical:
{
  PHP : SEP #$20
  LDA.l ItemBindingButton : BEQ .idle
  LDA.l ItemBindingLogical : BRA .done
.idle
  LDA.l ItemBindingSavedY
.done
  PLP : RTL
}

; Scoped input queries: A low is $40 or 0. No X-to-Y rewrite of physical
; controller bytes. Only item consumers may use these accessors.
ItemBindings_GetHeld:
{
  PHP : SEP #$20
  LDA.l ItemBindingButton : CMP.b #$01 : BEQ .y
  CMP.b #$02 : BNE .none
  LDA.b $F2 : BRA .mask
.y
  LDA.b $F0
.mask
  AND.b #$40 : BRA .done
.none
  LDA.b #$00
.done
  PLP : RTL
}
ItemBindings_GetNew:
{
  PHP : SEP #$20
  LDA.l ItemBindingButton : CMP.b #$01 : BEQ .y
  CMP.b #$02 : BNE .none
  LDA.b $F6 : BRA .mask
.y
  LDA.b $F4
.mask
  AND.b #$40 : BRA .done
.none
  LDA.b #$00
.done
  PLP : RTL
}
