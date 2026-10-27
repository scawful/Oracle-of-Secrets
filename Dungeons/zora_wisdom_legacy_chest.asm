; Old files can have the former Flippers chest ($9A) open without Wisdom.
; Let that file recover Wisdom from its still-closed ordinary $7A chest.
; The normal $7A reward remains the heart piece selected in Core/patches.asm.

pushpc
assert read4($01EB66) == $DA00A28B && read1($01EB6A) == $AB, "OpenChestForItem DB setup moved"
assert read2($01EB72) == $30C2, "OpenItemChest M16/X16 setup moved"
assert read4($01EC09) == $01E970BF, "OpenItemChest item load moved"
assert read2($01EC0D) == $0C85, "OpenItemChest item store moved"
assert read2($01E9F5) == $807A, "Legacy Wisdom chest record moved"
assert read2($01EA1C) == $809A, "Former Flippers chest record moved"
assert read2($009900) == $0100, "First chest live flag moved"
org $01EC09 ; @hook module=Dungeons name=ZoraWisdom_LegacyChestItem kind=jsl target=ZoraWisdom_LegacyChestItem expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
  JSL ZoraWisdom_LegacyChestItem
assert pc() == $01EC0D
pullpc

; OpenItemChest: M16/X16, D=$0000, DB=$00; X=matched table offset,
; Y=twice the chest ordinal. $0402 is still the pre-open live room state.
; Preserve the displaced load's high A byte, NZ and all other caller state.
ZoraWisdom_LegacyChestItem:
{
  LDA.l $01E970, X                         ; Displaced item-word load.
  PHP : PHA
  CPX.w #$0087 : BNE .unchanged            ; Exact $01E9F5 table row.
  AND.w #$00FF : CMP.w #$0017 : BNE .unchanged
  LDA.b $A0 : CMP.w #$007A : BNE .unchanged
  LDA.l Flippers : AND.w #$00FF : BEQ .unchanged
  LDA.l Pendants : AND.w #!Pendant_Wisdom : BNE .unchanged
  ; $9A has one chest, ordinal 0. SaveRoomData shifts live $0100 right 4.
  LDA.l $7EF134 : AND.w #$0010 : BEQ .unchanged
  LDA.w $0402 : AND.w $9900, Y : BNE .unchanged

  PLA
  AND.w #$FF00 : ORA.w #$0038              ; Wisdom; keep the loaded high byte.
  BRA .done

  .unchanged
  PLA
  .done
  PLP
  RTL
}
ZoraWisdom_LegacyChestItem_End:
assert pc() <= $2CFD00
