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
; Replaces FluteMenu_LoadMap ($0AB74B: STZ $1AF0 : JSL $0ABA30 : RTL).
; Starts the cursor on the first unlocked destination (0 when none).
TravelPicker_LoadMap:
{
  PHP : SEP #$30
  LDX.b #$00
.next
  LDA.l TravelDest_Bits, X : AND.l TravelSpotsVisited : BNE .set
  INX : CPX.b #$08 : BCC .next
  LDX.b #$00
.set
  TXA : STA.l $7E1AF0
  PLP
  JML $0ABA30                             ; WorldMap_LoadLightWorldMap (RTLs)
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
  LDA.l TravelDest_Bits, X : AND.l TravelSpotsVisited : BNE .found
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
; The cursor numeral always draws; other locked numerals are skipped.
TravelPicker_Numeral:
{
  CPX.w $1AF0 : BEQ .selected
  LDA.l TravelDest_Bits, X : AND.l TravelSpotsVisited : BNE .unlocked
  JML $0AB8AA                             ; .to_next_numeral
.selected
  JML $0AB818                             ; .selected
.unlocked
  JML $0AB864                             ; .not_selected
}

; ---------------------------------------------------------
; Vanilla hook sites (bank $0A). Original bytes asserted first.
pushpc

assert read1($0AB74B) == $9C && read2($0AB74C) == $1AF0
org $0AB74B
  JML TravelPicker_LoadMap

assert read1($0AB7AC) == $8E && read2($0AB7AD) == $1AF0
org $0AB7AC
  JSL TravelPicker_Move
  BRA TravelPicker_MoveDone              ; a label: asar emits a numeric BRA operand as a raw offset

assert read1($0AB813) == $EC && read2($0AB814) == $1AF0 && read1($0AB816) == $D0
org $0AB813
  JML TravelPicker_Numeral
  NOP

pullpc
