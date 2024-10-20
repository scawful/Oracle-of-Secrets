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
%Set_Sprite_Properties(Sprite_IceBlock_Prep, Sprite_IceBlock_Long);


Sprite_IceBlock_Long:
{
  PHB : PHK : PLB

  LDA.w SprMiscC, X : BEQ .not_being_pushed
    STZ.w SprMiscC, X
    STZ.b $5E : STZ.b $48
  .not_being_pushed
  LDA.w $0DF0, X : BEQ .retain_momentum
    LDA.b #$01 : STA.w SprMiscC, X
    LDA.b #$84 : STA $48 
    LDA.b #$04 : STA.b $5E
  .retain_momentum

  JSR Sprite_IceBlock_Draw ; Call the draw code
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_IceBlock_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

Sprite_IceBlock_Prep:
{
  PHB : PHK : PLB
    
  ; Cache Sprite position
  LDA.w SprX, X : STA.w SprMiscD, X
  LDA.w SprY, X : STA.w SprMiscE, X
  LDA.w SprXH, X : STA.w SprMiscF, X
  LDA.w SprYH, X : STA.w SprMiscG, X

  STZ.w $0CAA, X

  PLB
  RTL
}

StatueDirection:
db $04, $06, $00, $02

StatuePressMask:
db $01, $02, $04, $08

StatueSpeed:
.x
db -16,  16 ; bleeds into next

.y
db   0,   0, -16,  16

Sprite_IceBlock_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw MovementHandler
  dw NotInContact

  ; 0x00
  MovementHandler:
  {
    %PlayAnimation(0, 0, 1)

    JSR Statue_BlockSprites

    JSL Sprite_CheckDamageFromPlayer
    BCC .no_damage
      LDA.w SprMiscD, X : STA.w SprX, X
      LDA.w SprMiscE, X : STA.w SprY, X
      LDA.w SprMiscF, X : STA.w SprXH, X
      LDA.w SprMiscG, X : STA.w SprYH, X
      STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    .no_damage

    ; JSR IceBlock_CheckForGround

    STZ.w $0642
    JSR Sprite_IceBlock_CheckForSwitch : BCC .no_switch
      STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
      LDA.b #$01 : STA.w $0642
    .no_switch

    JSL Sprite_Move ; Sprite MoveXY 
    JSL Sprite_Get_16_bit_Coords ; Get 16bit coords
    JSL Sprite_CheckTileCollision ; Check Tile collision
    JSL Sprite_CheckDamageToPlayerSameLayer
    BCC NotInContact
    JSR ApplyPush
    ; Set timer 
    LDA.b #$07 : STA.w $0DF0, X

    JSL $079291 ; Sprite_RepelDash_long

    LDA.w $0E00,X : BNE Statue_CancelHookshot
    ; JSL Sprite_DirectionToFacePlayer
    ; LDA.w StatueSpeed_x,Y
    ; STA.w SprXSpeed,X
    ; LDA.w StatueSpeed_y,Y
    ; STA.w SprYSpeed,X
    ; JSR Statue_HandleGrab
    
    LDA.w SprX, X : AND #$F0 : STA.w SprX, X
    LDA.w SprY, X : AND #$F0 : STA.w SprY, X
    RTS
    .not_in_contact
    %GotoAction(1)
    .dont_move
    RTS
  }

  Statue_CancelHookshot:
  {
    JSL $0FF540
    RTS
  }

  ; 0x01
  NotInContact:
  {
    %PlayAnimation(0, 0, 1)
    LDA.w $0DF0,X : BNE .delay_timer
    LDA.b #$0D : STA.w $0E00,X

    .delay_timer

    REP #$20
    LDA.w SprCachedX
    SEC : SBC.b $22
    CLC : ADC.w #$0010
    CMP.w #$0023 : BCS .reset_contact

    LDA.w SprCachedY
    SEC : SBC.b $20
    CLC : ADC.w #$000C
    CMP.w #$0024 : BCS .reset_contact
    SEP #$30

    JSL Sprite_DirectionToFacePlayer

    ; LDA.b $2F
    ; CMP.w StatueDirection,Y : BNE .reset_contact
    ; LDA.w $0372 : BNE .reset_contact
    ; LDA.b #$01 : STA.w $02FA
    ; LDA.b #$01 : STA.w SprFrame,X
    ; LDA.w $0376 : AND.b #$02 : BEQ .exit

    ; LDA.b $F0 : AND.w StatuePressMask,Y : BEQ .exit

    ; LDA.b $30 : ORA.b $31 : BEQ .exit

    ; TYA : EOR.b #$01 : TAY

    ; LDA.w StatueSpeed_x,Y : STA.w SprXSpeed,X

    ; LDA.w StatueSpeed_y,Y : STA.w SprYSpeed,X

    ; JMP.w Statue_HandleGrab

    .reset_contact
    SEP #$30

    LDA.w SprFrame,X : BEQ .exit
    STZ.w SprFrame,X

    STZ.b $5E
    STZ.w $0376
    STZ.w $02FA

    LDA.b $50 : AND.b #$FE : STA.b $50

    .exit
    %GotoAction(0)
    RTS
  }


  ApplyPush:
  {
    LDA $26 : CMP.b #$01 : BEQ .push_right
      CMP.b #$02 : BEQ .push_left
      CMP.b #$04 : BEQ .push_down
      CMP.b #$08 : BEQ .push_up

    .push_right
      LDA #16 : STA.w SprXSpeed,X
      LDA #00 : STA.w SprYSpeed,X
      JMP .push_done
    .push_left
      LDA #-16 : STA.w SprXSpeed,X
      LDA #00 : STA.w SprYSpeed,X
      JMP .push_done
    .push_down
      LDA #00 : STA.w SprXSpeed,X
      LDA #16 : STA.w SprYSpeed,X
      JMP .push_done
    .push_up
      LDA #00 : STA.w SprXSpeed,X
      LDA #-16 : STA.w SprYSpeed,X

    .push_done

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
  LDA.w $0E20,Y
  CMP.b #$1C ; SPRITE 1C
  BEQ .skip

  CPY.w $0FA0
  BEQ .skip

  TYA
  EOR.b $1A
  AND.b #$01
  BNE .skip

  LDA.w $0DD0,Y
  CMP.b #$09
  BCC .skip

  LDA.w SprX,Y
  STA.b $04

  LDA.w SprXH,Y
  STA.b $05

  LDA.w SprY,Y
  STA.b $06

  LDA.w SprYH,Y
  STA.b $07

  REP #$20

  LDA.w SprCachedX
  SEC
  SBC.b $04
  CLC
  ADC.w #$000C

  CMP.w #$0018
  BCS .skip

  LDA.w SprCachedY
  SEC
  SBC.b $06
  CLC
  ADC.w #$000C

  CMP.w #$0024
  BCS .skip

  SEP #$20

  LDA.b #$04
  STA.w $0EA0,Y

  PHY

  LDA.b #$20
  JSL Sprite_CheckSlopedTileCollision ; JSR Sprite_ProjectSpeedTowardsLocation

  PLY

  LDA.b $00
  STA.w $0F30,Y

  LDA.b $01
  STA.w $0F40,Y

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