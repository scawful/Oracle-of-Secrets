; =========================================================
; Octoboss by Zarby89
; Overworld boss: two octopus pirate brothers on DW $75 (underwater).
; Red (SprMiscF = 0) is placed on the map and runs the fight; it spawns
; the blue brother (SprMiscF = 1) as a second copy of this sprite.
; Was hooked over Kholdstare ($A2); now its own slot so D8 keeps Kholdstare.

!SPRID              = Sprite_Octoboss
!NbrTiles           = 06  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = $40 ; Number of Health the sprite have
!Damage             = 04  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 01  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 06  ; Matches the old Kholdstare slot palette
!Hitbox             = 09  ; 00 to 31, can be viewed in sprite draw tool
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
!Boss               = 01  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_Octoboss_Prep, Sprite_Octoboss_Long)

BrotherSpr = $0EB0

; Map-local positions (pixels from the area origin, 16-bit).
!OctoTriggerY       = $0190 ; fight starts when Link is above this line
!OctoBlueHomeX      = $0120
!OctoBlueHomeY      = $0120
!OctoSubmergeX      = $00C8 ; red resurfaces here to throw the reward
!OctoSubmergeY      = $0110
!OctoRewardX        = $00F8 ; reward position when re-entering after the fight
!OctoRewardY        = $0120

; Fight tuning
!OctoSurrenderTotal = $30   ; surrender when both brothers together are below this
!OctoSurrenderOne   = $10   ; ... or when either brother is below this
!OctoEnrageTotal    = $58   ; second half of the fight
!OctoLungeSpeed     = $18
!OctoRedIdleTime    = $40
!OctoBlueIdleTime   = $60   ; offset so the brothers do not attack together

; Reward (Quake until the underwater reward is decided)
!OctoRewardSprite   = $C0
!OctoRewardItemGet  = $11
!OctoRewardSram     = $7EF349
!OctoRewardGfx      = $1C

; Dialogue. $48-$4B now hold other text in the ROM (sword and shield,
; Toto Ranch sign, witch); the Octoboss lines need new message IDs.
!OctoMsgIntro       = $0048
!OctoMsgBrother     = $0049
!OctoMsgWait        = $004A
!OctoMsgSurrender   = $004B

macro Octoboss_PlaceAt(x, y)
  REP #$20
  LDA.w #<x> : STA.b $0E
  LDA.w #<y> : STA.b $0C
  SEP #$20
  JSR Octoboss_PlaceLocal
endmacro

Sprite_Octoboss_Prep:
{
  STZ.w SprAction, X
  STZ.w SprMiscD, X
  STZ.w SprMiscF, X
  RTL
}

Sprite_Octoboss_Long:
{
  PHB : PHK : PLB

  LDA.w SprMiscD, X : BNE + ; is the sprite already init
    STZ.w SprBulletproof, X

    ; Red only: after the fight the boss stays gone. If Link left without
    ; the reward, put it back on the bridge.
    LDA.w SprMiscF, X : BNE .notKilledYet
    PHX
    LDX.b $8A
    LDA.l $7EF280, X : AND.b #$40 : BEQ .notKilledYet_plx
      PLX
      LDA.l !OctoRewardSram : BNE .weHaveReward
        JSR SpawnMedallionAlt
      .weHaveReward
      STZ.w SprState, X
      BRA .SpriteIsNotActive
    .notKilledYet_plx
    PLX
    .notKilledYet

    LDA.b #15 : STA.w SprFrame, X
    LDA.b #$87 : STA.l $7EC664 : STA.l $7EC684
    LDA.b #$55 : STA.l $7EC665 : STA.l $7EC685
    INC.b $15
    INC.w SprMiscD, X ; increase it so sprite is initialized
  +

  LDA.w SprMiscF, X : BNE +
    JSR Sprite_Octoboss_Draw
    BRA ++
  +
  JSR Sprite_Octoboss_Draw2
  ++

  JSR Octoboss_KeepAlive

  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    LDA.w SprMiscF, X : BNE +
      JSR Sprite_Octoboss_Main
      BRA .SpriteIsNotActive
    +
    JSR Sprite_Octoboss_Secondary
  .SpriteIsNotActive
  PLB
  RTL
}

; The fight ends by surrender, never by death: cap any pending hit so it
; leaves at least 1 HP. Damage in $0CE2 is applied when the hit timer
; $0EF0 reaches $18; values $F9+ are special effects, not damage.
Octoboss_KeepAlive:
{
  LDA.w $0EF0, X : AND.b #$7F : BEQ .exit
    LDA.w $0CE2, X : CMP.b #$F9 : BCS .exit
      CMP.w SprHealth, X : BCC .exit
        LDA.w SprHealth, X : DEC : STA.w $0CE2, X
  .exit
  RTS
}

Sprite_Octoboss_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw WaitForPlayerToApproach ; 00
  dw Emerge ; 01
  dw EmergedShowMessage ; 02
  dw SpawnAndAwakeHisBrother ; 03
  dw WaitForBrotherEmerge ; 04
  dw SpawnPirateHats ; 05

  dw IdlePhase ; 06
  dw PickDirection ; 07
  dw Moving ; 08

  dw WaitMessageBeforeSurrender ; 09
  dw RemoveHat ; 0A
  dw Submerge ; 0B
  dw SubmergeWaitWall ; 0C
  dw EmergeWaitGiveItem ; 0D
  dw SubmergeForeverKill ; 0E


Sprite_Octoboss_Secondary:
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw WaitForPlayerToApproach ; 00
  dw Emerge ; 01
  dw WaitDialog ; 02
  dw IdlePhase ; 03
  dw PickDirection ; 04
  dw Moving ; 05

  dw IdleWait ; 06
  dw SubmergeForeverKill ; 07

  WaitForPlayerToApproach:
  {
    JSR Octoboss_GetAreaOrigin
    REP #$20
    LDA.b $20 : SEC : SBC.b $0A : CMP.w #!OctoTriggerY
    SEP #$20
    BCS .TooFar
      INC.w SprAction, X
      STZ.w SprFrame, X
      JSR SpawnSplash
    .TooFar
    RTS
  }

  Emerge:
  {
    LDA.b #$01 : STA.w $02E4 ; prevent link from moving
    LDA.w SprTimerB, X : BNE +
      LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #8 : BCC .noframereset
        INC.w SprAction, X
      .noframereset
      LDA.b #2 : STA.w SprTimerB, X
    +
    RTS
  }

  EmergedShowMessage:
  {
    %ShowUnconditionalMessage(!OctoMsgIntro)
    INC.w SprAction, X
    RTS
  }

  WaitDialog:
    RTS

  SpawnAndAwakeHisBrother:
  {
    LDA.b #!SPRID
    JSL Sprite_SpawnDynamically : BMI .retry
      TYA : STA.w BrotherSpr, X ; keep the brother id
      TXA : STA.w BrotherSpr, Y ; and the brother keeps ours
      %Octoboss_PlaceAt(!OctoBlueHomeX, !OctoBlueHomeY)
      LDA.b #$00 : STA.w SprAction, Y
      STA.w SprMiscD, Y
      STA.w SprFrame, Y
      LDA.b #$01 : STA.w SprMiscF, Y
      LDA.b #$40 : STA.w SprTimerC, X
      INC.w SprAction, X
    .retry
    RTS
  }

  WaitForBrotherEmerge:
  {
    LDA.w SprTimerC, X : BNE +
      %ShowUnconditionalMessage(!OctoMsgBrother)
      LDA #$16 : STA.w SprTimerC, X
      INC.w SprAction, X
    +
    RTS
  }

  SpawnPirateHats:
  {
    LDA.w SprTimerC, X : CMP #$14 : BNE +
      JSR SpawnBossPoof
      PHX
      LDA.w BrotherSpr, X : TAX
      JSR SpawnBossPoof
      PLX
    +

    LDY.w BrotherSpr, X
    LDA.w SprTimerC, X : CMP #$0A : BNE +
      LDA.b #10 : STA.w SprFrame, X
      LDA.b #10 : STA.w SprFrame, Y
    +

    ; Spawn Walls too
    LDA.w SprTimerC, X : BNE +

      LDA.w SprAction, Y : INC : STA.w SprAction, Y
      LDA.b #!OctoBlueIdleTime : STA.w SprTimerC, Y
      LDA.b #!OctoRedIdleTime : STA.w SprTimerC, X

      STZ.w $02E4 ; allow link to move again

      INC.w SprAction, X
      LDA.b #$00 : JSR Octoboss_DrawWall ; raise the bridge wall
    +
    RTS
  }

  IdlePhase:
  {
    LDA.w SprTimerC, X : CMP.b #$08 : BNE +
      JSL Sprite_SpawnFireball
    +
    ; Second half of the fight: one more fireball per idle
    LDA.w SprTimerC, X : CMP.b #$20 : BNE +
      JSR ReturnTotalHealth : CMP.b #!OctoEnrageTotal : BCS +
        JSL Sprite_SpawnFireball
    +
    LDA.w SprTimerC, X : BNE +
      INC.w SprAction, X
    +
    JSR Octoboss_AnimateSwim
    JSL Sprite_CheckDamageFromPlayer
    JSR Octoboss_CheckSurrender
    RTS
  }

  PickDirection:
  {
    INC.w SprAction, X
    JSR ReturnTotalHealth : CMP.b #!OctoEnrageTotal : BCS .wander
    JSL GetRandomInt : AND.b #$01 : BEQ .wander
      ; Lunge at Link, shorter swim
      LDA.b #!OctoLungeSpeed
      JSL Sprite_ApplySpeedTowardsPlayer
      JSL GetRandomInt : AND.b #$1F : CLC : ADC.b #$18 : STA.w SprTimerC, X
      RTS
    .wander
    JSL GetRandomInt : AND.b #$1F : SEC : SBC #$10 : STA.w SprXSpeed, X
    JSL GetRandomInt : AND.b #$1F : SEC : SBC #$10 : STA.w SprYSpeed, X
    JSL GetRandomInt : AND.b #$4F : CLC : ADC.b #$1F : STA.w SprTimerC, X
    RTS
  }

  ; Shared by both brothers; bounds come from Octoboss_Bounds by SprMiscF.
  Moving:
  {
    LDA.w SprTimerC, X : BNE +
      DEC.w SprAction, X
      DEC.w SprAction, X
      LDA.b #!OctoRedIdleTime
      LDY.w SprMiscF, X : BEQ .red
        LDA.b #!OctoBlueIdleTime
      .red
      STA.w SprTimerC, X
    +

    JSL Sprite_Move
    JSR Octoboss_AnimateSwim
    JSR Octoboss_KeepInPool

    JSR HandleMovingSplash
    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer
    JSR Octoboss_CheckSurrender
    RTS
  }

  WaitMessageBeforeSurrender:
  {
    ; Wait! WAIT! please!
    LDY.w BrotherSpr, X
    LDA.b #$06 : STA.w SprAction, Y ; set brother to action 6
    %SetTimerC($50) ; set timer to remove hat, surrender
    %ShowUnconditionalMessage(!OctoMsgWait)
    INC.w SprAction, X ; go to remove hat routine
    RTS
  }

  RemoveHat:
  {
    LDA.b #$01 : STA.w $02E4
    STZ.b $5D ; kill link action
    ; Use timer to remove hat like when it's spawning
    LDA.w SprTimerC, X : CMP #$34 : BNE +
      JSR SpawnBossPoof
      PHX
      LDA.w BrotherSpr, X : TAX
      JSR SpawnBossPoof
      PLX
    +

    LDY.w BrotherSpr, X
    LDA.w SprTimerC, X : CMP #$3A : BNE +
      LDA.b #9 : STA.w SprFrame, X
      LDA.b #9 : STA.w SprFrame, Y
    +

    LDA.w SprTimerC, X : BNE +
      %ShowUnconditionalMessage(!OctoMsgSurrender)
      INC.w SprAction, X ; surrender message
    +
    RTS
  }

  Submerge:
  {
    LDA.w SprTimerB, X : BNE +
      LDA.w SprFrame, X : DEC : STA.w SprFrame, X : CMP.b #01 : BCS .noframereset
      JSR SpawnSplash
      INC.w SprAction, X
      LDA.b #15 : STA.w SprFrame, X
      STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
      TXY
      %Octoboss_PlaceAt(!OctoSubmergeX, !OctoSubmergeY)
      LDA.b #$90 : STA.w SprTimerC, X
      .noframereset
      LDA.b #2 : STA.w SprTimerB, X
      +
    RTS
  }

  SubmergeWaitWall:
  {
    ; go under water to get the item - move back to original position
    LDA.w SprTimerC, X : BNE +
      STZ.w SprFrame, X
      INC.w SprAction, X
      LDA.b #$40 : STA.w SprTimerC, X
    +

    LDA.w SprTimerC, X : CMP.b #$40 : BNE +
      LDA.b #$04 : JSR Octoboss_DrawWall ; clear the bridge wall
    +
    RTS
  }

  EmergeWaitGiveItem:
  {
    ; Emerge back wait few frames, throw item in the middle moat, despawn wall
    LDA.w SprTimerB, X : BNE +
      LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #9 : BCC .noframereset
        LDA.b #$09 : STA.w SprFrame, X
      .noframereset
      LDA.b #2 : STA.w SprTimerB, X
    +

    LDA.w SprTimerC, X : BNE .noItemYet
      INC.w SprAction, X
      JSR SpawnMedallion
      LDY.w BrotherSpr, X
      LDA.b #$07 : STA.w SprAction, Y
      PHX
      LDX.b $8A
      LDA.l $7EF280, X : ORA.b #$40 : STA.l $7EF280, X ; save in HP sram
      PLX
    .noItemYet
    RTS
  }

  SubmergeForeverKill:
  {
    STZ.w $02E4 ; allow link to move
    LDA.w SprTimerB, X : BNE +
      LDA.w SprFrame, X : DEC : STA.w SprFrame, X : CMP.b #01 : BCS .noframereset
        JSR SpawnSplash
        STZ.w SprState, X
      .noframereset
      LDA.b #2 : STA.w SprTimerB, X
    +
    RTS
  }

  IdleWait:
    RTS

  ReturnTotalHealth:
  {
    LDY.w BrotherSpr, X
    LDA.w SprHealth, Y : STA.b $00
    LDA.w SprHealth, X : CLC : ADC.b $00
    RTS
  }
}

; Swim bob: frames 10-11, half a tile up on the second frame
Octoboss_AnimateSwim:
{
  LDA.w SprTimerB, X : BNE .exit
    LDA.b #$01 : STA.w SprHeight, X
    LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #12 : BCC .noframereset
      LDA.b #10 : STA.w SprFrame, X
      STZ.w SprHeight, X
    .noframereset
    LDA.b #12 : STA.w SprTimerB, X
  .exit
  RTS
}

; Red only. Carry the fight to the surrender scene.
Octoboss_CheckSurrender:
{
  LDA.w SprMiscF, X : BNE .exit
  LDA.w SprAction, X : CMP.b #$09 : BCS .exit
  JSR ReturnTotalHealth : CMP.b #!OctoSurrenderTotal : BCC .surrender
  LDA.w SprHealth, X : CMP.b #!OctoSurrenderOne : BCC .surrender
  LDY.w BrotherSpr, X
  LDA.w SprHealth, Y : CMP.b #!OctoSurrenderOne : BCS .exit
  .surrender
  STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
  LDA.b #$09 : STA.w SprAction, X ; go to wait message action
  .exit
  RTS
}

; Bounce off the pool edges. Bounds are map-local, one row per brother.
Octoboss_KeepInPool:
{
  JSR Octoboss_GetLocalPos
  LDA.w SprMiscF, X : ASL : TAY

  REP #$20 : LDA.b $0E : CMP.w .min_x, Y : SEP #$20 : BCS .check_right
    LDA.w SprXSpeed, X : BPL .check_right
      EOR.b #$FF : INC : STA.w SprXSpeed, X
  .check_right
  REP #$20 : LDA.b $0E : CMP.w .max_x, Y : SEP #$20 : BCC .check_up
    LDA.w SprXSpeed, X : BMI .check_up
      EOR.b #$FF : INC : STA.w SprXSpeed, X
  .check_up
  REP #$20 : LDA.b $0C : CMP.w .min_y, Y : SEP #$20 : BCS .check_down
    LDA.w SprYSpeed, X : BPL .check_down
      EOR.b #$FF : INC : STA.w SprYSpeed, X
  .check_down
  REP #$20 : LDA.b $0C : CMP.w .max_y, Y : SEP #$20 : BCC .exit
    LDA.w SprYSpeed, X : BMI .exit
      EOR.b #$FF : INC : STA.w SprYSpeed, X
  .exit
  RTS

  ;       red,   blue
  .min_x : dw $0080, $0118
  .max_x : dw $00D8, $0170
  .min_y : dw $0108, $0108
  .max_y : dw $0140, $0140
}

; Bridge wall: map16 tiles ($0F-$11, $07-$08) of the area.
; In: A = 0 to raise the wall, 4 to clear it.
Octoboss_DrawWall:
{
  PHX
  REP #$30
  AND.w #$00FF : TAY
  %GetTilePos($0F, $07)
  .next_tile
    PHY : PHX
    LDA.w .tiles, Y : JSL Overworld_DrawMap16_Persist
    PLX : PLY
    INX : INX
    CPX.w #(($07*$80)+($12*$02)) : BNE .same_row
      %GetTilePos($0F, $08)
      INY : INY
    .same_row
  CPX.w #(($08*$80)+($12*$02)) : BNE .next_tile
  SEP #$30
  PLX
  LDA.b #$01 : STA.b $14
  RTS

  ;       top,   bottom
  .tiles : dw $068F, $06A4 ; wall
           dw $0034, $0034 ; water
}

; Out: $08 = area origin X, $0A = area origin Y (16-bit). Keeps X and Y.
Octoboss_GetAreaOrigin:
{
  PHX
  REP #$30
  LDA.b $8A : AND.w #$00FF : ASL : TAX
  LDA.l Pool_OverworldTransitionPositionX_New, X : STA.b $08
  LDA.l Pool_OverworldTransitionPositionY_New, X : STA.b $0A
  SEP #$30
  PLX
  RTS
}

; Out: $0E = sprite X, $0C = sprite Y, map-local (16-bit).
Octoboss_GetLocalPos:
{
  JSR Octoboss_GetAreaOrigin
  LDA.w SprX, X : STA.b $0E : LDA.w SprXH, X : STA.b $0F
  LDA.w SprY, X : STA.b $0C : LDA.w SprYH, X : STA.b $0D
  REP #$20
  LDA.b $0E : SEC : SBC.b $08 : STA.b $0E
  LDA.b $0C : SEC : SBC.b $0A : STA.b $0C
  SEP #$20
  RTS
}

; In: Y = sprite slot, $0E = local X, $0C = local Y (16-bit).
Octoboss_PlaceLocal:
{
  JSR Octoboss_GetAreaOrigin
  REP #$20
  LDA.b $0E : CLC : ADC.b $08 : STA.b $0E
  LDA.b $0C : CLC : ADC.b $0A : STA.b $0C
  SEP #$20
  LDA.b $0E : STA.w SprX, Y : LDA.b $0F : STA.w SprXH, Y
  LDA.b $0C : STA.w SprY, Y : LDA.b $0D : STA.w SprYH, Y
  RTS
}

Sprite_Octoboss_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC.w SprFrame, X : TAY
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
  LDA.b $05 : ORA.w .properties, X : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00, $04, $0A, $10, $16, $1C, $20, $24, $28, $2C, $30, $34, $38, $3C, $40, $44
  .nbr_of_tiles
  db 3, 5, 5, 5, 5, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 0
  .x_offsets
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8, -8, 8
  dw -8, 8, -8, 8, -8, 8
  dw -8, 8, -8, 8, -8, 8
  dw -8, 8, -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw 0
  .y_offsets
  dw 6, 6, 16, 16
  dw 16, 16, 0, 0, 16, 16
  dw 12, 12, -4, -4, 16, 16
  dw 8, 8, -8, -8, 16, 16
  dw 4, 4, -12, -12, 16, 16
  dw 0, 0, -16, -16
  dw -2, -2, -18, -18
  dw 0, 0, -16, -16
  dw -16, -16, 0, 0
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0
  .chr
  db $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04
  db $2C, $2E, $02, $04
  db $2C, $2E, $02, $04
  db $02, $04, $24, $26
  db $20, $22, $02, $08
  db $20, $22, $00, $00
  db $28, $2A, $00, $00
  db $2C, $2E, $00, $00
  db $2C, $2E, $00, $00
  db $24, $26, $00, $00
  db $0E
  .properties
  db $37, $37, $37, $37
  db $37, $37, $37, $37, $37, $37
  db $37, $37, $37, $37, $37, $37
  db $37, $37, $37, $37, $37, $37
  db $37, $37, $37, $37, $37, $37
  db $37, $37, $37, $37
  db $37, $37, $37, $37
  db $37, $37, $37, $37
  db $37, $37, $37, $37
  db $37, $37, $37, $37
  db $37, $37, $37, $77
  db $37, $37, $37, $77
  db $37, $37, $37, $77
  db $37, $37, $37, $77
  db $37, $37, $37, $77
  db $37
  .sizes
  db $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02

}

Sprite_Octoboss_Draw2:
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
  LDA.b $05 : ORA.w .properties, X : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  ; =========================================================

  .start_index
  db $00, $04, $0A, $10, $16, $1C, $20, $24, $28, $2C, $30, $34, $38, $3C, $40, $44
  .nbr_of_tiles
  db 3, 5, 5, 5, 5, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 0
  .x_offsets
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8, -8, 8
  dw 8, -8, -8, 8, -8, 8
  dw 8, -8, -8, 8, -8, 8
  dw 8, -8, -8, 8, -8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw -8, 8, 8, -8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw 0
  .y_offsets
  dw 6, 6, 16, 16
  dw 16, 16, 0, 0, 16, 16
  dw 12, 12, -4, -4, 16, 16
  dw 8, 8, -8, -8, 16, 16
  dw 4, 4, -12, -12, 16, 16
  dw 0, 0, -16, -16
  dw -2, -2, -18, -18
  dw 0, 0, -16, -16
  dw -16, -16, 0, 0
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0
  .chr
  db $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04
  db $2C, $2E, $02, $04
  db $2C, $2E, $02, $04
  db $02, $04, $24, $26
  db $20, $22, $02, $08
  db $20, $22, $00, $00
  db $28, $2A, $00, $00
  db $2C, $2E, $00, $00
  db $2C, $2E, $00, $00
  db $24, $26, $00, $00
  db $0E
  .properties
  db $39, $39, $39, $39
  db $39, $39, $39, $39, $39, $39
  db $79, $79, $39, $39, $39, $39
  db $79, $79, $39, $39, $39, $39
  db $79, $79, $39, $39, $39, $39
  db $79, $79, $39, $39
  db $79, $79, $39, $39
  db $79, $79, $39, $39
  db $39, $39, $79, $79
  db $79, $79, $39, $39
  db $79, $79, $39, $79
  db $79, $79, $39, $79
  db $79, $79, $39, $79
  db $79, $79, $39, $79
  db $79, $79, $39, $79
  db $39
  .sizes
  db $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02
}

SpawnSplash:
{
  LDA.b #$EC ; SPRITE EC
  JSL Sprite_SpawnDynamically : BMI .exit
    JSL Sprite_SetSpawnedCoords
    LDA.b #$03 : STA.w SprState, Y
    LDA.b #$0F : STA.w SprTimerA, Y
    LDA.b #$00 : STA.w $0D80, Y
    LDA.b #$03 : STA.w SprNbrOAM,Y
    LDA.b #$28 : JSL Sound_SetSfx2PanLong
  .exit
  RTS
}

; Hat poof. Used to spawn sprite $CE, which is Twinrova now.
SpawnBossPoof:
{
  LDA.b #$0C : STA.w $012E
  JSL Sprite_SpawnPoofGarnish
  RTS
}

HandleMovingSplash:
{
  LDA.b $1A : AND.b #$0F : BNE .exit
    LDA.b #$28 : JSL Sound_SetSfx2PanLong
    PHX
    TXY
    LDX.b #$1D
    .next_slot
    LDA.l $7FF800, X : BEQ .free_slot
    DEX : BPL .next_slot
    PLX
    RTS

    .free_slot
    LDA.b #$15 ; GARNISH 15
    STA.l $7FF800, X
    STA.w $0FB4

    LDA.w SprX, Y : STA.l $7FF83C, X
    LDA.w SprXH, Y : STA.l $7FF878, X
    LDA.w SprY, Y : CLC : ADC.b #$18 : STA.l $7FF81E, X
    LDA.w SprYH, Y : ADC.b #$00 : STA.l $7FF85A, X
    LDA.b #$0F : STA.l $7FF90E, X

    PLX
  .exit
  RTS
}

; Reward thrown from the red brother onto the bridge
SpawnMedallion:
{
  LDA.b #!OctoRewardSprite
  JSL Sprite_SpawnDynamically : BMI Octoboss_SetupReward_exit
    JSL Sprite_SetSpawnedCoords
    LDA.b #$10 : STA.w SprXSpeed, Y
    LDA.b #$30 : STA.w $0F80, Y
    LDA.b #$20 ; SFX2.20
    JSL $0DBB7C ; SpriteSFX_QueueSFX2WithPan
    BRA Octoboss_SetupReward
}

; Reward left on the bridge when Link returns without it
SpawnMedallionAlt:
{
  LDA.b #!OctoRewardSprite
  JSL Sprite_SpawnDynamically : BMI Octoboss_SetupReward_exit
    %Octoboss_PlaceAt(!OctoRewardX, !OctoRewardY)
}

; In: Y = reward slot. Keeps X; Y is not kept.
Octoboss_SetupReward:
{
  PHX
  TYX
  LDA.b #!OctoRewardItemGet : STA.w SprFrame, X
  LDA.b #$83 : STA.w SprNbrOAM, X
  LDA.b #$58 : STA.w SprGfxProps, X
  AND.b #$0F : STA.w SprProps, X
  LDA.b #!OctoRewardGfx : JSL $00D4ED ; WriteTo4BPPBuffer_item_gfx
  PLX
  #Octoboss_SetupReward_exit:
  RTS
}
