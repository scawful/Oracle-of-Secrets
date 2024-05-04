;==============================================================================
; Sprite Properties
;==============================================================================
!SPRID              = $9F ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 02  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = $08  ; Number of Health the sprite have
!Damage             = 04  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 00  ; Unused in this AntiKirby (can be 0 to 7)
!Hitbox             = 03  ; 00 to 31, can be viewed in sprite draw tool
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

%Set_Sprite_Properties(Sprite_AntiKirby_Prep, Sprite_AntiKirby_Long);


Sprite_AntiKirby_Long:
{
  PHB : PHK : PLB

  JSR Sprite_AntiKirby_Draw ; Call the draw code
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_AntiKirby_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

; ==============================================================================

Sprite_AntiKirby_Prep:
{
  PHB : PHK : PLB
  
  LDA #$00 : STA $0CAA, X
  LDA #$00 : STA $0B6B, X

  LDY $0FFF

  LDA .bump_damage, Y : STA $0CD2, X

  LDA .hp, Y : STA $0E50, X

  LDA .prize_pack, Y : STA $0BE0, X

  PLB
  RTL

  .bump_damage
  db $81, $88

  .hp
  db 4, 8

  .prize_pack
  db 6, 2
}

!RecoilTime = $30

Sprite_AntiKirby_Main:
{  
  
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw AntiKirby_Start
  dw AntiKirby_WalkRight
  dw AntiKirby_WalkLeft
  ; dw AntiKirby_Main
  ; dw AntiKirby_Moving
  ; dw AntiKirby_Collision
  dw AntiKirby_Hurt
  dw AntiKirby_Suck
  dw AntiKirby_Full
  dw AntiKirby_Death

  ; AntiKirby_Main:
  ; {
  ;   %PlayAnimation(0, 0, 10) ; Idle

  ;   .TileCollision
  ;   ; Reset some stuff

  ;   JSL Sprite_CheckDamageToPlayer
  ;   JSL Sprite_CheckDamageFromPlayer

  ;   JSL Sprite_MoveLong
  ;   JSL Sprite_CheckTileCollision

  ;   LDA $0E70, X : BNE .TileCollision

  ;   RTS

  ; }

  AntiKirby_Start:
  {
      %PlayAnimation(0, 0, 10) ; Idle

      ; Check health 
      LDA SprHealth, X : CMP.b #$01 : BCS .NotDead
        %GotoAction(6)
        RTS
    .NotDead

      JSL Sprite_DirectionToFacePlayer 
      TYA : CMP.b #$02 : BCC .WalkRight

    .WalkLeft
      %GotoAction(2)
      RTS

    .WalkRight 
      JSL Sprite_IsBelowPlayer : BCS .WalkLeft
      %GotoAction(1)
      RTS
  }

  AntiKirby_WalkRight:
  {
      %PlayAnimation(0, 3, 10) ; Walk Right
      
      PHX 
      JSL Sprite_DamageFlash_Long
      JSL Sprite_CheckDamageFromPlayerLong : BCC .NoDamage

      LDA #!RecoilTime : STA SprTimerA, X
      %GotoAction(3) ; Hurt
      PLX 
      RTS

    .NoDamage
      %DoDamageToPlayerSameLayerOnContact()
      PLX 
      %MoveTowardPlayer(10)
      JSL Sprite_BounceFromTileCollision
      JSL Sprite_PlayerCantPassThrough
      
    .Collision
      %GotoAction(0)
      RTS
  }

  AntiKirby_WalkLeft:
  {
    %PlayAnimation(4, 7, 10) ; Walk Left

    PHX 
    JSL Sprite_DamageFlash_Long
    JSL Sprite_CheckDamageFromPlayerLong : BCC .NoDamage
    LDA #!RecoilTime : STA SprTimerA, X
    %GotoAction(3) ; Hurt
    PLX : RTS
  .NoDamage
    %DoDamageToPlayerSameLayerOnContact()
    PLX 

    %MoveTowardPlayer(10)
    JSL Sprite_BounceFromTileCollision
    JSL Sprite_PlayerCantPassThrough
    %GotoAction(0)

    RTS
  }

  AntiKirby_Hurt:
  {
      %PlayAnimation(8, 8, 10) ; Hurt 
      LDA SprTimerA, X : BNE .NotDone
      %GotoAction(0)
    .NotDone
      RTS
  }

  AntiKirby_Suck:
  {
    %PlayAnimation(9, 10, 10) ; Suck
    RTS
  }

  AntiKirby_Full:
  {
    %PlayAnimation(11, 11, 10) ; Full
    RTS
  }

  AntiKirby_Death:
  {
    %PlayAnimation(8, 8, 10) ; Death

    LDA.b #$06
    STA.w $0DD0,X

    LDA.b #$0A
    STA.w $0DF0,X

    STZ.w $0BE0,X

    LDA.b #$09 ; SFX2.1E
    JSL $0DBB8A ; SpriteSFX_QueueSFX3WithPan
    
    RTS
  }
  
  
}


Sprite_AntiKirby_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

  LDA $0DA0, X : STA $08

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

  .start_index
  db $00, $01, $02, $03, $05, $06, $07, $08, $0A, $0B, $0D, $0F, $11
  .nbr_of_tiles
  db 0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 1, 1, 1
  .x_offsets
  dw 0
  dw 1
  dw 0
  dw 0, 16
  dw 0
  dw -1
  dw 0
  dw 0, -16
  dw 0
  dw 0, 16
  dw 0, 16
  dw -4, 12
  dw -4, 12
  .y_offsets
  dw 0
  dw 0
  dw 0
  dw 0, 0
  dw 0
  dw 0
  dw 0
  dw 0, 0
  dw 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  .chr
  db $00
  db $02
  db $00
  db $04, $06
  db $00
  db $02
  db $00
  db $04, $06
  db $20
  db $08, $0A
  db $28, $2A
  db $22, $24
  db $22, $24
  .properties
  db $37
  db $37
  db $37
  db $37, $37
  db $77
  db $77
  db $77
  db $77, $77
  db $37
  db $37, $37
  db $37, $37
  db $37, $37
  db $37, $37
  .sizes
  db $02
  db $02
  db $02
  db $02, $02
  db $02
  db $02
  db $02
  db $02, $02
  db $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
}