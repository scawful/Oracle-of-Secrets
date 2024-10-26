; Contains all the dreams in the game
; Each dream is a separate subroutine

; To enter a dream, Link will see the Maku tree
; after getting an essence from a dungeon.
; We will put the player into LinkState_Sleeping

Link_EnterDream:
{
  PHB : PHK : PLB

  JSR Link_HandleDreams

  PLB

  RTL
}

Link_HandleDreams:
{
  LDA.w CurrentDream
  JSL JumpTableLocal

  dw Dream_MushroomGrotto
  dw Dream_TailPalace
  dw Dream_KalyxoCastle
  dw Dream_ZoraTemple
  dw Dream_GlaciaEstate
  dw Dream_GoronMines
  dw Dream_DragonShip

  Dream_MushroomGrotto:
  {
    LDA.l DREAMS : ORA.b #%00000001 : STA.l DREAMS
    LDX.b #$00
    JSR Link_FallIntoDungeon
    RTS
  }

  Dream_TailPalace:
  {
    LDA.l DREAMS : ORA.b #%00000010 : STA.l DREAMS
    RTS
  }

  Dream_KalyxoCastle:
  {
    LDA.l DREAMS : ORA.b #%00000100 : STA.l DREAMS
    RTS
  }

  Dream_ZoraTemple:
  {
    LDA.l DREAMS : ORA.b #%00001000 : STA.l DREAMS
    RTS
  }

  Dream_GlaciaEstate:
  {
    LDA.l DREAMS : ORA.b #%00010000 : STA.l DREAMS
    RTS
  }

  Dream_GoronMines:
  {
    LDA.l DREAMS : ORA.b #%00100000 : STA.l DREAMS
    RTS
  }

  Dream_DragonShip:
  {
    LDA.l DREAMS : ORA.b #%01000000 : STA.l DREAMS
    RTS
  }
}

; Takes X as argument for the entrance ID
Link_FallIntoDungeon:
{
  LDA.w .entrance, X
  STA.w $010E
  STZ.w $010F

  LDA.b #$20 : STA.b $5C
  LDA.b #$01 : STA.b LinkState
  LDA.b #$11 : STA.b $10
  STZ.b $11 : STZ.b $B0

  RTS
  .entrance
  db $78 ; 0x00 - Deku Dream
  db $79 ; 0x01 - Castle Dream 
  db $7A ; 0x02 -
  db $81 ; 0x03
}

SummonGuards:
{
  LDA.l SWORD : CMP.b #$02 : BNE +
    JSR Overlord_SpawnSoldierPath
  +
  RTL
}

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
    LDA.w $0FB5 : STA.w $0DE0,Y

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

org $09B7BE
  dw Overlord_KalyxoCastleGuards

org $09F253
Overlord_KalyxoCastleGuards:
  JSL SummonGuards
  RTS

pullpc

print "End of all_dreams.asm             ", pc
