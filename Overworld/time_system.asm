;----------------[ Time system ]----------------
@xkas
warn xkas off
lorom 

; tiles locations on HUD
!hud_min_low = $7EC798
!hud_min_high = $7EC796
!hud_hours_low = $7EC792
!hud_hours_high = $7EC790
!hud_template = $0DFF07

org !hud_template
	db $10,$24,$11,$24
  db $6C,$25
  db $90,$24,$90,$24
  db $6C,$25,$90,$24,$90,$24	; HUD Template(adjusts timer's color)
	
org $068361
	JSL $1CFF30
  ;originally JSL $09B06E, executed every frame

org $1CFF30
	JSR counter_preroutine
	LDX #$00
debut:
	LDY #$00
	LDA $7EE000,x

debut2:
	CMP #$0A
	BMI draw
	SBC #$0A
	INY
	BRA debut2

draw:
	adc #$90
	CPX #$01
	BEQ minutes_low
	STA !hud_hours_low
	BRA 04

minutes_low:
	STA !hud_min_low
	tya
	clc
	adc #$90
	CPX #$01
	BEQ minutes_high
	STA !hud_hours_high
	BRA 04

minutes_high:
	STA !hud_min_high
	INX
	CPX #$02
	BMI debut
	JSL $09B06E
	rtl

;--------------------------------

counter_preroutine:
	LDA $10			;checks current event in game
	CMP #$07		;dungeon/building?
	BEQ counter_increasing
	CMP #$09		;overworld?
	BEQ overworld
	CMP #$0B
	BEQ overworld		;sub-area ? (under the bridge; zora domain...)
	CMP #$0E		;dialog box?
	BEQ dialog
	RTS

overworld:
	LDA $11
	CMP #$23		;hdma transfer? (warping)
	bne mosaic
mosaic:
	CMP #$0D		;mosaic ?
	BMI counter_increasing
	rts

dialog:
	LDA $11			;which kind of dialog? (to prevent the counter from increasing if save menu or item menu openned)
	CMP #$02		;NPC/signs speech
	BEQ counter_increasing
	rts

counter_increasing:
  ; time speed (1,3,5,7,F,1F,3F,7F,FF) 
  ; #$3F is almost 1 sec = 1 game minute
	LDA $1A : AND #$05
	BEQ increase_minutes
end:
	rts

increase_minutes:
	LDA $7EE001
	INC A
	STA $7EE001
	CMP #$3C		; minutes = #60 ?
	BPL increase_hours
	RTS

increase_hours:
	LDA #$00
	STA $7EE001
	LDA $7EE000
	INC A
	STA $7EE000
	CMP #$18		; hours = #24 ?
	BPL reset_hours

	LDA $1B			;check indoors/outdoors
	BEQ outdoors0
	RTS

outdoors0:
	JSL rom_to_buff		;update buffer palette
	JSL buff_to_eff		;update effective palette
	LDA $8C
	CMP #$9F		;rain layer ?
	BEQ skip_bg_updt0
	JSL $0BFE70		;update background color
	BRA inc_hours_end
	
skip_bg_updt0:			;prevent the sub layer from disappearing ($1D zeroed)
	JSL $0BFE72
inc_hours_end:	
	RTS

reset_hours:
	LDA #$00
	STA $7EE000

	LDA $1B			;check indoors/outdoors
	BEQ outdoors1
	RTS
outdoors1:
	JSL rom_to_buff
	JSL buff_to_eff
	LDA $8C
	CMP #$9F		;rain layer ?
	BEQ skip_bg_updt1
	JSL $0BFE70		;update background color
	BRA reset_end
	
skip_bg_updt1:			;prevent the sub layer from disappearing ($1D zeroed)
	JSL $0BFE72
reset_end:	
	RTS

;-----------------------------------------------
;----[ Day / Night system * palette effect ]----
;-----------------------------------------------

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
	STA !pal_color

	CPX #$0041
	BPL title_check
	STA $7EC300,X
	RTL
  
title_check:
	LDA $10
	AND #$00FF
	CMP #$0002	; title or file select screen ?
	BPL outin_check
	LDA !pal_color
	STA $7EC300,X
	RTL

outin_check:
	LDA $1B : AND #$00FF : BEQ outdoors2
	LDA !pal_color
	STA $7EC300,X
	RTL

outdoors2:
	PHX
	JSL ColorSubEffect
	PLX
	STA $7EC300,X
	RTL
}
;--------------------------------

ColorSubEffect:
{
	LDA $7EE000		; LDA #hours
	AND #$00FF
	CLC
	ADC $7EE000		; #hours * 2
	AND #$00FF
	TAX

do_blue:
	LDA !pal_color
	AND #$7C00
	STA !blue_value
	SEC
	SBC blue_table,x	; substract amount to blue field based on a table
	STA !temp_value
	AND #$7C00		; mask out everything except the blue bits
	CMP !temp_value		; overflow ?
	BEQ no_blue_sign_change

blue_sign_change:
	LDA #$0400		; LDA smallest blue value

no_blue_sign_change:
	STA !blue_value 

do_green:
	LDA !pal_color
	AND #$03E0
	STA !green_value
	SEC
	SBC green_table,x	; substract amount to blue field based on a table
	STA !temp_value
	AND #$03E0		; mask out everything except the green bits
	CMP !temp_value		; overflow ?
	BEQ no_green_sign_change
  
green_sign_change:
	LDA #$0020		; LDA smallest green value
	no_green_sign_change:
	STA !green_value
	
do_red:
	LDA !pal_color
	AND #$001F
	STA !red_value
	SEC
	SBC red_table,x		; substract amount to red field based on a table
	STA !temp_value
	AND #$001F		; mask out everything except the red bits
	CMP !temp_value		; overflow ?
	BEQ no_red_sign_change

red_sign_change:
	LDA #$0001		; LDA smallest red value

no_red_sign_change:
	STA !red_value

	LDA !blue_value
	ORA !green_value
	ORA !red_value
	
	RTL
}

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
	STA $7EC500
	STA $7EC300
	STA $7EC540
	STA $7EC340
	rtl
}

SubAreasFix:
{
	STA !pal_color
	PHX
	JSL ColorSubEffect
	PLX
	STA $7EC300
	STA $7EC340
	rtl
}


GlovesFix:
{
	STA !pal_color
	LDA $1B
	AND #$00FF
	BEQ .outdoors3
	LDA !pal_color
	STA $7EC4FA
	RTL

.outdoors3:
	PHX
	JSL ColorSubEffect
	PLX
	STA $7EC4FA
	RTL
}


; $0BFE70 -> background color loading routine
;Background color write fix - 16 bytes
;$0B/FEB6 8F 00 C5 7E STA $7EC500
;$0B/FEBA 8F 00 C3 7E STA $7EC300
;$0B/FEBE 8F 40 C5 7E STA $7EC540
;$0B/FEC2 8F 40 C3 7E STA $7EC340

org $0BFEB6
	STA !pal_color
	JSL BackgroundFix
	nop #8

; Subareas background color fix (under the bridge; zora...)
;$0E/D601 8F 00 C3 7E STA $7EC300[$7E:C300]
;$0E/D605 8F 40 C3 7E STA $7EC340[$7E:C340]

org $0ED601
	JSL SubAreasFix

;--------------------------------
	
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
