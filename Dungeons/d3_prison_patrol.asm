; The two authored room64 soldiers patrol while the blade is confiscated.
; Exact initial positions acquire transient markers; no extra sprite or SRAM.
; Room54 and ordinary guards retain native behavior. The paired room recipe
; keeps the two patrol chambers empty of sight-blocking interior objects.
if !ENABLE_D3_PRISON_SEQUENCE == 1

!D3Prison_PatrolUpper = $E3
!D3Prison_PatrolLower = $E4

; Guard_Main entry: native M8/X8, DP0, DB05, X=sprite slot. Preserve all
; original flags/registers on fallback before replaying LDA SprGfx,X / PHA.
; The handled path skips both native AI and native player-damage processing.
D3Prison_PatrolDispatch:
{
  PHP : PHX : PHY : PHB
  PHK : PLB
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
  PHK : PLB
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
  PHK : PLB
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
  CMP.w .right_edge, Y : BCC .store_right
    LDA.w .right_edge, Y
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
  CMP.w .left_edge, Y : BEQ .turn_right
  BCS .store_left
  .turn_right
    LDA.w .left_edge, Y
    JSR .store_x
    STZ.w SprMiscC, X : STZ.w SprMiscE, X
    BRA .animate
  .store_left
  JSR .store_x
  .animate
  INC.w SprMiscD, X
  LDA.w SprMiscD, X : LSR #3 : AND.b #$03 : TAY
  LDA.w SprMiscC, X : BEQ .right_frame
    LDA.w .left_frames, Y
    BRA .frame
  .right_frame
  LDA.w .right_frames, Y
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
; The room's two empty open-floor rectangles bound sight, so the dividing
; wall, door tunnels and cell-wall gap never become transparent. Same floor
; is mandatory. No mask, Cape, invincibility or damage routine grants immunity.
; Preserves DP00..07 and all public-contract registers except scratch A.
D3Prison_PatrolCanSee:
{
  PHP : PHB
  PHK : PLB
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
  CMP.w #$0041 : BCC .yes
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

; Caller already established sight/contact. Revalidate before committing;
; the second guard in the same frame sees submodule19 and cannot retrigger.
; Preserve DP00..0F, X/Y/DB/P except Carry around the palette and mirror
; routines (both use scratch/index registers). No recapture/backup overwrite.
D3Prison_PatrolCaught:
{
  PHP : PHX : PHY : PHB
  PHK : PLB
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
