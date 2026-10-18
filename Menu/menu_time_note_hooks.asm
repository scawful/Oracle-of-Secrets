; Restore a prior OBJ lease before native DMA, then draw the note after all
; native uploads. The original updates and joypad reader still run once.
pushpc
org $00813E
assert read3($00813E) == $89E020, "NMI graphics update call moved"
assert read3($008141) == $83D120, "NMI joypad call moved"
; @hook Menu_TimeNoteNmi kind=jsr target=MenuTimeNote_NmiTrampoline
; @assumption Native NMI bank $00, DBR=$00, DP=$0000, M/X=8.
  JSR MenuTimeNote_NmiTrampoline : NOP #3
assert pc() == $008144

org $0089C2
assert read4($0089C2) == $FFFFFFFF, "Time note NMI trampoline space occupied"
assert read3($0089C6) == $FFFFFF, "Time note NMI trampoline tail occupied"
assert read4($0089C9) == $FFFFFFFF, "Time note NMI trampoline extension occupied"
assert read3($0089CD) == $FFFFFF, "Time note NMI trampoline last bytes occupied"
MenuTimeNote_NmiTrampoline:
  JSL MenuTimeNote_NmiRestore
  JSR $89E0 ; displaced JSR NMI_DoUpdates
  JSL MenuTimeNote_NmiFinish
  JMP $83D1 ; original joypad reader returns through NOPs to $008144
assert pc() == $0089D0
pullpc

MenuTimeNote_NmiFinish:
{
  JSL MenuTimeNote_Nmi
  JSL MenuTimeNote_PatchVramNmiLong
  RTL
}
