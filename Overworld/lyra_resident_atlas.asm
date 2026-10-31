; =========================================================
; File: Overworld/lyra_resident_atlas.asm
; Purpose: Physical-page Tile16 words for a resident gameplay-area atlas.
; Author: Codex
; =========================================================
;@source: usdasm bank_02.asm $02F435/$02F50A/$02FDF7;
;         bank_1B.asm Overworld_DrawMap16_Anywhere/Overworld_AlterTileHardcore.
;@verified: Source ABI only; allocation and native activation remain unbound.
;
; ABI v1 directory:32 physical pages A0..BF,8 bytes per record:
; index pointer24, word pointer24, area index8, remap row count8.
; Index:128 block IDs for Tile16>>5, then packed32-byte nonzero blocks.
; Block0 and row0 mean an unqualified native fallback; target word0 is valid.
; Word rows are8 bytes in TL/TR/BL/BR order, including unused zero row0.
; Each directory/index/word extent must remain within one LoROM bank.
; Missing dynamic Tile16 rows do not establish appearance or build readiness.

!LyraResidentEnabled = 0
if defined("LYRA_CURRENT_RESIDENT_ENABLED")
  !LyraResidentEnabled = !LYRA_CURRENT_RESIDENT_ENABLED
endif
assert !LyraResidentEnabled == 0 || !LyraResidentEnabled == 1
if !LyraResidentEnabled == 1
assert !LyraNativeCurrentBranch == 1
assert defined("LYRA_CURRENT_RESIDENT_ABI_VERSION"), "Resident atlas ABI is unbound"
assert defined("LYRA_CURRENT_RESIDENT_CODE_BASE"), "Resident atlas code origin is unbound"
assert defined("LYRA_CURRENT_RESIDENT_CODE_END"), "Resident atlas code bound is unbound"
assert defined("LYRA_CURRENT_RESIDENT_DIRECTORY"), "Resident atlas directory is unbound"
assert defined("LYRA_CURRENT_RESIDENT_TILE16_COUNT"), "Resident atlas Tile16 extent is unbound"
assert !LYRA_CURRENT_RESIDENT_ABI_VERSION == 1
assert !LYRA_CURRENT_RESIDENT_TILE16_COUNT > 0
assert !LYRA_CURRENT_RESIDENT_TILE16_COUNT <= 4096
assert !LYRA_CURRENT_RESIDENT_CODE_BASE&$8000
assert !LYRA_CURRENT_RESIDENT_CODE_END > !LYRA_CURRENT_RESIDENT_CODE_BASE
assert !LYRA_CURRENT_RESIDENT_CODE_END-!LYRA_CURRENT_RESIDENT_CODE_BASE <= $0600
assert (!LYRA_CURRENT_RESIDENT_CODE_BASE>>16) == ((!LYRA_CURRENT_RESIDENT_CODE_END-1)>>16)
assert !LYRA_CURRENT_RESIDENT_DIRECTORY&$8000
assert (!LYRA_CURRENT_RESIDENT_DIRECTORY&$FFFF)+$0100 <= $10000

; Every hook enters M16/X16. Preserve X/Y/DBR/D and all caller flags except
; loaded-word N/Z. Capture the native word before classification, so every
; refused lookup retains its original operand. Use DP0 and binary arithmetic
; internally; restore caller D and decimal state before returning.
; Full hooks also replace the following four-byte native long store.
macro LyraResidentWord(name, old, quadrant, source, full, destination)
<name>:
    PHP : PHD : PEA.w $0000 : PLD : CLD
if <full> == 1
    LDA.w <old>, Y
else
    LDA.l <old>, X
endif
    PHA : PHX : PHY
    LDA.w #<quadrant> : PHA
    JSR <source>
    BCC ?restore
    STA $07,S
?restore:
    PLA : PLY : PLX : PLA : PLD : PLP
    PHA : PLA
if <full> == 1
    STA.l <destination>, X
endif
    RTL
<name>_End:
endmacro

pushpc
org !LYRA_CURRENT_RESIDENT_CODE_BASE
Lyra_ResidentAtlasCodeStart:
%LyraResidentWord(Lyra_ResidentFull0, $8000, $0000, Lyra_ResidentFullWord, 1, $7F2000)
%LyraResidentWord(Lyra_ResidentFull1, $8002, $0002, Lyra_ResidentFullWord, 1, $7F2000)
%LyraResidentWord(Lyra_ResidentFull2, $8004, $0004, Lyra_ResidentFullWord, 1, $7F2040)
%LyraResidentWord(Lyra_ResidentFull3, $8006, $0006, Lyra_ResidentFullWord, 1, $7F2040)
%LyraResidentWord(Lyra_ResidentHorizontal0, $BD8000, $0000, Lyra_ResidentHorizontalWord, 0, $000000)
%LyraResidentWord(Lyra_ResidentHorizontal1, $BD8002, $0002, Lyra_ResidentHorizontalWord, 0, $000000)
%LyraResidentWord(Lyra_ResidentHorizontal2, $BD8004, $0004, Lyra_ResidentHorizontalWord, 0, $000000)
%LyraResidentWord(Lyra_ResidentHorizontal3, $BD8006, $0006, Lyra_ResidentHorizontalWord, 0, $000000)
%LyraResidentWord(Lyra_ResidentVertical0, $BD8000, $0000, Lyra_ResidentVerticalWord, 0, $000000)
%LyraResidentWord(Lyra_ResidentVertical1, $BD8002, $0002, Lyra_ResidentVerticalWord, 0, $000000)
%LyraResidentWord(Lyra_ResidentVertical2, $BD8004, $0004, Lyra_ResidentVerticalWord, 0, $000000)
%LyraResidentWord(Lyra_ResidentVertical3, $BD8006, $0006, Lyra_ResidentVerticalWord, 0, $000000)
%LyraResidentWord(Lyra_ResidentMutable0, $BD8000, $0000, Lyra_ResidentMutableWord, 0, $000000)
%LyraResidentWord(Lyra_ResidentMutable1, $BD8002, $0002, Lyra_ResidentMutableWord, 0, $000000)
%LyraResidentWord(Lyra_ResidentMutable2, $BD8004, $0004, Lyra_ResidentMutableWord, 0, $000000)
%LyraResidentWord(Lyra_ResidentMutable3, $BD8006, $0006, Lyra_ResidentMutableWord, 0, $000000)

; Ice Rod's direct writer enters M16/X16 with X=the raw terrain target.
; Its qualified B7 row must have four identical source and packed words.
; Preserve X/Y/DBR/D, scratch and P except loaded N/Z, especially carry:
; the unchanged second DMA row uses ADC #$0020 without another CLC.
if defined("LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED")
if !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED == 1
Lyra_ResidentIceRodWord:
    PHP : PHD : PEA.w $0000 : PLD : CLD
    LDA.w #$1D83 : PHA : PHX : PHY
    LDA.l $7E001B : AND.w #$00FF : BNE .restore
    TXA : CMP.w #$2000 : BCS .restore
    LDY.w #($00B7*8)
    JSR Lyra_ResidentLookup
    BCC .restore
    STA $05,S
.restore:
    PLY : PLX : PLA : PLD : PLP
    PHA : PLA : RTL
Lyra_ResidentIceRodWord_End:
endif
endif

; Internal M16/X16 helpers return C set only for a qualified remap word.
; At entry:3,S=quadrant,5,S=native Y,7,S=native X,9,S=native word.
; $02 is already two bytes beyond the current $0500 entry.
Lyra_ResidentFullWord:
    LDA.b $04 : CMP.w #$2000 : BNE .native
    LDA.b $06 : AND.w #$00FF : CMP.w #$007E : BNE .native
    LDA.b $86 : ASL : JSR Lyra_ResidentBufferDelta
    CLC : ADC.b $84 : SEC : SBC.w #$0410 : AND.w #$1FFF
    PHA
    LDA $07,S : ORA $05,S : TAY
    PLA
    JSR Lyra_ResidentLookup
    RTS
.native:
    CLC : RTS
Lyra_ResidentFullWord_End:

Lyra_ResidentHorizontalWord:
    LDA.b $88 : ASL : JSR Lyra_ResidentBufferDelta
    ASL : ASL : ASL : ASL : ASL : ASL
    CLC : ADC.b $84 : PHA
    LDA.w $0416 : AND.w #$0002 : TAX
    LDA.l Lyra_ResidentHorizontalOffsets, X
    EOR.w #$FFFF : INC : CLC : ADC $01,S
    STA $01,S : PLA
    CMP.w #$2000 : BCS .native
    PHA
    LDA $09,S : ORA $05,S : TAY
    PLA
    JSR Lyra_ResidentLookup
    RTS
.native:
    CLC : RTS
Lyra_ResidentHorizontalWord_End:

Lyra_ResidentVerticalWord:
    LDA.b $86 : ASL : JSR Lyra_ResidentBufferDelta
    CLC : ADC.b $84 : PHA
    LDA.w $0416 : AND.w #$0004 : LSR : TAX
    LDA.l Lyra_ResidentVerticalOffsets, X
    EOR.w #$FFFF : INC : CLC : ADC $01,S
    STA $01,S : PLA
    CMP.w #$2000 : BCS .native
    PHA
    LDA $09,S : ORA $05,S : TAY
    PLA
    JSR Lyra_ResidentLookup
    RTS
.native:
    CLC : RTS
Lyra_ResidentVerticalWord_End:

; Both mutable renderers retain the actual terrain byte offset in $00.
; Native X is Tile16*8, while native Y indexes the output stripe buffer.
; Refuse nonterrain offsets instead of wrapping them onto a resident page.
Lyra_ResidentMutableWord:
    LDA.b $00 : CMP.w #$2000 : BCS .native
    LDA $07,S : ORA $03,S : TAY
    LDA.b $00
    JSR Lyra_ResidentLookup
    RTS
.native:
    CLC : RTS
Lyra_ResidentMutableWord_End:

; A=twice the native buffer origin ($86 for rows, $88 for columns).
; Return (($02-2)-A)&$003F without changing any live native scratch.
Lyra_ResidentBufferDelta:
    PHA
    LDA.b $02 : SEC : SBC.w #$0002 : SEC : SBC $01,S
    AND.w #$003F : STA $01,S : PLA
    RTS
Lyra_ResidentBufferDelta_End:

; A=raw terrain byte offset; Y=Tile16*8+quadrant*2. The full source
; wraps to $1FFF before entry; stripe callers refuse raw offsets >=$2000.
; Physical page uses saved parent/size, independently of Link's $0700.
Lyra_ResidentPhysicalPage:
    PHA
    LDA.b $8A : AND.w #$00FF : TAX
    AND.w #$FFE0 : CMP.w #$00A0 : BNE .native_source
    LDA.l !LYRA_CURRENT_TABLE_parent, X : AND.w #$00FF
    CMP.w #$00A0 : BCC .native_source
    CMP.w #$00C0 : BCS .native_source
    PHA
    LDA.l !LYRA_CURRENT_TABLE_area_size, X : AND.w #$00FF
    CMP.w #$0004 : BCS .native_parent
    ASL : TAX
    LDA.l Lyra_ResidentQuadrantMasks, X : PHA
    LDA $05,S : AND.w #$1000 : XBA : LSR : PHA
    LDA $07,S : AND.w #$0040
    LSR : LSR : LSR : LSR : LSR : LSR
    ORA $01,S : AND $03,S : CLC : ADC $05,S
    STA $07,S
    PLA : PLA : PLA : PLA
    CMP.w #$00A0 : BCC .native
    CMP.w #$00C0 : BCS .native
    SEC : RTS
.native_parent:
    PLA
.native_source:
    PLA
.native:
    CLC : RTS
Lyra_ResidentPhysicalPage_End:

; Two-level ABI v1 lookup. The saved $00/$02 words cover every byte
; written by the temporary long pointer. No other caller scratch is written.
Lyra_ResidentLookup:
    PHA
    TYA : CMP.w #(!LYRA_CURRENT_RESIDENT_TILE16_COUNT*8) : BCC .tile_valid
    PLA : CLC : RTS
.tile_valid:
    PLA : JSR Lyra_ResidentPhysicalPage
    BCS .page_valid
    RTS
.page_valid:
    SEC : SBC.w #$00A0 : ASL : ASL : ASL : TAX
    LDA.b $00 : PHA
    LDA.b $02 : PHA
    LDA.l !LYRA_CURRENT_RESIDENT_DIRECTORY+3, X : PHA
    LDA.l !LYRA_CURRENT_RESIDENT_DIRECTORY+5, X : AND.w #$00FF : PHA
    LDA.l !LYRA_CURRENT_RESIDENT_DIRECTORY+7, X : AND.w #$00FF : PHA
    LDA.l !LYRA_CURRENT_RESIDENT_DIRECTORY, X : STA.b $00
    LDA.l !LYRA_CURRENT_RESIDENT_DIRECTORY+2, X : AND.w #$00FF : STA.b $02
    TYA : AND.w #$0006 : PHA
    TYA : LSR : LSR : LSR : PHA
    LSR : LSR : LSR : LSR : LSR : TAY
    SEP #$20
    LDA.b [$00], Y
    REP #$20
    AND.w #$00FF : BEQ .missing_index
    CMP.w #$0081 : BCS .missing_index
    DEC : ASL : ASL : ASL : ASL : ASL
    CLC : ADC.w #$0080 : PHA
    LDA $03,S : AND.w #$001F : CLC : ADC $01,S : TAY
    PLA
    SEP #$20
    LDA.b [$00], Y
    REP #$20
    AND.w #$00FF : BEQ .missing_index
    CMP $05,S : BEQ .row_valid
    BCS .missing_index
.row_valid:
    ASL : ASL : ASL : CLC : ADC $03,S : TAY
    LDA $09,S : STA.b $00
    LDA $07,S : STA.b $02
    LDA.b [$00], Y : TAX
    PLA : PLA : PLA : PLA : PLA
    PLA : STA.b $02
    PLA : STA.b $00
    TXA : SEC : RTS
.missing_index:
    PLA : PLA : PLA : PLA : PLA
    PLA : STA.b $02
    PLA : STA.b $00
    CLC : RTS
Lyra_ResidentLookup_End:

Lyra_ResidentQuadrantMasks:
    dw $0000, $0009, $0001, $0008 ; small, large, wide, tall
Lyra_ResidentHorizontalOffsets:
    dw $03D0, $0410
Lyra_ResidentVerticalOffsets:
    dw $0410, $F410
Lyra_ResidentAtlasCodeEnd:
assert pc() <= !LYRA_CURRENT_RESIDENT_CODE_END, "Resident atlas code exceeds explicit origin"
assert Lyra_ResidentAtlasCodeEnd-Lyra_ResidentAtlasCodeStart <= $0600
pullpc

; Full: a three-byte LDA.w plus four-byte STA.l. Each stripe replaces
; only its four-byte LDA.l, leaving the native following store untouched.
pushpc
assert read3($02FE1B) == (($8000<<8)|$B9), "Native full Tile16 reader moved"
assert read4($02FE1B+3) == (($7F2000<<8)|$9F), "Native full Tile16 store moved"
org $02FE1B ; @hook module=Overworld kind=jsl target=Lyra_ResidentFull0 expected_m=16 expected_x=16 protected_size=7
    JSL Lyra_ResidentFull0 : NOP #3
assert pc() == $02FE1B+7
assert read3($02FE22) == (($8004<<8)|$B9), "Native full Tile16 reader moved"
assert read4($02FE22+3) == (($7F2040<<8)|$9F), "Native full Tile16 store moved"
org $02FE22 ; @hook module=Overworld kind=jsl target=Lyra_ResidentFull2 expected_m=16 expected_x=16 protected_size=7
    JSL Lyra_ResidentFull2 : NOP #3
assert pc() == $02FE22+7
assert read3($02FE2B) == (($8002<<8)|$B9), "Native full Tile16 reader moved"
assert read4($02FE2B+3) == (($7F2000<<8)|$9F), "Native full Tile16 store moved"
org $02FE2B ; @hook module=Overworld kind=jsl target=Lyra_ResidentFull1 expected_m=16 expected_x=16 protected_size=7
    JSL Lyra_ResidentFull1 : NOP #3
assert pc() == $02FE2B+7
assert read3($02FE32) == (($8006<<8)|$B9), "Native full Tile16 reader moved"
assert read4($02FE32+3) == (($7F2040<<8)|$9F), "Native full Tile16 store moved"
org $02FE32 ; @hook module=Overworld kind=jsl target=Lyra_ResidentFull3 expected_m=16 expected_x=16 protected_size=7
    JSL Lyra_ResidentFull3 : NOP #3
assert pc() == $02FE32+7
assert read4($02F456) == (($BD8000<<8)|$BF), "Native stripe Tile16 reader moved"
org $02F456 ; @hook module=Overworld kind=jsl target=Lyra_ResidentHorizontal0 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentHorizontal0
assert pc() == $02F456+4
assert read4($02F45D) == (($BD8002<<8)|$BF), "Native stripe Tile16 reader moved"
org $02F45D ; @hook module=Overworld kind=jsl target=Lyra_ResidentHorizontal1 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentHorizontal1
assert pc() == $02F45D+4
assert read4($02F466) == (($BD8004<<8)|$BF), "Native stripe Tile16 reader moved"
org $02F466 ; @hook module=Overworld kind=jsl target=Lyra_ResidentHorizontal2 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentHorizontal2
assert pc() == $02F466+4
assert read4($02F46D) == (($BD8006<<8)|$BF), "Native stripe Tile16 reader moved"
org $02F46D ; @hook module=Overworld kind=jsl target=Lyra_ResidentHorizontal3 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentHorizontal3
assert pc() == $02F46D+4
assert read4($02F51E) == (($BD8000<<8)|$BF), "Native stripe Tile16 reader moved"
org $02F51E ; @hook module=Overworld kind=jsl target=Lyra_ResidentVertical0 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentVertical0
assert pc() == $02F51E+4
assert read4($02F525) == (($BD8004<<8)|$BF), "Native stripe Tile16 reader moved"
org $02F525 ; @hook module=Overworld kind=jsl target=Lyra_ResidentVertical2 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentVertical2
assert pc() == $02F525+4
assert read4($02F52E) == (($BD8002<<8)|$BF), "Native stripe Tile16 reader moved"
org $02F52E ; @hook module=Overworld kind=jsl target=Lyra_ResidentVertical1 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentVertical1
assert pc() == $02F52E+4
assert read4($02F535) == (($BD8006<<8)|$BF), "Native stripe Tile16 reader moved"
org $02F535 ; @hook module=Overworld kind=jsl target=Lyra_ResidentVertical3 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentVertical3
assert pc() == $02F535+4
; Mutable draws replace only their four-byte global word loads. Keep the
; following stripe stores, target coordinates and native update scheduling.
assert read4($1BC9B2) == (($BD8000<<8)|$BF), "Native stripe Tile16 reader moved"
org $1BC9B2 ; @hook module=Overworld kind=jsl target=Lyra_ResidentMutable0 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentMutable0
assert pc() == $1BC9B2+4
assert read4($1BC9B9) == (($BD8002<<8)|$BF), "Native stripe Tile16 reader moved"
org $1BC9B9 ; @hook module=Overworld kind=jsl target=Lyra_ResidentMutable1 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentMutable1
assert pc() == $1BC9B9+4
assert read4($1BC9C0) == (($BD8004<<8)|$BF), "Native stripe Tile16 reader moved"
org $1BC9C0 ; @hook module=Overworld kind=jsl target=Lyra_ResidentMutable2 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentMutable2
assert pc() == $1BC9C0+4
assert read4($1BC9C7) == (($BD8006<<8)|$BF), "Native stripe Tile16 reader moved"
org $1BC9C7 ; @hook module=Overworld kind=jsl target=Lyra_ResidentMutable3 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentMutable3
assert pc() == $1BC9C7+4
assert read4($1BCA3F) == (($BD8000<<8)|$BF), "Native stripe Tile16 reader moved"
org $1BCA3F ; @hook module=Overworld kind=jsl target=Lyra_ResidentMutable0 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentMutable0
assert pc() == $1BCA3F+4
assert read4($1BCA46) == (($BD8002<<8)|$BF), "Native stripe Tile16 reader moved"
org $1BCA46 ; @hook module=Overworld kind=jsl target=Lyra_ResidentMutable1 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentMutable1
assert pc() == $1BCA46+4
assert read4($1BCA4D) == (($BD8004<<8)|$BF), "Native stripe Tile16 reader moved"
org $1BCA4D ; @hook module=Overworld kind=jsl target=Lyra_ResidentMutable2 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentMutable2
assert pc() == $1BCA4D+4
assert read4($1BCA54) == (($BD8006<<8)|$BF), "Native stripe Tile16 reader moved"
org $1BCA54 ; @hook module=Overworld kind=jsl target=Lyra_ResidentMutable3 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_ResidentMutable3
assert pc() == $1BCA54+4
pullpc
endif
