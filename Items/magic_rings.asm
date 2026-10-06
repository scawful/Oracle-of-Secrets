; =========================================================
; Magic Rings

; ..pa hlbs  (bit order used by the ring menu: RingMenu_Controls .rings,
;             Menu_DrawMagicRingsInBox, Menu_RingNames)
;   p - power      $20  ring ID 2
;   a - armor      $10  ring ID 3
;   h - heart      $08  ring ID 4
;   l - light      $04  ring ID 5
;   b - blast      $02  ring ID 6
;   s - steadfast  $01  ring ID 7
; (Before 2026-09-25 this comment said ..pa slbh; the menu names bit $08
;  HEART and bit $01 STEADFAST.)
;
; FOUNDRINGS   - rings found, not yet appraised (Eon Zora, Error NPC)
; MAGICRINGS   - rings appraised and owned (Vasu ORs FOUNDRINGS in)
; RingSlot1-3  - equipped ring IDs (0 = empty, 2-7 = ring menu index + 2).
;                With !ENABLE_ONE_RING only RingSlot1 is used.
;
; Save bytes: see RingSaveBlock in Core/sram.asm.
if !ENABLE_RING_SRAM_RELOCATE == 1
FOUNDRINGS     = RingSaveBlock+0   ; $7EF3A1
MAGICRINGS     = RingSaveBlock+1   ; $7EF3A2

RingSlot1      = RingSaveBlock+2   ; $7EF3A3
RingSlot2      = RingSaveBlock+3   ; $7EF3A4
RingSlot3      = RingSaveBlock+4   ; $7EF3A5
; RingSaveBlock+5 ($7EF3A6) was RingSlotsNum (never read or written); it is
; PortalRodOwned now (Core/sram.asm).
else
; Legacy addresses. They alias other save data (known bug, 2026-09-25):
;   FOUNDRINGS   = SideQuestProgress   ($7EF3D7)
;   MAGICRINGS   = SideQuestProgress2  ($7EF3D8)
;   RingSlot2    = Pineapples          ($7EF38D)
;   RingSlotsNum = RockMeatCount       ($7EF38F)
FOUNDRINGS     = $7EF3D7
MAGICRINGS     = $7EF3D8

RingSlot1      = $7EF38C
RingSlot2      = $7EF38D
RingSlot3      = $7EF38E
RingSlotsNum   = $7EF38F
endif

DamageSubclassValue = $0DB8F1

if !ENABLE_RING_SRAM_RELOCATE == 1
; Ring IDs stored in RingSlot1-3: ring menu cursor index + 2
; (RingMenu_Controls in Menu/menu.asm; names in Menu_RingNames).
!RingID_Power     = $02
!RingID_Armor     = $03
!RingID_Heart     = $04
!RingID_Light     = $05
!RingID_Blast     = $06
!RingID_Steadfast = $07

; In: A = ring ID, 8-bit A. Out: C set = the ring is in any equipped slot
; (with !ENABLE_ONE_RING: the ring is RingSlot1, the only worn ring).
; Keeps A, X, Y. Called with JSR from the checks below (same bank).
MagicRing_IsEquipped:
{
  CMP.l RingSlot1 : BEQ .equipped
if !ENABLE_ONE_RING == 0
  CMP.l RingSlot2 : BEQ .equipped
  CMP.l RingSlot3 : BEQ .equipped
endif
    CLC
    RTS
  .equipped
  SEC
  RTS
}
endif

if !ENABLE_TRUTHFUL_CONTROLS == 1
; Ring grant (Eon Zora message $1AE, Error message $121). Marks one ring as
; found (FOUNDRINGS), picked at random among the rings that are neither found
; nor owned (MAGICRINGS). Grants nothing while a found ring still waits for
; Vasu's appraisal (one ring per appraisal, as Vasu's price is per ring), or
; when every ring is found or owned. Replaces GetRandomInt AND #$06 STA
; FOUNDRINGS, which could only give Blast ($02) and/or Light ($04), or none,
; and overwrote a ring that was not appraised yet.
; In: 8-bit A/X/Y. Out: C set = a ring was granted. Keeps X, Y.
MagicRing_GrantUnfound:
{
  PHX : PHY
  ; A found ring still waits for appraisal: grant nothing.
  LDA.l MAGICRINGS : EOR.b #$FF : AND.l FOUNDRINGS : AND.b #$3F : BNE .none
  ; Candidates: neither found nor owned.
  LDA.l FOUNDRINGS : ORA.l MAGICRINGS : EOR.b #$FF : AND.b #$3F : BEQ .none
  PHA                                    ; $01,S = candidate bits
  LDX.b #$00                             ; X = number of candidates
  .count
    LSR A : BCC .count_next
      INX
    .count_next
  CMP.b #$00 : BNE .count
  PHX                                    ; $01,S = count, $02,S = candidates
  JSL GetRandomInt
  .mod
    CMP $01,S : BCC .have_index
    SBC $01,S
    BRA .mod
  .have_index
  TAY                                    ; Y = pick (0 to count-1)
  PLX                                    ; drop the count
  LDX.b #$01                             ; X = ring bit
  .scan
    TXA : AND $01,S : BEQ .scan_next
      DEY : BMI .grant
    .scan_next
    TXA : ASL A : TAX
    BRA .scan
  .grant
  PLA                                    ; drop the candidates
  TXA : ORA.l FOUNDRINGS : STA.l FOUNDRINGS
  PLY : PLX
  SEC
  RTL

  .none
  PLY : PLX
  CLC
  RTL
}
endif

pushpc
; Sprite_ApplyCalculatedDamage
org $06EDC0 ; @hook module=Items
JSL MagicRing_CheckForPower
pullpc

if !ENABLE_RING_SRAM_RELOCATE == 1
; Power     - Attack Up: sword damage classes 1-3 deal +$10.
;             "Defense Down" is not implemented.
; Replaces LDA.l DamageSubclassValue, X (M=8, X=8). Out: A = damage.
MagicRing_CheckForPower:
{
  LDA.b #!RingID_Power : JSR MagicRing_IsEquipped : BCC .vanilla
  LDA.w $0CF2 : CMP.b #$04 : BCS .vanilla
                CMP.b #$01 : BCC .vanilla
  LDA.l DamageSubclassValue, X
  ; Keep immunity ($00) and the special codes ($F9-$FF) unchanged.
  CMP.b #$01 : BCC .done
  CMP.b #$E9 : BCS .done
    CLC : ADC.b #$10
  .done
  RTL

  .vanilla
  LDA.l DamageSubclassValue, X
  RTL
}
else
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
endif

pushpc
; Sprite_AttemptDamageToLinkPlusRecoil
org $06F400 ; @hook module=Items
  JSL MagicRing_CheckForArmor
  ; The hook replaces LDA.w $F427,Y : STA.w $0373 (6 bytes). Without these
  ; NOPs the last 2 bytes ($73 $03) run as ADC ($03,S),Y after the RTL.
  NOP #2
pullpc

; $0373 - Damage queue for Link
Sprite_BumpDamageGroups = $06F427

if !ENABLE_RING_SRAM_RELOCATE == 1
; Armor     - Defense Up: contact damage to Link (Sprite_AttemptDamageToLink-
;             PlusRecoil) is halved. "Attack Down" is not implemented.
MagicRing_CheckForArmor:
{
  LDA.w Sprite_BumpDamageGroups, Y : STA.w $0373
  LDA.b #!RingID_Armor : JSR MagicRing_IsEquipped : BCC .done
    LDA.w $0373 : LSR : STA.w $0373
  .done
  RTL
}
else
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
endif


; =========================================================
; Steadfast - Less knockback

if !ENABLE_RING_SRAM_RELOCATE == 1
MagicRing_CheckForSteadfast:
{
  ; Steadfast reduces knockback only. Feather jumps and ledge hops also run
  ; Link_HandleRecoiling with $4D = 2; keep their speed.
  LDA.b $4D : CMP.b #$02 : BEQ .done
  LDA.b #!RingID_Steadfast : JSR MagicRing_IsEquipped : BCC .done
    STZ.b LinkRecoilX
    STZ.b LinkRecoilY
  .done
  STZ.b $67                 ; replaced vanilla code ($07E1BE)
  LDY.b #$08                ; replaced vanilla code ($07E1C0)
  RTL
}
else
MagicRing_CheckForSteadfast:
{
  ; Steadfast reduces knockback only. Feather jumps and ledge hops also run
  ; Link_HandleRecoiling with $4D = 2; keep their speed.
  LDA.b $4D : CMP.b #$02 : BEQ +
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
endif

pushpc
org $07E1BE ; @hook module=Items
  JSL MagicRing_CheckForSteadfast
pullpc

; =========================================================
; Light     - Sword beam at -2 hearts

if !ENABLE_RING_SRAM_RELOCATE == 1
; In: A = MaxHP - 4 (vanilla). Out: C from CMP CurrentHealth (C set = no beam).
MagicRing_CheckForLight:
{
  PHA
  LDA.b #!RingID_Light : JSR MagicRing_IsEquipped
  PLA                       ; keeps C
  BCC .compare
    SEC : SBC.b #$10 : BCS .compare
      LDA.b #$00            ; MaxHP < 20: do not wrap
  .compare
  CMP.l $7EF36D
  RTL
}
else
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
endif

pushpc
org $079C77 ; @hook module=Items
  JSL MagicRing_CheckForLight
pullpc

; =========================================================
; Blast     - Bomb Damage up

if !ENABLE_RING_SRAM_RELOCATE == 1
; In: X = ancilla ID (8-bit). Bomb ($07) uses damage class $0D instead of $08.
MagicRing_CheckForBlast:
{
  CPX.b #$07 : BNE .vanilla
    LDA.b #!RingID_Blast : JSR MagicRing_IsEquipped : BCC .vanilla
      LDA.b #$0D
      RTL
  .vanilla
  LDA.l AncillaDamageClasses, X
  RTL
}
else
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
endif

AncillaDamageClasses = $06EC7E

pushpc
org $06ECBF ; @hook module=Items
  JSL MagicRing_CheckForBlast
pullpc

; =========================================================
; Heart     - Slowly regenerate hearts

if !ENABLE_RING_SRAM_RELOCATE == 1
; +1 HP on 4 frames of every 256 (half a heart about every 4.3 s).
MagicRings_CheckForHeart:
{
  LDA.b #!RingID_Heart : JSR MagicRing_IsEquipped : BCC .done
  LDA.l CURHP : CMP.l MAXHP : BCS .done
  LDA.l FrameCounter : LSR #2 : AND.b #$3F : BNE .done
    LDA.l CURHP : INC A : STA.l CURHP
  .done
  LDA.b $F5                 ; replaced vanilla code ($07810C)
  AND.b #$80
  RTL
}
else
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
endif

pushpc
org $07810C ; @hook module=Items
  JSL MagicRings_CheckForHeart
pullpc
