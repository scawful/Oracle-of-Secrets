; =========================================================
; Garo Master prototype. Y standing still opens a timed contact parry, then
; Y counters. Y while walking toward Link's facing is a short sword lunge;
; Y again during the lunge is a Roc's Cape style forward jump. A d-pad tap
; away from Link's facing while the guard is open is a short evasive leap.
; Player art by Herowho (garomaster.1.zspr); palette 1 retained.
; Gameplay entries use M/X=8; LinkMain_FrameHook owns full preservation.
; State is volatile. Local lunge JSRs remain in this graphics/behavior bank.
; =========================================================

; Called once by LinkMain_FrameHook (Masks/mask_routines.asm).
; M/X=8, DBR=$07. The shared wrapper owns the displaced instructions and
; full register/flags preservation. Keep local lunge JSRs in this bank.
GaroMask_FrameTick:
{
  ; The cooldown also runs while inactive: a leap is vanilla recoil, which
  ; fails CanAct for its whole flight, and its cooldown must outlast it.
  LDA.w GaroCooldown : BEQ +
  DEC.w GaroCooldown
  +
  JSR GaroMask_LungeTick
  JSL GaroMask_CanAct : BCS .active
  JSL GaroMask_Clear
  BRA .done
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
  .done
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

; Ends a guard or counter. The cooldown and a lunge are left to end on their
; own; the startup hook clears the whole prototype range.
GaroMask_Clear:
{
  STZ.w GaroGuardTimer
  STZ.w GaroCounterTimer
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
  LDA.w GaroGuardTimer : BEQ +
  JSR GaroMask_TryLeap
  +
  LDA.b $F4 : AND.b #$40 : BEQ .done
  ; LinkState_Default runs the Y-item tick before its sword-input handler.
  ; Leave a counter press for that later hook; the effective Y action is 0.
  LDA.w GaroCounterTimer : BNE .done
  ; Y never dispatches the selected normal item while this form is active.
  LDA.b #$40 : TRB.b $F4
  LDA.w GaroCooldown : BNE .done
  LDA.b $3C : BNE .done
  LDA.b $3A : AND.b #$C0 : BNE .done
  JSR GaroMask_TryLunge : BCS .done
  LDA.b #$0C : STA.w GaroGuardTimer
  LDA.b #$20 : STA.w GaroCooldown
  LDA.b #$05 : STA.w $012E ; guard cue; the same clink confirms contact
  .done
  RTL
}

; Called only while the guard is open. A new d-pad press with no part of
; it toward Link's facing starts a leap: the vanilla sprite-bump recoil
; ($4D=1) aimed by that press, with a small hop and damage immunity ($037B)
; until vanilla lands it. This runs before LinkState_Default turns Link, so
; $2F is still the guarded facing and is kept: the usual move is a back-step
; from the enemy being faced, or a side-step. A held direction never
; triggers it, so turning to guard toward an enemy is unaffected.
; The hop is about 8 frames high, so it is meant to stay short of clearing
; a 16 px pit; Tests/native/garo_leap.py measures it. Vanilla resolves the
; landing tile as for any bump.
GaroMask_TryLeap:
{
  PHX
  LDA.b $3C : BNE .no
  LDA.b $3A : AND.b #$C0 : BNE .no
  LDA.b $F4 : AND.b #$0F : BEQ .no
  PHA
  LDA.b $2F : LSR A : TAX
  PLA : PHA
  AND.l GaroFacingBits, X : BNE .no_pull
  PLA : TAX
  LDA.l .speed_y, X : STA.b $27
  LDA.l .speed_x, X : STA.b $28
  ORA.b $27 : BEQ .no ; opposite directions cancel
  STZ.b $24 : STZ.b $25
  LDA.b #$08 : STA.b $29 : STA.w $02C7
  LDA.b #$03 : STA.w $02C6 ; the first landing ends it, without a bounce
  LDA.b #$0E : STA.b $46
  LDA.b #$01 : STA.b $4D : STA.w $037B
  STA.w $02F8 ; landing thud
  STZ.w GaroGuardTimer
  LDA.b #$30 : STA.w GaroCooldown
  LDA.b #$20 : STA.w $012E ; vanilla ledge-hop cue
  PLX : RTS
  .no_pull
  PLA
  .no
  PLX : RTS

  ; Indexed by the new d-pad press. $18 is the vanilla bump speed; diagonals $11.
  .speed_y
  db $00, $00, $00, $00, $18, $11, $11, $18
  db $E8, $EF, $EF, $E8, $00, $00, $00, $00
  .speed_x
  db $00, $18, $E8, $00, $00, $11, $EF, $00
  db $00, $11, $EF, $00, $00, $18, $E8, $00
}

; Indexed by $2F/2: up, down, left, right. D-pad bits: 3=U 2=D 1=L 0=R.
; The same values as vanilla LinkDirections26 ($078F61).
GaroFacingBits:
  db $08, $04, $02, $01

!GaroLungeFrames = $0E

; Called on a Y press that would open a guard. Y while the d-pad holds
; exactly Link's facing starts a lunge: the vanilla Pegasus dash state
; ($5D=$11, Link_PerformDash $07B281) entered past its charge-up ($0374=0).
; Vanilla owns the dash speed, the sword-forward pose and its hitbox, dust,
; bonks and the steer-out exit; GaroMask_LungeTick only limits its length.
; A diagonal or a fresh turn this frame opens the guard instead.
; Carry set = lunge started.
GaroMask_TryLunge:
{
  PHX
  LDA.b $2F : LSR A : TAX
  LDA.b $F0 : AND.b #$0F : CMP.l GaroFacingBits, X : BNE .no
  LDA.l $7EF359 : BEQ .no
  CMP.b #$05 : BCS .no ; includes the smith-held $FF sentinel
  ; Link_PerformDash's own refusals: Somaria platform, moving floor, sliding.
  LDA.w $02F5 : ORA.w $0314 : ORA.w $02EC : BNE .no
  STZ.b $3B : STZ.w $0374
  LDA.b #$40 : STA.w $02F1
  LDA.b #$11 : STA.b $5D
  LDA.b #$01 : STA.w $0372
  STZ.b $3A
  STZ.w $0308 : STZ.w $0301
  STZ.b $48 : STZ.b $6B
  ; The charge-up normally sets these; it is skipped.
  STZ.b $30 : STZ.b $31
  LDA.b #$10 : STA.b $5E
  LDA.l GaroFacingBits, X : STA.b $26 : STA.b $67 : STA.w $0340
  ; The sword handler still runs this frame; a B press must not slash.
  LDA.b #$80 : TRB.b $F4
  LDA.b #!GaroLungeFrames : STA.w GaroLungeTimer
  LDA.b #$28 : STA.w GaroCooldown
  LDA.b #$23 : STA.w $012E ; vanilla dash cue
  PLX : SEC : RTS
  .no
  PLX : CLC : RTS
}

; From FrameTick, before Link's state dispatch. A lunge ends when its timer
; runs out, or turns into a cape hop on a Y press. Anything else that leaves
; the dash state (a bonk, steering out, a transition) was already cleaned up
; by vanilla, so only the timer is cleared.
GaroMask_LungeTick:
{
  LDA.w GaroLungeTimer : BEQ .done
  LDA.w !CurrentMask : CMP.b #$08 : BNE .stop
  LDA.b $5D : CMP.b #$11 : BNE .stop
  LDA.w $0372 : BEQ .stop
  LDA.b $F4 : AND.b #$40 : BEQ .tick
  LDA.b #$40 : TRB.b $F4
  JMP GaroMask_CapeHop
  .tick
  DEC.w GaroLungeTimer : BNE .done
  ; Out of time: stop as the dash would, without the bonk.
  JSL Link_CancelDash
  STZ.b $3A : STZ.b $3C : STZ.b $3D
  STZ.b $5D
  RTS
  .stop
  STZ.w GaroLungeTimer
  .done
  RTS
}

; Vanilla gates the dash sword pose on story progress. A Garo lunge already
; validated sword ownership, so its pose must not depend on that story byte.
; Other dashes retain the displaced load and its zero/nonzero result.
pushpc
org $079104 ; @hook module=Masks name=GaroMask_DashSword kind=jsl target=GaroMask_DashSword
assert read4($079104) == $7EF3C5AF, "Dash sword story load moved"
  JSL GaroMask_DashSword
assert pc() == $079108
pullpc

GaroMask_DashSword:
{
  LDA.l GameState : BNE .done
  LDA.w GaroLungeTimer
  .done
  RTL
}

; Y during a lunge: a Roc's Cape style forward jump. It is the Roc's Feather
; jump (Items/jump_feather.asm: recoil state $5D=2, ledge hop $4D=2, $46=$20,
; height $24), aimed along the lunge with a faster carry ($18 vs $10), plus
; damage immunity ($037B) until vanilla lands it. $5D=2 also skips spike
; damage (CheckIfJumpingForSpikeDamage). The recoil state checks the floor
; only on landing, so the jump carries Link over pits and lava it clears.
GaroMask_CapeHop:
{
  STZ.w GaroLungeTimer
  JSL Link_CancelDash
  STZ.b $3A : STZ.b $3C : STZ.b $3D
  STZ.b $30 : STZ.b $31
  STZ.b $24 : STZ.b $25
  LDA.b $2F : LSR A : TAX
  LDA.l .speed_y, X : STA.b $27
  LDA.l .speed_x, X : STA.b $28
  LDA.l GaroFacingBits, X : STA.b $67 : STA.w $0340
  LDA.b #$24 : STA.b $29 : STA.w $02C7
  LDA.b #$03 : STA.w $02C6 ; the first landing ends it, without a bounce
  LDA.b #$20 : STA.b $46
  LDA.b #$02 : STA.b $5D : STA.b $4D
  LDA.b #$01 : STA.w $037B
  STA.w $02F8 ; landing thud
  LDA.b #$40 : STA.w GaroCooldown
  LDA.b #$20 : STA.w $012E ; vanilla ledge-hop cue
  RTS

  ; Indexed by $2F/2: up, down, left, right.
  .speed_y
  db $E8, $18, $00, $00
  .speed_x
  db $00, $00, $E8, $18
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
