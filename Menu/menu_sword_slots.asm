; Two-slot sword helpers, called with JSL from the Equipment page (bank $2D)
; and Menu_Exit. Assembled in Items bank $2B: Menu bank $2D is full with
; Map & Travel on, and $2E reaches the D8 code slot.
; Heavy sword = Greatblade, found broken (decisions.org 2026-11-16). Broken:
; level 1. Reforged (bit2): level 3. Name and smith text are not approved.
!HEAVY_SWORD_LEVEL        = 3
!HEAVY_SWORD_BROKEN_LEVEL = 1
!HEAVY_SWORD_ICON         = 3
DecompressSwordGraphics_Long = $00D2C8
Palettes_Load_Sword_Long     = $1BED03

; Idempotent; 8-bit A/X/Y, keeps X/Y. Old saves (bit7 clear) copy a 1-4
; Sword into SwordStoryBlade and never grant the heavy sword. Afterwards any
; 1-4 Sword written outside this menu (receipt, pedestal, smith) is a story
; blade, except the heavy level while the heavy sword is equipped.
; 0 and the smith-held $FF leave both slots unchanged.
SwordSlots_Sync:
{
  PHX
  LDA.l SwordSlotFlags : BMI .initialized
  LDA.l Sword : DEC : CMP.b #$04 : BCC +
  LDA.b #$FF                          ; 0, $FF, garbage -> story 0
+
  INC : STA.l SwordStoryBlade
  LDA.b #!SwordSlot_Initialized : STA.l SwordSlotFlags
  BRA .done
.initialized
  LDA.l Sword : DEC : CMP.b #$04 : BCS .done
  INC : TAX
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyEquipped : BEQ .story
  JSL SwordSlots_IsHeavyLevel : BEQ .done
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyEquipped^$FF : STA.l SwordSlotFlags
.story
  TXA : STA.l SwordStoryBlade
.done
  PLX
  RTL
}

; Menu_Exit: refresh Link's sword tiles and palette for the equipped level.
; Only the heavy sword can change Sword in this menu, so saves without it
; skip this and keep vanilla exit behavior. 8-bit A/X/Y.
SwordSlots_ExitReload:
{
  SEP #$30
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyOwned : BEQ .done
  LDA.l Sword : DEC : CMP.b #$04 : BCS .done
  JSL DecompressSwordGraphics_Long
  JSL Palettes_Load_Sword_Long
.done
  SEP #$30
  RTL
}

; Menu_Equipment_Owned for slots 24-26. A = slot; returns the icon variant,
; zero when unavailable (smith-held $FF hides both swords). Caller saved X.
; Slot 26 is the tunic (Menu/menu_tunic.asm): a cursor stop whenever Armor
; is 0-2, so its footer name shows even with one colour owned. M/X=8.
SwordSlots_Variant:
{
  CMP.b #$1A : BEQ .tunic : BCS .none
  TAX
  LDA.l Sword : CMP.b #$FF : BEQ .none
  CPX.b #$19 : BEQ .heavy
  LDA.l SwordStoryBlade : CMP.b #$05 : BCS .none
  RTL                                 ; 0 = no story blade; 1-4 = SwordGFX variant
.heavy
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyOwned : BEQ .done
  LDA.b #!HEAVY_SWORD_ICON
.done
  RTL
.none
  LDA.b #$00
  RTL
.tunic
  JMP Tunic_WornVariant
}

; A on an owned GEAR slot. A = 24 story / 25 heavy / 26 tunic. M/X=8.
SwordSlots_Select:
{
  CMP.b #$1A : BNE +
  JMP Tunic_Cycle
+
  CMP.b #$19 : BEQ .heavy
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyEquipped^$FF : STA.l SwordSlotFlags
  LDA.l SwordStoryBlade : STA.l Sword
  RTL
.heavy
  LDA.l SwordSlotFlags : ORA.b #!SwordSlot_HeavyEquipped : STA.l SwordSlotFlags
  JSL SwordSlots_HeavyLevel : STA.l Sword
  RTL
}

; A = heavy-sword level: reforged 3, broken 1. M=8; keeps X/Y.
SwordSlots_HeavyLevel:
{
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyReforged : BEQ +
  LDA.b #!HEAVY_SWORD_LEVEL
  RTL
+
  LDA.b #!HEAVY_SWORD_BROKEN_LEVEL
  RTL
}

; Z set when X (8-bit) is the heavy-sword level. M/X=8; clobbers A.
SwordSlots_IsHeavyLevel:
{
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyReforged : BEQ +
  CPX.b #!HEAVY_SWORD_LEVEL
  RTL
+
  CPX.b #!HEAVY_SWORD_BROKEN_LEVEL
  RTL
}

; Heavy icon = the level-3 SwordGFX icon with its blade (top two tiles)
; moved from red palette 1 to grey palette 4. Broken: the top-right blade
; tile is the level-1 icon's shorter blade ($CE), so the tip is missing.
; Bank $2D has no room for a new SwordGFX row, so the tiles are written
; into the tilemap buffer.
!HEAVY_ICON_POS       = $018C         ; menu_offset(6,6), asserted in menu_equipment.asm
!HEAVY_ICON_TL        = $308A
!HEAVY_ICON_TR        = $3065
!HEAVY_ICON_BROKEN_TR = $30CE

; Called after the gear icons are drawn. Recolors the heavy icon, then
; returns A = equipped sword slot (24 story, 25 heavy) for the red marker.
; M/X=8.
assert !SwordSlot_HeavyEquipped == $02, "MarkerSlot shifts bit1 into bit0"
SwordSlots_MarkerSlot:
{
  JSL Tunic_DrawArmorLabel
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyOwned : BEQ .marker
  LDA.l Sword : CMP.b #$FF : BEQ .marker
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyReforged
  REP #$20
  BEQ .broken
  LDA.w #!HEAVY_ICON_TR : BRA +
.broken
  LDA.w #!HEAVY_ICON_BROKEN_TR
+
  STA.l $7E110A+!HEAVY_ICON_POS
  LDA.w #!HEAVY_ICON_TL : STA.l $7E1108+!HEAVY_ICON_POS
  SEP #$20
.marker
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyEquipped : LSR : ORA.b #$18
  RTL
}

; Footer name for X = $30 story / $32 heavy / $34 tunic (slot*2): 14 cells
; to $1692. DBR = $2D; $1692 is the WRAM mirror. Returns M/X=8.
SwordSlots_Name:
{
  CPX.b #$34 : BNE .sword
  JSL Tunic_GetWorn : TAX
  LDA.l .tunic_rows,X : BRA .copy
.sword
  LDA.b #28 : CPX.b #$32 : BEQ .copy  ; heavy: name not decided, blank
  LDA.l SwordStoryBlade : CMP.b #$02
  LDA.b #$00 : BCC .copy              ; level 1: Meadow blade
  LDA.b #56                           ; level 2-4: Master Sword
.copy
  REP #$30
  AND.w #$00FF : TAX
  LDY.w #$0000
.loop
  LDA.l .names,X : STA.w $1692,Y
  INX #2 : INY #2 : CPY.w #$001C : BCC .loop
  SEP #$30
  RTL
.tunic_rows
  db 84,112,140                       ; GREEN/BLUE/RED_TUNIC rows below
.names
  ; Items assemble before Menu/menu_text.asm defines the menu font map, so
  ; map only these letters here and restore the table for later Items code.
  pushtable
  'A' = $2550
  'B' = $2551
  'C' = $2552
  'D' = $2553
  'E' = $2554
  'G' = $2556
  'I' = $2558
  'L' = $255B
  'M' = $255C
  'N' = $255D
  'O' = $255E
  'R' = $2561
  'S' = $2562
  'T' = $2563
  'U' = $2564
  'W' = $2566
  '_' = $20F5
  dw "MEADOW_BLADE__"
  dw "______________"
  dw "MASTER_SWORD__"
  dw "GREEN_TUNIC___"
  dw "BLUE_TUNIC____"
  dw "RED_TUNIC_____"
  pulltable
}
