; =========================================================
; Goriya Sprite Properties
; =========================================================

!SPRID              = Sprite_Goriya
!NbrTiles           = 06  ; 4 death poof + 2 body + 1 shadow (allocates 7 slots)
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 08  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
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
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_Goriya_Prep, Sprite_Goriya_Long)

GoriyaMovementSpeed   = 12
!Goriya_ChaseSpeed    = 16
!Goriya_DetectRange   = $68
!Goriya_ThrowRange    = $78
!Goriya_AlertDuration = $60
!Goriya_WaitDuration  = $48
!Goriya_ThrowCooldown = $90
!Goriya_BoomSpeed     = $20
!Goriya_BoomOutTime   = $28
!Goriya_BoomRetTime   = $38
!Goriya_CatchDist     = 12

Sprite_Goriya_Long:
{
  PHB : PHK : PLB
  ; Keep drawing the body while SpriteModule_Die ($0DD0 == 6) counts SprTimerA
  ; down from $1F to $0A (in Region A slots after SpriteDeath_DrawPoof).
  LDA.w SprState, X : CMP.b #$06 : BNE .draw
    LDA.w SprTimerA, X : CMP.b #$0A : BCC .dying
  .draw
  ; Subtype 1 is the thrown boomerang; subtype 0 and subtypes 2+ are Goriya variants.
  LDA.w SprSubtype, X : CMP.b #$01 : BEQ .boomerang_draw
    JSR Sprite_Goriya_Draw : BCS .draw_done
    JSL Sprite_DrawShadow
    BRA .draw_done
  .boomerang_draw
    JSR Sprite_Boomerang_Draw
  .draw_done
  .dying
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Goriya_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Goriya_Prep:
{
  PHB : PHK : PLB
  LDA.b #$08 : STA.w SprHealth, X

  ; Select per-instance OAM palette bits (palette << 1) in SprMiscG:
  ;   Subtypes 2..6 explicitly pick Red, Blue, Green, Sand, or Gold.
  ;   Default subtype 0 alternates by slot parity:
  ;     Desert (OW $36): Sand (Pal 6) / Red (Pal 3)
  ;     Elsewhere:       Red (Pal 3) / Blue (Pal 4; Teal in DW)
  LDA.w SprSubtype, X : CMP.b #$02 : BCC .auto_palette
    SEC : SBC.b #$02
    CMP.b #$05 : BCC +
      LDA.b #$00
    +
    TAY
    LDA.w .subtype_palettes, Y
    BRA .set_palette
  .auto_palette
  TXA : AND.b #$01 : TAY
  LDA.b $1B : BNE .default_pal
  LDA.b $8A : CMP.b #$36 : BEQ .desert_pal
  .default_pal
    LDA.w .default_palettes, Y
    BRA .set_palette
  .desert_pal
    LDA.w .desert_palettes, Y
  .set_palette
  STA.w SprMiscG, X
  PLB
  RTL

  .default_palettes
    db $06, $08                       ; Pal 3 (Red), Pal 4 (Blue/Teal)
  .desert_palettes
    db $0C, $06                       ; Pal 6 (Sand), Pal 3 (Red)
  .subtype_palettes
    db $06, $08, $0A, $0C, $02        ; Subtypes 2..6: Red, Blue, Green, Sand, Gold
}

Sprite_Goriya_Main:
{
  LDA.w SprSubtype, X : CMP.b #$01 : BNE .goriya
    JMP BoomerangAttack
  .goriya
  LDA.w SprAction, X : AND.b #$03
  JSL JumpTableLocal

  dw Goriya_WalkingUp
  dw Goriya_WalkingDown
  dw Goriya_WalkingLeft
  dw Goriya_WalkingRight

  Goriya_WalkingUp:
  Goriya_WalkingDown:
  Goriya_WalkingLeft:
  Goriya_WalkingRight:
  {
    JSR Goriya_SyncFrame
    LDA.w SprMiscB, X : CMP.b #$04 : BNE .animate
      ; Hold standing pose while winding up / waiting for boomerang return.
      LDA.w SprAction, X : ASL A : STA.w SprFrame, X
      JMP Sprite_Goriya_Move
    .animate
    LDA.w SprTimerB, X : BNE .wait_frame
      LDA.w SprFrame, X : EOR.b #$01 : STA.w SprFrame, X
      LDA.b #$0A : STA.w SprTimerB, X
    .wait_frame
    JMP Sprite_Goriya_Move
  }

  BoomerangAttack:
  {
    %PlayAnimation(0, 3, 2)

    JSL Sprite_Move
    JSL Sprite_SpawnSparkleGarnish

    JSL Sprite_CheckDamageToPlayer : BCC .no_player_hit
      LDA.w SprMiscC, X : BNE .no_player_hit
        JSR Boomerang_StartReturn
    .no_player_hit

    JSL Sprite_CheckDamageFromPlayer : BCC .no_weapon_hit
      LDA.w SprMiscC, X : BNE .no_weapon_hit
        JSR Boomerang_StartReturn
    .no_weapon_hit

    JSL Sprite_CheckTileCollision
    LDA.w SprCollision, X : BEQ .no_wall
      LDA.w SprMiscC, X : BNE .despawn
        JSR Boomerang_StartReturn
        RTS
    .no_wall

    LDA.w SprMiscC, X : BNE .returning
      LDA.w SprTimerD, X : BNE .done
        JSR Boomerang_StartReturn
      .done
      RTS

    .returning
    LDY.w SprMiscA, X
    CPY.b #$10 : BCS .despawn
    LDA.w SprState, Y : CMP.b #$09 : BNE .despawn
    LDA.w SprType, Y : CMP.b #Sprite_Goriya : BNE .despawn
    LDA.w SprSubtype, Y : CMP.b #$01 : BEQ .despawn

    LDA.w SprXH, X : CMP.w SprXH, Y : BNE .check_timer
    LDA.w SprYH, X : CMP.w SprYH, Y : BNE .check_timer
    LDA.w SprX, X : SEC : SBC.w SprX, Y : BPL + : EOR.b #$FF : INC A : +
    CMP.b #!Goriya_CatchDist : BCS .check_timer
    LDA.w SprY, X : SEC : SBC.w SprY, Y : BPL + : EOR.b #$FF : INC A : +
    CMP.b #!Goriya_CatchDist : BCS .check_timer
      ; Cut the parent throw pause short on catch.
      LDA.b #$01 : STA.w SprTimerC, Y
      BRA .despawn

    .check_timer
    LDA.w SprTimerD, X : BNE .keep_returning
    .despawn
    STZ.w SprState, X
    .keep_returning
    RTS
  }

  Boomerang_StartReturn:
  {
    LDA.b #$01 : STA.w SprMiscC, X
    LDA.b #!Goriya_BoomRetTime : STA.w SprTimerD, X
    JSL Sprite_InvertSpeed_XY
    RTS
  }
}

; Maps Sprite_DirectionToFacePlayer (0=Right, 1=Left, 2=Down, 3=Up)
; into Goriya cardinal direction (0=Up, 1=Down, 2=Left, 3=Right).
Goriya_FaceToDir:
  db $03, $02, $01, $00

; Keep SprFrame within the 2-frame pair for SprAction (0-1, 2-3, 4-5, 6-7)
; so direction changes snap immediately without moonwalking.
Goriya_SyncFrame:
{
  LDA.w SprAction, X : ASL A : STA.b $02
  LDA.w SprFrame, X : AND.b #$FE : CMP.b $02 : BEQ +
    LDA.b $02 : STA.w SprFrame, X
  +
  RTS
}

; Carry set if Link is within A pixels of this sprite on both X and Y axes.
Goriya_IsPlayerWithinRange:
{
  STA.b $04
  STZ.b $05
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  LDA.w SprY, X : STA.b $02
  LDA.w SprYH, X : STA.b $03
  REP #$20
  LDA.b $00 : SEC : SBC.b $22 : BPL + : EOR.w #$FFFF : INC A : +
  CMP.b $04 : BCS .out_of_range
  LDA.b $02 : SEC : SBC.b $20 : BPL + : EOR.w #$FFFF : INC A : +
  CMP.b $04 : BCS .out_of_range
  SEP #$20
  SEC
  RTS
  .out_of_range
  SEP #$20
  CLC
  RTS
}

; Shared by Goriya and Darknut (Sprites/Enemies/darknut.asm).
; Updates SprAction, SprMiscB, SprMiscE, and SprTimerC on tile collision.
Goriya_HandleTileCollision:
{
  JSL Sprite_CheckTileCollision
  LDA.w SprCollision, X : BEQ .no_collision
    JSL GetRandomInt : AND.b #$03
    CMP.w SprAction, X : BNE +
      EOR.b #$01
    +
    STA.w SprAction, X
    STA.w SprMiscB, X
    STA.w SprMiscE, X
    %SetTimerC(60)
  .no_collision
  RTS
}

Goriya_BoomerangAttack:
{
  LDA.b #$09 : STA.w $012E            ; SFX2.09 Boomerang fwish (not SFX3.09 Enemy Death!)
  LDA.b #Sprite_Goriya
  JSL Sprite_SpawnDynamically : BMI .no_slot
    LDA.b #$01 : STA.w SprSubtype, Y
    LDA.b #$04 : STA.w SprAction, Y
    TXA : STA.w SprMiscA, Y           ; parent Goriya slot
    LDA.w SprX, X : STA.w SprX, Y
    LDA.w SprY, X : STA.w SprY, Y
    LDA.w SprXH, X : STA.w SprXH, Y
    LDA.w SprYH, X : STA.w SprYH, Y
    LDA.w SprFloor, X : STA.w SprFloor, Y
    LDA.b #$00
    STA.w SprNbrOAM, Y                ; 1 OAM slot (4 bytes), harmful
    STA.w SprHitbox, Y
    STA.w SprMiscC, Y                 ; 0 = outward flight
    LDA.b #$40 : STA.w $0E60, Y       ; ImperviousAll
    LDA.b #$56 : STA.w SprDefl, Y     ; active + deflect projectiles/sword/arrows
    LDA.b #$01 : STA.w SprTileDie, Y  ; cannot fall in holes
    LDA.b #$FF : STA.w SprBulletproof, Y
    LDA.b #$40 : STA.w SprHealth, Y
    LDA.b #!Goriya_BoomOutTime : STA.w SprTimerD, Y
    PHX
    TYX
    LDA.b #!Goriya_BoomSpeed
    JSL Sprite_ApplySpeedTowardsPlayer
    PLX
  .no_slot
  RTS
}

Sprite_Goriya_Move:
{
  JSL Sprite_Move
  JSL Sprite_PlayerCantPassThrough
  JSL Sprite_DamageFlash_Long
  JSL Sprite_CheckDamageToPlayer
  JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
    LDA.b #!Goriya_AlertDuration : STA.w SprTimerE, X
  .no_damage
  JSL Sprite_CheckIfRecoiling
  JSR Goriya_HandleTileCollision

  ; Alert when Link enters detection range.
  LDA.b #!Goriya_DetectRange
  JSR Goriya_IsPlayerWithinRange : BCC .not_detected
    LDA.b #!Goriya_AlertDuration : STA.w SprTimerE, X
  .not_detected

  ; Hold throw/wait stance until SprTimerC expires (or boomerang catch).
  LDA.w SprMiscB, X : CMP.b #$04 : BNE .not_waiting
    LDA.w SprTimerC, X : BEQ .pick_new_dir
      JMP Goriya_Wait
  .not_waiting

  ; Throw boomerang when alerted, cooldown ready, and Link is in throw range.
  LDA.w SprTimerE, X : BEQ .check_dir_timer
  LDA.w SprTimerD, X : BNE .check_dir_timer
  LDA.b #!Goriya_ThrowRange
  JSR Goriya_IsPlayerWithinRange : BCC .check_dir_timer
    LDA.b #$04 : STA.w SprMiscB, X
    %SetTimerC(!Goriya_WaitDuration)
    %SetTimerD(!Goriya_ThrowCooldown)
    JSR Goriya_BoomerangAttack
    BRA Goriya_Wait

  .check_dir_timer
  LDA.w SprTimerC, X : BNE .apply_move

  .pick_new_dir
  LDA.w SprTimerE, X : BEQ .patrol_dir
    JSL Sprite_DirectionToFacePlayer
    LDA.w Goriya_FaceToDir, Y : STA.w SprMiscB, X
    %SetTimerC(24)
    BRA .apply_move

  .patrol_dir
  JSL GetRandomInt : AND.b #$03 : STA.w SprMiscB, X
  %SetTimerC(60)

  .apply_move
  LDA.w SprTimerE, X : BEQ +
    LDA.b #!Goriya_ChaseSpeed
    BRA .have_speed
  +
  LDA.b #GoriyaMovementSpeed
  .have_speed
  ; Preserve speeds outside $00-$03 because JumpTableLocal clobbers $00-$03.
  STA.b $08
  EOR.b #$FF : INC A : STA.b $09
  LDA.w SprMiscB, X : AND.b #$03
  STA.w SprAction, X
  STA.w SprMiscE, X
  JSL JumpTableLocal

  dw Goriya_MoveUp
  dw Goriya_MoveDown
  dw Goriya_MoveLeft
  dw Goriya_MoveRight

  Goriya_MoveUp:
  {
    LDA.b $09 : STA.w SprYSpeed, X
    STZ.w SprXSpeed, X
    JMP Goriya_SyncFrame
  }

  Goriya_MoveDown:
  {
    LDA.b $08 : STA.w SprYSpeed, X
    STZ.w SprXSpeed, X
    JMP Goriya_SyncFrame
  }

  Goriya_MoveLeft:
  {
    STZ.w SprYSpeed, X
    LDA.b $09 : STA.w SprXSpeed, X
    JMP Goriya_SyncFrame
  }

  Goriya_MoveRight:
  {
    STZ.w SprYSpeed, X
    LDA.b $08 : STA.w SprXSpeed, X
    JMP Goriya_SyncFrame
  }

  Goriya_Wait:
  {
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    JSL Sprite_DirectionToFacePlayer
    LDA.w Goriya_FaceToDir, Y
    STA.w SprAction, X
    STA.w SprMiscE, X
    JMP Goriya_SyncFrame
  }
}

; =========================================================

; 0-1 : Walking Up
; 2-3 : Walking Down
; 4-5 : Walking Left
; 6-7 : Walking Right
Sprite_Goriya_Draw:
{
  JSL Sprite_PrepOamCoord : BCC .on_screen
    SEC
    RTS
  .on_screen
  LDA.w SprState, X : CMP.b #$06 : BEQ .alloc_done
    JSL Sprite_OAM_AllocateDeferToPlayer
  .alloc_done

  LDA.w SprGfx, X : CLC : ADC.w SprFrame, X : TAY
  CPY.b #$08 : BCC +
    LDY.b #$00
  +
  LDA.w .start_index, Y : STA.b $06

  ; Combine per-instance OAM palette (SprMiscG) with damage flash cycling.
  ; Sprite_TimersAndOAM pre-shifts SprFlash during dying ($0DD0 == 6).
  LDA.w SprMiscG, X : BNE +
    LDA.b #$0C                        ; default Sand palette (Pal 6)
  +
  STA.b $08
  LDA.w SprState, X : CMP.b #$06 : BEQ .dying_flash
    LDA.w SprFlash, X : ASL A : BRA .apply_flash
  .dying_flash
    LDA.w SprFlash, X
  .apply_flash
  EOR.b $08 : AND.b #$0E : STA.b $08

  PHX
  LDX.w .nbr_of_tiles, Y              ; amount of tiles - 1
  LDY.b #$00
  .nextTile
    PHX
    TXA : CLC : ADC.b $06
    PHA
    ASL A : TAX

    REP #$20
    LDA.b $00 : CLC : ADC.w .x_offsets, X : STA ($90), Y
    AND.w #$0100 : STA.b $0E : INY
    LDA.b $02 : CLC : ADC.w .y_offsets, X : STA ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .on_screen_y
      LDA.b #$F0 : STA ($90), Y : STA.b $0E
    .on_screen_y

    PLX
    INY
    LDA.w .chr, X : STA ($90), Y : INY
    LDA.w .properties, X : ORA.b $08 : STA ($90), Y

    PHY
    TYA : LSR #2 : TAY
    LDA.b #$02 : ORA.b $0F : STA ($92), Y
    PLY : INY
    PLX : DEX : BPL .nextTile
  PLX
  CLC
  RTS

  .start_index
    db $00, $02, $04, $06, $08, $0A, $0C, $0E
  .nbr_of_tiles
    db 1, 1, 1, 1, 1, 1, 1, 1
  .x_offsets
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
  .y_offsets
    dw 0, -9
    dw 0, -9
    dw 0, -10
    dw 0, -10
    dw 0, -10
    dw 0, -9
    dw 0, -9
    dw -1, -10
  .chr
    ; Body  Head
    db $E4, $C0
    db $E4, $C0
    db $E6, $C2
    db $E6, $C2
    db $E2, $C4
    db $E0, $C4
    db $E2, $C4
    db $E0, $C4
  .properties
    ; Palette bits cleared so SprMiscG / SprFlash control the OAM palette row.
    db $21, $21
    db $61, $21
    db $21, $21
    db $61, $21
    db $21, $21
    db $21, $21
    db $61, $61
    db $61, $61
}

Sprite_Boomerang_Draw:
{
  JSL Sprite_PrepOamCoord : BCC .on_screen
    SEC
    RTS
  .on_screen
  LDA.w SprState, X : CMP.b #$06 : BEQ .alloc_done
    JSL Sprite_OAM_AllocateDeferToPlayer
  .alloc_done

  PHX
  LDA.w SprFrame, X : AND.b #$03 : TAX
  LDY.b #$00
  REP #$20
  LDA.b $00 : STA ($90), Y : AND.w #$0100 : STA.b $0E
  INY
  LDA.b $02 : STA ($90), Y
  CLC : ADC.w #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y
    LDA.b #$F0 : STA ($90), Y
    STA.b $0E
  .on_screen_y
  INY
  LDA.b #$26 : STA ($90), Y
  INY
  LDA.w .properties, X : STA ($90), Y
  LDY.b #$00
  LDA.b #$02 : ORA.b $0F : STA ($92), Y
  PLX
  CLC
  RTS

  .properties
    db $22, $A2, $E2, $62
}
