; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_DekuLeaf
!NbrTiles           = 03  ; OAM slots - 1: 4 tiles (16 bytes)
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = $0D ; 00 to 31, can be viewed in sprite draw tool
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

%Set_Sprite_Properties(Sprite_DekuLeaf_Prep, Sprite_DekuLeaf_Long)

Sprite_DekuLeaf_Long:
{
  PHB : PHK : PLB
  LDA.b $8A : CMP.b #$3D : BEQ .whirlpool
    JSR Sprite_DekuLeaf_Draw
    BRA .run_main
  .whirlpool
    JSR Sprite_Whirlpool_Draw
  .run_main
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_DekuLeaf_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_DekuLeaf_Prep:
{
  PHB : PHK : PLB
  LDA.b $8A : CMP.b #$3D : BNE .not_whirlpool
    LDA.b #$01 : STA.w SprAction, X
  .not_whirlpool
  PLB
  RTL
}

Sprite_DekuLeaf_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw WaitForPlayer
  dw Whirlpool_Main

  WaitForPlayer:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 0, 10)

    JSR CheckIfPlayerIsOn : BCC +
      LDA.b #$01 : STA.b $71
      LDA.w $02B2 : CMP.b #$01 : BNE ++
        JSL Sprite_SpawnPoofGarnish
      ++
      RTS
    +
    STZ.b $71
    RTS
  }

  Whirlpool_Main:
  {
    %PlayAnimation(0, 2, 10)
    JSR CheckIfPlayerIsOn : BCC .not_on

    LDA.w $0AAB : BEQ .not_on

      STZ.b $55    ; Reset cape flag
      STZ.w $0AAB  ; Reset underwater flag
      STZ.w $0351  ; Reset ripple flag
      STZ.w $037B  ; Reset invincibility flag
      ; Reset the mask with its sprite bank and palette. STZ $02B2 alone left
      ; the Zora Mask palette on Link's sprite (Discord 2025-01-01).
      LDA.w $02B2 : BEQ +
        PHX ; palette loaders clobber X (sprite slot)
        JSL ResetToLinkGraphics
        PLX
      +

      LDA.b $10 : CMP.b #$0B : BEQ .exit
        LDA.b $8A : AND.b #$40 : STA.b $7B : BEQ .no_mirror_portal
          LDA.b $20 : STA.w $1ADF
          LDA.b $21 : STA.w $1AEF
          LDA.b $22 : STA.w $1ABF
          LDA.b $23 : STA.w $1ACF
        .no_mirror_portal
        LDA.b #$23

        #SetGameModeLikeMirror:
        STA.b $11
        STZ.w $03F8
        LDA.b #$01 : STA.w $02DB
        STZ.b $B0
        STZ.b $27 : STZ.b $28
        LDA.b #$14 : STA.b $5D

    .not_on
    .exit
    RTS
  }
}

Sprite_DekuLeaf_Draw:
{
  LDA.b #$00
  BRA DekuLeaf_DrawFrame
}

Sprite_Whirlpool_Draw:
{
  LDA.w SprFrame, X : CMP.b #$03 : BCC +
    LDA.b #$00
  +
  INC A
}

; Shared 4-tile Region B draw for Deku Leaf (frame 0) and Whirlpool (frames 1-3).
; Keeps both flat water/surface sprites below Link and avoids !NbrTiles=0 OAM
; overflow by explicitly requesting $10 bytes (4 OAM slots) after clipping.
DekuLeaf_DrawFrame:
{
  PHA
  JSL Sprite_PrepOamCoord : BCC .check_viewport
    PLA
    RTS
  .check_viewport
  REP #$20
  LDA.b $00 : CLC : ADC.w #$0017 : CMP.w #$011F : BCS .clipped
  LDA.b $02 : CLC : ADC.w #$0017 : CMP.w #$00FF : BCC .draw_on_screen
  .clipped
    SEP #$20
    PLA
    RTS
  .draw_on_screen
  SEP #$20
  LDA.b #$10
  JSL OAM_AllocateFromRegionB

  PLY
  LDA.w .start_index, Y : STA.b $06

  PHX
  LDX.w .nbr_of_tiles, Y ; amount of tiles - 1
  LDY.b #$00
  .nextTile
    PHX
    TXA : CLC : ADC.b $06
    PHA
    ASL A : TAX

    REP #$20
    LDA.b $00 : CLC : ADC.w .x_offsets, X : STA ($90), Y
    AND.w #$0100 : STA.b $0E
    INY
    LDA.b $02 : CLC : ADC.w .y_offsets, X : STA ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .on_screen_y
      LDA.b #$F0 : STA ($90), Y ; Put the sprite out of the way
      STA.b $0E
    .on_screen_y

    PLX
    INY
    LDA.w .chr, X : STA ($90), Y
    INY
    LDA.w .properties, X : STA ($90), Y

    PHY
    TYA : LSR #2 : TAY
    LDA.b #$02 : ORA.b $0F : STA ($92), Y ; store size in oam buffer
    PLY : INY

    PLX : DEX : BPL .nextTile
  PLX
  RTS

  ; Frame 0: Deku Leaf; Frames 1-3: Whirlpool
  .start_index
    db $00, $04, $08, $0C
  .nbr_of_tiles
    db 3, 3, 3, 3
  .x_offsets
    dw -8,  8,  8, -8
    dw -8,  8, -8,  8
    dw  8, -8,  8, -8
    dw -8,  8, -8,  8
  .y_offsets
    dw  8,  8, -8, -8
    dw -8, -8,  8,  8
    dw -8, -8,  8,  8
    dw  8,  8, -8, -8
  .chr
    db $A0, $A2, $82, $80
    db $C4, $C6, $E4, $E6
    db $C4, $C6, $E4, $E6
    db $C4, $C6, $E4, $E6
  .properties
    db $23, $23, $23, $23
    db $29, $29, $29, $29
    db $69, $69, $69, $69
    db $A9, $A9, $A9, $A9
}
