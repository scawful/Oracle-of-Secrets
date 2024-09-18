; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_MakuTree
!NbrTiles           = 00  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 0   ; Number of Health the sprite have
!Damage             = 0   ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 0   ; Unused in this template (can be 0 to 7)
!Hitbox             = $0D ; 00 to 31, can be viewed in sprite draw tool
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

%Set_Sprite_Properties(Sprite_MakuTree_Prep, Sprite_MakuTree_Long)

; =========================================================

Sprite_MakuTree_Long:
{
    PHB : PHK : PLB

    JSL Sprite_CheckActive   ; Check if game is not paused
    BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

    JSR Sprite_MakuTree_Main ; Call the main sprite code

  .SpriteIsNotActive
    PLB ; Get back the databank we stored previously
    RTL ; Go back to original code
}
; =========================================================

Sprite_MakuTree_Prep:
{
  PHB : PHK : PLB

  ; Play the Maku Song
  LDA.b #$03 : STA.w $012C

  PLB
  RTL
}

; =========================================================

PaletteFilter_StartBlindingWhite = $00EEF1
ApplyPaletteFilter = $00E914

Sprite_MakuTree_Main:
{
  JSL Sprite_PlayerCantPassThrough
  
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw MakuTree_Handler
  dw MakuTree_MeetLink
  dw MakuTree_SpawnHeartContainer
  dw MakuTree_HasMetLink

  dw MakuTree_OfferTheDreamer
  dw MakuTree_HandleResponse
  dw MakuTree_HandleDreams
  dw MakuTree_DreamTransition

  MakuTree_Handler:
  {
    ; Check the progress flags 
    LDA.l $7EF3D4 : CMP.b #$01 : BEQ .has_met_link
      %GotoAction(1)
      RTS

    .has_met_link
    %GotoAction(3) 
    RTS
  }

  MakuTree_MeetLink:
  {
    LDA POSX : STA $02
    LDA POSY : STA $03
    LDA SprX, X : STA $04
    LDA SprY, X : STA $05
    JSL GetDistance8bit_Long : CMP #$28 : BCS .not_too_close
      %ShowUnconditionalMessage($20)
      LDA.b #$01 : STA.l $7EF3D4
      LDA.b #$01 : STA.l $7EF3C7 ; Mark the Hall of Secrets
      LDA.l $7EF3D6 : ORA.b #$02 : STA.l $7EF3D6
      %GotoAction(2)
    .not_too_close
    RTS
  }

  MakuTree_SpawnHeartContainer:
  {
    ; Give Link a heart container
    LDY #$3E : JSL Link_ReceiveItem
    %GotoAction(3)
    RTS
  }

  MakuTree_HasMetLink:
  {
    %ShowSolicitedMessage($22) : BCC .no_talk
      LDA.l $7EF3D6 : ORA.b #$02 : STA.l $7EF3D6
      ; TODO: Activate when dreams are implemented
      ; LDA.l CRYSTALS : BNE .no_essences
      ;   INC.w SprAction, X
      ; .no_essences
    .no_talk
    RTS
  }

  MakuTree_OfferTheDreamer:
  {
    %ShowSolicitedMessage($013C) : BCC .no_talk
      INC.w SprAction, X
    .no_talk
    RTS
  }

  MakuTree_HandleResponse:
  {
    LDA.w MsgChoice : BEQ .become_dreamer
    CMP.b #$01 : BEQ .said_no
      RTS
    .become_dreamer
    INC.w SprAction, X
    RTS
    .said_no
    %GotoAction(4)
    RTS
  }

  MakuTree_HandleDreams:
  {
    ; Check if Link has seen the dream
    LDA.l DREAMS
    CMP.b #$01 : BCC .mushroom_grotto
    CMP.b #$02 : BCC .tail_palace
    CMP.b #$04 : BCC .kalyxo_castle
    CMP.b #$08 : BCC .zora_temple
    CMP.b #$10 : BCC .glacia_estate
    CMP.b #$20 : BCC .goron_mines
    CMP.b #$40 : BCC .dragon_ship

    ; .kzt dimg
    ;   m - Mushroom Grotto
    ;   t - Tail Palace
    ;   k - Kalyxo Castle
    ;   z - Zora Temple
    ;   i - Glacia Estate
    ;   g - Goron Mines
    ;   d - Dragon Ship
    ;  CRYSTALS        = $7EF37A

    ; TODO: Check if Link has the essence for the dream
    .mushroom_grotto
    LDA.b #$00 : STA.w CurrentDream
    JMP .enter_dream
    .tail_palace
    LDA.b #$01 : STA.w CurrentDream
    JMP .enter_dream
    .kalyxo_castle
    LDA.b #$02 : STA.w CurrentDream
    JMP .enter_dream
    .zora_temple
    LDA.b #$03 : STA.w CurrentDream
    JMP .enter_dream
    .glacia_estate
    LDA.b #$04 : STA.w CurrentDream
    JMP .enter_dream
    .goron_mines
    LDA.b #$05 : STA.w CurrentDream
    JMP .enter_dream
    .dragon_ship
    LDA.b #$06 : STA.w CurrentDream
    .enter_dream
    PHX 
    LDA.b #$16 : STA.b $5D ; Set Link to sleeping
    LDA.b #$20 : JSL AncillaAdd_Blanket
    LDA.b $20 : CLC : ADC.b #$04 : STA.w $0BFA,X
    LDA.b $21 : STA.w $0C0E,X
    LDA.b $22 : SEC : SBC.b #$08 : STA.w $0C04,X
    LDA.b $23 : STA.w $0C18,X
    JSL PaletteFilter_StartBlindingWhite
    JSL ApplyPaletteFilter
    PLX 

    LDA.b #$60 : STA.w SprTimerB, X
    INC.w SprAction, X
    RTS
  }

  MakuTree_DreamTransition:
  {
    LDA.w SprTimerB, X : BNE +
      JSL Link_EnterDream
    +
    RTS
  }

}


