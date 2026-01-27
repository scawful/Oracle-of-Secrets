; =========================================================
; Kydrog NPC (Intro Cutscene)
;
; NARRATIVE ROLE: The Pirate King who kidnaps Farore and banishes Link
;   to the Eon Abyss. This is the NPC/cutscene version - not the boss.
;   Kydrog is a fallen knight corrupted by Ganondorf over centuries.
;
; TERMINOLOGY: "Kydrog" = KydrogNPC (NPC form)
;   - "Pirate King" - his self-styled title
;   - "Fallen Knight" - his true origin (revealed late-game)
;   - See kydrog_boss.asm for D7 boss fight
;   - See kydreeok.asm for final boss (dragon form)
;
; TRIGGER: Spawns at Maku Tree area (LW 0x2A) during intro
;   - Despawns permanently after encounter ($7EF300 = 1)
;
; STATES:
;   0: StartCutscene - Auto-walk Link north, play music
;   1: AttractPlayer - Timer countdown, show message 0x21
;   2: SpawnOffspring - Update Farore's story flag ($B6)
;   3: WarpPlayerAway - Banish to Eon Abyss (DW 0x20)
;
; MESSAGES:
;   0x21 - Intro confrontation ("Well, well, what a surprise!")
;
; FLAGS WRITTEN:
;   $7EF300 = 1 - KydrogFaroreRemoved (prevents respawn)
;   $7EF303 = 0 - InCutScene cleared
;   $7EF3C6 |= 0x04 - OOSPROG2 bit 2 (Kydrog encounter done)
;   $7EF3CA ^= 0x40 - Toggle Dark World flag
;   $7EF3CC = 0 - Remove Impa follower
;
; FLAGS READ:
;   $7EF300 - If set, sprite is killed in Prep
;
; RELATED:
;   - farore.asm (captured by Kydrog, uses $B6 story state)
;   - impa.asm (follower removed during warp)
;   - maku_tree.asm (same area, appears after Kydrog gone)
;   - narrative_lockdown.md (backstory, death scene plans)
;
; LORE HOOK: Message 0x21 contains "cast away to the Eon Abyss,
;   just as I was" - hints at his fallen hero origin.
;
; TODO: Implement "Fallen Knight" transition logic where his palette 
;       changes as his armor breaks (visual storytelling).
; =========================================================
; Cutscene Kydrog Sprite Properties
; =========================================================

!SPRID              = Sprite_KydrogNPC
!NbrTiles           = 6   ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 0   ; Number of Health the sprite have
!Damage             = 0   ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 0   ; Unused in this template (can be 0 to 7)
!Hitbox             = 0   ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 0   ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_Kydrog_Prep, Sprite_Kydrog_Long)

Sprite_Kydrog_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Kydrog_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Kydrog_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Kydrog_Prep:
{
  PHB : PHK : PLB
  LDA.l $7EF300 : BEQ .PlayIntro
    STZ.w SprState, X ; Kill the sprite
  .PlayIntro
  PLB
  RTL
}

Sprite_Kydrog_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Kydrog_StartCutscene
  dw Kydrog_AttractPlayer
  dw Kydrog_SpawnOffspring
  dw Kydrog_WarpPlayerAway

  Kydrog_StartCutscene:
  {
    LDA #$03 : STA $012C ; Play music
    LDA.w WALKSPEED : STA.b $57 ; Slow Link down for the cutscene
    LDA.b #$08 : STA.b $49 ; Auto-movement north

    LDA.b $20 ; Link's Y Position
    CMP.b #72 ; Y = 6C
    BCC .linkistoofar
      LDA.b #$80 : STA.w SprTimerA, X
      %GotoAction(1)
    .linkistoofar

    RTS
  }

  Kydrog_AttractPlayer:
  {
    LDA.w SprTimerA, X : BNE +
      LDA.b #$0C : STA $012D
      LDA #$00 : STA $7EF303
      %ShowUnconditionalMessage($21)
      %GotoAction(2)
    +
    RTS
  }

  Kydrog_SpawnOffspring:
  {
    LDA.b #$02 : STA.b $B6 ; Update story flag for Farore
    STZ.b $49 ; Stop Link from moving
    %GotoAction(3)
    RTS
  }

  Kydrog_WarpPlayerAway:
  {
    ; TODO: Trigger "Abyss" background effect here (BG3 mosaic or HDMA scanlines)
    ;       to emphasize the banishment sequence.
    
    ; Put us in the Dark World.
    LDA $7EF3CA : EOR.b #$40 : STA $7EF3CA

    JSL Sprite_LoadGfxProperties

    STZ $037B : STZ $3C : STZ $3A : STZ $03EF

    ; Link can't move
    LDA.b #$01 : STA $02E4

    ; The module to return to is #$08 (preoverworld)
    LDA.b #$08 : STA $010C

    ; Set the map I want
    LDA.b #$20 : STA $A0 : STZ $A1

    ; Set us to the warp state
    LDA.b #$15 : STA $10

    ; Clear submodules
    STZ $11 : STZ $B0

    ; Remove Impa follower
    LDA.b #$00 : STA $7EF3CC

    ; Set the flag to remove Farore and Kydrog from Maku area
    LDA #$01 : STA.l $7EF300

    ; Set the progress flag for Impa (Zelda) in the sanctuary
    LDA $7EF3C6 : ORA.b #$04 : STA $7EF3C6

    RTS
  }
}

Sprite_Kydrog_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?
  TXA : CLC : ADC $06 ; Add Animation Index Offset
  PHA ; Keep the value with animation index offset?
  ASL A : TAX

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
    db $00
  .nbr_of_tiles
    db 5
  .x_offsets
    dw -8, 8, 8, -8, -8, 8
  .y_offsets
    dw -12, -12, 4, 4, 20, 20
  .chr
    db $CC, $CE, $EE, $EC, $E8, $EA
  .properties
    db $39, $39, $39, $39, $39, $39
}
