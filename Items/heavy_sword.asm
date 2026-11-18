; Heavy sword = Greatblade, found broken (decisions.org 2026-11-16); name
; and smith text not approved. Broken: Sword level 1. Reforged
; (SwordSlotFlags bit2): level 3. In both states, while the heavy slot is
; equipped: no sword beam, a slower windup, no shield draw and no shield
; block. The story blade keeps vanilla behavior.
; $7EF35A (shield level) is never written. Assembled in Items bank $2B with
; menu_sword_slots.asm.

; Carry set = heavy slot equipped (bit1) and Sword holds the heavy level
; for its state. Any M/X; keeps A/X/Y and every flag except carry.
HeavySword_Active:
{
  PHP : SEP #$30 : PHA : PHX
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyEquipped : BEQ .no
  LDA.l Sword : TAX
  JSL SwordSlots_IsHeavyLevel : BNE .no
  PLX
  PLA : PLP : SEC
  RTL
.no
  PLX : PLA : PLP : CLC
  RTL
}

; $079C7D, M=8: beam level read. Heavy reports 0, so INC/AND #$FE skips the beam.
HeavySword_BeamLevel:
{
  JSL HeavySword_Active : BCC +
  LDA.b #$00
  RTL
+
  LDA.l Sword
  RTL
}

; $079D21, M/X=8, X = swing step 1-8. Each step lasts timer+1 frames; the
; heavy sword adds 1 frame to windup steps 1-4 (+4 frames per swing).
HeavySword_SwingTimer:
{
  LDA.l $079CBF,X : STA.b $3D
  JSL HeavySword_Active : BCC .done
  CPX.b #$05 : BCS .done
  INC.b $3D
.done
  RTL
}

; $06F18B (projectile block) and $0596CB (fireball block), M=8: shield level
; read. Heavy reports 0 (sets Z) so the shield never blocks.
HeavySword_ShieldLevel:
{
  JSL HeavySword_Active : BCC +
  LDA.b #$00
  RTL
+
  LDA.l $7EF35A
  RTL
}

; Grants the Broken Greatblade (owned, not reforged; plus the initialized
; bit after an old-save sync). Not wired to the smith's partner: the text is
; a draft. Any M/X; keeps A/X/Y.
HeavySword_GrantBroken:
{
  PHP : SEP #$30 : PHA
  LDA.l SwordSlotFlags : BMI +
  JSL SwordSlots_Sync
+
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyReforged^$FF
  ORA.b #!SwordSlot_HeavyOwned|!SwordSlot_Initialized
  STA.l SwordSlotFlags
  PLA : PLP
  RTL
}

; The smiths reforge the Greatblade: sets the reforged bit and, while the
; heavy slot is equipped, raises Sword to the reforged level and reloads its
; tiles/palette. Not wired to the smiths. Any M/X, DP=$0000; keeps A/X/Y.
HeavySword_Reforge:
{
  PHP : SEP #$30 : PHA : PHX : PHY
  LDA.l SwordSlotFlags : BMI +
  JSL SwordSlots_Sync
+
  LDA.l SwordSlotFlags
  ORA.b #!SwordSlot_HeavyOwned|!SwordSlot_HeavyReforged|!SwordSlot_Initialized
  STA.l SwordSlotFlags
  AND.b #!SwordSlot_HeavyEquipped : BEQ +
  LDA.b #!HEAVY_SWORD_LEVEL : STA.l Sword
  JSL SwordSlots_ExitReload
  LDA.b #$01 : STA.b $15              ; upload the new sword palette at NMI
+
  PLY : PLX : PLA : PLP
  RTL
}

pushpc
org $079C7D ; @hook module=Items
  assert read4($079C7D) == $7EF359AF, "HeavySword: $079C7D is not LDA.l $7EF359"
  JSL HeavySword_BeamLevel
org $079D21 ; @hook module=Items
  assert read4($079D21) == $859CBFBD, "HeavySword: $079D21 is not LDA.w SwordSwingTimers,X"
  assert read1($079D25) == $3D, "HeavySword: $079D24 is not STA.b $3D"
  JSL HeavySword_SwingTimer : NOP
org $06F18B ; @hook module=Items
  assert read4($06F18B) == $7EF35AAF, "HeavySword: $06F18B is not LDA.l $7EF35A"
  JSL HeavySword_ShieldLevel
org $0596CB ; @hook module=Items
  assert read4($0596CB) == $7EF35AAF, "HeavySword: $0596CB is not LDA.l $7EF35A"
  JSL HeavySword_ShieldLevel
pullpc
