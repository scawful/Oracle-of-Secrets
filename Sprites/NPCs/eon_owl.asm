; =========================================================
; Kaepora Gaebora and Eon Owl

!SPRID              = Sprite_EonOwl
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
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
!DeflectProjectiles = 01  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 01  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 01  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_EonOwl_Prep, Sprite_EonOwl_Long)

Sprite_EonOwl_Long:
{
  PHB : PHK : PLB
  ; If it is not the Hall of Secrets map
  LDA.b $8A : CMP.b #$0E : BNE .NotGaebora
    ; If the map doesn't have the 6 crystals
     LDA.l $7EF37A : CMP.b #$77 : BNE .Despawn
        ; If the player has the Song of Soaring, despawn
        LDA.l $7EF34C : CMP.b #$03 : BCS .Despawn
          LDA.b #$01 : STA.w SprSubtype, X
          JSR Sprite_KaeporaGaebora_Draw
          JMP .HandleSprite
  .NotGaebora
  JSR Sprite_EonOwl_Draw
  .HandleSprite
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_EonOwl_Main
  .SpriteIsNotActive
  PLB
  RTL
  .Despawn
  STZ.w SprState, X
  PLB
  RTL
}

; =========================================================

Sprite_EonOwl_Prep:
{
  PHB : PHK : PLB

  STZ.w SprHitbox, X

  LDA.b $8A : CMP.b #$0E : BNE .NotGaebora
    LDA.b #$20 : STA.w SprTimerA, X
    LDA.b #$03 : STA.w SprAction, X
  .NotGaebora
  LDA.w AreaIndex : CMP.b #$50 : BNE .not_intro
    ; If Map 0x50, don't spawn after getting sword
    LDA.l Sword : CMP.b #$01 : BCC .continue
       STZ.w SprState, X
    .continue
  .not_intro
  PLB
  RTL
}

; =========================================================

Sprite_EonOwl_Main:
{
  LDA.w SprAction, X
  JSL   JumpTableLocal

  dw EonOwl_Idle
  dw EonOwl_IntroDialogue
  dw EonOwl_FlyingAway

  dw KaeporaGaebora
  dw KaeporaGaebora_Respond
  dw KaeporaGaebora_FlyAway

  EonOwl_Idle:
  {
    %PlayAnimation(0,1,16)
    JSL GetDistance8bit_Long : CMP #$28 : BCS .not_too_close
      %GotoAction(1)
    .not_too_close
    RTS
  }

  EonOwl_IntroDialogue:
  {
    %PlayAnimation(0,1,16)
    %ShowUnconditionalMessage($00E6)
    LDA.b #$C0 : STA.w SprTimerA, X
    %GotoAction(2)
    RTS
  }

  EonOwl_FlyingAway:
  {
    %PlayAnimation(2,3,10)
    LDA.b #$F8 : STA.w SprYSpeed, X
    JSL   Sprite_Move

    LDA.w SprTimerA, X : CMP.b #$80 : BNE +
      LDA.b #$40 : STA.w SprXSpeed, X
    +

    LDA.w SprTimerA, X : BNE .not_done
      STZ.w SprState, X
    .not_done

    RTS
  }

  ; 0x03 - Kaepora Gaebora
  KaeporaGaebora:
  {
    %PlayAnimation(0,0,1)
    JSL GetDistance8bit_Long : CMP.b #$50 : BCC .not_ready
      LDA.w SprTimerA, X : BNE .not_ready
        %ShowUnconditionalMessage($146)
        %GotoAction(4)
    .not_ready
    RTS
  }

  KaeporaGaebora_Respond:
  {
    LDA $1CE8 : BNE .player_said_no
      %GotoAction(3)
      RTS
    .player_said_no
    %GotoAction(5)
    LDA.b #$60 : STA.w SprTimerA, X
    LDA.b #$03 : STA.l $7EF34C
    RTS
  }

  FlyAwaySpeed = 10
  KaeporaGaebora_FlyAway:
  {
    LDA.b #-FlyAwaySpeed : STA.w SprYSpeed, X
    JSL Sprite_Move
    LDA.w SprTimerA, X : BNE .not_ready
      STZ.w SprState, X
    .not_ready
    RTS
  }
}

; =========================================================

Sprite_EonOwl_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame,     X : TAY     ;Animation Frame
  LDA   .start_index, Y : STA $06

  PHX
  LDX   .nbr_of_tiles, Y ;amount of tiles -1
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
  CLC   : ADC #$0010 : CMP.w #$0100
  SEP   #$20
  BCC   .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA   $0E
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

  .start_index
  db $00, $04, $06, $08
  .nbr_of_tiles
  db 3, 1, 1, 1
  .x_offsets
  dw 0, 0, 8, 8
  dw 8, -8
  dw -8, 8
  dw 8, -8
  .y_offsets
  dw 0, 8, 0, 8
  dw 0, 0
  dw 0, 0
  dw 0, 0
  .chr
  db $C2, $D2, $C2, $D2
  db $C3, $C3
  db $C7, $C7
  db $C9, $C9
  .properties
  db $37, $37, $77, $77
  db $37, $77
  db $37, $77
  db $37, $77
  .sizes
  db $00, $00, $00, $00
  db $02, $02
  db $02, $02
  db $02, $02
}

Sprite_KaeporaGaebora_Draw:
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

  .start_index
  db $00
  .nbr_of_tiles
  db 3
  .x_offsets
  dw -8, -8, 8, 8
  .y_offsets
  dw 0, -16, 0, -16
  .chr
  db $AE, $8E, $AE, $8E
  .properties
  db $3B, $3B, $7B, $7B
  .sizes
  db $02, $02, $02, $02
}
