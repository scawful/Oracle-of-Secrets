; =========================================================
; Exact Goron88 shared-stop ownership; no new route or save state.
; Source: native01 game1fa and existing action7 route semantics.
; Verification: focused actualAsarCPU; successor native not run.
; The two code chunks use existing sprite-stream tails, bank31 and2C.
; =========================================================

; Exact room88 shared stop: T3 remains a distinct vehicle, dormant while
; T10 occupies this dock. This is the existing action7 representation.
; Called before Long's dormant early exit so departure can wake T3.
; M/X8, D0; preserve P/X/Y/DBR and all scratch. Only T3's action changes.
Goron88_SharedStopOccupancy:
{
  PHP
  LDA.b $1B : BNE + : PLP : RTL
+
  LDA.b $EE : BEQ + : PLP : RTL
+
  REP #$20
  LDA.b $10 : CMP.w #$0007 : BEQ + : PLP : RTL
+
  LDA.b $A0 : CMP.w #$0088 : BEQ + : PLP : RTL
+
  SEP #$20
  LDA.w SprState,X : CMP.b #$09 : BEQ + : PLP : RTL
+
  LDA.w SprSubtype,X : CMP.b #$03 : BEQ + : PLP : RTL
+
  LDA.w SprFloor,X : BEQ + : PLP : RTL
+
  LDA.w SprMiscG,X : ORA.w SprHeight,X : BEQ + : PLP : RTL
+
  LDA.w SprMiscB,X : CMP.b #$03 : BEQ + : PLP : RTL
+
  LDA.w SprAction,X : BEQ .idle
  CMP.b #$07 : BEQ .idle
  PLP : RTL
  .idle
  JML Goron88_SharedStopCoordinates
}

; Emit the coordinate/actor scan at the normal bank2C sprite cursor.
; The front chunk tail-jumps here with its original PHP still stacked.
macro Goron88_EmitSharedStopScan()
Goron88_SharedStopCoordinates:
{
  LDA.w SprXH,X : XBA : LDA.w SprX,X
  REP #$20
  CMP.w #$1160 : BEQ + : PLP : RTL
+
  SEP #$20
  LDA.w SprYH,X : XBA : LDA.w SprY,X
  REP #$20
  CMP.w #$10D0 : BEQ + : PLP : RTL
+
  SEP #$20
  PHY
  LDY.b #$0F
  .scan
  LDA.w SprState,Y : CMP.b #$09 : BNE .next
  LDA.w SprType,Y : CMP.b #Sprite_Minecart : BNE .next
  LDA.w SprSubtype,Y : CMP.b #$0A : BNE .next
  LDA.w SprFloor,Y : BNE .next
  LDA.w SprMiscG,Y : ORA.w SprHeight,Y : BNE .next
  LDA.w SprAction,Y : CMP.b #$07 : BCS .next
  ; Body-clearance square centered on the exact BA stop. At distance32
  ; the incoming cart is clear and T3 can be visible again.
  LDA.w SprXH,Y : XBA : LDA.w SprX,Y
  REP #$20
  SEC : SBC.w #$1160 : CLC : ADC.w #$001F
  CMP.w #$003F : BCS .next_wide
  SEP #$20
  LDA.w SprYH,Y : XBA : LDA.w SprY,Y
  REP #$20
  SEC : SBC.w #$10D0 : CLC : ADC.w #$001F
  CMP.w #$003F : BCS .next_wide
  SEP #$20
  LDA.b #$07 : STA.w SprAction,X
  BRA .done
  .next_wide
  SEP #$20
  .next
  DEY : BPL .scan
  LDA.w SprAction,X : CMP.b #$07 : BNE .done
    STZ.w SprAction,X ; untouched BA/West facing resumes normal idle0
  .done
  PLY
  PLP
  RTL
}
endmacro
