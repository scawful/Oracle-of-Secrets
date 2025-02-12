; =========================================================
; Maku Tree

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

Sprite_MakuTree_Long:
{
  PHB : PHK : PLB
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_MakuTree_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_MakuTree_Prep:
{
  PHB : PHK : PLB
  ; Play the Maku Song
  LDA.l OOSPROG2 : AND.b #$04 : BEQ +
    LDA.b #$03 : STA.w $012C
  +
  PLB
  RTL
}

PaletteFilter_StartBlindingWhite = $00EEF1
ApplyPaletteFilter = $00E914

Sprite_MakuTree_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw MakuTree_Handler
  dw MakuTree_MeetLink
  dw MakuTree_SpawnHeartContainer
  dw MakuTree_HasMetLink

  MakuTree_Handler:
  {
    ; Check the progress flags
    LDA.l MakuTreeQuest : AND.b #$01 : BNE .has_met_link
      %GotoAction(1)
      RTS
    .has_met_link
    %GotoAction(3)
    RTS
  }

  MakuTree_MeetLink:
  {
    JSL GetDistance8bit_Long : CMP #$28 : BCS .not_too_close
      %ShowUnconditionalMessage($20)
      LDA.b #$01 : STA.l MakuTreeQuest
      LDA.b #$01 : STA.l MapIcon ; Mushroom Grotto
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
    .no_talk
    RTS
  }
}
