; Zora Princess
; Grants Link the Zora Mask when Song of Healing is played

!SPRID              = Sprite_ZoraPrincess
!NbrTiles           = 9 ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 02  ; 00 to 31, can be viewed in sprite draw tool
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
%Set_Sprite_Properties(Sprite_ZoraPrincess_Prep, Sprite_Zora_Long);

Sprite_ZoraPrincess_Long:
{
  PHB : PHK : PLB
  JSR Sprite_ZoraPrincess_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_ZoraPrincess_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_ZoraPrincess_Prep:
{
  PHB : PHK : PLB
  LDA.l $7EF302 : BEQ .doesnt_have_mask
    STZ.w SprState, X ; Kill the sprite
  .doesnt_have_mask

  LDA #$00 : STA.w SprDefl, X
  LDA #$00 : STA.w SprTileDie, X
  PLB
  RTL
}


Sprite_ZoraPrincess_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw WaitForLink
  dw CheckForSongOfHealing
  dw ThanksMessage
  dw GiveZoraMask

  WaitForLink:
  {
    %PlayAnimation(0, 1, 10)
    %ShowSolicitedMessage($0C5) : BCC .no_hablaba
      %GotoAction(1)
    .no_hablaba
    RTS
  }

  CheckForSongOfHealing:
  {
    %PlayAnimation(0, 1, 10)
    LDA.b SongFlag : BEQ .ninguna_cancion
      STZ.b SongFlag
      LDA.b #$C0 : STA.w SprTimerD, X
      %GotoAction(2)
    .ninguna_cancion
    RTS
  }

  ThanksMessage:
  {
    %PlayAnimation(0, 1, 10)
    LDA.w SprTimerD,              X : BNE +
      %ShowUnconditionalMessage($0C6)
      LDA.b #$C0 : STA.w SprTimerD, X
      %GotoAction(3)
    +
    RTS
  }

  GiveZoraMask:
  {
    LDA.w SprTimerD, X : BNE +
      LDY   #$0F : STZ $02E9     ; Give the Zora Mask
      JSL   Link_ReceiveItem
      LDA   #$01 : STA.l $7EF302
      LDA.b #$00 : STA.w SprState, X
    +
    RTS
  }
}


Sprite_ZoraPrincess_Draw:
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
  db $00, $04
  .nbr_of_tiles
  db 3, 11
  .x_offsets
  dw -4, 4, -4, 4
  dw 4, 4, 4, 4, -4, -4, -4, -4, 12, 12, 12, 12
  .y_offsets
  dw -8, -8, 8, 8
  dw -8, 0, 8, 16, -8, 0, 8, 16, -8, 0, 8, 16
  .chr
  db $C0, $C1, $E0, $E1
  db $C1, $D1, $E1, $F1, $C3, $D3, $E3, $F3, $C3, $D3, $E3, $F3
  .properties
  db $33, $33, $33, $33
  db $33, $33, $33, $33, $33, $33, $33, $33, $73, $73, $73, $73
  .sizes
  db $02, $02, $02, $02
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
}
