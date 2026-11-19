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

MagicBeanSpot_Screens:
  db $00, $2D, $15, $33

MagicBeanSpot_SramLow:
  db $9B, $C0, $C1, $C2

; Home soil world pixel coordinates per spot:
;   0: $0240, $00D0 (576, 208)   OW $00/$01 (36, 13)
;   1: $0BA0, $0AC0 (2976, 2752) OW $2D     (26, 12)
;   2: $0B90, $05C0 (2960, 1472) OW $15     (25, 28)
;   3: $0740, $0E30 (1856, 3632) OW $33     (20, 35)
MagicBeanSpot_HomeXLo:
  db $40, $A0, $90, $40
MagicBeanSpot_HomeXHi:
  db $02, $0B, $0B, $07
MagicBeanSpot_HomeYLo:
  db $D0, $C0, $C0, $30
MagicBeanSpot_HomeYHi:
  db $00, $0A, $05, $0E

; Spot 0: OW $00/$01 (576,208) -> NE Ranch cliff (996,420) [+420, +212]
; Spot 1: OW $2D (2976,2752) -> NW plateau (2720,2656) [-256, -96]
; Spot 2: OW $15 (2960,1472) -> North terrace (2896,1104) [-64, -368]
; Spot 3: OW $33 (1856,3632) -> Top E39 ridge (2064,3152) [+208, -480]
MagicBean_LegXSpeed:
  db $0C, $18, $18
  db $F0, $E8, $F8
  db $F8, $00, $F8
  db $08, $08, $10

MagicBean_LegYSpeed:
  db $FC, $0E, $0E
  db $F0, $FC, $FC
  db $E8, $E8, $EC
  db $E8, $E8, $E8

MagicBean_LegTimers:
  db $30, $80, $80
  db $30, $70, $50
  db $40, $80, $40
  db $60, $80, $60

MagicBean_LegDragDir:
  db $03, $03, $03
  db $02, $02, $02
  db $00, $00, $00
  db $00, $00, $00

MagicBean_GetSpotIndex:
{
  LDA.b $1B : BNE .not_spot
  LDY.b #$03
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
  LDY.b #$03
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
  LDY.b #$03
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
