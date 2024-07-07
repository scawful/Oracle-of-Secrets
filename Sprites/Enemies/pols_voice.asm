
!SPRID              = $A4 ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 02  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 10  ; Number of Health the sprite have
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
%Set_Sprite_Properties(Sprite_PolsVoice_Prep, Sprite_PolsVoice_Long);

; =========================================================

Sprite_PolsVoice_Long:
{
  PHB : PHK : PLB

  JSR Sprite_PolsVoice_Draw ; Call the draw code
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_PolsVoice_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

; =========================================================
Sprite_PolsVoice_Prep:
{
  PHB : PHK : PLB
    
  LDA.b #$80 : STA.w SprTimerA, X
  LDA.b #$00 : STA.w SprDefl, X
  LDA.b #$00 : STA.w SprTileDie, X

  PLB
  RTL
}

; =========================================================
Sprite_PolsVoice_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw PolsVoice_MoveAround
  dw PolsVoice_HopAround

  PolsVoice_MoveAround:
  {
    %StartOnFrame(0)
    %PlayAnimation(0,3,10)

    ;$09 = speed, $08 = max height
    LDA #$05 : STA $09
    LDA #$02 : STA $08
    JSL Sprite_BounceTowardPlayer
    JSL Sprite_BounceFromTileCollision
    JSL Sprite_DamageFlash_Long

    
    %DoDamageToPlayerSameLayerOnContact()

    JSL GetRandomInt : AND #$3F : BNE .not_done
      LDA #$04 : STA.w SprTimerA, X
      %GotoAction(1)
    .not_done

    JSL Sprite_CheckDamageFromPlayerLong : BCC .no_damage
      JSL Sprite_DirectionToFacePlayer
      
      ; Apply the speed positive or negative speed
      LDA $0E : BPL .not_up
        LDA #$20 : STA.w SprYSpeed, X 
        BRA .not_down
      .not_up
      LDA #$E0 : STA.w SprYSpeed, X
      .not_down
      LDA $0F : BPL .not_right
        LDA #$20 : STA.w SprXSpeed, X
        BRA .not_left
      .not_right
      LDA #$E0 : STA.w SprXSpeed, X
      .not_left
      LDA #$04 : STA.w SprTimerA, X
      %GotoAction(1)
    .no_damage
    RTS
  }

  PolsVoice_HopAround:
  {
    %StartOnFrame(4)
    %PlayAnimation(4,4,10)

    JSL Sprite_MoveXyz
    JSL Sprite_BounceFromTileCollision
    JSL Sprite_DamageFlash_Long

    %DoDamageToPlayerSameLayerOnContact()

    LDA SprTimerA, X : BNE .not_done
      %GotoAction(0)
    .not_done
    JSL Sprite_CheckDamageFromPlayerLong : BCC .no_damage
      JSL Sprite_InvertSpeed_XY
    .no_damage
    RTS
  }

}


; =========================================================

Sprite_PolsVoice_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

  LDA.w SprFlash, X : STA $08

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
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY 
      
  TYA : LSR #2 : TAY
      
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
      
  PLY : INY
      
  PLX : DEX : BPL .nextTile

  PLX

  RTS


  ; =======================================================

  .start_index
    db $00, $01, $02, $03, $04
  .nbr_of_tiles
    db 0, 0, 0, 0, 1
  .x_offsets
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0, 0
  .y_offsets
    dw 0
    dw 0
    dw 0
    dw 0
    dw -4, -20
  .chr
    db $6C
    db $6A
    db $6C
    db $6A
    db $6E, $4E
  .properties
    db $3B
    db $3B
    db $3B
    db $7B
    db $3B, $3B
  .sizes
    db $02
    db $02
    db $02
    db $02
    db $02, $02
}