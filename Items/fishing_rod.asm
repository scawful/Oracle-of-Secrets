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
; Modify the code of the sprite "RunningBoy" 0x74
; =========================================================
; Values
;#$400 ; to show fishing hud
;#$14A ; only the hud

; ================= USED FOR THE FLOATER ==================

; Sprite_2D_NecklessMan_bounce
org $06C0B2
{
  JSL FloaterBoySpriteCheck
  RTS
}

org $07AF3E ; Cane of Byrna
LinkItem_FishingRodAndPortalRod:
{
  ; If the sram slot is 02, we can swap between the fishing rod and the portal rod
  LDA.l $7EF351 : CMP.b #$02 : BEQ +
    JSL LinkItem_FishingRod
    RTS
  +

  LDA.w FishingOrPortalRod : BNE .portal_rod
    JSL LinkItem_FishingRod
    JMP ++
  .portal_rod
  JSR LinkItem_PortalRod
  ++
  LDA.b $F6
  BIT.b #$20 : BNE .left ; pressed left 
  BIT.b #$10 : BNE .right ; pressed right
  RTS
  
  ; Swap the ram variable FishingOrPortalRod based on left or right
  ; 00 = fishing rod, 01 = portal rod
  .left
  LDA.w FishingOrPortalRod : CMP #$00 : BEQ .right
  LDA.b #$00 : STA.w FishingOrPortalRod
  RTS
  .right
  LDA.w FishingOrPortalRod : CMP #$01 : BEQ .left
  LDA.b #$01 : STA.w FishingOrPortalRod
  RTS
}

warnpc $07AFB4

pullpc

FishingRodExit:
  PLB
  RTL

LinkItem_FishingRod:
{
  PHB : PHK : PLB

  BIT.b $3A
  BVS .holding_y

  LDA.b $6C
  BNE FishingRodExit

  JSR CheckYButtonPress
  BCC FishingRodExit
  
  LDA.b $67
  AND.b #$F0
  STA.b $67

  JSL FishingSwapCaneBlockHammerGfx


  STZ.b $69
  STZ.b $68
  LDA.b #$08
  TSB.w $037A
  STZ.b $2E
  STZ.w $0300
  STZ.w $0301

  LDA.w RodAndCaneAnimationTimer
  STA.b $3D


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

  LDA.w RodAndCaneAnimationTimer, X  ; load timer for current frame animation state
  STA.b $3D ; timer
  CPX.b #$01 : BNE +
  ; spawn floater
  PHX
  LDA.b #$2D
  JSL $1DF65D ; Sprite_SpawnDynamically because whatever

  LDA.b $22 : STA.w SprX, Y
  LDA.b $23 : STA.w SprXH, Y
  LDA.b $20 : STA.w SprY, Y
  LDA.b $21 : STA.w SprYH, Y
  LDA.b #$01 : STA.w $0E70, Y ; is floater
  TYA : STA.l $7F5BA3 ; keep the index of the sprite
  TYX
  JSL SpritePrep_Floater ; just call it there
  PLX

  +
  CPX.b #$02
  BCC .exit
  LDA #$01
  STA.l $7F5BA2 ; set fishing rod state to rod is out
  LDA.b #$FE : STA $3D ;set timer to 8 frames
  ; wait for Y press
  .waitforend

  LDA.b $F4 : AND #$40 : BEQ .exit
  LDA.b #$08 : STA $3D ;set timer to 8 frames
  STZ.w $0300 ; set animation frame to 0 (pull back)
  LDA.l $7F5BA3 : TAX

  LDY.b $66
  LDA.w DirSpeedsY, Y : STA.w $0D40, X ; YSpeed
  LDA.w DirSpeedsX, Y : STA.w $0D50, X ; YSpeed
  .BringBackFloater
  LDA.b #$10 : STA.w $0F80, X ; Gravity


  ;===========================================================
  ; We got something spawn it and pull it at us
  LDA.w $0DB0, X : BEQ .noPrize
  JSL $0DBA71 : AND #$0F ; get random int
  TAY : LDA Prizes, Y : BEQ .noPrize

  JSL $1DF65D ; Sprite_SpawnDynamically because whatever
  JSL $09AE64 ; Sprite_SetSpawnedCoords

  LDA.w $0E20, Y : CMP.b #$D2 : BNE .notafish
  LDA #$04 : STA.w $0F70, Y
  LDA #$01 : STA.w $0D80, Y
  .notafish

  PHX
  LDX.b $66
  LDA.w DirSpeedsY, X : STA.w $0D40, Y ; YSpeed
  LDA.w DirSpeedsX, X : STA.w $0D50, Y ; YSpeed

  PLX
  LDA.b #$FF : STA.w $0EE0, Y
  LDA.b #$20 : STA.w $0F80, Y ; Gravity
  ;LDA.b #$06 : STA.w $0F70, Y

  .noPrize
  LDA.b #$02 : STA.l $7F5BA2 ; set fishing rod state to pulling back 


  .exit
  PLB
  RTL
}

EndFishing:
{
  LDA #$00
  STA.l $7F5BA2
  LDA.l $7F5BA3 : TAX
  STZ.w $0DD0, X
  STZ.b $5E
  STZ.w $0300
  STZ.b $3D
  STZ.w $0350
  STZ.w $037A
  LDA.b $3A
  AND.b #$BF
  STA.b $3A
  JSL RestoreCaneBlockHammerGfx
  PLB
  RTL
}

RodAndCaneAnimationTimer:
  db $0A, $05, $2A

DirSpeedsX:
  db $00, $00, $20, $DF
DirSpeedsY:
  db $20, $DF, $00, $00

Prizes:
  db $D8, $D2, $D2, $D2, $D9, $DA, $DB, $DC, $DF, $E0, $E1, $D9, $D9, $DA, $D9, $DA


;warnpc $07A64A


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
    LDA.b $F4 : AND.b #$40 : BEQ .fail
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
  PHB : PHK : PLB
  JSR Sprite_Floater
  PLB
  RTL
}

Sprite_CheckIfActive:
{
    LDA.w $0FC1 ; Remove that if want to be able to pause all other sprites
    BNE .inactive

    LDA.b $11
    BNE .inactive

    LDA.w $0CAA,X
    BMI .active

    LDA.w $0F00,X
    BEQ .active

  .inactive
    PLA
    PLA

  .active
    RTS
}

;======================================================================
;Floater sprite code
SpritePrep_Floater:
{
    LDA.b $66 : CMP.b #$03 : BNE .notRight
    LDA.b #$12 : STA.w $0D50, X ; XSpeed
    BRA .DoInitFloater
    .notRight
    CMP.b #$02 : BNE .notLeft
    LDA.b #$ED : STA.w $0D50, X ; XSpeed
    BRA .DoInitFloater
    .notLeft
    CMP.b #$01 : BNE .notDown
    LDA.b #$12 : STA.w $0D40, X ; YSpeed
    BRA .DoInitFloater
    .notDown
    CMP.b #$00 : BNE .notUp
    LDA.b #$ED : STA.w $0D40, X ; YSpeed
    BRA .DoInitFloater
    .notUp


  .DoInitFloater

    LDA.b #$08 : STA.w $0F70, X ; Height
    LDA.b #$10 : STA.w $0F80, X ; Gravity
    LDA.b #$00 : STA.w $0ED0, X ; is it in water?
    LDA.b #$00 : STA.w $0EB0, X ; Wiggling Velocity index
    LDA.b #$00 : STA.w $0E90, X ; just for a check
    LDA.b #$00 : STA.w $0DB0, X ; if we have a fish on line

    ;$0EE0 Timer for when floater is in water waiting for a fish to catch

    RTL
}

;---------------------------------------------------------------------

Sprite_Floater:
{
  ; Floater Draw, allocate 4 tiles to use for the hud
  LDA $0ED0, X : BEQ +
  JSL $059FFA ; draw water ripple
  +
  JSR Sprite_Floater_Draw

  LDA $0ED0, X : BNE +
  JSL $06DC54 ; shadow
  +

  JSR Sprite_CheckIfActive

  LDA.w $0ED0, X : BEQ .noFishOnLine ; is the floater in water?


  LDA.w $0EE0, X : BNE .noWigglingYet; timerD wait until fish is on line

  LDA.w $0DB0, X : BNE .fishOnlineWait
  ; start another random timer for the time it'll last
  JSL $0DBA71 : AND #$3F ; GetRandomInt
  CLC : ADC.b #$0F : STA.w $0DF0, X ; wiggling timer
  INC.w $0DB0, X ; we have a fish on line

  .noWigglingYet


  LDA.w $0DB0, X : BEQ .noFishOnLine ; do we already have a fish on line?
  .fishOnlineWait
  LDA.w $0DF0, X : BNE .stillwiggling
  STZ.w $0DB0, X ; no more fish on line took too much time
  JSL $0DBA71 : AND.b #$7F ; GetRandomInt
  CLC : ADC.b #$7F : STA.w $0EE0, X ; reset timer wait until fish is on line
  STZ.w $0D50, X
  STZ.w $0D40, X
  BRA .noFishOnLine
  .stillwiggling



  LDY.w $0E10, X
  LDA.w WigglingTable, Y : STA.w $0D50,X
  LDA.w WigglingTable, Y : STA.w $0D40,X
  LDY.w $0E10, X : BNE + ; use timer to do wiggling
  ; if = 0 then put it back to F
  LDA.b #$0F : STA.w $0E10, X ; wiggling timer
  +




  .noFishOnLine



  JSL $1D808C ; Sprite_Move_XY
  JSL Sprite_MoveAltitude

  LDA.w $0F80,X
  SEC
  SBC.b #$01
  STA.w $0F80,X

  LDA.w $0F70,X
  BPL .aloft

  STZ.w $0F70,X

  LDA.w $0D50,X
  ASL A
  ROR.w $0D50,X

  LDA.w $0D40,X
  ASL A
  ROR.w $0D40,X

  LDA.w $0F80,X
  EOR.b #$FF
  INC A

  LSR A
  CMP.b #$09
  BCS .no_bounce



  LDA.w $0E90, X : BNE .not_water_tileLast
  INC.w $0E90, X 
  JSL $06E496 ; Sprite_CheckTileCollision
  LDA.w $0FA5
  CMP.b #$08 ; TILETYPE 08
  BEQ .water_tileLast
  CMP.b #$09 ; TILETYPE 09
  BNE .not_water_tileLast
  .water_tileLast
  INC.w $0ED0, X ; Set that so we know floater is in water!
  JSL $1EA820 ; Sprite_SpawnSmallSplash

  JSL $0DBA71 : AND #$3F ; GetRandomInt
  CLC : ADC #$3F : STA.w $0EE0, X

  .not_water_tileLast
  STZ.w $0F80,X
  STZ.w $0D50,X
  STZ.w $0D40,X

  BRA .aloft

  .no_bounce
  STA.w $0F80,X

  JSL $06E496 ; Sprite_CheckTileCollision
  LDA.w $0FA5
  CMP.b #$08 ; TILETYPE 08
  BEQ .water_tile

  CMP.b #$09 ; TILETYPE 09
  BNE .not_water_tile

  .water_tile
  ;STZ.w $0F80,X

  JSL $1EA820 ; Sprite_SpawnSmallSplash

  .not_water_tile
  .aloft

  LDA.b #$01 : STA.w $0E70, X ; restore floater sprite seems to be overwriten
  RTS
}

Sprite_Floater_Draw:
{
  LDA.b #$4 ; 1 oam slots
  JSL $0DBA88 ; SpriteDraw_AllocateOAMFromRegionC
  JSL $06E416 ; Sprite_PrepOamCoord
  REP #$20

  LDA.b $00 : STA.b ($90),Y
  CLC : AND.w #$0100 : STA.b $0E

  LDA.b $02 : INY
  STA.b ($90),Y
  CMP.w #$0100
  SEP #$20
  BCC .on_screen

  LDA.b #$F0 : STA.b ($90),Y

  .on_screen

  LDA.b #$0C : INY : STA.b ($90),Y

  LDA.b #$32 : INY : STA.b ($90),Y

  LDA.b #$02 : STA.b ($92)

  RTS
}


WigglingTable:
db 08, -10, 06, -8, 12, -14, 18, -20, 10, -12, 04, -6, 08,-10, 14,-16, 08, -10, 06, -8, 12, -14, 18, -20, 10, -12, 04, -6, 08,-10, 14,-16

DismissRodFromMenu:
{
  STZ.w $0300
  STZ.b $3D
  LDA #$00
  STA.l $7F5BA2
  LDA.l $7F5BA3 : TAX
  STZ.w $0DD0, X
  STZ.b $5E
  STZ.w $0300
  STZ.b $3D
  STZ.w $0350
  STZ.w $037A
  LDA.b $3A
  AND.b #$BF
  STA.b $3A
  RTL
}

print  "End of Items/fishing_rod.asm      ", pc