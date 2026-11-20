; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_SeaUrchin
!NbrTiles           = 05  ; 4 death poof + 1 body + 1 shadow (allocates 6 slots)
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 06  ; Number of Health the sprite have
!Damage             = 04  ; (08 is a whole heart), 04 is half heart
  ; Core/early_game_balance.asm: 4 HP, damage class 1 (half heart on any
  ; mail; class 4 above is 1 heart on any mail).
  !Health           = 04
  !Damage           = 01
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 00  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 01  ; 01 = can be blocked by link's shield?
!Prize              = 03  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_SeaUrchin_Prep, Sprite_SeaUrchin_Long);

Sprite_SeaUrchin_Long:
{
  PHB : PHK : PLB
  ; Keep drawing the body while SpriteModule_Die ($0DD0 == 6) counts SprTimerA
  ; down from $1F to $0A (in Region A slots after SpriteDeath_DrawPoof).
  LDA.w SprState, X : CMP.b #$06 : BNE .draw
    LDA.w SprTimerA, X : CMP.b #$0A : BCC .dying
  .draw
  JSR Sprite_SeaUrchin_Draw : BCS .dying
    JSL Sprite_DrawShadow
  .dying
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_SeaUrchin_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_SeaUrchin_Prep:
{
  PHB : PHK : PLB
  LDA #$01 : STA.w SprPrize, X
  LDA.w WORLDFLAG : BEQ +
    ; Eon Sea Urchin impervious to sword
    LDA.b #%10000100 : STA.w SprDefl, X
    LDA.b #$07 : STA.w SprPrize, X
  +
  PLB
  RTL
}

Sprite_SeaUrchin_Main:
{
  %PlayAnimation(0,3,8)
  %PlayerCantPassThrough()
  %DoDamageToPlayerSameLayerOnContact()
  JSL Sprite_DamageFlash_Long
  JSL Sprite_CheckIfRecoiling
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_CheckDamageFromPlayer
  RTS
}


Sprite_SeaUrchin_Draw:
{
  JSL Sprite_PrepOamCoord : BCC .on_screen
    SEC
    RTS
  .on_screen
  LDA.w SprState, X : CMP.b #$06 : BEQ .alloc_done
    JSL Sprite_OAM_AllocateDeferToPlayer
  .alloc_done

  LDA.w SprState, X : CMP.b #$06 : BEQ .dying_flash
    LDA.w SprFlash, X : ASL A : BRA .apply_flash
  .dying_flash
    LDA.w SprFlash, X
  .apply_flash
  AND.b #$0E : STA $08

  LDA $0DC0, X : CLC : ADC $0D90, X : AND.b #$07 : TAY ; Animation Frame
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
  LDA .properties, X : EOR $08 : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX
  CLC
  RTS


  .start_index
    db $00, $01, $02, $03, $04, $05, $06, $07
  .nbr_of_tiles
    db 0, 0, 0, 0, 0, 0, 0, 0
  .x_offsets
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
  .y_offsets
    dw 0
    dw -1
    dw 0
    dw -1
    dw 0
    dw -1
    dw 0
    dw -1
  .chr
    db $EA
    db $EC
    db $EA
    db $EC
    db $EA
    db $EC
    db $EA
    db $EC
  .properties
    db $29
    db $29
    db $69
    db $69
    db $29
    db $29
    db $69
    db $69
}
