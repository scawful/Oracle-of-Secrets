; Goron Sprite

!SPRID              = $F2 ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 04  ; Number of tiles used in a frame
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
%Set_Sprite_Properties(Sprite_Goron_Prep, Sprite_Goron_Long);

Sprite_Goron_Long:
{
  PHB : PHK : PLB

  LDA.w WORLDFLAG : BEQ .kalyxo
    JSR Sprite_EonGoron_Draw
    JMP +
  .kalyxo
  JSR Sprite_KalyxoGoron_Draw
  +
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive
  BCC .SpriteIsNotActive

  JSR Sprite_Goron_Main

  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Goron_Prep:
{
  PHB : PHK : PLB
  LDA.w WORLDFLAG : BEQ +
    LDA.b #$03 : STA.w SprAction, X
    JMP ++
  +
  PHX 
  LDX $8A
  LDA.l $7EF280,X : CMP.b #$20 : BEQ +++
  PLX
  STZ.w SprAction, X
  ++
  PLB
  RTL
  +++
  PLX
  LDA.b #$02 : STA.w SprAction, X
  PLB
  RTL
}

Sprite_Goron_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw KalyxoGoron_Main
  dw KalyxoGoron_OpenMines
  dw KalyxoGoron_MinesOpened
  dw EonGoron_Main
  dw EonGoron_Sing
  dw EonGoron_Punch

  KalyxoGoron_Main:
  {
    LDA.l RockMeat : BEQ +
                     CMP.b #$05 : BCC ++
                     %ShowSolicitedMessage($01A9) : BCC +++
                     INC.w SprAction, X
                     +++
                     RTS
    +
    %ShowSolicitedMessage($01A7)
    RTS
    ++
    %ShowSolicitedMessage($01A8)
    RTS
  }

  KalyxoGoron_OpenMines:
  {
    %PlayAnimation(1,1,10)
    LDA.b #$04 : STA $04C6
    INC.w SprAction, X
    RTS
  }

  KalyxoGoron_MinesOpened:
  {
    %PlayAnimation(1,1,10)
    RTS
  }

  EonGoron_Main:
  {
    %PlayAnimation(0, 1, 10)
    RTS
  }

  EonGoron_Sing:
  {
    %PlayAnimation(2, 3, 10)
    RTS
  }

  EonGoron_Punch:
  {
    %PlayAnimation(4, 5, 10)
    RTS
  }
}

Sprite_KalyxoGoron_Draw:
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
  db 3, 3
  .x_offsets
  dw -8, -8, 8, 8
  dw -8, -8, 8, 8
  .y_offsets
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  .chr
  db $8C, $AC, $8C, $AC
  db $8A, $AA, $8A, $AA
  .properties
  db $37, $37, $77, $77
  db $37, $37, $77, $77
  .sizes
  db $02, $02, $02, $02
  db $02, $02, $02, $02

}

Sprite_EonGoron_Draw:
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
  db $00, $01, $02, $03, $04, $06
  .nbr_of_tiles
  db 0, 0, 0, 0, 1, 1
  .x_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0, 0
  dw 0, 8
  .y_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0, -8
  dw 0, -8
  .chr
  db $8C
  db $8C
  db $AC
  db $AC
  db $AA, $B9
  db $AA, $B9
  .properties
  db $37
  db $77
  db $37
  db $77
  db $37, $37
  db $77, $77
  .sizes
  db $02
  db $02
  db $02
  db $02
  db $02, $00
  db $02, $00
}
