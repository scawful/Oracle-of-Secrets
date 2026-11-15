; Room78 on-foot encounter: three retained Lanmolas and direct BigKey32.
; Source: actual room78 placements/vanilla E5 key receipt/save-room flags.
; M/X8, D0, mirroredWRAM DBR. No newRAM/SRAM; customLanmola's otherwise
; unused SprMiscD($0E90) holds each full-word target's high byte.
; Helpers use three measured existing code tails; no bound is widened.
pushpc
org $06D032
assert read3($06D032) == $0CBABC, "E4/E5 LDY preimage differs"
assert read3($06D035) == $0403AD, "E4/E5 LDA preimage differs"
  JML Goron78_KeyAfterLanmolas ; @hook module=Sprites name=Goron78_KeyAfterLanmolas kind=jml target=Goron78_KeyAfterLanmolas protected_size=6 expected_m=8 expected_x=8
  NOP #2
assert pc() == $06D038
pullpc

; JML entry from native bank06 JSR dispatch. Every exit retains that
; return frame; restore P before replaying native LDY/LDA or returning.
Goron78_KeyAfterLanmolas:
{
  PHP
  JSL Goron78_IsRoom : BCC .vanilla
  LDA.w SprType,X : CMP.b #$E5 : BNE .vanilla
  JSL Lanmola_EncounterIsClear : BCS .vanilla
    PLP
    JML $06D040
  .vanilla
  PLP
  LDY.w $0CBA,X
  LDA.w $0403
  JML $06D038
}
assert pc() <= $320000, "Room78 key helper exceeds sprite bank31"

macro Goron78_EmitCoreHelpers()
Goron78_IsRoom:
{
  LDA.b $1B : BEQ .no
  LDA.b $A1 : BNE .no
  LDA.b $A0 : CMP.b #$78 : BEQ .yes
  .no
  CLC : RTL
  .yes
  SEC : RTL
}
Lanmola_EncounterIsClear:
{
  PHX
  LDX.b #$01
  JSL Goron78_IsRoom : BCC .scan
    LDX.b #$02
  .scan
  LDA.w SprType,X : CMP.b #$54 : BNE .next
    LDA.w SprState,X : BNE .alive
  .next
  DEX : BPL .scan
  PLX : SEC : RTL
  .alive
  PLX : CLC : RTL
}

Goron78_RecordLanmolaClear:
{
  PHP
  JSL Goron78_IsRoom : BCC .done
    LDA.w $0403 : ORA.b #$80 : STA.w $0403
  .done
  PLP : RTL
}
; GetRandomInt consumes incomingC. Preserve it through table indexing,
; then replay the low-byte load's A/N/Z contract before the Y RNG call.
Goron78_SelectLanmolaX:
{
  PHP
  JSL Goron78_IsRoom : BCC .vanilla
  PHX
  TXA : ASL A : TAX
  LDA.l Goron78_LanmolaXTargets,X : STA.w SprMiscA,Y
  INX
  LDA.l Goron78_LanmolaXTargets,X : STA.w SprMiscD,Y
  PLX : PLP
  LDA.w SprMiscA,Y
  RTL
  .vanilla
  PLP
  LDA.l $7EEAA8,X : STA.w SprMiscA,Y
  RTL
}

Goron78_ResetLanmolaX:
{
  PHP
  JSL Goron78_IsRoom : BCC .vanilla
  PHX
  TXA : ASL A : TAX
  LDA.l Goron78_LanmolaXTargets,X : STA.w SprX,Y
  INX
  LDA.l Goron78_LanmolaXTargets,X : STA.w SprXH,Y
  PLX : PLP
  LDA.w SprX,Y
  RTL
  .vanilla
  PLP
  LDA.l $7EEAA8,X : STA.w SprX,Y
  RTL
}

Goron78_LanmolaXTargets:
  dw $10A0,$10B8,$10D0,$10E8,$1100,$1118,$1130,$1140
Goron78_CoreHelpersEnd:
endmacro

macro Goron78_EmitTargetHighHelper()
Goron78_LoadLanmolaTargetXHigh:
{
  PHP
  JSL Goron78_IsRoom : BCC .vanilla
  PLP
  LDA.w SprMiscD,X
  RTL
  .vanilla
  PLP
  LDA.w SprXH,X
  RTL
}
Goron78_TargetHighHelperEnd:
endmacro
