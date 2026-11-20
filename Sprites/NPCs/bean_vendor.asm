; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_BeanVendor
!NbrTiles           = 05  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 03  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 01  ; Keep offscreen flowers alive on 64x64 maps ($00/$33)
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

!MAGIC_BEAN_OAM_HOOKS = 1

if not(defined("MAGIC_BEAN_WRAM_DEFINED"))
  MagicBean_WramStart      = $7ECC80
  MagicBean_Magic          = $7ECC80
  MagicBean_ReqMask        = $7ECC82
  MagicBean_ResidentMask   = $7ECC83
  MagicBean_PendingUpload  = $7ECC84
  MagicBean_PendingRestore = $7ECC85
  MagicBean_TrackCount     = $7ECC86
  MagicBean_BlockSlot      = $7ECC87
  MagicBean_BlockChr       = $7ECC8A
  MagicBean_BackupSheet    = $7ECC8D
  MagicBean_HoldFrames     = $7ECC90
  MagicBean_TrackMask      = $7ECC93
  MagicBean_TrackOff       = $7ECC9B
  MagicBean_TrackEnd       = $7ECCAB
  MagicBean_Occ            = $7ECCBB
  MagicBean_BackupBuf      = $7ECCC3
  MagicBean_Scratch0       = $7ECE4F
  MagicBean_Scratch1       = $7ECE50
  MagicBean_Scratch2       = $7ECE51
  MagicBean_Scratch3       = $7ECE52
  MagicBean_WramEnd        = $7ECE53
endif
MagicBean_HorseMarker   = $7E1EDE
MagicBean_HorseOffState = $7F5402
MagicBean_KorlMarker    = $7FF3E2
MagicBean_KorlDockState = $7FF3EC
!MAGIC_BEAN_MAGIC_SIG   = $424E

!MB_Magic          = $CC80
!MB_ReqMask        = $CC82
!MB_ResidentMask   = $CC83
!MB_PendingUpload  = $CC84
!MB_PendingRestore = $CC85
!MB_TrackCount     = $CC86
!MB_BlockSlot      = $CC87
!MB_BlockChr       = $CC8A
!MB_BackupSheet    = $CC8D
!MB_HoldFrames     = $CC90
!MB_TrackMask      = $CC93
!MB_TrackOff       = $CC9B
!MB_TrackEnd       = $CCAB
!MB_Occ            = $CCBB
!MB_Scratch0       = $CE4F
!MB_Scratch1       = $CE50
!MB_Scratch2       = $CE51
!MB_Scratch3       = $CE52

assert $7E0000+!MB_Magic == MagicBean_Magic
assert $7E0000+!MB_Scratch3 == MagicBean_Scratch3

%Set_Sprite_Properties(Sprite_BeanVendor_Prep, Sprite_BeanVendor_Long)

Sprite_BeanVendor_Long:
{
  PHB : PHK : PLB
    ; Subtype 2: Part00 house villager (Core/part00.asm) — strictly Room $0104
    ; so Mayor Ruul (Room $0119, Sprite 0x07 sub=2) is never hijacked.
    LDA.w SprSubtype, X : CMP.b #$02 : BNE +
      LDA.b $A0 : CMP.b #$04 : BNE +
      LDA.b $A1 : CMP.b #$01 : BNE +
      JSL HouseVillager_Main
      PLB
      RTL
    +
  LDA.w SprMiscD, X : BNE +
    JSR Sprite_BeanVendor_Draw : BCS +
      JSL Sprite_DrawShadow
  +
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    LDA.w SprSubtype, X : BEQ +
      JSR Sprite_VillageElder_Main
      JMP ++
    +
    JSR Sprite_BeanVendor_Main
    ++
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_BeanVendor_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X
  LDA.b #$40 : STA.w SprTimerA, X
  STZ.w SprMiscD, X
  STZ.w SprMiscE, X
  STZ.w SprMiscC, X

  JSR MagicBean_ReadCurrentSpotProg : BCC .not_spot
    AND.b #$3F : BEQ .unplanted
    CMP.b #$3F : BEQ .grown
      ; Planted sprout still growing ($01..$3E): action 5, sprout frame 5.
      LDA.b #$05 : STA.w SprAction, X
      STA.w SprFrame, X
      BRA .not_spot

    .unplanted
    LDA.b #$01 : STA.w SprMiscD, X
    LDA.b #$04 : STA.w SprAction, X
    BRA .not_spot

    .grown
    LDA.b #$05 : STA.w SprAction, X
    LDA.b #$04 : STA.w SprFrame, X
    JSR MagicBean_MarkBeanstalkGrown
  .not_spot
  PLB
  RTL
}

Sprite_BeanVendor_Main:
{
  %SpriteJumpTable(BeanVendor,
                   MagicBean,
                   BeanVendor_SpawnMagicBean,
                   BeanVendor_PlayerSaidNo,
                   MagicBean_FertileSoil,
                   MagicBean_RanchFlower,
                   MagicBean_DragPlayer,
                   MagicBean_Finished)

  BeanVendor:
  {
    %PlayAnimation(0,0,1)
    JSL Sprite_PlayerCantPassThrough
    JSR MagicBean_HasBottledBean : BCS .cannot_sell
    JSR MagicBean_HasUnplantedSpot : BCC .cannot_sell
      %ShowSolicitedMessage($142) : BCC .no_message
        %GotoAction(2)
      .no_message
      RTS
    .cannot_sell
    %ShowSolicitedMessage($144)
    RTS
  }

  MagicBean:
  {
    %SetFrame(1)

    LDA.w SprMiscE, X : CMP.b #$01 : BEQ .not_lifting
      LDA.w $0309 : CMP.b #$02 : BNE .not_lifting
        JSR MagicBean_ReadCurrentSpotProg : BCC .bottle_bean
        AND.b #$01 : BNE .bottle_bean
          BRA .not_lifting
        .bottle_bean
        JSR MagicBean_BottleLogic
        RTS

    .not_lifting
    JSL Sprite_CheckIfLifted
    JSL ThrownSprite_TileAndSpriteInteraction_long
    RTS
  }

  BeanVendor_SpawnMagicBean:
  {
    %PlayAnimation(0,0,1)
    LDA.w $1CE8 : BNE .player_said_no_or_not_enough_rupees
      REP #$20
      LDA.l $7EF360
      CMP.w #$0064 ; 100 rupees (matches message $142)
      SEP #$30
      BCC .player_said_no_or_not_enough_rupees
        JSR MagicBean_FindEmptyBottle : BCC .no_empty_bottle
          ; A/X index = bottle slot (0..3); preserve sprite slot X on stack
          PHX
          TAX
          REP #$20
          LDA.l $7EF360
          SEC
          SBC.w #$0064
          STA.l $7EF360
          SEP #$30
          LDA.b #$09 : STA.l $7EF35C, X
          PLX
          %ShowUnconditionalMessage($034)
          %GotoAction(0)
          RTS
        .no_empty_bottle
        %ShowUnconditionalMessage($033)
        %GotoAction(0)
        RTS
    .player_said_no_or_not_enough_rupees
    %GotoAction(3)
    RTS
  }

  BeanVendor_PlayerSaidNo:
  {
    %PlayAnimation(0,0,1)
    %ShowUnconditionalMessage($144)
    %GotoAction(0)
    RTS
  }

  MagicBean_FertileSoil:
  {
    STX.b $01
    LDY.b #$0F
    .scan_beans
      CPY.b $01 : BEQ .next_slot
      LDA.w SprState, Y : CMP.b #$09 : BNE .next_slot
      LDA.w SprType, Y  : CMP.b #Sprite_BeanVendor : BNE .next_slot
      LDA.w SprAction, Y : CMP.b #$01 : BNE .next_slot
        PHY
        PHX
        TYX
        JSL Sprite_SetupHitBox
        PLX
        JSL Sprite_SetupHitBox_Alt
        JSL CheckIfHitBoxesOverlap
        PLY
        BCC .next_slot
          LDA.b #$00 : STA.w SprState, Y
          STZ.w SprMiscD, X
          LDA.b #$01 : JSR MagicBean_OrCurrentSpotProg
          LDA.b #$05 : STA.w SprAction, X
          STA.w SprFrame, X
          LDA.b #$2D : STA.w $012F
          RTS
      .next_slot
      DEY : BPL .scan_beans
    RTS
  }

  MagicBean_RanchFlower:
  {
    JSR MagicBean_ReadCurrentSpotProg : BCS + : JMP .done : +

    AND.b #$02 : BNE .check_grown
      ; Check for overlapping active Good Bee ($B2, action=1, $0EB0/SprMiscE!=0)
      LDY.b #$0F
      .scan_bees
        LDA.w SprState, Y : CMP.b #$09 : BNE .next_bee
        LDA.w SprType, Y  : CMP.b #$B2 : BNE .next_bee
        LDA.w SprAction, Y : CMP.b #$01 : BNE .next_bee
        LDA.w SprMiscE, Y : BEQ .next_bee
          PHY
          PHX
          TYX
          JSL Sprite_SetupHitBox
          PLX
          JSL Sprite_SetupHitBox_Alt
          JSL CheckIfHitBoxesOverlap
          PLY
          BCC .next_bee
            LDA.b #$02 : JSR MagicBean_OrCurrentSpotProg
            LDA.b #$2D : STA.w $012F
            BRA .check_grown
        .next_bee
        DEY : BPL .scan_bees

    .check_grown
    JSR MagicBean_ReadCurrentSpotProg : BCS +
      JMP .done
    +
    AND.b #$3F : CMP.b #$3F : BEQ .rideable
      %PlayAnimation(5,6,16)
      RTS

    .rideable
    LDA.b #$04 : STA.w SprFrame, X
    JSR MagicBean_MarkBeanstalkGrown
    LDA.w SprTimerC, X : BNE .done
    LDA.b $4D : ORA.b $5D : BNE .done
      JSL Link_SetupHitBox
      JSL Sprite_SetupHitBox
      JSL CheckIfHitBoxesOverlap : BCC .done
        JSR MagicBean_GetSpotIndex : BCC .done
          TYA : ASL A : STY.b $00 : CLC : ADC.b $00 : TAY ; Y = spot * 3
          LDA.w MagicBean_LegTimers, Y : STA.w SprTimerC, X
          LDA.b #$1B : STA.w $012F
          STZ.w SprMiscC, X
          LDA.b #$01 : STA.w SprMiscE, X
          %GotoAction(6)
    .done
    RTS
  }

  MagicBean_DragPlayer:
  {
    LDA.b #$04 : STA.w SprFrame, X
    JSR MagicBean_GetSpotIndex : BCS +
      JMP MagicBean_ResetToHome
    +
    TYA : ASL A : STY.b $00 : CLC : ADC.b $00
    CLC : ADC.w SprMiscC, X : TAY

    LDA.w MagicBean_LegXSpeed, Y : STA.w SprXSpeed, X
    LDA.w MagicBean_LegYSpeed, Y : STA.w SprYSpeed, X
    LDA.w MagicBean_LegDragDir, Y
    PHY ; preserve leg table index across DragPlayer/camera/Sprite_Move

    TAY
    JSL InitMovement_Long
    LDA.b #$01 : STA.w $037F
    LDA.b #$02 : STA.w LinkSomaria
    LDA.b #$08 : STA.b POSZ
    STZ.b POSZH
    LDA.b #$04 : STA.w SprHeight, X

    JSL DragPlayer

    PHX
    JSL HandleIndoorCameraAndDoors
    JSL Link_CancelDash
    LDA.b $22 : SEC : SBC.b $3F : STA.b $31
    LDA.b $20 : SEC : SBC.b $3E : STA.b $30
    PLX

    JSL Sprite_Move

    PLY
    LDA.w SprTimerC, X : BNE .continue
      LDA.w SprMiscC, X : INC A : CMP.b #$03 : BCS .finish_flight
        STA.w SprMiscC, X
        INY
        LDA.w MagicBean_LegTimers, Y : STA.w SprTimerC, X
        RTS
      .finish_flight
      STZ.w SprXSpeed, X
      STZ.w SprYSpeed, X
      %GotoAction(7)
    .continue
    RTS
  }

  MagicBean_Finished:
  {
    STZ.w $037F
    STZ.w SprHeight, X
    LDA.b #$FF : STA.b POSZ : STA.b POSZH
    STZ.w LinkSomaria
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    STZ.w SprXRound, X
    STZ.w SprYRound, X

    LDA.b #$40 : JSR MagicBean_OrCurrentSpotProg
    JSR MagicBean_MarkBeanstalkGrown

    MagicBean_ResetToHome:
    JSR MagicBean_GetSpotIndex : BCC .done
      LDA.w MagicBeanSpot_HomeXLo, Y : STA.w SprX, X
      LDA.w MagicBeanSpot_HomeXHi, Y : STA.w SprXH, X
      LDA.w MagicBeanSpot_HomeYLo, Y : STA.w SprY, X
      LDA.w MagicBeanSpot_HomeYHi, Y : STA.w SprYH, X
      LDA.w SprY, X : STA.w SprCachedY+0
      LDA.w SprX, X : STA.w SprCachedX+0
      LDA.w SprYH, X : STA.w SprCachedY+1
      LDA.w SprXH, X : STA.w SprCachedX+1
    .done
    STZ.w SprMiscE, X
    STZ.w SprMiscC, X
    LDA.b #$20 : STA.w SprTimerC, X
    LDA.b #$04 : STA.w SprFrame, X
    %GotoAction(5)
    RTS
  }
}

; =========================================================
; Magic Bean spot tables & shared helpers
; =========================================================

incsrc "Data/overworld/magic_bean_spots_table.asm"

MagicBean_GetSpotIndex:
{
  LDA.b $1B : BNE .not_spot
  LDY.b #!MagicBean_MaxSpotIndex
  .loop
    LDA.b $8A : CMP.w MagicBeanSpot_Screens, Y : BEQ .found
    DEY : BPL .loop
  .not_spot
  CLC
  RTS
  .found
  SEC
  RTS
}

MagicBean_ReadSpotProgAtY:
{
  PHX
  LDA.w MagicBeanSpot_SramLow, Y : TAX
  LDA.l $7EF300, X
  PLX
  RTS
}

MagicBean_OrSpotProgAtY:
{
  STA.b $00
  PHX
  LDA.w MagicBeanSpot_SramLow, Y : TAX
  LDA.l $7EF300, X : ORA.b $00 : STA.l $7EF300, X
  PLX
  RTS
}

MagicBean_ReadCurrentSpotProg:
{
  JSR MagicBean_GetSpotIndex : BCC .none
    JSR MagicBean_ReadSpotProgAtY
    SEC
    RTS
  .none
  LDA.b #$00
  CLC
  RTS
}

MagicBean_OrCurrentSpotProg:
{
  PHA
  JSR MagicBean_GetSpotIndex : BCC .none
    PLA
    JSR MagicBean_OrSpotProgAtY
    SEC
    RTS
  .none
  PLA
  CLC
  RTS
}

MagicBean_MarkBeanstalkGrown:
{
  LDA.l SideQuestProg2 : ORA.b #!SideQuest2_BeanstalkGrown : STA.l SideQuestProg2
  RTS
}

MagicBean_HasBottledBean:
{
  PHX
  LDX.b #$03
  .loop
    LDA.l $7EF35C, X : CMP.b #$09 : BEQ .yes
    DEX : BPL .loop
  PLX
  CLC
  RTS
  .yes
  PLX
  SEC
  RTS
}

; Returns Carry Set and bottle index (0..3) in A when an empty bottle ($02) exists.
MagicBean_FindEmptyBottle:
{
  PHX
  LDX.b #$00
  .loop
    LDA.l $7EF35C, X : CMP.b #$02 : BEQ .found
    INX : CPX.b #$04 : BCC .loop
  PLX
  CLC
  RTS
  .found
  TXA
  PLX
  SEC
  RTS
}

MagicBean_HasUnplantedSpot:
{
  LDY.b #!MagicBean_MaxSpotIndex
  .loop
    JSR MagicBean_ReadSpotProgAtY
    AND.b #$01 : BEQ .found
    DEY : BPL .loop
  CLC
  RTS
  .found
  SEC
  RTS
}

MagicBean_WaterCurrentSpot_Long:
{
  PHB : PHK : PLB
  PHX : PHY
  JSR MagicBean_ReadCurrentSpotProg : BCC .done
    AND.b #$05 : CMP.b #$01 : BNE .done ; Needs planted ($01) and unwatered ($04==0)
      LDA.b #$04 : JSR MagicBean_OrSpotProgAtY
      LDA.b #$2D : STA.w $012F
  .done
  PLY : PLX
  PLB
  RTL
}

MagicBean_AdvanceDailyGrowth_Long:
{
  PHB : PHK : PLB
  PHX : PHY
  STZ.b $02
  LDY.b #!MagicBean_MaxSpotIndex
  .loop
    JSR MagicBean_ReadSpotProgAtY
    CMP.b #$7F : BEQ .next
    AND.b #$01 : BEQ .next
      JSR MagicBean_ReadSpotProgAtY
      AND.b #$08 : BNE .not_first
        LDA.b #$08 : BRA .apply
      .not_first
      JSR MagicBean_ReadSpotProgAtY
      AND.b #$10 : BNE .not_second
        LDA.b #$10 : BRA .apply
      .not_second
      JSR MagicBean_ReadSpotProgAtY
      AND.b #$20 : BNE .next
        LDA.b #$20
      .apply
      JSR MagicBean_OrSpotProgAtY
      INC.b $02
    .next
    DEY : BPL .loop
  LDA.b $02 : BEQ .no_sfx
    LDA.b #$2D : STA.w $012F
  .no_sfx
  PLY : PLX
  PLB
  RTL
}

InitMovement_Long:
{
  LDA.b $22 : STA.b $3F
  LDA.b $23 : STA.b $41
  LDA.b $20 : STA.b $3E
  LDA.b $21 : STA.b $40
  RTL
}

ReleaseMagicBean:
{
  ; X is the bottle ID
  PHB : PHK : PLB
  JSR MagicBean_ReadCurrentSpotProg : BCC .not_a_spot
    AND.b #$01 : BNE .not_a_spot
      LDA.b #$07
      JSL Sprite_SpawnDynamically : BMI .not_a_spot
        LDA.b $20 : STA.w SprY, Y
        LDA.b $21 : STA.w SprYH, Y
        LDA.b $22 : STA.w SprX, Y
        LDA.b $23 : STA.w SprXH, Y
        LDA.b #$01 : STA.w SprAction, Y
        STA.w SprFrame, Y
        LDA.b #$00 : STA.w SprMiscD, Y : STA.w SprMiscE, Y : STA.w SprMiscF, Y
        LDA.b #$02 : STA.l $7EF35C, X
        PHX : PHY
        JSL RebuildHUD_long
        PLY : PLX
        PLB
        RTL
  .not_a_spot
  %ShowUnconditionalMessage($030)
  PLB
  RTL
}

MagicBean_BottleLogic:
{
  JSR MagicBean_FindEmptyBottle : BCS .bottle_available
    %ShowUnconditionalMessage($033)
    RTS

  .bottle_available
  PHX
  TAX
  LDA.b #$09 : STA.l $7EF35C, X
  PHX : PHY
  JSL RebuildHUD_long
  PLY : PLX
  PLX
  %ShowUnconditionalMessage($034)
  LDA.b #$01 : STA.w SprMiscE, X
  STZ.w SprState, X
  RTS
}

; =========================================================

Sprite_BeanVendor_Draw:
{
  JSL Sprite_PrepOamCoord
  ; Skip offscreen OAM allocation/drawing when !Persist = 01 holds a flower off-camera.
  REP #$20
  LDA.b $00 : CLC : ADC.w #$0040 : CMP.w #$0170 : BCS .offscreen
  LDA.b $02 : CLC : ADC.w #$0040 : CMP.w #$0170 : BCC .onscreen
  .offscreen
  SEP #$20
  SEC
  RTS
  .onscreen
  SEP #$20
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  JSL MagicBean_TryDrawNonRanch_Long
  BMI .native_draw
  RTS
  .native_draw
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

  CLC
  RTS

  .start_index
  db $00, $04, $05, $0B, $11, $13, $15
  .nbr_of_tiles
  db 3, 0, 5, 5, 3, 1, 1
  .x_offsets
  dw -4, 4, 4, -4
  dw 0
  dw -4, -4, 4, 4, -4, -4
  dw -4, -4, 4, 4, -4, -4
  dw -8, 8, -8, 8 ; Flower
  dw 0, 8
  dw 0, 8
  .y_offsets
  dw 4, 4, -4, -4
  dw 0
  dw 4, -4, 4, -4, 8, 16
  dw -4, 4, 4, -4, 8, 16
  dw 0, 0, -16, -16 ; Flower
  dw 4, 4
  dw 4, 4
  .chr
  db $A8, $A9, $99, $98
  db $A6
  db $9B, $8B, $9B, $8B, $BB, $BC
  db $8B, $8D, $8D, $8B, $BB, $BC
  db $A8, $A8, $A4, $A4 ; Flower
  db $C8, $C9
  db $CA, $C8
  .properties
  db $3B, $3B, $3B, $3B
  db $3B
  db $3B, $3B, $7B, $7B, $3B, $3B
  db $3B, $3B, $7B, $7B, $3B, $3B
  db $3B, $7B, $3B, $7B ; Flower
  db $32, $72
  db $32, $72
  .sizes
  db $02, $02, $02, $02
  db $02
  db $02, $02, $02, $02, $00, $00
  db $02, $02, $02, $02, $00, $00
  db $02, $02, $02, $02 ; Flower
  db $00, $00
  db $00, $00
}

; =========================================================
; Non-Ranch Flower & Released Bean Page 1 OAM/VRAM Cache
; Code & tables in Bank $3A ($3AB000-$3AB7FF, before Core/part00 $3AB800).
; Raw 384B SP1 4bpp tiles in Bank $59 ($59E000-$59E17F, after Korok $59C000-$59DFFF).
; =========================================================
pushpc
org $59E000

; Block k = 0 (FlowerTop $A4), 1 (FlowerBot $A8), 2 (Bean $A6).
; Each 128B block stores 64B top tile pair + 64B bottom tile pair,
; palette-remapped from Ranch 0xBD SP5 {0,1,2,3,4,5,6,7} -> SP1 {0,1,6,7,6,5,4,3}.
MagicBean_TilePayload:
MagicBean_FlowerTopGfx:
  db $00, $00, $00, $00, $01, $00, $0F, $00, $0E, $06, $0E, $06, $10, $00, $EE, $00
  db $00, $00, $00, $00, $01, $00, $0F, $00, $09, $00, $09, $00, $1F, $00, $F1, $00
  db $0F, $00, $30, $00, $C3, $03, $E3, $0B, $F3, $03, $F5, $05, $A0, $AE, $40, $5B
  db $0F, $00, $3F, $00, $FC, $00, $1C, $00, $0C, $00, $0F, $00, $FF, $00, $FF, $00
  db $9E, $10, $9E, $10, $D8, $18, $4F, $0F, $5F, $1F, $7C, $3D, $FE, $30, $9F, $10
  db $E1, $00, $E1, $00, $E7, $00, $71, $00, $63, $00, $43, $00, $C1, $00, $E0, $00
  db $29, $EF, $04, $D4, $42, $EE, $05, $5F, $10, $9F, $99, $5E, $00, $BB, $15, $6D
  db $FF, $00, $FF, $00, $FF, $00, $FF, $00, $FF, $00, $7E, $00, $FF, $00, $EF, $00

MagicBean_FlowerBotGfx:
  db $8F, $00, $CE, $41, $5E, $1E, $7E, $7E, $7F, $7C, $FB, $78, $E3, $60, $80, $00
  db $F0, $00, $B1, $00, $61, $00, $01, $00, $00, $00, $84, $00, $9C, $00, $FF, $00
  db $00, $FC, $30, $5A, $00, $ED, $05, $BF, $88, $10, $80, $00, $E3, $60, $7F, $7C
  db $FF, $00, $DF, $00, $FF, $00, $FF, $00, $77, $00, $7F, $00, $1C, $00, $80, $00
  db $E0, $00, $10, $00, $1F, $0F, $1F, $00, $00, $00, $00, $00, $00, $00, $00, $00
  db $FF, $00, $1F, $00, $10, $00, $1F, $00, $00, $00, $00, $00, $00, $00, $00, $00
  db $73, $70, $00, $00, $C0, $C0, $E0, $60, $FB, $7A, $7E, $38, $38, $00, $00, $00
  db $8C, $00, $FF, $00, $3F, $00, $9F, $00, $85, $00, $46, $00, $38, $00, $00, $00

MagicBean_BeanGfx:
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $01, $00
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $01, $00
  db $06, $00, $09, $04, $0A, $00, $16, $04, $27, $0A, $53, $1E, $9E, $1C, $3E, $1C
  db $06, $00, $0F, $00, $0E, $00, $1A, $00, $39, $00, $6D, $00, $E2, $00, $D2, $00
  db $06, $00, $18, $00, $60, $00, $C3, $47, $75, $33, $3F, $0F, $0F, $00, $00, $00
  db $07, $00, $1F, $00, $7F, $00, $BE, $00, $4A, $00, $30, $00, $0F, $00, $00, $00
  db $6C, $58, $FC, $78, $38, $F0, $F0, $E0, $E0, $C0, $C0, $00, $00, $00, $00, $00
  db $94, $00, $44, $00, $C8, $00, $10, $00, $20, $00, $C0, $00, $00, $00, $00, $00
MagicBean_TilePayloadEnd:
assert pc() <= $59E200, "Magic Bean SP1 raw 4bpp payload exceeded Bank $59 slice"

org $3AB000

MagicBean_CodeStart:

MagicBean_BitMask:
  db $01, $02, $04, $08, $10, $20, $40, $80

MagicBean_InvBitMask:
  db $FE, $FD, $FB

; Row allocation preference: Sheet 2 (4,5), Sheet 3 non-KoRL (7), Sheet 1 (2,3),
; Sheet 0 non-Horse (1), KoRL row (6), Epona row (0).
MagicBean_RowOrder:
  db $04, $05, $07, $02, $03, $01, $06, $00

MagicBean_BackupOffTable:
  dw $0000, $0084, $0108

MagicBean_PayloadAddrTable:
  dw MagicBean_FlowerTopGfx, MagicBean_FlowerBotGfx, MagicBean_BeanGfx

; Tile layout: index 0 = Released Bean (1 tile), indices 1..4 = Flower (4 tiles)
MagicBean_TileDx:
  dw 0, 8, -8, 8, -8
MagicBean_TileDy:
  dw 0, -16, -16, 0, 0
MagicBean_TileBlk:
  db 2, 0, 0, 1, 1
MagicBean_TileProp:
  db $33, $73, $33, $73, $33

; Assumes M=8, DBR=$7E (safe under X=8 or X=16). Preserves X/Y.
MagicBean_InitWram_Near:
{
  LDA.b #$00
  STA.w !MB_ReqMask
  STA.w !MB_ResidentMask
  STA.w !MB_PendingUpload
  STA.w !MB_PendingRestore
  STA.w !MB_TrackCount
  STA.w !MB_HoldFrames
  STA.w !MB_HoldFrames+1
  STA.w !MB_HoldFrames+2
  LDA.b #$FF
  STA.w !MB_BackupSheet
  STA.w !MB_BackupSheet+1
  STA.w !MB_BackupSheet+2
  REP #$20
  LDA.w #!MAGIC_BEAN_MAGIC_SIG
  STA.w !MB_Magic
  SEP #$20
  RTS
}

; Called from Sprite_BeanVendor_Draw with A = Y = frame, X = sprite slot, M=8, X=8.
; Out: A=$FF (N=1), Y preserved -> fall back to native draw.
;      A=$00 (N=0), C=1 -> hidden awaiting VRAM (skip shadow); C=0 -> drawn (draw shadow).
MagicBean_TryDrawNonRanch_Long:
{
  CMP.b #$01 : BEQ .maybe_non_ranch
  CMP.b #$04 : BEQ .maybe_non_ranch
    LDA.b #$FF
    RTL
  .maybe_non_ranch
  PHA
  LDA.b $1B : BNE .go_non_ranch
  LDA.l $7EC2FE : CMP.b #$4A : BNE .go_non_ranch
    PLA
    LDA.b #$FF
    RTL

  .go_non_ranch
  PLA
  PHB : PHX : PHY
  TAX
  LDA.b #$7E : PHA : PLB

  REP #$20
  LDA.w !MB_Magic : CMP.w #!MAGIC_BEAN_MAGIC_SIG
  SEP #$20
  BEQ +
    JSR MagicBean_InitWram_Near
  +

  CPX.b #$04 : BEQ .setup_flower
    LDA.b #$04 : STA.b $06 : STA.b $07
    STZ.b $08
    STZ.b $09
    STZ.b $0A
    BRA .track
  .setup_flower
    LDA.b #$03 : STA.b $06
    LDA.b #$10 : STA.b $07 : STZ.b $08
    LDA.b #$01 : STA.b $09
    LDA.b #$04 : STA.b $0A

  .track
  LDA.w !MB_ReqMask : ORA.b $06 : STA.w !MB_ReqMask

  REP #$20
  LDA.b $90 : SEC : SBC.w #$0800
  CMP.w #$0200 : BCS .skip_track
  STA.b $0E
  SEP #$20
  LDA.w !MB_TrackCount : CMP.b #$08 : BCS .check_resident
    TAX
    LDA.b $06 : STA.w !MB_TrackMask, X
    TXA : ASL A : TAX
    REP #$20
    LDA.b $0E : STA.w !MB_TrackOff, X
    CLC : ADC.b $07 : STA.w !MB_TrackEnd, X
    SEP #$20
    INC.w !MB_TrackCount
    BRA .check_resident
  .skip_track
  SEP #$20

  .check_resident
  LDA.w !MB_ResidentMask : AND.b $06 : CMP.b $06 : BEQ .emit_resident

  ; Wait until required Page 1 VRAM blocks finish NMI upload so no garbage flashes.
  LDX.b $09
  LDY.b #$00
  .hide_loop
    INY
    LDA.b #$F0 : STA ($90), Y
    PHY : TYA : LSR #2 : TAY : LDA.b #$02 : STA ($92), Y : PLY
    INY #3
    CPX.b $0A : BCS .hide_done
    INX
    BRA .hide_loop
  .hide_done
  PLY : PLX : PLB
  LDA.b #$00
  SEC
  RTL

  .emit_resident
  LDX.b $09
  LDY.b #$00
  .draw_loop
    PHX
    TXA : ASL A : TAX
    REP #$20
    LDA.b $00 : CLC : ADC.l MagicBean_TileDx, X : STA ($90), Y
    AND.w #$0100 : STA.b $0E
    INY
    LDA.b $02 : CLC : ADC.l MagicBean_TileDy, X : STA ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .on_screen_y
      LDA.b #$F0 : STA ($90), Y
      STA.b $0E
    .on_screen_y
    PLX
    INY
    PHX
    LDA.l MagicBean_TileBlk, X : TAX
    LDA.w !MB_BlockChr, X : STA ($90), Y
    PLX
    INY
    LDA.l MagicBean_TileProp, X : STA ($90), Y
    PHY
    TYA : LSR #2 : TAY
    LDA.b #$02 : ORA.b $0F : STA ($92), Y
    PLY
    INY
    CPX.b $0A : BCS .draw_done
    INX
    BRA .draw_loop

  .draw_done
  PLY : PLX : PLB
  LDA.b #$00
  CLC
  RTL
}

; Clears tracked Flower/Bean OAM entries matching A bitmask immediately before NMI.
; In: A = block mask ($01/$02/$04/$FF), M=8, DBR=$7E. Preserves X, Y and X-width.
MagicBean_HideTrackedMask_Near:
{
  STA.w !MB_Scratch0
  LDA.w !MB_TrackCount : BEQ .done
  PHP : REP #$10 : PHX : PHY
  LDY.w #$0000
  .h_loop
    LDA.w !MB_TrackMask, Y : AND.w !MB_Scratch0 : BEQ .h_next
      REP #$20
      TYA : ASL A : TAX
      LDA.w !MB_TrackEnd, X : STA.w !MB_Scratch1
      LDA.w !MB_TrackOff, X : TAX
      .slot_loop
        TXA : CMP.w !MB_Scratch1 : BCS .slot_done
        SEP #$20
        LDA.b #$F0 : STA.w $0801, X
        REP #$20
        INX #4
        BRA .slot_loop
      .slot_done
      SEP #$20
    .h_next
    INY
    TYA : CMP.w !MB_TrackCount : BCC .h_loop
  PLY : PLX : PLP
  .done
  RTS
}

; In: A = col (0..7), M=8, X=8. Out: A = BitMask[c]. Preserves X, Y.
MagicBean_GetBitMask_Near:
{
  PHX
  AND.b #$07 : TAX
  LDA.l MagicBean_BitMask, X
  PLX
  RTS
}

; In: A = row (0..7), !MB_Scratch3 = bitmask, M=8, X=8, DBR=$7E. Preserves X, Y.
MagicBean_AddOccBit_Near:
{
  PHX
  AND.b #$07 : TAX
  LDA.w !MB_Occ, X : ORA.w !MB_Scratch3 : STA.w !MB_Occ, X
  PLX
  RTS
}

; In: X = k (0..2), M=8, X=8. Out: A = $7EC2FC+BlockSlot[k]. Preserves X.
MagicBean_ReadSlotSheet_Near:
{
  PHX
  LDA.l MagicBean_BlockSlot, X : AND.b #$03 : TAX
  LDA.l $7EC2FC, X
  PLX
  RTS
}

; Moves active block k from Resident -> PendingRestore (hiding tracked OAM), clears PendingUpload & HoldFrames.
; In: X = k (0..2), M=8, X=8, DBR=$7E. Preserves X.
MagicBean_ReleaseBlock_Near:
{
  LDA.l MagicBean_InvBitMask, X : AND.w !MB_PendingUpload : STA.w !MB_PendingUpload
  LDA.w !MB_ResidentMask : AND.l MagicBean_BitMask, X : BEQ .clr
    LDA.l MagicBean_BitMask, X : JSR MagicBean_HideTrackedMask_Near
    LDA.l MagicBean_InvBitMask, X : AND.w !MB_ResidentMask : STA.w !MB_ResidentMask
    LDA.l MagicBean_BitMask, X : ORA.w !MB_PendingRestore : STA.w !MB_PendingRestore
  .clr
  LDA.b #$00 : STA.w !MB_HoldFrames, X
  RTS
}

MagicBean_MainRoutingFrameEnd_Long:
{
  JSL $0080B5 ; Module_MainRouting
  JML MagicBean_FrameEndScan_Long
}

; Called at end of main frame routing (after all sprite OAM writes, before NMI).
; Preserves registers, widths, and DBR.
MagicBean_FrameEndScan_Long:
{
  PHP : PHB
  REP #$30 : PHA : PHX : PHY
  SEP #$30 ; M=8, X=8
  LDA.b #$7E : PHA : PLB

  REP #$20
  LDA.w !MB_Magic : CMP.w #!MAGIC_BEAN_MAGIC_SIG
  SEP #$20
  BEQ +
    JSR MagicBean_InitWram_Near
    JMP .exit
  +

  LDA.w !MB_ReqMask
  ORA.w !MB_ResidentMask
  ORA.w !MB_PendingUpload
  ORA.w !MB_PendingRestore
  BNE +
    JMP .exit
  +

  LDA.w $0010 : CMP.b #$0E : BNE .not_overlay
    LDA.w $0011
    CMP.b #$01 : BEQ .safe_overlay
    CMP.b #$02 : BEQ .safe_overlay
    CMP.b #$04 : BEQ .safe_overlay
    CMP.b #$08 : BEQ .safe_overlay
    CMP.b #$09 : BEQ .safe_overlay
    CMP.b #$0B : BEQ .safe_overlay
    CMP.b #$07 : BEQ .check_0200
    CMP.b #$0A : BEQ .check_0200
    BRA .leaving
    .check_0200
    LDA.w $0200 : BNE .leaving
    .safe_overlay
    JMP .exit_clear_req

  .not_overlay
  CMP.b #$09 : BEQ +
  CMP.b #$0B : BNE .leaving
  +
  LDA.w $001B : ORA.w $0011 : BNE .leaving
  LDA.w $C2FE : CMP.b #$4A : BEQ .leaving
  BRA .build_occ

  .leaving
  LDA.b #$FF : JSR MagicBean_HideTrackedMask_Near
  LDA.w !MB_ResidentMask : ORA.w !MB_PendingRestore : STA.w !MB_PendingRestore
  LDA.b #$00
  STA.w !MB_ResidentMask
  STA.w !MB_PendingUpload
  STA.w !MB_HoldFrames
  STA.w !MB_HoldFrames+1
  STA.w !MB_HoldFrames+2
  JMP .exit_clear_req

  .build_occ
  LDX.b #$07
  LDA.b #$00
  -
    STA.w !MB_Occ, X
    DEX : BPL -

  REP #$20 : LDA.l MagicBean_HorseMarker : CMP.w #$4852 : SEP #$20 : BNE +
    LDA.l MagicBean_HorseOffState : BEQ +
      LDA.b #$FF : STA.w !MB_Occ+0
  +
  REP #$20 : LDA.l MagicBean_KorlMarker : CMP.w #$4B4C : SEP #$20 : BNE +
    LDA.l MagicBean_KorlDockState : BEQ +
      LDA.b #$FF : STA.w !MB_Occ+6
  +

  REP #$10 ; X=16 for $0000..$01FC OAM buffer scan
  LDX.w #$0000
  .oam_scan
    LDA.w $0801, X : CMP.b #$F0 : BNE + : JMP .oam_next : +
    LDA.w $0803, X : LSR : BCS + : JMP .oam_next : +

    LDA.w !MB_TrackCount : BEQ .oam_not_ours
      STA.w !MB_Scratch0
      PHX
      REP #$20 : TXA : STA.w !MB_Scratch2
      LDX.w #$0000
      .ours_loop
        LDA.w !MB_Scratch2
        CMP.w !MB_TrackOff, X : BCC .ours_next
        CMP.w !MB_TrackEnd, X : BCC .ours_hit
        .ours_next
        INX #2
        SEP #$20
        DEC.w !MB_Scratch0 : BEQ .ours_done
        REP #$20
        BRA .ours_loop
      .ours_hit
      SEP #$20
      PLX
      JMP .oam_next
      .ours_done
      SEP #$20
      PLX
    .oam_not_ours

    LDA.w $0802, X : STA.w !MB_Scratch0
    REP #$20 : TXA : LSR #2 : TAY : SEP #$20
    LDA.w $0A20, Y : AND.b #$02 : STA.w !MB_Scratch1
    PHX
    SEP #$10 ; X=8 for helpers
    LDA.w !MB_Scratch0 : LSR #5 : STA.w !MB_Scratch2
    LDA.w !MB_Scratch0 : LSR : JSR MagicBean_GetBitMask_Near : STA.w !MB_Scratch3
    LDA.w !MB_Scratch2 : JSR MagicBean_AddOccBit_Near

    LDA.w !MB_Scratch1 : BEQ .occ_done
      LDA.w !MB_Scratch0 : BIT.b #$01 : BEQ .no_odd_col
        LDA.w !MB_Scratch3 : PHA
        LDA.w !MB_Scratch0 : LSR : INC : JSR MagicBean_GetBitMask_Near : STA.w !MB_Scratch3
        LDA.w !MB_Scratch2 : JSR MagicBean_AddOccBit_Near
        PLA : STA.w !MB_Scratch3
      .no_odd_col
      LDA.w !MB_Scratch0 : BIT.b #$10 : BEQ .occ_done
        LDA.w !MB_Scratch2 : INC : AND.b #$07 : STA.w !MB_Scratch2
        JSR MagicBean_AddOccBit_Near
        LDA.w !MB_Scratch0 : BIT.b #$01 : BEQ .occ_done
          LDA.w !MB_Scratch0 : LSR : INC : JSR MagicBean_GetBitMask_Near : STA.w !MB_Scratch3
          LDA.w !MB_Scratch2 : JSR MagicBean_AddOccBit_Near
    .occ_done
    REP #$10
    PLX

    .oam_next
    INX #4
    CPX.w #$0200 : BCS + : JMP .oam_scan : +
  SEP #$10 ; back to X=8

  ; Single-pass sheet verification, collision/idle check, and remaining-block Occ reservation.
  LDX.b #$00
  .chk_loop
    LDA.w !MB_ResidentMask
    ORA.w !MB_PendingUpload
    ORA.w !MB_PendingRestore
    AND.l MagicBean_BitMask, X : BNE + : JMP .chk_next : +

    JSR MagicBean_ReadSlotSheet_Near
    CMP.w !MB_BackupSheet, X : BEQ .sheet_ok
      LDA.l MagicBean_InvBitMask, X
      AND.w !MB_PendingRestore : STA.w !MB_PendingRestore
      LDA.b #$FF : STA.w !MB_BackupSheet, X
      JSR MagicBean_ReleaseBlock_Near
      ; ReleaseBlock may have queued PendingRestore; drop it cleanly since sheet changed.
      LDA.l MagicBean_InvBitMask, X
      AND.w !MB_PendingRestore : STA.w !MB_PendingRestore
      BRA .chk_next

    .sheet_ok
    LDA.w !MB_BlockChr, X : STA.w !MB_Scratch0
    LSR #5 : STA.w !MB_Scratch1
    LDA.w !MB_Scratch0 : LSR : JSR MagicBean_GetBitMask_Near : STA.w !MB_Scratch3

    LDA.w !MB_ResidentMask : ORA.w !MB_PendingUpload
    AND.l MagicBean_BitMask, X : BEQ .reserve_occ

    PHX
    LDA.w !MB_Scratch1 : TAX
    LDA.w !MB_Occ, X : AND.w !MB_Scratch3
    BEQ +
      PLX
      BRA .do_release
    +
    PLX

    LDA.w !MB_ReqMask : AND.l MagicBean_BitMask, X : BEQ .idle_decay
      LDA.b #$08 : STA.w !MB_HoldFrames, X
      BRA .reserve_occ
    .idle_decay
      LDA.w !MB_HoldFrames, X : BEQ .do_release
      DEC : STA.w !MB_HoldFrames, X : BNE .reserve_occ

    .do_release
    JSR MagicBean_ReleaseBlock_Near
    LDA.w !MB_PendingRestore : AND.l MagicBean_BitMask, X : BEQ .chk_next

    .reserve_occ
    LDA.w !MB_Scratch1 : JSR MagicBean_AddOccBit_Near

    .chk_next
    INX : CPX.b #$03 : BCS + : JMP .chk_loop : +

  ; Allocate free non-colliding Page 1 blocks for newly requested unresident blocks.
  LDX.b #$00
  .alloc_k_loop
    LDA.w !MB_ReqMask : AND.l MagicBean_BitMask, X : BNE + : JMP .alloc_k_next : +
    LDA.w !MB_ResidentMask : ORA.w !MB_PendingUpload : ORA.w !MB_PendingRestore
    AND.l MagicBean_BitMask, X : BEQ + : JMP .alloc_k_next : +

    LDA.b #$01 : STA.w !MB_Scratch3
    .alloc_pass
      LDY.b #$00
      .alloc_row_loop
        PHX : TYX : LDA.l MagicBean_RowOrder, X : PLX
        STA.w !MB_Scratch0
        LSR : STA.w !MB_Scratch1
        PHX : TAX : LDA.w $C2FC, X : STA.w !MB_Scratch2 : PLX
        LDA.w !MB_Scratch3 : BEQ .row_occ_chk
          LDA.w !MB_Scratch2 : BEQ .row_occ_chk
          CMP.b #$FF : BNE .alloc_row_next
        .row_occ_chk
        PHX : LDA.w !MB_Scratch0 : TAX : LDA.w !MB_Occ, X : PLX
        CMP.b #$FF : BEQ .alloc_row_next

        PHX
        PHY
        PHA
        LDY.b #$07
        .alloc_col_loop
          LDA $01, S
          TYX
          AND.l MagicBean_BitMask, X
          BEQ .found_block
          DEY : BPL .alloc_col_loop
        PLA
        PLY
        PLX
        .alloc_row_next
        INY : CPY.b #$08 : BCC .alloc_row_loop

      LDA.w !MB_Scratch3 : BEQ .alloc_k_next
      LDA.b #$00 : STA.w !MB_Scratch3
      BRA .alloc_pass

    .found_block
    PLA
    TYA
    PLY
    PLX
    PHA
    JSR MagicBean_GetBitMask_Near : STA.w !MB_Scratch3
    LDA.w !MB_Scratch0 : JSR MagicBean_AddOccBit_Near
    PLA : ASL
    STA.w !MB_Scratch3
    LDA.w !MB_Scratch0 : ASL #5 : ORA.w !MB_Scratch3
    STA.w !MB_BlockChr, X
    LDA.w !MB_Scratch1 : STA.w !MB_BlockSlot, X
    LDA.w !MB_Scratch2 : STA.w !MB_BackupSheet, X
    LDA.l MagicBean_BitMask, X : ORA.w !MB_PendingUpload : STA.w !MB_PendingUpload
    LDA.b #$08 : STA.w !MB_HoldFrames, X

    .alloc_k_next
    INX : CPX.b #$03 : BCS + : JMP .alloc_k_loop : +

  .exit_clear_req
  LDA.b #$00
  STA.w !MB_ReqMask
  STA.w !MB_TrackCount
  .exit
  REP #$30 : PLY : PLX : PLA : PLB : PLP
  RTL
}

; Transfers 2 VRAM tile rows (row 0 at !MB_Scratch0, row 1 at !MB_Scratch0+$0100).
; Caller sets $4300, $4301, $4304, !MB_Scratch0 (VRAM), !MB_Scratch2 (addr0).
; In: Y(8-bit) = byte len ($40/$42), A(16-bit) = row address stride ($40/$42), M=16, X=8, DBR=$00.
; Out: M=8, X preserved.
MagicBean_DmaPair_Near:
{
  PHA
  LDA.l MagicBean_Scratch2 : STA.w $4302
  TYA : AND.w #$00FF : STA.w $4305
  LDA.l MagicBean_Scratch0 : STA.w $2116
  SEP #$20
  LDA.b #$01 : STA.w $420B

  REP #$20
  PLA : CLC : ADC.l MagicBean_Scratch2 : STA.w $4302
  TYA : AND.w #$00FF : STA.w $4305
  LDA.l MagicBean_Scratch0 : CLC : ADC.w #$0100 : STA.w $2116
  SEP #$20
  LDA.b #$01 : STA.w $420B
  RTS
}

; Sets !MB_Scratch0 = VRAM top word and !MB_Scratch2 = BackupBuf + 132*k.
; In: X = k (0..2), M=8, X=8. Out: M=8, X preserved, Y = k*2.
MagicBean_PrepBlockAddr_Near:
{
  LDA.l MagicBean_BlockChr, X
  REP #$20 : AND.w #$00FF : ASL #4 : CLC : ADC.w #$5000 : STA.l MagicBean_Scratch0
  TXA : ASL A : PHX : TAX
  LDA.l MagicBean_BackupOffTable, X : CLC : ADC.w #MagicBean_BackupBuf : STA.l MagicBean_Scratch2
  TXA : TAY
  PLX
  SEP #$20
  RTS
}

; Called from P2_NmiUpload .done (VBlank NMI, M=8, X=16, DBR=$00).
; Restores all pending-restore blocks cleanly, then services at most 1 pending upload (260 B).
MagicBean_NmiUpload_Long:
{
  PHP : PHB
  REP #$30 : PHA : PHX : PHY
  SEP #$30 ; M=8, X=8
  LDA.b #$00 : PHA : PLB

  REP #$20
  LDA.l MagicBean_Magic : CMP.w #!MAGIC_BEAN_MAGIC_SIG
  SEP #$20
  BEQ +
    JMP .exit
  +
  LDA.l MagicBean_PendingRestore : ORA.l MagicBean_PendingUpload
  BNE +
    JMP .exit
  +

  LDA.b #$80 : STA.w $2115

  LDA.l MagicBean_PendingRestore : BEQ .phase2_upload
  LDX.b #$00
  .restore_loop
    LDA.l MagicBean_PendingRestore : AND.l MagicBean_BitMask, X : BEQ .restore_next
    JSR MagicBean_ReadSlotSheet_Near
    CMP.l MagicBean_BackupSheet, X : BNE .restore_clear

    JSR MagicBean_PrepBlockAddr_Near
    LDA.b #$01 : STA.w $4300
    LDA.b #$18 : STA.w $4301
    LDA.b #MagicBean_BackupBuf>>16 : STA.w $4304
    LDY.b #$40
    REP #$20
    LDA.l MagicBean_Scratch2 : CLC : ADC.w #$0002 : STA.l MagicBean_Scratch2
    LDA.w #$0042
    JSR MagicBean_DmaPair_Near

    .restore_clear
    LDA.l MagicBean_InvBitMask, X : AND.l MagicBean_PendingRestore : STA.l MagicBean_PendingRestore
    .restore_next
    INX : CPX.b #$03 : BCC .restore_loop

  .phase2_upload
  LDA.l MagicBean_PendingUpload : BNE + : JMP .restore_dma_defaults : +
  LDX.b #$00
  .find_up_loop
    AND.l MagicBean_BitMask, X : BNE .found_up
    INX : CPX.b #$03 : BCC .find_up_loop_next : JMP .restore_dma_defaults
    .find_up_loop_next
    LDA.l MagicBean_PendingUpload
    BRA .find_up_loop

  .found_up
  LDA.w $0010 : CMP.b #$09 : BEQ +
                CMP.b #$0B : BEQ +
                BRA .cancel_all_up
  +
  LDA.w $001B : ORA.w $0011 : BNE .cancel_all_up
  JSR MagicBean_ReadSlotSheet_Near
  CMP.l MagicBean_BackupSheet, X : BEQ .do_up
    LDA.l MagicBean_InvBitMask, X : AND.l MagicBean_PendingUpload : STA.l MagicBean_PendingUpload
    BRA .restore_dma_defaults
  .cancel_all_up
    LDA.b #$00 : STA.l MagicBean_PendingUpload
    BRA .restore_dma_defaults

  .do_up
  JSR MagicBean_PrepBlockAddr_Near

  LDA.b #$81 : STA.w $4300
  LDA.b #$39 : STA.w $4301
  LDA.b #MagicBean_BackupBuf>>16 : STA.w $4304
  LDY.b #$42
  REP #$20 : LDA.w #$0042 : JSR MagicBean_DmaPair_Near

  LDA.b #$01 : STA.w $4300
  LDA.b #$18 : STA.w $4301
  LDA.b #MagicBean_TilePayload>>16 : STA.w $4304
  PHX
  TXA : ASL A : TAX
  REP #$20
  LDA.l MagicBean_PayloadAddrTable, X : STA.l MagicBean_Scratch2
  PLX
  LDY.b #$40
  LDA.w #$0040 : JSR MagicBean_DmaPair_Near

  LDA.l MagicBean_InvBitMask, X : AND.l MagicBean_PendingUpload : STA.l MagicBean_PendingUpload
  LDA.l MagicBean_BitMask, X : ORA.l MagicBean_ResidentMask : STA.l MagicBean_ResidentMask

  .restore_dma_defaults
  LDA.b #$01 : STA.w $4300
  LDA.b #$18 : STA.w $4301
  LDA.b #$7E : STA.w $4304
  LDA.b #$80 : STA.w $2115

  .exit
  REP #$30 : PLY : PLX : PLA : PLB : PLP
  RTL
}

; Called from HouseVillager_LoadSheet ($00E1CF / $00D739) when VRAM $5000+ sprite sets reload.
; Preserves A/X/Y and P widths.
MagicBean_OnSheetReload_Long:
{
  PHP : SEP #$20 : PHA
  REP #$20
  LDA.l MagicBean_Magic : CMP.w #!MAGIC_BEAN_MAGIC_SIG
  SEP #$20
  BNE .done
    LDA.b #$00
    STA.l MagicBean_ReqMask
    STA.l MagicBean_ResidentMask
    STA.l MagicBean_PendingUpload
    STA.l MagicBean_PendingRestore
    STA.l MagicBean_TrackCount
    STA.l MagicBean_HoldFrames
    STA.l MagicBean_HoldFrames+1
    STA.l MagicBean_HoldFrames+2
  .done
  PLA : PLP
  RTL
}

MagicBean_CodeEnd:
assert pc() <= $3AB800, "Magic Bean Page 1 OAM/VRAM cache exceeded Bank $3A slot ($3AB000-$3AB7FF)"

if defined("ENABLE_HORSE_PARK_ANYWHERE")
  if !ENABLE_HORSE_PARK_ANYWHERE == 0 || !ENABLE_HORSE_FORM == 0 || !DISABLE_MASKS == 1
    org $008056 ; @hook module=Sprites name=MagicBean_FrameEndScan kind=jsl target=MagicBean_MainRoutingFrameEnd_Long
      assert read1($008056) == $22 && read3($008057) == $0080B5, "Expected JSL Module_MainRouting at $008056"
      JSL MagicBean_MainRoutingFrameEnd_Long
  endif
endif

pullpc
