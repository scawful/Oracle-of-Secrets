;=====================================================
; Fishing system for alttp V1.0
;-----------------------------------------------------
; Made by someone, somewhere, something
;-----------------------------------------------------
; Important infos
; Use the address $021B - 16bit (can be changed)
; $7F5BA0 RAM for fishing power
; $7F5BA2 RAM for fishing mode - 1 = rod out, 2 = pull
; $7F5BA3 RAM Index for the fishing floater
; Mode 3 owns the rod graphics during the cast wind-up; $FF means no floater.
!FishingFloaterSignature = $F1 ; SprMiscA, reset by native sprite allocation
; Modify the code of the sprite "RunningBoy" 0x74
; ====================================================

; Sprite_2D_NecklessMan_bounce (active only when Horse Form is disabled; when enabled,
; Sprites/NPCs/horse.asm owns $06:92DD and dispatches SprMiscA==$F1 to FloaterBoySpriteCheck).
; Save the items freespace cursor, patch the vanilla dispatcher, then pullpc
; below. This used to be a pushpc left open at the end of portal_rod.asm.
pushpc
if !ENABLE_HORSE_FORM == 0
org $06C0B2 ; @hook module=Items
{
  JSL FloaterBoySpriteCheck
  RTS
}
endif

org $07AF3E ; Cane of Byrna
LinkItem_FishingRodAndPortalRod:
{
  %SelectedItem()
  CMP.b #$1B : BNE .not_byrna
    JSR LinkItem_RestoredByrna
    RTS
  .not_byrna
  ; The Portal Rod has its own Items cell ($0202 = $19, Menu_ItemIndex $0D
  ; like the Fishing Rod cell $10). The cell picks the rod; no L/R switch.
  %SelectedItem()
  CMP.b #$19 : BEQ .own_cell_portal_rod
    JSL LinkItem_FishingRod
    RTS
  .own_cell_portal_rod
  JSR LinkItem_PortalRod
  RTS
}

assert pc() <= $07AFB4

; Held Cane/Rod OAM palette override ($0DA6AA..$0DA6B4, 11 bytes).
; Vanilla sets $0F = $04 (OAM pal 2 blue) for $0303 == $0D (Byrna/Portal Rod).
; When actively fishing ($7F5BA2 != 0), switch to OAM pal 7 ($0E, Link's
; palette: color 14 = warm wood brown, color 6 = tan, color 5 = outline) to
; match the F2 Menu/HUD Fishing Rod while leaving Byrna/Somaria/Portal intact.
assert read4($0DA6AA) == $C90303AD && read1($0DA6AE) == $0D && read4($0DA6B1) == $0F8504A9, "Bank 0D Cane/Rod OAM palette check moved"
org $0DA6AA ; @hook module=Items name=FishingRod_WeaponOamPalette kind=jsl target=FishingRod_WeaponOamPalette expected_m=8 protected_size=11
  JSL FishingRod_WeaponOamPalette
  NOP #7
assert pc() == $0DA6B5

pullpc

FishingRod_WeaponOamPalette:
{
  LDA.w $0303 : CMP.b #$0D : BNE .done
  LDA.l $7F5BA2 : BNE .fishing
    LDA.b #$04 : STA.b $0F
    RTL
  .fishing
    LDA.b #$0E : STA.b $0F
  .done
  RTL
}

FishingRodExit:
  PLB
  RTL

LinkItem_FishingRod:
{
  PHB : PHK : PLB

  ; Abort and clean up any active session in non-default states (swim/fall/recoil/door/carry/dash/submodule/Minish/Moosh).
  LDA.b $5D : ORA.w $0345 : ORA.b $5B : ORA.b $6C
  ORA.w $0308 : ORA.w $0372 : ORA.b $11 : BNE .abort_if_active
  LDA.w $02B2 : BEQ .form_ok
  CMP.b #$06 : BEQ .form_ok
.abort_if_active
  JSR Fishing_ClearSession
  BRA FishingRodExit
.form_ok

  BIT.b $3A : BVS .holding_y
    ; Never reuse an orphaned session when starting a fresh cast.
    LDA.l $7F5BA2 : BEQ +
      JSR Fishing_ClearSession
    +
    JSR CheckYButtonPress : BCC FishingRodExit

    LDA.b $67 : AND.b #$F0 : STA.b $67

    JSL FishingSwapCaneBlockHammerGfx
    LDA.b #$03 : STA.l $7F5BA2
    LDA.b #$FF : STA.l $7F5BA3

    STZ.b $69
    STZ.b $68
    LDA.b #$08
    TSB.w $037A
    STZ.b $2E
    STZ.w $0300
    STZ.w $0301

    LDA.w RodAndCaneAnimationTimer : STA.b $3D

  .holding_y
  JSR HaltLinkWhenUsingItems
  LDA.b #$26 : STA.w $0107 ; Sword DMA to Floater Hammer

  LDA.w $0300 : CMP #$02 : BEQ +
    DEC.b $3D ; decrease timer
    BPL FishingRodExit
  +

  LDA.l $7F5BA2 : CMP #$02 : BNE +
    JMP EndFishing
  +
  CMP #$01 : BEQ .waitforend

  LDA.w $0300 ; animation state
  INC A
  STA.w $0300

  TAX

  ; load timer for current frame animation state
  LDA.w RodAndCaneAnimationTimer, X : STA.b $3D ; timer
  CPX.b #$01 : BNE +
    ; spawn floaters
    PHX
    LDA.b #$2D
    JSL Sprite_SpawnDynamically
    BPL .spawned
      PLX
      JMP EndFishing
    .spawned

    LDA.b $22 : STA.w SprX, Y
    LDA.b $23 : STA.w SprXH, Y
    LDA.b $20 : STA.w SprY, Y
    LDA.b $21 : STA.w SprYH, Y
    LDA.b $EE : STA.w SprFloor, Y
    LDA.b #$01 : STA.w SprCollision, Y ; is floater
    LDA.b #!FishingFloaterSignature : STA.w SprMiscA, Y
    TYA : STA.l $7F5BA3 ; keep the index of the sprite
    TYX
    JSL SpritePrep_Floater ; just call it there
    PLX
  +
  CPX.b #$02 : BCC .exit
  LDA #$01 : STA.l $7F5BA2 ; set fishing rod state to rod is out
  LDA.b #$FE : STA $3D ;set timer to 8 frames
  ; wait for Y press
  .waitforend
  JSR Fishing_GetFloater : BCS +
    JMP EndFishing
  +

  JSL ItemBindings_UsePress : BEQ .exit
  .reel
  LDA.b #$08 : STA $3D ;set timer to 8 frames
  STZ.w $0300 ; set animation frame to 0 (pull back)

  LDY.b $66
  LDA.w DirSpeedsY, Y : STA.w SprYSpeed, X ; YSpeed
  LDA.w DirSpeedsX, Y : STA.w SprXSpeed, X ; YSpeed
  .BringBackFloater
  LDA.b #$10 : STA.w $0F80, X ; Gravity


  ; =======================================================
  ; We got something spawn it and pull it at us
  LDA.w SprMiscB, X : BEQ .noPrize
  JSL GetRandomInt : AND #$0F : TAY : LDA Prizes, Y : BEQ .noPrize
    JSL Sprite_SpawnDynamically
    BMI .noPrize
    JSL Sprite_SetSpawnedCoordinates

    PHX
    LDX.b $66
    LDA.w DirSpeedsY, X : STA.w SprYSpeed, Y ; YSpeed
    LDA.w DirSpeedsX, X : STA.w SprXSpeed, Y ; YSpeed

    PLX
    LDA.b #$FF : STA.w SprTimerD, Y
    LDA.b #$20 : STA.w $0F80, Y ; Gravity
    ;LDA.b #$06 : STA.w SprHeight, Y

  .noPrize
  LDA.b #$02 : STA.l $7F5BA2 ; set fishing rod state to pulling back


  .exit
  PLB
  RTL
}

EndFishing:
{
  JSR Fishing_ClearSession
  PLB
  RTL
}

; C set and X = our live floater; a remembered slot alone is not ownership.
Fishing_GetFloater:
{
  LDA.l $7F5BA3 : CMP.b #$10 : BCS .none
  TAX
  LDA.w SprState, X : CMP.b #$09 : BNE .none
  LDA.w SprType, X : CMP.b #$2D : BNE .none
  LDA.w SprMiscA, X : CMP.b #!FishingFloaterSignature : BNE .none
  SEC : RTS
  .none
  CLC : RTS
}

Fishing_ClearSession:
{
  LDA.l $7F5BA2 : BEQ .return
  PHX
  JSR Fishing_GetFloater : BCC .clear
    STZ.w SprState, X
  .clear
  LDA.b #$00 : STA.l $7F5BA2
  LDA.b #$FF : STA.l $7F5BA3
  STZ.b $5E
  STZ.w $0300
  STZ.b $3D
  STZ.w $0350
  STZ.w $037A
  LDA.b $3A
  AND.b #$BF
  STA.b $3A
  JSL RestoreCaneBlockHammerGfx
  PLX
  .return
  RTS
}

RodAndCaneAnimationTimer:
  db $0A, $05, $2A

DirSpeedsX:
  db $00, $00, $20, $DF
DirSpeedsY:
  db $20, $DF, $00, $00

; Sprite ID $D2 is repurposed to Sprite_CloudBridge (Objects/cloud_bridge.asm); use valid vanilla pickups.
Prizes:
  db $D8, $DB, $D8, $DA, $D9, $DA, $DB, $DC, $DF, $E0, $E1, $D9, $D9, $DA, $D9, $DA


;assert pc() <= $07A64A


fishingrodgfx:
  incbin gfx/fishingrod.bin
blockgfx:
  incbin gfx/blockgfx.bin
canegfx:
  incbin gfx/canegfx.bin
floatergfx:
  incbin gfx/floatergfx.bin
hammergfx:
  incbin gfx/hammergfx.bin


CheckYButtonPress:
{
  BIT.b $3A : BVS .fail
  LDA.b $46 : BNE .fail
  JSL ItemBindings_UsePress : BEQ .fail
    TSB.b $3A
    SEC
    RTS

  .fail
  CLC
  RTS
}


HaltLinkWhenUsingItems:
{
  LDA.b $AD : CMP.b #$02 : BNE .skip
    LDA.w $0322 : AND.b #$03 : CMP.b #$03 : BNE .skip
      STZ.b $30
      STZ.b $31
      STZ.b $67
      STZ.b $2A
      STZ.b $2B
      STZ.b $6B

  .skip
  LDA.w $02F5 : BEQ .return
    STZ.b $67
  .return
  RTS
}

FishingSwapCaneBlockHammerGfx:
{
  PHX ; keep X
  PHP ; keep processor byte

  REP #$30 ; 16bit is a bit faster

  LDX #$01BE
  --
  LDA.l fishingrodgfx, X : STA.l $7E9F40, X
  LDA.l floatergfx, X : STA.l $7EA480, X
  DEX : DEX
  BPL --

  PLP
  PLX
  RTL
}

RestoreCaneBlockHammerGfx:
{
  PHX ; keep X
  PHP ; keep processor byte

  REP #$30 ; 16bit is a bit faster

  LDX #$01BE
  --
  LDA.l canegfx, X : STA.l $7E9F40, X
  LDA.l blockgfx, X : STA.l $7EA480, X
  LDA.l hammergfx, X : STA.l $7E9640, X
  DEX : DEX
  BPL --

  PLP
  PLX
  RTL
}

FloaterBoySpriteCheck:
{
  LDA.w SprMiscA, X : CMP.b #!FishingFloaterSignature : BEQ .is_floater
    JML $0DC6DE
.is_floater
  PHB : PHK : PLB
  JSR Sprite_Floater
  PLB
  RTL
}

Sprite_CheckIfActive:
{
  LDA.w SprFreeze ; Remove that if want to be able to pause all other sprites
  BNE .inactive

  LDA.b $11
  BNE .inactive

  LDA.w SprDefl, X
  BMI .active

  LDA.w $0F00, X
  BEQ .active

  .inactive
  PLA
  PLA

  .active
  RTS
}

; =========================================================
; Floater sprite code

SpritePrep_Floater:
{
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprYRound, X
  STZ.w SprXRound, X
  STZ.w SprHeightS, X
  STZ.w SprTimerA, X
  STZ.w SprTimerC, X
  STZ.w SprTimerD, X

  LDA.b $66 : CMP.b #$03 : BNE .notRight
    LDA.b #$12 : STA.w SprXSpeed, X ; XSpeed
    BRA .DoInitFloater
  .notRight
  CMP.b #$02 : BNE .notLeft
    LDA.b #$ED : STA.w SprXSpeed, X ; XSpeed
    BRA .DoInitFloater
  .notLeft
  CMP.b #$01 : BNE .notDown
    LDA.b #$12 : STA.w SprYSpeed, X ; YSpeed
    BRA .DoInitFloater
  .notDown
  CMP.b #$00 : BNE .notUp
    LDA.b #$ED : STA.w SprYSpeed, X ; YSpeed
    BRA .DoInitFloater
  .notUp

  .DoInitFloater

  ; Keep floater active when cast past a screen edge ($0CAA bit 7) and use small shadow ($0E60 bit 5),
  ; overriding Epona's shared $2D property table defaults ($0CAA=$46, $0E60=$C6).
  LDA.w SprDefl, X : ORA.b #$80 : STA.w SprDefl, X
  LDA.w $0E60, X : ORA.b #$20 : STA.w $0E60, X

  LDA.b #$08 : STA.w SprHeight, X    ; Height
  LDA.b #$10 : STA.w $0F80, X    ; Gravity
  LDA.b #$00 : STA.w SprMiscG, X ; is it in water?
  LDA.b #$00 : STA.w SprMiscE, X    ; Wiggling Velocity index
  LDA.b #$00 : STA.w SprMiscD, X    ; just for a check
  LDA.b #$00 : STA.w SprMiscB, X    ; if we have a fish on line

  ;SprTimerD Timer for when floater is in water waiting for a fish to catch

  RTL
}

; ---------------------------------------------------------

Sprite_Floater:
{
  LDA.l $7F5BA2 : BNE +
    STZ.w SprState, X
    RTS
  +
  LDA.b $5D : ORA.w $0345 : ORA.b $5B : ORA.b $11 : BEQ +
    JSR Fishing_ClearSession
    RTS
  +

  ; Floater Draw, allocate 4 tiles to use for the hud
  LDA.w SprMiscG, X : BEQ +
    JSL Sprite_DrawWaterRipple
  +
  JSR Sprite_Floater_Draw

  LDA.w SprMiscG, X : BNE +
    JSL Sprite_DrawShadow
  +

  JSR Sprite_CheckIfActive

  LDA.w SprMiscG, X : BEQ .noFishOnLine ; is the floater in water?

    LDA.w SprTimerD, X : BNE .noWigglingYet ; timerD wait until fish is on line

      LDA.w SprMiscB, X : BNE .fishOnlineWait
      ; start another random timer for the time it'll last
      JSL GetRandomInt : AND #$3F
      CLC : ADC.b #$0F : STA.w SprTimerA, X ; wiggling timer
      INC.w SprMiscB, X ; we have a fish on line

    .noWigglingYet

    LDA.w SprMiscB, X : BEQ .noFishOnLine ; do we already have a fish on line?
    .fishOnlineWait
    LDA.w SprTimerA, X : BNE .still_wiggling
    STZ.w SprMiscB, X ; no more fish on line took too much time
    JSL GetRandomInt : AND.b #$7F
    CLC : ADC.b #$7F : STA.w SprTimerD, X ; reset timer wait until fish is on line
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    BRA .noFishOnLine
    .still_wiggling


    LDA.w SprTimerC, X : AND.b #$1F : TAY
    LDA.w WigglingTable, Y : STA.w SprXSpeed, X
    STA.w SprYSpeed, X
    LDY.w SprTimerC, X : BNE + ; use timer to do wiggling
    ; if = 0 then put it back to F
    LDA.b #$0F : STA.w SprTimerC, X ; wiggling timer
    +

  .noFishOnLine

  JSL Sprite_MoveLong
  JSL Sprite_MoveAltitude

  LDA.w $0F80, X : SEC : SBC.b #$01 : STA.w $0F80, X

  LDA.w SprHeight, X : BPL .aloft

  STZ.w SprHeight, X

  LDA.w SprXSpeed, X : ASL A : ROR.w SprXSpeed, X

  LDA.w SprYSpeed, X : ASL A : ROR.w SprYSpeed, X

  LDA.w $0F80, X : EOR.b #$FF : INC A

  LSR A
  CMP.b #$09
  BCS .no_bounce

  LDA.w SprMiscD, X : BNE .not_water_tile_last
    INC.w SprMiscD, X
    JSL Sprite_CheckTileCollision
    LDA.w $0FA5
    CMP.b #$08 : BEQ .water_tile_last
    CMP.b #$09 : BNE .not_water_tile_last
    .water_tile_last
    INC.w SprMiscG, X ; Set that so we know floater is in water!
    JSL Sprite_SpawnSmallSplash

    JSL GetRandomInt : AND #$3F
    CLC : ADC #$3F : STA.w SprTimerD, X

  .not_water_tile_last
  STZ.w $0F80, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X

  BRA .aloft

  .no_bounce
  STA.w $0F80, X

  JSL Sprite_CheckTileCollision
  LDA.w $0FA5
  CMP.b #$08 : BEQ .water_tile
  CMP.b #$09 : BNE .not_water_tile

  .water_tile
  ;STZ.w $0F80, X

  JSL Sprite_SpawnSmallSplash

  .not_water_tile
  .aloft

  LDA.b #$01 : STA.w SprCollision, X ; restore floater sprite seems to be overwriten
  RTS
}

Sprite_Floater_Draw:
{
  JSL Sprite_PrepOamCoord
  BCS .offscreen

  REP #$20
  LDA.b $00 : CLC : ADC.w #$000F : CMP.w #$010F : BCS .offscreen_16
  LDA.b $02 : CLC : ADC.w #$000F : CMP.w #$00EF : BCS .offscreen_16
  SEP #$20

  LDA.b #$04 ; 1 oam slot
  JSL OAM_AllocateFromRegionC

  REP #$20
  LDA.b $00 : AND.w #$0100 : STA.b $0E ; high byte ($0F) holds X-MSB bit 0
  SEP #$20

  LDY.b #$00
  LDA.b $00 : STA.b ($90), Y
  INY
  LDA.b $02 : STA.b ($90), Y
  INY
  LDA.b #$0C : STA.b ($90), Y
  INY
  LDA.b #$32 : STA.b ($90), Y

  LDA.b #$02 : ORA.b $0F : STA.b ($92)
  RTS

.offscreen_16
  SEP #$20
.offscreen
  RTS
}


WigglingTable:
  db 08, -10, 06, -8, 12, -14, 18, -20
  db 10, -12, 04, -6, 08,-10, 14,-16, 08
  db -10, 06, -8, 12, -14, 18, -20, 10
  db -12, 04, -6, 08,-10, 14,-16

DismissRodFromMenu:
{
  PHA
  PHB : PHK : PLB
  JSR Fishing_ClearSession
  PLB
  PLA
  RTL
}

%log_end("Items/fishing_rod.asm", !LOG_ITEMS)
