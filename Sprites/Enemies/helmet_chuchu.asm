; ========================================================= 
; Sprite Properties
; ========================================================= 

!SPRID              = $05 ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 05  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = $10 ; Number of Health the sprite have
!Damage             = 04  ; (08 is a whole heart), 04 is half heart
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

%Set_Sprite_Properties(Sprite_HelmetChuchu_Prep, Sprite_HelmetChuchu_Long)

; =========================================================

; 0-1: No Helmet Green
; 2-3: Mask Red
; 4-5: Helmet Green

Sprite_HelmetChuchu_Long:
{
  PHB : PHK : PLB

  JSR Sprite_HelmetChuchu_Draw ; Call the draw code
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_HelmetChuchu_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}


Sprite_HelmetChuchu_Prep:
{
  PHB : PHK : PLB

  LDA.b #$20 : STA.w SprHealth, X
  JSL GetRandomInt : AND.b #$02 : STA SprAction, X
  STZ.w SprMiscB, X

  PLB
  RTL
}

; =========================================================

Sprite_HelmetChuchu_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw HelmetGreen
  dw NoHelmetGreen
  dw MaskRed
  
  HelmetGreen:
  {
    %StartOnFrame(4)
    %PlayAnimation(4, 5, 16)
    JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
      %GotoAction(1)
    .no_damage
    JSR Sprite_Chuchu_Move    
    RTS
  }

  NoHelmetGreen:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 1, 16)
    JSL Sprite_CheckDamageFromPlayer
    JSR Sprite_Chuchu_Move
    RTS
  }

  MaskRed:
  {
    %StartOnFrame(2)
    %PlayAnimation(2, 3, 16)
    JSL Sprite_CheckDamageFromPlayer
    JSR Sprite_Chuchu_Move
    RTS
  }
}

Sprite_Chuchu_Move:
{
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprMiscB, X 
  JSL UseImplicitRegIndexedLocalJumpTable

  dw BounceTowardPlayer
  dw RecoilFromPlayer

  BounceTowardPlayer:
  {
    JSL GetRandomInt : AND.b #$02 : STA $09 ; Speed
    JSL GetRandomInt : AND.b #$07 : STA $08 ; Height

    JSL Sprite_MoveAltitude
    DEC.w $0F80,X : DEC.w $0F80,X
    LDA.w $0F70, X : BPL .aloft
      STZ.w $0F70, X
      LDA.b $08 : STA.w $0F80, X ; set height from 08
      LDA.b $09
      JSL Sprite_ApplySpeedTowardsPlayer
    .aloft
    LDA.w $0F70, X : BEQ .dontmove
      JSL Sprite_Move
    .dontmove

    JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
      INC.w SprMiscB, X
      LDA.b #$20 : STA.w SprTimerB, X
    .no_damage

    JSL Sprite_CheckDamageToPlayer : BCC .no_attack
      INC.w SprMiscB, X
      LDA.b #$20 : STA.w SprTimerB, X
    .no_attack

    RTS
  }

  RecoilFromPlayer:
  {
    JSL GetRandomInt : AND.b #$02 : STA $09 ; Speed
    LDA SprX, X : CLC : ADC $09 : STA $04
    LDA SprY, X : SEC : SBC $09 : STA $06
    LDA SprXH, X : ADC #$00 : STA $05
    LDA SprYH, X : ADC #$00 : STA $07
    LDA $09 : STA $00 : STA $01
    JSL Sprite_ProjectSpeedTowardsEntityLong

    LDA.w SprTimerB, X : BNE .not_done
      STZ.w SprMiscB, X
    .not_done

    RTS
  }
}

; =========================================================

Sprite_HelmetChuchu_Draw:
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

  LDA $00 : STA ($90), Y
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


  ; =======================================================
  ;         chr     prop
  ; Mask    $04     $37
  ; Helmet  $08     $3B

  .start_index
  db $00, $02, $03, $06, $08, $0A, $0C, $0E
  .nbr_of_tiles
  db 1, 0, 2, 1, 1, 1, 1, 0
  .y_offsets
  dw 0, -8
  dw 0
  dw 0, -8, -8
  dw 0, -4
  dw 0, -8
  dw 0, -4
  dw 0, -8
  dw 0
  .chr
  ; No Helmet Green
  db $26, $16
  db $24
  ; Mask Red
  db $26, $16, $04
  db $24, $04
  ; Helmet Green
  db $26, $08
  db $24, $08
  ; No Helmet Green
  db $26, $16
  db $24
  .properties
  db $3B, $3B
  db $3B
  db $37, $37, $37
  db $37, $37
  db $3B, $39
  db $3B, $39
  db $39, $39
  db $39
}
