; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_Mineswitch
!NbrTiles           = 02  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
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
!CanFall            = 01  ; 01 sprite can fall in hole, 01 = can't fall
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

%Set_Sprite_Properties(Sprite_LeverSwitch_Prep, Sprite_LeverSwitch_Long);

; =========================================================

Sprite_LeverSwitch_Long:
{
  PHB : PHK : PLB
  JSR Sprite_LeverSwitch_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_LeverSwitch_Main
  .SpriteIsNotActive
  PLB
  RTL
}

; =========================================================

Sprite_LeverSwitch_Prep:
{
  PHB : PHK : PLB

  LDA.b #$00 : STA.w SprDefl, X

  ; Get the subtype of the switch so that we can get its on/off state.
  LDA.w SprSubtype, X : TAY

  LDA.w SwitchRam, Y : STA.w SprAction, X : STA.w SprFrame, X
  LDA.b #$00 : STA.w SprTileDie, X
  STZ.w SprBulletproof, X

  PLB
  RTL
}

; =========================================================

Sprite_LeverSwitch_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw SwitchOff
  dw SwitchOn
  dw SpeedSwitchOff
  dw SpeedSwitchOn

  SwitchOff:
  {
    %PlayAnimation(0,0,4)
    LDA.w SprTimerA, X : BNE .NoDamage
      JSL Sprite_CheckDamageFromPlayer : BCC .NoDamage
        LDA #$25 : STA $012F

        ; Get the subtype of the switch so that we can get its on/off state.
        LDA.w SprSubtype, X : TAY

        ; Turn the switch on.
        LDA #$01 : STA.w SwitchRam, Y
        LDA #$10 : STA.w SprTimerA, X
        %GotoAction(1)
    .NoDamage
    RTS
  }

  SwitchOn:
  {
    %PlayAnimation(1,1,4)
    LDA.w SprTimerA, X : BNE .NoDamage
      JSL Sprite_CheckDamageFromPlayer : BCC .NoDamage
        LDA #$25 : STA $012F

        ; Get the subtype of the switch so that we can get its on/off state.
        LDA.w SprSubtype, X : TAY
        
        ; Turn the switch off.
        LDA #$00 : STA.w SwitchRam, Y
        LDA #$10 : STA.w SprTimerA, X
        %GotoAction(0)
    .NoDamage
    RTS
  }

  SpeedSwitchOff:
  {
    %PlayAnimation(0,0,4)
    JSL Sprite_CheckDamageFromPlayer : BCC .NoDamage
      LDA.b #$25 : STA $012F
      LDA.b #$01 : STA $36
      %GotoAction(3)
    .NoDamage
    RTS
  }

  SpeedSwitchOn:
  {
    %PlayAnimation(1,1,4)
    JSL Sprite_CheckDamageFromPlayer : BCC .NoDamage
      LDA #$25 : STA $012F
      STZ.w $36
      %GotoAction(2)
    .NoDamage
    RTS
  }
}

; =========================================================

Sprite_LeverSwitch_Draw:
{
    JSL Sprite_PrepOamCoord
    LDA.b #$04 : JSL Sprite_OAM_AllocateDeferToPlayer

    LDA $0DC0, X : CLC : ADC $0D90, X : TAY ;Animation Frame
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

    LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer

    PLY : INY

    PLX : DEX : BPL .nextTile

    PLX

    RTS


  .start_index
    db $00, $01
  .nbr_of_tiles
    db 0, 0
  .x_offsets
    dw 0
    dw 0
  .y_offsets
    dw 0
    dw 0
  .chr
    db $66
    db $64
  .properties
    db $37
    db $37
}
