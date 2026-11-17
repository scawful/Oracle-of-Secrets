!D8Farore_A6WorldX = $0C38
!D8Farore_A6WorldY = $1440
!D8Farore_A6Layer = 0

; Gated sprite-stream helper. Caller owns stable gameplay, placed actor and
; presence policy1. SprMiscA is an actor-local active-follow latch, reset in Prep.
; No persistent state, input ownership, warp or new artwork.
; Requires a long wrapper for the existing four-corner footprint checker.
D8Farore_FollowStart:
D8Farore_Follow:
{
  PHP : PHB : PHK : PLB
  SEP #$30
  STZ.w SprGfx,X ; never leave a walking frame during holds/blocked movement
  LDA.w SprFloor,X : CMP.b $EE : BEQ + : JMP .hold : +
  LDA.b $5D : BEQ + : JMP .hold : + ; don't chase while Link is using a special movement state
  ; Start outside40px, stop once both axes fit32px. Hysteresis prevents
  ; threshold vibration while retaining the existing one-pixel cardinal step.
  JSR .position
  REP #$20
  LDA.b $22 : SEC : SBC.b $08 : BPL + : EOR.w #$FFFF : INC : +
  STA.b $00
  LDA.b $20 : SEC : SBC.b $0A : BPL + : EOR.w #$FFFF : INC : +
  CMP.b $00 : BCS + : LDA.b $00 : +
  CMP.w #$0021 : BCS + : JMP .settled : +
  CMP.w #$0029 : BCS .engage
  SEP #$20
  LDA.w SprMiscA,X : BNE .step
  JMP .done
.engage
  SEP #$20
  LDA.b #$01 : STA.w SprMiscA,X
.step

  REP #$20
  LDA.b $22 : SEC : SBC.b $08
  BPL .right
  EOR.w #$FFFF : INC : CMP.w #$0021 : BCC .try_y
  DEC.b $08 : BRA .check_x
.right
  CMP.w #$0021 : BCC .try_y
  INC.b $08
.check_x
  SEP #$20
  JSL D8Farore_CheckFootprintLong : BCS .retry_y
  JSR .commit
  STZ.w SprGfx,X
  BRA .done
.retry_y
  JSR .position
.try_y
  REP #$20
  LDA.b $20 : SEC : SBC.b $0A
  BPL .down
  EOR.w #$FFFF : INC : CMP.w #$0021 : BCC .no_move
  DEC.b $0A
  SEP #$20
  JSL D8Farore_CheckFootprintLong : BCS .done
  JSR .commit
  ; Original north walking frames only; no invented horizontal/south walk art.
  LDA.b $1A : LSR #3 : AND.b #$01 : CLC : ADC.b #$03
  STA.w SprGfx,X
  BRA .done
.down
  CMP.w #$0021 : BCC .no_move
  INC.b $0A
  SEP #$20
  JSL D8Farore_CheckFootprintLong : BCS .done
  JSR .commit
.no_move
  SEP #$20
  BRA .done
.settled
  SEP #$20
  STZ.w SprMiscA,X
.hold
  STZ.w SprMiscA,X
.done
  PLB : PLP : RTL
.position
  LDA.w SprX,X : STA.b $08
  LDA.w SprXH,X : STA.b $09
  LDA.w SprY,X : STA.b $0A
  LDA.w SprYH,X : STA.b $0B
  RTS
.commit
  LDA.b $08 : STA.w SprX,X
  LDA.b $09 : STA.w SprXH,X
  LDA.b $0A : STA.w SprY,X
  LDA.b $0B : STA.w SprYH,X
  RTS
}
; Join behind Link's current facing, then diagonal behind candidates. Do not
; use a forward/on-Link fallback: a blocked doorway keeps the actor pending,
; and Frame retries normally when the player clears it. A6's wait anchor stays.
D8Farore_JoinBehind:
{
  PHP : PHB : PHK : PLB
  SEP #$30
  LDA.b $A0 : CMP.b #$A6 : BEQ .wait_anchor
  LDY.b #$00
.try
  PHY
  REP #$20
  TYA : AND.w #$00FF : STA.b $00
  LDA.b $2F : AND.w #$0006 : LSR : STA.b $02
  ASL : CLC : ADC.b $02 : CLC : ADC.b $00 : ASL : TAY
  LDA.b $22 : CLC : ADC.w .dx,Y : STA.b $08
  LDA.b $20 : CLC : ADC.w .dy,Y : STA.b $0A
  ; Reject room wrapping before native floor probes mask coordinates to512px.
  LDA.b $08 : EOR.b $22 : AND.w #$FE00 : BNE .bounds_blocked
  LDA.b $0A : EOR.b $20 : AND.w #$FE00 : BNE .bounds_blocked
  LDA.b $08 : AND.w #$01FF : CMP.w #$01F1 : BCS .bounds_blocked
  LDA.b $0A : AND.w #$01FF : CMP.w #$01ED : BCS .bounds_blocked
  SEP #$20
  LDA.b $EE : STA.w SprFloor,X
  JSR .connected
  PLY : BCC .place
  BRA .next
.bounds_blocked
  SEP #$20
  PLY
.next
  INY : CPY.b #$03 : BCC .try
  BRA .done
.wait_anchor
  REP #$20
  LDA.w #!D8Farore_A6WorldX : STA.b $08
  LDA.w #!D8Farore_A6WorldY : STA.b $0A
  SEP #$20
  LDA.b #!D8Farore_A6Layer : STA.w SprFloor,X
  JSL D8Farore_CheckFootprintLong : BCS .done
.place
  LDA.b $08 : STA.w SprX,X
  LDA.b $09 : STA.w SprXH,X
  LDA.b $0A : STA.w SprY,X
  LDA.b $0B : STA.w SprYH,X
  LDA.b #$01 : STA.w SprMiscB,X
.done
  PLB : PLP : RTL
; Test a short cardinal connection, not only the destination. The endpoint
; is32px behind and optionally32px sideways. Side-first steps are8px and
; overlap16px footboxes; start, corners and every crossed tile stay checked.
.connected
  REP #$20
  LDA.b $08 : PHA
  LDA.b $0A : PHA
  LDA.b $22 : STA.b $08
  LDA.b $20 : STA.b $0A
  SEP #$20
  JSL D8Farore_CheckFootprintLong : BCS .connection_blocked
.connection_step
  REP #$20
  LDA.b $08 : CMP $03,S : BEQ .connection_y
  BCC .connection_right
  SEC : SBC.w #$0008 : STA.b $08 : BRA .connection_probe
.connection_right
  CLC : ADC.w #$0008 : STA.b $08 : BRA .connection_probe
.connection_y
  LDA.b $0A : CMP $01,S : BEQ .connection_clear
  BCC .connection_down
  SEC : SBC.w #$0008 : STA.b $0A : BRA .connection_probe
.connection_down
  CLC : ADC.w #$0008 : STA.b $0A
.connection_probe
  SEP #$20
  JSL D8Farore_CheckFootprintLong : BCC .connection_step
.connection_blocked
  SEC : BRA .connection_restore
.connection_clear
  CLC
.connection_restore
  REP #$20
  PLA : STA.b $0A
  PLA : STA.b $08
  SEP #$20
  RTS
.dx dw 0,-32,32, 0,-32,32, 32,32,32, -32,-32,-32
.dy dw 32,32,32, -32,-32,-32, 0,-32,32, 0,-32,32
}
; Existing D8 frames are16px wide, with the lower body ending atY+19.
; Native small-shadow glyph38 is8px wide: center it atX+4, Y+19. The
; native custom entry adds1px for the existing SmallShadow flag (E60 bit20).
; Its OBJ4 palette/glyph/page stay vanilla; D8 uploads only page1 tiles80+.
D8Farore_DrawGroundShadow:
{
  PHP
  JSL D8Farore_IsMember : BCC .done
  REP #$20
  LDA.b $00 : CLC : ADC.w #$0004
  ; Keep signed partial-left visibility and reject wholly clipped8px shadows.
  ; In particular, never fold a positive offscreen X through the9-bit OAM wrap.
  CMP.w #$0100 : BCC .visible_x
  CMP.w #$FFF9 : BCC .done
.visible_x
  STA.b $00
  SEP #$20
  LDA.b #$12
  JSL $06DC5C ; native SpriteDraw_Shadow_custom_long
.done
  PLP : RTL
}
D8Farore_FollowEnd:
