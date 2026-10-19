; D3 hall arrest. Transient ownership lives in two staged native guard slots;
; there is no new SRAM field, room-data marker, or generic contact capture.
; The pending blade receipt remains authoritative until the final transaction.
if !ENABLE_D3_PRISON_SEQUENCE == 1

!D3Prison_GuardLead = $E1
!D3Prison_GuardRear = $E2

if !ENABLE_DREAM_RETURN == 0
; When dream return is isolated off there is no shared Maple callback.
D3Prison_LinkMain:
{
  JSL $078000
  JML D3Prison_PlayerControl
}
pushpc
org $028947 ; @hook module=Dungeons name=D3Prison_LinkMain kind=jsl target=D3Prison_LinkMain expected_m=8 expected_x=8
  JSL D3Prison_LinkMain
pullpc
endif

; Room-independent saved-state check, also used by the cold-load selector.
; Preserve P except Carry, X/Y/DB. Native DP=0. A is scratch.
D3Prison_ShouldResumeHall:
{
  PHP
  SEP #$20
  LDA.l CastleAmbushFlags : AND.b #$0F
  CMP.b #!CastleAmbush_AmbushPending : BNE .no
  LDA.l Sword : CMP.b #$02 : BNE .no
  PLP : SEC : RTL
  .no
  PLP : CLC : RTL
}

; Called after Link_Main in the existing cooperative player callback.
; Preserve P, X/Y and DB; native module callback permits scratch A/DP.
D3Prison_PlayerControl:
{
  PHP
  REP #$10
  PHX : PHY : PHB
  PHK : PLB
  SEP #$30
  JSR D3Prison_InPlayerControl : BCS +
    JMP .done
  +
  ; An indoor load cancels any abandoned outdoor-message queue.
  LDA.b #$00 : STA.l D3Prison_ExitMessage : STA.l D3Prison_ExitMessage+1
  LDA.b $A0 : CMP.b #$56 : BEQ +
    JMP .done
  +
  JSR D3Prison_FindGuards : BCC .not_running
  JSL D3Prison_ShouldResumeHall : BCS .tick
  JMP .release
  .not_running
  ; A lost actor must not leave an orphaned scene lock. Exact marker tags
  ; identify ownership even if the slot's state was cleared unexpectedly.
  JSR D3Prison_ReleaseGuards
  JSL D3Prison_ShouldResumeHall : BCS +
    JMP .done
  +
  ; SW hall, after returning from the NW blade room. No direction test:
  ; a pending death/continue enters from the south and must still arrest.
  LDA.b $EE : ORA.b $5D : BEQ +
    JMP .done
  +
  LDA.w $02E4 : ORA.w $0FFC : BEQ + ; another scene owns Link
    JMP .done
  +
  REP #$20
  LDA.b $22 : CMP.w #$0C20 : BCC .outside
  CMP.w #$0CE0 : BCS .outside
  LDA.b $20 : CMP.w #$0B20 : BCC .outside
  CMP.w #$0BE0 : BCS .outside
  SEP #$20
  JSR D3Prison_StageGuards : BCC .done
  .tick
  ; The pair owns these locks only after both slots have been acquired.
  LDA.b #$01 : STA.w $02E4 : STA.w $0FFC : STA.w $0FC1
  LDA.w SprTimerF, X : CMP.b #$C1 : BCS .capture
  INC.w SprTimerF, X
  LDA.w SprTimerF, X : CMP.b #$C0 : BCS .taunt
  PHY
  JSR D3Prison_MoveGuard
  PLY
  LDA.w SprTimerF, X : STA.w SprTimerF, Y
  TYX
  JSR D3Prison_MoveGuard
  BRA .done
  .taunt
  JSL D3Prison_ShowCaptureTaunt
  BRA .done
  .capture
  JSL D3Prison_Capture : BCC .release
  ; Save the current room flags and keys through the native mirror fade.
  ; Capture must commit before this changes submodule00 to19.
  JSR D3Prison_ReleaseGuards
  STZ.b $AE : STZ.b $AF
  LDA.b #$01 : STA.w $010A
  LDA.b #$32 : STA.w $010E
  STZ.w $010F : STZ.w $04AA : STZ.w $04AB
  JSL $02A1B1 ; Mirror_SaveRoomData -> Module07_19 -> Module05 cell profile
  BRA .done
  .release
  JSR D3Prison_ReleaseGuards
  BRA .done
  .outside
  SEP #$20
  .done
  PLB
  REP #$10
  PLY : PLX
  PLP
  RTL
}

; Both exact markers are required; ordinary blue guards never own the scene.
; C=1, X=leader, Y=rear. Called with M8/X8 and our bank in DB.
D3Prison_FindGuards:
{
  LDX.b #$0F
  .lead
    LDA.w SprState, X : CMP.b #$09 : BNE .next_lead
    LDA.w SprType, X : CMP.b #$41 : BNE .next_lead
    LDA.w SprSubtype, X : CMP.b #!D3Prison_GuardLead : BEQ .find_rear
  .next_lead
    DEX : BPL .lead
  CLC : RTS
  .find_rear
  LDY.b #$0F
  .rear
    LDA.w SprState, Y : CMP.b #$09 : BNE .next_rear
    LDA.w SprType, Y : CMP.b #$41 : BNE .next_rear
    LDA.w SprSubtype, Y : CMP.b #!D3Prison_GuardRear : BEQ .found
  .next_rear
    DEY : BPL .rear
  CLC : RTS
  .found
  SEC : RTS
}

D3Prison_StageGuards:
{
  ; Acquire both free slots before writing any sprite or freezing Link.
  LDX.b #$0F
  .first
    LDA.w SprState, X : BEQ .have_first
    DEX : BPL .first
  CLC : RTS
  .have_first
  TXY
  .second
    DEY : BMI .no_room
    LDA.w SprState, Y : BNE .second
  PHX : PHY
  JSR D3Prison_InitGuard
  LDA.b #!D3Prison_GuardLead : STA.w SprSubtype, X
  LDA.b #$F0 : STA.w SprX, X
  LDA.b #$88 : STA.w SprY, X
  PLY : PHY : TYX
  JSR D3Prison_InitGuard
  LDA.b #!D3Prison_GuardRear : STA.w SprSubtype, X
  LDA.b #$F8 : STA.w SprX, X
  LDA.b #$98 : STA.w SprY, X
  PLY : PLX
  SEC : RTS
  .no_room
  CLC : RTS
}

D3Prison_InitGuard:
{
  LDA.b #$41 : STA.w SprType, X
  JSL $0DB818 ; native reset + properties + palette, before custom staging
  LDA.b #$09 : STA.w SprState, X
  LDA.b #$0C : STA.w SprXH, X
  LDA.b #$0B : STA.w SprYH, X
  LDA.b #$01 : STA.w SprMiscC, X : STA.w SprMiscE, X
  STA.w $0BA0, X ; no damage/recoil while the scene owns this guard
  LDA.b #$04 : STA.w SprGfx, X
  LDA.b #$FF : STA.w $0BC0, X ; not a saved room-list death slot
  STZ.w $0CBA, X : STZ.w SprFloor, X
  RTS
}

; Walk west from the east door, then approach north, then hold before fade.
; No native guard timer or AI is relied on while sprites are frozen.
D3Prison_MoveGuard:
{
  LDA.w SprTimerF, X : CMP.b #$61 : BCS .north
  DEC.w SprX, X
  LDA.b #$01 : STA.w SprMiscC, X : STA.w SprMiscE, X
  LDA.w SprTimerF, X : LSR #3 : AND.b #$03 : TAY
  LDA.w .left_frames, Y : STA.w SprGfx, X
  RTS
  .north
  CMP.b #$81 : BCS .hold
  DEC.w SprY, X
  LDA.b #$03 : STA.w SprMiscC, X : STA.w SprMiscE, X
  LDA.w SprTimerF, X : LSR #3 : AND.b #$03 : TAY
  LDA.w .up_frames, Y : STA.w SprGfx, X
  .hold
  RTS
  .left_frames
  db $04, $05, $06, $05
  .up_frames
  db $07, $08, $09, $0A
}

; Release a full or partial pair. A survivor's exact type/subtype proves
; scene ownership; ordinary room guards and unrelated locks stay untouched.
D3Prison_ReleaseGuards:
{
  LDY.b #$00
  LDX.b #$0F
  .next
  LDA.w SprType, X : CMP.b #$41 : BNE .skip
  LDA.w SprSubtype, X : CMP.b #!D3Prison_GuardLead : BEQ .owned
  CMP.b #!D3Prison_GuardRear : BNE .skip
  .owned
  STZ.w SprState, X : STZ.w SprSubtype, X
  INY
  .skip
  DEX : BPL .next
  TYA : BEQ .done
    STZ.w $02E4 : STZ.w $0FFC : STZ.w $0FC1
  .done
  RTS
}

; Module07 checks Select before Link_Main. Only pending arrest is vetoed;
; captured/reclaimed players may save normally through the cell checkpoint.
; Original contract: M8/X8, A/N/Z = $F0 & $20. X/Y/DB/other flags preserved.
D3Prison_SelectGate:
{
  PHP
  JSL D3Prison_ShouldResumeHall : BCC .native
  JSR D3Prison_InDungeon : BCC .native
  PLP
  LDA.b #$00
  RTL
  .native
  PLP
  LDA.b $F0 : AND.b #$20
  RTL
}

; The native item handler tests SFX3C after this long call. Reject only an
; active D3 transaction; the hall itself calls native02A1B1 directly to fade.
D3Prison_MirrorGate:
{
  PHP
  SEP #$20
  JSR D3Prison_InDungeon : BCC .native
  JSL D3Prison_ShouldResumeHall : BCS .blocked
  JSL D3Prison_ShouldResumeCell : BCC .native
  .blocked
  LDA.b #$3C : STA.l $7E012E
  PLP
  RTL
  .native
  PLP
  JML $02A1B1
}

; Module08 still has the indoor room/dungeon context at this hook. Native
; stores are replayed after the transaction, leaving ordinary exits intact.
D3Prison_RecordExit:
{
  PHP
  REP #$20
  PHA
  LDA.w #$0000 : STA.l D3Prison_ExitMessage
  SEP #$20
  JSL D3Prison_CompleteEscape : BCC .native
  REP #$20
  LDA.w #!D3Prison_ExitMessageLive : STA.l D3Prison_ExitMessage
  .native
  REP #$20
  PLA
  PLP
  STZ.b $1B : STZ.w $0458
  RTL
}

; Collision65 permits Moosh elsewhere. A prison wall's tiny gap is Minish
; only during captivity. Preserve caller widths and all flags except Carry.
D3Prison_IsTinyPrisonGap:
{
  PHP
  SEP #$20
  JSR D3Prison_InDungeon : BCC .no
  LDA.l $7E00A0 : CMP.b #$65 : BEQ .room
  CMP.b #$64 : BNE .no
  .room
  JSL D3Prison_ShouldResumeCell : BCC .no
  PLP : SEC : RTL
  .no
  PLP : CLC : RTL
}

pushpc
org $02891B ; @hook module=Dungeons name=D3Prison_SelectGate kind=jsl target=D3Prison_SelectGate expected_m=8 expected_x=8
  JSL D3Prison_SelectGate
assert pc() == $02891F
org $07A965 ; @hook module=Dungeons name=D3Prison_MirrorGate kind=jsl target=D3Prison_MirrorGate expected_m=8 expected_x=8
  JSL D3Prison_MirrorGate
assert pc() == $07A969
org $02E4A6 ; @hook module=Dungeons name=D3Prison_RecordExit kind=jsl target=D3Prison_RecordExit expected_m=8 expected_x=8
  JSL D3Prison_RecordExit
  NOP
assert pc() == $02E4AB
pullpc
endif
