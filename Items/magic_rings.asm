; =========================================================
; Magic Rings

; ..pa slbh
;   p - power 
;   a - armor  
;   s - steadfast
;   l - light 
;   b - blast
;   h - heart
FOUNDRINGS     = $7EF3D7
MAGICRINGS     = $7EF3D8

RingSlot1      = $7EF38C
RingSlot2      = $7EF38D
RingSlot3      = $7EF38E

; Power     - Attack Up, Defense Down
; Armor     - Defense Up, Attack Down

; =========================================================
; Steadfast - Less knockback

MagicRing_CheckForSteadfast:
{
  LDA.l RingSlot1 : AND.b #$07 : BEQ +
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

; =========================================================
; Light     - Sword beam at -2 hearts

MagicRing_CheckForLight:
{
  PHA 
  LDA.l RingSlot1 : AND.b #$05 : BEQ +
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

; =========================================================
; Blast     - Bomb Damage up

MagicRing_CheckForBlast:
{
  CPX #$07 : BNE +
    LDA.l RingSlot1 : AND.b #$06 : BEQ +
      LDA.b #$0D
      RTL
  +
  LDA.l AncillaDamageClasses, X
  RTL
}

AncillaDamageClasses = $06EC7E

pushpc
org $06ECBF
  JSL MagicRing_CheckForBlast
pullpc

; =========================================================
; Heart     - Slowly regenerate hearts

MagicRings_CheckForHeart:
{
  LDA.l RingSlot1 : AND.b #$04 : BEQ ++
    LDA.l CURHP : CMP.l MAXHP : BCS ++
      LDA.l FrameCounter : LSR #2 : AND.b #$3F : BEQ +
        JMP ++
      +
      LDA.l CURHP : CLC : ADC.b #$01 : STA.l CURHP
  ++
  LDA.b $F5
  AND.b #$80
  RTL
}

pushpc
org $07810C
  JSL MagicRings_CheckForHeart
pullpc