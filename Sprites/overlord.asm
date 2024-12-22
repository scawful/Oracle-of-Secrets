; Overlord Sprites and Events

SummonGuards:
{
  LDA.l SWORD : CMP.b #$02 : BNE +
    JSR Overlord_SpawnSoldierPath
  +
  RTL
}

; TimerB - Manages spawn rate
Overlord_SpawnSoldierPath:
{
  LDA.w OverlordTimerB, X : CMP.b #$80 : BEQ .spawn
    DEC.w OverlordTimerB, X
    RTS
  .spawn

  ; JSL GetRandomInt : AND.b #$1F
  ; CLC : ADC.b #$60 : STA.w OverlordTimerB, X
  INC.w OverlordTimerB, X

  STZ.b $00
  LDY.b #$0F
  .next_check
  LDA.w SprState, Y : BEQ .skip
    LDA.w SprType, Y : CMP.b #$41 : BNE .skip
      INC.b $00
  .skip
  DEY
  BPL .next_check

  LDA.b $00 : CMP.b #$05 : BCS .exit
    LDY.b #$0C
    LDA.b #$41 ; SPRITE 41 - Blue Soldier
    JSL Sprite_SpawnDynamically_slot_limited : BMI .exit

    LDA.b $05 : STA.w SprX,Y
    LDA.b $06 : STA.w SprXH,Y
    LDA.b $07 : STA.w SprY,Y
    LDA.b $08 : STA.w SprYH,Y

    LDA.w .soldier_position_x, X : STA.w SprX,Y
    LDA.w .soldier_position_y, X : STA.w SprY,Y
    LDA.w $0B40,X : STA.w SprFloor,Y
    LDA.b #$20 : STA.w SprTimerA,Y
    LDA.w $0FB5 : STA.w SprMiscC,Y
  .exit
  RTS

  .soldier_position_x
  db $30, $C0, $30, $C0, $50, $A0

  .soldier_position_y
  db $70, $70, $98, $98, $C0, $C0

  .soldier_direction
  db $00, $01, $00, $01, $03, $03

  .soldier_palette
  db $09, $09, $09, $09, $07, $09
}


pushpc

; Overlord04_Unused
org $09B7AE
  dw Overlord_KalyxoCastleGuards

org $09F253
Overlord_KalyxoCastleGuards:
  JSL SummonGuards
  RTS

pullpc

print "End of overlord.asm             ", pc
