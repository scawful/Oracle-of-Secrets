; Native special-overworld readers, selectively retained from606 current mode.
; Lyra_* names remain searchable aliases; all32 tail pages share this engine.
; Ordinary Build emits code only. Table/dictionary/stream bodies stay ROM-owned.
assert !SPECIAL_OVERWORLD_NATIVE == 1
assert !LYRA_CURRENT_FIRST == $A0 && !LYRA_CURRENT_END == $C0
assert !LYRA_CURRENT_PARENT_COUNT == $C0
if not(defined("LYRA_CURRENT_HIDDEN_STREAMS_BOUND"))
  !LYRA_CURRENT_HIDDEN_STREAMS_BOUND = 0
endif
assert !LYRA_CURRENT_HIDDEN_STREAMS_BOUND == 0 || !LYRA_CURRENT_HIDDEN_STREAMS_BOUND == 1

; Save full A/X before classification. The stack result replaces only its low
; byte for an M8 caller, preserving hidden B. PHA/PLA after PLP establishes
; the original-width load N/Z without changing caller C/V, DBR, D or Y.
; reg=0 is X, reg=1 is Y; bounds are ORIGINAL byte indices, before bias.
macro LyraCurrentIndexed(name, old, selected, reg, first, end, bias)
<name>:
    PHP : REP #$30 : PHA : PHX
if <reg> == 0
    TXA
else
    TYA
endif
    CMP.w #<first> : BCC ?legacy
    CMP.w #<end> : BCS ?legacy
if <bias> != 0
    CLC : ADC.w #<bias>
endif
    TAX
    LDA $05,S : AND.w #$0020 : BNE ?byte
    LDA.l <selected>, X : STA $03,S
    BRA ?restore
?byte:
    SEP #$20
    LDA.l <selected>, X : STA $03,S
    REP #$20
?restore:
    PLX : PLA : PLP
    PHA : PLA : RTL
?legacy:
    PLX : PLA : PLP
if <reg> == 0
    LDA.l <old>, X
else
    LDA.w <old>, Y
endif
    RTL
<name>_End:
endmacro

; Sprite resources follow the same three placement states as the actor list.
; Save full A/X/Y and P before classification; only selected tail calls query
; Oracle's phase. The M16 SpecialPalette caller initializes a word cache, so
; it copies phase0 without consulting active-area clock/progression state.
; All other selected reads preserve the original byte/word load width.
macro LyraCurrentSpriteIndexed(name, old, phase0, phase1, phase2, first, end, bias, word_cache)
<name>:
    PHP : REP #$30 : PHA : PHX : PHY
    TXA
    CMP.w #<first> : BCS ?upper
      BRL ?legacy
?upper:
    CMP.w #<end> : BCC ?selected
      BRL ?legacy
?selected:
if <bias> != 0
    CLC : ADC.w #<bias>
endif
    TAX
if <word_cache> == 1
    LDA $07,S : AND.w #$0020 : BEQ ?load
endif
    JSR Lyra_CurrentSpritePhase
    CMP.w #$0002 : BEQ ?phase1
    CMP.w #$0003 : BNE ?load
    TXA : CLC : ADC.w #(<phase2>-<phase0>) : TAX
    BRA ?load
?phase1:
    TXA : CLC : ADC.w #(<phase1>-<phase0>) : TAX
?load:
    LDA $07,S : AND.w #$0020 : BNE ?byte
    LDA.l <phase0>, X : STA $05,S
    BRA ?restore
?byte:
    SEP #$20
    LDA.l <phase0>, X : STA $05,S
    REP #$20
?restore:
    PLY : PLX : PLA : PLP
    PHA : PLA : RTL
?legacy:
    PLY : PLX : PLA : PLP
    LDA.l <old>, X
    RTL
<name>_End:
endmacro

pushpc
org !LYRA_CURRENT_CODE_BASE
Lyra_CurrentNativeCodeStart:
; M16/XY16 internal helper. CheckIfNight uses native DP0; retain caller D,
; the normalized table index and Y even if that source changes index width.
Lyra_CurrentSpritePhase:
    PHD : PHX : PHY
    PEA.w $0000 : PLD
    SEP #$20
    JSL Oracle_CheckIfNight
    REP #$30
    AND.w #$00FF
    PLY : PLX : PLD
    RTS
Lyra_CurrentSpritePhase_End:

%LyraCurrentIndexed(Lyra_ReadAnimated, $2882A0, !LYRA_CURRENT_TABLE_animated+$0000, 0, $00A0, $00C0, $0000)
%LyraCurrentIndexed(Lyra_ReadMainPalette, $288160, !LYRA_CURRENT_TABLE_main_palette+$0000, 0, $00A0, $00C0, $0000)
%LyraCurrentIndexed(Lyra_ReadOverlay, $288340, !LYRA_CURRENT_TABLE_overlay+$0000, 0, $0140, $0180, $0000)
%LyraCurrentIndexed(Lyra_ReadSize, $02F88D, !LYRA_CURRENT_TABLE_area_size+$0000, 0, $00A0, $00C0, $0000)
Oracle_Lyra_ReadParent:
%LyraCurrentIndexed(Lyra_ReadParent, $288998, !LYRA_CURRENT_TABLE_parent+$0000, 0, $00A0, $00C0, $0000)
%LyraCurrentIndexed(Lyra_ReadTransitionYX, $288F38, !LYRA_CURRENT_TABLE_transition_y+$0000, 0, $0140, $0180, $0000)
%LyraCurrentIndexed(Lyra_ReadTransitionXX, $289078, !LYRA_CURRENT_TABLE_transition_x+$0000, 0, $0140, $0180, $0000)
%LyraCurrentIndexed(Lyra_ReadTransitionYY, $288F38, !LYRA_CURRENT_TABLE_transition_y+$0000, 1, $0140, $0180, $0000)
%LyraCurrentIndexed(Lyra_ReadTransitionXY, $289078, !LYRA_CURRENT_TABLE_transition_x+$0000, 1, $0140, $0180, $0000)
%LyraCurrentIndexed(Lyra_ReadScrollNorth, $2891B8, !LYRA_CURRENT_TABLE_scroll_north+$0000, 1, $0140, $0180, $0000)
%LyraCurrentIndexed(Lyra_ReadScrollWest, $2892F8, !LYRA_CURRENT_TABLE_scroll_west+$0000, 1, $0140, $0180, $0000)
Oracle_Lyra_ReadPaletteSet:
%LyraCurrentIndexed(Lyra_ReadPaletteSet, $09C635, !LYRA_CURRENT_TABLE_palette_set+$0000, 0, $00A0, $00C0, $0000)
Oracle_Lyra_ReadSpritePalette:
%LyraCurrentSpriteIndexed(Lyra_ReadSpritePalette, $7EFD40, !LYRA_CURRENT_TABLE_special_sprite_palettes, !LYRA_CURRENT_TABLE_special_sprite_palettes_phase1, !LYRA_CURRENT_TABLE_special_sprite_palettes_phase2, $00A0, $00C0, $0000, 0)
%LyraCurrentSpriteIndexed(Lyra_ReadSpecialPalette, $02E701, !LYRA_CURRENT_TABLE_special_sprite_palettes, !LYRA_CURRENT_TABLE_special_sprite_palettes_phase1, !LYRA_CURRENT_TABLE_special_sprite_palettes_phase2, $0020, $0040, $0080, 1)
%LyraCurrentSpriteIndexed(Lyra_ReadSpecialSpriteGfx, $02E6E1, !LYRA_CURRENT_TABLE_special_sprite_gfx, !LYRA_CURRENT_TABLE_special_sprite_gfx_phase1, !LYRA_CURRENT_TABLE_special_sprite_gfx_phase2, $0020, $0040, $0080, 0)
%LyraCurrentSpriteIndexed(Lyra_ReadSpriteGfxByArea, $02E661, !LYRA_CURRENT_TABLE_special_sprite_gfx, !LYRA_CURRENT_TABLE_special_sprite_gfx_phase1, !LYRA_CURRENT_TABLE_special_sprite_gfx_phase2, $00A0, $00C0, $0000, 0)
%LyraCurrentIndexed(Lyra_ReadSpecialEntryGfx, $02E821, !LYRA_CURRENT_TABLE_special_entry_gfx+$0000, 0, $0020, $0040, $0080)
%LyraCurrentIndexed(Lyra_ReadAreaGfx, $00FC9C, !LYRA_CURRENT_TABLE_area_gfx+$0000, 0, $00A0, $00C0, $0000)
%LyraCurrentIndexed(Lyra_ReadBombDoor, $02A644, !LYRA_CURRENT_TABLE_bomb_doors+$0000, 0, $0140, $0180, $0000)
%LyraCurrentIndexed(Lyra_ReadHiddenItems, $82A784, !LYRA_CURRENT_TABLE_hidden_items+$0000, 0, $0140, $0180, $0000)
%LyraCurrentIndexed(Lyra_ReadSign, $2897F8, !LYRA_CURRENT_TABLE_sign_text+$0000, 1, $0140, $0180, $0000)
%LyraCurrentIndexed(Lyra_ReadGfx0, $288480, !LYRA_CURRENT_TABLE_gfx+$0000, 0, $0500, $0600, $0000)
%LyraCurrentIndexed(Lyra_ReadGfx1, $288481, !LYRA_CURRENT_TABLE_gfx+$0001, 0, $0500, $0600, $0000)
%LyraCurrentIndexed(Lyra_ReadGfx2, $288482, !LYRA_CURRENT_TABLE_gfx+$0002, 0, $0500, $0600, $0000)
%LyraCurrentIndexed(Lyra_ReadGfx3, $288483, !LYRA_CURRENT_TABLE_gfx+$0003, 0, $0500, $0600, $0000)
%LyraCurrentIndexed(Lyra_ReadGfx4, $288484, !LYRA_CURRENT_TABLE_gfx+$0004, 0, $0500, $0600, $0000)
%LyraCurrentIndexed(Lyra_ReadGfx5, $288485, !LYRA_CURRENT_TABLE_gfx+$0005, 0, $0500, $0600, $0000)
%LyraCurrentIndexed(Lyra_ReadGfx6, $288486, !LYRA_CURRENT_TABLE_gfx+$0006, 0, $0500, $0600, $0000)
%LyraCurrentIndexed(Lyra_ReadGfx7, $288487, !LYRA_CURRENT_TABLE_gfx+$0007, 0, $0500, $0600, $0000)
%LyraCurrentIndexed(Lyra_ReadMosaic, $288200, !LYRA_CURRENT_TABLE_mosaic, 0, $00A0, $00C0, $0000)
; These take map*2 WITHOUT a native direction*0140 folded into X.
; The root caller must retain direction before selecting one of four readers.
%LyraCurrentIndexed(Lyra_ReadByScreen1, $288A38, !LYRA_CURRENT_TABLE_ByScreen1, 0, $0140, $0180, $0000)
%LyraCurrentIndexed(Lyra_ReadByScreen2, $288B78, !LYRA_CURRENT_TABLE_ByScreen2, 0, $0140, $0180, $0000)
%LyraCurrentIndexed(Lyra_ReadByScreen3, $288CB8, !LYRA_CURRENT_TABLE_ByScreen3, 0, $0140, $0180, $0000)
%LyraCurrentIndexed(Lyra_ReadByScreen4, $288DF8, !LYRA_CURRENT_TABLE_ByScreen4, 0, $0140, $0180, $0000)

; OverworldHandleTransitions ABI: M16/X16, A=destination map*2,
; X=direction0/2/4/6. Keep the native direction index separate from map rows.
; Returns delta in A, preserves X/Y/D/DB and caller C/V; no scratch writes.
Lyra_ReadByScreen:
    PHP : REP #$30 : PHA : PHX
    CPX.w #$0002 : BEQ .left
    CPX.w #$0004 : BEQ .down
    CPX.w #$0006 : BEQ .up
    TAX : JSL Lyra_ReadByScreen1 : BRA .loaded
.left:
    TAX : JSL Lyra_ReadByScreen2 : BRA .loaded
.down:
    TAX : JSL Lyra_ReadByScreen3 : BRA .loaded
.up:
    TAX : JSL Lyra_ReadByScreen4
.loaded:
    STA $03,S : PLX : PLA : PLP : PHA : PLA : RTL
Lyra_ReadByScreen_End:

; M16/X16 original pointer ABI. Sub-overlays select their actual one-page
; request, independently of the map currently hosting the overlay.
macro LyraCurrentPointer(name, old, selected)
<name>:
    PHP
    TXA : CMP.w #(!LYRA_CURRENT_FIRST*3) : BCC ?legacy
    CMP.w #(!LYRA_CURRENT_END*3) : BCS ?legacy
    PLP
    LDA.l <selected>, X : STA.b $C8
    LDA.l <selected>+1, X : STA.b $C9
    RTL
?legacy:
    PLP
    LDA.l <old>, X : STA.b $C8
    LDA.l <old>+1, X : STA.b $C9
    RTL
<name>_End:
endmacro
%LyraCurrentPointer(Lyra_SubHigh, $02F94D, !LYRA_CURRENT_TABLE_map32_high)
%LyraCurrentPointer(Lyra_SubLow, $02FB2D, !LYRA_CURRENT_TABLE_map32_low)

; The native full loader ALWAYS requests8A+[0,1,8,9], even for small/wide/
; tall maps and atBF. Classify its BASE8A, then map the requested quadrant
; through the saved parent/size. Native00..9F loads retain their original
; operands even when an unused quadrant's request happens to reachA0+.
; Entry M16/X16; preserve X/Y/DBR/D/C/V, write onlyC8..CA, return pointer
; mid/bank in A and its N/Z exactly as the replaced second LDA.
macro LyraCurrentFullPointer(name, old, selected)
<name>:
    PHP : PHX : PHY
    LDA.b $8A : AND.w #$00FF
    CMP.w #!LYRA_CURRENT_FIRST : BCS ?upper
      BRL ?legacy
?upper:
    CMP.w #!LYRA_CURRENT_END : BCC ?tail
      BRL ?legacy
?tail:
    TAX
    LDA.l !LYRA_CURRENT_TABLE_parent, X : AND.w #$00FF : TAY
    LDA.l !LYRA_CURRENT_TABLE_area_size, X : AND.w #$00FF
    CMP.w #$0004 : BCC ?sizeValid
      BRL ?legacy
?sizeValid:
    PHA : PHX ; size, base area
    TXA : ASL : CLC : ADC $01,S : PHA ; base*3
    LDA $09,S : SEC : SBC $01,S ; original X minus base*3
    BEQ ?deltaReady
    CMP.w #$0003 : BEQ ?right
    CMP.w #$0018 : BEQ ?down
    CMP.w #$001B : BEQ ?downRight
      PLA : PLA : PLA
      BRL ?legacy
?right:
    LDA.w #$0001 : BRA ?deltaReady
?down:
    LDA.w #$0008 : BRA ?deltaReady
?downRight:
    LDA.w #$0009
?deltaReady:
    PHA ; quadrant delta
    LDA $07,S : ASL : TAX
    LDA.l ?quadMasks, X : AND $01,S : STA $01,S
    TYA : CLC : ADC $01,S : PHA ; parent + masked quadrant
    ASL : CLC : ADC $01,S : TAX ; resolved map*3
    PLA : PLA : PLA : PLA : PLA ; map, delta, base*3, area, size
    LDA.l <selected>, X : STA.b $C8
    LDA.l <selected>+1, X : STA.b $C9
    PLY : PLX : PLP : PHA : PLA : RTL
?legacy:
    PLY : PLX : PLP
    LDA.l <old>, X : STA.b $C8
    LDA.l <old>+1, X : STA.b $C9
    RTL
?quadMasks:
    dw $0000, $0009, $0001, $0008 ; small, large, wide, tall
<name>_End:
endmacro
%LyraCurrentFullPointer(Lyra_FullHigh, $02F94D, !LYRA_CURRENT_TABLE_map32_high)
%LyraCurrentFullPointer(Lyra_FullLow, $02FB2D, !LYRA_CURRENT_TABLE_map32_low)

; Original phase Y is 0/2 (phase0),4 (phase1),6 (phase2).
; Each relocated phase has a complete192-row extent, never a native160 stride.
Lyra_SpritePointer:
    PHP : REP #$30 : PHA : PHX
    LDA.w $040A : AND.w #$00FF
    CMP.w #!LYRA_CURRENT_FIRST : BCC .legacy
    CMP.w #!LYRA_CURRENT_END : BCS .legacy
    ASL : TAX
    CPY.w #$0004 : BEQ .phase1
    CPY.w #$0006 : BEQ .phase2
    LDA.l !LYRA_CURRENT_TABLE_sprite_phase0, X : BRA .loaded
.phase1:
    LDA.l !LYRA_CURRENT_TABLE_sprite_phase1, X : BRA .loaded
.phase2:
    LDA.l !LYRA_CURRENT_TABLE_sprite_phase2, X
.loaded:
    STA $03,S : PLX : PLA : PLP : PHA : PLA : RTL
.legacy:
    PLX : PLA : PLP
    LDA.l $289438, X : RTL
Lyra_SpritePointer_End:

; Enter M8/X16 with one inherited saved DB. Original initializer/storm writes
; the first160 cache bytes before this tail. Only A0..BF are filled here.
Lyra_InitMusicTail:
    PHP : REP #$30 : PHA : PHX : PHY
    SEP #$30
    JSL Oracle_CheckIfNight
    CMP.b #$01 : BEQ .phase1
    CMP.b #$02 : BEQ .phase2
    CMP.b #$03 : BCS .phase3
    REP #$10 : LDX.w #!LYRA_CURRENT_FIRST
.phase0Loop:
    LDA.l !LYRA_CURRENT_TABLE_music_phase0, X : STA.l $7EC900, X
    INX : CPX.w #!LYRA_CURRENT_END : BCC .phase0Loop
    BRA .done
.phase1:
    REP #$10 : LDX.w #!LYRA_CURRENT_FIRST
.phase1Loop:
    LDA.l !LYRA_CURRENT_TABLE_music_phase1, X : STA.l $7EC900, X
    INX : CPX.w #!LYRA_CURRENT_END : BCC .phase1Loop
    BRA .done
.phase2:
    REP #$10 : LDX.w #!LYRA_CURRENT_FIRST
.phase2Loop:
    LDA.l !LYRA_CURRENT_TABLE_music_phase2, X : STA.l $7EC900, X
    INX : CPX.w #!LYRA_CURRENT_END : BCC .phase2Loop
    BRA .done
.phase3:
    REP #$10 : LDX.w #!LYRA_CURRENT_FIRST
.phase3Loop:
    LDA.l !LYRA_CURRENT_TABLE_music_phase3, X : STA.l $7EC900, X
    INX : CPX.w #!LYRA_CURRENT_END : BCC .phase3Loop
.done:
    REP #$30 : PLY : PLX : PLA : PLP
    SEP #$10 : PLB : RTL
Lyra_InitMusicTail_End:

; Root supplies the original backdrop continuation label after its first
; five-byte LDA8A/AND00FF. No historical3483AA code origin is borrowed.
Lyra_ReadBackdrop:
    PHP : REP #$30 : PHA : PHX
    LDA.b $8A : AND.w #$00FF
    CMP.w #!LYRA_CURRENT_FIRST : BCC .legacy
    CMP.w #!LYRA_CURRENT_END : BCS .legacy
    ASL : TAX
    LDA.l !LYRA_CURRENT_TABLE_bg_color, X
    STA $03,S : PLX : PLA : PLP : PHA : PLA : RTL
.legacy:
    PLX : PLA : PLP
    LDA.b $8A : AND.w #$00FF
    JML Oracle_Lyra_CurrentBackdropLegacy
Lyra_ReadBackdrop_End:
if !LYRA_CURRENT_ACTORS_ENABLED == 1
  incsrc "lyra_actor_stream.asm"
endif
incsrc "lyra_tail_events.asm"

; Hookshot ABI is M16/X8: $0700 is the worldless true-cell*2, not $8A*2.
; Only A0..BF adds the page bits before widening X. Other maps retain the
; original index/table. PHX/PHP/PHA leaves saved P at3,S; LSR restores its C.
; After SBC, discard saved P and restore X8, then restore the result N/Z.
macro LyraHookshotSubtract(name, old, selected)
<name>:
    PHX : PHP : PHA
    LDA.b $8A : AND.w #$FFE0 : CMP.w #$00A0 : BNE ?legacy
    AND.w #$00C0 : ASL : ORA.w $0700
    REP #$10 : TAX
    LDA $03,S : LSR : PLA
    SBC.l <selected>, X
    SEP #$10 : PLX : PLX
    PHA : PLA : RTL
?legacy:
    LDA $03,S : LSR : PLA
    PLX : PLX
    SBC.l <old>, X
    RTL
<name>_End:
endmacro
%LyraHookshotSubtract(Lyra_HookshotSubtractY, $288F38, !LYRA_CURRENT_TABLE_transition_y)
%LyraHookshotSubtract(Lyra_HookshotSubtractX, $289078, !LYRA_CURRENT_TABLE_transition_x)
; M16/X16. Raw physical DP8A selects only full-word A0..BF, independently
; of parent040A. Restore P before the final bank load: C/V and all other
; flags survive except native LDA N/Z. A and DP02/03 hold the bank word;
; X/Y/DBR/D, DP00/04 and the stack retain their caller values.
if !LYRA_CURRENT_HIDDEN_STREAMS_BOUND == 1
Lyra_HiddenStreamsBank:
    PHP
    LDA.b $8A : AND.w #$FFE0 : CMP.w #$00A0 : BNE .native
    PLP : LDA.w #!LYRA_CURRENT_HIDDEN_STREAMS_BANK : STA.b $02 : RTL
.native:
    PLP : LDA.w #$009B : STA.b $02 : RTL
Lyra_HiddenStreamsBank_End:
endif
Lyra_CurrentNativeCodeEnd:
assert pc() <= !LYRA_CURRENT_CODE_END, "Current reader code exceeds explicit origin"
pullpc


; Fixed original-engine hook sites keep their original preimage assertions.
pushpc
if read4($02F59D) == $02F94DBF
  assert read4($02F5A3) == $02F94EBF, "Native pointer second read moved"
else
  assert read4($02F59D) == ((Lyra_FullHigh<<8)|$22), "Installed native reader call moved"
  assert read4($02F5A1) == $EAEAEAEA, "Installed native reader padding moved"
  assert read4($02F5A5) == $EAEAEAEA, "Installed native reader padding moved"
endif
org $02F59D ; @hook module=Overworld name=Lyra_FullHigh kind=jsl target=Lyra_FullHigh expected_m=16 expected_x=16
    JSL Lyra_FullHigh : NOP #8
assert pc() == $02F5A9
if read4($02F5C8) == $02FB2DBF
  assert read4($02F5CE) == $02FB2EBF, "Native pointer second read moved"
else
  assert read4($02F5C8) == ((Lyra_FullLow<<8)|$22), "Installed native reader call moved"
  assert read4($02F5CC) == $EAEAEAEA, "Installed native reader padding moved"
  assert read4($02F5D0) == $EAEAEAEA, "Installed native reader padding moved"
endif
org $02F5C8 ; @hook module=Overworld name=Lyra_FullLow kind=jsl target=Lyra_FullLow expected_m=16 expected_x=16
    JSL Lyra_FullLow : NOP #8
assert pc() == $02F5D4
if read4($02F7E3) == $02F94DBF
  assert read4($02F7E9) == $02F94EBF, "Native pointer second read moved"
else
  assert read4($02F7E3) == ((Lyra_SubHigh<<8)|$22), "Installed native reader call moved"
  assert read4($02F7E7) == $EAEAEAEA, "Installed native reader padding moved"
  assert read4($02F7EB) == $EAEAEAEA, "Installed native reader padding moved"
endif
org $02F7E3 ; @hook module=Overworld name=Lyra_SubHigh kind=jsl target=Lyra_SubHigh expected_m=16 expected_x=16
    JSL Lyra_SubHigh : NOP #8
assert pc() == $02F7EF
if read4($02F80E) == $02FB2DBF
  assert read4($02F814) == $02FB2EBF, "Native pointer second read moved"
else
  assert read4($02F80E) == ((Lyra_SubLow<<8)|$22), "Installed native reader call moved"
  assert read4($02F812) == $EAEAEAEA, "Installed native reader padding moved"
  assert read4($02F816) == $EAEAEAEA, "Installed native reader padding moved"
endif
org $02F80E ; @hook module=Overworld name=Lyra_SubLow kind=jsl target=Lyra_SubLow expected_m=16 expected_x=16
    JSL Lyra_SubLow : NOP #8
assert pc() == $02F81A
assert read4($02AC3C) == $02F88DBF || read4($02AC3C) == ((Lyra_ReadSize<<8)|$22), "Native size reader moved"
org $02AC3C ; @hook module=Overworld name=Lyra_Size02AC3C kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02AC6C) == $02F88DBF || read4($02AC6C) == ((Lyra_ReadSize<<8)|$22), "Native size reader moved"
org $02AC6C ; @hook module=Overworld name=Lyra_Size02AC6C kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02B2F3) == $02F88DBF || read4($02B2F3) == ((Lyra_ReadSize<<8)|$22), "Native size reader moved"
org $02B2F3 ; @hook module=Overworld name=Lyra_Size02B2F3 kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02B34F) == $02F88DBF || read4($02B34F) == ((Lyra_ReadSize<<8)|$22), "Native size reader moved"
org $02B34F ; @hook module=Overworld name=Lyra_Size02B34F kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02ED32) == $02F88DBF || read4($02ED32) == ((Lyra_ReadSize<<8)|$22), "Native size reader moved"
org $02ED32 ; @hook module=Overworld name=Lyra_Size02ED32 kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02ED66) == $02F88DBF || read4($02ED66) == ((Lyra_ReadSize<<8)|$22), "Native size reader moved"
org $02ED66 ; @hook module=Overworld name=Lyra_Size02ED66 kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02F035) == $02F88DBF || read4($02F035) == ((Lyra_ReadSize<<8)|$22), "Native size reader moved"
org $02F035 ; @hook module=Overworld name=Lyra_Size02F035 kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02F2E8) == $02F88DBF || read4($02F2E8) == ((Lyra_ReadSize<<8)|$22), "Native size reader moved"
org $02F2E8 ; @hook module=Overworld name=Lyra_Size02F2E8 kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02F31C) == $02F88DBF || read4($02F31C) == ((Lyra_ReadSize<<8)|$22), "Native size reader moved"
org $02F31C ; @hook module=Overworld name=Lyra_Size02F31C kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02F35A) == $02F88DBF || read4($02F35A) == ((Lyra_ReadSize<<8)|$22), "Native size reader moved"
org $02F35A ; @hook module=Overworld name=Lyra_Size02F35A kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02F394) == $02F88DBF || read4($02F394) == ((Lyra_ReadSize<<8)|$22), "Native size reader moved"
org $02F394 ; @hook module=Overworld name=Lyra_Size02F394 kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($1BC8B8) == $82A784BF || read4($1BC8B8) == ((Lyra_ReadHiddenItems<<8)|$22), "Hidden item directory moved"
org $1BC8B8 ; @hook module=Overworld name=Lyra_HiddenItems kind=jsl target=Lyra_ReadHiddenItems expected_m=16 expected_x=16
    JSL Lyra_ReadHiddenItems
; BEGIN CURRENT HIDDEN STREAM BANK HOOK
if !LYRA_CURRENT_HIDDEN_STREAMS_BOUND == 1
assert read3($1BC8BE) == $009BA9, "Hidden item native bank load moved"
assert read2($1BC8C1) == $0285, "Hidden item bank pointer store moved"
org $1BC8BE ; @hook module=Overworld name=Lyra_HiddenStreamsBank kind=jsl target=Lyra_HiddenStreamsBank expected_m=16 expected_x=16 protected_size=5
LyraCall_HiddenStreamsBank:
    JSL Lyra_HiddenStreamsBank : NOP
assert pc() == $1BC8C3
endif
; END CURRENT HIDDEN STREAM BANK HOOK
assert read4($02C4BC) == $6BAB10E2 || read4($02C4BC) == ((Lyra_InitMusicTail<<8)|$5C), "Music initializer tail moved"
org $02C4BC ; @hook module=Overworld name=Lyra_InitMusic kind=jml target=Lyra_InitMusicTail expected_m=8 expected_x=16
    JML Lyra_InitMusicTail
pullpc

pushpc
assert read4($02B0F5) == $7EFD40BF || read4($02B0F5) == ((Lyra_ReadSpritePalette<<8)|$22), "Native sprite palette cache reader moved"
org $02B0F5 ; @hook module=Overworld name=Lyra_SpritePal02B0F5 kind=jsl target=Lyra_ReadSpritePalette
    JSL Lyra_ReadSpritePalette
assert read4($02B38B) == $7EFD40BF || read4($02B38B) == ((Lyra_ReadSpritePalette<<8)|$22), "Native sprite palette cache reader moved"
org $02B38B ; @hook module=Overworld name=Lyra_SpritePal02B38B kind=jsl target=Lyra_ReadSpritePalette
    JSL Lyra_ReadSpritePalette
assert read4($02B4C7) == $7EFD40BF || read4($02B4C7) == ((Lyra_ReadSpritePalette<<8)|$22), "Native sprite palette cache reader moved"
org $02B4C7 ; @hook module=Overworld name=Lyra_SpritePal02B4C7 kind=jsl target=Lyra_ReadSpritePalette
    JSL Lyra_ReadSpritePalette
assert read4($02EAA5) == $7EFD40BF || read4($02EAA5) == ((Lyra_ReadSpritePalette<<8)|$22), "Native sprite palette cache reader moved"
org $02EAA5 ; @hook module=Overworld name=Lyra_SpritePal02EAA5 kind=jsl target=Lyra_ReadSpritePalette
    JSL Lyra_ReadSpritePalette
assert read4($02ECE2) == $7EFD40BF || read4($02ECE2) == ((Lyra_ReadSpritePalette<<8)|$22), "Native sprite palette cache reader moved"
org $02ECE2 ; @hook module=Overworld name=Lyra_SpritePal02ECE2 kind=jsl target=Lyra_ReadSpritePalette
    JSL Lyra_ReadSpritePalette
pullpc

pushpc
org Oracle_ReadOverworldBackdropColor ; @manifest-org-bank=$34
    JML Lyra_ReadBackdrop : NOP
assert pc() == Oracle_Lyra_CurrentBackdropLegacy
pullpc
