pushpc

org $28424
JML MyNewMusic
NOP #02
MyReturn:

pullpc

MyNewMusic:
LDA $A0 : CMP #$C9 : BNE +
JML $028467 ; room was C9 Play village song
+
CMP #$11 : BNE +
JML $028467 ; room was 11 Play village song
+
CMP #$22 : BNE +
JML $028467 ; room was 22 Play village song
+
CMP #$1F : BNE +
JML $028467 ; room was 1F Play village song
+
LDX #$05 ; Load Song 05 (Forest)
CMP #$67 : BNE +
JML $028467 ; room was 67 Play forest song
+
CMP #$59 : BNE +
JML $028467 ; room was 63 Play forest song
+
; Room was not any of the rooms above
JML MyReturn ; return to normal code!


; LDX #$05   for any time that you want to change what song loads