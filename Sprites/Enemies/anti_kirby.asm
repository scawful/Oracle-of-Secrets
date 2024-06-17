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
  
  LDA #$00 : STA.w SprDefl, X
  LDA #$00 : STA.w SprTileDie, X
  STZ.w SprMiscB, X

  LDY $0FFF
  LDA .bump_damage, Y : STA.w SprBump, X
  LDA .health, Y : STA.w SprHealth, X
  LDA .prize_pack, Y : STA SprPrize, X

  PLB
  RTL

  .bump_damage
    db $81, $88

  .health
    db 8, 16

  .prize_pack
    db 6, 2
}

!RecoilTime = $30

Sprite_AntiKirby_Main:
{  
  JSL Sprite_IsToRightOfPlayer 
  TYA : CMP #$01 : BNE .WalkRight
  .WalkLeft
  LDA.b #$40 : STA.w SprMiscC, X
  JMP +
  .WalkRight
  STZ.w SprMiscC, X
  +

  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw AntiKirby_Main
  dw AntiKirby_Hurt
  dw AntiKirby_Suck
  dw AntiKirby_Full
  dw AntiKirby_Death

  AntiKirby_Main:
  {
    ; Check health 
    LDA SprHealth, X : CMP.b #$01 : BCS .NotDead
      %GotoAction(4)
      RTS
    .NotDead

    ; Randomly Suck
    JSL GetRandomInt : AND #$3F : BNE .not_done
      LDA #$04 : STA SprTimerA, X
      %GotoAction(2)
      RTS
    .not_done

    %PlayAnimation(0, 2, 10) ; Start
    
    JSL Sprite_DamageFlash_Long
    JSL Sprite_CheckDamageFromPlayerLong : BCC .NoDamage
      LDA #!RecoilTime : STA SprTimerA, X
      %GotoAction(1) ; Hurt
      RTS
    .NoDamage

    %DoDamageToPlayerSameLayerOnContact()
    %MoveTowardPlayer(10)
    JSL Sprite_BounceFromTileCollision
    JSL Sprite_PlayerCantPassThrough
    

    RTS
  }

  AntiKirby_Hurt:
  {
    %PlayAnimation(3, 3, 10) ; Hurt 

    JSL Sprite_DamageFlash_Long

    LDA SprTimerA, X : BNE .NotDone
      %GotoAction(0)
    .NotDone

    RTS
  }

  AntiKirby_Suck:
  {
      %PlayAnimation(4, 5, 10) ; Suck
      

      LDA.b $0E : CLC : ADC.b #$30 : CMP.b #$60 : BCS .dont_tongue_link
        LDA.b $0F : CLC : ADC.b #$30 : CMP.b #$60 : BCS .dont_tongue_link
          INC.w SprAction, X

          LDA.b #$1F
          JSL Sprite_ProjectSpeedTowardsPlayer
          JSL Sprite_ConvertVelocityToAngle

          LSR A
          STA.w SprMiscD,X

          LDA.b #$5F
          STA.w SprTimerA, X

          RTS
      ; -----------------------------------------------------

      .dont_tongue_link

      

      LDA.w SprTimerA, X : BNE + 
        STZ.w SprAction, X
      +

      RTS
  }

  AntiKirby_Full:
  {
    ; %PlayAnimation(6, 6, 10) ; Full

    LDA.w SprTimerA, X : BNE .lickylicky
      STZ.w SprAction, X

      LDA.b #$10
      STA.w SprTimerA, X
      STZ.w SprFrame, X
      STZ.w SprMiscG, X

      RTS

    .lickylicky
    LSR A
    LSR A
    PHA

    TAY
    LDA.w .anim, Y : STA.w SprGfx, X
    TYA

    LDY.w SprMiscD, X
    PHY

    CLC : ADC.w .index_offset_x, Y
    TAY

    LDA.w .pos, Y : STA.w SprFrame, X

    STA.b $04
    STZ.b $05

    BPL .positive_x

    DEC.b $05

    .positive_x
    PLY

    PLA
    CLC : ADC.w .index_offset_y, Y

    TAY
    LDA.w .pos, Y : STA.w SprMiscE, X

    STA.b $06
    STZ.b $07
    STZ.b $07

    BPL .positive_y

    DEC.b $07

    .positive_y
    LDA.w SprMiscG, X : BNE .exit

    REP #$20

    LDA.w $0FD8
    CLC : ADC.b $04
    SEC : SBC.b $22
    CLC : ADC.w #$000C : CMP.w #$0018 : BCS .exit

    LDA.w $0FDA 
    CLC : ADC.b $06
    SEC : SBC.b $20
    CLC : ADC.w #$000C : CMP.w #$0020 : BCS .exit

    ; -----------------------------------------------------

    SEP #$20

    LDA.w SprTimerA, X : CMP.b #$2E : BCS .exit

    ; JSL Link_CalculateSFXPan
    ; ORA.b #$26 ; SFX2.26
    ; STA.w $012E

    JSL GetRandomInt
    AND.b #$03
    INC A
    STA.w SprMiscG, X
    STA.w SprMiscE, X

    CMP.b #$01 : BNE .dont_steal_bomb
      LDA.l $7EF343 : BEQ .dont_steal_anything
        DEC A
        STA.l $7EF343
        RTS
      .dont_steal_anything
      SEP #$20
      STZ.w SprMiscG,X
      RTS
    .dont_steal_bomb

    CMP.b #$02 : BNE .dont_steal_arrow
      LDA.l $7EF377 : BEQ .dont_steal_anything
        DEC A
        STA.l $7EF377
        RTS
    .dont_steal_arrow

    CMP.b #$03 : BNE .dont_steal_rupee
      REP #$20
      LDA.l $7EF360 : BEQ .dont_steal_anything
        DEC A
        STA.l $7EF360
      .exit
      SEP #$20
      RTS
    ; -----------------------------------------------------

    .dont_steal_rupee
    LDA.l $7EF35A
    STA.w SprSubtype, X
    BEQ .dont_steal_anything

    CMP.b #$03
    BEQ .dont_steal_anything

    LDA.b #$00
    STA.l $7EF35A

    RTS

    .anim
    db $04, $04, $04, $04, $05, $05, $05, $05
    db $05, $05, $05, $05, $05, $05, $05, $05
    db $05, $05, $05, $05, $04, $04, $04, $04

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
    ; db $18, $18, $00, $30, $30, $30, $00, $18
    db $00, $00, $00, $00, $00, $00, $00, $00

    .index_offset_y
    ; db $00, $18, $18, $18, $00, $30, $30, $30
    db $00, $00, $00, $00, $00, $00, $00, $00
  }

  AntiKirby_Death:
  {
    %PlayAnimation(3, 3, 10) ; Death

    LDA.b #$06 : STA.w SprState, X
    LDA.b #$0A : STA.w SprTimerA, X

    STZ.w SprPrize, X

    LDA.b #$09 ; SFX2.1E
    JSL $0DBB8A ; SpriteSFX_QueueSFX3WithPan
    
    RTS
  }
}

; 7-9: Walking with hat
; 10: Hurt with hat

Sprite_AntiKirby_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA SprGfx, X : CLC : ADC SprFrame, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

  LDA.w SprMiscA, X : STA $08
  LDA.w SprMiscC, X : STA $09

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
  LDA .properties, X : ORA $08 : AND.b #$FF : ORA $09 : STA ($90), Y

  PHY 
      
  TYA : LSR #2 : TAY
      
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
      
  PLY : INY
      
  PLX : DEX : BPL .nextTile

  PLX

  RTS

  ; Anti-Kirby V2 draw

  .start_index
  db $00, $01, $02, $03, $04, $06, $08, $0A, $0C, $0E, $10
  .nbr_of_tiles
  db 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1
  .x_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0, 8
  dw 0, 8
  dw -4, 4
  dw 0, -4
  dw 0, -4
  dw 0, -4
  dw 0, -4
  .y_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, -8
  dw 0, -8
  dw 0, -8
  dw 0, -6
  .chr
  db $02
  db $00
  db $04
  db $20
  db $08, $09
  db $28, $29
  db $22, $23
  db $02, $25
  db $00, $25
  db $04, $25
  db $20, $25
  .properties
  db $37
  db $37
  db $37
  db $37
  db $37, $37
  db $37, $37
  db $37, $37
  db $37, $3B
  db $37, $3B
  db $37, $3B
  db $37, $3B
  .sizes
  db $02
  db $02
  db $02
  db $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
}
