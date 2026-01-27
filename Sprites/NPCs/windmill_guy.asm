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
; NOTE:
;   Uses Race Game Lady draw routine as a placeholder.
;   TODO: Swap to windmill NPC graphics/palette.
; =========================================================

SpriteDraw_RaceGameLady =  $1AF92C

!SPRID              = Sprite_WindmillGuy
!NbrTiles           = 02 ; Number of tiles used in a frame
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

%Set_Sprite_Properties(Sprite_WindmillGuy_Prep, Sprite_WindmillGuy_Long)

Sprite_WindmillGuy_Long:
{
  PHB : PHK : PLB
  LDA.b #$01 : STA.w SprMiscC, X
  JSL SpriteDraw_RaceGameLady
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_WindmillGuy_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_WindmillGuy_Prep:
{
  PHB : PHK : PLB
  PLB
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
    LDA.b #$13
    STA.w $0CF8
    JSL $0DBB67 ; Link_CalculateSFXPan
    ORA.w $0CF8
    STA $012E ; Play the song learned sound
    BRA .done

  .no_ocarina
  %ShowSolicitedMessage($1D5)
  BRA .done

  .need_healing
  %ShowSolicitedMessage($1D6)
  BRA .done

  .already
  %ShowSolicitedMessage($1D8)

  .done
  RTS
}
