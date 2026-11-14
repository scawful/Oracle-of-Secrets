; Semantic SOURCE quadrant words, independent of resident VRAM remapping.
; Experimental record413: sorted (physical page, local12bit ID, TL,TR,BL,BR),
; six LE16 words; all-FF trailing padding. No new runtime data format.
; Default OFF and UNHOOKED. Build still refuses revision5. A future producer
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

; Unhooked adapter for native $008864 (M16/X16, native D=0 context).
; This is deliberately not installed at that address. It reconstitutes the
; terrain offset lost when X became Tile16*8+quadrant*2. $00 is pixelY while
; $02 is Tile8X: preserve the native masks/shifts, do not use Link's $0700.
; Existing resident parent/area_size tables must already be authenticated.
; Synthetic code binding below qualifies the adapter mechanics only; ordinary
; Build cannot emit this module or admit revision5 yet.
if !SPECIAL_OVERWORLD_RESIDENT_ENABLED == 1
assert !SPECIAL_OVERWORLD_SEMANTIC_CAPACITY == !SPECIAL_OVERWORLD_RESIDENT_END
assert (!SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE>>16) == (Lyra_ResidentPhysicalPage>>16)
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
    JSR Lyra_ResidentPhysicalPage
    BCC .restore
    TAX : PLA
    JSL Lyra_SemanticSourceWord
    PHA
.restore:
    PLA : PLY : PLX : PLD : PLP
    PHA : PLA ; replaced LDA's N/Z, all other caller flags preserved
    RTL
Lyra_SemanticCollisionWord_End:
endif
Lyra_SemanticCodeEnd:
assert pc() <= !SPECIAL_OVERWORLD_SEMANTIC_CODE_END, "Semantic code exceeds explicit bound"
pullpc
endif
