; =========================================================
; Magic Rings

; Power     - Attack Up, Defense Down
; Armor     - Defense Up, Attack Down

; Steadfast - Less knockback
MagicRing_CheckForSteadfast:
{
  LDA.l MAGICRINGS : AND.b #$08 : BEQ +
    STZ.b LinkRecoilX
    STZ.b LinkRecoilY
  +
  #_07E1BE: STZ.b $67

  #_07E1C0: LDY.b #$08

  RTL
}

pushpc
org $07E1BE
  JSL MagicRing_CheckForSteadfast
pullpc

; Light     - Sword beam at -2 hearts

MagicRing_CheckForLight:
{
  PHA 
  LDA.l MAGICRINGS : AND.b #$04 : BEQ +
    PLA
    SEC
    SBC.b #$10
    CMP.l $7EF36D
    RTL
  +
  PLA
  CMP.l $7EF36D
  RTL
}

pushpc

org $079C77
  JSL MagicRing_CheckForLight

pullpc 

; Blast     - Bomb Damage up
; Heart     - Slowly regenerate hearts