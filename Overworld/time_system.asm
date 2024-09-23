; ---------------------[ Time system ]---------------------

; tiles locations on HUD
!hud_min_low = $7EC7CC
!hud_min_high = $7EC7CA
!hud_hours_low = $7EC7C6
!hud_hours_high = $7EC7C4
!hud_template = $0DFF07

Hours = $7EE000
Minutes = $7EE001
TimeSpeed = $7EE002

org !hud_template
	db $10,$24,$11,$24
  db $6C,$25
  db $90,$24,$90,$24
  db $6C,$25,$90,$24,$90,$24	; HUD Template(adjusts timer's color)

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
  LDA.b #$08 : STA.l $7EE000 ; Set the time to 6:00am
  LDA.b #$3F : STA.l $7EE002 ; Set the time speed
  RTL
}

pushpc
org $0CCA59
  JSL ResetClockTriforceRoom
pullpc
ResetClockTriforceRoom:
{
  JSL $00E384 ; LoadCommonSprites_long
  LDA.b #$00 : STA.l $7EE000 ; low hours for palette?
  LDA.b #$00 : STA.l $7EE001 ; high hours for palette?
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
    LDY #$00 : LDA $7EE000,x

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

RunClock:
{
  LDA $10	; checks current event in game
  CMP #$07 : BEQ .counter_increasing ; dungeon/building?
    CMP #$09 : BEQ .overworld ; overworld?
    CMP #$0B : BEQ .overworld ; sub-area ? (under the bridge; zora domain...)
      CMP #$0E : BEQ .dialog  ; dialog box?
        RTS
    .overworld
    ; Reload Sprite Gfx Properties
    JSL $00FC62 ; Sprite_LoadGraphicsProperties

    LDA $11 : CMP #$23 : BNE .mosaic ; HDMA transfer? (warping)
      ; Lol what?
    .mosaic

    CMP #$0D : BMI .counter_increasing ; Mosaic ?
      RTS

    .dialog
    LDA $11 ; check submodule to prevent the counter from increasing if save/menu open
    CMP #$02 : BEQ .counter_increasing ; NPC/signs speech
      RTS

  .counter_increasing
  ; GBC Link code
  LDA $0FFF : CMP #$00 : BEQ .light_world
    LDA $02B2 : CMP.b #$05 : BCS .already_gbc_or_minish
      JSL UpdateGbcPalette
      LDA.b #$3B : STA $BC   ; change link's sprite
      LDA.b #$06 : STA $02B2 ; set the form id
  .light_world
  .already_gbc_or_minish

  JSR CheckForSongOfTime
  ; time speed (1,3,5,7,F,1F,3F,7F,FF)
  ; #$3F is almost 1 sec = 1 game minute
  LDA $1A : AND TimeSpeed : BEQ .increase_minutes ; 05
    .end
    RTS

  .increase_minutes
  LDA $7EE001 : INC A : STA $7EE001
  CMP #$3C : BPL .increase_hours ; minutes = #60 ?
    RTS

  .increase_hours
  LDA #$00 : STA $7EE001
  LDA $7EE000 : INC A : STA $7EE000
  CMP #$18 : BPL .reset_hours ; hours = #24 ?
    ;check indoors/outdoors
    LDA $1B	: BEQ .outdoors0
      RTS

    .outdoors0

    JSL rom_to_buff	; update buffer palette
    JSL buff_to_eff	; update effective palette

    ;rain layer ?
    LDA $8C : CMP #$9F : BEQ .skip_bg_updt0
      LDA $8C : CMP #$9E : BEQ .skip_bg_updt0	; canopy layer ?
        CMP #$97 : BEQ .skip_bg_updt0	; fog layer?
        JSL $0BFE70	; update background color
        BRA .inc_hours_end

    .skip_bg_updt0 ; prevent the sub layer from disappearing ($1D zeroed)
    JSL $0BFE72

    .inc_hours_end
    RTS

  .reset_hours

  LDA #$00 : STA $7EE000

  ; check indoors/outdoors
  LDA $1B	: BEQ .outdoors1
    RTS
  .outdoors1

  JSL rom_to_buff
  JSL buff_to_eff

  LDA $8C : CMP #$9F : BEQ .skip_bg_updt1 ; rain layer ?
    LDA $8C : CMP #$9E : BEQ .skip_bg_updt1	; canopy layer ?
      JSL $0BFE70 ; update background color
      BRA .reset_end

  .skip_bg_updt1 ; prevent the sub layer from disappearing ($1D zeroed)

  JSL $0BFE72

  .reset_end
  RTS
}

CheckForSongOfTime:
{
  LDA $FE : CMP.b #$02 : BNE +
    LDA.b #$00 : STA.l $7EE002

    LDA.l $7EE000 : CMP.b #$06 : BNE ++
      LDA.l $7EE001 : BNE ++
        LDA.b #$3F : STA.l $7EE002
        STZ $FE
    ++

    LDA.l $7EE000 : CMP.b #$12 : BNE ++
      LDA.l $7EE001 : BNE ++
        LDA.b #$3F : STA.l $7EE002
        STZ $FE
    ++
  +
  RTS
}

pushpc

; =========================================================
;----[ Day / Night system * palette effect ]----
; =========================================================

!blue_value = $7EE010
!green_value = $7EE012
!red_value = $7EE014

!temp_value = $7EE016
!pal_color = $7EE018

org $02FF80		; free space on bank $02
buff_to_eff:
	JSR $C769	; $02:C65F -> palette buffer to effective routine
	RTL

rom_to_buff:
	JSR $AAF4	; $02:AAF4 -> change buffer palette of trees,houses,rivers,etc.
	JSR $C692	; $02:C692 -> rom to palette buffer for other colors
	RTL

PaletteBuffer_HUD = $7EC300
PaletteBuffer_BG = $7EC340
PaletteBuffer_Spr = $7EC400

PaletteCgram_HUD = $7EC500
PaletteCgram_BG = $7EC540
PaletteCgram_Spr = $7EC600

; part of rom pal to buffer routine
; $1B/EF61 9F 00 C3 7E STA $7EC300,x[$7E:C422]
; $1B/EF3D 9F 00 C3 7E STA $7EC300,x[$7E:C412]
; $1B/EF84 9F 00 C3 7E STA $7EC300,x[$7E:C4B2]

; Palettes_LoadSingle.next_color
org $1BEF3D
	JSL LoadDayNightPaletteEffect

; Palettes_LoadMultiple.next_color
org $1BEF61
	JSL LoadDayNightPaletteEffect

; Palettes_LoadMultiple_Arbitrary.next_color
org $1BEF84
	JSL LoadDayNightPaletteEffect

pullpc
LoadDayNightPaletteEffect:
{
  STA.l !pal_color

  CPX #$0041 : BPL .title_check
    STA PaletteBuffer_HUD,X
    RTL
  .title_check

  ; title or file select screen ?
  LDA $10 : AND #$00FF : CMP #$0002	: BCS .outin_check
    LDA.l !pal_color : STA PaletteBuffer_HUD,X
    RTL

  .outin_check
  LDA.b $10 : AND #$00FF
    CMP.w #$0005 : BCC .restorecode
    CMP.w #$0012 : BCS .restorecode
    BRA .overworld
  .restorecode
    LDA.l !pal_color : STA.l PaletteBuffer_HUD, X
    RTL
  .overworld

  LDA $1B : AND #$00FF : BEQ .outdoors2
    LDA.l !pal_color
    STA PaletteBuffer_HUD,X
    RTL

  .outdoors2

  PHX
  JSL ColorSubEffect
  PLX
  STA.l PaletteBuffer_HUD,X
  RTL
}

; =========================================================

ColorSubEffect:
{
	LDA $7EE000		; LDA #hours
	AND #$00FF
	CLC
	ADC $7EE000		; #hours * 2
	AND #$00FF
	TAX

  .do_blue
	LDA.l !pal_color : AND #$7C00 : STA !blue_value
  ; Subtract amount to blue field based on a table
	SEC : SBC.l blue_table, X : STA !temp_value
  ; mask out everything except the blue bits
	AND #$7C00 : CMP !temp_value : BEQ .no_blue_sign_change ; overflow ?
    .blue_sign_change
    LDA #$0400		; LDA smallest blue value

  .no_blue_sign_change
	STA.l !blue_value

  do_green:
	LDA !pal_color : AND #$03E0 : STA !green_value
	SEC : SBC.l green_table,x	; Subtract amount to blue field based on a table
	STA.l !temp_value
  ; Mask out everything except the green bits
	AND #$03E0 : CMP !temp_value : BEQ .no_green_sign_change ; overflow ?
    .green_sign_change
    LDA #$0020		; LDA smallest green value

  .no_green_sign_change
	STA.l !green_value

  .do_red
	LDA.l !pal_color : AND #$001F : STA.l !red_value
	SEC : SBC.l red_table,x		; substract amount to red field based on a table
	STA.l !temp_value
	AND #$001F		; mask out everything except the red bits
	CMP !temp_value : BEQ .no_red_sign_change ; overflow ?
    .red_sign_change
    LDA #$0001		; LDA smallest red value

  .no_red_sign_change
	STA.l !red_value

	LDA.l !blue_value
	ORA.l !green_value
	ORA.l !red_value

	RTL
}

; =========================================================

; color_sub_tables : 24 * 2 bytes each = 48 bytes (2 bytes = 1 color sub for each hour)

blue_table:
	dw $1000, $1000, $1000, $1000
  dw $1000, $1000, $1000, $0800
  dw $0000, $0000, $0000, $0000
  dw $0000, $0000, $0000, $0000
  dw $0000, $0400, $0800, $0800
  dw $0800, $1000, $1000, $1000

green_table:
	dw $0100, $0100, $0100, $0100
  dw $0100, $00C0, $0080, $0040
  dw $0000, $0000, $0000, $0000
  dw $0000, $0000, $0000, $0000
  dw $0000, $0020, $0040, $0080
  dw $00C0, $0100, $0100, $0100

red_table:
	dw $0008, $0008, $0008, $0008
  dw $0008, $0006, $0004, $0002
  dw $0000, $0000, $0000, $0000
  dw $0000, $0000, $0000, $0000
  dw $0000, $0000, $0000, $0002
  dw $0004, $0006, $0008, $0008

BackgroundFix:
{
  BEQ .no_effect		;BRAnch if A=#$0000 (transparent bg)
    JSL ColorSubEffect

  .no_effect:
  STA.l PaletteCgram_HUD
  STA.l PaletteBuffer_HUD
  STA.l PaletteCgram_BG
  STA.l PaletteBuffer_BG
  RTL
}

SubAreasFix:
{
  BEQ .no_effect
	STA.l !pal_color
	PHX
    REP #$20
      JSL ColorSubEffect
    SEP #$20
	PLX
  .no_effect
	STA.l PaletteBuffer_HUD
	STA.l PaletteBuffer_BG
	RTL
}

GlovePalettePosition = $7EC4FA

GlovesFix:
{
	STA.l !pal_color
	LDA $1B : AND #$00FF : BEQ .outdoors3
    LDA.l !pal_color
    STA GlovePalettePosition
    RTL

  .outdoors3:
	PHX
	JSL ColorSubEffect
	PLX
	STA GlovePalettePosition
	RTL
}

CheckIfNight:
{
  JSR LoadPeacetimeSprites : BCS +
    RTL
  +
  LDA.l $7EF3C5 : CMP.b #$02 : BCC .day_time
  LDA $7EE000 : CMP.b #$12 : BCS .night_time
  LDA $7EE000 : CMP.b #$06 : BCC .night_time
    .day_time
    LDA.l $7EF3C5
    RTL
  .night_time
    LDA.b #$03
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
  JSL ColorSubEffect
  STA.l PaletteCgram_HUD
  STA.l PaletteCgram_BG
  RTL

  .vanilla
  REP #$30
  PLA
  STA.l PaletteCgram_HUD
  RTL
}

CheckIfNight16Bit:
{
  JSR LoadPeacetimeSprites : BCS +
    RTL
  +
  ; Don't change the spriteset during the intro sequence
  LDA.l $7EF3C5 : AND.w #$00FF : CMP.w #$0002 : BCC .day_time
    ; 0x12 = 18 hours or 6 pm
    LDA $7EE000 : AND.w #$00FF : CMP.w #$0012 : BCS .night_time
      ; If it's less than 6 am, jump to night time
      LDA $7EE000 : AND.w #$00FF : CMP.w #$0006 : BCC .night_time
  .day_time
  LDA.l $7EF3C5
  RTL
  .night_time
  ; Load the gamestate 03 spritesets, but don't change the save ram
  LDA.l $7EF3C5 : CLC : ADC #$0001
  RTL
}

LoadPeacetimeSprites:
{
  ; Map 2E, 2F if CRYSTALS && 0x10 == 0
  LDA $8A : CMP.b #$2E : BEQ .tail_palace
            CMP.b #$2F : BEQ .tail_palace
    JMP +
  .tail_palace
  LDA.l CRYSTALS : AND #$10 : BNE .load_peacetime
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
  LDA #$08 : STA $7EE000
  LDA.l $7EF3C5
  RTL
}

FixShockPalette:
{
  PHA
  LDA $1B : BNE .indoors
  PLA
  STA !pal_color
  PHX
  JSL ColorSubEffect
  PLX
  STA.l PaletteCgram_HUD, X
  RTL
  .indoors
  PLA
  RTL
}

FixDungeonMapColors:
{
  PHA
  ; Cache the current time
  LDA $7EE000 : STA $7EF900
  LDA $7EE001 : STA $7EF901
  ; Set the time to 8:00am while map is open
  LDA #$08 : STA $7EE000
  LDA #$00 : STA $7EE001

  PLA
  STA $7EC229
  RTL
}

RestoreTimeForDungeonMap:
{
  ; Restore the time
  LDA $7EF900 : STA $7EE000
  LDA $7EF901 : STA $7EE001
  LDA.l $7EC017
  RTL
}

pushpc

; Overworld_LoadSprites
org $09C4E3
  JSL CheckIfNight

; Sprite_LoadGraphicsProperties_light_world_only
org $00FC6A
  JSL CheckIfNight16Bit


; $0BFE70 -> background color loading routine
;Background color write fix - 16 bytes
;$0B/FEB6 8F 00 C5 7E STA $7EC500
;$0B/FEBA 8F 00 C3 7E STA $7EC300
;$0B/FEBE 8F 40 C5 7E STA $7EC540
;$0B/FEC2 8F 40 C3 7E STA $7EC340

if ZS_CUSTOM_OW_V2 == 0
; Custom BG Color Mosaic Background Color fix
org $028464
  NOP #6
else
; SetBGColorMainBuffer
org $0ED5F9
  JSL ColorBgFix
endif

; OverworldMosaicTransition_HandleScreensAndLoadShroom
org $02AE92
  NOP #6

; =========================================================

; org $0BFEB6 VANILLA DAY/NIGHT HOOK

; ZS OW - ReplaceBGColor
if ZS_CUSTOM_OW_V2 == 0
org $2886B4
  STA !pal_color
  JSL BackgroundFix
  ;NOP #8
endif

; ZS OW - CheckForChangeGraphicsTransitionLoad
if ZS_CUSTOM_OW_V2 == 1
org $289447
	JSL SubAreasFix
else
org $2885F9
  JSL SubAreasFix
endif

; Subareas background color fix (under the bridge; zora...)
;$0E/D601 8F 00 C3 7E STA $7EC300[$7E:C300]
;$0E/D605 8F 40 C3 7E STA $7EC340[$7E:C340]

org $0ED601
	JSL SubAreasFix

; =========================================================
; Gloves color loading routine
;$1B/EE1B C2 30       REP #$30
;$1B/EE1D AF 54 F3 7E LDA $7EF354[$7E:F354]
;$1B/EE21 29 FF 00    AND #$00FF
;$1B/EE24 F0 0F       BEQ $0F    [$EE35]
;$1B/EE26 3A          DEC A
;$1B/EE27 0A          ASL A
;$1B/EE28 AA          TAX
;$1B/EE29 BF F5 ED 1B LDA $1BEDF5,x[$1B:EDF7]
;$1B/EE2D 8F FA C4 7E STA $7EC4FA[$7E:C4FA]
;$1B/EE31 8F FA C6 7E STA $7EC6FA[$7E:C6FA]
;$1B/EE35 E2 30       SEP #$30
;$1B/EE37 E6 15       INC $15    [$00:0015]
;$1B/EE39 6B          RTL

; Palettes_Load_LinkGloves
org $1BEE2D
	JSL GlovesFix

; =========================================================

; org $0ABA5A
; TODO: Handle overworld map palette for flashing icons

org $0ED956
  JSL FixDungeonMapColors

org $0AEFA6
  JSL RestoreTimeForDungeonMap

org $0ED745
  JSL FixShockPalette

org $09F604
GameOver_SaveAndQuit:
  JSL FixSaveAndQuit
