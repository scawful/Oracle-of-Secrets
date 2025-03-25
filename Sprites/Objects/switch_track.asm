; =========================================================
; Switch Track sprite

!SPRID              = Sprite_SwitchTrack
!NbrTiles           = 02  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 01  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 00  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 01  ; 01 = your sprite continue to live offscreen
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

%Set_Sprite_Properties(Sprite_RotatingTrack_Prep, Sprite_RotatingTrack_Long)

Sprite_RotatingTrack_Long:
{
  PHB : PHK : PLB
  JSR Sprite_RotatingTrack_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_RotatingTrack_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_RotatingTrack_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X

  ; Setup Minecart position to look for tile IDs
  ; We use AND #$F8 to clamp to a 8x8 grid.
  ; Subtract 8 from the Y position to get the tile right above instead.
  LDA.w SprY, X : AND #$F8 : SEC : SBC.b #$08 : STA.b $00
  LDA.w SprYH, X : STA.b $01

  LDA.w SprX, X : AND #$F8 : STA.b $02
  LDA.w SprXH, X : STA.b $03

  ; Fetch tile attributes based on current coordinates
  LDA.b #$00 : JSL Sprite_GetTileAttr

  LDA.w SPRTILE : SEC : SBC.b #$D0 : STA.w SprAction, X

  ; Run the main frame once so that the animation frame is
  ; started correctly.
  JSR Sprite_RotatingTrack_Main
  PLB
  RTL
}

; =========================================================
; Modes
; 0 = TopLeft -> TopRight
; 1 = TopRight -> BottomRight
; 2 = BottomRight -> BottomLeft
; 3 = BottomLeft -> TopLeft

; The state of each switch. Up to $0250 used which is all free ram.
SwitchRam = $0230

Sprite_RotatingTrack_Main:
{
  ; Get the subtype of the track so that we can get its on/off state.
  LDA.w SprSubtype, X : TAY

  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw TopLeftToTopRight
  dw BottomLeftToTopLeft
  dw TopRightToBottomRight
  dw BottomRightToBottomLeft

  ; 00 = TopLeft -> TopRight
  TopLeftToTopRight:
  {
    LDA.w SwitchRam, Y : BNE .part2
      LDA.b #$00 : STA.w SprFrame, X
      RTS
    .part2
    LDA.b #$01 : STA.w SprFrame, X
    RTS
  }

  ; 01 = BottomLeft -> TopLeft
  BottomLeftToTopLeft:
  {
    LDA.w SwitchRam, Y : BNE .part2_c
      LDA.b #$03 : STA.w SprFrame, X
      RTS
    .part2_c
    LDA.b #$00 : STA.w SprFrame, X
    RTS
  }

  ; 02 = TopRight -> BottomRight
  TopRightToBottomRight:
  {
    LDA.w SwitchRam, Y : BNE .part2_a
      LDA.b #$01 : STA.w SprFrame, X
      RTS
    .part2_a
    LDA.b #$02 : STA.w SprFrame, X
    RTS
  }

  ; 03 = BottomRight -> BottomLeft
  BottomRightToBottomLeft:
  {
    LDA.w SwitchRam, Y : BEQ .part2_b
      LDA.b #$03 : STA.w SprFrame, X
      RTS
    .part2_b
    LDA.b #$02 : STA.w SprFrame, X
    RTS
  }
}

Sprite_RotatingTrack_Draw:
{
  JSL Sprite_PrepOamCoord
  LDA.b #$04 : JSL OAM_AllocateFromRegionB

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
  LDA $02 : STA ($90), Y
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

  .start_index
    db $00, $01, $02, $03
  .nbr_of_tiles
    db 0, 0, 0, 0
  .chr
    db $44
    db $44
    db $44
    db $44
  .properties
    db $3D
    db $7D
    db $FD
    db $BD
}

