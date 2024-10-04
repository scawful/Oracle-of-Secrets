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
RingSlotsNum   = $7EF38F

DamageSubclassValue = $0DB8F1

pushpc
; Sprite_ApplyCalculatedDamage
org $06EDC0
JSL MagicRing_CheckForPower
pullpc

; Power     - Attack Up, Defense Down
MagicRing_CheckForPower:
{
  LDA.l RingSlot1 : AND.b #$20 : BEQ +
  LDA.l RingSlot2 : AND.b #$20 : BEQ +
  LDA.l RingSlot3 : AND.b #$20 : BEQ +
    LDA.w $0CF2 : CMP.b #$04 : BCS .not_sword
                  CMP.b #$01 : BCC .not_sword
     LDA.l DamageSubclassValue, X
     CLC : ADC.b #$10
     RTL
    .not_sword
  +
  LDA.l DamageSubclassValue, X
  RTL
}

pushpc
; Sprite_AttemptDamageToLinkPlusRecoil
org $06F400
  JSL MagicRing_CheckForArmor
pullpc

; $0373 - Damage queue for Link
Sprite_BumpDamageGroups = $06F427

; Armor     - Defense Up, Attack Down
MagicRing_CheckForArmor:
{
  LDA.w Sprite_BumpDamageGroups, Y : STA.w $0373
  LDA.l RingSlot1 : AND.b #$10 : BEQ +
  LDA.l RingSlot2 : AND.b #$10 : BEQ +
  LDA.l RingSlot3 : AND.b #$10 : BEQ +
    ; Reduce the damage queue by half
    LDA $0373 : BEQ +
      LSR : STA $0373
  +
  RTL
}


; =========================================================
; Steadfast - Less knockback

MagicRing_CheckForSteadfast:
{
  LDA.l RingSlot1 : AND.b #$07 : BEQ +
  LDA.l RingSlot2 : AND.b #$07 : BEQ +
  LDA.l RingSlot3 : AND.b #$07 : BEQ +
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
  LDA.l RingSlot2 : AND.b #$05 : BEQ +
  LDA.l RingSlot3 : AND.b #$05 : BEQ +
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
    LDA.l RingSlot2 : AND.b #$06 : BEQ +
    LDA.l RingSlot3 : AND.b #$06 : BEQ +
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
  LDA.l RingSlot2 : AND.b #$04 : BEQ ++
  LDA.l RingSlot3 : AND.b #$04 : BEQ ++
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

