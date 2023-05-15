; =============================================================================
; Ocarina Multiple Song Select
;
; $7EF3CB - Ocarina Song RAM 
; 
; =============================================================================

org $0994FE
  AddTravelBird:

org $098D11
  AddWeathervaneExplosion:

; SFX2_Accomp
; SFX2 13 (Previous $3E)
org $1A8C60
  db $00

; SFX2_13
org $1A9750
Song_of_Healing:
{
  db $E0, $0D
  db $2A ; change this to change length of quarter note
  db $46
  db $A3, $A1, $9D
  db $A3, $A1, $9D
  db $A3, $A1
  db $15 ; make this half of whatever you made quarter note
  db $9C, $9A
  db $7F ; make this triple whatever you made quarter note (max value 7F)
  db $9C
  db $00
}

; D F D - D F D - E F E - F E C
; D F d D F d e f e f e c
; SFX2_12
org $1A977D
{
  db $E0, $0D ; set sfx instrument - twee

  db $0F, $46 ; duration 1/4, params
  db $9A ; play note D3
  db $9D ; play note F3
  db $1E, $46 ; duration 1/2, params
  db $9A ; play note D3

  db $0F, $46 ; duration 1/4, params
  db $9A ; play note D3
  db $9D ; play note F3
  db $1E, $46 ; duration 1/2, params
  db $9A ; play note D3
  
  db $0F, $3C ; duration 1/4, params
  db $9C ; play note E3
  db $9D ; play note F3
  db $9C ; play note E3

  db $9D ; play note F3
  db $9C ; play note E3
  db $1E, $3C ; duration 1/2, params
  db $98 ; play note C3

  db $00 ; end sfx
}

; =============================================================================

org $07A3DB
LinkItem_FluteHook:
{
  JSR LinkItem_NewFlute
  RTS
}

; Free Space Bank07
org $07FC69
ReturnFromFluteHook:
  RTS

LinkItem_NewFlute:
{
  ; Code for the flute item (with or without the bird activated)
  
  BIT $3A : BVC .y_button_not_held
  DEC $03F0 : LDA $03F0 : BNE ReturnFromFluteHook
  LDA $3A : AND.b #$BF : STA $3A

.y_button_not_held

  ; Check for Switch Swong 
  JSR UpdateFluteSong
  JSR Link_CheckNewY_ButtonPress : BCC ReturnFromFluteHook
  
  ; Success... play the flute.
  LDA.b #$80 : STA $03F0
  
  LDA $030F
  CMP.b #$01 : BEQ .song_of_soaring
  CMP.b #$02 : BEQ .song_of_healing
  CMP.b #$03 : BEQ .song_of_storms

.song_of_healing
  LDA.b #$13 : JSR Player_DoSfx2 : RTS

.song_of_storms
  ; Play the Song of Storms SFX
  LDA.b #$12 : JSR Player_DoSfx2 
  JSR OcarinaEffect_SummonStorms
  RTS

.song_of_soaring
  LDA.b #$3E : JSR Player_DoSfx2

  ; Are we indoors?
  LDA $1B : BNE .return
  
  ; Are we in the dark world? The flute doesn't work there.
  LDA $8A : AND.b #$40 : BNE .return
  
  ; Also doesn't work in special areas like Master Sword area.
  LDA $10 : CMP.b #$0B : BEQ .return
  
  LDX.b #$04

.next_ancillary_slot

  ; Is there already a travel bird effect in this slot?
  LDA $0C4A, X : CMP.b #$27 : BEQ .return
  ; If there isn't one, keep checking.
  DEX : BPL .next_ancillary_slot

  ; Paul's weathervane stuff Do we have a normal flute (without bird)?
  LDA $7EF34C : CMP.b #$02 : BNE .travel_bird_already_released
  
  REP #$20

  ; check the area, is it #$18 = 30?
  LDA $8A : CMP.w #$0018 : BNE .not_weathervane_trigger
  
  ; Y coordinate boundaries for setting it off.
  LDA $20
  
  CMP.w #$0760 : BCC .not_weathervane_trigger
  CMP.w #$07E0 : BCS .not_weathervane_trigger
  
  ; do if( (Ycoord >= 0x0760) && (Ycoord < 0x07e0
  LDA $22
  
  CMP.w #$01CF : BCC .not_weathervane_trigger
  CMP.w #$0230 : BCS .not_weathervane_trigger
  
  ; do if( (Xcoord >= 0x1cf) && (Xcoord < 0x0230)
  SEP #$20
  ; Apparently a special Overworld mode for doing this?
  LDA.b #$2D : STA $11
  
  ; Trigger the sequence to start the weathervane explosion.
  LDY.b #$00
  LDA.b #$37
  JSL AddWeathervaneExplosion

.not_weathervane_trigger

  SEP #$20
  BRA .return

.travel_bird_already_released

  LDY.b #$04
  LDA.b #$27
  JSL AddTravelBird
  STZ $03F8

.return

  RTS
}

; =============================================================================

; $7EF3CB - Ocarina Song SRAM

; $030F - Current Song RAM
; 00 - No Song
; 01 - Song of Healing
; 02 - Song of Soaring 
; 03 - Song of Storms

UpdateFluteSong:
{
  LDA $030F : BNE .songExists
  LDA #$01 : STA $030F  ; if this code is running, we have the flute song 1
.songExists
  LDA.b $F6
  BIT.b #$20 : BNE .left
  BIT.b #$10 : BNE .right

  RTS

.left
  ; LDA.b #$13 : JSR Player_DoSfx2
  DEC $030F
  LDA $030F
  BNE .notPressed

  LDA #$03
  STA $030F
  JMP .notPressed

.right
  ; R Button Pressed - Increment song
  INC $030F        ; increment $030F Song RAM
  LDA $030F        ; load incremented Song RAM
  CMP.b #$04       ; compare with 3
  BCC .notPressed    ; if less than 3, branch to .notFlute

  LDA #$01         ; load value 1
  STA $030F        ; set Song RAM to 1

.notPressed
  RTS
}

OcarinaEffect_SummonStorms:
{
  LDA.l $7EE00C : BEQ .summonStorms

  LDA #$01 : STA $7EE00D
  RTS

.summonStorms
  LDA #$01 : STA $7EE00E
  RTS
}

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
	lda $7EE00E
	bne .On
	lda $7EE00D
	bne .Off
	bra Rain_End
Rain_On:
	lda #$01
	sta $7EE00F
	sta $7EE00C
	lda #$01
	sta $7EE00E
	bra Rain_End
Rain_Off:
	lda #$00
	sta $7EE00F
	sta $7EE00C
	sta $7EE00D
	bra Rain_End
Rain_End:
	lda #$00
	sta $7EE00E
	sta $7EE00D
	lda $7EF3C5
	rtl
}


org $208200 ; these are executed every frame
RainOnTime:
	lda $7EE001
	cmp #$1E
	bne .End
	lda $7EE000
	cmp #$01
	bne .End
	lda $7EE00B
	bne .End
	lda #$01
	sta $7EE00E
	sta $7EE00F
RainOnTime_End:
	rtl

org $208300 ; these are executed every frame
RainOffTime:
	lda $7EE001
	cmp #$1E
	bne .End
	lda $7EE000
	cmp #$03
	bne .End
	lda #$01
	sta $7EE00D
RainOffTime_End:
	rtl

org $20C000 ; moved this function to expanded space to change it, don't think i needed to though :(
	LDA $8A
	CMP #$70
	BEQ BRANCH_EVIL_SWAMP
	LDA $7EE00F
	Beq BRANCH_SKIPMOVEMENT
BRANCH_EVIL_SWAMP:
	LDA $7EF2F0 ; If misery mire has been opened already, weíre done
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
	jsl $20C000
	bra $59
org $02AC12 ; load overlays OW to OW
	lda $7EE00C
	nop #2
	beq $03
org $02AFFC ; load overlays dungeon to OW
	lda $7EE00C
	nop #06
	beq $03
org $02838C ; indoor ambience (can do immediate)
	lda $7EE00F
	nop #02
	beq $1e
org $02845D ; music routine 
	lda $7EE00C
	nop #02
	beq $02
org $0284EA ; outdoor ambience
	lda $7EE00C
	nop #2
	beq $02
org $02C463 ; overworld music routine, modified to use the 'Beginning' music if 7EE00C is not equal to zero (Rain activated)
	PHB
	PHK
	PLB
	REP #$10
	LDA #$02
	STA $00
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

org $02C303 ; Overworld beginning music for each OW Screen changes the music to use heavy rain outside of lost woods, and light rain inside
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
; org $02A4CD
	JSL $208100
