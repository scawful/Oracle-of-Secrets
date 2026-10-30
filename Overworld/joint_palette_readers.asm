; Joint palette directory consumer. Included late, outside namespace Oracle,
; after Core/Generated/joint_palette/directory.asm. The directory labels must
; come from that generated include: a missing include fails as undefined labels.
; Each native reader keeps its 7 bytes and REP #$21 entry; X is the 8-bit
; palette id*2 and A receives the bank-$1B record address. Callers set $02.
assert !JOINT_PALETTE_DIRECTORY_ENABLED == 1
assert !DISABLE_OVERWORLD == 0, "Joint palettes require the ZS main palette reader"
assert JointPalette_MainDirectory == $1BB6A8 && JointPalette_MainDirectoryEnd == $1BB6B6
assert JointPalette_AuxDirectory == $1BB6B6 && JointPalette_AuxDirectoryEnd == $1BB6E8
assert JointPalette_ZSMainReader_End-JointPalette_ZSMainReader == 7, "ZS main reader changed size"

; Input ROM preimage: LDA.l table,X : ADC.w #base (read*() never sees this patch).
assert read4($1BEECE) == $1BEC3BBF && read4($1BEED1) == $E6C8691B, "Native main palette reader changed"
assert read4($1BEEF2) == $1BEC13BF && read4($1BEEF5) == $E86C691B, "Native aux1 palette reader changed"
assert read4($1BEF16) == $1BEC13BF && read4($1BEF19) == $E86C691B, "Native aux2 palette reader changed"

pushpc
org $1BEECE ; @hook module=Overworld kind=patch name=JointPaletteMain1BEECE
  LDA.l JointPalette_MainDirectory, X : NOP #3
assert pc() == $1BEED5
org $1BEEF2 ; @hook module=Overworld kind=patch name=JointPaletteAux1BEEF2
  LDA.l JointPalette_AuxDirectory, X : NOP #3
assert pc() == $1BEEF9
org $1BEF16 ; @hook module=Overworld kind=patch name=JointPaletteAux1BEF16
  LDA.l JointPalette_AuxDirectory, X : NOP #3
assert pc() == $1BEF1D
pullpc
