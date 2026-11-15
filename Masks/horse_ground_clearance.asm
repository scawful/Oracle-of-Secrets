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
  JSR .is_fence : BCS .fence_clear
  JSR .fence_ahead : BCS .fence_clear
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
  ; A solid neighbour (e.g. a post beside a pit gap) does not block when a
  ; fence Tile16 is ahead: either CheckFenceJump's own near/far probe for this
  ; direction (so a blocked turn-around can still face the fence and jump), or
  ; the probe line at this leading edge (body row y+11 sideways, centre column
  ; x+8 vertically). Edge index/2 = Horse_JumpDir (U,D,L,R); CheckFenceJump
  ; rewrites Horse_JumpDir before any read, so the store here is scratch.
  ; In: A16/X8, $0A/$0C = edge point, $0E = edge index. Out: carry = fence.
  ; X and $0A or $0C are clobbered; the caller recomputes them per point.
  .fence_ahead
  PEI ($0A) : PEI ($0C)
  SEP #$20
  LDA.b $0E : LSR : STA.l Horse_JumpDir
  LDA.b #$00 : JSR HorseForm_ProbeFence : BCS .probe_hit
  LDA.b #$01 : JSR HorseForm_ProbeFence : BCS .probe_hit
  REP #$20
  PLA : STA.b $0C : PLA : STA.b $0A
  LDA.b $0E : AND.w #$00FF : CMP.w #$0004 : BCS .probe_body_row
    LDA.b $22 : CLC : ADC.w #$0008 : STA.b $0C
    BRA .probe_query
  .probe_body_row
    LDA.b $20 : CLC : ADC.w #$000B : STA.b $0A
  .probe_query
  SEP #$20
  JSR Horse_QueryTileAt
  REP #$20
  BRA .is_fence
  .probe_hit
  REP #$20
  PLA : PLA
  SEC
  RTS
  ; In: A16/X8, $04 = Tile16. Out: carry set if $04 is in HorseFenceTile16s.
  .is_fence
  LDX.b #$00
  .fence
  LDA.l HorseFenceTile16s, X : CMP.b $04 : BEQ .is_fence_hit
  INX #2 : CPX.b #HorseFenceTile16s_End-HorseFenceTile16s : BCC .fence
  CLC
  RTS
  .is_fence_hit
  SEC
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
; Ranch fence Tile16s Epona can jump: Toto Ranch fence set, $02D6, and the Kalyxo-art
; pit gap Tile16s $0EF2 (top) / $0EF4 (bottom) on map $22 (x=4, y=17..18).
HorseFenceTile16s:
  dw $0078, $007B, $043A, $003B, $0267, $002C, $02D6, $0EF2, $0EF4
HorseFenceTile16s_End:
assert pc() <= $53E800, "Horse grounded clearance exceeded its bounded bank53 slice"
pullpc
