;----------------[ Time system ]----------------

; tiles locations on HUD (status bar)
!hud_min_low = $7EC79E
!hud_min_high = $7EC79C
!hud_hours_low = $7EC798
!hud_hours_high = $7EC796
!hud_template = $0DFF07

org !hud_template
	db $10,$24,$11,$24,$12,$24,$90,$24,$90,$24,$13,$24,$90,$24,$90,$24	; HUD Template(adjusts timer's color)
	
org $068361
	jsl $1CFF30
  ;originally JSL $09B06E, executed every frame

org $1CFF30
	jsr counter_preroutine
	ldx #$00
debut:
	ldy #$00
	lda $7EE000,x

debut2:
	cmp #$0A
	bmi draw
	sbc #$0A
	iny
	bra debut2

draw:
	adc #$90
	cpx #$01
	beq minutes_low
	sta !hud_hours_low
	bra 04

minutes_low:
	sta !hud_min_low
	tya
	clc
	adc #$90
	cpx #$01
	beq minutes_high
	sta !hud_hours_high
	bra 04

minutes_high:
	sta !hud_min_high
	inx
	cpx #$02
	bmi debut
	jsl $09B06E
	rtl

;--------------------------------

counter_preroutine:
	lda $10			;checks current event in game
	cmp #$07		;dungeon/building?
	beq counter_increasing
	cmp #$09		;overworld?
	beq overworld
	cmp #$0B
	beq overworld		;sub-area ? (under the bridge; zora domain...)
	cmp #$0E		;dialog box?
	beq dialog
	rts

overworld:
	lda $11
	cmp #$23		;hdma transfer? (warping)
	bne mosaic
mosaic:
	cmp #$0D		;mosaic ?
	bmi counter_increasing
	rts

dialog:
	lda $11			;which kind of dialog? (to prevent the counter from increasing if save menu or item menu openned)
	cmp #$02		;NPC/signs speech
	beq counter_increasing
	rts

counter_increasing:
	lda $1A
	and #$1F		;change value (1,3,5,7,F,1F,3F,7F,FF) to have different time speed, #$3F is almost 1 sec = 1 game minute
	beq increase_minutes
end:
	rts

increase_minutes:
	lda $7EE001
	inc a
	sta $7EE001
	cmp #$3C		; minutes = #60 ?
	bpl increase_hours
	rts

increase_hours:
	lda #$00
	sta $7EE001
	lda $7EE000
	inc a
	sta $7EE000
	cmp #$18		; hours = #24 ?
	bpl reset_hours

	lda $1B			;check indoors/outdoors
	beq outdoors0
	rts
outdoors0:
	jsl rom_to_buff		;update buffer palette
	jsl buff_to_eff		;update effective palette
	lda $8C
	cmp #$9F		;rain layer ?
	beq skip_bg_updt0
	jsl $0BFE70		;update background color
	bra inc_hours_end
	
skip_bg_updt0:			;prevent the sub layer from disappearing ($1D zeroed)
	jsl $0BFE72
inc_hours_end:	
	rts

reset_hours:
	lda #$00
	sta $7EE000

	lda $1B			;check indoors/outdoors
	beq outdoors1
	rts
outdoors1:
	jsl rom_to_buff
	jsl buff_to_eff
	lda $8C
	cmp #$9F		;rain layer ?
	beq skip_bg_updt1
	jsl $0BFE70		;update background color
	bra reset_end
	
skip_bg_updt1:			;prevent the sub layer from disappearing ($1D zeroed)
	jsl $0BFE72
reset_end:	
	rts

;-----------------------------------------------
;----[ Day / Night system * palette effect ]----
;-----------------------------------------------

!blue_value = $7EE010
!green_value = $7EE012
!red_value = $7EE014

!temp_value = $7EE016
!pal_color = $7EE018
!x_reg = $08

org $02FF70		; free space on bank $02

buff_to_eff:
	jsr $C769	; $02:C65F -> palette buffer to effective routine
	rtl
rom_to_buff:
	jsr $AAF4	; $02:AAF4 -> change buffer palette of trees,houses,rivers,etc.
	jsr $C692	; $02:C692 -> rom to palette buffer for other colors
	rtl

; part of rom pal to buffer routine
;$1B/EF61 9F 00 C3 7E STA $7EC300,x[$7E:C422]
;$1B/EF3D 9F 00 C3 7E STA $7EC300,x[$7E:C412]
;$1B/EF84 9F 00 C3 7E STA $7EC300,x[$7E:C4B2]

org $1BEF3D
	jsl new_palette_load
org $1BEF61
	jsl new_palette_load
org $1BEF84
	jsl new_palette_load

org $1EEE25	; free space

new_palette_load:

	sta !pal_color

	cpx #$0041
	bpl title_check
	sta $7EC300,x
	rtl
title_check:
	lda $10
	and #$00FF
	cmp #$0002	; title or file select screen ?
	bpl outin_check
	lda !pal_color
	sta $7EC300,x
	rtl
outin_check:
	lda $1B
	and #$00FF
	beq outdoors2
	lda !pal_color
	sta $7EC300,x
	rtl

outdoors2:
	phx
	jsl color_sub_effect
	plx
	sta $7EC300,x
	rtl

;--------------------------------

color_sub_effect:
	lda $7EE000		; lda #hours
	and #$00FF
	clc
	adc $7EE000		; #hours * 2
	and #$00FF
	tax


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
	LDA #$0400		; lda smallest blue value
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
	LDA #$0020		; lda smallest green value
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
	LDA #$0001		; lda smallest red value
no_red_sign_change:
	STA !red_value

	LDA !blue_value
	ORA !green_value
	ORA !red_value
	
	rtl


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

background_fix:
	beq no_effect		;branch if A=#$0000 (transparent bg)
	jsl color_sub_effect
  
no_effect:
	sta $7EC500
	sta $7EC300
	sta $7EC540
	sta $7EC340
	rtl

subareas_fix:
	sta !pal_color
	phx
	jsl color_sub_effect
	plx
	STA $7EC300
	STA $7EC340
	rtl

gloves_fix:
	sta !pal_color
	lda $1B
	and #$00FF
	beq outdoors3
	lda !pal_color
	STA $7EC4FA
	rtl

outdoors3:
	phx
	jsl color_sub_effect
	plx
	STA $7EC4FA
	rtl

; $0BFE70 -> background color loading routine
;Background color write fix - 16 bytes
;$0B/FEB6 8F 00 C5 7E STA $7EC500
;$0B/FEBA 8F 00 C3 7E STA $7EC300
;$0B/FEBE 8F 40 C5 7E STA $7EC540
;$0B/FEC2 8F 40 C3 7E STA $7EC340

org $0BFEB6
	sta !pal_color
	jsl background_fix
	nop #8

; Subareas background color fix (under the bridge; zora...)
;$0E/D601 8F 00 C3 7E STA $7EC300[$7E:C300]
;$0E/D605 8F 40 C3 7E STA $7EC340[$7E:C340]

org $0ED601
	jsl subareas_fix

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
	jsl gloves_fix
















