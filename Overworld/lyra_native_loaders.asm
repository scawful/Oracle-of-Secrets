; Ordinary selected-project native loaders. Global ZSOW namespace.
; Included late, after ZSOW, source sheet overrides, and prepared data.
; Exact A1 selectors only: unselected maps retain their original readers.
assert !LYRA_PROJECT_DATA_PRESENT == 1
assert !LYRA_NATIVE_A1_ENABLED == 1
assert !LYRA_A1_ID == $A1
assert !LYRA_RUNTIME_TABLE_BASE == $28C000
assert !LYRA_RUNTIME_CODE_BASE == $F8C000
assert Lyra_A1Descriptor == $F8DFC0

; Original M/X/C/V, D/DB/X/Y and hidden B survive until the final LDA.
; Its A and N/Z outputs match the replaced byte/word load.
macro LyraReadX(name, old, selected, mask, index)
<name>:
    PHP : REP #$30 : PHA
    TXA : AND.w #<mask> : CMP.w #<index> : BNE ?legacy
    PLA : PLP
    LDA.l <selected>
    RTL
?legacy:
    PLA : PLP
    LDA.l <old>, X
    RTL
<name>_End:
endmacro

; Y-indexed original callers have established DB=$28.
macro LyraReadY(name, old, selected, mask, index)
<name>:
    PHP : REP #$30 : PHA
    TYA : AND.w #<mask> : CMP.w #<index> : BNE ?legacy
    PLA : PLP
    LDA.l <selected>
    RTL
?legacy:
    PLA : PLP
    LDA.w <old>, Y
    RTL
<name>_End:
endmacro

; Graphics X is a verified byte-area*8 plus a slot0..7, not just row base.
macro LyraReadGfx(name, old, selected)
<name>:
    PHP : REP #$30 : PHA
    TXA : AND.w #$07F8 : CMP.w #$0508 : BNE ?legacy
    PLA : PLP
    LDA.l <selected>, X
    RTL
?legacy:
    PLA : PLP
    LDA.l <old>, X
    RTL
<name>_End:
endmacro

pushpc
org !LYRA_RUNTIME_CODE_BASE
Lyra_NativeCodeStart:
%LyraReadX(Lyra_ReadAnimated, $2882A0, !LYRA_TABLE_animated+$00A1, $00FF, $00A1)
%LyraReadX(Lyra_ReadMainPalette, $288160, !LYRA_TABLE_main_palette+$00A1, $00FF, $00A1)
%LyraReadX(Lyra_ReadOverlay, $288340, !LYRA_TABLE_overlay+$0142, $01FF, $0142)
%LyraReadX(Lyra_ReadSize, $02F88D, !LYRA_TABLE_area_size+$00A1, $00FF, $00A1)
Oracle_Lyra_ReadParent:
%LyraReadX(Lyra_ReadParent, $288998, !LYRA_TABLE_parent+$00A1, $00FF, $00A1)
%LyraReadX(Lyra_ReadTransitionYX, $288F38, !LYRA_TABLE_transition_y+$0142, $01FF, $0142)
%LyraReadX(Lyra_ReadTransitionXX, $289078, !LYRA_TABLE_transition_x+$0142, $01FF, $0142)
%LyraReadY(Lyra_ReadTransitionYY, $288F38, !LYRA_TABLE_transition_y+$0142, $01FF, $0142)
%LyraReadY(Lyra_ReadTransitionXY, $289078, !LYRA_TABLE_transition_x+$0142, $01FF, $0142)
%LyraReadY(Lyra_ReadScrollNorth, $2891B8, !LYRA_TABLE_scroll_north+$0142, $01FF, $0142)
%LyraReadY(Lyra_ReadScrollWest, $2892F8, !LYRA_TABLE_scroll_west+$0142, $01FF, $0142)
Oracle_Lyra_ReadPaletteSet:
%LyraReadX(Lyra_ReadPaletteSet, $09C635, !LYRA_TABLE_palette_set+$00A1, $00FF, $00A1)
Oracle_Lyra_ReadSpritePalette:
%LyraReadX(Lyra_ReadSpritePalette, $7EFD40, !LYRA_TABLE_special_sprite_palettes+$0021, $00FF, $00A1)
%LyraReadX(Lyra_ReadSpecialPalette, $02E701, !LYRA_TABLE_special_sprite_palettes+$0021, $00FF, $0021)
%LyraReadX(Lyra_ReadSpecialSpriteGfx, $02E6E1, !LYRA_TABLE_special_sprite_gfx+$0021, $00FF, $0021)
%LyraReadX(Lyra_ReadSpriteGfxByArea, $02E661, !LYRA_TABLE_special_sprite_gfx+$0021, $00FF, $00A1)
%LyraReadX(Lyra_ReadSpecialEntryGfx, $02E821, !LYRA_TABLE_special_entry_gfx+$0021, $00FF, $0021)
%LyraReadX(Lyra_ReadAreaGfx, $00FC9C, !LYRA_TABLE_area_gfx+$00A1, $00FF, $00A1)
%LyraReadX(Lyra_ReadBombDoor, $02A644, !LYRA_TABLE_bomb_doors+$0142, $01FF, $0142)
%LyraReadX(Lyra_ReadHiddenItems, $82A784, !LYRA_TABLE_hidden_items+$0142, $01FF, $0142)
%LyraReadY(Lyra_ReadSign, $2897F8, !LYRA_TABLE_sign_text+$0142, $01FF, $0142)
%LyraReadGfx(Lyra_ReadGfx0, $288480, !LYRA_TABLE_gfx+0)
%LyraReadGfx(Lyra_ReadGfx1, $288481, !LYRA_TABLE_gfx+1)
%LyraReadGfx(Lyra_ReadGfx2, $288482, !LYRA_TABLE_gfx+2)
%LyraReadGfx(Lyra_ReadGfx3, $288483, !LYRA_TABLE_gfx+3)
%LyraReadGfx(Lyra_ReadGfx4, $288484, !LYRA_TABLE_gfx+4)
%LyraReadGfx(Lyra_ReadGfx5, $288485, !LYRA_TABLE_gfx+5)
%LyraReadGfx(Lyra_ReadGfx6, $288486, !LYRA_TABLE_gfx+6)
%LyraReadGfx(Lyra_ReadGfx7, $288487, !LYRA_TABLE_gfx+7)

; M16/X16. Preserve all original pointer-read outputs and caller state.
macro LyraPointer(name, old, selected)
<name>:
    PHP
    LDA.b $8A : AND.w #$00FF : CMP.w #$00A1 : BNE ?legacy
    PLP
    LDA.l <selected>+$01E3 : STA.b $C8
    LDA.l <selected>+$01E4 : STA.b $C9
    RTL
?legacy:
    PLP
    LDA.l <old>, X : STA.b $C8
    LDA.l <old>+1, X : STA.b $C9
    RTL
<name>_End:
endmacro
%LyraPointer(Lyra_FullHigh, $02F94D, !LYRA_TABLE_map32_high)
%LyraPointer(Lyra_FullLow, $02FB2D, !LYRA_TABLE_map32_low)
%LyraPointer(Lyra_SubHigh, $02F94D, !LYRA_TABLE_map32_high)
%LyraPointer(Lyra_SubLow, $02FB2D, !LYRA_TABLE_map32_low)

; M16/X16 at source sprite pointer load. Y is retained phase*2.
Lyra_SpritePointer:
    PHP : PHA
    LDA.w $040A : AND.w #$00FF : CMP.w #$00A1 : BNE .legacy
    CPY.w #$0004 : BEQ .phase1
    CPY.w #$0006 : BEQ .phase2
    PLA : PLP
    LDA.l !LYRA_TABLE_sprite_phase0+$0142
    RTL
.phase1:
    PLA : PLP
    LDA.l !LYRA_TABLE_sprite_phase1+$0142
    RTL
.phase2:
    PLA : PLP
    LDA.l !LYRA_TABLE_sprite_phase2+$0142
    RTL
.legacy:
    PLA : PLP
    LDA.l $289438, X
    RTL
Lyra_SpritePointer_End:

; Inherited AdjustOverworldAmbiance tail: M8/X16, one saved DB on stack.
; The storm producer already ran. Do not add a PHP/PHB frame here.
Lyra_InitMusicTail:
    LDA.l !LYRA_TABLE_music_dark_special+$0061
    STA.l $7EC9A1
    SEP #$10
    PLB
    RTL
Lyra_InitMusicTail_End:

; M16/X16 backdrop entry. Legacy tail remains at its reviewed address.
Lyra_ReadBackdrop:
    PHP
    LDA.b $8A : AND.w #$00FF : CMP.w #$00A1 : BNE .legacy
    PLP
    LDA.l !LYRA_TABLE_bg_color+$0142
    RTL
.legacy:
    PLP
    LDA.b $8A : AND.w #$00FF
    JML $3483AF
Lyra_ReadBackdrop_End:

; Explicit bridges for calls assembled inside namespace Oracle.

Lyra_NativeCodeEnd:
assert pc() <= $F8DFC0, "Native loader code collides with descriptor"
pullpc

; Zero-byte runtime fixture observations. These do not install an entry route.
Lyra_Fixture_PreProfile = $02E58B

pushpc
assert read4($02F59D) == $02F94DBF, "Native pointer preimage moved"
assert read4($02F5A3) == $02F94EBF, "Native pointer second read moved"
org $02F59D ; @hook module=Overworld name=Lyra_FullHigh kind=jsl target=Lyra_FullHigh expected_m=16 expected_x=16
    JSL Lyra_FullHigh : NOP #8
assert pc() == $02F5A9
assert read4($02F5C8) == $02FB2DBF, "Native pointer preimage moved"
assert read4($02F5CE) == $02FB2EBF, "Native pointer second read moved"
org $02F5C8 ; @hook module=Overworld name=Lyra_FullLow kind=jsl target=Lyra_FullLow expected_m=16 expected_x=16
    JSL Lyra_FullLow : NOP #8
assert pc() == $02F5D4
assert read4($02F7E3) == $02F94DBF, "Native pointer preimage moved"
assert read4($02F7E9) == $02F94EBF, "Native pointer second read moved"
org $02F7E3 ; @hook module=Overworld name=Lyra_SubHigh kind=jsl target=Lyra_SubHigh expected_m=16 expected_x=16
    JSL Lyra_SubHigh : NOP #8
assert pc() == $02F7EF
assert read4($02F80E) == $02FB2DBF, "Native pointer preimage moved"
assert read4($02F814) == $02FB2EBF, "Native pointer second read moved"
org $02F80E ; @hook module=Overworld name=Lyra_SubLow kind=jsl target=Lyra_SubLow expected_m=16 expected_x=16
    JSL Lyra_SubLow : NOP #8
assert pc() == $02F81A
assert read4($02AC3C) == $02F88DBF, "Native size reader moved"
org $02AC3C ; @hook module=Overworld name=Lyra_Size02AC3C kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02AC6C) == $02F88DBF, "Native size reader moved"
org $02AC6C ; @hook module=Overworld name=Lyra_Size02AC6C kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02B2F3) == $02F88DBF, "Native size reader moved"
org $02B2F3 ; @hook module=Overworld name=Lyra_Size02B2F3 kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02B34F) == $02F88DBF, "Native size reader moved"
org $02B34F ; @hook module=Overworld name=Lyra_Size02B34F kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02ED32) == $02F88DBF, "Native size reader moved"
org $02ED32 ; @hook module=Overworld name=Lyra_Size02ED32 kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02ED66) == $02F88DBF, "Native size reader moved"
org $02ED66 ; @hook module=Overworld name=Lyra_Size02ED66 kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02F035) == $02F88DBF, "Native size reader moved"
org $02F035 ; @hook module=Overworld name=Lyra_Size02F035 kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02F2E8) == $02F88DBF, "Native size reader moved"
org $02F2E8 ; @hook module=Overworld name=Lyra_Size02F2E8 kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02F31C) == $02F88DBF, "Native size reader moved"
org $02F31C ; @hook module=Overworld name=Lyra_Size02F31C kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02F35A) == $02F88DBF, "Native size reader moved"
org $02F35A ; @hook module=Overworld name=Lyra_Size02F35A kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($02F394) == $02F88DBF, "Native size reader moved"
org $02F394 ; @hook module=Overworld name=Lyra_Size02F394 kind=jsl target=Lyra_ReadSize
    JSL Lyra_ReadSize
assert read4($1BC8B8) == $82A784BF, "Hidden item directory moved"
org $1BC8B8 ; @hook module=Overworld name=Lyra_HiddenItems kind=jsl target=Lyra_ReadHiddenItems expected_m=16 expected_x=16
    JSL Lyra_ReadHiddenItems
assert read4($02C4BC) == $6BAB10E2, "Music initializer tail moved"
org $02C4BC ; @hook module=Overworld name=Lyra_InitMusic kind=jml target=Lyra_InitMusicTail expected_m=8 expected_x=16
    JML Lyra_InitMusicTail
pullpc

pushpc
assert read4($02B0F5) == $7EFD40BF, "Native sprite palette cache reader moved"
org $02B0F5 ; @hook module=Overworld name=Lyra_SpritePal02B0F5 kind=jsl target=Lyra_ReadSpritePalette
    JSL Lyra_ReadSpritePalette
assert read4($02B38B) == $7EFD40BF, "Native sprite palette cache reader moved"
org $02B38B ; @hook module=Overworld name=Lyra_SpritePal02B38B kind=jsl target=Lyra_ReadSpritePalette
    JSL Lyra_ReadSpritePalette
assert read4($02B4C7) == $7EFD40BF, "Native sprite palette cache reader moved"
org $02B4C7 ; @hook module=Overworld name=Lyra_SpritePal02B4C7 kind=jsl target=Lyra_ReadSpritePalette
    JSL Lyra_ReadSpritePalette
assert read4($02EAA5) == $7EFD40BF, "Native sprite palette cache reader moved"
org $02EAA5 ; @hook module=Overworld name=Lyra_SpritePal02EAA5 kind=jsl target=Lyra_ReadSpritePalette
    JSL Lyra_ReadSpritePalette
assert read4($02ECE2) == $7EFD40BF, "Native sprite palette cache reader moved"
org $02ECE2 ; @hook module=Overworld name=Lyra_SpritePal02ECE2 kind=jsl target=Lyra_ReadSpritePalette
    JSL Lyra_ReadSpritePalette
pullpc

pushpc
assert Oracle_ReadOverworldBackdropColor == $3483AA, "Backdrop source entry moved"
org $3483AA ; @hook module=Overworld name=Lyra_Backdrop kind=jml target=Lyra_ReadBackdrop expected_m=16 expected_x=16
    JML Lyra_ReadBackdrop : NOP
pullpc
Lyra_Fixture_FullHighReturned = $02F5A1
Lyra_Fixture_FullLowReturned = $02F5CC
Lyra_Fixture_SubHighReturned = $02F7E7
Lyra_Fixture_SubLowReturned = $02F812
