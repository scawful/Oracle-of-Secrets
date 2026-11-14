; Dual binding core, first Bow/Boomerang slice. Not included in the game yet.
; Integrator must provide seven granted long-address symbols:
; ItemBindingSavedVersion, ItemBindingSavedY, ItemBindingSavedX (saved bytes);
; ItemBindingCursor, ItemBindingLogical, ItemBindingAction, ItemBindingButton
; (volatile bytes). No fallback addresses, ORG, hooks, or feature activation.
;
; Long-entry ABI: native mode, D=0, any M/X and DBR; X/Y, DBR, D and widths
; preserved. A low byte is output/scratch; A high byte is preserved. C is
; output only where documented; other P flags restored. Binary arithmetic.
; IDs 1=Bow, 2=Boomerang only. Other tools remain outside this first slice.
; Button 0=idle, 1=Y, 2=X. Caller owns gameplay eligibility/completion.
; No physical input, $0202, $0303/$0304, HUD, mask, sword or map writes.

; C=owned and supported, A unchanged. Private M8 near helper.
ItemBindings_Validate:
{
  PHA
  CMP.b #$01 : BEQ .bow
  CMP.b #$02 : BNE .no
  LDA.l $7EF341 : BEQ .no
  CMP.b #$03 : BCS .no
  PLA : SEC : RTS
.bow
  LDA.l $7EF340 : BEQ .no
  CMP.b #$05 : BCS .no
  PLA : SEC : RTS
.no
  PLA : CLC : RTS
}

; Pure logical-to-action mapping. Unsupported/empty -> 0. M8 near helper.
ItemBindings_MapAction:
{
  CMP.b #$01 : BEQ .bow
  CMP.b #$02 : BEQ .done
  LDA.b #$00 : RTS
.bow
  LDA.b #$03
.done
  RTS
}

; Load/new-file migration, only after inventory and saved bytes are loaded.
; Unknown version: retain supported owned vanilla selection, otherwise choose
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
  JSR ItemBindings_Validate : BCS .store_y
  LDA.b #$01 : JSR ItemBindings_Validate : BCS .store_y
  LDA.b #$02 : JSR ItemBindings_Validate : BCS .store_y
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
