; =========================================================
; Garo Master prototype: timed contact parry, then Y counter.
; Player art by Herowho (garomaster.1.zspr); palette 1 retained.
; Gameplay entries use M/X=8 except the documented Link_Main frame hook.
; X/Y are preserved. State is volatile.
; =========================================================

pushpc
org $07800F
; @hook GaroMask_FrameTick kind=jsl target=GaroMask_FrameTick
; @source usdasm/bank_07.asm:Link_Main ($07800F-$078013)
; @assumption M=16, DBR=$07; inherited index width is preserved.
; Replaces SEP #$20 / STZ $0FC1, replayed by the helper.
  JSL GaroMask_FrameTick
  NOP
assert pc() == $078014
pullpc

; Link_Main reaches this once before state dispatch, including carrying,
; recoil, swimming and item states that never call Link_HandleYItem.
; Preserve full A/X/Y/DBR and precisely the flags after the displaced SEP.
GaroMask_FrameTick:
{
  %a8()
  STZ.w $0FC1
  PHP
  %m16()
  PHA : PHX : PHY : PHB
  %m8()
  ; DBR remains $07 so absolute WRAM accesses stay valid in bank $42 code.
if !ENABLE_MINISH_AUTO_PORTAL == 1
  ; This always-included Link_Main hook also covers GBC and non-Y-item states.
  JSL MinishPortal_Maintain
endif
  JSL GaroMask_CanAct : BCS .active
  JSL GaroMask_Clear
  BRA .restore
  .active
  LDA.w GaroGuardTimer : BEQ +
  DEC.w GaroGuardTimer
  +
  LDA.w GaroCounterTimer : BEQ +
  BMI .counter_live
  DEC.w GaroCounterTimer
  BRA +
  .counter_live
  ; Bit 7 = a counter slash is live (set only by GaroMask_CounterInput). It
  ; ends when vanilla resets the sword ($3A bit 7 clear) or the slash turns
  ; into a spin charge, poke or spin ($3C >= 9, unsigned).
  LDA.b $3A : BPL .counter_done
  LDA.b $3C : CMP.b #$09 : BCC +
  .counter_done
  STZ.w GaroCounterTimer
  +
  LDA.w GaroCooldown : BEQ +
  DEC.w GaroCooldown
  +
  .restore
  PLB
  %m16()
  PLY : PLX : PLA
  PLP
  RTL
}

UpdateGaroPalette:
{
  PHP : REP #$30
  PHX
  LDX.w #$001E
  .loop
  LDA.l GaroMasterPalette, X : STA.l $7EC6E0, X
  DEX : DEX : BPL .loop
  PLX : SEP #$20
  INC.b $15
  PLP
  RTL
}

GaroMasterPalette:
  dw $0000
  incbin "gfx/garo_master_palette.bgr555"
assert pc()-GaroMasterPalette == $20

GaroMask_Clear:
{
  STZ.w GaroGuardTimer
  STZ.w GaroCounterTimer
  STZ.w GaroCooldown
  RTL
}

; Carry set only during normal controllable gameplay. A guard does not survive
; doorway movement, text, transitions, recoil, swimming, lifting, or a cutscene.
GaroMask_CanAct:
{
  LDA.w !CurrentMask : CMP.b #$08 : BNE .no
  LDA.l GaroMaskOwned : CMP.b #$01 : BNE .no
  LDA.b $10 : CMP.b #$07 : BEQ .module_ok
  CMP.b #$09 : BEQ .module_ok
  CMP.b #$0B : BNE .no
  .module_ok
  LDA.b $11 : ORA.b $6C : ORA.b $5D : BNE .no
  LDA.w $0FFC : ORA.w $02E4 : ORA.w $0301 : ORA.w $037A : BNE .no
  LDA.w $0308 : ORA.w $0376 : ORA.w $0377 : BNE .no
  LDA.b $46 : BNE .no
  SEC : RTL
  .no
  CLC : RTL
}

GaroMask_Tick:
{
  JSL GaroMask_CanAct : BCS .active
  JML GaroMask_Clear
  .active
  LDA.b $F4 : AND.b #$40 : BEQ .done
  ; LinkState_Default runs the Y-item tick before its sword-input handler.
  ; Leave a counter press for that later hook; the effective Y action is 0.
  LDA.w GaroCounterTimer : BNE .done
  ; Y never dispatches the selected normal item while this form is active.
  LDA.b #$40 : TRB.b $F4
  LDA.w GaroCooldown : BNE .done
  LDA.b $3C : BNE .done
  LDA.b $3A : AND.b #$C0 : BNE .done
  LDA.b #$0C : STA.w GaroGuardTimer
  LDA.b #$20 : STA.w GaroCooldown
  LDA.b #$05 : STA.w $012E ; guard cue; the same clink confirms contact
  .done
  RTL
}

; Called by the existing contact-damage/Armor Ring hook after damage is queued.
; This deliberately does not catch floor damage or grant persistent immunity.
; Contact recoil has already been set, so CanAct's recoil guard is not used.
; The hook runs only on a real contact (vanilla $06F3DB passed its $031F/$037B
; gate), so the contact itself is the trigger. The queued damage is not
; tested: the Armor Ring halves a 1-damage bump to 0 before this runs.
GaroMask_ParryContact:
{
  PHP : PHA
  LDA.w !CurrentMask : CMP.b #$08 : BNE .done
  LDA.l GaroMaskOwned : CMP.b #$01 : BNE .done
  LDA.w GaroGuardTimer : BEQ .done
  LDA.b $11 : ORA.b $6C : ORA.b $5D : BNE .done
  LDA.w $0FFC : ORA.w $02E4 : BNE .done
  LDA.w $0308 : ORA.w $0376 : ORA.w $0377 : BNE .done
  STZ.w $0373
  STZ.b $46 : STZ.b $4D
  STZ.b $27 : STZ.b $28
  STZ.w GaroGuardTimer
  LDA.b #$20 : STA.w GaroCounterTimer
  LDA.b #$0C : STA.w $031F ; brief recovery from the blocked contact
  LDA.b #$05 : STA.w $012E
  .done
  PLA : PLP : RTL
}

; Runs at the existing sword-input hook AFTER the Y-item tick. A successful
; parry grants one Y-triggered normal sword slash; vanilla owns its animation,
; hitbox and damage. No equipment or synthetic sword state is installed.
GaroMask_CounterInput:
{
  JSL GaroMask_CanAct : BCC .done
  LDA.w GaroCounterTimer : BEQ .done
  BMI .done ; a counter slash is already live
  LDA.b $F4 : AND.b #$40 : BEQ .done
  LDA.b $3C : BNE .done
  LDA.b $3A : AND.b #$C0 : BNE .done
  LDA.l $7EF359 : BEQ .done
  CMP.b #$05 : BCS .done ; includes the smith-held $FF sentinel
  LDA.b #$40 : TRB.b $F4
  LDA.b #$80 : TSB.b $F4
  ; Mark this slash as the counter. FrameTick clears the mark when it ends.
  STA.w GaroCounterTimer
  LDA.b #$10 : STA.w GaroCooldown
  .done
  RTL
}

; =========================================================
; Point-blank counter reach.
; A parry happens at body contact, but the normal slash box sits past Link's
; body and can miss an enemy that already overlaps him. While a counter slash
; is live, the slash box also covers Link's body (X+0..15, Y+4..19), which
; contains his contact hurtbox (X+4, Y+8, 8x8) with 4 px to spare.
; Spin, dash and hammer/net boxes never reach this tail with index != 0.

ActionHitbox_SizeX = $06F4AE
ActionHitbox_SizeY = $06F530

pushpc
org $06F633
; @hook GaroMask_ActionHitboxSize kind=jsl target=GaroMask_ActionHitboxSize
; @source usdasm/bank_06.asm:SetupActionHitbox ($06F633-$06F63E)
; @assumption M/X=8, DBR=$06, X = ActionHitbox index (0 = hammer/net).
; Replaces both size loads; the helper replays them before any change.
assert read3($06F633) == $F4AEBD, "SetupActionHitbox size_x load moved"
assert read3($06F638) == $F530BD, "SetupActionHitbox size_y load moved"
  JSL GaroMask_ActionHitboxSize
  PLX
  RTS
  NOP #6
assert pc() == $06F63F
pullpc

; X and Y are free here: the caller's next instruction is PLX, and vanilla
; SetupActionHitbox already clobbers Y. Exits with M=8.
GaroMask_ActionHitboxSize:
{
  LDA.l ActionHitbox_SizeX, X : STA.b $02
  LDA.l ActionHitbox_SizeY, X : STA.b $03
  BIT.w GaroCounterTimer : BPL .done
  CPX.b #$00 : BEQ .done

  ; X axis: union of [$08:$00, +$02) and [Link X, +16).
  LDA.b $08 : XBA : LDA.b $00
  REP #$20
  PHA                                     ; 3,S after the next push = left
  LDA.b $02 : AND.w #$00FF : CLC : ADC $01, S
  PHA                                     ; 1,S = right
  LDA.b $22 : CMP $03, S : BCS +
    STA $03, S
  +
  LDA.b $22 : CLC : ADC.w #$0010 : CMP $01, S : BCC +
    STA $01, S
  +
  PLA : SEC : SBC $01, S
  SEP #$20 : STA.b $02
  REP #$20 : PLA
  SEP #$20 : STA.b $00 : XBA : STA.b $08

  ; Y axis: union of [$09:$01, +$03) and [Link Y+4, +16).
  LDA.b $09 : XBA : LDA.b $01
  REP #$20
  PHA
  LDA.b $03 : AND.w #$00FF : CLC : ADC $01, S
  PHA
  LDA.b $20 : CLC : ADC.w #$0004 : CMP $03, S : BCS +
    STA $03, S
  +
  LDA.b $20 : CLC : ADC.w #$0014 : CMP $01, S : BCC +
    STA $01, S
  +
  PLA : SEC : SBC $01, S
  SEP #$20 : STA.b $03
  REP #$20 : PLA
  SEP #$20 : STA.b $01 : XBA : STA.b $09
  .done
  RTL
}

; =========================================================
; Armored Darknut: sprite $1D (Sprite_Darknut) with room subtype 1.
; Its armor blocks every attack with a clink; only a live Garo counter slash
; (GaroCounterTimer bit 7, set by GaroMask_CounterInput) can hurt it.
; Ordinary Darknuts (subtype 0, every overworld placement) keep the original
; paths: each helper replays the replaced Darknut instructions unchanged.
; Armor bits: $0E60 bit 6 = no damage from any source, $0CAA bit 2 = sword
; and hammer clink, $0B6B bit 3 = arrows deflect.
; Callers run in bank $30 with DBR=$30, M/X=8, X = sprite slot.
if !DISABLE_SPRITES == 0

!DarknutArmoredSubtype = $01
!DarknutArmorPalette   = $02 ; ORed into OAM props: palette 4 -> 5

; Replaces LDA #$80 : STA SprDefl,X : LDA #$60 : STA SprTileDie,X in Prep.
Darknut_PrepDefense:
{
  LDA.b #$80 : STA.w SprDefl, X
  LDA.b #%01100000 : STA.w SprTileDie, X
  LDA.w SprSubtype, X : CMP.b #!DarknutArmoredSubtype : BNE .done
  JSR Darknut_SetArmor
  .done
  RTL
}

Darknut_SetArmor:
{
  LDA.w $0E60, X : ORA.b #$40 : STA.w $0E60, X
  LDA.w SprDefl, X : ORA.b #$04 : STA.w SprDefl, X
  LDA.w SprTileDie, X : ORA.b #$08 : STA.w SprTileDie, X
  RTS
}

; Replaces JSL Sprite_CheckDamageFromPlayer in Main; returns its carry.
; The armor drops only around this one check, and only for a live counter.
Darknut_CheckDamage:
{
  LDA.w SprSubtype, X : CMP.b #!DarknutArmoredSubtype : BEQ .armored
  JML Sprite_CheckDamageFromPlayer
  .armored
  BIT.w GaroCounterTimer : BPL .guarded
  LDA.w $0E60, X : AND.b #$BF : STA.w $0E60, X
  LDA.w SprDefl, X : AND.b #$FB : STA.w SprDefl, X
  .guarded
  JSL Sprite_CheckDamageFromPlayer
  PHP
  JSR Darknut_SetArmor
  PLP
  RTL
}

; Replaces LDA SprFlash,X : STA $08 in Draw.
Darknut_DrawFlash:
{
  LDA.w SprSubtype, X : CMP.b #!DarknutArmoredSubtype : BNE .plain
  LDA.w SprFlash, X : ORA.b #!DarknutArmorPalette : STA.b $08
  RTL
  .plain
  LDA.w SprFlash, X : STA.b $08
  RTL
}

; Every non-sword damage source (arrows that pass the deflect test, bombs,
; Bombchu, rods, boomerang, hookshot, thrown objects, medallions) reaches
; Sprite_ApplyCalculatedDamage. Vanilla leaves an invulnerable sprite there
; silently; an armored Darknut also clinks.
pushpc
org $06ED8E
; @hook GaroArmor_BlockedDamage kind=jsl target=GaroArmor_BlockedDamage
; @source usdasm/bank_06.asm:Sprite_ApplyCalculatedDamage ($06ED8E-$06ED94)
; @assumption M/X=8, X = sprite slot; DBR is the caller's (< $40).
; Replaces LDA $0E60,X : AND #$40 : BNE .exit_a; Z=0 takes the same exit.
assert read3($06ED8E) == $0E60BD, "ApplyCalculatedDamage invulnerable test moved"
assert read4($06ED91) == $0AD04029, "ApplyCalculatedDamage invulnerable exit moved"
  JSL GaroArmor_BlockedDamage
  BNE $06ED9F
  NOP
assert pc() == $06ED95
pullpc

GaroArmor_BlockedDamage:
{
  LDA.w $0E60, X : AND.b #$40 : BEQ .done
  LDA.w $0E20, X : CMP.b #Sprite_Darknut : BNE .blocked
  LDA.w SprSubtype, X : CMP.b #!DarknutArmoredSubtype : BNE .blocked
  LDA.w $012E : BNE .blocked
  LDA.b #$05 : STA.w $012E ; clink, the same cue as a sword tink
  .blocked
  LDA.b #$40 ; Z=0: vanilla's invulnerable exit
  .done
  RTL
}
endif
