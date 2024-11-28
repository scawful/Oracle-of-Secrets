; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_VillageDog
!NbrTiles           = 08  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this VillageDog (can be 0 to 7)
!Hitbox             = 09  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 01  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 01  ; 01 = will check both layer for collision
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

%Set_Sprite_Properties(Sprite_VillageDog_Prep, Sprite_VillageDog_Long)

Sprite_VillageDog_Long:
{
  PHB : PHK : PLB
  LDA.w WORLDFLAG : BEQ .village
    JSR Sprite_EonDog_Draw
    JMP +
  .village
  JSR Sprite_VillageDog_Draw
  +
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_VillageDog_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_VillageDog_Prep:
{
  PHB : PHK : PLB
  LDA.w WORLDFLAG : BEQ .village
    LDA.b #$07 : STA.w SprAction, X
  .village
  PLB
  RTL
}

HandleTossedDog:
{
  LDA.w SprHeight, X : BEQ .on_ground
    DEC.w SprHeight, X
  .on_ground
  RTS
}

LiftOrTalk:
{
  LDA.w $02B2 : BEQ .lifting
                CMP.b #$03 : BEQ .wolf
                CMP.b #$05 : BEQ .minish
                JMP .lifting
  .wolf
  .minish
  JSR   ShowMessageIfMinish
  JMP +
  .lifting
    JSL Sprite_CheckIfLifted
    JSL ThrownSprite_TileAndSpriteInteraction_long
  +
  RTS
}

Sprite_VillageDog_Main:
{
  LDA.w SprAction, X
  JSL   UseImplicitRegIndexedLocalJumpTable

  dw Dog_Handler              ; 00
  dw Dog_LookLeftAtLink       ; 01
  dw Dog_LookRightAtLink      ; 02
  dw Dog_MoveLeftTowardsLink  ; 03
  dw Dog_MoveRightTowardsLink ; 04
  dw Dog_WagTailLeft          ; 05
  dw Dog_WagTailRight         ; 06

  dw EonDog_Handler           ; 07
  dw EonDog_Right             ; 08

  ; 0
  Dog_Handler:
  {
    %PlayAnimation(8,8,8) ; Sitting
    JSR HandleTossedDog
    LDA $0309 : AND #$03 : BNE .lifting
      LDA #$20 : STA.w SprTimerD, X
      JSL Sprite_IsToRightOfPlayer : TYA : BEQ .walk_right
        %GotoAction(1)
        JMP .lifting
      .walk_right
      %GotoAction(2)
      .lifting
      JSR LiftOrTalk
    JSL Sprite_Move
    RTS
  }

  ; 01
  Dog_LookLeftAtLink:
  {
    %PlayAnimation(9,9,8)
    JSR HandleTossedDog
    LDA.w SprTimerD, X : BNE +
      ; Load the timer for the run
      LDA.b #$60 : STA.w SprTimerD, X
      %GotoAction(3)
    +
    RTS
  }

  ; 02
  Dog_LookRightAtLink:
  {
    %PlayAnimation(10,10,8)
    JSR HandleTossedDog
    LDA.w SprTimerD, X : BNE +
      ; Load the timer for the run
      LDA.b #$60 : STA.w SprTimerD, X
      %GotoAction(4)
    +
    RTS
  }

  ; 03
  Dog_MoveLeftTowardsLink:
  {
    %PlayAnimation(2,4,6)
    JSR HandleTossedDog
    ; Check if the dog is near link, then wag the tail
    JSR CheckIfPlayerIsNearby : BCC +
      %GotoAction(5)
    +

    ; Check for collision
    JSL Sprite_CheckTileCollision
    LDA $0E70, X : BEQ .no_collision
      %GotoAction(0)
    .no_collision

    LDA.b #$0A
    JSL Sprite_ApplySpeedTowardsPlayer
    STZ $06 : STZ $07
    JSL Sprite_MoveLong

    JSR LiftOrTalk

    LDA.w SprTimerD, X : BNE +
      %GotoAction(0)
    +
    RTS
  }

  ; 04
  Dog_MoveRightTowardsLink:
  {
    %PlayAnimation(5,7,6)
    JSR HandleTossedDog
    JSR CheckIfPlayerIsNearby : BCC +
      %GotoAction(6)
    +

    ; Check for collision
    JSL Sprite_CheckTileCollision
    LDA $0E70, X : BEQ .no_collision
      %GotoAction(0)
    .no_collision

    LDA.b #$0A
    JSL Sprite_ApplySpeedTowardsPlayer
    STZ $06 : STZ $07
    JSL Sprite_MoveLong
    JSR LiftOrTalk

    LDA.w SprTimerD, X : BNE ++
      %GotoAction(0)
    ++
    RTS
  }

  ; 05
  Dog_WagTailLeft:
  {
    %PlayAnimation(0,1, 8)
    JSR LiftOrTalk
    JSR HandleTossedDog
    LDA.w SprTimerD, X : BNE +
      %GotoAction(0)
    +
    RTS
  }

  ; 06
  Dog_WagTailRight:
  {
    %PlayAnimation(11,12,8)
    JSR LiftOrTalk
    JSR HandleTossedDog
    LDA.w SprTimerD, X : BNE +
      %GotoAction(0)
    +
    RTS
  }

  EonDog_Handler:
  {
    %PlayAnimation(0,1,8)
    JSR LiftOrTalk
    JSR HandleTossedDog
    RTS
  }

  EonDog_Right:
  {
    %PlayAnimation(2,3,8)
    JSR LiftOrTalk
    JSR HandleTossedDog
    RTS
  }
}

CheckIfPlayerIsNearby:
{
  REP #$20
  LDA $22 : CLC : ADC #$0012 : CMP.w SprCachedX : BCC .out
  LDA $22 : SEC : SBC #$0012 : CMP.w SprCachedX : BCS .out
  LDA $20 : CLC : ADC #$001A : CMP.w SprCachedY : BCC .out
  LDA $20 : SEC : SBC #$001A : CMP.w SprCachedY : BCS .out
  SEP #$21
  RTS ; Return with carry set

  .out
  SEP #$20
  CLC
  RTS ; Return with carry cleared
}

ShowMessageIfMinish:
{
  LDA $02B2 : CMP.b #$05 : BNE .not_minish
    %ShowSolicitedMessage($18) : JMP .continue
  .not_minish
  %ShowSolicitedMessage($1B)
  .continue
  RTS
}

Sprite_VillageDog_Draw:
{
  JSL   Sprite_PrepOamCoord
  JSL   Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY ; Animation Frame
  LDA   .start_index,     Y : STA $06

  PHX
  LDX   .nbr_of_tiles,    Y              ; amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX                                    ; Save current Tile Index?

  TXA   : CLC : ADC $06                  ; Add Animation Index Offset

  PHA                                    ; Keep the value with animation index offset?

  ASL   A : TAX

  REP   #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC   : ADC #$0010 : CMP.w #$0100
  SEP   #$20
  BCC   .on_screen_y

  LDA.b #$F0 : STA ($90), Y              ;Put the sprite out of the way
  STA   $0E
  .on_screen_y

  PLX                                    ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : STA ($90), Y

  PHY

  TYA   : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY   : INY

  PLX   : DEX : BPL .nextTile

  PLX

  RTS


  .start_index
    db $00, $04, $08, $0C, $10, $13, $17, $1B, $1F, $20, $21, $22, $26
  .nbr_of_tiles
    db 3, 3, 3, 3, 2, 3, 3, 3, 0, 0, 0, 3, 3
  .x_offsets
    dw -4, -4, 12, 12
    dw -4, -4, 12, 12
    dw -4, -4, 4, 12
    dw -4, -4, 4, 4
    dw -4, 4, 4
    dw 4, -4, 4, -4
    dw 4, -4, 4, -4
    dw 4, -4, -4, -4
    dw 0
    dw 0
    dw 0
    dw 8, 8, 0, 0
    dw 8, 8, 0, 0
  .y_offsets
    dw -4, 4, 4, 12
    dw -4, 4, 4, 12
    dw -8, 0, 0, -8
    dw 0, -8, -8, 0
    dw 0, 0, -16
    dw 0, 0, -8, -8
    dw 0, 0, -16, -8
    dw 0, 0, 8, -8
    dw 0
    dw 0
    dw 0
    dw -4, 4, 4, 12
    dw -4, 4, 4, 12
  .chr
    db $10, $20, $22, $32
    db $10, $20, $02, $12
    db $13, $23, $24, $15
    db $26, $16, $17, $27
    db $29, $2A, $0A
    db $23, $24, $13, $14
    db $26, $27, $06, $18
    db $29, $2B, $3B, $1B
    db $2C
    db $2E
    db $2E
    db $10, $20, $22, $32
    db $10, $20, $02, $12
  .properties
    db $27, $27, $27, $27
    db $27, $27, $27, $27
    db $27, $27, $27, $27
    db $27, $27, $27, $27
    db $27, $27, $27
    db $67, $67, $67, $67
    db $67, $67, $67, $67
    db $67, $67, $67, $67
    db $27
    db $67
    db $27
    db $67, $67, $67, $67
    db $67, $67, $67, $67
  .sizes
    db $02, $02, $00, $00
    db $02, $02, $00, $00
    db $02, $02, $02, $00
    db $02, $02, $02, $02
    db $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $00
    db $02, $00, $00, $00
    db $02
    db $02
    db $02
    db $02, $02, $00, $00
    db $02, $02, $00, $00
}

Sprite_EonDog_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
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
  db $00, $01, $02, $03
  .nbr_of_tiles
  db 0, 0, 0, 0
  .x_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  .y_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  .chr
  db $C0
  db $C2
  db $C0
  db $C2
  .properties
  db $3B
  db $3B
  db $7B
  db $7B
  .sizes
  db $02
  db $02
  db $02
  db $02
}
