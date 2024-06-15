;----------------[ Time system ]----------------

; tiles locations on HUD
!hud_min_low = $7EC7CC
!hud_min_high = $7EC7CA
!hud_hours_low = $7EC7C6
!hud_hours_high = $7EC7C4
!hud_template = $0DFF07

org !hud_template
	db $10,$24,$11,$24
  db $6C,$25
  db $90,$24,$90,$24
  db $6C,$25,$90,$24,$90,$24	; HUD Template(adjusts timer's color)
	
org $068361
	JSL HUD_ClockDisplay ; $1CFF30
  ;originally JSL $09B06E, executed every frame

; =========================================================

; org $1CFF30
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
org $0CC265 ; IntroLogoPaletteFadeIn
JSL LogoFadeInSetClock
pullpc

LogoFadeInSetClock:
JSL $00ED7C ; restore code
LDA.b #$08 : STA.l $7EE000 ; Set the time to 6:00am
RTL 

pushpc
org $0CCA59
JSL ResetClockTriforceRoom

pullpc

ResetClockTriforceRoom:
JSL $00E384 ;Restored code

LDA.b #$00 : STA.l $7EE000 ; low hours for palette?
LDA.b #$00 : STA.l $7EE001 ; high hours for palette?

RTL

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
  LDA $10	;checks current event in game
  CMP #$07 : BEQ .counter_increasing ;dungeon/building?
    CMP #$09 : BEQ .overworld ;overworld?
    CMP #$0B : BEQ .overworld		;sub-area ? (under the bridge; zora domain...)
      CMP #$0E : BEQ .dialog ;dialog box?
        RTS

    .overworld
    ; Reload Sprite Gfx Properties
    JSL $00FC62 ; Sprite_LoadGraphicsProperties

    LDA $11 : CMP #$23 : BNE .mosaic ;hdma transfer? (warping)
      ; Lol what?
    .mosaic

    CMP #$0D : BMI .counter_increasing ;mosaic ?
      RTS

    .dialog
    LDA $11 ;which kind of dialog? (to prevent the counter from increasing if save menu or item menu openned)
    CMP #$02 : BEQ .counter_increasing ;NPC/signs speech
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

  ; time speed (1,3,5,7,F,1F,3F,7F,FF) 
  ; #$3F is almost 1 sec = 1 game minute
  LDA $1A : AND #$3F : BEQ .increase_minutes ; 05
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

    JSL rom_to_buff	;update buffer palette
    JSL buff_to_eff	;update effective palette

    ;rain layer ?
    LDA $8C : CMP #$9F : BEQ .skip_bg_updt0
      LDA $8C : CMP #$9E : BEQ .skip_bg_updt0	; canopy layer ?
        CMP #$97 : BEQ .skip_bg_updt0	; fog layer?
        JSL $0BFE70	;update background color
        BRA .inc_hours_end
    
    .skip_bg_updt0 ;prevent the sub layer from disappearing ($1D zeroed)
    JSL $0BFE72

    .inc_hours_end


    
    RTS

  .reset_hours

  LDA #$00 : STA $7EE000

  ;check indoors/outdoors
  LDA $1B	: BEQ .outdoors1
    RTS
  .outdoors1

  JSL rom_to_buff
  JSL buff_to_eff

  LDA $8C : CMP #$9F : BEQ .skip_bg_updt1 ;rain layer ?
    LDA $8C : CMP #$9E : BEQ .skip_bg_updt1	; canopy layer ?
      JSL $0BFE70 ;update background color
      BRA .reset_end
    
  .skip_bg_updt1 ;prevent the sub layer from disappearing ($1D zeroed)

  JSL $0BFE72

  .reset_end
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

; part of rom pal to buffer routine
;$1B/EF61 9F 00 C3 7E STA $7EC300,x[$7E:C422]
;$1B/EF3D 9F 00 C3 7E STA $7EC300,x[$7E:C412]
;$1B/EF84 9F 00 C3 7E STA $7EC300,x[$7E:C4B2]

org $1BEF3D
	JSL LoadDayNightPaletteEffect

org $1BEF61
	JSL LoadDayNightPaletteEffect

org $1BEF84
	JSL LoadDayNightPaletteEffect

org $0EEE25	; free space
LoadDayNightPaletteEffect:
{
  STA.l !pal_color

  CPX #$0041 : BPL .title_check
    STA $7EC300,X
    RTL
    
  .title_check

  ; title or file select screen ?
  LDA $10 : AND #$00FF : CMP #$0002	: BCS .outin_check
    LDA.l !pal_color : STA $7EC300,X
    RTL

  .outin_check
  LDA.b $10 : AND #$00FF
    CMP.w #$0005 : BCC .restorecode
    CMP.w #$0012 : BCS .restorecode
    BRA .overworld
  .restorecode
    LDA.l !pal_color : STA.l $7EC300, X
    RTL
  .overworld

  LDA $1B : AND #$00FF : BEQ .outdoors2
    LDA.l !pal_color
    STA $7EC300,X
    RTL

  .outdoors2

  PHX
  JSL ColorSubEffect
  PLX
  STA.l $7EC300,X
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
  ; substract amount to blue field based on a table
	SEC : SBC.l blue_table, X : STA !temp_value
	AND #$7C00		; mask out everything except the blue bits
	CMP !temp_value : BEQ .no_blue_sign_change; overflow ?
    .blue_sign_change
    LDA #$0400		; LDA smallest blue value

  .no_blue_sign_change
	STA.l !blue_value 

  do_green:
	LDA !pal_color : AND #$03E0 : STA !green_value
	SEC : SBC.l green_table,x	; substract amount to blue field based on a table
	STA.l !temp_value
  ; mask out everything except the green bits
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
	STA.l $7EC500
	STA.l $7EC300
	STA.l $7EC540
	STA.l $7EC340
	rtl
}

SubAreasFix:
{
	STA.l !pal_color
	PHX
	JSL ColorSubEffect
	PLX
	STA $7EC300
	STA $7EC340
	rtl
}

GlovesFix:
{
	STA.l !pal_color
	LDA $1B : AND #$00FF : BEQ .outdoors3
    LDA.l !pal_color
    STA $7EC4FA
    RTL

  .outdoors3:
	PHX
	JSL ColorSubEffect
	PLX
	STA $7EC4FA
	RTL
}

CheckIfNight:
{
  LDA.l $7EF3C5 : CMP.b #$02 : BCC .day_time
  LDA $7EE000 : CMP.b #$06 : BCC .night_time
    .day_time
    LDA.l $7EF3C5
    RTL
  .night_time
  LDA $7EE000 : CMP.b #$12 : BCS .day_time
    LDA.b #$03
    RTL
  .dont_change

}

warnpc $0EF3F9  ; free space

org $09C4E3
  JSL CheckIfNight

org $00FC6A
  JSL CheckIfNight16Bit


; $0BFE70 -> background color loading routine
;Background color write fix - 16 bytes
;$0B/FEB6 8F 00 C5 7E STA $7EC500
;$0B/FEBA 8F 00 C3 7E STA $7EC300
;$0B/FEBE 8F 40 C5 7E STA $7EC540
;$0B/FEC2 8F 40 C3 7E STA $7EC340

; Custom BG Color Mosaic Background Color fix
org $028464
  NOP #6

org $02AE92
  NOP #6

; org $0BFEB6 OLD HOOK
; ZS OW Expanded - ReplaceBGColor
org $2886B4 
	STA !pal_color
	JSL BackgroundFix
	;NOP #8

; ZS OW Expanded - CheckForChangeGraphicsTransitionLoad
org $2885F9
	JSL SubAreasFix

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

org $1BEE2D
	JSL GlovesFix

; =========================================================

pullpc

CheckIfNight16Bit:
{
  LDA.l $7EF3C5 : AND.w #$00FF : CMP.w #$0002 : BCC .day_time
  LDA $7EE000 : AND.w #$00FF : CMP.w #$0006 : BCC .night_time
    .day_time
    LDA.l $7EF3C5

    RTL
  .night_time

  LDA $7EE000 : AND.w #$00FF : CMP.w #$0012 : BCS .day_time
    LDA.l $7EF3C5
    CLC
    ADC #$0001
    RTL
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
  STA.l $7EC500, X
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

org $0ED956
  JSL FixDungeonMapColors

org $0AEFA6
  JSL RestoreTimeForDungeonMap

; org $0ABA5A
; TODO: Handle overworld map palette for flashing icons

org $0ED745
  JSL FixShockPalette

org $09F604
GameOver_SaveAndQuit:
{
  JSL FixSaveAndQuit
}