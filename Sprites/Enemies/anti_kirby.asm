; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = $A8 ; The sprite ID you are overwriting (HEX)
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

; =========================================================

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
    db 8, 16

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
  dw AntiKirby_Hurt
  dw AntiKirby_Suck
  dw AntiKirby_Full
  dw AntiKirby_Death

  AntiKirby_Start:
  {
      ; Check health 
      LDA SprHealth, X : CMP.b #$01 : BCS .NotDead
        %GotoAction(6)
        RTS
    .NotDead

      ; Randomly Suck
      JSL GetRandomInt : AND #$3F : BNE .not_done
        LDA #$04 : STA SprTimerA, X
        %GotoAction(4)
        RTS
    .not_done
      
      JSL Sprite_IsToRightOfPlayer 
      TYA : CMP #$01 : BNE .WalkRight

    .WalkLeft
      %GotoAction(2)
      RTS

    .WalkRight 
      %GotoAction(1)
      RTS
  }

  AntiKirby_WalkRight:
  {
      %PlayAnimation(0, 2, 10) ; Walk Right
      
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
      
      %GotoAction(0)
      RTS
  }

  AntiKirby_WalkLeft:
  {
    %PlayAnimation(3, 6, 10) ; Walk Left

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

      LDA.b $0E : CLC : ADC.b #$30 : CMP.b #$60 : BCS .dont_tongue_link
        LDA.b $0F : CLC : ADC.b #$30 : CMP.b #$60 : BCS .dont_tongue_link
          INC.w $0D80,X

          LDA.b #$1F
          JSL Sprite_ProjectSpeedTowardsPlayer
          JSL Sprite_ConvertVelocityToAngle

          LSR A
          STA.w $0DE0,X

          LDA.b #$5F
          STA.w SprTimerA, X

          RTS
      ; ---------------------------------------------------------

      .dont_tongue_link
      STZ.w $0D80,X

      LDA.b #$10
      STA.w SprTimerA, X

      RTS
  }

  AntiKirby_Full:
  {
    %PlayAnimation(11, 11, 10) ; Full

    LDA.w SprTimerA, X : BNE .lickylicky

      STZ.w $0D80,X

      LDA.b #$10
      STA.w SprTimerA, X

      STZ.w $0D90,X
      STZ.w $0DA0,X
      STZ.w $0ED0,X

      RTS

    .lickylicky
    LSR A
    LSR A
    PHA

    TAY

    LDA.w .anim,Y : STA.w $0DC0,X

    TYA

    LDY.w $0DE0,X
    PHY

    CLC : ADC.w .index_offset_x,Y
    TAY

    LDA.w .pos,Y : STA.w $0D90,X

    STA.b $04
    STZ.b $05

    BPL .positive_x

    DEC.b $05

    .positive_x
    PLY

    PLA
    CLC : ADC.w .index_offset_y,Y

    TAY
    LDA.w .pos,Y : STA.w $0DA0,X

    STA.b $06
    STZ.b $07
    STZ.b $07

    BPL .positive_y

    DEC.b $07

    .positive_y
    LDA.w $0ED0,X : BNE .exit

    REP #$20

    LDA.w $0FD8
    CLC : ADC.b $04

    SEC : SBC.b $22

    CLC : ADC.w #$000C

    CMP.w #$0018 : BCS .exit

    LDA.w $0FDA : CLC : ADC.b $06

    SEC : SBC.b $20

    CLC : ADC.w #$000C

    CMP.w #$0020 : BCS .exit

    ; ---------------------------------------------------------

    SEP #$20

    LDA.w SprTimerA, X : CMP.b #$2E : BCS .exit

    ; JSL Link_CalculateSFXPan
    ; ORA.b #$26 ; SFX2.26
    ; STA.w $012E

    JSL GetRandomInt
    AND.b #$03
    INC A
    STA.w $0ED0,X
    STA.w $0E90,X

    CMP.b #$01 : BNE .dont_steal_bomb

    LDA.l $7EF343 : BEQ .dont_steal_anything

    DEC A
    STA.l $7EF343

    RTS

    .dont_steal_anything
    SEP #$20

    STZ.w $0ED0,X

    RTS

    ; ---------------------------------------------------------

    .dont_steal_bomb
    CMP.b #$02 : BNE .dont_steal_arrow

    LDA.l $7EF377 : BEQ .dont_steal_anything

    DEC A
    STA.l $7EF377

    RTS

    ; ---------------------------------------------------------

    .dont_steal_arrow
    CMP.b #$03 : BNE .dont_steal_rupee

    REP #$20

    LDA.l $7EF360 : BEQ .dont_steal_anything

    DEC A
    STA.l $7EF360

    .exit
    SEP #$20

    RTS

    ; ---------------------------------------------------------

    .dont_steal_rupee
    LDA.l $7EF35A
    STA.w $0E30,X
    BEQ .dont_steal_anything

    CMP.b #$03
    BEQ .dont_steal_anything

    LDA.b #$00
    STA.l $7EF35A

    RTS

    .anim
    db $09, $09, $09, $09, $0A, $0A, $0A, $0A
    db $0A, $0A, $0A, $0A, $0A, $0A, $0A, $0A
    db $0A, $0A, $0A, $0A, $09, $09, $09, $09

    .pos
    db   0,   0,   0,   0,   0,   0,   0,   0
    db   0,   0,   0,   0,   0,   0,   0,   0
    db   0,   0,   0,   0,   0,   0,   0,   0

    db   0,   0,   0,   0,   0,   0,   0,   0
    db  12,  16,  24,  32,  32,  24,  16,  12
    db   0,   0,   0,   0,   0,   0,   0,   0

    db   0,   0,   0,   0,   0,   0,   0,   0
    db -12, -16, -24, -32, -32, -24, -16, -12
    db   0,   0,   0,   0,   0,   0,   0,   0

    .index_offset_x
    db $18, $18, $00, $30, $30, $30, $00, $18

    .index_offset_y
    db $00, $18, $18, $18, $00, $30, $30, $30
  }

  AntiKirby_Death:
  {
    %PlayAnimation(12, 12, 10) ; Death

    LDA.b #$06
    STA.w $0DD0,X

    LDA.b #$0A
    STA.w SprTimerA, X

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