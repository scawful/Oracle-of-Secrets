; ========================================================= 
; Sprite Properties
; ========================================================= 

!SPRID              = $CD ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 03  ; Number of tiles used in a frame
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
%Set_Sprite_Properties(Sprite_ThunderGhost_Prep, Sprite_ThunderGhost_Long)

; =========================================================

Sprite_ThunderGhost_Long:
{
  PHB : PHK : PLB

  JSR Sprite_ThunderGhost_Draw ; Call the draw code
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_ThunderGhost_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}


Sprite_ThunderGhost_Prep:
{
  PHB : PHK : PLB
    
  LDA.b #$08 : STA.w SprTimerA, X
  LDA.b #$08 : STA.w SprTimerB, X
  LDA.b #$10 : STA.w SprHealth, X 

  PLB
  RTL
}

; =========================================================

Sprite_ThunderGhost_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw ThunderGhostFaceForward
  dw ThunderGhostLeft
  dw ThunderGhostRight
  dw CastThunderLeft
  dw CastThunderRight


  ThunderGhostFaceForward:
  {
    %PlayAnimation(0, 1, 16)
    JSR Sprite_ThunderGhost_Move

    RTS
  }

  ThunderGhostLeft:
  {
    %PlayAnimation(2, 3, 16)
    JSR Sprite_ThunderGhost_Move
    RTS
  }

  ThunderGhostRight:
  {
    %PlayAnimation(4, 5, 16)
    JSR Sprite_ThunderGhost_Move
    RTS
  }

  CastThunderLeft:
  {
    %StartOnFrame(6)
    %PlayAnimation(6, 6, 16)
    JSL Sprite_CheckDamageToPlayer
    JSL Sprite_Move
    LDA.w SprTimerA, X : BNE +
      STZ.w SprState, X
    +
    RTS
  }

  CastThunderRight:
  {
    %StartOnFrame(6)
    %PlayAnimation(7, 7, 16)
    JSL Sprite_CheckDamageToPlayer
    JSL Sprite_Move
    LDA.w SprTimerA, X : BNE +
      STZ.w SprState, X
    +
    RTS
  }
}


Sprite_ThunderGhost_Move:
{
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_PlayerCantPassThrough

  
  JSL GetRandomInt : AND #$7F : BNE ++
    JSR SpawnLightningAttack
  ++

  LDA.w SprTimerA, X : BNE +
    JSL Sprite_IsToRightOfPlayer : CPY.b #$01 : BNE .ToRight
      %GotoAction(1)
      JMP .Continue
    .ToRight
    %GotoAction(2)
    LDA.b #$20 : STA.w SprTimerA, X
    JMP .Continue
  +
  %GotoAction(0)
  .Continue

  LDA.w SprMiscB, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw ThunderGhostMove

  ThunderGhostMove:
  {
    JSL GetRandomInt : AND.b #$03
    JSL Sprite_ApplySpeedTowardsPlayer
    JSL Sprite_CheckTileCollision

    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer

    RTS
  }
}

SpawnLightningAttack:
{
  PHX 
  LDA.b #$CD 
  JSL Sprite_SpawnDynamically
  BMI .no_space

  ; Use SprXSpeed, SprYSpeed, SprXRound, SprYRound
  ; SprX, SprY, SprXH, SprY, to cast the lightning spell
  ; and make it move off to the bottom left or bottom right

  ; Y is the ID of the new attack sprite
  ; X is the ID of the current source sprite 

  ; Left 0 or Right 1
  PHY
  JSL Sprite_IsToRightOfPlayer : TAY : CMP.b #$01 : BEQ +
    LDA.b #$00
    JMP .Continue
  +
  LDA.b #$01
  .Continue
  CLC : ADC.b #$03
  PLY
  STA.w SprSubtype, Y
  STA.w SprAction, Y

  LDA.w SprX, X : STA.w SprX, Y
  LDA.w SprY, X : STA.w SprY, Y
  LDA.w SprXH, X : STA.w SprXH, Y
  LDA.w SprYH, X : STA.w SprYH, Y

  LDA.w SprXSpeed, X : STA.w SprXSpeed, Y
  LDA.w SprYSpeed, X : STA.w SprYSpeed, Y
  LDA.b #$02 : STA.w SprXRound, Y
  LDA.b #$02 : STA.w SprYRound, Y
  LDA.b #$30 : STA.w SprTimerA, Y
  LDA.b #$30 : STA.w SprTimerB, Y
  .no_space

  PLX

  RTS
}

; =========================================================

Sprite_ThunderGhost_Draw:
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
      
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
      
  PLY : INY
      
  PLX : DEX : BPL .nextTile

  PLX

  RTS


  ; =======================================================
  .start_index
  db $00, $03, $06, $09, $0C, $0F, $12, $15
  .nbr_of_tiles
  db 2, 2, 2, 2, 2, 2, 2, 2
  .x_offsets
  dw 0, 0, 8
  dw 8, 0, 0
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 8, 0
  dw 0, 8, 0
  dw -12, -8, -16
  dw 12, 16, 20
  .y_offsets
  dw -8, 0, -8
  dw -8, 0, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 12, 24, 20
  dw 12, 24, 12
  .chr
  db $3A, $02, $3B
  db $3A, $02, $3B
  db $20, $00, $01
  db $22, $10, $11
  db $20, $00, $01
  db $22, $10, $11
  db $28, $2A, $2B
  db $28, $2A, $2B
  .properties
  db $3B, $3B, $3B
  db $7B, $7B, $7B
  db $3B, $3B, $3B
  db $3B, $3B, $3B
  db $7B, $7B, $7B
  db $7B, $7B, $7B
  db $3B, $3B, $3B
  db $7B, $3B, $3B
  .sizes
  db $00, $02, $00
  db $00, $02, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
}
