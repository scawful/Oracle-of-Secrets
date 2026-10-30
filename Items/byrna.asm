; Restored vanilla Cane of Byrna, in the bank-$07 item extension.
; The split item grid assigns logical $1B, while $10/$19 remain the rods.
; Function $0D still enters the existing dispatcher at $07AF3E.
if !ENABLE_GOLDSTAR_CELL == 1
LinkItem_RestoredByrna:
{
  LDA.l ByrnaOwned : CMP.b #$01 : BNE .return
  JSR $AFB5                         ; SearchForByrnaSpark (unchanged vanilla)
  BCS .return
  BIT.b $3A : BVS .pressed_y
  LDA.b $6C : BNE .return
  JSR $B073 : BCC .return            ; CheckYButtonPress
  LDX.b #$08
  JSR $B0AB : BCC .lack_magic        ; LinkCheckMagicCost
  LDY.b #$00
  LDA.b #$30
  JSL AncillaAdd_CaneOfByrnaInitSpark
  STZ.b $79
  LDA.w $AF3B : STA.b $3D            ; original ByrnaAnimationTimers
  STZ.w $030D
  STZ.w $0300
  LDA.b #$08 : STA.w $037A
  LDA.b #$01 : TSB.b $50
  STZ.b $2E
  .pressed_y
  JSR $AE65                         ; HaltLinkWhenUsingItems
  LDA.b $67 : AND.b #$F0 : STA.b $67
  DEC.b $3D : BPL .return
  LDX.w $0300 : INX : STX.w $0300
  LDA.w $AF3B,X : STA.b $3D
  CPX.b #$01 : BNE .skip_sfx
  PHX
  LDA.b #$2A : JSR $802F             ; PlaySFX_Set3
  PLX
  .skip_sfx
  CPX.b #$03 : BNE .return
  .lack_magic
  STZ.w $030D
  STZ.w $0300
  LDA.b $3A : AND.b #$80 : STA.b $3A
  STZ.w $037A
  LDA.b $50 : AND.b #$FE : STA.b $50
  .return
  RTS
}
; Keep the original effective-action check: R-bound masks can override Y
; without changing the saved logical selection. Out: Z set only for Byrna.
Byrna_IsSelected:
{
  LDA.w $0303 : CMP.b #$0D : BNE .return
  LDA.w $0202 : CMP.b #$1B
  .return
  RTL
}
assert pc() < $07FF00, "Restored Byrna exceeds bank-$07 item extension"

pushpc
; All three tools share function $0D, so the vanilla action-ID check would
; retain the shield after equipping either rod. Keep vanilla termination,
; magic drain, damage and pause handling; only identify the selected tool.
org $08DC7C ; @hook module=Items name=ByrnaSelectedItem kind=jsl target=Byrna_IsSelected
  JSL Byrna_IsSelected : NOP
assert pc() == $08DC81
pullpc
endif
