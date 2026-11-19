; =========================================================
; Wayward Village Multi-Form Animal Interactions
; (Included from Items/all_items.asm, Bank $2B)
;
; Asymmetric interactions for Minish Link ($02B2 == #$05) vs
; Wolf Link ($02B2 == #$03) vs Human Link ($02B2 == #$00):
;   1. Village Dog ($25, Sprites/NPCs/village_dog.asm):
;      - Human: lifts & tosses dog (Sprite_CheckIfLifted).
;      - Wolf: pack-mate tail wag within 40px + solicited canine speech
;              (!Dog_MsgWolf / !RichardDog_MsgWolf).
;      - Minish: gentle approach speed/stop + solicited tiny-visitor speech
;              (!Dog_MsgMinish).
;   2. Cucco ($0B, hooked at $06:F244 inside Sprite_CheckIfLifted):
;      - Human / other forms: untouched native permissive lift ($06:F257).
;      - Minish: solicited talk (!Cucco_MsgMinish) + cluck SFX + curious hop.
;      - Wolf: nervous fast wing-flap within 28px; solicited talk
;              (!Cucco_MsgWolf) + panicked cluck SFX + immediate flee ($02).
;   3. Indoor Peaceful Village Rats ($6D, hooked at $05:A8CE in Sprite_6D_Rat):
;      - Scoped strictly to peaceful Wayward Village interiors ($0102, $0103,
;        $0104, $0106, $0107 Library, $0119, $011F) with $0FFF == 0 and
;        Link in Minish (#$05) or Wolf (#$03) form.
;      - Cave/Well ($0FE), Sewers, Dungeons, DW crickets, and Human Link keep
;        100% untouched vanilla damage & movement.
;      - Minish: zero contact damage, rat pauses within 24px, solicited talk
;              (!Rat_MsgMinish) + squeak SFX.
;      - Wolf: zero contact damage, rat freezes in place within 36px,
;              solicited talk (!Rat_MsgWolf) + panicked squeak SFX.
;   4. Village Cat ($28 Action 3, hooked at $06:8CA1 / $06:AE34 / $06:AF1A):
;      - Extends Storyteller ($28) prep to Wayward Village OW $23 and houses
;        ($0102, $0103, $0104, $0106, $0107, $0119, $011F), plus temporary $000F compatibility
;        until removed from Maple's Hut.
;      - Human: native $0149 ("Will you pet the cat?") + happy purr hop.
;      - Minish / Wolf: solicited form reactions (!Cat_MsgMinish / !Cat_MsgWolf).
;      - Draw selects 0xBC $4E cat in spritesets without 0xC0 in slot 1.
;
; Dialogue IDs use existing ROM messages as placeholders until canon lines
; in AFS (ANIMAL_DIALOGUE_DRAFT.md) are approved by scawful.
; =========================================================

!Dog_MsgMinish        = $0018 ; "You can understand me?..."
!Dog_MsgWolf          = $001B ; "Bark! Bark!" (placeholder for Wolf pack talk)
!RichardDog_MsgWolf   = $001B ; Placeholder for Richard's Wolf-form hint
!Cucco_MsgMinish      = $0018 ; Placeholder for towering Cucco talk
!Cucco_MsgWolf        = $001B ; Placeholder for spooked Cucco squawk
!Rat_MsgMinish        = $0018 ; Placeholder for Library Rat peer clue
!Rat_MsgWolf          = $001B ; Placeholder for cornered Rat squeak
!Cat_MsgHuman         = $0149 ; Native "Meow. ... Will you pet the cat?"
!Cat_MsgMinish        = $0149 ; Placeholder for towering Village Cat reaction
!Cat_MsgWolf          = $0149 ; Placeholder for bristling Village Cat reaction

; ---- Vanilla hook-site byte guards ----
assert read3($06F244) == $0E20BD && read4($06F247) == $0CF00BC9 && read4($06F24B) == $08F04AC9, "Sprite_CheckIfLifted $0B/$4A site changed"
assert read3($05A8CE) == $AB9320 && read3($05A8D1) == $F9ED20, "Sprite_6D_Rat combat/move site changed"
assert read4($068CA1) == $00A0A0A5 && read4($068CA5) == $F08C99D9 && read4($068CA9) == $F8D0C803, "SpritePrep_Storyteller room lookup site changed"
assert read3($06AE34) == $0DF0BD && read2($06AE37) == $19D0, "Sprite_28 Action 3 Broccoli site changed"
assert read4($06AF1A) == $0A0E80BD && read3($06AF1E) == $0DC07D, "Sprite_28_Draw site changed"

pushpc
org $06F257
Sprite_CheckIfLifted_Permissive:
org $06F2A9
Sprite_CheckIfLifted_Exit:

; $06:F244 (11 bytes): replaces `LDA $0E20,X : CMP #$0B : BEQ $F257 : CMP #$4A : BEQ $F257`
org $06F244 ; @hook module=Sprites name=VillageCucco_LiftOrTalk kind=jsl target=VillageCucco_LiftOrTalk expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JSL VillageCucco_LiftOrTalk
  BCS Sprite_CheckIfLifted_Permissive ; C=1 -> Human Cucco or $4A permissive lift (+$0D)
  BEQ Sprite_CheckIfLifted_Exit       ; C=0, Z=1 -> Minish/Wolf Cucco handled (+$5D)
  NOP #3                              ; C=0, Z=0 -> fall through to $06:F24F for all other sprites
assert pc() == $06F24F, "VillageCucco_LiftOrTalk hook size mismatch"

; $05:A8CE (6 bytes): replaces `JSR Sprite_CheckDamageToAndFromLink_Bank05 : JSR Sprite_Move_XY_Bank05`
org $05A8CE ; @hook module=Sprites name=VillageRat_InteractOrCombat kind=jsl target=VillageRat_InteractOrCombat expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JSL VillageRat_InteractOrCombat
  NOP #2
assert pc() == $05A8D4, "VillageRat_InteractOrCombat hook size mismatch"

; $06:8CA1 (12 bytes): replaces unbounded Storyteller room scan before `TYA : STA $0E80,X`
org $068CA1 ; @hook module=Sprites name=VillageCat_Prep kind=jsl target=VillageCat_Prep expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JSL VillageCat_Prep
  NOP #8
assert pc() == $068CAD, "VillageCat_Prep hook size mismatch"

; $06:AE34 (5 bytes): replaces Action 3 (Cat / Broccoli) entry
org $06AE34 ; @hook module=Sprites name=VillageCat_Main kind=jsl target=VillageCat_Main expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JSL VillageCat_Main
  RTS
assert pc() == $06AE39, "VillageCat_Main hook size mismatch"

; $06:AF1A (7 bytes): replaces `LDA $0E80,X : ASL : ADC $0DC0,X` at start of Sprite28_Draw
org $06AF1A ; @hook module=Sprites name=VillageCat_Draw kind=jsl target=VillageCat_Draw expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JSL VillageCat_Draw
  BCC .vanilla_draw
  RTS
  .vanilla_draw
assert pc() == $06AF21, "VillageCat_Draw hook size mismatch"
pullpc

; ---------------------------------------------------------
; Shared helper: 16-bit box check |Link - Sprite(X)| < A on both axes.
; Reads SprX/SprXH and SprY/SprYH directly (no $0FD8 dependency).
; In: A = 8-bit radius ($01-$7F), M=8, X=8. Out: C=1 if inside box.
; Clobbers $04, $06-$09 (scratch). Preserves X, Y.
; ---------------------------------------------------------
Animal_NearPlayer:
{
  STZ.b $07 : STA.b $06
  ASL A : STZ.b $09 : STA.b $08
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  STA.b $04
  LDA.b $22 : SEC : SBC.b $04 : CLC : ADC.b $06 : CMP.b $08 : BCS .far
  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  STA.b $04
  LDA.b $20 : SEC : SBC.b $04 : CLC : ADC.b $06 : CMP.b $08 : BCS .far
  SEP #$21 ; M=8, C=1
  RTS
.far
  SEP #$20
  CLC
  RTS
}

; ---------------------------------------------------------
; Shared helper: run Sprite_ShowSolicitedMessageIfPlayerFacing with
; temporary Harmless ($0E40 bit 7) and NPC talk hitbox ($09) so small
; or non-harmless actors (Cuccos, Library Rats) never damage Link and
; have comfortable face-and-press-A talk overlap.
; In: A = msg low, Y = msg high, X = sprite slot (M=8, X=8).
; Out: C=1 if message box opened, X preserved.
; ---------------------------------------------------------
Animal_SolicitedTalk:
{
  PHA
  LDA.w $0E40, X : PHA
  ORA.b #$80 : STA.w $0E40, X
  LDA.w $0F60, X : PHA
  AND.b #$E0 : ORA.b #$09 : STA.w $0F60, X
  LDA 3, S
  JSL Sprite_ShowSolicitedMessageIfPlayerFacing
  PHP
  PLA : STA.b $04          ; save returned P (carry)
  PLA : STA.w $0F60, X
  PLA : STA.w $0E40, X
  PLA                      ; drop msg low
  LDA.b $04 : PHA : PLP    ; restore returned carry
  RTS
}

; ---------------------------------------------------------
; 1. Village Dog ($25): called from LiftOrTalk when $02B2 is #$03 or #$05.
; ---------------------------------------------------------
VillageDog_FormInteractLong:
{
  PHB : PHK : PLB
  LDA.w $02B2 : CMP.b #$05 : BEQ .minish
    ; Wolf Link (#$03): canine-to-canine talk (subtype != 0 = Richard)
    LDA.w SprSubtype, X : BEQ .stray_wolf
      LDY.b #!RichardDog_MsgWolf>>8
      LDA.b #!RichardDog_MsgWolf&$FF
      BRA .try_wolf
    .stray_wolf
    LDY.b #!Dog_MsgWolf>>8
    LDA.b #!Dog_MsgWolf&$FF
    .try_wolf
    JSR Animal_SolicitedTalk
    PLB
    RTL

  .minish
  LDY.b #!Dog_MsgMinish>>8
  LDA.b #!Dog_MsgMinish&$FF
  JSR Animal_SolicitedTalk
  PLB
  RTL
}

; ---------------------------------------------------------
; 2. Cucco ($0B): hooked at $06:F244 inside Sprite_CheckIfLifted.
; Exit flags MUST be set AFTER PLB (PLB overwrites N/Z):
;   - C=1       -> BCS $06F257 (Human Cucco or $4A permissive lift)
;   - C=0, Z=1  -> BEQ $06F2A9 (Minish/Wolf Cucco handled; skip lift)
;   - C=0, Z=0  -> fall through to $06:F24F (other sprites)
; ---------------------------------------------------------
VillageCucco_LiftOrTalk:
{
  LDA.w $0E20, X
  CMP.b #$0B : BEQ .is_cucco
  CMP.b #$4A : BEQ .permissive_no_plb
    CLC
    LDA.b #$01 ; Z=0, C=0
    RTL

  .permissive_no_plb
  SEC
  RTL

  .is_cucco
  LDA.w $02B2
  CMP.b #$05 : BEQ .cucco_minish
  CMP.b #$03 : BEQ .cucco_wolf
    SEC ; Human / other form -> native permissive Cucco lift
    RTL

  .cucco_minish
  PHB : PHK : PLB
  LDY.b #!Cucco_MsgMinish>>8
  LDA.b #!Cucco_MsgMinish&$FF
  JSR Animal_SolicitedTalk : BCC .done_cucco
    LDA.b #$30 : JSL Sound_SetSfx2PanLong ; BawkBawk cluck
    LDA.w SprAction, X : CMP.b #$02 : BCS .done_cucco
      LDA.b #$0C : STA.w SprTimerF, X
      LDA.b #$01 : STA.w SprAction, X
  .done_cucco
  PLB
  CLC
  LDA.b #$00 ; Z=1, C=0 -> BEQ EXIT_06F2A9
  RTL

  .cucco_wolf
  PHB : PHK : PLB
  LDA.w SprAction, X : CMP.b #$02 : BCS .wolf_try_talk
    LDA.b #$1C : JSR Animal_NearPlayer : BCC .wolf_try_talk
      ; Nervous wing-flutter in place when Wolf Link prowls close
      INC.w $0E80, X : INC.w $0E80, X
  .wolf_try_talk
  LDY.b #!Cucco_MsgWolf>>8
  LDA.b #!Cucco_MsgWolf&$FF
  JSR Animal_SolicitedTalk : BCC .done_cucco
    LDA.b #$30 : JSL Sound_SetSfx2PanLong ; Panicked cluck
    LDA.b #$02 : STA.w SprAction, X       ; Bolt into Cucco_Flee!
    LDA.b #$10 : STA.w SprXSpeed, X
    LDA.w SprXH, X : XBA : LDA.w SprX, X
    REP #$20 : CMP.b $22 : SEP #$20 : BCS +
      LDA.b #$F0 : STA.w SprXSpeed, X
    +
    BRA .done_cucco
}

; ---------------------------------------------------------
; 3. Indoor Village Rats ($6D): hooked at $05:A8CE in Sprite_6D_Rat.
; Peaceful Wayward Village rooms only when Link is Minish or Wolf.
; ---------------------------------------------------------
VillageRat_InteractOrCombat:
{
  LDA.b $1B : BEQ .hostile
  LDA.w $0FFF : BNE .hostile
  LDA.w $02B2
  CMP.b #$05 : BEQ .check_room
  CMP.b #$03 : BNE .hostile

  .check_room
  REP #$20
  LDA.b $A0
  CMP.w #$0107 : BEQ .peaceful ; Village Library (primary rat NPC room)
  CMP.w #$0102 : BEQ .peaceful ; Sick Boy / Vasu
  CMP.w #$0103 : BEQ .peaceful ; Village Bar / Carpenter
  CMP.w #$0104 : BEQ .peaceful ; Old Woman House
  CMP.w #$0106 : BEQ .peaceful ; Richard Shed
  CMP.w #$0119 : BEQ .peaceful ; Town Hall
  CMP.w #$011F : BEQ .peaceful ; Mask / Village Shop
  SEP #$20

  .hostile
  JSL Sprite_CheckDamageFromPlayer
  JSL Sprite_CheckDamageToPlayer
  JSL Sprite_MoveLong
  RTL

  .peaceful
  SEP #$20
  PHB : PHK : PLB
  LDA.w $02B2 : CMP.b #$05 : BEQ .rat_minish

  ; Wolf Link (#$03): rat freezes in place within 36px, talks with panicked squeak
  LDA.b #$24 : JSR Animal_NearPlayer : BCC .wolf_move
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    STZ.w SprAction, X
    LDA.b #$28 : STA.w SprTimerA, X
    BRA .wolf_talk
  .wolf_move
    JSL Sprite_MoveLong
  .wolf_talk
  LDY.b #!Rat_MsgWolf>>8
  LDA.b #!Rat_MsgWolf&$FF
  JSR Animal_SolicitedTalk : BCC .done
    LDA.b #$17 : JSL Sound_SetSfx3PanLong
  BRA .done

  .rat_minish
  ; Minish Link (#$05): eye-level peer; rat pauses within 24px to chat
  LDA.b #$18 : JSR Animal_NearPlayer : BCC .minish_move
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    STZ.w SprAction, X
    LDA.b #$20 : STA.w SprTimerA, X
    BRA .minish_talk
  .minish_move
    JSL Sprite_MoveLong
  .minish_talk
  LDY.b #!Rat_MsgMinish>>8
  LDA.b #!Rat_MsgMinish&$FF
  JSR Animal_SolicitedTalk : BCC .done
    LDA.b #$17 : JSL Sound_SetSfx3PanLong

  .done
  PLB
  RTL
}

; ---------------------------------------------------------
; 4. Village Cat ($28 Action 3):
;    Prep sets Y = action index ($03 for Wayward Village + legacy $000F).
;    Uses DB = caller ($06) for Prep, PHK/PLB for Main and Draw.
; ---------------------------------------------------------
VillageCat_Prep:
{
  PHB : PHK : PLB
  LDA.b $1B : BNE .indoors
    LDA.b $8A : CMP.b #$23 : BEQ .cat_action
    BRA .bounded_vanilla
  .indoors
  REP #$20
  LDA.b $A0
  CMP.w #$000F : BEQ .cat_ind
  CMP.w #$0102 : BEQ .cat_ind
  CMP.w #$0103 : BEQ .cat_ind
  CMP.w #$0104 : BEQ .cat_ind
  CMP.w #$0106 : BEQ .cat_ind
  CMP.w #$0107 : BEQ .cat_ind
  CMP.w #$0119 : BEQ .cat_ind
  CMP.w #$011F : BEQ .cat_ind
  SEP #$20

  .bounded_vanilla
  LDA.b $A0
  LDY.b #$00
  .scan
    CMP.w .vanilla_rooms, Y : BEQ .done
    INY
    CPY.b #$05 : BCC .scan
  .cat_action
  LDY.b #$03
  .done
  PLB
  RTL

  .cat_ind
  SEP #$20
  LDY.b #$03
  PLB
  RTL

  .vanilla_rooms : db $0E, $0E, $12, $1A, $14
}

VillageCat_Main:
{
  PHB : PHK : PLB
  LDA.w SprHeight, X : BEQ .grounded
    DEC.w SprHeight, X
  .grounded

  LDA.w $02B2 : CMP.b #$03 : BEQ .wolf
  CMP.b #$05 : BEQ .minish

  ; Human / other forms: idle look flip + native MSG $0149 ("Will you pet the cat?")
  LDA.w SprTimerA, X : BNE .human_talk
    LDA.b $1A : AND.b #$3F : BNE .human_talk
      LDA.w $0F50, X : EOR.b #$40 : STA.w $0F50, X
  .human_talk
  LDY.b #!Cat_MsgHuman>>8
  LDA.b #!Cat_MsgHuman&$FF
  JSR Animal_SolicitedTalk : BCC .done
    LDA.b #$04 : STA.w SprHeight, X
    LDA.b #$20 : STA.w SprTimerA, X
  .done
  PLB
  RTL

  .minish
  LDY.b #!Cat_MsgMinish>>8
  LDA.b #!Cat_MsgMinish&$FF
  JSR Animal_SolicitedTalk : BCC .done
    LDA.b #$03 : STA.w SprHeight, X
    LDA.b #$20 : STA.w SprTimerA, X
  PLB
  RTL

  .wolf
  ; Alertly track Wolf Link within 32px; solicited talk bristles/hops.
  LDA.b #$20 : JSR Animal_NearPlayer : BCC .wolf_talk
    JSL Sprite_IsToRightOfPlayer
    LDA.w $0F50, X : AND.b #$BF
    CPY.b #$00 : BEQ +
      ORA.b #$40
    +
    STA.w $0F50, X
  .wolf_talk
  LDY.b #!Cat_MsgWolf>>8
  LDA.b #!Cat_MsgWolf&$FF
  JSR Animal_SolicitedTalk : BCC .done
    LDA.b #$06 : STA.w SprHeight, X
    LDA.b #$28 : STA.w SprTimerA, X
  PLB
  RTL
}

; Out: C=1 if custom Village Cat drawn (returns via RTS at $06:AF20);
;      C=0 with A = (SprAction*2)+SprFrame if vanilla table should draw.
VillageCat_Draw:
{
  LDA.w SprAction, X : CMP.b #$03 : BNE .vanilla
  LDA.b $1B : BEQ .check_bc
    ; Preserve legacy Maple's Hut ($000F) draw until removed cleanly.
    REP #$20 : LDA.b $A0 : CMP.w #$000F : SEP #$20 : BEQ .vanilla
  .check_bc
  ; If current spriteset ALREADY has 0xC0 in slot 1, vanilla $6A/$6C draws the sitting cat.
  LDA.w $0AA3
  CMP.b #$28 : BEQ .vanilla
  CMP.b #$45 : BEQ .vanilla
  CMP.b #$47 : BEQ .vanilla
  CMP.b #$4D : BEQ .vanilla
  CMP.b #$4E : BEQ .vanilla
  CMP.b #$4F : BEQ .vanilla
  CMP.b #$60 : BEQ .vanilla

  ; Otherwise draw 0xBC $0E (OAM $4E) curled/sitting cat from slot 1 + shadow.
  PHB : PHK : PLB
  LDA.b #.cat_bc_oam : STA.b $08
  LDA.b #.cat_bc_oam>>8 : STA.b $09
  LDA.b #$01 : STA.b $06
  STZ.b $07
  JSL $05DF75 ; SpriteDraw_Tabulated_player_deferred
  JSL Sprite_DrawShadow
  PLB
  SEC
  RTL

  .vanilla
  LDA.w SprAction, X : ASL A : ADC.w SprFrame, X
  CLC
  RTL

  .cat_bc_oam
  dw 0, 0 : db $4E, $0A, $00, $02
}

print "End of village_animals.asm         ", pc
