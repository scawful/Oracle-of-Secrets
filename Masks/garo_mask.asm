; =========================================================
; Garo Master prototype: timed contact parry, then Y counter.
; Player art by Herowho (garomaster.1.zspr); palette 1 retained.
; Gameplay entries use M/X=8 except the documented Link_Main frame hook.
; X/Y are preserved. State is volatile.
; =========================================================

pushpc
org $07800F
; @hook GaroMask_FrameTick kind=jsl target=GaroMask_FrameTick
; @source usdasm/bank_07.asm:Link_Main ($07800F-$078013)
; @assumption M=16, DBR=$07; inherited index width is preserved.
; Replaces SEP #$20 / STZ $0FC1, replayed by the helper.
  JSL GaroMask_FrameTick
  NOP
assert pc() == $078014
pullpc

; Link_Main reaches this once before state dispatch, including carrying,
; recoil, swimming and item states that never call Link_HandleYItem.
; Preserve full A/X/Y/DBR and precisely the flags after the displaced SEP.
GaroMask_FrameTick:
{
  %a8()
  STZ.w $0FC1
  PHP
  %m16()
  PHA : PHX : PHY : PHB
  %m8()
  ; DBR remains $07 so absolute WRAM accesses stay valid in bank $42 code.
  JSL GaroMask_CanAct : BCS .active
  JSL GaroMask_Clear
  BRA .restore
  .active
  LDA.w GaroGuardTimer : BEQ +
  DEC.w GaroGuardTimer
  +
  LDA.w GaroCounterTimer : BEQ +
  DEC.w GaroCounterTimer
  +
  LDA.w GaroCooldown : BEQ +
  DEC.w GaroCooldown
  +
  .restore
  PLB
  %m16()
  PLY : PLX : PLA
  PLP
  RTL
}

UpdateGaroPalette:
{
  PHP : REP #$30
  PHX
  LDX.w #$001E
  .loop
  LDA.l GaroMasterPalette, X : STA.l $7EC6E0, X
  DEX : DEX : BPL .loop
  PLX : SEP #$20
  INC.b $15
  PLP
  RTL
}

GaroMasterPalette:
  dw $0000
  incbin "gfx/garo_master_palette.bgr555"
assert pc()-GaroMasterPalette == $20

GaroMask_Clear:
{
  STZ.w GaroGuardTimer
  STZ.w GaroCounterTimer
  STZ.w GaroCooldown
  RTL
}

; Carry set only during normal controllable gameplay. A guard does not survive
; doorway movement, text, transitions, recoil, swimming, lifting, or a cutscene.
GaroMask_CanAct:
{
  LDA.w !CurrentMask : CMP.b #$08 : BNE .no
  LDA.l GaroMaskOwned : CMP.b #$01 : BNE .no
  LDA.b $10 : CMP.b #$07 : BEQ .module_ok
  CMP.b #$09 : BEQ .module_ok
  CMP.b #$0B : BNE .no
  .module_ok
  LDA.b $11 : ORA.b $6C : ORA.b $5D : BNE .no
  LDA.w $0FFC : ORA.w $02E4 : ORA.w $0301 : ORA.w $037A : BNE .no
  LDA.w $0308 : ORA.w $0376 : ORA.w $0377 : BNE .no
  LDA.b $46 : BNE .no
  SEC : RTL
  .no
  CLC : RTL
}

GaroMask_Tick:
{
  JSL GaroMask_CanAct : BCS .active
  JML GaroMask_Clear
  .active
  LDA.b $F4 : AND.b #$40 : BEQ .done
  ; LinkState_Default runs the Y-item tick before its sword-input handler.
  ; Leave a counter press for that later hook; the effective Y action is 0.
  LDA.w GaroCounterTimer : BNE .done
  ; Y never dispatches the selected normal item while this form is active.
  LDA.b #$40 : TRB.b $F4
  LDA.w GaroCooldown : BNE .done
  LDA.b $3C : BNE .done
  LDA.b $3A : AND.b #$C0 : BNE .done
  LDA.b #$0C : STA.w GaroGuardTimer
  LDA.b #$20 : STA.w GaroCooldown
  LDA.b #$05 : STA.w $012E ; guard cue; the same clink confirms contact
  .done
  RTL
}

; Called by the existing contact-damage/Armor Ring hook after damage is queued.
; This deliberately does not catch floor damage or grant persistent immunity.
; Contact recoil has already been set, so CanAct's recoil guard is not used.
GaroMask_ParryContact:
{
  PHP : PHA
  LDA.w !CurrentMask : CMP.b #$08 : BNE .done
  LDA.l GaroMaskOwned : CMP.b #$01 : BNE .done
  LDA.w GaroGuardTimer : BEQ .done
  LDA.w $0373 : BEQ .done
  LDA.b $11 : ORA.b $6C : ORA.b $5D : BNE .done
  LDA.w $0FFC : ORA.w $02E4 : BNE .done
  LDA.w $0308 : ORA.w $0376 : ORA.w $0377 : BNE .done
  STZ.w $0373
  STZ.b $46 : STZ.b $4D
  STZ.b $27 : STZ.b $28
  STZ.w GaroGuardTimer
  LDA.b #$20 : STA.w GaroCounterTimer
  LDA.b #$0C : STA.w $031F ; brief recovery from the blocked contact
  LDA.b #$05 : STA.w $012E
  .done
  PLA : PLP : RTL
}

; Runs at the existing sword-input hook AFTER the Y-item tick. A successful
; parry grants one Y-triggered normal sword slash; vanilla owns its animation,
; hitbox and damage. No equipment or synthetic sword state is installed.
GaroMask_CounterInput:
{
  JSL GaroMask_CanAct : BCC .done
  LDA.w GaroCounterTimer : BEQ .done
  LDA.b $F4 : AND.b #$40 : BEQ .done
  LDA.b $3C : BNE .done
  LDA.b $3A : AND.b #$C0 : BNE .done
  LDA.l $7EF359 : BEQ .done
  CMP.b #$05 : BCS .done ; includes the smith-held $FF sentinel
  LDA.b #$40 : TRB.b $F4
  LDA.b #$80 : TSB.b $F4
  STZ.w GaroCounterTimer
  LDA.b #$10 : STA.w GaroCooldown
  .done
  RTL
}
