; Gated sprite-stream helper. Caller owns stable gameplay, placed actor and
; presence policy1. No new state, input ownership, warp or new artwork.
; Requires a long wrapper for the existing four-corner footprint checker.
D8Farore_FollowStart:
D8Farore_Follow:
{
  PHP : PHB : PHK : PLB
  SEP #$30
  LDA.w SprFloor,X : CMP.b $EE : BNE .done
  LDA.b $5D : BNE .done ; don't chase while Link is using a special movement state
  ; One pixel per ordinary frame; retain a24px following gap on either axis.
  JSR .position
  REP #$20
  LDA.b $22 : SEC : SBC.b $08
  BPL .right
  EOR.w #$FFFF : INC : CMP.w #$0019 : BCC .try_y
  DEC.b $08 : BRA .check_x
.right
  CMP.w #$0019 : BCC .try_y
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
  EOR.w #$FFFF : INC : CMP.w #$0019 : BCC .no_move
  DEC.b $0A
  SEP #$20
  JSL D8Farore_CheckFootprintLong : BCS .done
  JSR .commit
  ; Original north walking frames only; no invented horizontal/south walk art.
  LDA.b $1A : LSR #3 : AND.b #$01 : CLC : ADC.b #$03
  STA.w SprGfx,X
  BRA .done
.down
  CMP.w #$0019 : BCC .no_move
  INC.b $0A
  SEP #$20
  JSL D8Farore_CheckFootprintLong : BCS .done
  JSR .commit
.no_move
  SEP #$20
  STZ.w SprGfx,X
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
D8Farore_FollowEnd:
