; D8 Farore graphics and bounded presence/recovery prototype. No new animation.
; Private prototype: flag 0 emits no hooks, code or blob.
; Slot $3A9800-$3A9FFF granted by Root; mask code bounds tighten only when on.
; Native conversion fills the transition buffer before overlay. Full-load
; callers own forced blank; additionally refuse DMA unless shadow $13 says blank.
; No $0412, LASTSPRSET, global sheet ID, direct CGRAM or saved-state writes.
if !ENABLE_D8_FARORE_GRAPHICS == 1
pushpc
assert read1($01B63A) == $BF && read3($01B63B) == $0ED463, "Farore palette header preimage changed"
assert read1($01B63E) == $8D && read2($01B63F) == $0AAE, "Farore palette store changed"
org $01B63A ; @hook module=Sprites name=D8Farore_HeaderPalette kind=jsl target=D8Farore_HeaderPalette expected_m=8 expected_x=16 expected_exit_m=8 expected_exit_x=16
  JSL D8Farore_HeaderPalette : NOP #3
assert pc() == $01B641, "Farore header overlaps WallSel_HeaderGfx"
assert read1($028A97) == $22 && read3($028A98) == $00E031, "Farore transition preimage changed"
org $028A97 ; @hook module=Sprites name=D8Farore_Transition028A97 kind=jsl target=D8Farore_LoadSet expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JSL D8Farore_LoadSet
assert read1($028D10) == $22 && read3($028D11) == $00E031, "Farore transition preimage changed"
org $028D10 ; @hook module=Sprites name=D8Farore_Transition028D10 kind=jsl target=D8Farore_LoadSet expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JSL D8Farore_LoadSet
assert read1($0294E6) == $22 && read3($0294E7) == $00E031, "Farore transition preimage changed"
org $0294E6 ; @hook module=Sprites name=D8Farore_Transition0294E6 kind=jsl target=D8Farore_LoadSet expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JSL D8Farore_LoadSet
assert read1($028286) == $22 && read3($028287) == $00E19B, "Farore full-load preimage changed"
org $028286 ; @hook module=Sprites name=D8Farore_Full028286 kind=jsl target=D8Farore_InitializeTilesets expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JSL D8Farore_InitializeTilesets
assert read1($029BA7) == $22 && read3($029BA8) == $00E19B, "Farore full-load preimage changed"
org $029BA7 ; @hook module=Sprites name=D8Farore_Full029BA7 kind=jsl target=D8Farore_InitializeTilesets expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JSL D8Farore_InitializeTilesets

; Closing the dungeon map also reloads room graphics. Its prior step owns
; forced blank ($0EDA3B), so use the same guarded full-load wrapper.
assert read1($0AEF48) == $22 && read3($0AEF49) == $00E19B, "Farore map-return preimage changed"
org $0AEF48 ; @hook module=Sprites name=D8Farore_MapReturn kind=jsl target=D8Farore_InitializeTilesets expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JSL D8Farore_InitializeTilesets

org $3A9800
D8Farore_GraphicsStart:
; Carry is membership; all other P bits, A (including B), X/Y/DBR preserved.
; Full 16-bit room check prevents $0190 aliasing $0090. DP is untouched.
D8Farore_IsMember:
{
  PHP : REP #$20 : PHA
  SEP #$20
  LDA.l $7E001B : BEQ .no
  LDA.l $7EF37A : AND.b #$80 : BNE .no
  REP #$20
  LDA.l $7E00A0
  CMP.w #$0090 : BCC .no
  CMP.w #$0096 : BCC .yes
  CMP.w #$00A0 : BEQ .yes
  CMP.w #$00A6 : BEQ .yes
  CMP.w #$00A7 : BEQ .yes
  CMP.w #$00B0 : BEQ .yes
.no
  REP #$20 : PLA : PLP : CLC : RTL
.yes
  REP #$20 : PLA : PLP : SEC : RTL
}

; Header ABI M8/X16. Original aux2 load remains exact for every nonmember.
; Only OBJ6 colors1..7 are selected here. $0AB1 owns colors9..15/pots.
D8Farore_HeaderPalette:
{
  LDA.l $0ED463,X : STA.w $0AAE
  PHP : PHA
  JSL D8Farore_IsMember : BCC .done
  LDA.b #$03 : STA.w $0AAE
.done
  PLA : PLP : RTL
}

; Native caller always runs first. Return its complete CPU state.
D8Farore_LoadSet:
  JSL $00E031
D8Farore_OverlayBuffer:
{
  PHP : REP #$30 : PHA : PHX : PHY
  JSL D8Farore_IsMember : BCS .copy
  JMP .done
.copy
  LDX.w #$003E
.row0
  LDA.l D8Farore_Tiles+$0000,X : STA.l $7F1500,X
  DEX : DEX : BPL .row0
  LDX.w #$003E
.row1
  LDA.l D8Farore_Tiles+$0040,X : STA.l $7F1700,X
  DEX : DEX : BPL .row1
  LDX.w #$003E
.row2
  LDA.l D8Farore_Tiles+$0080,X : STA.l $7F1540,X
  DEX : DEX : BPL .row2
  LDX.w #$003E
.row3
  LDA.l D8Farore_Tiles+$00C0,X : STA.l $7F1740,X
  DEX : DEX : BPL .row3
  LDX.w #$003E
.row4
  LDA.l D8Farore_Tiles+$0100,X : STA.l $7F1580,X
  DEX : DEX : BPL .row4
  LDX.w #$003E
.row5
  LDA.l D8Farore_Tiles+$0140,X : STA.l $7F1780,X
  DEX : DEX : BPL .row5
  LDX.w #$003E
.row6
  LDA.l D8Farore_Tiles+$0180,X : STA.l $7F1000,X
  DEX : DEX : BPL .row6
  LDX.w #$003E
.row7
  LDA.l D8Farore_Tiles+$01C0,X : STA.l $7F1200,X
  DEX : DEX : BPL .row7
  LDX.w #$003E
.row8
  LDA.l D8Farore_Tiles+$0200,X : STA.l $7F1040,X
  DEX : DEX : BPL .row8
  LDX.w #$003E
.row9
  LDA.l D8Farore_Tiles+$0240,X : STA.l $7F1240,X
  DEX : DEX : BPL .row9
  LDX.w #$003E
.row10
  LDA.l D8Farore_Tiles+$0280,X : STA.l $7F1080,X
  DEX : DEX : BPL .row10
  LDX.w #$003E
.row11
  LDA.l D8Farore_Tiles+$02C0,X : STA.l $7F1280,X
  DEX : DEX : BPL .row11
  LDX.w #$003E
.row12
  LDA.l D8Farore_Tiles+$0300,X : STA.l $7F1400,X
  DEX : DEX : BPL .row12
  LDX.w #$003E
.row13
  LDA.l D8Farore_Tiles+$0340,X : STA.l $7F1600,X
  DEX : DEX : BPL .row13
.done
  PLY : PLX : PLA : PLP : RTL
}

D8Farore_InitializeTilesets:
  JSL $00E19B
D8Farore_OverlayVram:
{
  PHP : REP #$30 : PHA : PHX : PHY
  JSL D8Farore_IsMember : BCC .done
  SEP #$20
  LDA.l $7E0013 : AND.b #$80 : BEQ .done
  LDA.l $7E009B : AND.b #$01 : BNE .done ; channel0 cannot also own HDMA
  ; InitializeTilesets leaves VMAIN=$80; native NMI rebuilds DMA0MODE
  ; and source/destination before each upload ($0089EF onward). Channel0
  ; is scratch here, with HDMA0 refused above. Do not blank
  ; the display or touch HDMA/NMI enable; the enclosing module owns both.
  LDA.b #$80 : STA.l $002115
  LDA.b #D8Farore_Tiles>>16 : STA.l $004304
  REP #$20
  LDA.w #$1801 : STA.l $004300
  LDX.w #$0000 : LDY.w #$0000
.row
  LDA.l D8Farore_VramRows,X : STA.l $002116
  TYA : CLC : ADC.w #D8Farore_Tiles : STA.l $004302
  LDA.w #$0040 : STA.l $004305
  SEP #$20
  LDA.b #$01 : STA.l $00420B
  REP #$20
  TYA : CLC : ADC.w #$0040 : TAY
  INX : INX : CPX.w #$001C : BNE .row
.done
  REP #$30 : PLY : PLX : PLA : PLP : RTL
}

; M8, A=original char/property, preserves P/X/Y/DBR. These are draw helpers,
; not a replacement for the future D8 companion dispatcher.
D8Farore_RemapTile:
{
  PHP
  JSL D8Farore_IsMember : BCC .done
  CMP.b #$86 : BNE .next88
  LDA.b #$80 : BRA .done
.next88
  CMP.b #$88 : BNE .next8A
  LDA.b #$82 : BRA .done
.next8A
  CMP.b #$8A : BNE .next8C
  LDA.b #$84 : BRA .done
.next8C
  CMP.b #$8C : BNE .done
  LDA.b #$A0
.done
  PLP : RTL
}
D8Farore_RemapPalette:
{
  PHP
  JSL D8Farore_IsMember : BCC .done
  AND.b #$F1 : ORA.b #$0C ; OBJ6, preserve priority, flips and page1
.done
  PLP : RTL
}

D8Farore_VramRows:
  dw $5A80,$5B80,$5AA0,$5BA0,$5AC0,$5BC0,$5800,$5900,$5820,$5920,$5840,$5940,$5A00,$5B00
D8Farore_Tiles:
  incbin "Sprites/NPCs/Data/farore_d8_low.4bpp"
assert pc()-D8Farore_Tiles == $0380, "Farore must contain exactly28 Tile8"
D8Farore_GraphicsEnd:
incsrc "Sprites/NPCs/farore_d8_companion.asm"
D8Farore_SupportEnd:
assert pc() <= $3AA000, "Farore support exceeds granted2KiB slot"
pullpc
endif
