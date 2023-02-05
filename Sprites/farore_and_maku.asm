;==============================================================================
; Farore/Maku Tree - Sprite Uncle/Priest
; 
;
;==============================================================================

incsrc sprite_macros.asm
incsrc sprite_functions_hooks.asm

;==============================================================================

org $298000
incsrc sprite_jump_table.asm

;==============================================================================

org $308000
incsrc sprite_new_functions.asm

;==============================================================================
; Sprite Properties
;==============================================================================
!SPRID              = $73; The sprite ID you are overwriting (HEX)
!NbrTiles           = 00 ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 00  ; 00 to 31, can be viewed in sprite draw tool
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
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

;==============================================================================

; TODO: Setup Sprite Properties for Farore 
%Set_Sprite_Properties(Sprite_Farore_Prep, Sprite_Farore_Long) 

;==============================================================================


SpritePrep_FaroreAndMakuTree:
{
  ; farore forest during intro 
  ; activates impa sprite 

  ; maku tree interaction in the forest 
  ; needs to be in part 1 of the game 
}

;==============================================================================

Sprite_FaroreAndMakuTree:
{
  LDA $0E90, X ; 

  JSL UseImplicitRegIndexedLocalJumpTable

  dw Sprite_Farore
  dw Sprite_MakuTree
}

;==============================================================================

Sprite_Farore:
{
  ; Main entry point for the Farore sprite in the overworld
  JSL Farore_Draw 
  JSR Sprite2_CheckIfActive

  LDA $0E80, X
  
  JSL UseImplicitRegIndexedLocalJumpTable

  dw Farore_IntroCutscene
  dw Farore_FinaleCutscene
}

;==============================================================================

Farore_IntroCutscene:
{
  ; Link approaches Farore sprite with Impa sprite (Zelda)
  
  ; Activates Mantle style cutscene

  ; Jump to antagonist cutscene code 
}

;==============================================================================

Sprite_MakuTree:
{
  ; Main entry point for the MakuTree routines 
}

;==============================================================================
