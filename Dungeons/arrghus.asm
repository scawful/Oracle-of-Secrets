pullpc ; Bank 33
AdvancedArrghus:
{
  LDA $0CAA, Y : ORA.b #$08 : STA $0CAA, Y
  LDA.b #$04 : STA $0CD2, Y
  
  JSL Sprite_SpawnFireball
  LDA.b #$50 : STA $0DF0, X
  RTL
}
pushpc

org $1E7F21 
Sprite3_Move:

; *$F3593-$F35C7 JUMP LOCATION
org $1EB593
Arrghus_ApproachTargetSpeed:
{
    LDA $0DF0, X : BNE .delay
    
    INC $0D80, X
    
    JSL AdvancedArrghus : NOP

.delay
}