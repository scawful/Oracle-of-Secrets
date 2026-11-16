; The two authored room64 soldiers patrol while the blade is confiscated.
; Exact initial positions acquire transient markers; no extra sprite or SRAM.
; Room54 and ordinary guards retain native behavior. Full-solid masonry or
; opaque stacks outside the patrol rails can block the forward sight ray.
if !ENABLE_D3_PRISON_CELL65 == 1

!D3Prison_PatrolUpper = $E3
!D3Prison_PatrolLower = $E4

; Guard_Main entry: native M8/X8, DP0, DB05, X=sprite slot. Preserve all
; original flags/registers on fallback before replaying LDA SprGfx,X / PHA.
; The handled path skips both native AI and native player-damage processing.
D3Prison_PatrolDispatch:
{
  PHP : PHX : PHY : PHB
  LDA.b #$00 : PHA : PLB
  JSL D3Prison_PatrolInit : BCC .native
  JSL D3Prison_GuardMain
  SEP #$30
  PLB : PLY : PLX : PLP
  JML $05C226 ; native RTS, with its original caller still on the stack
  .native
  PLB : PLY : PLX : PLP
  LDA.w SprGfx, X : PHA
  JML $05C22B
}

; Public helper contract: native M8/X8, DP0, X=slot 0..15; A is scratch.
; Context/Init/CanSee/Caught preserve X/Y/DB and P except Carry. Step preserves
; P as well. No helper borrows auto-decrementing sprite timers for its phase.
; Context is independent of menu/fade state so the owned actors still draw.
D3Prison_PatrolContext:
{
  PHP
  LDA.l $7E001B : CMP.b #$01 : BNE .no
  LDA.l $7E040C : CMP.b #$10 : BNE .no
  LDA.l $7E00A1 : BNE .no
  LDA.l $7E00A0 : CMP.b #$64 : BNE .no
  LDA.l $7E0E20, X : CMP.b #$41 : BNE .no
  LDA.l $7E0DD0, X : CMP.b #$09 : BNE .no
  LDA.l CastleAmbushFlags : AND.b #$0F
  CMP.b #!CastleAmbush_HasBeenCaptured : BNE .no
  LDA.l Sword : BNE .no
  JSL D3Prison_ShouldResumeCell : BCC .no
  PLP : SEC : RTL
  .no
  PLP : CLC : RTL
}

; C=1 only for an acquired patrol. Idempotent after the first room tick.
; Writes only this slot's subtype, X/Y, facing, frame, phase, action and speed.
D3Prison_PatrolInit:
{
  PHP : PHB
  LDA.b #$00 : PHA : PLB
  JSL D3Prison_PatrolContext : BCC .no
  JSR D3Prison_PatrolOwned : BCS .yes
  LDA.w SprSubtype, X : BNE .no
  LDA.w SprXH, X : CMP.b #$08 : BNE .no
  LDA.w SprY, X : CMP.b #$60 : BNE .no
  LDA.w SprYH, X : CMP.b #$0C : BEQ .upper
  CMP.b #$0D : BNE .no
  LDA.w SprX, X : CMP.b #$80 : BNE .no
  LDA.b #!D3Prison_PatrolLower : STA.w SprSubtype, X
  LDA.b #$78 : STA.w SprY, X
  BRA .init
  .upper
  LDA.w SprX, X : CMP.b #$F0 : BNE .no
  LDA.b #!D3Prison_PatrolUpper : STA.w SprSubtype, X
  LDA.b #$80 : STA.w SprY, X
  .init
  STZ.w SprMiscC, X : STZ.w SprMiscE, X ; native direction0 = right
  STZ.w SprMiscD, X                    ; manual patrol animation phase
  STZ.w SprAction, X
  STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
  LDA.b #$0B : STA.w SprGfx, X
  .yes
  PLB : PLP : SEC : RTL
  .no
  PLB : PLP : CLC : RTL
}

; Private M8/X8 predicate. Caller supplies this code bank in DB.
D3Prison_PatrolOwned:
{
  LDA.w SprSubtype, X : CMP.b #!D3Prison_PatrolUpper : BEQ .yes
  CMP.b #!D3Prison_PatrolLower : BNE .no
  .yes
  SEC : RTS
  .no
  CLC : RTS
}

; Drawing continues while movement/sight stop for menus, text, transitions,
; and other scenes. Ignore offscreen SprPause: this deterministic route must
; not depend on which portion of the room happens to be on camera.
D3Prison_PatrolUnfrozen:
{
  LDA.b $10 : CMP.b #$07 : BNE .no
  LDA.b $11 : ORA.w $02E4 : ORA.w $0FFC : ORA.w $0FC1
  BNE .no
  SEC : RTS
  .no
  CLC : RTS
}

; Called only after Init acquired this slot. The native long draw wrapper
; owns bank05 and its offscreen early return; never JSL its internal JSR entry.
D3Prison_GuardMain:
{
  JSL $05C676 ; Guard_HandleAllAnimation_long; preserves X and DB
  SEP #$30
  JSL D3Prison_PatrolStep
  JSL D3Prison_PatrolCanSee : BCC .done
  JSL D3Prison_PatrolCaught
  .done
  RTL
}

; Advance one pixel per active tick, turning immediately on the inclusive
; endpoint. Only X position, facing, phase and frame change; DP is untouched.
D3Prison_PatrolStep:
{
  PHP : PHY : PHB
  LDA.b #$00 : PHA : PLB
  JSL D3Prison_PatrolContext : BCS +
    JMP .done
  +
  JSR D3Prison_PatrolOwned : BCS +
    JMP .done
  +
  JSR D3Prison_PatrolUnfrozen : BCS +
    JMP .done
  +
  LDY.b #$00
  LDA.w SprSubtype, X : CMP.b #!D3Prison_PatrolUpper : BEQ +
    LDY.b #$02
  +
  LDA.w SprMiscC, X : BNE .left
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  INC A
  PHB : PHK : PLB : CMP.w .right_edge, Y : PLB : BCC .store_right
    PHB : PHK : PLB : LDA.w .right_edge, Y : PLB
    JSR .store_x
    LDA.b #$01 : STA.w SprMiscC, X : STA.w SprMiscE, X
    BRA .animate
  .store_right
  JSR .store_x
  BRA .animate
  .left
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  DEC A
  PHB : PHK : PLB : CMP.w .left_edge, Y : PLB : BEQ .turn_right
  BCS .store_left
  .turn_right
    PHB : PHK : PLB : LDA.w .left_edge, Y : PLB
    JSR .store_x
    STZ.w SprMiscC, X : STZ.w SprMiscE, X
    BRA .animate
  .store_left
  JSR .store_x
  .animate
  INC.w SprMiscD, X
  LDA.w SprMiscD, X : LSR #3 : AND.b #$03 : TAY
  LDA.w SprMiscC, X : BEQ .right_frame
    PHB : PHK : PLB : LDA.w .left_frames, Y : PLB
    BRA .frame
  .right_frame
  PHB : PHK : PLB : LDA.w .right_frames, Y : PLB
  .frame
  STA.w SprGfx, X
  .done
  PLB : PLY : PLP
  RTL
  .store_x
  SEP #$20
  STA.w SprX, X : XBA : STA.w SprXH, X
  RTS
  .left_edge
  dw $0840, $0880
  .right_edge
  dw $0980, $09B0
  ; usdasm GuardBodySteps $05C339: direction0 right, direction1 left.
  .right_frames
  db $0B, $0C, $0D, $0C
  .left_frames
  db $04, $05, $06, $05
}

; C=1 for contact (both axes <=12px) or a 64px forward sight strip (Y<=12).
; The two chamber rectangles bound sight; a feet-centre collision ray then
; rejects full-solid cover ($01/$02). Contact is unchanged. Same floor
; is mandatory. No mask, Cape, invincibility or damage routine grants immunity.
; Preserves DP00..07 and all public-contract registers except scratch A.
D3Prison_PatrolCanSee:
{
  PHP : PHB
  LDA.b #$00 : PHA : PLB
  JSL D3Prison_PatrolContext : BCC .early_no
  JSR D3Prison_PatrolOwned : BCC .early_no
  JSR D3Prison_PatrolUnfrozen : BCC .early_no
  LDA.b $EE : CMP.w SprFloor, X : BEQ .eligible
  .early_no
  PLB : PLP : CLC : RTL
  .eligible
  REP #$20
  LDA.b $00 : PHA
  LDA.b $02 : PHA
  LDA.b $04 : PHA
  SEP #$20
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  STA.b $00
  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  STA.b $02
  LDA.b $22 : CMP.w #$0830 : BCS +
    BRL .no
  +
  CMP.w #$09D0 : BCC +
    BRL .no
  +
  LDA.b $00 : CMP.w #$0830 : BCS +
    BRL .no
  +
  CMP.w #$09D0 : BCC +
    BRL .no
  +
  SEP #$20
  LDA.w SprSubtype, X : CMP.b #!D3Prison_PatrolUpper : BNE .lower
  REP #$20
  LDA.b $20 : CMP.w #$0C30 : BCC .no
  CMP.w #$0CD0 : BCS .no
  LDA.b $02 : CMP.w #$0C30 : BCC .no
  CMP.w #$0CD0 : BCS .no
  BRA .delta
  .lower
  REP #$20
  LDA.b $20 : CMP.w #$0D30 : BCC .no
  CMP.w #$0DD0 : BCS .no
  LDA.b $02 : CMP.w #$0D30 : BCC .no
  CMP.w #$0DD0 : BCS .no
  .delta
  LDA.b $20 : SEC : SBC.b $02
  CLC : ADC.w #$000C : CMP.w #$0019 : BCS .no
  LDA.b $22 : SEC : SBC.b $00 : STA.b $04
  CLC : ADC.w #$000C : CMP.w #$0019 : BCC .yes ; contact behind too
  SEP #$20
  LDA.w SprMiscC, X : BEQ .right
  REP #$20
  LDA.b $04 : EOR.w #$FFFF : INC A
  BRA .range
  .right
  REP #$20
  LDA.b $04
  .range
  CMP.w #$0041 : BCS .no
  JSR D3Prison_PatrolSightClear : BCS .yes
  .no
  REP #$20
  PLA : STA.b $04
  PLA : STA.b $02
  PLA : STA.b $00
  SEP #$20
  PLB : PLP : CLC : RTL
  .yes
  REP #$20
  PLA : STA.b $04
  PLA : STA.b $02
  PLA : STA.b $00
  SEP #$20
  PLB : PLP : SEC : RTL
}

; Private M16/X8, DB0, DP0; $00/$02=guard origin, $04=signed dx.
; Caller proves 13..64 forward pixels, |dy|<=12 and same floor. Feet centres
; are (+8,+12), independent of OAM head position. Traverse Tile8 boundaries,
; comparing cross-products instead of dividing: tX=distanceX*abs(dy),
; tY=distanceY*abs(dx), end=abs(dx*dy). At an exact corner test both side
; cells before the diagonal. A horizontal ray uses dy=1 and tY=$FFFF.
; At most nine X and two Y crossings; no per-pixel loop or persistent RAM.
; Loaded collision indexing matches native $06E89A-$06E8B4. Only full-solid
; attrs $01/$02 are opaque: the room must bind these to full-height masonry
; or opaque stacks. Low props/rails sharing them are NOT certified cover.
; Slopes, water, pits, door triggers and custom attrs are not inferred opaque.
; Preserves X/Y/P except Carry and DP06..0F. Caller restores DP00..05.
; $10 onward is module/NMI state and must never be borrowed, even briefly.
D3Prison_PatrolSightClear:
{
  PHP : REP #$30 : PHX : PHY
  LDA.b $06 : PHA
  LDA.b $08 : PHA
  LDA.b $0A : PHA
  LDA.b $0C : PHA
  LDA.b $0E : PHA
  ; Steps in the collision array; boundary deltas are scaled by eight.
  LDA.w #$0001 : STA.b $0A
  LDA.b $04 : BPL .dx
    LDA.w #$FFFF : STA.b $0A
    LDA.b $04 : EOR.w #$FFFF : INC A
  .dx
  ASL #3 : STA.b $08
  LDA.w #$0040 : STA.b $0C
  LDA.b $20 : SEC : SBC.b $02 : BEQ .horizontal
  BPL .dy
    LDA.w #$FFC0 : STA.b $0C
    LDA.b $20 : SEC : SBC.b $02 : EOR.w #$FFFF : INC A
  .dy
  ASL #3 : STA.b $06
  BRA .product
  .horizontal
  STZ.b $0C
  LDA.w #$0008 : STA.b $06
  .product
  LDA.b $06 : LSR #3 : TAY
  LDA.b $08 : LSR #3 : STA.b $04
  LDA.w #$0000
  .multiply_end
  CLC : ADC.b $04 : DEY : BNE .multiply_end
  STA.b $0E
  ; First X boundary, including an immediate crossing when facing left
  ; from an exact boundary. Multiplication runs at most eight additions.
  LDA.b $00 : CLC : ADC.w #$0008 : AND.w #$0007 : STA.b $04
  LDA.b $0A : BMI .left_distance
  LDA.w #$0008 : SEC : SBC.b $04 : BRA .x_count
  .left_distance
  LDA.b $04
  .x_count
  TAY : LDA.w #$0000
  CPY.w #$0000 : BEQ .x_ready
  .multiply_x
  CLC : ADC.b $06 : DEY : BNE .multiply_x
  .x_ready
  LSR #3 : STA.b $04
  ; First Y boundary; horizontal rays never enter another row.
  LDA.b $0C : BEQ .y_horizontal
  BMI .up_distance
  LDA.b $02 : CLC : ADC.w #$000C : AND.w #$0007
  EOR.w #$FFFF : CLC : ADC.w #$0009 : BRA .y_count
  .up_distance
  LDA.b $02 : CLC : ADC.w #$000C : AND.w #$0007
  .y_count
  TAY : LDA.w #$0000
  CPY.w #$0000 : BEQ .y_ready
  .multiply_y
  CLC : ADC.b $08 : DEY : BNE .multiply_y
  .y_ready
  LSR #3 : BRA .save_y
  .y_horizontal
  LDA.w #$FFFF
  .save_y
  PHA
  ; Current Tile8 index and floor. Guard/player share the floor by contract.
  LDA.b $00 : CLC : ADC.w #$0008 : AND.w #$01F8 : LSR #3 : STA.b $00
  LDA.b $02 : CLC : ADC.w #$000C : AND.w #$01F8 : ASL #3
  ORA.b $00 : STA.b $00
  LDA.b $EE : AND.w #$00FF : BEQ .plane_ready
    LDA.b $00 : ORA.w #$1000 : STA.b $00
  .plane_ready
  LDA.b $04 : STA.b $02
  PLA : STA.b $04
  .visit
  LDX.b $00 : JSR .cell : BCC .blocked
  LDA.b $02 : CMP.b $04 : BCC .cross_x
  BEQ .corner
  ; Y is the next boundary; crossing after the endpoint is not part of ray.
  LDA.b $04 : CMP.b $0E : BCC .cross_y
  BEQ .cross_y
  BRA .clear
  .cross_y
  LDA.b $00 : CLC : ADC.b $0C : STA.b $00
  LDA.b $04 : CLC : ADC.b $08 : STA.b $04
  BRA .visit
  .cross_x
  CMP.b $0E : BCC .do_x
  BEQ .do_x
  BRA .clear
  .do_x
  LDA.b $00 : CLC : ADC.b $0A : STA.b $00
  LDA.b $02 : CLC : ADC.b $06 : STA.b $02
  BRA .visit
  .corner
  CMP.b $0E : BCC .do_corner
  BEQ .do_corner
  BRA .clear
  .do_corner
  LDA.b $00 : CLC : ADC.b $0A : TAX
  JSR .cell : BCC .blocked
  LDA.b $00 : CLC : ADC.b $0C : TAX
  JSR .cell : BCC .blocked
  LDA.b $00 : CLC : ADC.b $0A : CLC : ADC.b $0C : STA.b $00
  LDA.b $02 : CLC : ADC.b $06 : STA.b $02
  LDA.b $04 : CLC : ADC.b $08 : STA.b $04
  BRA .visit
  .clear
  SEC : BRA .restore
  .blocked
  CLC
  .restore
  PLA : STA.b $0E
  PLA : STA.b $0C
  PLA : STA.b $0A
  PLA : STA.b $08
  PLA : STA.b $06
  PLY : PLX
  BCC .no
  PLP : SEC : RTS
  .no
  PLP : CLC : RTS
  .cell
  LDA.l $7F2000, X : AND.w #$00FF
  CMP.w #$0001 : BEQ .solid
  CMP.w #$0002 : BEQ .solid
  SEC : RTS
  .solid
  CLC : RTS
}

; Caller already established sight/contact. Revalidate before committing;
; the second guard in the same frame sees submodule19 and cannot retrigger.
; Preserve DP00..0F, X/Y/DB/P except Carry around the palette and mirror
; routines (both use scratch/index registers). No recapture/backup overwrite.
D3Prison_PatrolCaught:
{
  PHP : PHX : PHY : PHB
  LDA.b #$00 : PHA : PLB
  JSL D3Prison_PatrolContext : BCC .no
  JSR D3Prison_PatrolOwned : BCC .no
  JSR D3Prison_PatrolUnfrozen : BCC .no
  JSL D3Prison_RestartEscape : BCC .no
  LDY.b #$0F
  .save_dp
    LDA.w $0000, Y : PHA
  DEY : BPL .save_dp
  ; MirrorFade reloads the file/room but does not reset Oracle's mask byte.
  ; Use the existing graphics/palette reset, without another transform cloud.
  JSL ResetToLinkGraphics
  SEP #$30
  STZ.w MinishPortalTimer : STZ.w MinishPortalFrame
  STZ.b $5D
  STZ.b $AE : STZ.b $AF
  LDA.b #$01 : STA.w $010A
  LDA.b #$32 : STA.w $010E
  STZ.w $010F : STZ.w $04AA : STZ.w $04AB
  JSL $02A1B1 ; saves keys/room flags and starts Module07_19 -> cell profile
  SEP #$30
  LDY.b #$00
  .restore_dp
    PLA : STA.w $0000, Y
  INY : CPY.b #$10 : BNE .restore_dp
  PLB : PLY : PLX : PLP
  SEC : RTL
  .no
  PLB : PLY : PLX : PLP
  CLC : RTL
}

pushpc
assert read4($05C227) == $480DC0BD, "Unexpected native Guard_Main prologue"
org $05C227 ; @hook module=Dungeons name=D3Prison_PatrolDispatch kind=jml target=D3Prison_PatrolDispatch expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JML D3Prison_PatrolDispatch
assert pc() == $05C22B
pullpc

endif
