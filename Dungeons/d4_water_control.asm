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
org $01883E ; @hook module=Dungeons name=D4Water_SelectObjectLists kind=jsl target=D4Water_SelectObjects expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16 protected_size=12
  assert read4($01883E) == $1F8001BF && read2($018842) == $B885
  assert read4($018844) == $1F8000BF && read2($018848) == $B785
  assert read3($01883F) == !D4Water_ObjectTable+1
  assert read3($018845) == !D4Water_ObjectTable
  JSL D4Water_SelectObjects
  NOP #8
assert pc() == $01884A

if !ENABLE_DREAM_RETURN == 0
org $028947 ; @hook module=Dungeons name=D4Water_PlayerControl kind=jsl target=D4Water_PlayerControl expected_m=8 expected_x=8 protected_size=4
  assert read4($028947) == $07800022
  JSL D4Water_PlayerControl
endif

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
  .check_main
  REP #$20
  LDA.b $22 : AND.w #$01FF : CMP.w #$0060 : BCS +
  JMP .done
  +
  CMP.w #$0078 : BCS .done_jump
  LDA.b $20 : AND.w #$01FF : CMP.w #$0058 : BCC .done_jump
  CMP.w #$006C : BCS .done_jump
  .valve
  SEP #$20
  LDA.b $5D : BNE .done_jump
  LDA.b $2F : BNE .done_jump
  LDA.w $0308 : ORA.w $0309 : BNE .done_jump
  LDA.w $0AAB ; !ZoraDiving (Masks/all_masks.asm is included later)
  BNE .done_jump
  LDA.b $F6 : AND.b #$80 : BEQ .done_jump
  LDA.l WaterGateStates : AND.b #!D4Water_Latch : BEQ .locked
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
  BRA .done
  .locked
  LDA.b #$3C : STA.w $012E
  .done_jump
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
  LDA.b [$08],Y : TAX
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
D4Water25LowCollision:  incbin "Data/Rooms/d4_water/25-low-collision.bin"
D4Water25HighCollision: incbin "Data/Rooms/d4_water/25-high-collision.bin"
D4Water37ClosedCollision: incbin "Data/Rooms/d4_water/37-closed-collision.bin"

D4Water26Low:  incbin "Data/Rooms/d4_water/26-low.bin"
D4Water26High: incbin "Data/Rooms/d4_water/26-high.bin"
D4Water25Low:  incbin "Data/Rooms/d4_water/25-low.bin"
D4Water25High: incbin "Data/Rooms/d4_water/25-high.bin"
D4Water37Closed: incbin "Data/Rooms/d4_water/37-closed.bin"
D4Water_End:
assert D4Water_End <= $50A000, "D4 paired water controller exceeds its slot"
pullpc
