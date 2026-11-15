; Mounted leading-edge clearance for tall horse/rider art. Native Link still
; owns hazards, slopes, water, pits and actual movement. Only hard solid types
; $01/$02 extend the mounted boundary; named Ranch fences retain jump handling.
; Leading edge only: an overlap in front cannot prevent backing away from it.
; Runs before Link_ControlHandler, only ordinary grounded control frames.
; Entry/exit M8/X8. DP/X/Y/DBR/stack preserved. A/P are scratch, including
; the active-jump bypass; outer LinkMain_FrameHook preserves caller A/P.
pushpc
org $53E000
HorseForm_ConstrainGroundInput:
{
  LDA.l Horse_State : BEQ + : RTS : +
  PHP : REP #$30
  PHA : PHX : PHY
  LDA.b $00 : PHA : LDA.b $02 : PHA : LDA.b $04 : PHA
  LDA.b $06 : PHA : LDA.b $08 : PHA : LDA.b $0A : PHA
  LDA.b $0C : PHA : LDA.b $0E : PHA
  SEP #$30
  LDX.b #$03
  .direction
  LDA.l .buttons, X : AND.b $F0 : BEQ .next_direction
  PHX
  TXA : ASL : STA.b $0E
  LDY.b #$02
  CPX.b #$02 : BCC + : LDY.b #$04 : +
  .point
  PHY
  TYA : ASL : TAX
  REP #$20
  LDA.l .along, X : STA.b $08
  LDA.b $0E : AND.w #$00FF : TAX
  LDA.l .edge_x, X : CLC : ADC.b $22 : STA.b $0C
  LDA.l .edge_y, X : CLC : ADC.b $20 : STA.b $0A
  CPX.b #$04 : BCS .vertical_edge
    LDA.b $0C : CLC : ADC.b $08 : STA.b $0C
    BRA .query
  .vertical_edge
    LDA.b $0A : CLC : ADC.b $08 : STA.b $0A
  .query
  SEP #$20
  JSR Horse_QueryTileAt
  CMP.b #$01 : BEQ .solid
  CMP.b #$02 : BNE .clear_point
  .solid
  ; A thin named fence is handled by CheckFenceJump, not this solid envelope.
  REP #$20
  LDX.b #$00
  .fence
  LDA.l HorseFenceTile16s, X : CMP.b $04 : BEQ .fence_clear
  INX #2 : CPX.b #HorseFenceTile16s_End-HorseFenceTile16s : BCC .fence
  SEP #$20
  PLY : PLX
  LDA.l .buttons, X : TRB.b $F0 : TRB.b $F2
  BRA .next_direction
  .fence_clear
  SEP #$20
  .clear_point
  PLY : DEY : BPL .point
  PLX
  .next_direction
  DEX : BMI .restore
  BRL .direction
  .restore
  REP #$30
  PLA : STA.b $0E : PLA : STA.b $0C : PLA : STA.b $0A
  PLA : STA.b $08 : PLA : STA.b $06 : PLA : STA.b $04
  PLA : STA.b $02 : PLA : STA.b $00
  PLY : PLX : PLA : PLP
  RTS
  .buttons
  db $08,$04,$02,$01 ; north, south, west, east
  ; Includes four pixels of next-step lookahead (horse cardinal speed2.75px).
  ; North uses rider head clearance; sides use the horse body, not its tail tip.
  .edge_x
  dw $0000,$0000,$FFF0,$0020
  .edge_y
  dw $FFDC,$0014,$FFE8,$FFE8
  .along
  dw $0000,$0008,$0010,$0018,$0020
}
HorseGroundClearance_End:
assert pc() <= $53E800, "Horse grounded clearance exceeded its bounded bank53 slice"
pullpc
