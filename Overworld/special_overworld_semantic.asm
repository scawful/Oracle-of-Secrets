; Semantic SOURCE quadrant words, independent of resident VRAM remapping.
; Experimental record413: sorted (physical page, local12bit ID, TL,TR,BL,BR),
; six LE16 words; all-FF trailing padding. No new runtime data format.
; Default OFF and unbound. The enabled module installs guarded collision
; and action source-word hooks. Ordinary Build still refuses revision5.
; A future producer
; must authenticate the directory/413 CRC and extents before binding these
; constants. Structural assembly checks below do not replace authentication.
if not(defined("SPECIAL_OVERWORLD_SEMANTIC_ENABLED"))
  !SPECIAL_OVERWORLD_SEMANTIC_ENABLED = 0
endif
assert !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 0 || !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
if !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
assert defined("SPECIAL_OVERWORLD_SEMANTIC_REVISION")
assert !SPECIAL_OVERWORLD_SEMANTIC_REVISION == 5
assert defined("SPECIAL_OVERWORLD_SEMANTIC_CAPACITY")
assert !SPECIAL_OVERWORLD_SEMANTIC_CAPACITY == 160 || !SPECIAL_OVERWORLD_SEMANTIC_CAPACITY == 192
assert defined("SPECIAL_OVERWORLD_SEMANTIC_ROWS")
assert defined("SPECIAL_OVERWORLD_SEMANTIC_COUNT")
assert defined("SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE")
assert defined("SPECIAL_OVERWORLD_SEMANTIC_CODE_END")
assert !SPECIAL_OVERWORLD_SEMANTIC_COUNT > 0
assert !SPECIAL_OVERWORLD_SEMANTIC_ROWS >= $008000 && !SPECIAL_OVERWORLD_SEMANTIC_ROWS <= $FFFFFF
assert !SPECIAL_OVERWORLD_SEMANTIC_ROWS&$8000
assert (!SPECIAL_OVERWORLD_SEMANTIC_ROWS>>16) != $7E && (!SPECIAL_OVERWORLD_SEMANTIC_ROWS>>16) != $7F
assert (!SPECIAL_OVERWORLD_SEMANTIC_ROWS&$FFFF)+(!SPECIAL_OVERWORLD_SEMANTIC_COUNT*12) <= $10000
assert !SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE >= $008000 && !SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE <= $FFFFFF
assert !SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE&$8000
assert (!SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE>>16) != $7E && (!SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE>>16) != $7F
assert !SPECIAL_OVERWORLD_SEMANTIC_CODE_END > !SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE
assert (!SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE>>16) == ((!SPECIAL_OVERWORLD_SEMANTIC_CODE_END-1)>>16)
assert !SPECIAL_OVERWORLD_SEMANTIC_CODE_END <= !SPECIAL_OVERWORLD_SEMANTIC_ROWS || !SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE >= !SPECIAL_OVERWORLD_SEMANTIC_ROWS+(!SPECIAL_OVERWORLD_SEMANTIC_COUNT*12)
; Validate the exact immutable source extent before code emission. A malformed
; row/order/padding is an assembly refusal, never an ambiguous runtime match.
!semantic_i = 0
!semantic_last_page #= 0
!semantic_last_id #= 0
!semantic_padding = 0
while !semantic_i < !SPECIAL_OVERWORLD_SEMANTIC_COUNT
  !semantic_at #= !SPECIAL_OVERWORLD_SEMANTIC_ROWS+(!semantic_i*12)
  !semantic_page #= read2(!semantic_at)
  !semantic_id #= read2(!semantic_at+2)
  if !semantic_page == $FFFF
    !semantic_padding = 1
    assert read4(!semantic_at) == $FFFFFFFF && read4(!semantic_at+4) == $FFFFFFFF && read4(!semantic_at+8) == $FFFFFFFF, "Malformed semantic padding"
  else
    assert !semantic_padding == 0, "Semantic row follows padding"
    assert !semantic_page >= $80 && !semantic_page < !SPECIAL_OVERWORLD_SEMANTIC_CAPACITY, "Invalid semantic page"
    assert !semantic_id <= $FFF, "Invalid semantic local ID"
    if !semantic_page == !semantic_last_page
      assert !semantic_id > !semantic_last_id, "Unsorted or duplicate semantic row"
    else
      assert !semantic_page > !semantic_last_page, "Unsorted or duplicate semantic row"
    endif
    !semantic_last_page #= !semantic_page
    !semantic_last_id #= !semantic_id
  endif
  !semantic_i #= !semantic_i+1
endwhile

pushpc
org !SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE
Lyra_SemanticCodeStart:
; M16/X16. A=original global word, X=explicit physical page,
; Y=local Tile16*8+quadrant*2 (TL0,TR2,BL4,BR6).
; Return A=effective source word; preserve ALL P/X/Y/DBR/D and scratch.
; Invalid query/missing row returns the supplied original word exactly.
; Binary search [low,high), at most ceil(log2(count+1)) row comparisons.
Lyra_SemanticSourceWord:
    PHP : PHX : PHY : PHA : CLD
    TYA : AND.w #$8001 : BNE .restore
    TXA : CMP.w #$0080 : BCC .restore
    CMP.w #!SPECIAL_OVERWORLD_SEMANTIC_CAPACITY : BCS .restore
    TYA : LSR : LSR : LSR : PHA ; local ID
    LDA.w #$0000 : PHA ; low
    LDA.w #!SPECIAL_OVERWORLD_SEMANTIC_COUNT : PHA ; high
.search:
    LDA $03,S : CMP $01,S : BCS .missing
    CLC : ADC $01,S : LSR : PHA ; midpoint
    ; stack: mid,high,low,id,nativeword,nativeY,nativeX,P
    ASL : ASL : PHA : ASL : CLC : ADC $01,S : TAX : PLA
    LDA.l !SPECIAL_OVERWORLD_SEMANTIC_ROWS, X
    CMP $0D,S : BCC .higher : BNE .lower
    LDA.l !SPECIAL_OVERWORLD_SEMANTIC_ROWS+2, X
    CMP $07,S : BCC .higher : BNE .lower
    TXA : CLC : ADC.w #$0004 : PHA
    LDA $0D,S : AND.w #$0006 : CLC : ADC $01,S : TAX : PLA
    LDA.l !SPECIAL_OVERWORLD_SEMANTIC_ROWS, X
    STA $09,S
    PLA ; mid
.missing:
    PLA : PLA : PLA ; high,low,id
.restore:
    PLA : PLY : PLX : PLP : RTL
.higher:
    PLA : INC : STA $03,S : BRA .search
.lower:
    PLA : STA $01,S : BRA .search
Lyra_SemanticSourceWord_End:

; Adapter for the guarded native $008864 hook (M16/X16, native D=0).
; It reconstitutes the terrain offset lost when X became Tile16*8+quadrant*2. $00 is pixelY while
; $02 is Tile8X: preserve the native masks/shifts, do not use Link's $0700.
; Existing resident parent/area_size tables must already be authenticated.
; Explicit authenticated code binding is required; ordinary Build does not
; enable this module or admit revision5.
if !SPECIAL_OVERWORLD_RESIDENT_ENABLED == 1
assert !SPECIAL_OVERWORLD_SEMANTIC_CAPACITY == !SPECIAL_OVERWORLD_RESIDENT_END
assert !SPECIAL_OVERWORLD_SEMANTIC_CODE_END <= !LYRA_CURRENT_RESIDENT_CODE_BASE || !SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE >= !LYRA_CURRENT_RESIDENT_CODE_END
Lyra_SemanticCollisionWord:
    PHP : PHD : PHX : PHY
    PEA.w $0000 : PLD : CLD
    LDA.l !LYRA_CURRENT_MAP16_DEFINITIONS, X : PHA
    TXA : TAY
    LDA.l $7E001B : AND.w #$00FF : BNE .restore
    LDA.b $00 : SEC : SBC.l $7E0708 : AND.l $7E070A
    ASL : ASL : ASL : PHA
    LDA.b $02 : SEC : SBC.l $7E070C : AND.l $7E070E
    ORA $01,S : STA $01,S : PLA
    CMP.w #$2000 : BCS .restore
    JSL Lyra_ResidentPhysicalPageLong
    BCC .restore
    TAX : PLA
    JSL Lyra_SemanticSourceWord
    PHA
.restore:
    PLA : PLY : PLX : PLD : PLP
    PHA : PLA ; replaced LDA's N/Z, all other caller flags preserved
    RTL
Lyra_SemanticCollisionWord_End:

; Explicit foreground query: A=raw terrain byte offset, X=Tile16*8+quadrant*2.
; Return source word with LDA N/Z. Preserve X/Y/DBR/D, otherP and allscratch.
; BG1 overlays are not gameplay terrain: resident visuals use host87 while
; record413 semantic rows belong to the physical page. Never infer host87 here.
Lyra_SemanticTerrainSourceWord:
    PHP : PHD : PHX : PHY : PHA
    PEA.w $0000 : PLD : CLD
    LDA.l !LYRA_CURRENT_MAP16_DEFINITIONS, X : PHA
    TXA : TAY
    LDA.l $7E001B : AND.w #$00FF : BNE .restore
    LDA $03,S : CMP.w #$2000 : BCS .restore
    BIT.w #$0001 : BNE .restore
    JSL Lyra_ResidentPhysicalPageLong
    BCC .restore
    TAX : PLA
    JSL Lyra_SemanticSourceWord
    PHA
.restore:
    PLA : STA $01,S : PLA
    PLY : PLX : PLD : PLP
    PHA : PLA
    RTL
Lyra_SemanticTerrainSourceWord_End:

; Entrance/trigger readers keep their original terrain offset in Y; the
; adjacent probe reads Y+2. X remains the caller's Tile16*8 on return.
macro SemanticEntranceWord(name, quadrant, delta)
<name>:
    PHP : PHX : PHY : CLD
    TXA : CLC : ADC.w #<quadrant> : TAX
    TYA : CLC : ADC.w #<delta>
    JSL Lyra_SemanticTerrainSourceWord
    PLY : PLX : PLP
    PHA : PLA
    RTL
endmacro
%SemanticEntranceWord(Lyra_SemanticEntrance0, 0, 0)
%SemanticEntranceWord(Lyra_SemanticEntrance2, 2, 0)
%SemanticEntranceWord(Lyra_SemanticEntrance4, 4, 0)
%SemanticEntranceWord(Lyra_SemanticEntrance6, 6, 0)
%SemanticEntranceWord(Lyra_SemanticNeighbor0, 0, 2)
%SemanticEntranceWord(Lyra_SemanticNeighbor4, 4, 2)
%SemanticEntranceWord(Lyra_SemanticNeighbor6, 6, 2)

; Capture X BEFORE native code replaces its raw terrain offset with a word
; index. DrawMap16 preserves this X even after $00/$02 become VRAM scratch.
; Execute the displaced quadrant instructions and their $06/flags/X effects
; exactly. The raw offset lives on this call's stack only. No fixed ID changes.
Lyra_SemanticTileActionWord:
    PHX
    ASL : ASL : STA.b $06
    LDA.b $00 : AND.w #$0008 : LSR : LSR : TSB.b $06
    LDA.b $02 : AND.w #$0001 : ORA.b $06 : ASL : TAX
    LDA $01,S
    JSL Lyra_SemanticTerrainSourceWord
    STA $01,S : PLA
    RTL
Lyra_SemanticHammerWord:
    PHX
    ASL : ASL : ASL : TAX
    LDA $01,S
    JSL Lyra_SemanticTerrainSourceWord
    STA $01,S : PLA
    RTL
Lyra_SemanticLiftWord:
    PHX
    ASL : ASL : STA.b $06
    LDA.b $02 : AND.w #$0008 : LSR : LSR : TSB.b $06
    LDA.b $00 : LSR : LSR : LSR : AND.w #$0001
    ORA.b $06 : ASL : TAX
    LDA $01,S
    JSL Lyra_SemanticTerrainSourceWord
    STA $01,S : PLA
    RTL
Lyra_SemanticActionWords_End:

endif
Lyra_SemanticCodeEnd:
assert pc() <= !SPECIAL_OVERWORLD_SEMANTIC_CODE_END, "Semantic code exceeds explicit bound"
pullpc

; Semantic source loads: bind only the existing explicitly enabled module.
; The visual mutable 1BC9/1BCA loads remain resident VRAM-word consumers.
if !SPECIAL_OVERWORLD_RESIDENT_ENABLED == 1
pushpc
; Replace only LDA.l Map16Definitions,X. The following STA $06, character
; mask and SkyTileType/H-flip continuation retain their original ownership.
assert read4($008864) == ((!LYRA_CURRENT_MAP16_DEFINITIONS<<8)|$BF) || read4($008864) == (((!LYRA_CURRENT_MAP16_DEFINITIONS|$800000)<<8)|$BF), "Semantic collision source read moved"
org $008864 ; @hook module=Overworld kind=jsl target=Lyra_SemanticCollisionWord expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_SemanticCollisionWord
assert pc() == $008868
; Active vanilla special-transition callers retain GetMap16Tile Y=raw offset
; and X=Tile16*8. The dormant special_areas.asm is not an active caller.
assert read4($0EDE4E) == ((!LYRA_CURRENT_MAP16_DEFINITIONS<<8)|$BF) || read4($0EDE4E) == (((!LYRA_CURRENT_MAP16_DEFINITIONS|$800000)<<8)|$BF), "Semantic special transition source read moved"
org $0EDE4E ; @hook module=Overworld kind=jsl target=Lyra_SemanticEntrance0 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_SemanticEntrance0
assert pc() == $0EDE52
assert read4($0EDEE8) == ((!LYRA_CURRENT_MAP16_DEFINITIONS<<8)|$BF) || read4($0EDEE8) == (((!LYRA_CURRENT_MAP16_DEFINITIONS|$800000)<<8)|$BF), "Semantic special transition source read moved"
org $0EDEE8 ; @hook module=Overworld kind=jsl target=Lyra_SemanticEntrance0 expected_m=16 expected_x=16 protected_size=4
    JSL Lyra_SemanticEntrance0
assert pc() == $0EDEEC
assert read1($1BBEDF) == $0A, "Semantic action prefix moved"
assert read1($1BBEE0) == $0A, "Semantic action prefix moved"
assert read1($1BBEE1) == $85, "Semantic action prefix moved"
assert read1($1BBEE2) == $06, "Semantic action prefix moved"
assert read1($1BBEE3) == $A5, "Semantic action prefix moved"
assert read1($1BBEE4) == $00, "Semantic action prefix moved"
assert read1($1BBEE5) == $29, "Semantic action prefix moved"
assert read1($1BBEE6) == $08, "Semantic action prefix moved"
assert read1($1BBEE7) == $00, "Semantic action prefix moved"
assert read1($1BBEE8) == $4A, "Semantic action prefix moved"
assert read1($1BBEE9) == $4A, "Semantic action prefix moved"
assert read1($1BBEEA) == $04, "Semantic action prefix moved"
assert read1($1BBEEB) == $06, "Semantic action prefix moved"
assert read1($1BBEEC) == $A5, "Semantic action prefix moved"
assert read1($1BBEED) == $02, "Semantic action prefix moved"
assert read1($1BBEEE) == $29, "Semantic action prefix moved"
assert read1($1BBEEF) == $01, "Semantic action prefix moved"
assert read1($1BBEF0) == $00, "Semantic action prefix moved"
assert read1($1BBEF1) == $05, "Semantic action prefix moved"
assert read1($1BBEF2) == $06, "Semantic action prefix moved"
assert read1($1BBEF3) == $0A, "Semantic action prefix moved"
assert read1($1BBEF4) == $AA, "Semantic action prefix moved"
assert read4($1BBEF5) == ((!LYRA_CURRENT_MAP16_DEFINITIONS<<8)|$BF) || read4($1BBEF5) == (((!LYRA_CURRENT_MAP16_DEFINITIONS|$800000)<<8)|$BF), "Semantic action source read moved"
org $1BBEDF ; @hook module=Overworld kind=jsl target=Lyra_SemanticTileActionWord expected_m=16 expected_x=16 protected_size=26
    JSL Lyra_SemanticTileActionWord : NOP #22
assert pc() == $1BBEF9
assert read1($1BBF1E) == $0A, "Semantic action prefix moved"
assert read1($1BBF1F) == $0A, "Semantic action prefix moved"
assert read1($1BBF20) == $0A, "Semantic action prefix moved"
assert read1($1BBF21) == $AA, "Semantic action prefix moved"
assert read4($1BBF22) == ((!LYRA_CURRENT_MAP16_DEFINITIONS<<8)|$BF) || read4($1BBF22) == (((!LYRA_CURRENT_MAP16_DEFINITIONS|$800000)<<8)|$BF), "Semantic action source read moved"
org $1BBF1E ; @hook module=Overworld kind=jsl target=Lyra_SemanticHammerWord expected_m=16 expected_x=16 protected_size=8
    JSL Lyra_SemanticHammerWord : NOP #4
assert pc() == $1BBF26
assert read1($1BC027) == $0A, "Semantic action prefix moved"
assert read1($1BC028) == $0A, "Semantic action prefix moved"
assert read1($1BC029) == $85, "Semantic action prefix moved"
assert read1($1BC02A) == $06, "Semantic action prefix moved"
assert read1($1BC02B) == $A5, "Semantic action prefix moved"
assert read1($1BC02C) == $02, "Semantic action prefix moved"
assert read1($1BC02D) == $29, "Semantic action prefix moved"
assert read1($1BC02E) == $08, "Semantic action prefix moved"
assert read1($1BC02F) == $00, "Semantic action prefix moved"
assert read1($1BC030) == $4A, "Semantic action prefix moved"
assert read1($1BC031) == $4A, "Semantic action prefix moved"
assert read1($1BC032) == $04, "Semantic action prefix moved"
assert read1($1BC033) == $06, "Semantic action prefix moved"
assert read1($1BC034) == $A5, "Semantic action prefix moved"
assert read1($1BC035) == $00, "Semantic action prefix moved"
assert read1($1BC036) == $4A, "Semantic action prefix moved"
assert read1($1BC037) == $4A, "Semantic action prefix moved"
assert read1($1BC038) == $4A, "Semantic action prefix moved"
assert read1($1BC039) == $29, "Semantic action prefix moved"
assert read1($1BC03A) == $01, "Semantic action prefix moved"
assert read1($1BC03B) == $00, "Semantic action prefix moved"
assert read1($1BC03C) == $05, "Semantic action prefix moved"
assert read1($1BC03D) == $06, "Semantic action prefix moved"
assert read1($1BC03E) == $0A, "Semantic action prefix moved"
assert read1($1BC03F) == $AA, "Semantic action prefix moved"
assert read4($1BC040) == ((!LYRA_CURRENT_MAP16_DEFINITIONS<<8)|$BF) || read4($1BC040) == (((!LYRA_CURRENT_MAP16_DEFINITIONS|$800000)<<8)|$BF), "Semantic action source read moved"
org $1BC027 ; @hook module=Overworld kind=jsl target=Lyra_SemanticLiftWord expected_m=16 expected_x=16 protected_size=29
    JSL Lyra_SemanticLiftWord : NOP #25
assert pc() == $1BC044
pullpc
endif
endif
