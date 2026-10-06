; Independent mask binding. Included in bank $3A under ENABLE_MASK_R_BINDING.
; $0202 remains the normal item. $0303 is the effective action for vanilla
; Link_HandleYItem, and $0304 retains vanilla in-flight action bookkeeping.
; All entry points use 8-bit A/X/Y unless documented otherwise.

; Return a validated binding (1-5), or 0. Keep X/Y. No unowned activation.
MaskBinding_Get:
{
  PHX
  LDA.l BoundMask : BEQ .none
  CMP.b #$06 : BCS .none
  DEC : TAX
  LDA.l .ownership, X : TAX
  LDA.l $7EF300, X : BEQ .none
  LDA.l BoundMask
  PLX : CMP.b #$00 : RTL
  .none
  LDA.b #$00 : PLX : CMP.b #$00 : RTL
  .ownership
  db $49, $47, $58, $48, $52
}

; Page-3 selection/marker value in the legacy mask-item ID range.
MaskBinding_SelectedItem:
{
  JSL MaskBinding_Get : BEQ .done
  CLC : ADC.b #$12
  .done
  RTL
}

; Old saves can have a mask in $0202. Preserve it as the R binding and
; choose the first owned normal item (or none). Never index beyond a table.
MaskBinding_MigrateSelection:
{
  PHX : PHY
  LDA.w $0202 : CMP.b #$13 : BCC .done
  CMP.b #Menu_ItemIndex_End-Menu_ItemIndex : BCS .choose
  CMP.b #$18 : BCS .done
  SEC : SBC.b #$12 : STA.l BoundMask
  .choose
  LDX.b #$01
  .scan
  CPX.b #$13 : BCC .check
  CPX.b #$18 : BCC .next
  .check
  TXA : DEC : TAX
  LDA.l Menu_AddressLong, X : TAY
  INX
  PHX : TYX
  LDA.l $7EF300, X
  PLX : CMP.b #$00 : BNE .found
  .next
  INX : CPX.b #Menu_ItemIndex_End-Menu_ItemIndex : BCC .scan
  LDX.b #$00
  .found
  STX.w $0202
  .done
  PLY : PLX : RTL
}

; Equal-sized replacement for the wolf/flute dispatch test in bank $07.
; Z set means Ocarina. An active Wolf always digs, even with Ocarina selected.
MaskBinding_IsOcarina:
{
  LDA.w !CurrentMask : CMP.b #$03 : BNE .item
  LDA.b #$01 : RTL
  .item
  LDA.w $0202 : CMP.b #$0D : RTL
}

MaskBinding_Tick:
{
  PHX : PHY
  JSL MaskBinding_MigrateSelection
  ; Consume R centrally so no item handler sees the same transform press.
  ; Hookshot/Goldstar slot separation is a separate integration prerequisite.
  ; Ignore activation during a doorway, cutscene or in-flight item.
  LDA.b $F6 : AND.b #$10 : BNE +
  JMP .route
  +
  LDA.b #$10 : TRB.b $F6
  LDA.b $6C : BEQ +
  JMP .route
  +
  LDA.w $0FFC : BEQ +
  JMP .route
  +
  LDA.b $5D : BEQ +
  JMP .route
  +                ; no unmasking while swimming/hovering
  LDA.b $3C : BEQ +
  JMP .route
  +                ; sword action
  LDA.b $3A : AND.b #$40 : BEQ +
  JMP .route
  +
  LDA.w $0301 : ORA.w $037A : BEQ +
  JMP .route
  +
  LDA.w !ZoraDiving : BEQ +
  JMP .route
  +
  LDA.b $46 : BEQ +
  JMP .route
  +
  LDA.w !CurrentMask : BEQ .as_link
  CMP.b #$06 : BEQ .as_link
  CMP.b #$05 : BCS .blocked            ; Minish / Moosh
  ; An active form comes off first, regardless of the newly selected binding.
  JSL PlayerTransform
  JSL ResetToLinkGraphics
  BRA .consume_y

  .as_link
  LDA.b $55 : BEQ .put_on
  JSL StoneMask_TakeOff
  BRA .consume_y

  .put_on
  JSL MaskBinding_Get : BEQ .route
  CMP.b #$05 : BEQ .stone
  PHA
  JSL PlayerTransform
  PLA : STA.w !CurrentMask : TAX
  LDA.l .graphics-1, X : STA.b $BC
  JSL Palette_ArmorAndGloves
  BRA .consume_y

  .stone
  ; An inactive cape timer is not serviced while another item is routed.
  ; Clear that dormant delay on explicit activation, then let vanilla Cape
  ; validate magic, spawn effects and start its active timers.
  STZ.w $02E2
  LDA.b #$40 : TSB.b $F4
  LDA.b #$13 : BRA .set_action

  .blocked
  ; Preserve M3 recovery: a pre-existing cape can always be removed,
  ; even if another transition put Link into Minish or Moosh.
  LDA.b $55 : BEQ +
  JSL StoneMask_TakeOff
  BRA .consume_y
  +
  JSL MaskBinding_Get : BEQ .route
  %ErrorBeep()
  .consume_y
  ; R+Y changes form once; it must not also fire the newly exposed item.
  LDA.b #$40 : TRB.b $F4

  .route
  LDA.w !CurrentMask : BEQ .base_form
  CMP.b #$06 : BEQ .base_form
  CMP.b #$05 : BCS .regular            ; preserve automatic Minish / Moosh
  TAX
  LDA.l .actions-1, X : BRA .set_action
  .base_form
  LDA.b $55 : BEQ .regular
  LDA.b #$13 : BRA .set_action          ; Stone remains an effective Cape
  .regular
  LDX.w $0202 : CPX.b #Menu_ItemIndex_End-Menu_ItemIndex : BCS .no_item
  LDA.l Menu_ItemIndex, X : BRA .set_action
  .no_item
  LDA.b #$00
  .set_action
  CMP.w $0303 : BEQ .done
  STA.w $0303
  JSL HUD_RefreshLong
  .done
  PLY : PLX
  ; Restore the displaced LDA $3C / BEQ contract at $079B0E.
  LDA.b $3C : BNE .sword
  LDA.b #$09
  .sword
  RTL

  .actions
  db $11, $0F, $08, $10
  .graphics
  db $35, $36, $38, $37
}
