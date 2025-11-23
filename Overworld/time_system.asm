; ---------------------[ Time system ]---------------------

; tiles locations on HUD
!hud_min_low = $7EC7CC
!hud_min_high = $7EC7CA
!hud_hours_low = $7EC7C6
!hud_hours_high = $7EC7C4

; HUD Template adjusts timer's color
org $0DFF07
  db $10, $24, $11, $24
  db $6C, $25
  db $90, $24, $90, $24
  db $6C, $25, $90, $24, $90, $24

; Sprite_Main.dont_reset_drag
; Executes every frame to update the clock
org $068361
  JSL HUD_ClockDisplay
pullpc
HUD_ClockDisplay:
{
  JSR RunClock
  JSR DrawClockToHud
  JSL $09B06E ; Restore Garnish_ExecuteUpperSlots_long
  RTL
}

; Zarby Intro and Credits fix
pushpc
org $0CC265 ; Intro_FadeLogoIn
  JSL LogoFadeInSetClock
pullpc
LogoFadeInSetClock:
{
  JSL $00ED7C ; IntroLogoPaletteFadeIn
  LDA.b #$08 : STA.l TimeState.Hours ; Set the time to 6:00am
  LDA.b #$3F : STA.l TimeState.Speed ; Set the time speed
  RTL
}

pushpc
org $0CCA59
  JSL ResetClockTriforceRoom
pullpc
ResetClockTriforceRoom:
{
  JSL $00E384 ; LoadCommonSprites_long
  LDA.b #$00 : STA.l TimeState.Hours ; low hours for palette?
  LDA.b #$00 : STA.l TimeState.Minutes ; high hours for palette?
  RTL
}

DrawClockToHudLong:
{
  JSR DrawClockToHud
  RTL
}

DrawClockToHud:
{
  LDX #$00
  .debut
  LDY #$00 : LDA TimeState.Hours,x
  .debut2
  CMP #$0A : BMI .draw
    SBC #$0A : INY : BRA .debut2
  .draw
  ADC #$90 : CPX #$01 : BEQ .minutes_low
    STA.l !hud_hours_low
    LDA #$30 : STA.l !hud_hours_low+1 ; white palette
    BRA .continue_draw ; 04
  .minutes_low
  STA.l !hud_min_low
  LDA #$30 : STA.l !hud_min_low+1 ; white palette
  .continue_draw
  TYA
  CLC : ADC #$90 : CPX #$01 : BEQ .minutes_high
    STA.l !hud_hours_high
    LDA #$30 : STA.l !hud_hours_high+1 ; white palette
    BRA .finish_draw ; 04
  .minutes_high
  STA.l !hud_min_high
  LDA #$30 : STA.l !hud_min_high+1 ; white palette
  .finish_draw
  INX : CPX #$02 : BMI .debut
  RTS
}

; =========================================================

Overworld_SetFixedColAndScroll = $0BFE70
Overworld_SetFixedColAndScroll_AltEntry = $0BFE72

RunClock:
{
  JSR TimeSystem_CheckCanRun : BCC .return

  JSR TimeSystem_UpdateGBCLink
  JSR CheckForSongOfTime
  
  JSR TimeSystem_IncrementTime : BCC .return

  JSR TimeSystem_UpdatePalettes

  .return
  RTS
}

TimeSystem_CheckCanRun:
{
  ; checks current event in game
  LDA $10 : CMP #$07 : BEQ .counter_increasing ; dungeon/building?
            CMP #$09 : BEQ .overworld ; overworld?
            CMP #$0B : BEQ .overworld ; special overworld?
            CMP #$0E : BEQ .dialog  ; dialog box?
              CLC : RTS
    .overworld
    ; Reload Sprite Gfx Properties
    JSL $00FC62 ; Sprite_LoadGraphicsProperties

    LDA $11 : CMP #$23 : BNE .mosaic ; HDMA transfer? (warping)
      ; Lol what?
    .mosaic

    CMP #$0D : BMI .counter_increasing ; Mosaic ?
      CLC : RTS

    .dialog
    ; check submodule to prevent the counter from increasing if save/menu open
    LDA $11 : CMP #$02 : BEQ .counter_increasing ; NPC/signs speech
      CLC : RTS

  .counter_increasing
  SEC : RTS
}

TimeSystem_UpdateGBCLink:
{
  ; GBC Link code
  LDA $0FFF : CMP #$00 : BEQ .light_world
    LDA $02B2 : BNE .already_gbc_or_minish
      JSL UpdateGbcPalette
      LDA.b #$3B : STA $BC   ; change link's sprite
      LDA.b #$06 : STA $02B2 ; set the form id
  .light_world
  .already_gbc_or_minish
  RTS
}

TimeSystem_IncrementTime:
{
  ; time speed (1,3,5,7,F,1F,3F,7F,FF)
  ; #$3F is almost 1 sec = 1 game minute
  LDA $1A : AND TimeState.Speed : BEQ .increase_minutes ; 05
    CLC : RTS

  .increase_minutes
  LDA.l TimeState.Minutes : INC A : STA.l TimeState.Minutes
  CMP #$3C : BPL .increase_hours ; minutes = 60 ?
    CLC : RTS

  .increase_hours
  LDA #$00 : STA.l TimeState.Minutes
  LDA.l TimeState.Hours : INC A : STA.l TimeState.Hours
  CMP #$18 : BPL .reset_hours ; hours = 24 ?
    SEC : RTS

  .reset_hours
  JSR CheckForDailyQuests
  LDA.b #$00 : STA.l TimeState.Hours
  SEC : RTS
}

TimeSystem_UpdatePalettes:
{
    ; check indoors/outdoors
    LDA $1B	: BEQ .outdoors
      RTS
    .outdoors

    JSL RomToPaletteBuffer	; update buffer palette
    JSL PaletteBufferToEffective	; update effective palette

    ; rain layer ?
    LDA $8C : CMP #$9F : BEQ .skip_bg_updt
      LDA $8C : CMP #$9E : BEQ .skip_bg_updt	; canopy layer ?
        CMP #$97 : BEQ .skip_bg_updt	; fog layer?
        JSL Overworld_SetFixedColAndScroll ; update background color
        RTS

    .skip_bg_updt ; prevent the sub layer from disappearing ($1D zeroed)
    JSL Overworld_SetFixedColAndScroll_AltEntry
    RTS
}

CheckForSongOfTime:
{
  ; Check if Song of Time was activated
  LDA.b SongFlag : CMP.b #$02 : BNE +
    ; Speed up the time
    LDA.b #$00 : STA.l TimeState.Speed

    ; If we reached 6am
    LDA.l TimeState.Hours : CMP.b #$06 : BNE ++
      LDA.l TimeState.Minutes : BNE ++
        LDA.b #$3F : STA.l TimeState.Speed
        STZ.b SongFlag
    ++

    ; If we reached 6pm
    LDA.l TimeState.Hours : CMP.b #$12 : BNE ++
      LDA.l TimeState.Minutes : BNE ++
        LDA.b #$3F : STA.l TimeState.Speed
        STZ.b SongFlag
    ++
  +
  RTS
}

CheckForDailyQuests:
{
  LDA.l MagicBeanProg : CMP.b #$7F : BEQ .bean_done
                        AND.b #$01 : BEQ .bean_done
    LDA.l MagicBeanProg : AND.b #$08 : BNE .not_first
      LDA.b #$08 : JMP +
    .not_first
    LDA.l MagicBeanProg : AND.b #$10 : BNE .not_second
      LDA.b #$10 : JMP +
    .not_second
    LDA.l MagicBeanProg : AND.b #$20 : BNE .bean_done
      LDA.b #$20
    +
    ORA.l MagicBeanProg : STA.l MagicBeanProg
    LDA.b #$2D : STA.w $012F
  .bean_done
  RTS
}

CheckIfNight:
{
  JSR LoadPeacetimeSprites : BCS +
    RTL
  +
  LDA.l GameState : CMP.b #$02 : BCC .day_time
    LDA TimeState.Hours : CMP.b #$12 : BCS .night_time
      LDA TimeState.Hours : CMP.b #$06 : BCC .night_time
      .day_time
      LDA.l GameState
      RTL
  .night_time
  LDA.b #$03
  RTL
}

CheckIfNight16Bit:
{
  SEP #$30
  JSR LoadPeacetimeSprites : BCS +
    REP #$30
    RTL
  +
  REP #$30
  ; Don't change the spriteset during the intro sequence
  LDA.l GameState : AND.w #$00FF : CMP.w #$0002 : BCC .day_time
    ; 0x12 = 18 hours or 6 pm
    LDA TimeState.Hours : AND.w #$00FF : CMP.w #$0012 : BCS .night_time
      ; If it's less than 6 am, jump to night time
      LDA TimeState.Hours : AND.w #$00FF : CMP.w #$0006 : BCC .night_time
      .day_time
      LDA.l GameState
      RTL
  .night_time
  ; Load the gamestate 03 spritesets, but don't change the save ram
  LDA.l GameState : CLC : ADC #$0001
  RTL
}

pushpc

; Overworld_LoadSprites
; Temporarily commented out while porting to ZSOWv3
; org $09C4E3 : JSL CheckIfNight

; Sprite_LoadGraphicsProperties_light_world_only
; Temporarily commented out while porting to ZSOWv3
; org $00FC6A : JSL CheckIfNight16Bit

; =========================================================
; ----[ Day / Night system * palette effect ]----
; =========================================================

Overworld_CopyPalettesToCache = $02C769

org $02FF80 ; free space on bank $02
PaletteBufferToEffective:
  ; JSR $C769	; $02:C65F -> palette buffer to effective routine
  JSR $C65F
  RTL

OverworldPalettesScreenToSet_New           = $09C635 ; $04C635
OverworldPalettesLoader = $0ED5A8

; rom to palette buffer for other colors
OverworldLoadScreensPaletteSet = $02C692

; From OverworldHandleTransitions.change_palettes $02AAF4
; Change buffer palette of trees,houses,rivers,etc.
RomToPaletteBuffer:
{
  LDX.b $8A
  LDA.l $7EFD40,X : STA.b $00

  LDA.l OverworldPalettesScreenToSet_New,X
  JSL OverworldPalettesLoader
  JSR Overworld_CopyPalettesToCache
  JSR OverworldLoadScreensPaletteSet 
  RTL
}

PalBuf300_HUD = $7EC300
PalBuf340_BG = $7EC340
PalBuf400_Spr = $7EC400

PalCgram500_HUD = $7EC500
PalCgram540_BG = $7EC540
PalCgram600_Spr = $7EC600

; Palettes_LoadSingle.next_color
org $1BEF3D : JSL LoadDayNightPaletteEffect

; Palettes_LoadMultiple.next_color
org $1BEF61 : JSL LoadDayNightPaletteEffect

; Palettes_LoadMultiple_Arbitrary.next_color
org $1BEF84 : JSL LoadDayNightPaletteEffect

pullpc
LoadDayNightPaletteEffect:
{
  STA.l TimeState.SubColor : CPX #$0041 : BPL .title_check
    STA.l PalBuf300_HUD, X
    RTL
  .title_check

  ; title or file select screen ?
  LDA $10 : AND #$00FF : CMP #$0002	: BCS .outin_check
    LDA.l TimeState.SubColor
    STA.l PalBuf300_HUD, X
    RTL
  .outin_check

  LDA.b $10 : AND #$00FF : CMP.w #$0005 : BCC .restorecode
                           CMP.w #$0012 : BCS .restorecode
    BRA .overworld
  .restorecode
  LDA.l TimeState.SubColor
  STA.l PalBuf300_HUD, X
  RTL

  .overworld
  LDA $1B : AND #$00FF : BEQ .outdoors2
    LDA.l TimeState.SubColor
    STA.l PalBuf300_HUD,X
    RTL
  .outdoors2

  PHX
  JSL ColorSubEffect
  PLX
  STA.l PalBuf300_HUD, X
  RTL
}

; =========================================================

!SmallestBlue = #$0400
!SmallestGreen = #$0020
!SmallestRed = #$0001

ColorSubEffect:
{
  LDA.l TimeState.Hours : AND #$00FF : CLC : ADC.l TimeState.Hours	; hours * 2
  AND #$00FF : TAX

  ; Subtract amount to blue field based on a table
  LDA.l TimeState.SubColor : AND #$7C00 : STA.l TimeState.BlueVal
  SEC : SBC.l .blue, X : STA.l TimeState.TempColor

  ; mask out everything except the blue bits
  AND #$7C00 : CMP.l TimeState.TempColor : BEQ .no_blue_sign_change ; overflow ?
    LDA.l !SmallestBlue
  .no_blue_sign_change
  STA.l TimeState.BlueVal

  ; Subtract amount to green field based on a table
  LDA.l TimeState.SubColor : AND #$03E0 : STA.l TimeState.GreenVal
  SEC : SBC.l .green, X : STA.l TimeState.TempColor

  ; Mask out everything except the green bits
  AND #$03E0 : CMP.l TimeState.TempColor : BEQ .no_green_sign_change ; overflow ?
    LDA.l !SmallestGreen
  .no_green_sign_change
  STA.l TimeState.GreenVal

  ; substract amount to red field based on a table
  LDA.l TimeState.SubColor : AND #$001F : STA.l TimeState.RedVal
  SEC : SBC.l .red, X : STA.l TimeState.TempColor

  ; mask out everything except the red bits
  AND #$001F : CMP.l TimeState.TempColor : BEQ .no_red_sign_change ; overflow ?
    LDA.l !SmallestRed
  .no_red_sign_change
  STA.l TimeState.RedVal

  LDA.l TimeState.BlueVal : ORA.l TimeState.GreenVal : ORA.l TimeState.RedVal
  RTL

  ; color_sub_tables : 24 * 2 bytes each = 48 bytes
  ; (2 bytes = 1 color sub for each hour)

  .blue:
    dw $1000, $1000, $1000, $1000
    dw $1000, $1000, $1000, $0800
    dw $0000, $0000, $0000, $0000
    dw $0000, $0000, $0000, $0000
    dw $0000, $0400, $0800, $0800
    dw $0800, $1000, $1000, $1000

  .green:
    dw $0100, $0100, $0100, $0100
    dw $0100, $00C0, $0080, $0040
    dw $0000, $0000, $0000, $0000
    dw $0000, $0000, $0000, $0000
    dw $0000, $0020, $0040, $0080
    dw $00C0, $0100, $0100, $0100

  .red:
    dw $0008, $0008, $0008, $0008
    dw $0008, $0006, $0004, $0002
    dw $0000, $0000, $0000, $0000
    dw $0000, $0000, $0000, $0000
    dw $0000, $0000, $0000, $0002
    dw $0004, $0006, $0008, $0008
}

BackgroundFix:
{
  BEQ .no_effect		;BRAnch if A=#$0000 (transparent bg)
    JSL ColorSubEffect
  .no_effect:
  STA.l PalCgram500_HUD
  STA.l PalBuf300_HUD
  STA.l PalCgram540_BG
  STA.l PalBuf340_BG
  RTL
}

MosaicFix:
{
  BEQ +
    JSL ColorSubEffect
  +
  STA.l PalBuf300_HUD
  STA.l PalBuf340_BG
  RTL
}

SubAreasFix:
{
  BEQ .no_effect
  STA.l TimeState.SubColor
  PHX
    REP #$20
      JSL ColorSubEffect
    SEP #$20
  PLX
  .no_effect
  STA.l PalBuf300_HUD
  STA.l PalBuf340_BG
  RTL
}

GlovePalettePosition = $7EC4FA

GlovesFix:
{
  STA.l TimeState.SubColor
  LDA $1B : AND #$00FF : BEQ .outdoors3
    LDA.l TimeState.SubColor
    STA GlovePalettePosition
    RTL

  .outdoors3:
  PHX
  JSL ColorSubEffect
  PLX
  STA GlovePalettePosition
  RTL
}

ColorBgFix:
{
  PHA
  SEP #$30
  ; Check for save and quit
  LDA.b $10 : CMP.b #$17 : BEQ .vanilla
    REP #$30
    PLA
    STA.l TimeState.SubColor
    JSL ColorSubEffect
    STA.l PalCgram500_HUD
    STA.l PalCgram540_BG
    RTL
  .vanilla
  REP #$30
  PLA
  STA.l PalCgram500_HUD
  RTL
}

LoadPeacetimeSprites:
{
  ; Map 2E, 2F if Crystals && 0x10 == 0
  LDA $8A : CMP.b #$2E : BEQ .tail_palace
            CMP.b #$2F : BEQ .tail_palace
            CMP.b #$1E : BEQ .zora_sanctuary
    JMP +
  .tail_palace
  LDA.l Crystals : AND #$10 : BNE .load_peacetime
  JMP +
  .zora_sanctuary
  LDA.l Crystals : AND #$20 : BNE .load_peacetime
  JMP +
  .load_peacetime
  LDA.b #$01
  CLC
  RTS
  +
  SEC
  RTS
}

FixSaveAndQuit:
{
  LDA.b #$08 : STA.l TimeState.Hours
  LDA.l GameState
  RTL
}

FixShockPalette:
{
  PHA
  LDA.b $1B : BNE .indoors
    PLA
    STA TimeState.SubColor
    PHX
    JSL ColorSubEffect
    PLX
    STA.l PalCgram500_HUD, X
    RTL
  .indoors
  PLA
  RTL
}

FixDungeonMapColors:
{
  PHA
  ; Cache the current time
  LDA TimeState.Hours : STA $7EF900
  LDA TimeState.Minutes : STA $7EF901
  ; Set the time to 8:00am while map is open
  LDA.b #$08 : STA TimeState.Hours
  LDA.b #$00 : STA TimeState.Minutes
  PLA
  STA.l $7EC229
  RTL
}

RestoreTimeForDungeonMap:
{
  LDA $7EF900 : STA TimeState.Hours
  LDA $7EF901 : STA TimeState.Minutes
  LDA.l $7EC017
  RTL
}

pushpc

; SetBGColorMainBuffer
org $0ED5F9 : JSL ColorBgFix

; OverworldMosaicTransition_HandleScreensAndLoadShroom
org $02AE92 : NOP #6

; =========================================================

; Subareas background color fix (under the bridge; zora...)
; $0E/D601 8F 00 C3 7E STA $7EC300[$7E:C300]
; $0E/D605 8F 40 C3 7E STA $7EC340[$7E:C340]

; Temporarily commented out while porting to ZSOWv3
; org $0ED601 : JSL SubAreasFix

; =========================================================
; Gloves color loading routine
; $1B/EE1B C2 30       REP #$30
; $1B/EE1D AF 54 F3 7E LDA $7EF354[$7E:F354]
; $1B/EE21 29 FF 00    AND #$00FF
; $1B/EE24 F0 0F       BEQ $0F    [$EE35]
; $1B/EE26 3A          DEC A
; $1B/EE27 0A          ASL A
; $1B/EE28 AA          TAX
; $1B/EE29 BF F5 ED 1B LDA $1BEDF5,x[$1B:EDF7]
; $1B/EE2D 8F FA C4 7E STA $7EC4FA[$7E:C4FA]
; $1B/EE31 8F FA C6 7E STA $7EC6FA[$7E:C6FA]
; $1B/EE35 E2 30       SEP #$30
; $1B/EE37 E6 15       INC $15    [$00:0015]
; $1B/EE39 6B          RTL

; Palettes_Load_LinkGloves
org $1BEE2D : JSL GlovesFix

; org $0ABA5A
; TODO: Handle overworld map palette for flashing icons

; Module0E_03_00_DarkenAndPrep
org $0ED956 : JSL FixDungeonMapColors

; UnderworldMap_RecoverGFX
org $0AEFA6 : JSL RestoreTimeForDungeonMap

; RefreshLinkEquipmentPalettes
org $0ED745 : JSL FixShockPalette

; GameOver_SaveAndQuit:
org $09F604 : JSL FixSaveAndQuit