; Private D6 B2 circuit. Reuses native route arrays and room door flags.
; No SRAM/WRAM allocation. Tracks13/16 and action7 are local to the new docks.

; RoomTag39: M8/X8, D=0, mirrored WRAM DBR. Preserve P/DBR/X/Y.
; Clobber A and $00-$0B; $0E (native tag slot) is preserved.
D6CartCircuit_Main:
{
  PHB : PHK : PLB
  PHP : PHX : PHY
  JSR D6CartCircuit_Recall
  LDA.b $A0 : CMP.b #$D7 : BNE .done
  JSR D7Chu_Earn
  .done
  SEP #$30
  PLY : PLX : PLP
  PLB
  RTS
}

D6CartCircuit_IsRoom:
{
  PHA
  LDA.b $1B : BEQ .no
  LDA.b $A1 : BNE .no
  LDA.b $A0 : CMP.b #$D7 : BEQ .yes
  CMP.b #$D8 : BNE .no
  .yes
  PLA : SEC : RTL
  .no
  PLA : CLC : RTL
}

; F2/AF use the accepted stationary D9 mode in D7 as well.
D6ChuActor_IsRoom:
{
  PHA
  LDA.b $1B : BEQ .no
  LDA.b $A1 : BNE .no
  LDA.b $A0 : CMP.b #$D7 : BEQ .yes
  CMP.b #$D9 : BNE .no
  .yes
  PLA : SEC : RTL
  .no
  PLA : CLC : RTL
}
D6ChuActor_IsLoadedRoom:
{
  PHA
  LDA.b $1B : BEQ .no
  LDA.w $048F : BNE .no
  LDA.w $048E : CMP.b #$D7 : BEQ .yes
  CMP.b #$D9 : BNE .no
  .yes
  PLA : SEC : RTL
  .no
  PLA : CLC : RTL
}

; M16/X8: reproduce the native CMP room result, preserving A/X/Y/DBR.
; New endpoint placeholders use the room being loaded, not the departing A0.
D6CartCircuit_PrepRoomCompare:
{
  PHP : PHA
  LDA.w SprSubtype,X : AND.w #$00FF
  CMP.w #$000D : BEQ .lower
  CMP.w #$0010 : BNE .ordinary
  LDA.w $048E : CMP.w #$00D8 : BEQ .loaded
  BRA .ordinary
  .lower
  LDA.w $048E : CMP.w #$00D7 : BEQ .loaded
  CMP.w #$00D8 : BEQ .loaded
  .ordinary
  PLA : PLP
  CMP.b $A0
  RTL
  .loaded
  PLA : PLP
  CMP.w $048E
  RTL
}

; Called only from the original Prep kill path, M8/X8. C=1 retains a
; dormant endpoint placeholder. Ordinary tracks still take the native kill.
; Preserve X/Y/DBR; clobber A and return C.
D6CartCircuit_ParkDormant:
{
  PHP
  LDA.w $048F : BNE .no
  LDA.w SprSubtype,X : CMP.b #$0D : BEQ .lower
  CMP.b #$10 : BNE .no
  LDA.w $048E : CMP.b #$D8 : BEQ .keep
  BRA .no
  .lower
  LDA.w $048E : CMP.b #$D7 : BEQ .keep
  CMP.b #$D8 : BNE .no
  .keep
  LDA.b #$09 : STA.w SprState,X
  LDA.b #$04 : STA.w SprNbrOAM,X
  LDA.b #$40 : STA.w SprGfxProps,X
  LDA.b #$E0 : STA.w SprHitbox,X
  LDA.b #$07 : STA.w SprAction,X
  STZ.w SprDefl,X : STZ.w SprBump,X : STZ.w SprTileDie,X
  STZ.w SprXSpeed,X : STZ.w SprYSpeed,X
  STZ.w SprMiscG,X : STZ.w SprMiscF,X : STZ.w SprMiscA,X
  STZ.w SprFrame,X : STZ.w SprTimerB,X
  PLP : SEC : RTL
  .no
  PLP : CLC : RTL
}

; Only on an A press, normal floor, and no riding/carrying. Fixed posts are
; solid02 in the private collision map, so native lifting cannot remove them.
D6CartCircuit_Recall:
{
  LDA.b $F6 : AND.b #$80 : BNE + : RTS
+
  LDA.b $EE : BEQ + : RTS
+
  LDA.b $35 : BEQ + : RTS
+
  LDA.w LinkCarryOrToss : BEQ + : RTS
+
  ; Native Link control sees A first and may already start dash charge.
  LDA.b $5D : BEQ +
  CMP.b #$11 : BEQ + : RTS
+
  LDY.b #$00
  .dock
  REP #$20
  LDA.w .Docks,Y : CMP.b $A0 : BNE .next
  LDA.b $22 : SEC : SBC.w .Docks+8,Y : CLC : ADC.w #$0010
  CMP.w #$0030 : BCS .next
  LDA.b $20 : SEC : SBC.w .Docks+10,Y : CLC : ADC.w #$0020
  CMP.w #$0040 : BCS .next
  LDA.w .Docks,Y : STA.b $02
  LDA.w .Docks+4,Y : STA.b $04
  LDA.w .Docks+6,Y : STA.b $06
  SEP #$20
  LDA.w .Docks+2,Y : STA.b $00
  LDA.w .Docks+3,Y : STA.b $08
  JSR D6CartCircuit_CallSelected
  RTS
  .next
  SEP #$20
  TYA : CLC : ADC.b #$0C : TAY
  CPY.b #$30 : BCC .dock
  RTS

  ; Room, track, departure, cartX/Y, postX/Y. All coordinates are world.
  .Docks
  dw $00D7 : db $0D,$00 : dw $0F10,$1B50,$0F40,$1B40
  dw $00D8 : db $0D,$03 : dw $11C0,$1BB0,$11B0,$1B90
  dw $00D8 : db $10,$01 : dw $1070,$1A70,$1070,$1A50
  dw $00D8 : db $10,$03 : dw $11A0,$1A70,$1190,$1A80
}

; $00 route, $02 room, $04/$06 destination, $08 NESW. All exits M8/X8.
; Prefer an existing visible idle cart at the destination. If that actor has
; parked away from a dock, recover a same-route idle slot to the selected dock.
; A moving, released or tossed cart refuses recall. Other routes never change.
D6CartCircuit_CallSelected:
{
  LDA.b #$FF : STA.b $09 : STA.b $0A
  STZ.b $0B
  LDX.b #$0F
  .find
  LDA.w SprState,X : CMP.b #$09 : BNE .next
  LDA.w SprType,X : CMP.b #Sprite_Minecart : BNE .next
  LDA.w SprSubtype,X : CMP.b $00 : BNE .next
  LDA.w SprMiscG,X : BEQ + : RTS
+
  LDA.w SprAction,X : CMP.b #$02 : BCC .parked
  CMP.b #$07 : BEQ .parked
  RTS
  .parked
  STX.b $0A
  LDA.w SprXH,X : XBA : LDA.w SprX,X
  REP #$20
  CMP.b $04 : BNE .next_wide
  SEP #$20
  LDA.w SprYH,X : XBA : LDA.w SprY,X
  REP #$20
  CMP.b $06 : BNE .next_wide
  SEP #$20
  LDA.w SprAction,X : CMP.b #$07 : BNE .select
  LDA.b $09 : CMP.b #$FF : BNE .next
  .select
  STX.b $09
  BRA .next
  .next_wide
  SEP #$20
  .next
  DEX : BPL .find
  LDA.b $09 : CMP.b #$FF : BNE +
  LDA.b $0A : CMP.b #$FF : BNE .recover : RTS
  .recover
  STA.b $09
  LDA.b #$01 : STA.b $0B
+
  ; The room tag runs before Sprite_Main. A cart already here must retain
  ; ordinary input and timer so the player can B-board beside the A-call post.
  LDX.b $09
  LDA.b $0B : BNE .recall
  LDA.w SprAction,X : CMP.b #$07 : BEQ .recall
  RTS
  .recall
  ; Cancel only the accepted A-call's native dash charge. This vanilla
  ; helper preserves X/Y/DBR/M/X and DP scratch; it does not reset $5D.
  LDA.b $5D : CMP.b #$11 : BNE +
  JSL Link_CancelDash
  STZ.b $5D
+
  LDX.b #$0F
  .hide_other
  CPX.b $09 : BEQ .skip
  LDA.w SprState,X : CMP.b #$09 : BNE .skip
  LDA.w SprType,X : CMP.b #Sprite_Minecart : BNE .skip
  LDA.w SprSubtype,X : CMP.b $00 : BNE .skip
  LDA.b #$07 : STA.w SprAction,X
  STZ.w SprXSpeed,X : STZ.w SprYSpeed,X
  STZ.w SprMiscG,X
  .skip
  DEX : BPL .hide_other

  LDX.b $09
  LDA.b $04 : STA.w SprX,X
  LDA.b $05 : STA.w SprXH,X
  LDA.b $06 : STA.w SprY,X
  LDA.b $07 : STA.w SprYH,X
  STZ.w $0D60,X : STZ.w $0D70,X ; native fractional X/Y position
  LDA.b $08 : STA.w SprMiscB,X
  AND.b #$01 : EOR.b #$01 : STA.w SprAction,X
  ASL A : STA.w $0D90,X
  LDY.b $08
  LDA.w .Facing,Y : STA.w SprMiscC,X
  STZ.w SprFrame,X : STZ.w SprTimerB,X
  STZ.w SprXSpeed,X : STZ.w SprYSpeed,X
  STZ.w SprMiscG,X : STZ.w SprMiscF,X
  LDA.b #$01 : STA.w SprMiscA,X
  LDA.b #$10 : STA.w SprTimerA,X
  LDA.b $00 : ASL A : TAY
  REP #$20
  LDA.b $02 : STA.w MinecartTrackRoom,Y
  LDA.b $04 : STA.w MinecartTrackX,Y
  LDA.b $06 : STA.w MinecartTrackY,Y
  SEP #$20
  LDA.b $F6 : AND.b #$7F : STA.b $F6
  LDA.b #$25 : STA.w $012F
  RTS
  .Facing
  db $00,$03,$01,$02
}

; D7's unused fourth saved-door bit earns the boss condition. The only
; physical D7 door is index0/8000; a Small Key opening cannot earn1000.
D7Chu_Earn:
{
  REP #$20
  LDA.w $0400 : BIT.w #$1000
  SEP #$20
  BEQ + : RTS
+
  LDA.l BombchuSignature : CMP.b #$BC : BEQ + : RTS
+
  LDA.l BombchuIndoors : BNE + : RTS
+
  LDA.l BombchuAreaLow : CMP.b #$D7 : BEQ + : RTS
+
  LDA.l BombchuAreaHigh : BEQ + : RTS
+
  LDA.l BombchuFloor : BEQ + : RTS
+
  LDA.l BombchuSlot : BNE + : RTS
+
  CMP.b #$03 : BCC + : RTS
+
  DEC A : TAX
  LDA.w $0C4A,X : CMP.b #$07 : BEQ + : RTS
+
  LDA.w $03EA,X : CMP.b #$BC : BEQ + : RTS
+
  LDA.w $0C5E,X : BEQ + : RTS
+
  LDA.w $0C04,X : STA.b $00
  LDA.w $0C18,X : STA.b $01
  LDA.w $0BFA,X : STA.b $02
  LDA.w $0C0E,X : STA.b $03
  REP #$20
  LDA.b $00 : SEC : SBC.w #$0EC0 : CLC : ADC.w #$0007
  CMP.w #$001E : BCS .miss
  LDA.b $02 : SEC : SBC.w #$1AC0 : CLC : ADC.w #$0007
  CMP.w #$001E : BCS .miss
  LDA.w $0400 : ORA.w #$1000 : STA.w $0400
  LDA.l $7EF1AE : ORA.w #$1000 : STA.l $7EF1AE
  SEP #$20
  LDA.b #$01 : STA.w $039F,X
  LDA.b #$25 : STA.w $012F
  RTS
  .miss
  SEP #$20
  RTS
}

; Native Big Key door path, M16/X16, D=0, original DBR retained. JML entry
; replaces LDA7EF366/AND DungeonMask,Y/BNE at01CF22..2A. Preserve stack,
; DBR/X/Y and incoming C/V/D/I; reproduce A/N/Z on the ordinary path.
pushpc
; Ignore and clear an older saved boss-door opening until D7 is earned. This
; runs during native door drawing, before its graphics/collision choose open.
assert read3($01B0F3) == $068CAD, "Native door flag read changed"
assert read3($01B0F6) == $98C039, "Native door flag mask changed"
org $01B0F3 ; @hook module=Dungeons name=D6_Boss_Door_Load_Condition kind=jsl target=D6BossDoor_LoadFlag expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
  JSL D6BossDoor_LoadFlag
  NOP #2
assert pc() == $01B0F9
assert read4($01CF22) == $7EF366AF, "Native Big Key read changed"
assert read3($01CF26) == $98C039, "Native Big Key mask changed"
assert read2($01CF29) == $40D0, "Native Big Key branch changed"
org $01CF22 ; @hook module=Dungeons name=D6_Boss_Door_Condition kind=jml target=D6BossDoor_Check expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
  JML D6BossDoor_Check
  NOP #5
assert pc() == $01CF2B
pullpc
D6BossDoor_LoadFlag:
{
  PHP
  LDA.w $048E : CMP.w #$00D8 : BNE .ordinary
  CPY.w #$0002 : BNE .ordinary
  LDA.l $7EF1AE : BIT.w #$1000 : BNE .ordinary
  LDA.w $068C : AND.w #$BFBF : STA.w $068C
  LDA.w $0400 : AND.w #$BFFF : STA.w $0400
  LDA.l $7EF1B0 : AND.w #$BFFF : STA.l $7EF1B0
  PLP
  LDA.w #$0000
  RTL
  .ordinary
  PLP
  LDA.w $068C
  AND.w $98C0,Y
  RTL
}
D6BossDoor_Check:
{
  PHP
  LDA.b $A0 : CMP.w #$00D8 : BNE .ordinary
  LDA.w $0694 : CMP.w #$0002 : BNE .ordinary
  LDA.l $7EF1AE : BIT.w #$1000 : BNE .ordinary
  PLP
  JML $01CF41 ; closed, without incorrectly claiming the Big Key is missing
  .ordinary
  PLP
  LDA.l $7EF366
  AND.w $98C0,Y
  BEQ .missing
  JML $01CF6B
  .missing
  JML $01CF2B
}
