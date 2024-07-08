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
; Blast     - Bomb Damage up
; Heart     - Slowly regenerate hearts