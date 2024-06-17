org $01CC04 ; holes_1 tag routine
JSL NewTagRoutine
RTS

pullpc
NewTagRoutine:
; check under link feet what tile he is standing on
; save somewhere in ram last tile we were on so it doesn't turn it back off
; kill room tag
LDA.b $20 : CLC : ADC #$10 : AND.b #$F0
STA.w $0224 ; y

LDA.b $22 : CLC : ADC #$08 : AND.b #$F0
STA.w $0225 ; x


LDA.w $0224 : CMP.w $0226 : BNE .differentTile
LDA.w $0225 : CMP.w $0227 : BNE .differentTile
JMP .sameTile
.differentTile

; do code here for tile code
REP #$30

LDA.w $022A : AND.w #$01F0 : LSR #$02 : STA.b $00
LDA.w $0228 : AND.w #$01F0 : ASL #$04 : CLC : ADC.b $00 : STA.b $06
TAX

LDA.l $7E2000, X : CMP.w #$0CCC : BNE +
    JSR update_pit_tile
    SEP #$30
    JSR spawnFallingTile
    BRA .doneupdate
+
LDA.l $7E2000, X : CMP.w #$0C62 : BNE +
    JSR update_crack_tile
+
.doneupdate
SEP #$30

.sameTile

LDA.w $0224 : STA.w $0226 : STA.w $0228 ; Last Y
LDA.w $0225 : STA.w $0227 : STA.w $022A ; Last X
; Last Y with link high byte
LDA.b $21 : STA.w $0229
LDA.b $23 : STA.w $022B
RTL


spawnFallingTile:
LDX.b #$1D

.next
LDA.l $7FF800,X
BNE .skip

LDA.b #$03 ; GARNISH 03
STA.l $7FF800,X

LDA.w $022A
STA.l $7FF83C, X

LDA.w $022B
STA.l $7FF878,X

LDA.w $0228
CLC
ADC.b #$10
STA.l $7FF81E,X

LDA.w $0229
ADC.b #$00
STA.l $7FF85A,X

LDA.b #$1F
STA.l $7FF90E,X

STA.w $0FB4

BRA .exit

.skip
DEX
BPL .next

.exit
RTS


update_crack_tile:
STZ.b $0E
REP #$30

JSR replace_crack_pit

SEP #$30

LDA.b #$01
STA.b $14
REP #$30
RTS


update_pit_tile:
STZ.b $0E
REP #$30

JSR replace_tile_pit

SEP #$30

LDA.b #$01
STA.b $14
REP #$30
RTS

replace_crack_pit:
LDX.w $1000

LDA.w #$0CCC
STA.w $1006,X

LDA.w #$0CDC
STA.w $100C,X

LDA.w #$0CCD
STA.w $1012,X

LDA.w #$0CDD
STA.w $1018,X

LDX.b $06

LDA.w #$0CCC
STA.l $7E2000, X
LDA.w #$0CDC
STA.l $7E2080, X
LDA.w #$0CCD
STA.l $7E2002, X
LDA.w #$0CDD
STA.l $7E2082, X

LDA.w #$01E9
AND.w #$03FF
TAX

LDA.l $7EFE00,X
AND.w #$00FF
STA.b $08
STA.b $09

JMP replace_tile_continue

replace_tile_pit:
LDX.w $1000

LDA.w #$01E9
STA.w $1006,X
STA.w $100C,X
STA.w $1012,X
STA.w $1018,X

LDX.b $06

LDA.w #$01E9
STA.l $7E2000, X
STA.l $7E2080, X
STA.l $7E2002, X
STA.l $7E2082, X

TXA
LSR
TAX
LDA.w #$2020
STA.l $7F2000, X
STA.l $7F2040, X


LDA.w #$01E9
AND.w #$03FF
TAX

LDA.l $7EFE00,X
AND.w #$00FF
STA.b $08
STA.b $09

JMP replace_tile_continue


replace_tile_continue:

LDX.w $1000

LDA.w #$0000
JSR draw_one_corner
STA.w $1002,X

LDA.w #$0080
JSR draw_one_corner
STA.w $1008,X

LDA.w #$0002
JSR draw_one_corner
STA.w $100E,X

LDA.w #$0082
JSR draw_one_corner
STA.w $1014,X

LDA.w #$0100
STA.w $1004,X
STA.w $100A,X
STA.w $1010,X
STA.w $1016,X

LDA.w #$FFFF
STA.w $101A,X

TXA
CLC
ADC.w #$0018
STA.w $1000

RTS

; ---------------------------------------------------------

draw_one_corner:
CLC
ADC.b $06
STA.b $0E

AND.w #$0040

LSR A
LSR A
LSR A
LSR A

XBA
STA.b $08

LDA.b $0E
AND.w #$303F
LSR A
ORA.b $08
STA.b $08

LDA.b $0E
AND.w #$0F80
LSR A
LSR A
ORA.b $08
XBA

RTS

