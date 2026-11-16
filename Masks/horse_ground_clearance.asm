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
if !ENABLE_HORSE_LONG_JUMP == 1
  JSR .query_side                     ; out-of-area side probe reads clear
else
  SEP #$20
  JSR Horse_QueryTileAt
endif
if !ENABLE_HORSE_LONG_JUMP == 1
  ; A named water gap blocks like a wall unless a valid long jump crosses it
  ; from here (.gap_point: A = $00 clear, $FF block, else the attribute).
  JSR .gap_point : CMP.b #$FF : BEQ .block
endif
  CMP.b #$01 : BEQ .solid
  CMP.b #$02 : BNE .clear_point
  .solid
  ; A thin named fence is handled by CheckFenceJump, not this solid envelope.
  REP #$20
  JSR .is_fence : BCS .fence_clear
  JSR .fence_ahead : BCS .fence_clear
  SEP #$20
  .block
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
if !ENABLE_HORSE_LONG_JUMP == 1
  ; Same rule for a solid neighbour beside a valid long-jump gap.
  JSR .is_fence : BCS + : JMP .long_ahead : +
  RTS
else
  BRA .is_fence
endif
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
if !ENABLE_HORSE_LONG_JUMP == 1
  ; In: A16/X8, $0E = edge index. Out: carry = a valid long jump is ahead in
  ; this direction (CheckFenceJump near/far probes, then the probe line at
  ; this edge). X/Y, $04, $0A and $0C are clobbered; the caller restores them.
  .long_ahead
  SEP #$20
  LDA.b $0E : LSR : STA.l Horse_JumpDir
  JSR HorseLong_TryProbes : BCS .long_ahead_done
  REP #$20
  LDA.b $0E : AND.w #$00FF : CMP.w #$0004 : BCS .long_body_row
    LDA.b $22 : CLC : ADC.w #$0008 : STA.b $0C
    BRA .long_query
  .long_body_row
    LDA.b $20 : CLC : ADC.w #$000B : STA.b $0A
  .long_query
  SEP #$20
  JSR Horse_QueryTileAt
  REP #$20 : JSR HorseLong_IsGap : SEP #$20
  BCC .long_ahead_done
  JSR HorseLong_ScanGap
  .long_ahead_done
  REP #$20
  RTS
  ; In: M8/X8, A = attribute of the edge point, $04 = its Tile16, $0E = edge
  ; index. Out: M8/X8; A = $00 (gap with a valid jump: clear), $FF (gap, no
  ; valid jump: block) or the attribute unchanged (not a gap). Clearing a
  ; jumpable gap point lets the horse keep walking and turn to face the gap,
  ; so CheckFenceJump's probes can reach it (the queue123 freeze class).
  ; A side probe outside the current area would wrap ($070E/$070A masks in
  ; Horse_QueryTileAt) to the opposite edge of this area; skip it. Native
  ; Link collision and the area transition still own the seam itself.
  ; In: A16/X8, $0A/$0C = probe point, X = edge index. Out: M8/X8, A = tile
  ; attribute and $04 = Tile16, or A = $00 / $04 = $0000 (clear) when skipped.
  .query_side
  CPX.b #$04 : BCC + : JSR .point_outside_area : BCC +
    STZ.b $04
    SEP #$20 : LDA.b #$00
    RTS
  + SEP #$20
  JMP Horse_QueryTileAt
  ; In: A16/X8, $0A/$0C = probe point. Out: carry set when the point lies
  ; outside the current area (bits above the $070E/$070A masks; the masks
  ; are contiguous low bits, sub-tile bits are don't-care). Clobbers $04.
  .point_outside_area
  LDA.l $7E070E : EOR.w #$FFFF : STA.b $04
  LDA.b $0C : LSR #3 : SEC : SBC.l $7E070C
  AND.b $04 : AND.w #$FFFE : BNE .outside_area
  LDA.l $7E070A : EOR.w #$FFFF : STA.b $04
  LDA.b $0A : SEC : SBC.l $7E0708
  AND.b $04 : AND.w #$FFF0 : BNE .outside_area
  CLC
  RTS
  .outside_area
  SEC
  RTS
  .gap_point
  PHA
  REP #$20 : JSR HorseLong_IsGap : SEP #$20
  BCS +
  PLA
  RTS
  + PLA
  LDA.b $0E : LSR : STA.l Horse_JumpDir
  JSR HorseLong_ScanGap : SEP #$30
  LDA.b #$00 : BCS +
  DEC
  + RTS
endif
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

if !ENABLE_HORSE_LONG_JUMP == 1
!Horse_LongJumpMaxTiles = 2
!Horse_LongJumpMinFrames = $10
!Horse_LongJumpMaxFrames = $12
!Horse_LongJumpShakeFrames = $03

; Vanilla dash-bonk tremor spawner (ancilla $1D, Ancilla1D_ScreenShake).
HorseLong_AncillaAdd_DashTremor = $0993F3

; Long-jump height across 16 arc steps: peak 24 px (fence vault table peaks
; at 15). Index = step*16/N, so the curve stretches over N frames.
HorseLong_ZTable:
  db  3,  8, 13, 16, 19, 22, 23, 24
  db 24, 23, 22, 19, 16, 13,  8,  3

; Water-gap Tile16s Epona clears with a long jump (gap of 1..2 tiles).
; Clones keep the original 8x8 chars, so water collision is unchanged and
; Link on foot still meets deep water. D2 Tail Pond $2D x10/x11 y11-13:
; $0F90 = clone of $02C5, $0F91 = clone of $02CE.
HorseLongGapTile16s:
  dw $0F90, $0F91
HorseLongGapTile16s_End:

; In: A16/X8, $04 = Tile16. Out: carry set if $04 is a long-gap Tile16. X clobbered.
HorseLong_IsGap:
{
  LDX.b #$00
  .loop
  LDA.l HorseLongGapTile16s, X : CMP.b $04 : BEQ .hit
  INX #2 : CPX.b #HorseLongGapTile16s_End-HorseLongGapTile16s : BCC .loop
  CLC
  RTS
  .hit
  SEC
  RTS
}

; In: M8/X8, Horse_JumpDir. Probes CheckFenceJump's near then far point for a
; gap Tile16, then scans it. Out: carry = valid jump; Horse_JumpEndX/Y set.
HorseLong_TryProbes:
{
  LDA.b #$00 : JSR .probe : BCS .scan
  LDA.b #$01 : JSR .probe : BCC .done
  .scan
  JSR HorseLong_ScanGap
  .done
  RTS

  .probe
  PHA
  LDA.l Horse_JumpDir : ASL : ORA 1, S : ASL : TAX
  REP #$20
  LDA.l HorseForm_ProbeFence_dx_table, X : CLC : ADC.b $22 : STA.b $0C
  LDA.l HorseForm_ProbeFence_dy_table, X : CLC : ADC.b $20 : STA.b $0A
  SEP #$20
  PLA
  JSR Horse_QueryTileAt
  REP #$20 : JSR HorseLong_IsGap : SEP #$20
  RTS
}

; In: M8/X8, $0A/$0C = a point inside a gap Tile16, Horse_JumpDir (U,D,L,R).
; Walks one Tile16 at a time to the first non-gap Tile16 (at most
; !Horse_LongJumpMaxTiles more), then sets the landing with the fence-jump
; conventions and checks bounds, reach and the landing footprint.
; Out: carry = valid; Horse_JumpEndX/Y. Clobbers X/Y, $04, $0A, $0C.
HorseLong_ScanGap:
{
  REP #$20
  LDA.b $0C : AND.w #$FFF0 : STA.b $0C
  LDA.b $0A : AND.w #$FFF0 : STA.b $0A
  SEP #$20
  LDY.b #!Horse_LongJumpMaxTiles
  .step
    LDA.l Horse_JumpDir : ASL : TAX
    REP #$20
    LDA.b $0C : CLC : ADC.l .step_x, X : STA.b $0C
    LDA.b $0A : CLC : ADC.l .step_y, X : STA.b $0A
    SEP #$20
    JSR Horse_QueryTileAt
    REP #$20 : JSR HorseLong_IsGap : SEP #$20
    BCC .found_land
    DEY : BNE .step
  CLC
  RTS

  .found_land
  ; $0A/$0C = origin of the first ground Tile16 past the gap.
  LDA.l Horse_JumpDir : ASL : TAX
  REP #$20
  CPX.b #$04 : BCS .horizontal
    LDA.b $22 : STA.l Horse_JumpEndX
    LDA.b $0A
    CPX.b #$02 : BNE + : SEC : SBC.w #$0004 : +   ; down: fence FY+12 rule
    STA.l Horse_JumpEndY
    BRA .bounds
  .horizontal
    LDA.b $0C : STA.l Horse_JumpEndX
    LDA.b $20 : STA.l Horse_JumpEndY
  .bounds
  ; Same $400-quadrant/border rule as HorseForm_ComputeJumpEnd.
  LDA.l Horse_JumpEndX : CMP.w #$0010 : BCC .invalid
  EOR.b $22 : AND.w #$FC00 : BNE .invalid
  LDA.l Horse_JumpEndY : CMP.w #$0010 : BCC .invalid
  EOR.b $20 : AND.w #$FC00 : BNE .invalid
  ; Reach: |dX| and |dY| must fit the 8-bit lerp multiplicand.
  LDA.l Horse_JumpEndX : SEC : SBC.b $22 : BPL + : EOR.w #$FFFF : INC : +
  CMP.w #$00F0 : BCS .invalid
  LDA.l Horse_JumpEndY : SEC : SBC.b $20 : BPL + : EOR.w #$FFFF : INC : +
  CMP.w #$00F0 : BCS .invalid
  SEP #$20
  JMP HorseForm_CheckLandingWalkable        ; carry = landing walkable

  .invalid
  SEP #$20
  CLC
  RTS

  .step_x
  dw $0000, $0000, $FFF0, $0010
  .step_y
  dw $FFF0, $0010, $0000, $0000
}

; In: M8/X8 from CheckFenceJump with Horse_JumpDir set and no fence ahead.
; Out: carry = launch; Horse_JumpEndX/Y and Horse_JumpTimer (total frames) set.
HorseLong_TryJump:
{
  JSR HorseLong_TryProbes : BCC .done
  ; Frames = max(|dX|,|dY|)*5/16, clamped to 16..18: about 3.2 px per
  ; frame, about twice the measured riding speed (D2 54 px gap = 16 frames).
  REP #$20
  LDA.l Horse_JumpEndX : SEC : SBC.b $22 : BPL + : EOR.w #$FFFF : INC : +
  STA.b $06
  LDA.l Horse_JumpEndY : SEC : SBC.b $20 : BPL + : EOR.w #$FFFF : INC : +
  CMP.b $06 : BCS + : LDA.b $06 : +
  STA.b $06 : ASL #2 : CLC : ADC.b $06    ; dist*5 (dist < $F0)
  LSR #4
  CMP.w #!Horse_LongJumpMinFrames : BCS + : LDA.w #!Horse_LongJumpMinFrames : +
  CMP.w #!Horse_LongJumpMaxFrames : BCC + : LDA.w #!Horse_LongJumpMaxFrames : +
  SEP #$20
  STA.l Horse_JumpTimer
  SEC
  .done
  RTS
}

; Long-jump flight. M8/X8. Horse_JumpTimer = N total frames (16..18).
; Z = HorseLong_ZTable[step*16/N]; X/Y = Start + (End-Start)*(step+1)/N.
; Landing: SFX2.21 thud plus a 3-frame vanilla dash tremor shake.
HorseLong_JumpTick:
{
  LDA.b #$0F : TRB.b $F0 : TRB.b $F2
  LDA.l Horse_JumpStep : CMP.l Horse_JumpTimer : BCS .land
    REP #$20
    AND.w #$00FF : ASL #4 : STA.l $004204   ; dividend = step*16
    SEP #$20
    LDA.l Horse_JumpTimer : STA.l $004206
    NOP #8                                  ; 16-cycle divide
    LDA.l $004214 : TAX
    LDA.l HorseLong_ZTable, X : STA.l Horse_JumpZ

    LDA.l Horse_JumpStep : INC : STA.b $0E  ; t = 1..N
    REP #$20
    LDA.l Horse_JumpStartX : STA.b $00
    LDA.l Horse_JumpEndX   : STA.b $02
    JSR HorseLong_Lerp
    STA.b $22
    LDA.l Horse_JumpStartY : STA.b $00
    LDA.l Horse_JumpEndY   : STA.b $02
    JSR HorseLong_Lerp
    STA.b $20
    SEP #$20

    LDA.l Horse_JumpStep : INC : STA.l Horse_JumpStep
    CMP.l Horse_JumpTimer : BCC .done

  .land
  REP #$20
  LDA.l Horse_JumpEndX : STA.b $22
  LDA.l Horse_JumpEndY : STA.b $20
  SEP #$20
  LDA.b #$00 : STA.l Horse_State : STA.l Horse_JumpZ : STA.l Horse_JumpStep
  STA.l Horse_JumpTimer
  LDA.b #$10 : STA.l Horse_JumpCooldown
  LDA.b #$21 : STA.w $012E            ; SFX2.21 hoof landing thud
  ; Vanilla dash tremor (16 frames by default), cut to a short landing shake.
  ; DBR=$00 here; on success the spawner returns carry clear, X = slot.
  LDY.b #$01 : LDA.b #$1D
  JSL HorseLong_AncillaAdd_DashTremor : BCS .done
  LDA.b #!Horse_LongJumpShakeFrames : STA.w $0C5E, X
  .done
  RTS
}

; In: M16/X8, $00 = Start, $02 = End, $0E = t (8-bit), Horse_JumpTimer = N.
; |End-Start| < $100. Out: M16, A = Start + (End-Start)*t/N.
HorseLong_Lerp:
{
  LDA.b $02 : SEC : SBC.b $00 : BEQ .same
  PHP                                 ; N flag = sign
  BPL + : EOR.w #$FFFF : INC : +
  SEP #$20
  STA.l $004202
  LDA.b $0E : STA.l $004203
  NOP #4                              ; 8-cycle multiply
  REP #$20
  LDA.l $004216 : STA.l $004204
  SEP #$20
  LDA.l Horse_JumpTimer : STA.l $004206
  NOP #8                              ; 16-cycle divide
  REP #$20
  LDA.l $004214
  PLP : BPL + : EOR.w #$FFFF : INC : +
  CLC : ADC.b $00
  RTS
  .same
  LDA.b $00
  RTS
}
endif
assert pc() <= $53E800, "Horse grounded clearance exceeded its bounded bank53 slice"
pullpc
