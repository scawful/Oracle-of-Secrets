; =========================================================
; File: Dungeons/door_surrounds.asm
; Purpose: Stamp a qualified wall ornament behind ordinary upper doors
;          in D4 Zora, D5 Glacia, and D6 Goron. Every other room stays
;          on the vanilla door draw, so shared vanilla rooms are untouched.
; Ported from codex/dungeon-door-surrounds-20261106 @ ac19410b onto
; master bdfc0bdb. Bank $2C is full through $2CF700. Bank $50 above
; $50A000 is the special-overworld atlas spill, so this routine cannot
; live there. The fixed entrance tables end at $5E8300; the routine and
; tables own the zero-filled slot $5E8400-$5E8BFF.
; =========================================================
; Source: usdasm RoomDraw_DrawAllObjects ($01890D), ordinary ranged doors,
; DoorTilemapPositions ($00997E), objects $005/$006/$065/$066.
; Hook bytes are checked against the base ROM at assemble time.
;
; Entry: M/X=16, DBR=$00, D=$0000, A/$00=stored door word; $BF is the
; active tilemap pointer. The helper preserves A/X/Y/P, DBR, D, $00-$0F
; before entering the original door dispatcher. That dispatcher keeps its
; original JSR/RTS stack contract through a four-byte bank-$01 bridge.
; The two displaced INC $BA instructions run after the original draw.
;
; Ordinary upper types only: $00 normal, $18 shutter, $1C key, $1E big key.
; Lower/split doors and special entrances need their own material profile.
; Raw source words retain their palette, H/V, priority and tile classes.
; Enable byte $00 skips the room. Byte $01 uses the Glacia-qualified
; inward placement (one tile toward the floor). Authored faces and the
; seven contact holds live in the exception table and are not restamped.

pushpc

assert read3($01890D) == $891620, "RoomDraw door JSR moved"
assert read4($018910) == $BAE6BAE6, "door-loop INC $BA pair moved"
org $01890D ; @hook module=Dungeons name=DoorSurrounds_DrawDoor kind=jsl target=Oracle_DrawDoorWithSurrounds expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16 protected_size=7
  JSL Oracle_DrawDoorWithSurrounds
  NOP #3
assert pc() == $018914

; The custom-object entries end before $01B558. Vanilla header data starts
; at $01B560; never extend this bridge into those camera-offset words.
assert read1($01B558) == $FF && read1($01B55F) == $FF, "door-surround bridge gap is occupied"
org $01B558 ; @hook module=Dungeons name=DoorSurrounds_VanillaBridge kind=patch protected_size=8
Oracle_DoorSurrounds_VanillaBridge:
  JSR $8916
  RTL
assert pc() == $01B55C
; Versioned read-only descriptor for editor parity. This is the final four
; bytes of the same proven free gap; header camera data starts at $01B560.
  dl Oracle_DoorSurrounds_Policy
  db $02
assert pc() == $01B560
pullpc

pushpc
org $5E8400
; Past Overworld_ExpandedEntranceID ($5E8300). Banks $21-$27, $29-$2A,
; $3D-$3F, and the bank $50 atlas spill stay untouched.
for door_preimage = $5E8400..$5E8C00
  assert read1(!door_preimage) == $00, "door-surround slot preimage is occupied"
endfor

Oracle_DrawDoorWithSurrounds:
{
  PHP : PHA : PHX : PHY
  LDA.b $00 : PHA
  LDA.b $02 : PHA
  LDA.b $04 : PHA
  LDA.b $06 : PHA
  LDA.b $08 : PHA
  LDA.b $0A : PHA
  LDA.b $0C : PHA
  LDA.b $0E : PHA

  JSR Oracle_DoorSurrounds_DrawStoredDoor

  PLA : STA.b $0E
  PLA : STA.b $0C
  PLA : STA.b $0A
  PLA : STA.b $08
  PLA : STA.b $06
  PLA : STA.b $04
  PLA : STA.b $02
  PLA : STA.b $00
  PLY : PLX : PLA : PLP

  JSL Oracle_DoorSurrounds_VanillaBridge
  INC.b $BA
  INC.b $BA
  RTL
}

Oracle_DoorSurrounds_DrawStoredDoor:
{
  LDX.b $A0
  CPX.w #Oracle_DoorSurrounds_EnabledRoomsEnd-Oracle_DoorSurrounds_EnabledRooms
  BCS .return
  LDA.l Oracle_DoorSurrounds_EnabledRooms,X
  AND.w #$00FF : BEQ .return
  ; The upper object plane is $7E2000. Lower-plane ordinary records also
  ; wait for an explicit lower-height art/palette profile.
  LDA.b $BF : CMP.w #$2000 : BNE .return
  LDA.b $00 : XBA : AND.w #$00FF
  CMP.w #$0000 : BEQ .ordinary
  CMP.w #$0018 : BEQ .ordinary
  CMP.w #$001C : BEQ .ordinary
  CMP.w #$001E : BNE .return

.ordinary
  LDA.b $00 : AND.w #$00F0 : LSR #4 : STA.b $06
  CMP.w #$000C : BCS .return
  LDA.b $00 : AND.w #$0003 : STA.b $02

  ; North/west positions 6..11 emit the opposite physical face first.
  ; Match each face against the exception table independently.
  AND.w #$0001 : BNE .current_face
  LDA.b $06 : CMP.w #$0006 : BCC .current_face
  SEC : SBC.w #$0006 : STA.b $06
  INC.b $02
  JSR Oracle_DoorSurrounds_DrawFace
  DEC.b $02
  LDA.b $06 : CLC : ADC.w #$0006 : STA.b $06

.current_face
  JSR Oracle_DoorSurrounds_DrawFace
.return
  RTS
}

Oracle_DoorSurrounds_DrawFace:
{
  ; Face key is position<<4 | direction, independent of the saved lock
  ; state/type. A hand-authored face therefore stays an override if its
  ; door changes from a normal door to a key door.
  LDA.b $06 : ASL #4 : ORA.b $02 : STA.b $04
  LDX.w #$0000
.next_exception
  LDA.l Oracle_DoorSurrounds_Exceptions,X
  CMP.w #$FFFF : BEQ .draw
  CMP.b $A0 : BNE .next
  LDA.l Oracle_DoorSurrounds_Exceptions+2,X
  CMP.b $04 : BNE .next
  RTS
.next
  INX #4
  BRA .next_exception

.draw
  LDA.b $06 : ASL : TAX
  LDA.b $02 : BEQ .north
  CMP.w #$0001 : BEQ .south
  CMP.w #$0002 : BEQ .west

.east
  LDA.l $0099C6,X : SEC : SBC.w #$0080 : STA.b $08
  LDA.w #$0010 : STA.b $0A
  BRA .horizontal
.west
  LDA.l $0099AE,X : SEC : SBC.w #$0080 : STA.b $08
  STZ.b $0A
.horizontal
  JSR Oracle_DoorSurrounds_Stamp4x2
  LDA.b $08 : CLC : ADC.w #$0200 : STA.b $08
  JMP Oracle_DoorSurrounds_Stamp4x2

.north
  ; The qualified profile moves each stamp inward one tile from the wall
  ; slot, placing its passable feet on existing floor cells.
  LDA.l $00997E,X : SEC : SBC.w #$0002 : STA.b $08
  LDA.w #$0020 : STA.b $0A
  BRA .vertical
.south
  LDA.l $009996,X : SEC : SBC.w #$0002 : STA.b $08
  LDA.w #$0030 : STA.b $0A
.vertical
  JSR Oracle_DoorSurrounds_Stamp2x4
  LDA.b $08 : CLC : ADC.w #$0008 : STA.b $08
  JMP Oracle_DoorSurrounds_Stamp2x4
}

Oracle_DoorSurrounds_Stamp2x4:
{
  LDX.b $0A
  LDY.b $08
  LDA.w #$0002 : STA.b $0C
.column
  PHY
  LDA.w #$0004 : STA.b $0E
.row
  LDA.l $009F32,X : STA.b [$BF],Y
  INX #2
  TYA : CLC : ADC.w #$0080 : TAY
  DEC.b $0E : BNE .row
  PLY
  INY #2
  DEC.b $0C : BNE .column
  RTS
}

Oracle_DoorSurrounds_Stamp4x2:
{
  LDX.b $0A
  LDY.b $08
  LDA.w #$0002 : STA.b $0C
.row
  PHY
  LDA.w #$0004 : STA.b $0E
.column
  LDA.l $009F32,X : STA.b [$BF],Y
  INX #2 : INY #2
  DEC.b $0E : BNE .column
  PLY
  TYA : CLC : ADC.w #$0080 : TAY
  DEC.b $0C : BNE .row
  RTS
}

; Records: room word, physical-face key. Generated from the reviewed
; authored surrounds. Custom entrance types are excluded by the type gate.
incsrc "Dungeons/generated/door_surround_exceptions.asm"

assert Oracle_DoorSurrounds_EnabledRoomsEnd-Oracle_DoorSurrounds_EnabledRooms == $0110
assert Oracle_DoorSurrounds_Policy>>16 == $5E, "door-surround policy left bank $5E"
assert pc() <= $5E8C00, "door surrounds exceeded $5E8400-$5E8BFF"
print "End of door_surrounds.asm         ", pc
pullpc
