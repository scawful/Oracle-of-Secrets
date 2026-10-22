; The dive hole in $35 descends to $44. Its warp pad returns to $35,
; but vanilla warp pads preserve $A4 instead of undoing the pit's decrement.
; Restore that one floor only for this authored return, during warp substep 4.

pushpc
org $0296C0 ; @hook module=Dungeons name=ZoraTemple_WarpReturnFloor kind=jsl target=ZoraTemple_WarpReturnFloor expected_m=16 expected_x=8 expected_exit_m=16 expected_exit_x=8
  JSL ZoraTemple_WarpReturnFloor
  NOP
assert pc() == $0296C5

; Fixed tail allocation avoids relocating the bank-$2C NPC stream.
; $2CFD00 holds RoomTag_SomariaSocketDoor; $2CFE00/$2CFF00 are reserved.
org $2CFC00
; Caller: M16/X8, D=$0000. No index, data-bank or plane changes.
; Replay LDA $A0 / CMP #$0017 after restoring P: the vanilla BNE needs Z.
ZoraTemple_WarpReturnFloor:
{
  PHP
  LDA.b $A0 : CMP.w #$0035 : BNE .vanilla
  LDA.b $A2 : CMP.w #$0044 : BNE .vanilla
    SEP #$20
    INC.b $A4
  .vanilla
  PLP
  LDA.b $A0
  CMP.w #$0017
  RTL
}
assert pc() <= $2CFD00
pullpc
