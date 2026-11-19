; =========================================================
; Travel destinations: visited bits and the unlocked-only bird picker.
; Included from Items/all_items.asm (bank $34 is full).
;
; TravelSpotsVisited ($7EF412) holds one bit per bird destination:
; bit i = destination i of LoadTransport_screen_id ($02EAE5, 8 words).
; The bit is set the first time Link enters that overworld area. The bird
; picker (module $0E sub $0A) draws and selects only destinations whose bit
; is set. An empty mask is refused before the bird spawns (menu Travel and
; Song of Soaring), so the picker never opens with nothing to pick.
; =========================================================

TravelDest_ScreenIDs = $02EAE5            ; LoadTransport_screen_id (8 words)
TravelPicker_MoveDone = $0AB7D3           ; FluteMenu_HandleSelection after the move code

; ---------------------------------------------------------
; Area-load hook. Replaces the JSL to Oracle_CheckIfNight in
; LoadOverworldSprites_Interupt ($09C4C7), which runs on every overworld
; area load. Preserves P, X and Y, then tail-jumps to CheckIfNight.
TravelDest_MarkVisited:
{
  PHP : SEP #$30
  PHX
  LDA.l $7E040A
  LDX.b #$0E
.next
  CMP.l TravelDest_ScreenIDs, X : BEQ .hit
  DEX : DEX : BPL .next
  BRA .done
.hit
  TXA : LSR : TAX
  LDA.l TravelDest_Bits, X
  ORA.l TravelSpotsVisited : STA.l TravelSpotsVisited
.done
  PLX
  PLP
  JML CheckIfNight                        ; Oracle_CheckIfNight (same namespace)
}

TravelDest_Bits:
  db $01, $02, $04, $08, $10, $20, $40, $80

; ---------------------------------------------------------
; M8/X8 -> returns A = 8-bit unlocked destination mask (preserves X, Y).
; Light World ($00..$3F): TravelSpotsVisited ($7EF412).
; Special Overworld ($80..$BF, when !ENABLE_SPECIAL_OVERWORLD_SOARING == 1):
;   pins 1..5 always unlocked ($1F), plus pin 6 (Sky) when SkySoaringLearned == $A5 ($3F).
TravelPicker_GetMask:
{
if !ENABLE_SPECIAL_OVERWORLD_SOARING == 1
  LDA.b $8A : CMP.b #$80 : BCC .light_world
  CMP.b #$C0 : BCS .light_world
    LDA.l SkySoaringLearned : CMP.b #!SKY_SOARING_LEARNED : BEQ .with_sky
    LDA.b #$1F : RTS
  .with_sky
    LDA.b #$3F : RTS
  .light_world
endif
  LDA.l TravelSpotsVisited : RTS
}

; ---------------------------------------------------------
; Replaces FluteMenu_LoadMap ($0AB74B: STZ $1AF0 : JSL $0ABA30 : RTL).
; Starts the cursor on the first unlocked destination (0 when none).
TravelPicker_LoadMap:
{
  PHP : SEP #$30
  LDX.b #$00
.next
  JSR TravelPicker_GetMask : AND.l TravelDest_Bits, X : BNE .set
  INX : CPX.b #$08 : BCC .next
  LDX.b #$00
.set
  TXA : STA.l $7E1AF0
  PLP
  JML $0ABA30                             ; WorldMap_LoadLightWorldMap (RTLs)
}

if !ENABLE_SPECIAL_OVERWORLD_SOARING == 1
; ---------------------------------------------------------
; Replaces FluteMenu_HandleSelection input check at $0AB78F..$0AB79A (12B):
;   LDA $F2 : ORA $F0 : AND #$C0 : BEQ $0AB79D : INC $0200 : RTL
; Entry: M=8, X=8, DBR=$0A ($C8 == 0).
; Light World ($00..$3F): exact vanilla confirm behavior.
; Special Overworld ($80..$BF):
;   - B ($F4 bit 7) or X ($F6 bit 6): cancel via Module $0E Sub $07
;     (WorldMap_RestoreGraphics -> WorldMap_ExitMap -> Module $09 Sub $20).
;   - A ($F6 bit 7) or START ($F4 bit 4): confirm and advance to transport.
TravelPicker_CheckAction:
{
  LDA.b $8A : CMP.b #$80 : BCC .light_world
  CMP.b #$C0 : BCS .light_world
    LDA.b $F4 : AND.b #$80 : BNE .sw_cancel
    LDA.b $F6 : AND.b #$40 : BNE .sw_cancel
    LDA.b $F6 : AND.b #$80 : BNE .sw_confirm
    LDA.b $F4 : AND.b #$10 : BNE .sw_confirm
    JML $0AB79D                           ; .no_selection_made
  .sw_cancel
    STZ.w $1AF0
    LDA.b #$07 : STA.b $11                ; switch to OverworldMap exit sequence
    INC.w $0200                           ; 5 -> 6 (WorldMap_RestoreGraphics -> WorldMap_ExitMap)
    RTL
  .sw_confirm
    INC.w $0200                           ; 5 -> 6 (WorldMap_RestoreGraphics -> FluteMenu_LoadSelectedScreen)
    RTL

  .light_world
  LDA.b $F2 : ORA.b $F0 : AND.b #$C0 : BEQ .lw_none
    INC.w $0200
    RTL
  .lw_none
  JML $0AB79D                             ; .no_selection_made
}
endif

; ---------------------------------------------------------
; Replaces the cursor move at $0AB7AC (X = cursor, 8-bit).
; Up/left steps back, down/right steps forward, both skipping locked
; destinations with wrap. When no other destination is unlocked the
; cursor stays put and no sound plays. Preserves X and Y.
TravelPicker_Move:
{
  PHX : PHY
  STX.w $1AF0
  LDA.b $F4 : AND.b #$0A : BEQ .forward
  LDA.b #$FF : BRA .search
.forward
  LDA.b $F4 : AND.b #$05 : BEQ .done
  LDA.b #$01
.search
  STA.b $00
  LDY.b #$07
.next
  TXA : CLC : ADC.b $00 : AND.b #$07 : TAX
  JSR TravelPicker_GetMask : AND.l TravelDest_Bits, X : BNE .found
  DEY : BNE .next
  BRA .done
.found
  STX.w $1AF0
  LDA.b #$20 : STA.w $012F                ; SFX3.20 cursor
.done
  PLY : PLX
  RTL
}

; ---------------------------------------------------------
; Replaces .next_numeral at $0AB813 (CPX $1AF0 : BNE .not_selected).
; Entry: M=8, X=8, DBR=$0A, X = pin index (7 down to 0).
; Light World ($00..$3F): cursor numeral always draws; other locked numerals
; are skipped, using vanilla FluteMenuNumbers coordinates.
; Special Overworld ($80..$BF): unlocked pins 1..5 (plus 6 when Sky learned)
; load Lyra Sea coordinates into $1AB0..$1AE0/$7EC108..$7EC10B and rejoin
; vanilla selected ($0AB844) / unselected ($0AB890) OAM numeral rendering.
TravelPicker_Numeral:
{
if !ENABLE_SPECIAL_OVERWORLD_SOARING == 1
  LDA.b $8A : CMP.b #$80 : BCC .light_world
  CMP.b #$C0 : BCS .light_world
    JSR TravelPicker_GetMask : AND.l TravelDest_Bits, X : BNE .sw_unlocked
    JML $0AB8AA                           ; .to_next_numeral
  .sw_unlocked
    LDA.l SpecialSoaring_PinXLo, X : STA.w $1AB0, X : STA.l $7EC10A
    LDA.l SpecialSoaring_PinXHi, X : STA.w $1AC0, X : STA.l $7EC10B
    LDA.l SpecialSoaring_PinYLo, X : STA.w $1AD0, X : STA.l $7EC108
    LDA.l SpecialSoaring_PinYHi, X : STA.w $1AE0, X : STA.l $7EC109
    CPX.w $1AF0 : BEQ .sw_selected
    JML $0AB890                           ; .not_selected (post-coord load)
  .sw_selected
    JML $0AB844                           ; .selected (post-coord load)
  .light_world
endif
  CPX.w $1AF0 : BEQ .selected
  LDA.l TravelDest_Bits, X : AND.l TravelSpotsVisited : BNE .unlocked
  JML $0AB8AA                             ; .to_next_numeral
.selected
  JML $0AB818                             ; .selected
.unlocked
  JML $0AB864                             ; .not_selected
}

if !ENABLE_SPECIAL_OVERWORLD_SOARING == 1
; ---------------------------------------------------------
; Replaces FluteMenu_LoadSelectedScreen entry ($0AB8C5: LDA.l $7EF2BB).
; Entry: M=8, X=8, DBR=$0A ($0200 == 7 after WorldMap_RestoreGraphics).
; Special Overworld ($80..$BF): runs SpecialSoaring_ExecuteTransport; if the
; index is defensively rejected, exits cleanly via WorldMap_ExitMap ($0ABC54).
; Light World ($00..$3F): resumes vanilla FluteMenu_LoadSelectedScreen ($0AB8C9).
TravelPicker_LoadSelectedScreen:
{
  LDA.b $8A : CMP.b #$80 : BCC .light_world
  CMP.b #$C0 : BCS .light_world
    JSL SpecialSoaring_ExecuteTransport : BCS .transported
    JML $0ABC54                           ; WorldMap_ExitMap defensive fallback
  .transported
    RTL
  .light_world
  LDA.l $7EF2BB
  JML $0AB8C9
}
endif

; ---------------------------------------------------------
; Vanilla hook sites (bank $0A). Original bytes asserted first.
pushpc

assert read1($0AB74B) == $9C && read2($0AB74C) == $1AF0
org $0AB74B
  JML TravelPicker_LoadMap

if !ENABLE_SPECIAL_OVERWORLD_SOARING == 1
assert read4($0AB78F) == $F005F2A5 && read4($0AB793) == $06F0C029 && read4($0AB797) == $6B0200EE, "FluteMenu_HandleSelection input check moved"
org $0AB78F ; @hook module=Overworld name=TravelPicker_CheckAction kind=jml target=Oracle_TravelPicker_CheckAction expected_m=8 expected_x=8 protected_size=12
  JML TravelPicker_CheckAction
  NOP #8
assert pc() == $0AB79B
endif

assert read1($0AB7AC) == $8E && read2($0AB7AD) == $1AF0
org $0AB7AC
  JSL TravelPicker_Move
  BRA TravelPicker_MoveDone              ; a label: asar emits a numeric BRA operand as a raw offset

assert read1($0AB813) == $EC && read2($0AB814) == $1AF0 && read1($0AB816) == $D0
org $0AB813
  JML TravelPicker_Numeral
  NOP

if !ENABLE_SPECIAL_OVERWORLD_SOARING == 1
assert read4($0AB8C5) == $7EF2BBAF, "FluteMenu_LoadSelectedScreen entry moved"
org $0AB8C5 ; @hook module=Overworld name=TravelPicker_LoadSelectedScreen kind=jml target=Oracle_TravelPicker_LoadSelectedScreen expected_m=8 expected_x=8 protected_size=4
  JML TravelPicker_LoadSelectedScreen
assert pc() == $0AB8C9
endif

pullpc
