; =========================================================
; Eon Windmill NPC (Song of Storms)
;
; NARRATIVE ROLE: Eon Abyss windmill keeper who teaches Link the
;   Song of Storms after the Song of Healing.
;
; TERMINOLOGY: "Windmill Guy" = WindmillGuy
;   - Requires Ocarina ($7EF34C >= 1)
;   - Requires Song of Healing ($7EF34C >= 2)
;   - Teaches Song of Storms ($7EF34C = 3)
;
; MESSAGES:
;   0x1D5 - No Ocarina yet
;   0x1D6 - Need Song of Healing first
;   0x1D7 - Teach Song of Storms
;   0x1D8 - Already knows Song of Storms
;
; FLAGS READ:
;   $7EF34C - Ocarina/song progression
;
; FLAGS WRITTEN:
;   $7EF34C = 3 - Song of Storms learned
;
; GRAPHICS / PALETTES:
;   Room $00C9 uses spriteset $22 (34) -> slot 3 loads Sheet $38 (VRAM $C0..$FF).
;   Guru-Guru occupies the 12 blank tiles of Sheet $38 via Data/graphics/spr38.txt:
;     $E8 ($28/$29/$38/$39): Head/ears/eyes/beard/collar (16x16, OBJ5 $2B)
;     $EA ($2A/$2B/$3A/$3B): Tunic/wooden music box/feet (16x16, OBJ5 $2B)
;     $CF/$DF/$EF ($0F/$1F/$2F): Pewter gramophone horn (3x 8x8, OBJ6 $2D)
;     $FF ($3F): Music box crank + left hand (8x8, OBJ5 $2B / Frame 1 V-flip $AB)
; =========================================================

; Shared vanilla symbol referenced by Overworld/richard_quest.asm & Sprites/NPCs/ranch_girl.asm.
SpriteDraw_RaceGameLady =  $1AF92C

!SPRID              = Sprite_WindmillGuy
!NbrTiles           = 06 ; 6 body/horn/crank tiles + 1 shadow = 7 OAM slots (zero-based)
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 01  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 01  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 02  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 00  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 01  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 01  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

SpriteModule_Active_Bank1E = $1E8B11

%Set_Sprite_Properties(Sprite_WindmillGuy_Prep, Sprite_WindmillGuy_Long)

Sprite_WindmillGuy_Long:
{
  ; Safe sprite multiplexing: Sprite ID $B2 is shared between Sprite_WindmillGuy
  ; (NPC) and vanilla PlayerBee (spawned by Honeycomb swarm or player bottle bee).
  ; When spawned as a bee, $0D80,X is set to 1 (active player bee state).
  ; Windmill Guy has $0D80,X == 0.
  LDA.w $0D80, X : BEQ +
    JML SpriteModule_Active_Bank1E
  +
  PHB : PHK : PLB
  LDA.b #$01 : STA.w SprMiscC, X
  JSR Sprite_WindmillGuy_Draw
  BCS .skip_shadow
    JSL Sprite_DrawShadow
  .skip_shadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_WindmillGuy_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_WindmillGuy_Draw:
{
  JSL Sprite_PrepOamCoord : BCC .on_screen
    SEC
    RTS
  .on_screen
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : AND.b #$01 : TAY
  LDA.w .start_index, Y : STA.b $06

  PHX
  LDX.b #$05 ; 6 tiles per frame (indices 5..0 -> OAM slots 0..5)
  LDY.b #$00
  .nextTile
    PHX
    TXA : CLC : ADC.b $06
    PHA
    ASL A : TAX

    REP #$20
    LDA.b $00 : CLC : ADC.w .x_offsets, X : STA.b ($90), Y
    AND.w #$0100 : STA.b $0E
    INY
    LDA.b $02 : CLC : ADC.w .y_offsets, X : STA.b ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .on_screen_y
      LDA.b #$F0 : STA.b ($90), Y
      STA.b $0E
    .on_screen_y

    PLX
    INY
    LDA.w .chr, X : STA.b ($90), Y
    INY
    LDA.w .properties, X : STA.b ($90), Y

    PHY
    TYA : LSR #2 : TAY
    LDA.w .sizes, X : ORA.b $0F : STA.b ($92), Y
    PLY : INY

    PLX : DEX : BPL .nextTile
  PLX
  CLC
  RTS

  .start_index
  db $00, $06

  ; Order per frame (index 5 drawn to OAM slot 0 frontmost, index 0 backmost):
  ;   0: Horn neck ($CF)  1: Horn top ($DF)   2: Horn bot ($EF)
  ;   3: Body/Box ($EA)   4: Head ($E8)       5: Crank ($FF)
  .x_offsets
  dw 4, 12, 12, 0, 0, -5      ; Frame 0: Idle / Crank Up
  dw 4, 12, 12, 0, 0, -5      ; Frame 1: Crank Down + Nod

  .y_offsets
  dw -20, -23, -15, 0, -13, 2 ; Frame 0
  dw -19, -22, -14, 0, -12, 4 ; Frame 1

  .chr
  db $CF, $DF, $EF, $EA, $E8, $FF
  db $CF, $DF, $EF, $EA, $E8, $FF

  ; Priority 2 ($20) + OBJ page 1 ($01): OBJ5 = $2B ($AB V-flip), OBJ6 = $2D
  .properties
  db $2D, $2D, $2D, $2B, $2B, $2B
  db $2D, $2D, $2D, $2B, $2B, $AB

  .sizes
  db $00, $00, $00, $02, $02, $00
  db $00, $00, $00, $02, $02, $00
}

Sprite_WindmillGuy_Prep:
{
  RTL
}

Sprite_WindmillGuy_Main:
{
  JSL Sprite_PlayerCantPassThrough
  %PlayAnimation(0, 1, 16)

  LDA.l $7EF34C : CMP.b #$01 : BCC .no_ocarina
                  CMP.b #$02 : BCC .need_healing
                  CMP.b #$03 : BCS .already

  %ShowSolicitedMessage($1D7) : BCC .done
    LDA.b #$03 : STA.l $7EF34C
    LDA.b #$13 : STA.w $0CF8
    JSL $0DBB67 ; Link_CalculateSFXPan
    ORA.w $0CF8
    STA $012E ; Play the song learned sound
    RTS

  .no_ocarina
  %ShowSolicitedMessage($1D5)
  RTS

  .need_healing
  %ShowSolicitedMessage($1D6)
  RTS

  .already
  %ShowSolicitedMessage($1D8)

  .done
  RTS
}
