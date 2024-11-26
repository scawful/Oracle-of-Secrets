pushpc

org $1E7F21
Sprite3_Move:

; *$F3593-$F35C7 JUMP LOCATION
org $1EB593
Arrghus_ApproachTargetSpeed:
{
  LDA.w SprTimerA, X : BNE .delay
    INC $0D80, X
    JSL AdvancedArrghus : NOP
  .delay
}

pullpc
AdvancedArrghus:
{
  LDA.w SprDefl, Y : ORA.b #$08 : STA.w SprDefl, Y
  LDA.b #$04 : STA.w SprBump, Y

  JSL Sprite_SpawnFireball
  LDA.b #$50 : STA.w SprTimerA, X
  RTL
}
