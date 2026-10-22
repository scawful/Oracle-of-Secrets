; Room $27's filled reservoir uses a north intra-room stair to leave the water.
; The stair already restores the authored plane; finish its swim state as well.

pushpc
org $028F7C ; @hook module=Dungeons name=ZoraTemple_StairSwimExit kind=jsl target=ZoraTemple_StairSwimExit_Long expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JSL ZoraTemple_StairSwimExit_Long
  NOP
assert pc() == $028F81

; $2CFC00..$2CFC19 belongs to the floor-return helper. Keep the sequential
; dungeon/NPC stream in place and stop before SomariaSocketDoor at $2CFD00.
org $2CFC20
ZoraTemple_StairSwimExit_Long: ; @abi long_entry
{
  ; Replay the byte stores with the caller's original D and DB on every path.
  STZ.b $B0
  STZ.w $0418

  ; Save full A, including its hidden high byte at this M8/X8 hook.
  PHP
  REP #$30
  PHA : PHX : PHY
  PHB : PHD
  LDA.w #$0000 : TCD
  PHK : PLB
  SEP #$30

  ; Normalized D and DB=$2C address the intended low-WRAM state below.
  REP #$20
  LDA.b $A0 : CMP.w #$0027 : BNE .done
  SEP #$20
  LDA.b $1B : BEQ .done                    ; Indoors.
  LDA.b $67 : AND.b #$08 : BEQ .done       ; North stair travel.
  LDA.l $7EF411 : AND.b #$01 : BEQ .done   ; Reservoir filled.
  LDA.b $5D : CMP.b #$04 : BNE .done       ; Swimming Link.
  LDA.w $0345 : BEQ .done                  ; In deep water.
  LDA.b $EE : BNE .done                    ; Authored upper plane reached.
  LDA.w $0476 : BNE .done
  LDA.b $A4 : BNE .done                    ; Room $27's floor $00 only.

  STZ.w $0345
  STZ.b $5D
  JSL $07983A                             ; Link_ResetSwimmingState.

  .done
  REP #$30
  PLD : PLB
  PLY : PLX : PLA
  PLP
  RTL
}
ZoraTemple_StairSwimExit_End:
assert ZoraTemple_StairSwimExit_Long >= $2CFC1A
assert pc() <= $2CFD00
pullpc
