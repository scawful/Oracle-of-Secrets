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
  CMP.b #$80 : BCC .check_abyss
  CMP.b #$C0 : BCS .done
    LDX.b #(SpecialTravelDest_AreasEnd-SpecialTravelDest_Areas)-1
  .sw_next
    CMP.l SpecialTravelDest_Areas, X : BEQ .sw_hit
    DEX : BPL .sw_next
    BRA .done
  .sw_hit
    LDA.l SpecialTravelDest_Masks, X
    ORA.l SpecialTravelSpotsVisited : STA.l SpecialTravelSpotsVisited
    BRA .done
  .check_abyss
  CMP.b #$40 : BCC .light_world
    LDX.b #(AbyssTravelDest_AreasEnd-AbyssTravelDest_Areas)-1
  .dw_next
    CMP.l AbyssTravelDest_Areas, X : BEQ .dw_hit
    DEX : BPL .dw_next
    BRA .done
  .dw_hit
    LDA.l AbyssTravelDest_Masks, X
    ORA.l AbyssTravelSpotsVisited : STA.l AbyssTravelSpotsVisited
    BRA .done
  .light_world
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
; Resolves active Soaring picker world (M8 -> A = 0 LW, 1 DW, 2 SW).
; Uses Soaring_ViewWorld once initialized; falls back to live $8A when both
; Soaring_OriginWorld and Soaring_ViewWorld are 0 so direct calls stay safe.
; Preserves X, Y.
TravelPicker_ActiveWorld:
{
  LDA.l Soaring_OriginWorld : ORA.l Soaring_ViewWorld : BEQ .from_area
    LDA.l Soaring_ViewWorld
    RTS
  .from_area
  LDA.b $8A
  CMP.b #$80 : BCC .not_sw
  CMP.b #$C0 : BCS .not_sw
    LDA.b #$02 : RTS
  .not_sw
  CMP.b #$40 : BCC .is_lw
    LDA.b #$01 : RTS
  .is_lw
  LDA.b #$00 : RTS
}

; ---------------------------------------------------------
; M8/X8 -> returns A = 8-bit unlocked destination mask (preserves X, Y).
;   0 (Kalyxo LW): TravelSpotsVisited ($7EF412); returns $01 fallback if 0 and
;                  Soaring_OriginWorld == 2 so Link can never be trapped on Lyra Sea.
;   1 (Eon Abyss): AbyssTravelSpotsVisited | !AbyssSoaring_BaselineMask ($03).
;   2 (Lyra Sea):  (SpecialTravelSpotsVisited & $7F) | $0E, OR $80 iff SkySoaringLearned == $A5.
TravelPicker_GetMask:
{
  JSR TravelPicker_ActiveWorld
  CMP.b #$02 : BEQ .special_world
  CMP.b #$01 : BEQ .abyss_world
    LDA.l TravelSpotsVisited : BNE .lw_done
    LDA.l Soaring_OriginWorld : CMP.b #$02 : BNE .lw_zero
      LDA.b #$01 : RTS
    .lw_zero
    LDA.b #$00
    .lw_done
    RTS
  .abyss_world
    LDA.l AbyssTravelSpotsVisited : ORA.b #!AbyssSoaring_BaselineMask : RTS
  .special_world
    LDA.l SpecialTravelSpotsVisited
    AND.b #$7F
    ORA.b #$0E
    PHA
    LDA.l SkySoaringLearned : CMP.b #!SKY_SOARING_LEARNED : BNE .no_sky
      PLA : ORA.b #$80 : RTS
    .no_sky
    PLA : RTS
}

; ---------------------------------------------------------
; Replaces FluteMenu_LoadMap ($0AB74B: STZ $1AF0 : JSL $0ABA30 : RTL).
; Initializes OriginWorld/ViewWorld on fresh open (MapSwitchPending == 0),
; clears MapSwitchPending, and starts the cursor on the first unlocked spot.
TravelPicker_LoadMap:
{
  PHP : SEP #$30
  LDA.b #$00 : STA.l SpecialSoaring_LoadStep
  LDA.l Soaring_MapSwitchPending : BNE .after_init
    LDA.b $8A
    CMP.b #$80 : BCC .chk_dw
    CMP.b #$C0 : BCS .chk_dw
      LDA.b #$02 : BRA .store_worlds
    .chk_dw
    CMP.b #$40 : BCC .is_lw
      LDA.b #$01 : BRA .store_worlds
    .is_lw
    LDA.b #$00
    .store_worlds
    STA.l Soaring_OriginWorld
    STA.l Soaring_ViewWorld
  .after_init
  LDA.b #$00 : STA.l Soaring_MapSwitchPending
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

; ---------------------------------------------------------
; Replaces FluteMenu_HandleSelection input check at $0AB78F..$0AB79A (12B).
; Entry: M=8, X=8, DBR=$0A ($C8 == 0).
;   - B ($F4 bit 7) or X ($F6 bit 6): cancel cleanly from ANY world (LW/DW/SW).
;   - L ($F6 bit 5), R ($F6 bit 4), or SELECT ($F4 bit 5): flip ViewWorld <-> 0/2
;     when Soaring_OriginWorld == 2 OR (OriginWorld == 0 && SW reachable).
;   - A ($F6 bit 7) or START ($F4 bit 4) [or A-held $F2 bit 7 in vanilla LW]: confirm.
TravelPicker_CheckAction:
{
  LDA.b $F4 : AND.b #$80 : BNE .cancel
  LDA.b $F6 : AND.b #$40 : BNE .cancel

  LDA.b $F6 : AND.b #$30 : BNE .try_flip ; L / R
  LDA.b $F4 : AND.b #$20 : BNE .try_flip ; SELECT
  BRA .check_confirm

  .try_flip
  JSL Soaring_CanFlipWorld : BCC .check_confirm
    LDA.b #$20 : STA.w $012F            ; SFX3.20 swoosh
    LDA.l Soaring_ViewWorld : EOR.b #$02 : STA.l Soaring_ViewWorld
    LDA.b #$01 : STA.l Soaring_MapSwitchPending
    STZ.w $0200                         ; restart fade-out -> LoadMap -> fade-in
    RTL

  .check_confirm
  LDA.b $F6 : AND.b #$80 : BNE .confirm
  LDA.b $F4 : AND.b #$10 : BNE .confirm
  ; Preserve LW vanilla A-held confirm only when viewing LW from LW.
  JSR TravelPicker_ActiveWorld : BNE .none
  LDA.l Soaring_OriginWorld : BNE .none
  LDA.b $F2 : AND.b #$80 : BNE .confirm

  .none
  JML $0AB79D                           ; .no_selection_made

  .cancel
  JSL SpecialOverworld_RestoreMapPos
  JSL SpecialSoaring_CancelCleanup
  STZ.w $1AF0
  LDA.b #$07 : STA.b $11                ; switch to OverworldMap exit sequence
  INC.w $0200                           ; 5 -> 6 (WorldMap_RestoreGraphics -> ExitMap)
  RTL

  .confirm
  INC.w $0200                           ; 5 -> 6 (WorldMap_RestoreGraphics -> LoadSelectedScreen)
  RTL
}

; ---------------------------------------------------------
; Replaces Link blinking dot check at $0AB7D3..$0AB7D8 (6B).
; Draws cross-world toggle OAM badge when flip is enabled and hides Link's
; blinking dot whenever Soaring_ViewWorld != Soaring_OriginWorld.
TravelPicker_LinkAndBadge:
{
  JSL SpecialSoaring_DrawWorldToggleBadge
  LDA.l Soaring_OriginWorld : CMP.l Soaring_ViewWorld : BNE .skip_link
  LDA.b $1A : AND.b #$10 : BEQ .skip_link
    JML $0AB7D9                         ; draw Link dot
  .skip_link
  JML $0AB7FD                           ; .dont_draw_link
}

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
  JSR TravelPicker_ActiveWorld
  CMP.b #$02 : BEQ .sw_world
  CMP.b #$01 : BEQ .dw_world
    CPX.w $1AF0 : BEQ .lw_selected
    JSR TravelPicker_GetMask : AND.l TravelDest_Bits, X : BNE .lw_unlocked
    JML $0AB8AA                           ; .to_next_numeral
  .lw_selected
    JML $0AB818                           ; .selected
  .lw_unlocked
    JML $0AB864                           ; .not_selected

  .dw_world
    JSR TravelPicker_GetMask : AND.l TravelDest_Bits, X : BNE .dw_unlocked
    JML $0AB8AA                           ; .to_next_numeral
  .dw_unlocked
    LDA.l AbyssSoaring_PinXLo, X : STA.w $1AB0, X : STA.l $7EC10A
    LDA.l AbyssSoaring_PinXHi, X : STA.w $1AC0, X : STA.l $7EC10B
    LDA.l AbyssSoaring_PinYLo, X : STA.w $1AD0, X : STA.l $7EC108
    LDA.l AbyssSoaring_PinYHi, X : STA.w $1AE0, X : STA.l $7EC109
    CPX.w $1AF0 : BEQ .pin_selected
    JML $0AB890                           ; .not_selected (post-coord load)

  .sw_world
    JSR TravelPicker_GetMask : AND.l TravelDest_Bits, X : BNE .sw_unlocked
    JML $0AB8AA                           ; .to_next_numeral
  .sw_unlocked
    LDA.l SpecialSoaring_PinXLo, X : STA.w $1AB0, X : STA.l $7EC10A
    LDA.l SpecialSoaring_PinXHi, X : STA.w $1AC0, X : STA.l $7EC10B
    LDA.l SpecialSoaring_PinYLo, X : STA.w $1AD0, X : STA.l $7EC108
    LDA.l SpecialSoaring_PinYHi, X : STA.w $1AE0, X : STA.l $7EC109
    CPX.w $1AF0 : BEQ .pin_selected
    JML $0AB890                           ; .not_selected (post-coord load)
  .pin_selected
    JML $0AB844                           ; .selected (post-coord load)
}

; ---------------------------------------------------------
; Replaces FluteMenu_LoadSelectedScreen entry ($0AB8C5: LDA.l $7EF2BB).
; Entry: M=8, X=8, DBR=$0A ($0200 == 7 after WorldMap_RestoreGraphics).
; Dispatches on active Soaring view world:
;   2 (Lyra Sea SW): SpecialSoaring_ExecuteTransport
;   1 (Eon Abyss DW): AbyssSoaring_ExecuteTransport
;   0 (Kalyxo LW): if originating from SW ($02), scrub SW/Sky/water/sheet state
;     via SpecialSoaring_PrepareReturnToKalyxo before vanilla FluteMenu ($0AB8C9).
TravelPicker_LoadSelectedScreen:
{
  JSR TravelPicker_ActiveWorld
  CMP.b #$02 : BEQ .sw_transport
  CMP.b #$01 : BEQ .dw_transport
    LDA.l Soaring_OriginWorld : CMP.b #$02 : BNE .lw_ready
      JSL SpecialSoaring_PrepareReturnToKalyxo
      BRA .lw_go
    .lw_ready
    LDA.b #$00
    STA.l Soaring_MapSwitchPending
    STA.l Soaring_OriginWorld
    STA.l Soaring_ViewWorld
    .lw_go
    LDA.l $7EF2BB
    JML $0AB8C9
  .dw_transport
    JSL AbyssSoaring_ExecuteTransport : BCS .transported
    JML $0ABC54                           ; WorldMap_ExitMap defensive fallback
  .sw_transport
    JSL SpecialSoaring_ExecuteTransport : BCS .transported
    JML $0ABC54                           ; WorldMap_ExitMap defensive fallback
  .transported
    RTL
}

; ---------------------------------------------------------
; Vanilla hook sites (bank $0A). Original bytes asserted first.
pushpc

assert read1($0AB74B) == $9C && read2($0AB74C) == $1AF0
org $0AB74B
  JML TravelPicker_LoadMap

assert read4($0AB78F) == $F005F2A5 && read4($0AB793) == $06F0C029 && read4($0AB797) == $6B0200EE, "FluteMenu_HandleSelection input check moved"
org $0AB78F ; @hook module=Overworld name=TravelPicker_CheckAction kind=jml target=Oracle_TravelPicker_CheckAction expected_m=8 expected_x=8 protected_size=12
  JML TravelPicker_CheckAction
  NOP #8
assert pc() == $0AB79B

assert read1($0AB7AC) == $8E && read2($0AB7AD) == $1AF0
org $0AB7AC
  JSL TravelPicker_Move
  BRA TravelPicker_MoveDone              ; a label: asar emits a numeric BRA operand as a raw offset

assert read4($0AB7D3) == $10291AA5 && read2($0AB7D7) == $24F0, "FluteMenu Link-dot draw site moved"
org $0AB7D3 ; @hook module=Overworld name=TravelPicker_LinkAndBadge kind=jml target=Oracle_TravelPicker_LinkAndBadge expected_m=8 expected_x=8 protected_size=6
  JML TravelPicker_LinkAndBadge
  NOP #2
assert pc() == $0AB7D9

assert read1($0AB813) == $EC && read2($0AB814) == $1AF0 && read1($0AB816) == $D0
org $0AB813
  JML TravelPicker_Numeral
  NOP

assert read4($0AB8C5) == $7EF2BBAF, "FluteMenu_LoadSelectedScreen entry moved"
org $0AB8C5 ; @hook module=Overworld name=TravelPicker_LoadSelectedScreen kind=jml target=Oracle_TravelPicker_LoadSelectedScreen expected_m=8 expected_x=8 protected_size=4
  JML TravelPicker_LoadSelectedScreen
assert pc() == $0AB8C9

pullpc
