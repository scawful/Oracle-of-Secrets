; Pushable Ice Block

!SPRID              = $D5; The sprite ID you are overwriting (HEX)
!NbrTiles           = 03 ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 01  ; 00 = Can be attack, 01 = attack will clink on it
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
!Statue             = 01  ; 01 = Sprite is statue
!DeflectProjectiles = 01  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 01  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_IceBlock_Prep, Sprite_IceBlock_Long)

Sprite_IceBlock_Long:
{
  PHB : PHK : PLB
  LDA.w SprMiscC, X : BEQ .not_being_pushed
    STZ.w SprMiscC, X
    STZ.b LinkSpeedTbl
    STZ.b $48 ; Clear push actions bitfield
  .not_being_pushed
  LDA.w SprTimerA, X : BEQ .retain_momentum
    LDA.b #$01 : STA.w SprMiscC, X
    LDA.b #$84 : STA.b $48 ; Set statue and push block actions
    LDA.b #$04 : STA.b LinkSpeedTbl ; Slipping into pit speed
  .retain_momentum

  JSR Sprite_IceBlock_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_IceBlock_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_IceBlock_Prep:
{
  PHB : PHK : PLB
  ; Cache Sprite position
  LDA.w SprX, X : STA.w SprMiscD, X
  LDA.w SprY, X : STA.w SprMiscE, X
  LDA.w SprXH, X : STA.w SprMiscF, X
  LDA.w SprYH, X : STA.w SprMiscG, X
  STZ.w SprDefl, X
  PLB
  RTL
}

Sprite_IceBlock_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable
  dw MovementHandler

  MovementHandler:
  {
    %PlayAnimation(0, 0, 1)

    JSR Statue_BlockSprites
    JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
      LDA.w SprMiscD, X : STA.w SprX, X
      LDA.w SprMiscE, X : STA.w SprY, X
      LDA.w SprMiscF, X : STA.w SprXH, X
      LDA.w SprMiscG, X : STA.w SprYH, X
      STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    .no_damage

    STZ.w $0642
    JSR Sprite_IceBlock_CheckForSwitch : BCC .no_switch
      STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
      LDA.b #$01 : STA.w $0642
    .no_switch

    JSL Sprite_Move ; Sprite MoveXY
    JSL Sprite_Get_16_bit_Coords ; Get 16bit coords
    JSL Sprite_CheckTileCollision ; Check Tile collision
    ; ----udlr , u = up, d = down, l = left, r = right
    LDA.w SprCollision, X : AND.b #$0F : BEQ +
      STZ.w SprMiscA, X
    +

    ; TODO: Update Link push collision reaction
    ; If link is in contact, register a push with the sprite
    ; Run a timer briefly, and confirm the facing direction
    ; matches the push direction (cached) and then initiate
    ; the speed changes if they agree

    JSL Sprite_CheckDamageToPlayerSameLayer : BCC .NotInContact
      LDA.w SprMiscA, X : BNE .push_cached
        LDA.b $26 : STA.w SprMiscA, X
        JSR ApplyPush
      .push_cached

      LDA.b #$07 : STA.w SprTimerA, X
      STZ.b $5E
      JSL Sprite_RepelDash
      LDA.w SprTimerB, X : BNE .CancelHookshot
        LDA.w SprX, X : AND #$F8 : STA.w SprX, X
        LDA.w SprY, X : AND #$F8 : STA.w SprY, X
        RTS
      .CancelHookshot:
      JSL $0FF540
      RTS
    .NotInContact:
    LDA.w SprTimerA, X : BNE .delay_timer
      LDA.b #$0D : STA.w SprTimerB,X
    .delay_timer
    RTS
  }

  ApplyPush:
  {
    ; Only apply the push if the facing direction
    ; and pushing direction agree with each other
    LDA $26 : CMP.b #$01 : BEQ .push_right
              CMP.b #$02 : BEQ .push_left
              CMP.b #$04 : BEQ .push_down
              CMP.b #$08 : BEQ .push_up

    .push_right
      LDA #16 : STA.w SprXSpeed, X
      STZ.w SprYSpeed, X
      JMP +
    .push_left
      LDA #-16 : STA.w SprXSpeed, X
      STZ.w SprYSpeed, X
      JMP +
    .push_down
      STZ.w SprXSpeed, X
      LDA #16 : STA.w SprYSpeed, X
      JMP +
    .push_up
      STZ.w SprXSpeed, X
      LDA #-16 : STA.w SprYSpeed, X
    +
    RTS
  }
}

; Check if the tile beneath the sprite is the sliding ice
; Currently unused as it doesnt play well with the hitbox choices
IceBlock_CheckForGround:
{
  LDA.w SprY,X : CLC : ADC.b #$08 : STA.b $00
  LDA.w SprYH,X : ADC.b #$00 : STA.b $01
  LDA.w SprX,X : STA.b $02
  LDA.w SprXH,X : ADC.b #$00 : STA.b $03
  LDA.w $0F20,X
  PHY
  JSL $06E87B ; GetTileType_long
  PLY

  LDA.w $0FA5
  CMP.b #$0E : BNE .stop
  SEC
  RTS
.stop
  STZ.w SprXSpeed,X
  STZ.w SprYSpeed,X
  CLC
  RTS
}

Sprite_IceBlock_CheckForSwitch:
{
  LDY.b #$03

  .next_tile
  LDA.w SprY,X : CLC : ADC.w .offset_y,Y : STA.b $00
  LDA.w SprYH,X : ADC.b #$00 : STA.b $01
  LDA.w SprX,X : CLC : ADC.w .offset_x,Y : STA.b $02
  LDA.w SprXH,X : ADC.b #$00 : STA.b $03
  LDA.w $0F20,X

  PHY
  JSL $06E87B ; GetTileType_long
  PLY

  LDA.w $0FA5
  CMP.w .tile_id+0 : BEQ .switch_tile
  CMP.w .tile_id+1 : BEQ .switch_tile
  CMP.w .tile_id+2 : BEQ .switch_tile
  CMP.w .tile_id+3 : BNE .fail

  .switch_tile
  DEY
  BPL .next_tile

  SEC
  RTS

  .fail
  CLC
  RTS

  .offset_x
    db   3,  12,   3,  12

  .offset_y
    db   3,   3,  12,  12

  .tile_id
    db $23, $24, $25, $3B
}

Statue_BlockSprites:
{
  LDY.b #$0F

  .next
  ; SPRITE 1C
  LDA.w $0E20, Y : CMP.b #$1C : BEQ .skip
    CPY.w $0FA0 : BEQ .skip
      TYA : EOR.b $1A : AND.b #$01 : BNE .skip
        LDA.w SprState,Y : CMP.b #$09 : BCC .skip

  LDA.w SprX, Y : STA.b $04
  LDA.w SprXH, Y : STA.b $05
  LDA.w SprY, Y : STA.b $06
  LDA.w SprYH, Y : STA.b $07

  REP #$20

  LDA.w SprCachedX : SEC : SBC.b $04 : CLC : ADC.w #$000C
  CMP.w #$0018 : BCS .skip

  LDA.w SprCachedY : SEC : SBC.b $06 : CLC : ADC.w #$000C
  CMP.w #$0024 : BCS .skip

  SEP #$20

  LDA.b #$04 : STA.w $0EA0, Y

  PHY
  LDA.b #$20
  JSL Sprite_CheckSlopedTileCollision ; JSR Sprite_ProjectSpeedTowardsLocation
  PLY

  LDA.b $00 : STA.w SprYRecoil, Y
  LDA.b $01 : STA.w SprXRecoil, Y

  .skip
  SEP #$20

  DEY
  BPL .next

  RTS
}

Sprite_IceBlock_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC.w SprFrame, X : TAY;Animation Frame
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
  dw 0, 8, 0, 8
  .y_offsets
  dw 0, 0, 8, 8
  .chr
  db $E9, $E9, $E9, $E9
  .properties
  db $24, $64, $A4, $E4
  .sizes
  db $00, $00, $00, $00
}
