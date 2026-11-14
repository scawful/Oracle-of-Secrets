; Private reservoir/service bay and one-time inlet. Default off.
; Preserve legacy bits01/02.08 retains the earlier maintenance-latch meaning;
; 220/221 prototype04/08 saves do not grant inlet10 until a new High release.
!D4Water_High = $04
!D4Water_Latch = $08
!D4Water_Inlet = $10

pushpc
org $018745 ; @hook module=Dungeons name=D4Water_SelectObjects kind=jsl target=D4Water_SelectObjects expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16 protected_size=12
  assert read1($018745) == $BF && read2($018749) == $B885
  assert read1($01874B) == $BF && read2($01874F) == $B785
  !D4Water_ObjectTable = read3($01874C)
  assert read3($018746) == !D4Water_ObjectTable+1
  JSL D4Water_SelectObjects
  NOP #8
assert pc() == $018751

; LoadRoom restores the ROM-table pointer after drawing the shared layout.
; Select again here so the object lists use the same state as the floor header.
; M16/X16, D0, X=room*3; selector preserves X/Y/DBR and returns M16/X16.
org $01883E ; @hook module=Dungeons name=D4Water_SelectObjectLists kind=jsl target=D4Hub_RecoverBeforeRoomLoad expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16 protected_size=12
  assert read4($01883E) == $1F8001BF && read2($018842) == $B885
  assert read4($018844) == $1F8000BF && read2($018848) == $B785
  assert read3($01883F) == !D4Water_ObjectTable+1
  assert read3($018845) == !D4Water_ObjectTable
  ; This mandatory LoadRoom path still owns the old actors and ROOMCOPY.
  ; Recover custody after shared layout drawing, before native sprite reset.
  JSL D4Hub_RecoverBeforeRoomLoad
  JSL D4Water_SelectObjects
  NOP #4
assert pc() == $01884A

if !ENABLE_DREAM_RETURN == 0
org $028947 ; @hook module=Dungeons name=D4Water_PlayerControl kind=jsl target=D4Water_PlayerControl expected_m=8 expected_x=8 protected_size=4
  assert read4($028947) == $07800022
  JSL D4Water_PlayerControl
endif

; Native correct/wrong pull-switch bounce. Preserve all non-hub behavior.
org $06C003 ; @hook module=Dungeons name=D4Hub_ManualSwitch kind=jsl target=D4Hub_ManualSwitch expected_m=8 expected_x=8 protected_size=4
  assert read4($06C003) == $05D6BC22
  JSL D4Hub_ManualSwitch
assert pc() == $06C007

; Native down-pull input gate: LDA F2 / BPL +22 / LDA F0.
; The following AND03/BNE no_pull stays native; denied input returns03.
org $05D9F3 ; @hook module=Dungeons name=D4Hub_ManualInput kind=jsl target=D4Hub_ManualInput expected_m=8 expected_x=8 protected_size=6
  assert read4($05D9F3) == $2210F2A5 && read2($05D9F7) == $F0A5
  JSL D4Hub_ManualInput
  NOP #2
assert pc() == $05D9F9

; Vanilla drops follower09 before death/SaveQuit serialization. Earlier06/0D/0A
; branches still target09F558; this replaces only CMP09/BNE keep.
org $09F554 ; @hook module=Dungeons name=D4Hub_SaveFollower kind=jml target=D4Hub_SaveFollower expected_m=8 expected_x=8 protected_size=4
  assert read4($09F554) == $06D009C9, "Native follower09 purge moved"
  JML D4Hub_SaveFollower
assert pc() == $09F558

org $508000
D4Water_Start:
; Slot is explicitly reserved in allocation_ownership.json, not graphics padding.
for d4_preimage = $508000..$50A000
  assert read1(!d4_preimage) == $00, "D4 water slot preimage is occupied"
endfor

D4Water_SelectObjects:
{
  ; Entry D=0, M16/X16; X=room*3. Preserve X/Y/DBR and reproduce pointer result.
  LDA.l $7E00A0 : CMP.w #$0025 : BEQ .dam
  CMP.w #$0026 : BEQ .reservoir
  CMP.w #$0037 : BEQ .spillway
  .original
  LDA.l !D4Water_ObjectTable+1,X : STA.b $B8
  LDA.l !D4Water_ObjectTable,X : STA.b $B7
  RTL
  .dam
  SEP #$20
  STZ.b $AD ; still water in both states; inherited effect03 adds a left current
  LDA.l WaterGateStates : AND.b #!D4Water_High : BEQ .dam_low
  REP #$20
  LDA.w #D4Water25High>>8 : STA.b $B8
  LDA.w #D4Water25High : STA.b $B7
  RTL
  .dam_low
  STZ.b $AD
  REP #$20
  LDA.w #D4Water25Low>>8 : STA.b $B8
  LDA.w #D4Water25Low : STA.b $B7
  RTL
  .reservoir
  SEP #$20
  LDA.l WaterGateStates : AND.b #!D4Water_High : BEQ .reservoir_low
  REP #$20
  LDA.w #D4Water26High>>8 : STA.b $B8
  LDA.w #D4Water26High : STA.b $B7
  RTL
  .reservoir_low
  REP #$20
  LDA.w #D4Water26Low>>8 : STA.b $B8
  LDA.w #D4Water26Low : STA.b $B7
  RTL
  .spillway
  SEP #$20
  LDA.l WaterGateStates : AND.b #!D4Water_Inlet : BNE .spill_open
  REP #$20
  LDA.w #D4Water37Closed>>8 : STA.b $B8
  LDA.w #D4Water37Closed : STA.b $B7
  RTL
  .spill_open
  REP #$20
  JMP .original ; restore the original flooded room, not another water state

}

D4Water_PlayerControl:
  if !ENABLE_DREAM_RETURN == 1
    JSL DreamReturn_PlayerControl
  else
    JSL $078000
  endif
  JSL D4Water_Tick
  RTL

D4Water_Tick:
{
  ; Called after Link_Main. No input handling during transitions, menus or dives.
  PHP : REP #$30
  PHA : PHX : PHY : PHB : PHD
  LDA.w #$0000 : TCD
  SEP #$20
  LDA.b #$7E : PHA : PLB
  LDA.b $10 : CMP.b #$07 : BNE .done_near
  LDA.b $11 : ORA.w $02E4 : ORA.w $0FFC : BNE .done_near
  REP #$20
  LDA.b $A0 : CMP.w #$0025 : BNE +
  JMP .dam
  +
  CMP.w #$0026 : BEQ .collision_only
  CMP.w #$0037 : BEQ .collision_only
  .done_near
  JMP .done
  .collision_only
  JSR D4Water_ApplyCollision
  JMP .done
  .dam
  JSR D4Water_ApplyCollision
  JSR D4Hub_ReconcileRemotePose
  JMP .done
  .done
  REP #$30
  PLD : PLB : PLY : PLX : PLA : PLP
  RTL
}

; M16/X16, D0/DBR7E from Tick. Preserve its DP scratch, leave M16/X16.
; One native collision cell is a load sentinel, avoiding a full replay per frame.
; Each table starts with a deliberate native-load control cell; the focused
; native caller checks every run, not just this fast-path sentinel.
D4Water_ApplyCollision:
{
  LDA.b $08 : PHA
  LDA.b $0A : PHA
  LDA.b $0C : PHA
  LDA.b $A0 : CMP.w #$0025 : BNE .check26
  SEP #$20
  LDA.l WaterGateStates : AND.b #!D4Water_High : BEQ .low25
  REP #$20
  LDA.w #D4Water25HighCollision : BRA .pointer
  .low25
  REP #$20
  LDA.w #D4Water25LowCollision : BRA .pointer
  .check26
  CMP.w #$0026 : BNE .room37
  SEP #$20
  LDA.l WaterGateStates : AND.b #!D4Water_High : BEQ .low26
  JMP .done ; High26 keeps freshly loaded native collision
  .low26
  REP #$20
  LDA.w #D4Water26LowCollision : BRA .pointer
  .room37
  SEP #$20
  LDA.l WaterGateStates : AND.b #!D4Water_Inlet : BEQ .closed37
  JMP .done ; open37 uses the original stream and native collision unchanged
  .closed37
  REP #$20
  LDA.w #D4Water37ClosedCollision
  .pointer
  STA.b $08
  SEP #$20
  LDA.b #$50 : STA.b $0A
  REP #$20
  LDY.w #$0000
  ; A terminator-only profile owns no collision writes. Check before the
  ; first-run sentinel reads offset+3 or uses $FFFF as a collision index.
  LDA.b [$08],Y : CMP.w #$FFFF : BEQ .done
  TAX
  LDY.w #$0003
  SEP #$20
  LDA.b [$08],Y : CMP.l $7F2000,X : BEQ .done
  REP #$20
  LDY.w #$0000
  .next
  LDA.b [$08],Y : CMP.w #$FFFF : BEQ .done
  TAX : INY #2
  LDA.b [$08],Y : STA.b $0C
  INY #2
  SEP #$20
  .run
  LDA.b $0D : STA.l $7F2000,X
  INX : DEC.b $0C : BNE .run
  REP #$20
  BRA .next
  .done
  REP #$30
  PLA : STA.b $0C
  PLA : STA.b $0A
  PLA : STA.b $08
  RTS
}
D4Water26LowCollision: incbin "Data/Rooms/d4_water/26-low-collision.bin"
D4Water25LowCollision:  incbin "Dungeons/generated/d4_water/25-low-collision.bin"
D4Water25HighCollision: incbin "Dungeons/generated/d4_water/25-high-collision.bin"
D4Water37ClosedCollision: incbin "Data/Rooms/d4_water/37-closed-collision.bin"

D4Water26Low:  incbin "Data/Rooms/d4_water/26-low.bin"
D4Water26High: incbin "Data/Rooms/d4_water/26-high.bin"
D4Water25Low:  incbin "Dungeons/generated/d4_water/25-low.bin"
D4Water25High: incbin "Dungeons/generated/d4_water/25-high.bin"
D4Water37Closed: incbin "Data/Rooms/d4_water/37-closed.bin"
assert D4HubContactsBound == 1, "Enabled D4 hub requires generated accepted contacts"
; Same existing state/save/reload operations, now owned by completed manual04.
; D0/DBR7E, M8 entry, A/X scratch; both callers restore their own entry status.
D4Water_ToggleAndReload:
{
  LDA.l WaterGateStates : EOR.b #!D4Water_High
  BIT.b #!D4Water_High : BEQ .store_water
  ORA.b #!D4Water_Inlet ; monotonic: lowering never clears the released inlet
  .store_water
  STA.l WaterGateStates
  LDA.b #$25 : STA.w $012F
  ; Reproduce Underworld_SaveRoomData before the normal same-room warp reload.
  ; Keep collected chests/keys and open doors; no room flag or inventory reset.
  REP #$30
  LDA.b $A0 : ASL : TAX
  LDA.w $0402 : LSR #4 : PHA
  LDA.w $0400 : AND.w #$F000 : ORA.w $0408
  ORA $01,S : STA.l $7EF000,X
  PLA
  LDA.b $A0 : STA.b $A2
  SEP #$20
  STZ.b $B0 : STZ.w $0200
  LDA.b #$15 : STA.b $11
  SEP #$30
  RTS
}

; Existing native04 bounce, M8/X8/D0/X=actor, RAM-mirror DBR.
; Per-actor SprAction is unused by vanilla04.1=observed Link pull;2=completion.
D4Hub_ManualSwitch:
{
  PHP : REP #$20 : PHA : SEP #$20 : PHB
  LDA.b #$7E : PHA : PLB
  JSR D4Hub_IsPairedRemote : BCC .check_manual
  JSR D4Hub_DrawRemote
  JMP .done
  .check_manual
  JSR D4Hub_IsManual : BCS .scoped
  PLB : REP #$20 : PLA : PLP
  JML $05D6BC ; exact ordinary callee/return flags, originalA/DBR/P restored
  .scoped
  ; Before08, a broken pair cancels only this native Link episode. Never
  ; continue the native animation far enough to publish a stale completion.
  LDA.l WaterGateStates : AND.b #!D4Water_Latch : BNE .run_native
  LDA.w SprAction, X : BEQ .run_native
  JSR D4Hub_PairHeld : BCS .run_native
  STZ.w SprAction, X : STZ.w SprGfx, X : STZ.w SprTimerA, X
  STZ.w $0642
  JMP .done
  .run_native
  LDA.w SprGfx, X : PHA
  JSL $05D6BC
  PLA : BNE .after_start
  LDA.w SprGfx, X : CMP.b #$01 : BNE .after_start
  LDA.b #$01 : STA.w SprAction, X
  STZ.w $0642 ; this newly observed Link episode owns future completion
  .after_start
  LDA.w SprGfx, X : BNE +
  STZ.w SprAction, X ; native cancellation/reset discards episode ownership
  +
  LDA.w SprAction, X : CMP.b #$01 : BNE .pending
  LDA.w SprGfx, X : CMP.b #$0D : BNE .done
  LDA.w $0642 : BEQ .done
  STZ.w $0642
  LDA.b #$02 : STA.w SprAction, X
  .pending
  LDA.w SprAction, X : CMP.b #$02 : BNE .done
  LDA.b $10 : CMP.b #$07 : BNE .done
  LDA.b $11 : ORA.w $02E4 : ORA.w $0FFC : BNE .done
  LDA.l WaterGateStates : AND.b #!D4Water_Latch : BNE .unlocked
  JSR D4Hub_PairHeld : BCC .done
  ; Y is the reciprocal, fully bound Baby. Handoff must finish before reload
  ; discards actors. Existing follower serialization owns the recovered Baby.
  PHX : TYX
  JSL ZoraBaby_EnterFollower
  PLX
  LDA.l WaterGateStates : ORA.b #!D4Water_Latch : STA.l WaterGateStates
  ; First completion visibly raises High; preserve legacy01/02 and inlet10.
  AND.b #$FB : STA.l WaterGateStates
  .unlocked
  ; The real room reload/prep resets the completed native pull, not a forced
  ; mid-animation restart. No repeated commit before the reload begins.
  LDA.b #$03 : STA.w SprAction, X
  JSL D4Hub_ToggleFromManual
  .done
  PLB : REP #$20 : PLA : PLP
  RTL
}

; Replaces05D9F3 LDA F2/BPL(no_pull)/LDA F0. The following native AND03/BNE
; remains. A=03 routes blocked/not-pressed cases to exactly the native no_pull.
; M8/X8/D0; preserveX/Y/DBR/D and originalC/V/D/I. Next AND supplies nativeNZ.
D4Hub_ManualInput:
{
  PHP : PHX : PHY
  XBA : PHA : XBA ; preserve hidden accumulator high byte as native LDA does
  JSR D4Hub_IsManual : BCC .ordinary
  LDA.l WaterGateStates : AND.b #!D4Water_Latch : BNE .available
  JSR D4Hub_PairHeld : BCC .blocked
  .available
  LDA.b $10 : CMP.b #$07 : BNE .blocked
  LDA.b $11 : ORA.w $02E4 : ORA.w $0FFC : BNE .blocked
  LDA.b $5D : ORA.w $0308 : ORA.w $0309 : BNE .blocked
  LDA.b $EE : BNE .blocked
  LDA.w $0AAB : BNE .blocked
  .ordinary
  LDA.b $F2 : BPL .blocked
  LDA.b $F0 : BRA .done
  .blocked
  LDA.b #$03
  .done
  PHA
  LDA $02,S : XBA : PLA ; restore hiddenB, retain replacement lowA
  PLY ; discard savedB, then restore callerY/X/P
  PLY : PLX : PLP
  RTL
}

; LeavesX unchanged. Full actor identity and coordinates, not low-byte aliases.
; Called with M8/X8/D0 and RAM-mirror DBR (05,06,7E).
D4Hub_IsManual:
{
  LDA.b $1B : BEQ .no
  LDA.b $A0 : CMP.b #$25 : BNE .no
  LDA.b $A1 : BNE .no
  LDA.l D4HubContacts : CMP.b #$01 : BEQ .format
  CMP.b #$02 : BNE .no
  .format
  LDA.l D4HubContacts+1 : CMP.b #$01 : BNE .no
  LDA.w SprType, X : CMP.b #$04 : BNE .no
  LDA.w SprState, X : CMP.b #$09 : BNE .no
  LDA.w SprFloor, X : BNE .no
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  CMP.l D4HubContacts+6 : BNE .no16
  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  CMP.l D4HubContacts+8 : BNE .no16
  SEP #$20 : SEC : RTS
  .no16
  SEP #$20
  .no
  CLC : RTS
}

; Shared water transition wrapper.08 is awarded by the scoped completed
; native Link episode above, before this normal transition. Preserve fullA/X/Y/P/D/DBR.
D4Hub_ToggleFromManual:
{
  PHP : REP #$30
  PHA : PHX : PHY : PHB : PHD
  LDA.w #$0000 : TCD
  SEP #$20
  LDA.b #$7E : PHA : PLB
  JSR D4Water_ToggleAndReload
  REP #$30
  PLD : PLB : PLY : PLX : PLA : PLP
  RTL
}

; Room25-only backend. Uses existing actor-ownedSprAction7..C; no newRAM,
; SRAM or inputlock. Paired pull uses the native actor animation timer only.
; Exit/death/SaveQuit custody requires the separate supported lifecycle boundary.
; Publicentries D0/X=Baby/MX8, preserveDBR/P (returnMX8); A/Y,DP00-07scratch.
ZoraBaby_Room25AwaitSwitch:
{
  PHP : PHB : SEP #$30
  LDA.b #$7E : PHA : PLB
  LDA.b $1B : BEQ .cancel
  LDA.w SprAction, X : CMP.b #$0A : BNE .cancel
  LDA.b $A0 : CMP.b #$25 : BNE .cancel
  LDA.b $A1 : BNE .cancel
  LDA.w SprState, X : CMP.b #$09 : BNE .cancel
  LDA.w SprFloor, X : BNE .cancel
  LDA.l D4HubContacts : CMP.b #$02 : BNE .legacy
  JSR D4Hub_PairedAwait
  BRA .done
  .legacy
  JSR ZoraBaby_Room25FindSwitch : BCC .cancel
  LDA.w SprAction, Y : CMP.b #$01 : BEQ .done
  CMP.b #$02 : BNE .cancel
  LDA.w SprFrame, Y : CMP.b #$0A : BNE .cancel
  LDA.w $0642 : BEQ .cancel
  LDA.w SprHeight, X : BNE .done
  STZ.w $0642               ; consume only this owned completed21 event
  LDA.l WaterGateStates : ORA.b #!D4Water_Latch : STA.l WaterGateStates
  LDY.b #$01 : LDA.b #$07
  JSL Sprite_ShowMessageUnconditional
  LDA.b #$0B : STA.w SprAction, X
  BRA .done                ; only unlock08 is earned; no level or inlet mutation
  .cancel
  LDA.b #$04 : STA.w SprAction, X
  BRA .done
  .done
  PLB : PLP : SEP #$30
  RTL
}

ZoraBaby_Room25FindSwitch:
{
  LDY.b #$0F
  .scan
  LDA.w SprState, Y : CMP.b #$09 : BNE .next
  LDA.l D4HubContacts : CMP.b #$02 : BEQ .paired
  CMP.b #$01 : BNE .not_found
  LDA.w SprType, Y : CMP.b #$21 : BRA .type
  .paired
  LDA.w SprType, Y : CMP.b #$04
  .type
  BNE .next
  LDA.l D4HubContacts+1 : CMP.b #$01 : BNE .not_found
  LDA.w SprFloor, Y : BNE .next
  LDA.w SprXH, Y : CMP.l D4HubContacts+3 : BNE .next
  LDA.w SprX, Y : CMP.l D4HubContacts+2 : BNE .next
  LDA.w SprYH, Y : CMP.l D4HubContacts+5 : BNE .next
  LDA.w SprY, Y : CMP.l D4HubContacts+4 : BNE .next
  SEC : RTS
  .next
  DEY : BPL .scan
  .not_found
  CLC : RTS
}

ZoraBaby_Room25Global:
{
  PHP : PHB : SEP #$30
  LDA.b #$7E : PHA : PLB
  LDA.b $1B : BEQ .outside
  LDA.b $A0 : CMP.b #$25 : BNE .outside
  LDA.b $A1 : BEQ .room25
  .outside
  ; Scoped state never persists across an actual room departure.
  LDA.w SprAction, X : CMP.b #$07 : BCC .not_handled
  CMP.b #$0D : BCS .not_handled
  LDA.b #$04 : STA.w SprAction, X
  .not_handled
  PLB : PLP : SEP #$30 : CLC
  RTL
  .room25
  ; Avoid legacyChillin's non-attempt action5 path in this room.
  LDA.w SprAction, X : BNE +
  LDA.b #$04 : STA.w SprAction, X
  +
  CMP.b #$0A : BNE .not_releasing
  LDA.l D4HubContacts : CMP.b #$02 : BNE +
  JMP .handled ; paired handler owns motion; no airborne/native21 shortcut
  +
  JSL ThrownSprite_TileAndSpriteInteraction_long
  JSL Sprite_Move
  JMP .handled             ; settle Z while owned21 releases
  .not_releasing
  CMP.b #$04 : BEQ .movable
  CMP.b #$07 : BEQ .movable
  JMP .handled             ; remaining actions own their own handlers
  .movable
  LDA.w SprState, X : CMP.b #$0A : BNE .not_held
  LDA.b #$07 : STA.w SprAction, X
  JMP .handled             ; nativecarried module owns motion
  .not_held
  CMP.b #$09 : BEQ .active
  JMP .disarm
  .active
  JSL Sprite_CheckIfLifted
  LDA.w SprState, X : CMP.b #$0A : BNE .released
  LDA.b #$07 : STA.w SprAction, X
  JMP .handled
  .released
  JSL ThrownSprite_TileAndSpriteInteraction_long
  JSL Sprite_Move
  LDA.w SprState, X : CMP.b #$09 : BEQ +
  JMP .disarm
  +
  LDA.w SprAction, X : CMP.b #$07 : BEQ +
  JMP .handled
  +
  LDA.w SprFloor, X : BNE .miss
  LDA.l WaterGateStates : AND.b #!D4Water_Latch : BNE .miss
  JSR ZoraBaby_Room25FindSwitch : BCC .miss
  LDA.l D4HubContacts : CMP.b #$02 : BNE .legacy_start
  LDA.w SprHeight, X : ORA.w SprXSpeed, X : ORA.w SprYSpeed, X
  BNE .handled ; paired contact must be settled, never an airborne overlap
  LDA.w SprMiscB, X : CMP.b #$D4 : BNE .miss
  LDA.w SprGfx, Y : BNE .miss
  JSR D4Hub_BabyAtRemote : BCC .miss
  JSR D4Hub_StartPair
  BRA .handled
  .legacy_start
  LDA.w SprAction, Y : BNE .miss
  LDA.w SprFrame, Y : BNE .miss
  JSR D4Hub_BabyAtRemote : BCC .miss
  STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
  STZ.w $0642
  LDA.b #$00 : STA.w SprTimerA, Y : STA.w SprFrame, Y
  LDA.b #$01 : STA.w SprAction, Y
  LDA.b #$0A : STA.w SprAction, X
  BRA .handled
  .miss
  LDA.w SprHeight, X : ORA.w SprXSpeed, X : ORA.w SprYSpeed, X
  BNE .handled
  ; Only a released, settled miss in the verified isolated catch rectangle
  ; gets NPC recovery. Near-side and out-of-proof-region misses remainwait4.
  LDA.w SprFloor, X : BNE .disarm
  JSR ZoraBaby_Room25InCatch : BCC .disarm
  LDA.b #$08 : STA.w SprAction, X
  BRA .handled
  .disarm
  LDA.b #$04 : STA.w SprAction, X
  .handled
  PLB : PLP : SEP #$30 : SEC
  RTL
}

; Reviewed room contact bounds are generated; no old catch coordinates.
ZoraBaby_Room25InCatch:
{
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  CMP.l D4HubContacts+18 : BCC .no
  CMP.l D4HubContacts+20 : BCS .no
  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  CMP.l D4HubContacts+22 : BCC .no
  CMP.l D4HubContacts+24 : BCS .no
  SEP #$20 : SEC : RTS
  .no
  SEP #$20 : CLC : RTS
}

; Actions8/B walk to the reviewed mouth;9/C enter the authored hatch.
; Recovery is an NPC path, not proof of Link walkability.
ZoraBaby_Room25Recover:
{
  PHP : PHB : SEP #$30
  LDA.b #$7E : PHA : PLB
  LDA.w SprState, X : CMP.b #$09 : BEQ +
  JMP .cancel
  +
  LDA.w SprFloor, X : BEQ +
  JMP .cancel
  +
  ; Pause/transition must not convert follower or commit water.
  LDA.b $10 : CMP.b #$07 : BEQ +
  JMP .done
  +
  LDA.b $11 : ORA.w $02E4 : ORA.w $0FFC : BEQ +
  JMP .done
  +
  REP #$20
  LDA.l D4HubContacts+10 : STA.b $04
  LDA.l D4HubContacts+12 : STA.b $06
  SEP #$20
  LDA.w SprAction, X : CMP.b #$08 : BEQ .mouth
  CMP.b #$0B : BNE +
  .mouth
  REP #$20
  LDA.l D4HubContacts+14 : STA.b $04
  LDA.l D4HubContacts+16 : STA.b $06
  SEP #$20
  +
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  SEC : SBC.b $04 : BPL +
  EOR.w #$FFFF : INC A
  +
  STA.b $02
  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  SEC : SBC.b $06 : BPL +
  EOR.w #$FFFF : INC A
  +
  CLC : ADC.b $02 : CMP.w #$0006 : BCS .move
  SEP #$20
  STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
  LDA.w SprAction, X : CMP.b #$08 : BNE .at_hatch
  LDA.b #$09 : STA.w SprAction, X
  JMP .done
  .at_hatch
  CMP.b #$0B : BNE .handoff
  LDA.b #$0C : STA.w SprAction, X
  JMP .done
  .handoff
  JSL ZoraBaby_EnterFollower
  JMP .done
  .move
  SEP #$20
  LDA.b #$08
  JSL Sprite_ProjectSpeedTowardsEntityLong
  LDA.b $01 : STA.w SprXSpeed, X
  LDA.b $00 : STA.w SprYSpeed, X
  JSL Sprite_Move
  .wait
  JMP .done
  .cancel
  LDA.b #$04 : STA.w SprAction, X
  JMP .done
  .done
  PLB : PLP : SEP #$30
  RTL
}

; Full-coordinate historic overlap window, retainingY=bound remote actor.
D4Hub_BabyAtRemote:
{
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  SEC : SBC.l D4HubContacts+2 : CLC : ADC.w #$0009
  CMP.w #$0012 : BCS .no
  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  SEC : SBC.l D4HubContacts+4 : CLC : ADC.w #$0012
  CMP.w #$0024 : BCS .no
  SEP #$20 : SEC : RTS
  .no
  SEP #$20 : CLC : RTS
}

; Saved unlock08 restores the bound remote21's settled appearance on re-entry.
; Tick calls after collision, M16/X16/D0/DBR7E. Preserve fullA/X/Y/P; D/DBR
; unchanged. Writes only the selected actor's idle pose, never0642 or SRAM.
D4Hub_ReconcileRemotePose:
{
  PHP : REP #$30
  PHA : PHX : PHY
  LDA.b $A0 : CMP.w #$0025 : BNE .done
  SEP #$30
  LDA.b $1B : BEQ .done
  LDA.l WaterGateStates : AND.b #!D4Water_Latch : BEQ .done
  LDA.l D4HubContacts : CMP.b #$02 : BEQ .done ; paired04 is draw-only idle
  CMP.b #$01 : BNE .done
  JSR ZoraBaby_Room25FindSwitch : BCC .done
  ; Never overwrite a live release or attempt to restart a completed one.
  LDA.w SprAction, Y : BNE .done
  LDA.w SprFrame, Y : BNE .done
  ; Native stage9 leaves position06; stage10 sets frame0A/action02.
  ; Draw's shake term is (0DA0>>2)&3: zero produces the settled neutral pose.
  LDA.b #$00
  STA.w SprTimerA, Y : STA.w SprMiscA, Y : STA.w SprMiscB, Y
  LDA.b #$0A : STA.w SprFrame, Y
  LDA.b #$06 : STA.w SprMiscC, Y
  LDA.b #$02 : STA.w SprAction, Y
  .done
  REP #$30
  PLY : PLX : PLA : PLP
  RTS
}

; Header2 binds two native04 actors; header1 retains the native21 foundation.
; Header byte1=$01 marks a complete binding. All helpers enter/leave M8/X8,
; D0/RAM-mirror DBR; A/Y and DP00-03 scratch unless explicitly preserved.
D4Hub_IsPairedRemote:
{
  LDA.b $1B : BEQ .no
  LDA.b $A0 : CMP.b #$25 : BNE .no
  LDA.b $A1 : BNE .no
  LDA.l D4HubContacts : CMP.b #$02 : BNE .no
  LDA.l D4HubContacts+1 : CMP.b #$01 : BNE .no
  LDA.w SprType, X : CMP.b #$04 : BNE .no
  LDA.w SprState, X : CMP.b #$09 : BNE .no
  LDA.w SprFloor, X : BNE .no
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  CMP.l D4HubContacts+2 : BNE .no16
  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  CMP.l D4HubContacts+4 : BNE .no16
  SEP #$20 : SEC : RTS
  .no16
  SEP #$20
  .no
  CLC : RTS
}

; X=remote; Y returns its exact Baby. Reciprocal actor-owned tags and slots
; prevent a moved actor, carried Baby or another switch event owning this pair.
D4Hub_ValidatePair:
{
  JSR D4Hub_IsPairedRemote : BCS + : JMP .no
  +
  LDA.w SprMiscB, X : CMP.b #$D5 : BEQ + : JMP .no
  +
  LDA.w SprGfx, X : BNE + : JMP .no
  +
  CMP.b #$0E : BCC + : JMP .no
  +
  LDA.w SprMiscA, X : CMP.b #$10 : BCC + : JMP .no
  +
  TAY
  LDA.w SprType, Y : CMP.b #$39 : BEQ + : JMP .no
  +
  LDA.w SprState, Y : CMP.b #$09 : BEQ + : JMP .no
  +
  LDA.w SprFloor, Y : ORA.w SprHeight, Y : BEQ + : JMP .no
  +
  LDA.w SprXSpeed, Y : ORA.w SprYSpeed, Y : BEQ + : JMP .no
  +
  LDA.w SprAction, Y : CMP.b #$0A : BEQ + : JMP .no
  +
  LDA.w SprMiscB, Y : CMP.b #$D4 : BEQ + : JMP .no
  +
  TXA : CMP.w SprMiscA, Y : BEQ + : JMP .no
  +
  ; Native down-pull offsets, indexed by the remote's native SprGfx pose.
  PHX
  LDA.w SprGfx, X : TAX
  LDA.l D4Hub_BabyPullY, X : STA.b $00 : STZ.b $01
  PLX
  LDA.w SprXH, Y : XBA : LDA.w SprX, Y
  REP #$20
  CMP.l D4HubContacts+2 : BNE .no16
  LDA.l D4HubContacts+4 : CLC : ADC.b $00 : STA.b $02
  SEP #$20
  LDA.w SprYH, Y : XBA : LDA.w SprY, Y
  REP #$20
  CMP.b $02 : BNE .no16
  SEP #$20 : SEC : RTS
  .no16
  SEP #$20
  .no
  CLC : RTS
}

; Preserve X=manual actor. Only the fully pulled pose admits first Link input.
; Y returns Baby for the completion handoff; no SRAM/global event is consulted.
D4Hub_PairHeld:
{
  PHX
  LDA.l D4HubContacts : CMP.b #$02 : BNE .no
  JSR ZoraBaby_Room25FindSwitch : BCC .no
  TYX
  JSR D4Hub_ValidatePair : BCC .no
  LDA.w SprGfx, X : CMP.b #$0D : BNE .no
  PLX : SEC : RTS
  .no
  PLX : CLC : RTS
}

; X=paired upper04. Never call05D6BC/05D8B5/05D915 for this actor: those
; native update paths can write Link position, input state and completion0642.
D4Hub_DrawRemote:
{
  LDA.l WaterGateStates : AND.b #!D4Water_Latch : BNE .idle
  JSR D4Hub_ValidatePair : BCS .draw
  .idle
  STZ.w SprGfx, X : STZ.w SprTimerA, X : STZ.w SprAction, X
  STZ.w SprMiscA, X : STZ.w SprMiscB, X
  .draw
  PHB
  LDA.b #$05 : PHA : PLB
  ;05D953 returns RTS, including its offscreen unwind. A bank05 RTL opcode
  ; supplies the final long return; both nested native JSRs keep bank05.
  assert read3($05D953) == $FA5020, "Native down-pull draw entry moved"
  assert read1($05D6CE) == $6B, "Bank05 draw RTL trampoline moved"
  PHK : PEA.w .returned-1
  PEA.w $D6CE-1
  JML $05D953
  .returned
  PLB
  RTS
}

; X=Baby/Y=remote, entered only after released/settled contact and provenance.
; The native timers pace the visible pull; final hold has no expiry/countdown.
D4Hub_StartPair:
{
  TYA : STA.w SprMiscA, X
  TXA : STA.w SprMiscA, Y
  LDA.b #$D5 : STA.w SprMiscB, Y
  LDA.b #$01 : STA.w SprGfx, Y
  LDA.b #$0C : STA.w SprTimerA, Y
  LDA.b #$0A : STA.w SprAction, X
  JSR D4Hub_AlignBaby
  RTS
}

; Use existing north-facing head/body art, plus native pull distance. This
; supplies body motion and valve motion, not new authored hand/grip artwork.
D4Hub_AlignBaby:
{
  LDA.b #$20 : STA.w FollowerHeadOffset
  LDA.b #$C0 : STA.w FollowerBodyOffset
  LDA.b #$00 : STA.w FollowerHeadOffsetH : STA.w FollowerBodyOffsetH
  PHX
  LDA.w SprGfx, Y : TAX
  LDA.l D4Hub_BabyPullY, X : STA.b $00 : STZ.b $01
  PLX
  REP #$20
  LDA.l D4HubContacts+2 : STA.b $02
  SEP #$20
  LDA.b $02 : STA.w SprX, X
  LDA.b $03 : STA.w SprXH, X
  REP #$20
  LDA.l D4HubContacts+4 : CLC : ADC.b $00 : STA.b $02
  SEP #$20
  LDA.b $02 : STA.w SprY, X
  LDA.b $03 : STA.w SprYH, X
  RTS
}
D4Hub_BabyPullY: db 5,9,9,10,10,11,11,12,12,13,13,14,14,14

; X=Baby. Pause freezes progress. Native pickup invalidates the pair safely;
; a settled cancellation in the catch retains the existing mouth/hatch route.
D4Hub_PairedAwait:
{
  LDA.b $10 : CMP.b #$07 : BNE .done
  LDA.b $11 : ORA.w $02E4 : ORA.w $0FFC : BNE .done
  JSL Sprite_CheckIfLifted
  PHX
  LDA.w SprMiscA, X : CMP.b #$10 : BCS .invalid
  TAX
  JSR D4Hub_ValidatePair : BCC .invalid
  ; Ensure the validated Baby is this caller, not a second valid actor.
  TYA : CMP $01,S : BNE .invalid
  LDA.w SprTimerA, X : BNE .pose
  LDA.w SprGfx, X : CMP.b #$0D : BEQ .pose
  INC.w SprGfx, X
  LDA.b #$05 : STA.w SprTimerA, X
  .pose
  TXY : PLX
  JSR D4Hub_AlignBaby
  RTS
  .invalid
  PLX
  LDA.w SprState, X : CMP.b #$0A : BNE .not_carried
  LDA.b #$07 : STA.w SprAction, X
  RTS
  .not_carried
  LDA.b #$04 : STA.w SprAction, X
  JSR ZoraBaby_Room25InCatch : BCC .done
  LDA.w SprHeight, X : ORA.w SprFloor, X : BNE .done
  LDA.b #$08 : STA.w SprAction, X
  .done
  RTS
}

; Called only by actual follower09 -> NPC conversion, before follower is cleared.
; Preserve X/Y/DBR/P; M8/X8 caller. Tag exists for staged action4 as well as a
; later pair, so the supported unload/save boundary can recover exact custody.
ZoraBaby_Room25Stage:
{
  PHP : PHB : SEP #$30
  LDA.b #$7E : PHA : PLB
  LDA.b $1B : BEQ .done
  LDA.b $A0 : CMP.b #$25 : BNE .done
  LDA.b $A1 : BNE .done
  LDA.l D4HubContacts : CMP.b #$02 : BNE .done
  LDA.l D4HubContacts+1 : CMP.b #$01 : BNE .done
  LDA.l $7EF3CC : CMP.b #$09 : BNE .done
  CPY.b #$10 : BCS .done
  LDA.w SprType, Y : CMP.b #$39 : BNE .done
  LDA.w SprState, Y : CMP.b #$09 : BNE .done
  LDA.w SprFloor, Y : BNE .done
  LDA.b #$D4 : STA.w SprMiscB, Y
  .done
  PLB : PLP
  RTL
}

; Recover only real follower custody, never initial authored39 recruitment.
; ROOMCOPY0025 remains the source room while A0 may already be the destination.
; Full A/X/Y/D/DBR/P preserved except returned C=owned. No graphics/Link motion.
D4Hub_RecoverStagedBaby:
{
  PHP : REP #$30
  PHA : PHX : PHY : PHB : PHD
  LDA.w #$0000 : TCD
  SEP #$20
  LDA.b #$7E : PHA : PLB
  SEP #$10
  JSR .recover
  REP #$30
  PLD : PLB : PLY : PLX : PLA
  BCS .owned
  PLP : CLC : RTL
  .owned
  PLP : SEC : RTL
  .recover
  LDA.l D4HubContacts : CMP.b #$02 : BNE .no
  LDA.l D4HubContacts+1 : CMP.b #$01 : BNE .no
  LDA.b $1B : BEQ .no
  LDA.w $048E : CMP.b #$25 : BNE .no
  LDA.w $048F : BNE .no
  LDA.l $7EF3CC : CMP.b #$09 : BEQ .yes
  CMP.b #$00 : BNE .no ; never overwrite another real follower
  LDX.b #$0F
  .scan
  LDA.w SprType, X : CMP.b #$39 : BNE .next
  LDA.w SprState, X : CMP.b #$09 : BEQ .active
  CMP.b #$0A : BNE .next
  .active
  LDA.w SprFloor, X : BNE .next
  LDA.w SprMiscB, X : CMP.b #$D4 : BNE .next
  JSR D4Hub_ClearDepartingPair
  LDA.b #$09 : STA.l $7EF3CC
  LDA.b #$00 : STA.l $7EF3D3 ; resumed follower, not old-room active custody
  STZ.w SprMiscB, X : STZ.w SprState, X
  .yes
  SEC : RTS
  .next
  DEX : BPL .scan
  .no
  CLC : RTS
}

; Source-room/provenance was already checked. Preserve X=owned Baby. Clear
; only the reciprocal upper04 and exact manual04 episode before native reset.
; A0 may be the destination here, so use the already-qualified source binding.
D4Hub_ClearDepartingPair:
{
  LDY.b #$0F
  .scan
  LDA.w SprState, Y : CMP.b #$09 : BEQ +
  JMP .next
  +
  LDA.w SprType, Y : CMP.b #$04 : BEQ +
  JMP .next
  +
  LDA.w SprFloor, Y : BEQ +
  JMP .next
  +
  LDA.w SprXH, Y : CMP.l D4HubContacts+3 : BNE .manual
  LDA.w SprX, Y : CMP.l D4HubContacts+2 : BNE .manual
  LDA.w SprYH, Y : CMP.l D4HubContacts+5 : BNE .manual
  LDA.w SprY, Y : CMP.l D4HubContacts+4 : BNE .manual
  LDA.w SprMiscB, Y : CMP.b #$D5 : BNE .next
  TXA : CMP.w SprMiscA, Y : BNE .next
  LDA.b #$00 : STA.w SprMiscA, Y : STA.w SprMiscB, Y
  BRA .clear
  .manual
  LDA.w SprXH, Y : CMP.l D4HubContacts+7 : BNE .next
  LDA.w SprX, Y : CMP.l D4HubContacts+6 : BNE .next
  LDA.w SprYH, Y : CMP.l D4HubContacts+9 : BNE .next
  LDA.w SprY, Y : CMP.l D4HubContacts+8 : BNE .next
  LDA.w SprAction, Y : CMP.b #$01 : BEQ .clear
  CMP.b #$02 : BNE .next
  .clear
  LDA.b #$00 : STA.w SprGfx, Y : STA.w SprTimerA, Y : STA.w SprAction, Y
  .next
  DEY : BMI .done
  JMP .scan
  .done
  RTS
}

; Room-load caller needs exact pointer ABI and scratch/Link state unchanged.
; Initialize only a recovered staged NPC; an already live follower keeps history.
D4Hub_RecoverBeforeRoomLoad:
{
  PHP : REP #$30
  PHA : PHX : PHY : PHB : PHD
  LDA.w #$0000 : TCD
  SEP #$20
  LDA.b #$7E : PHA : PLB
  LDA.l $7EF3CC : CMP.b #$00 : BNE .done
  JSL D4Hub_RecoverStagedBaby : BCC .done
  REP #$20
  LDA.b $00 : PHA
  SEP #$20
  LDA.b $5E : PHA
  SEP #$10
  JSL Follower_Initialize
  PLA : STA.b $5E
  REP #$20
  PLA : STA.b $00
  .done
  REP #$30
  PLD : PLB : PLY : PLX : PLA : PLP
  RTL
}

;09F554: original A=follower, M8/X8/D0/DBR09. Preserve exact non-owned
; CMP09 branch destinations; downstream LDA supplies its own A/N/Z.
D4Hub_SaveFollower:
{
  PHA
  ; Existing follower09 already proves companion custody, including a later
  ; save in Room26 or elsewhere. ABI1 retains vanilla purge behavior.
  LDA.l D4HubContacts : CMP.b #$02 : BNE .recover
  LDA.l D4HubContacts+1 : CMP.b #$01 : BNE .recover
  PLA : PHA : CMP.b #$09 : BEQ .owned
  .recover
  JSL D4Hub_RecoverStagedBaby : BCC .ordinary
  .owned
  PLA
  JML $09F55E
  .ordinary
  PLA : CMP.b #$09 : BNE .keep
  JML $09F558
  .keep
  JML $09F55E
}

D4Water_End:
assert D4Water_End <= $50A000, "D4 paired water controller exceeds its slot"
pullpc
