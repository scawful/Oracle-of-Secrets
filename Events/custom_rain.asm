; variables
; 7EE00E - Rain Activator
; 7EE00D - Rain Deactivator (overridden if rain is activated before the deactivation occurs)
; 7EE00C - Activates the overlay animations and nonimmediate rain things
; 7EE00F - Activates thunder and indoor ambience (can be set at the same time as the Rain Activator)
; 7EE001 - Minutes in the time sequence script
; 7EE000 - Hours in the time sequence script
; 7EE00B - used to prevent my script from warping if rain is active, 0 allow rain disallow warp, 1 disallow rain allow warp 

;this is my loader for turning the rain on and off 
; executed on dungoen load (replaced an LDA $7EF3C5 which is read before we return)
org $208100 
LoadRainEffect:
{
	LDA $7EE00E : BNE .On
	LDA $7EE00D : BNE .Off
	BRA LoadRainEffect_End

LoadRainEffect_On:
	LDA #$01 : STA $7EE00F : STA $7EE00C
	LDA #$01 : STA $7EE00E
	BRA LoadRainEffect_End

LoadRainEffect_Off:
	LDA #$00
	STA $7EE00F
	STA $7EE00C
	STA $7EE00D
	BRA LoadRainEffect_End

LoadRainEffect_End:
	LDA #$00
	STA $7EE00E
	STA $7EE00D
	LDA $7EF3C5
	RTL
}


org $208200 ; these are executed every frame
RainOnTime:
	LDA $7EE001
	cmp #$1E
	bne .End
	LDA $7EE000
	cmp #$01
	bne .End
	LDA $7EE00B
	bne .End
	LDA #$01
	sta $7EE00E
	sta $7EE00F
RainOnTime_End:
	rtl

org $208300 ; these are executed every frame
RainOffTime:
	LDA $7EE001
	cmp #$1E
	bne .End
	LDA $7EE000
	cmp #$03
	bne .End
	LDA #$01
	sta $7EE00D
RainOffTime_End:
	rtl

; moved this function to expanded space to change it, don't think i needed to though :()
org $20C000 
	LDA $8A : CMP #$70 : BEQ BRANCH_EVIL_SWAMP
	LDA $7EE00F : BEQ BRANCH_SKIPMOVEMENT

BRANCH_EVIL_SWAMP:
	LDA $7EF2F0 ; If misery mire has been opened already, we're done
	AND #$20
	BNE BRANCH_SKIPMOVEMENT
	LDA $1A ; Check the frame counter.
	CMP #$03 ; On the third frame do a flash of lightning.
	BEQ BRANCH_LIGHTNING
	CMP #$05
	BEQ BRANCH_NORMAL_LIGHT
	CMP #$24 ; On the #$24-th frame cue the thunder.
	BEQ BRANCH_THUNDER
	CMP #$2C ; On the #$2C-th frame bring the light back to normal.
	BEQ BRANCH_NORMAL_LIGHT
	CMP #$58 ; On the #$58-th frame cue the lightning
	BEQ BRANCH_LIGHTNING
	CMP #$5A ; On the #$5A-th frame 
	BNE BRANCH_MOVEOVERLAY
BRANCH_NORMAL_LIGHT:
	LDA #$72 ; Keep the screen semi-dark.
	BRA BRANCH_SETBRIGHTNESS
BRANCH_THUNDER:
	LDX #$36
	STX $012E ; Play the thunder sound when outdoors.
BRANCH_LIGHTNING:
	LDA #$32 ; Make the screen flash with lightning.
BRANCH_SETBRIGHTNESS:
	STA $9A
BRANCH_MOVEOVERLAY:
	LDA $1A ; if the first two bits are set, do nothing
	AND #$03
	BNE BRANCH_SKIPMOVEMENT
	LDA $0494 ; otherwise start moving some rain
	INC
	AND #$03
	STA $0494
	TAX
	LDA $E1
	CLC
	ADC $02A46D, X
; $01246D IN ROM
	STA $E1
	LDA $E7
	CLC
	ADC $02A471, X
; $012471
	STA $E7
BRANCH_SKIPMOVEMENT:
	RTL

org $02A4CD ; rain animating overlays, thunder lightning, darkness (can do immediate)
	JSL $20C000
	BRA $59

org $02AC12 ; load overlays OW to OW
	LDA $7EE00C
	NOP #2
	BEQ $03

org $02AFFC ; load overlays dungeon to OW
	LDA $7EE00C
	NOP #06
	BEQ $03

org $02838C ; indoor ambience (can do immediate)
	LDA $7EE00F
	NOP #02
	BEQ $1e

org $02845D ; music routine 
	LDA $7EE00C
	NOP #02
	BEQ $02

org $0284EA ; outdoor ambience
	LDA $7EE00C
	NOP #2
	BEQ $02

; overworld music routine
; modified to use the 'Beginning' music if 7EE00C is not zero (Rain activated)
org $02C463 
	PHB : PHK : PLB
	REP #$10
    LDA #$02 : STA $00
    LDX #$0000
    LDA $7EE00C
    BNE $25

    LDY #$00C0
    LDA $7EF3C5
    CMP #$03
    BCS $1D

    LDY #$0080
    LDA $7EF359
    CMP #$02
    BCS $12

    LDA #$05
    STA $00
    LDY #$0040
    LDA $7EF3C5
    CMP #$02
    BCS $03

    LDY #$0000
    LDA $C303,Y
    STA $7F5B00,X
    INY
    INX
    CPX #$0040
    BNE $F2

    LDY #$0000
    LDA $C403,Y
    STA $7F5B00,X
    INX
    INY
    CPY #$0060
    BNE $F2

    LDA $00
    STA $7F5B80
	SEP #$10
	PLB
	RTL

; Overworld beginning music for each OW Screen 
; changes the music to use heavy rain outside of lost woods, and light rain inside
org $02C303 
	db $25,$25,$13,$13,$13,$13,$13,$13
	db $25,$25,$13,$13,$13,$13,$13,$13
	db $13,$13,$13,$13,$13,$13,$13,$13
	db $13,$13,$13,$13,$13,$13,$13,$13
	db $13,$13,$13,$13,$13,$13,$13,$13
	db $13,$13,$13,$13,$13,$13,$13,$13
	db $13,$13,$13,$13,$13,$13,$13,$13
	db $13,$13,$13,$13,$13,$13,$13,$13

; executed on dungoen load
org $028356 ; replaced an LDA $7EF3C5 which is read before we return
	JSL $208100