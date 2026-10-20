; D3 boss admission uses the existing room-$39 lightning-gate actor. Its
; native zap runs first; a scoped position guard also stops invulnerable Link.
; Do not change the generic damage/Cape paths or other barriers.
; The normal-profile prep patch remains untouched; this file emits nothing
; while the prison sequence is disabled.
if !ENABLE_D3_PRISON_SEQUENCE == 1

; HasEscaped is a permanent story unlock, separate from the currently held
; blade required at the boss entrance. A smith-held $FF is not a valid sword.
; DP=0; preserve A/X/Y/DB and P except C. C=1 admits Link to the boss.
; No saved-backup validation: that history must not undo an earned escape.
D3Prison_BossGateIsOpen:
{
  PHP
  SEP #$20
  PHA
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_HasEscaped
  BEQ .closed
  LDA.l Sword : CMP.b #$02 : BCC .closed
  CMP.b #$05 : BCS .closed
  PLA : PLP : SEC : RTL
  .closed
  PLA : PLP : CLC : RTL
}

; BarrierBounce, M8/X8, DP=0, DB05, X=sprite slot. Open/unrelated gates
; tail-call Sprite_40_LightningGate; closed gates return here for the stop.
; It establishes DB1D and retains its own draw and contact/recoil behavior.
; The closed case additionally stops crossing after native zap processing.
D3Prison_BossGateDispatch:
{
  PHP
  PHA
  LDA.l $7E0E20, X : CMP.b #$40 : BNE .native
  LDA.l $7E001B : CMP.b #$01 : BNE .native
  LDA.l $7E040C : CMP.b #$10 : BNE .native
  LDA.l $7E00A1 : BNE .native
  LDA.l $7E00A0 : CMP.b #$39 : BNE .native

  ; The closed progression gate cannot be destroyed with a sword, hammer
  ; or calculated item damage. Native prep already ignores projectiles.
  ; Keep palette/sheet bits; $0F50 (draw props) is deliberately untouched.
  LDA.l $7E0E60, X : ORA.b #$40 : STA.l $7E0E60, X
  JSL D3Prison_BossGateIsOpen : BCS .open
  LDA.l $7E001A : LSR : AND.b #$03
  STA.l $7E0DC0, X
  PLA
  PLP
  JSL $1DF063
  JSL D3Prison_BossGateStopCrossing
  RTL
  .open
  LDA.b #$04
  STA.l $7E0DC0, X
  .native
  PLA
  PLP
  JML $1DF063
}

; Native recoil alone does not stop Cape crossing. Stop northward
; crossing using actual full coordinates, without altering cloak, magic,
; damage, recoil or inventory. Southward retreat remains possible.
; DP=0, X=actor slot. Preserve A/X/Y/DB/P and DP00..05. Only Link Y may change.
; $30 is the signed actual Y movement for this frame; $27 is recoil, not speed.
D3Prison_BossGateStopCrossing:
{
  PHP
  REP #$20
  PHA
  SEP #$20
  LDA.l $7E0010 : CMP.b #$07 : BNE .done
  LDA.l $7E0011 : BNE .done
  LDA.l $7E001B : CMP.b #$01 : BNE .done
  LDA.l $7E040C : CMP.b #$10 : BNE .done
  LDA.l $7E00A1 : BNE .done
  LDA.l $7E00A0 : CMP.b #$39 : BNE .done
  LDA.l $7E0E20, X : CMP.b #$40 : BNE .done
  LDA.l $7E0DD0, X : CMP.b #$09 : BNE .done
  LDA.l $7E0FC1 : BNE .done
  LDA.l $7E00EE : CMP.l $7E0F20, X : BNE .done
  LDA.l $7E0CAA, X : BMI .active
  LDA.l $7E0F00, X : BNE .done
  .active
  JSL D3Prison_BossGateIsOpen : BCS .done
  LDA.l $7E0030 : BEQ .check_position
  BMI .check_position
  .done
  REP #$20
  PLA
  PLP
  RTL

  .check_position
  REP #$20
  LDA.b $00 : PHA
  LDA.b $02 : PHA
  LDA.b $04 : PHA
  SEP #$20
  LDA.l $7E0D30, X : XBA : LDA.l $7E0D10, X
  REP #$20
  STA.b $00
  SEP #$20
  LDA.l $7E0D20, X : XBA : LDA.l $7E0D00, X
  REP #$20
  CLC : ADC.w #$0010 : STA.b $02 ; first safe row south of native contact
  LDA.l $7E0030 : AND.w #$00FF
  BEQ .store_delta
  ORA.w #$FF00 ; remaining nonzero movement is negative
  .store_delta
  STA.b $04
  LDA.l $7E0022
  SEC : SBC.b $00
  CLC : ADC.w #$0020
  CMP.w #$0040 : BCS .restore_scratch
  LDA.l $7E0020 : CMP.b $02 : BCS .restore_scratch
  SEC : SBC.b $02
  CLC : ADC.w #$0018
  CMP.w #$0018 : BCC .stop ; within the native24px contact band
  ; A fast northward step may skip the whole band. Only catch a crossing
  ; from the south, never pull a player already entirely north back through.
  LDA.l $7E0020 : SEC : SBC.b $04
  CMP.b $02 : BCC .restore_scratch
  .stop
  LDA.b $02 : STA.l $7E0020
  .restore_scratch
  PLA : STA.b $04
  PLA : STA.b $02
  PLA : STA.b $00
  BRL .done
}

pushpc
; @source usdasm/bank_05.asm:BarrierBounce, $05D543-$05D546
assert read4($05D543) == $1DF06322, "Unexpected lightning-gate dispatch call"
org $05D543 ; @hook module=Dungeons name=D3Prison_BossGateDispatch kind=jsl target=D3Prison_BossGateDispatch expected_m=8 expected_x=8
  JSL D3Prison_BossGateDispatch
assert pc() == $05D547
pullpc

endif
