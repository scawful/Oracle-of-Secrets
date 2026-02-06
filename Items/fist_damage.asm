lorom

pushpc

org $028925
NOP
NOP

org $06EB90
NOP
NOP

org $06ED6A ; @hook module=Items
JSL FistBump ; $1BB4D0

org $06F2D6 ; @hook module=Items
db $80, $05 ; BRA 05 ??
JSL FistBump2 ; $1BB572
RTS

org $06F3C7 ; @hook module=Items
JMP $F2D8

org $06F6C4 ; @hook module=Items
JSL FistBump3 ; $1BB380
NOP

org $0781CD
NOP
NOP

org $079E67
NOP #$04
CMP #$FF

org $09F608
NOP
NOP

pullpc


FistBump3: ; Good ; $1BB380
ORA #$05
STA $012E ; play sound effect

PHA
AND #$05 : CMP #$05 : BEQ .branchA
PLA
RTL
.branchA

LDA.w $037A : CMP #$10 : BEQ .branchB
PLA
RTL
.branchB

STZ.w $037A
PLA
RTL



FistBump: ; $1BB4D0
JMP FistBump4

FistBump5:

CPX #$FE : BEQ .branchC
CPX #$FF : BEQ .branchC
LDA.l $06ED33, X
BRA .branchD
.branchC
LDA.b #$00
.branchD
RTL




FistBump4: ;$1BB4F0
LDA $037A
CMP #$10 : BNE .branchE
JMP FistBump5_branchC
.branchE
JMP FistBump5


FistBump2:; $1BB572
BCC .branchF
LDA $037A
AND #$10 : BNE +
.branchF
LDA.b #$00
+
RTL
