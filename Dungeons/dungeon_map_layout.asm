; Optional D8-only six-column pause map. The descriptor is authored ROM data;
; this file validates it but never emits or repairs it. All other dungeons use
; the original five-column code. Bank $52 is NOT a low-WRAM mirror: DBR remains
; $0A, and every table introduced here is read with long addressing.
incsrc "Config/dungeon_map_layout.asm"

!DungeonMapSixPresent #= 0
if read1(!DUNGEON_MAP_LAYOUT, $100) != $100
  !DungeonMapAllZero #= 1
  !DungeonMapAllFF #= 1
  !DungeonMapByte #= 0
  while !DungeonMapByte < !DUNGEON_MAP_LAYOUT_SIZE
    if read1(!DUNGEON_MAP_LAYOUT+!DungeonMapByte, $100) != $00
      !DungeonMapAllZero #= 0
    endif
    if read1(!DUNGEON_MAP_LAYOUT+!DungeonMapByte, $100) != $FF
      !DungeonMapAllFF #= 0
    endif
    !DungeonMapByte #= !DungeonMapByte+1
  endwhile
  if !DungeonMapAllZero == 0 && !DungeonMapAllFF == 0
    assert read1(!DUNGEON_MAP_LAYOUT+$1F, $100) != $100, "Truncated dungeon map layout descriptor"
    assert read4(!DUNGEON_MAP_LAYOUT) == $44534F4F, "Invalid dungeon map layout magic"
    assert read4(!DUNGEON_MAP_LAYOUT+4) == $0050414D, "Invalid dungeon map layout magic"
    assert read1(!DUNGEON_MAP_LAYOUT+8) == 1, "Unsupported dungeon map layout version"
    assert read1(!DUNGEON_MAP_LAYOUT+9) == 14, "Dungeon map layout requires fourteen slots"
    assert read1(!DUNGEON_MAP_LAYOUT+10) == 5, "Dungeon map layout requires five rows"
    assert read1(!DUNGEON_MAP_LAYOUT+11) == 0, "Dungeon map layout reserved byte is nonzero"
    !DungeonMapByte #= 0
    while !DungeonMapByte < 14
      if !DungeonMapByte == 2
        assert read1(!DUNGEON_MAP_LAYOUT+12+!DungeonMapByte) == 6, "D8 layout requires six columns"
      else
        assert read1(!DUNGEON_MAP_LAYOUT+12+!DungeonMapByte) == 5, "Only D8 may use six columns"
      endif
      !DungeonMapByte #= !DungeonMapByte+1
    endwhile
    while !DungeonMapByte < 20
      assert read1(!DUNGEON_MAP_LAYOUT+12+!DungeonMapByte) == 0, "Dungeon map layout reserved bytes are nonzero"
      !DungeonMapByte #= !DungeonMapByte+1
    endwhile
    !DungeonMapSixPresent #= 1
    assert !ENABLE_D8_SIX_COLUMN_MAP == 1, "Six-column authored dungeon map requires its runtime feature"
  endif
endif

; Every build consumes an unpatched authoring ROM. Require original bytes in
; all modes: a compiled six-column input is not an accepted build source, and
; removing its descriptor must not retain stale installed hooks. These spans
; exclude the four shared expanded-template hooks at E652/6B6/71A/77E.
assert read4($0AE44F) == $18E431B9, "Dungeon map requires original corner reader"
assert read4($0AE49E) == $14C902A5, "Dungeon map requires original border width"
assert read1($0AE4A2) == $00, "Dungeon map border width continuation changed"
assert read4($0AE4B1) == $18E445B9, "Dungeon map requires original side reader"
assert read4($0AE5C7) == $9A7D02A5, "Dungeon map requires original row reader"
assert read1($0AE5CB) == $E5, "Dungeon map row reader continuation changed"
assert read4($0AE5E7) == $18F5F5B9, "Dungeon map requires original floor reader"
assert read4($0AE5F0) == $0FC90CB1, "Dungeon map requires original room reader"
assert read4($0AE7E8) == $05C902A5, "Dungeon map requires original column limit"
assert read1($0AE7EC) == $00, "Dungeon map column limit continuation changed"
assert read4($0AE823) == $C2AB4B8B, "Dungeon map requires original marker entry"
assert read1($0AE827) == $10, "Dungeon map marker entry continuation changed"
assert read4($0AEB50) == $00A900A6, "Dungeon map requires original blinking marker"
assert read4($0AEBA8) == $00A503A0, "Dungeon map requires original location marker"

if !ENABLE_D8_SIX_COLUMN_MAP == 1 && !DungeonMapSixPresent == 1
assert !DUNGEON_MAP_CODE == $52E000, "Dungeon map code contract moved"
assert !DUNGEON_MAP_CODE_END == $52F000, "Dungeon map code boundary moved"
!DungeonMapSixFloorCount #= (read1($0AF5DD)&$0F)+(read1($0AF5DD)>>4)
assert !DungeonMapSixFloorCount > 0, "D8 grid requires at least one floor"
assert !DungeonMapSixFloorCount <= 16, "D8 grid supports at most sixteen floors"


pushpc
org $0AE44F ; @hook module=Dungeons name=DungeonMapSix_Corners kind=jsl target=DungeonMapSix_Corners expected_m=16 expected_x=16
  JSL DungeonMapSix_Corners
  assert pc() == $0AE453
org $0AE49E ; @hook module=Dungeons name=DungeonMapSix_BorderWidth kind=jsl target=DungeonMapSix_BorderWidth expected_m=16 expected_x=16
  JSL DungeonMapSix_BorderWidth : NOP
  assert pc() == $0AE4A3
org $0AE4B1 ; @hook module=Dungeons name=DungeonMapSix_Sides kind=jsl target=DungeonMapSix_Sides expected_m=16 expected_x=16
  JSL DungeonMapSix_Sides
  assert pc() == $0AE4B5
org $0AE5C7 ; @hook module=Dungeons name=DungeonMapSix_RowIndex kind=jsl target=DungeonMapSix_RowIndex expected_m=16 expected_x=16
  JSL DungeonMapSix_RowIndex : NOP
  assert pc() == $0AE5CC
org $0AE5E7 ; @hook module=Dungeons name=DungeonMapSix_FloorOffset kind=jsl target=DungeonMapSix_FloorOffset expected_m=16 expected_x=16
  JSL DungeonMapSix_FloorOffset
  assert pc() == $0AE5EB
org $0AE5F0 ; @hook module=Dungeons name=DungeonMapSix_RoomByte kind=jsl target=DungeonMapSix_RoomByte expected_m=8 expected_x=16
  JSL DungeonMapSix_RoomByte
  assert pc() == $0AE5F4
org $0AE7E8 ; @hook module=Dungeons name=DungeonMapSix_Columns kind=jsl target=DungeonMapSix_Columns expected_m=16 expected_x=16
  JSL DungeonMapSix_Columns : NOP
  assert pc() == $0AE7ED
org $0AE823 ; @hook module=Dungeons name=DungeonMapSix_Markers kind=jml target=DungeonMapSix_Markers expected_m=8 expected_x=8
  JML DungeonMapSix_Markers : NOP
  assert pc() == $0AE828
org $0AEB50 ; @hook module=Dungeons name=DungeonMapSix_BlinkingMarker kind=jml target=DungeonMapSix_BlinkingMarker expected_m=8 expected_x=8
  JML DungeonMapSix_BlinkingMarker
  assert pc() == $0AEB54
org $0AEBA8 ; @hook module=Dungeons name=DungeonMapSix_LocationMarker kind=jml target=DungeonMapSix_LocationMarker expected_m=8 expected_x=8
  JML DungeonMapSix_LocationMarker
  assert pc() == $0AEBAC

org $52E000 ; @manifest-org-bank=$52
DungeonMapSix_CodeStart:

; Arithmetic JSL joins enter M/X=16, DBR=$0A, D unchanged. Preserve X/Y.
; Reproduce the displaced arithmetic/flags; in particular RowIndex retains
; the carry entering the original ADC. Do not use PHK/PLB in this ROM bank.
DungeonMapSix_Corners:
  PHX
  LDX.w $040C : CPX.w #$0004 : BNE .legacy
    TYX
    LDA.l DungeonMapSix_CornerOffsets, X
    PLX
    CLC
    RTL
  .legacy
  PLX
  LDA.w $E431, Y : CLC
  RTL

DungeonMapSix_Sides:
  PHX
  LDX.w $040C : CPX.w #$0004 : BNE .legacy
    TYX
    LDA.l DungeonMapSix_SideOffsets, X
    PLX
    CLC
    RTL
  .legacy
  PLX
  LDA.w $E445, Y : CLC
  RTL

DungeonMapSix_BorderWidth:
  PHX
  LDX.w $040C : CPX.w #$0004 : BNE .legacy
    PLX
    LDA.b $02 : CMP.w #$0018
    RTL
  .legacy
  PLX
  LDA.b $02 : CMP.w #$0014
  RTL

DungeonMapSix_RowIndex:
  PHP
  LDA.w $040C : CMP.w #$0004 : BNE .legacy
    PLP
    LDA.b $02 : ADC.l DungeonMapSix_RowOffsets, X
    RTL
  .legacy
  PLP
  LDA.b $02 : ADC.w $E59A, X
  RTL

DungeonMapSix_FloorOffset:
  PHX
  LDX.w $040C : CPX.w #$0004 : BNE .legacy
    TYX
    CPX.w #!DungeonMapSixFloorCount*2 : BCC .valid_floor
      LDA.w #$0000
      BRA .done
    .valid_floor
    LDA.l DungeonMapSix_FloorOffsets, X
    .done
    PLX
    CLC
    RTL
  .legacy
  PLX
  LDA.w $F5F5, Y : CLC
  RTL

; The native renderer can draw a second, nonexistent floor when there is only
; one floor. Bound the offset above, and supply empty cells without reading past
; the authored stream. $0E still holds the native floor index times two.
; M=8, X/Y=16; preserve the accumulator's hidden high byte and X/Y.
DungeonMapSix_RoomByte:
  PHP
  REP #$20
  PHA
  LDA.w $040C : CMP.w #$0004 : BNE .read
  LDA.b $0E : CMP.w #!DungeonMapSixFloorCount*2 : BCC .read
    PLA
    PLP
    LDA.b #$0F : CMP.b #$0F
    RTL
  .read
  PLA
  PLP
  LDA.b ($0C), Y : CMP.b #$0F
  RTL

DungeonMapSix_Columns:
  PHX
  LDX.w $040C : CPX.w #$0004 : BNE .legacy
    PLX
    LDA.b $02 : CMP.w #$0006
    RTL
  .legacy
  PLX
  LDA.b $02 : CMP.w #$0005
  RTL

; Original long-entry ABI: M/X=8; return through the unmodified bank0A tail
; (AE910..AE953), which restores DBR and RTLs to its original caller.
DungeonMapSix_Markers:
  PHP
  REP #$20
  PHA
  LDA.l $7E040C : CMP.w #$0004 : BEQ .six
    PLA
    PLP
    PHB
    PEA $0A0A : PLB : PLB
    REP #$10
    JML $0AE828
  .six
  PLA
  PLP
  PHB
  PEA $0A0A : PLB : PLB
  REP #$30
  STZ.b $00 : STZ.b $02
  LDX.w $040C
  LDA.w $F605, X : STA.b $04
  ; Sign-extend the actual floor (FF=B1) before adding the basement count.
  LDA.b $A4 : AND.w #$00FF : CMP.w #$0080 : BCC .floor_positive
    ORA.w #$FF00
  .floor_positive
  STA.b $0C
  LDA.w $F5D9, X : AND.w #$000F : CLC : ADC.b $0C
  CMP.w #!DungeonMapSixFloorCount : BCC .valid_link_floor
    BRL .missing_link
  .valid_link_floor
  ASL A : TAX
  LDA.l DungeonMapSix_FloorOffsets, X : TAY
  LDA.b $A0 : STA.b $0E
  AND.w #$FF00 : BNE .missing_link
  LDX.w #$001E
  SEP #$20
  .find_link
    LDA.b ($04), Y : CMP.b $0E : BEQ .found_link
    INY
    DEX : BEQ .missing_link
    LDA.b $00 : CMP.b #$50 : BCC .next_link_column
      STZ.b $00
      LDA.b $02 : CLC : ADC.b #$10 : STA.b $02
      BRA .find_link
    .next_link_column
    CLC : ADC.b #$10 : STA.b $00
    BRA .find_link
  .found_link
  REP #$20
  LDA.b $00 : CLC : ADC.w #$0090 : STA.w $0215
  LDA.b $22 : AND.w #$01E0 : ASL #3 : XBA
  CLC : ADC.w $0215 : STA.w $0215
  LDY.w $0211
  LDA.b $02 : STA.w $0CF5
  CLC : ADC.w $E7F3, Y : STA.w $0217
  LDA.b $20 : AND.w #$01E0 : ASL #3 : XBA
  CLC : ADC.w $0217 : STA.w $0217
  BRA .boss
  .missing_link
  REP #$20
  ; FFFF is a transient map-display sentinel only, never a saved room flag.
  LDA.w #$FFFF : STA.w $0215 : STA.w $0217
  STZ.w $0CF5

  .boss
  LDX.w $040C
  LDA.w $EE79, X : AND.w #$00FF : CMP.w #$0080 : BCC .boss_floor_positive
    ORA.w #$FF00
  .boss_floor_positive
  STA.b $0C
  LDA.w $F5D9, X : AND.w #$000F : CLC : ADC.b $0C
  CMP.w #!DungeonMapSixFloorCount : BCS .missing_boss
  ASL A : TAX
  LDA.l DungeonMapSix_FloorOffsets, X : STA.b $0C
  LDX.w $040C
  LDA.w $F605, X : CLC : ADC.b $0C : STA.b $0E
  LDA.w $E807, X : CMP.w #$000F : BEQ .missing_boss
  AND.w #$FF00 : BNE .missing_boss
  SEP #$20
  LDA.b #$50 : STA.w $0FA8 : STZ.w $0FA9
  LDA.b #$40 : STA.w $0FAA : STZ.w $0FAB
  LDY.w #$001D
  .find_boss
    LDA.b ($0E), Y : CMP.b #$0F : BEQ .next_boss
    CMP.w $E807, X : BEQ .boss_ready
    .next_boss
    LDA.w $0FA8 : SEC : SBC.b #$10 : STA.w $0FA8
    BPL .boss_column
      LDA.b #$50 : STA.w $0FA8
      LDA.w $0FAA : SEC : SBC.b #$10 : STA.w $0FAA
    .boss_column
    DEY : BPL .find_boss
  .missing_boss
  REP #$20
  ; The retained tail applies floor-pan offsets. Keep the high byte
  ; nonzero throughout that adjustment so a missing boss stays offscreen.
  LDA.w #$4000 : STA.w $0FAA
  STZ.w $0FA8
  .boss_ready
  LDX.w $040C
  SEP #$20
  JML $0AE910

; Original short-call entries use JML so the bank0A RTS still consumes the
; original near return. Only an absent D8 room hides the two map markers.
DungeonMapSix_BlinkingMarker:
  PHP
  REP #$20
  PHA
  LDA.l $7E040C : CMP.w #$0004 : BNE .visible
  LDA.l $7E0215 : CMP.w #$FFFF : BNE .visible
    PLA
    PLP
    LDX.b $00
    LDA.b #$00 : STA.w $0A20, X
    TXA : ASL #2 : TAX
    LDA.b #$F0 : STA.w $0801, X
    JML $0AEB89
  .visible
  PLA
  PLP
  LDX.b $00 : LDA.b #$00
  JML $0AEB54

DungeonMapSix_LocationMarker:
  PHP
  REP #$20
  PHA
  LDA.l $7E040C : CMP.w #$0004 : BNE .visible
  LDA.l $7E0215 : CMP.w #$FFFF : BNE .visible
    PLA
    PLP
    ; The caller loops until $00 reaches9. Retain this routine's four-slot
    ; advancement even when no marker is drawn, or the caller would loop forever.
    LDY.b #$03
    .hide_next
      LDX.b $00
      LDA.b #$02 : STA.w $0A20, X
      TXA : ASL #2 : TAX
      LDA.b #$F0 : STA.w $0801, X
      INC.b $00
      DEY : BPL .hide_next
    JML $0AEC09
  .visible
  PLA
  PLP
  LDY.b #$03 : LDA.b $00
  JML $0AEBAC

DungeonMapSix_RowOffsets:
  dw 0, 6, 12, 18, 24
DungeonMapSix_FloorOffsets:
  dw 0, 30, 60, 90, 120, 150, 180, 210
  dw 240, 270, 300, 330, 360, 390, 420, 450
DungeonMapSix_CornerOffsets:
  dw $00E2, $00FC, $03A2, $03BC
DungeonMapSix_SideOffsets:
  dw $0122, $013C

DungeonMapSix_CodeEnd:
assert pc() <= $52F000, "Six-column dungeon map code exceeds its owned slot"
pullpc
endif
