; ==============================================================================
; Farore/Maku Tree - Sprite Uncle/Priest
; 
;
; ==============================================================================

SpritePrep_FaroreAndMakuTree:
{
  ; farore forest during intro 
  ; activates impa sprite 

  ; maku tree interaction in the forest 
  ; needs to be in part 1 of the game 
}

; ==============================================================================

Sprite_FaroreAndMakuTree:
{
  LDA $0E90, X ; 

  JSL UseImplicitRegIndexedLocalJumpTable

  dw Sprite_Farore
  dw Sprite_MakuTree
}

; ==============================================================================

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

; ==============================================================================

Farore_IntroCutscene:
{
  ; Link approaches Farore sprite with Impa sprite (Zelda)
  
  ; Activates Mantle style cutscene

  ; Jump to antagonist cutscene code 
}

; ==============================================================================

Sprite_MakuTree:
{
  ; Main entry point for the MakuTree routines 
}

; ==============================================================================
