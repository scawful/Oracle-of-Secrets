; =========================================================
; Pushable Ice Block
; =========================================================
; A sliding puzzle block that Link can push in cardinal directions.
; The block slides until it hits a wall or lands on a switch tile.
;
; Key Mechanics:
; - Direction Locking: Once Link starts pushing, the direction is locked
;   in SprMiscA until the block stops moving (speed = 0).
; - Side Validation: Link must be on the opposite side of the block from
;   the direction he's facing. Uses Sprite_DirectionToFacePlayer to
;   determine Link's relative position and validates against $26 (facing).
; - Switch Detection: Checks center point of block against switch tiles
;   ($23, $24, $25, $3B) to stop and activate switches.
; - Grid Snapping: Block position is snapped to 8px grid when pushed.
;
; Sprite RAM Usage:
;   SprMiscA - Locked push direction ($01=R, $02=L, $04=D, $08=U)
;   SprMiscC - Push state flag (set while being actively pushed)
;   SprMiscD-G - Cached initial position for damage reset
;   SprTimerA - Push momentum timer (keeps push active for 7 frames)
;   SprTimerB - Delay timer for hookshot cancellation
; =========================================================

!SPRID              = $D5
!NbrTiles           = 02
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 01  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 09  ; 00 to 31, can be viewed in sprite draw tool
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

; =========================================================
; Main Entry Point - Called every frame
; Handles push state management and dispatches to main logic
; =========================================================
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

; =========================================================
; Initialization - Called once when sprite spawns
; Caches initial position for damage reset
; =========================================================
Sprite_IceBlock_Prep:
{
  PHB : PHK : PLB
  ; Cache Sprite position
  LDA.w SprX, X : STA.w SprMiscD, X
  LDA.w SprY, X : STA.w SprMiscE, X
  LDA.w SprXH, X : STA.w SprMiscF, X
  LDA.w SprYH, X : STA.w SprMiscG, X
  STZ.w SprDefl, X
  LDA.w SprHitbox, X : ORA.b #$09 : STA.w SprHitbox, X
  PLB
  RTL
}

; =========================================================
; Main Logic - Handles movement, collision, and push detection
; =========================================================
Sprite_IceBlock_Main:
{
  %PlayAnimation(0, 0, 1)

  JSR Statue_BlockSprites
  JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
    LDA.w SprMiscD, X : STA.w SprX, X
    LDA.w SprMiscE, X : STA.w SprY, X
    LDA.w SprMiscF, X : STA.w SprXH, X
    LDA.w SprMiscG, X : STA.w SprYH, X
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    STZ.w SprTimerA, X : STZ.w SprMiscA, X
  .no_damage

  STZ.w $0642
  JSR Sprite_IceBlock_CheckForSwitch : BCC .no_switch
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    LDA.b #$01 : STA.w $0642
  .no_switch

  JSL Sprite_Move
  JSL Sprite_Get_16_bit_Coords
  JSL Sprite_CheckTileCollision
  ; ----udlr , u = up, d = down, l = left, r = right
  LDA.w SprCollision, X : AND.b #$0F : BEQ +
    ; Hit a wall - clear direction only if we actually stop
    STZ.w SprMiscA, X
  +

  ; If link is in contact, register a push with the sprite
  ; Must be pushing from correct side for the direction
  JSL Sprite_CheckDamageToPlayerSameLayer : BCC .NotInContact
    ; Check which side Link is on and validate push direction
    JSR IceBlock_ValidatePushSide : BCC .wrong_direction

    LDA.w SprMiscA, X : BNE .check_facing
      ; No direction cached - lock to current facing
      LDA.b $26 : STA.w SprMiscA, X
      JSR Sprite_ApplyPush
      BRA .do_push
    .check_facing
    ; Direction is locked - only allow push if Link faces same direction
    LDA.b $26 : CMP.w SprMiscA, X : BNE .wrong_direction
    .do_push

    LDA.b #$07 : STA.w SprTimerA, X
    STZ.b $5E
    JSL Sprite_RepelDash
    LDA.w SprTimerB, X : BNE .CancelHookshot
      LDA.w SprX, X : AND #$F8 : STA.w SprX, X
      LDA.w SprY, X : AND #$F8 : STA.w SprY, X
      RTS
    .CancelHookshot:
    JSL Sprite_CancelHookshot
    RTS

  .wrong_direction
    ; Link is pushing from wrong side - just repel, don't move block
    JSL Sprite_RepelDash
    RTS

  .NotInContact:

  ; Not in contact - only clear direction if block has stopped moving
  LDA.w SprXSpeed, X : ORA.w SprYSpeed, X : BNE .still_moving
    STZ.w SprMiscA, X  ; Block stopped, allow new direction
  .still_moving

  LDA.w SprTimerA, X : BNE .delay_timer
    LDA.b #$0D : STA.w SprTimerB, X
  .delay_timer
  RTS
}

; =========================================================
; Apply Push - Sets block velocity based on Link's facing direction
; Only applies if cached direction matches current facing
; =========================================================
Sprite_ApplyPush:
{
  ; Only apply the push if the facing direction
  ; and pushing direction agree with each other
  LDA.w SprMiscA, X : CMP.b $26 : BEQ .push
    RTS
  .push

  LDA $26 : CMP.b #$01 : BEQ .push_right
            CMP.b #$02 : BEQ .push_left
            CMP.b #$04 : BEQ .push_down
            CMP.b #$08 : BEQ .push_up

  .push_right
    LDA #16 : STA.w SprXSpeed, X : STZ.w SprYSpeed, X
    JMP +
  .push_left
    LDA #-16 : STA.w SprXSpeed, X : STZ.w SprYSpeed, X
    JMP +
  .push_down
    LDA #16 : STA.w SprYSpeed, X : STZ.w SprXSpeed, X
    JMP +
  .push_up
    LDA #-16 : STA.w SprYSpeed, X : STZ.w SprXSpeed, X
  +
  RTS
}

; =========================================================
; Validate Push Side - Anti-cheat for push direction
; =========================================================
; Prevents players from manipulating the block by changing
; direction while in contact. Uses Sprite_DirectionToFacePlayer
; to determine Link's actual position relative to the block,
; then validates that his facing direction ($26) is appropriate.
;
; Example: If Link is standing to the RIGHT of the block,
; he must be facing LEFT ($02) to push it leftward.
;
; Returns: Carry set = valid push, Carry clear = invalid push
; Link facing ($26): $01 = right, $02 = left, $04 = down, $08 = up
; Sprite_DirectionToFacePlayer returns Y:
;   Y=0: Link is to the right of sprite  -> must face left ($02)
;   Y=1: Link is to the left of sprite   -> must face right ($01)
;   Y=2: Link is below sprite            -> must face up ($08)
;   Y=3: Link is above sprite            -> must face down ($04)
; =========================================================
IceBlock_ValidatePushSide:
{
  JSL Sprite_DirectionToFacePlayer  ; Y = Link's position relative to block
  LDA.b $26                         ; A = Link's facing direction
  CPY.b #$00 : BEQ .link_is_right
  CPY.b #$01 : BEQ .link_is_left
  CPY.b #$02 : BEQ .link_is_below
  CPY.b #$03 : BEQ .link_is_above
  BRA .invalid  ; Unknown direction

.link_is_right
  CMP.b #$02 : BEQ .valid  ; Must face left
  BRA .invalid

.link_is_left
  CMP.b #$01 : BEQ .valid  ; Must face right
  BRA .invalid

.link_is_below
  CMP.b #$08 : BEQ .valid  ; Must face up
  BRA .invalid

.link_is_above
  CMP.b #$04 : BEQ .valid  ; Must face down (fall through to invalid)

.invalid
  CLC
  RTS

.valid
  SEC
  RTS
}

; =========================================================
; Helper Routines
; =========================================================

; Check if the tile beneath the sprite is the sliding ice
; Currently unused as it doesnt play well with the hitbox choices
IceBlock_CheckForGround:
{
  LDA.w SprY, X : CLC : ADC.b #$08 : STA.b $00
  LDA.w SprYH, X : ADC.b #$00 : STA.b $01
  LDA.w SprX, X : STA.b $02
  LDA.w SprXH, X : ADC.b #$00 : STA.b $03
  LDA.w SprFloor, X
  PHY
  JSL Sprite_GetTileAttr
  PLY

  LDA.w $0FA5 : CMP.b #$0E : BNE .stop
    SEC
    RTS
  .stop
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  CLC
  RTS
}

Sprite_IceBlock_CheckForSwitch:
{
  ; Check center point of block for switch tile
  LDA.w SprY, X : CLC : ADC.b #$08 : STA.b $00
  LDA.w SprYH, X : ADC.b #$00 : STA.b $01
  LDA.w SprX, X : CLC : ADC.b #$08 : STA.b $02
  LDA.w SprXH, X : ADC.b #$00 : STA.b $03
  LDA.w SprFloor, X

  JSL Sprite_GetTileAttr

  LDA.w $0FA5
  CMP.b #$23 : BEQ .on_switch
  CMP.b #$24 : BEQ .on_switch
  CMP.b #$25 : BEQ .on_switch
  CMP.b #$3B : BEQ .on_switch

  CLC
  RTS

.on_switch
  SEC
  RTS
}

; Block other sprites from passing through this block
; Applies recoil to sprites that collide with the ice block
Statue_BlockSprites:
{
  LDY.b #$0F

  .next
  ; SPRITE 1C
  LDA.w SprType, Y : CMP.b #$1C : BEQ .skip
    CPY.w SprSlot : BEQ .skip
      TYA : EOR.b $1A : AND.b #$01 : BNE .skip
        LDA.w SprState, Y : CMP.b #$09 : BCC .skip

  LDA.w SprX, Y : STA.b $04
  LDA.w SprXH, Y : STA.b $05
  LDA.w SprY, Y : STA.b $06
  LDA.w SprYH, Y : STA.b $07

  REP #$20

  LDA.w SprCachedX 
  SEC : SBC.b $04 
  CLC : ADC.w #$000C : CMP.w #$0018 : BCS .skip

  LDA.w SprCachedY 
  SEC : SBC.b $06 
  CLC : ADC.w #$000C : CMP.w #$0024 : BCS .skip

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

; =========================================================
; Drawing - Renders the 16x16 ice block using 4 8x8 tiles
; =========================================================
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
