D6ChuGate97_CodeStart = pc()
; Optional first Bombchu use at room97's existing north one-sided shutter.
; Unbound: requires tag1=39/tag2=00 and AF subtype0 at grid16 (9,20), floor0.
; No room data is written here. Preserve the eight existing actors and layout.
;
; Native door1 type36 draws north index1/type18 and south index9/type00.
; Only $4000 animates; $4040 would wait forever for a normal door to open.
; Room97's absent fourth door permits its native saved-door bit $1000 as
; the earned condition. Refuse a changed door composition before enabling.
assert read1($01B6CB) == $BF, "Room door-pointer loader changed"
!D6ChuGate97_Doors = read3(read3($01B6CC)+($97*3))
assert read2(!D6ChuGate97_Doors) == $0063, "Room97 east normal door changed"
assert read2(!D6ChuGate97_Doors+2) == $3660, "Room97 north shutter changed"
assert read2(!D6ChuGate97_Doors+4) == $FFFF, "Room97 saved-door bit1000 requires exactly two doors"

; Long-called from RoomTag39; emitted in the existing Items bank $2B stream.
; ABI: M8/X8, D=0, mirrored-WRAM DBR. Preserve P/X/Y/DBR,
; stack and native tag slot $0E; clobber A (including B) and $00-$03.
D6ChuGate97_Main:
{
  PHP : PHX : PHY
  JSL D6ChuGate97_IsRoom : BCS + : BRL .exit
+
  LDA.b $10 : CMP.b #$07 : BEQ + : BRL .exit
+
  LDA.b $11 : BEQ + : BRL .exit
+
  LDA.b $EE : BEQ + : BRL .exit
+
  ; Refuse partial/unbound data: a live target and the actual native shutter
  ; records are required. This is not a generic room or sprite-ID predicate.
  LDX.b #$0F
  .find_target
  LDA.w SprState,X : CMP.b #$09 : BNE .next_target
  JSL D6ChuGate97_IsTarget : BCS .target_present
  .next_target
  DEX : BPL .find_target
  BRL .exit
  .target_present
  REP #$20
  LDA.w $1982 : CMP.w #$0118 : BEQ + : BRL .exit
+
  LDA.w $1992 : CMP.w #$0900 : BEQ + : BRL .exit
+
  LDA.w $0400 : BIT.w #$1000 : BEQ + : BRL .open
+
  SEP #$20
  LDA.l BombchuOwned : CMP.b #$01 : BEQ + : BRL .closed
+
  LDA.l BombchuSignature : CMP.b #$BC : BEQ + : BRL .closed
+
  LDA.l BombchuIndoors : CMP.b #$01 : BEQ + : BRL .closed
+
  LDA.l BombchuAreaLow : CMP.b #$97 : BEQ + : BRL .closed
+
  LDA.l BombchuAreaHigh : BEQ + : BRL .closed
+
  LDA.l BombchuFloor : BEQ + : BRL .closed
+
  LDA.l BombchuSlot : BNE + : BRL .closed
+
  CMP.b #$03 : BCC + : BRL .closed
+
  DEC A : TAX
  LDA.w $0C4A,X : CMP.b #$07 : BEQ + : BRL .closed
+
  LDA.w $03EA,X : CMP.b #$BC : BEQ + : BRL .closed
+
  LDA.w $0C5E,X : BEQ + : BRL .closed
+
  LDA.w $039F,X : BNE + : BRL .closed ; positive travelling fuse, not expired
+
  ; Existing native travelling center / 15x15 footprint against the 16x16
  ; target at world ($0E90,$1340), not placement-grid or camera coordinates.
  LDA.w $0C04,X : STA.b $00
  LDA.w $0C18,X : STA.b $01
  LDA.w $0BFA,X : STA.b $02
  LDA.w $0C0E,X : STA.b $03
  REP #$20
  LDA.b $00 : SEC : SBC.w #$0E90 : CLC : ADC.w #$0007
  CMP.w #$001E : BCS .closed
  LDA.b $02 : SEC : SBC.w #$1340 : CLC : ADC.w #$0007
  CMP.w #$001E : BCS .closed
  LDA.w $0400 : ORA.w #$1000 : STA.w $0400
  LDA.l $7EF12E : ORA.w #$1000 : STA.l $7EF12E
  SEP #$20
  LDA.b #$01 : STA.w $039F,X ; consume the successful travelling Chu
  REP #$20
  .open
  LDA.w $068C : BIT.w #$4000 : BNE .exit
  STZ.w $0468
  BRA .animate
  .closed
  REP #$20
  ; Door-open state alone cannot earn this puzzle. Let native animation
  ; change the live mask, pixels and collision; never pre-clear $068C.
  LDA.w $0400 : AND.w #$BFFF : STA.w $0400
  LDA.w $068C : BIT.w #$4000 : BEQ .exit
  LDA.w #$0001 : STA.w $0468
  .animate
  STZ.w $068E : STZ.w $0690
  SEP #$20
  LDA.b #$05 : STA.b $11
  .exit
  SEP #$30
  PLY : PLX : PLP
  RTL
}

; M8/X8; preserve A including hidden B, X/Y/DBR/D/stack. C is the
; predicate result; N/Z are clobbered. Main requires native binary arithmetic.
; Keep D6ChuActor_IsRoom/IsLoadedRoom unchanged: Goron NPCs also use them.
D6ChuGate97_IsRoom:
{
  PHA
  LDA.b $1B : CMP.b #$01 : BNE .no
  LDA.b $A1 : BNE .no
  LDA.b $A0 : CMP.b #$97 : BNE .no
  LDA.b $AE : CMP.b #$39 : BNE .no
  LDA.b $AF : BNE .no
  PLA : SEC : RTL
  .no
  PLA : CLC : RTL
}

; AF prep uses the loaded room, never the departing current room.
D6ChuGate97_IsLoadedTarget:
{
  PHA
  LDA.b $1B : CMP.b #$01 : BNE .no
  LDA.w $048F : BNE .no
  LDA.w $048E : CMP.b #$97 : BNE .no
  LDA.b $AE : CMP.b #$39 : BNE .no
  LDA.b $AF : BNE .no
  PLA
  JML D6ChuGate97_IsTarget
  .no
  PLA : CLC : RTL
}

D6ChuGate97_IsTarget:
{
  PHA
  LDA.w SprType,X : CMP.b #$AF : BNE .no
  LDA.w SprSubtype,X : BNE .no
  LDA.w SprFloor,X : BNE .no
  LDA.w SprXH,X : CMP.b #$0E : BNE .no
  LDA.w SprX,X : CMP.b #$90 : BNE .no
  LDA.w SprYH,X : CMP.b #$13 : BNE .no
  LDA.w SprY,X : CMP.b #$40 : BNE .no
  PLA : SEC : RTL
  .no
  PLA : CLC : RTL
}

D6ChuGate97_CodeEnd = pc()
assert D6ChuGate97_CodeStart >= $2B8000, "Room97 gate left the Items stream"
assert D6ChuGate97_CodeEnd <= $2BE000, "Room97 gate reached D8 tile ownership"
