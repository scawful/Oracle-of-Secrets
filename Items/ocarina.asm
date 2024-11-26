; =========================================================
; Ocarina Multiple Song Select
;
; =========================================================

AddTravelBird = $0994FE
AddWeathervaneExplosion = $098D11
Player_DoSfx1 = $078021

; =========================================================
; Song of Healing

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

; =========================================================

; D F D - D F D - E F E - F E C
; D F d D F d e f e f e c
; SFX2_12
; org $1A977D

!Storms_Duration = $0F
!Storms_Params = $46

!Storms_Duration2 = $1E
!Storms_Params2 = $3C

org $1A92F7 ; SFX2_2F
Song_of_Storms:
{
  db $E0, $0D ; set sfx instrument - twee

  db !Storms_Duration
  db !Storms_Params ; duration 1/4
  db $9A ; play note D3
  db $9D ; play note F3
  db !Storms_Duration2
  db !Storms_Params ; duration 1/2
  db $9A ; play note D3

  db !Storms_Duration
  db !Storms_Params ; duration 1/4
  db $9A ; play note D3
  db $9D ; play note F3
  db !Storms_Duration2
  db !Storms_Params ; duration 1/2
  db $9A ; play note D3

  db !Storms_Duration
  db !Storms_Params2 ; duration 1/4
  db $9C ; play note E3
  db $9D ; play note F3
  db $9C ; play note E3

  db $9D ; play note F3
  db $9C ; play note E3
  db !Storms_Duration2
  db !Storms_Params2 ; duration 1/2
  db $98 ; play note C3

  db $00 ; end sfx
}
; assert pc() <= $1A8FD4

; =========================================================

; A, D, F, A, D, F
; SFX3_27 Agahnim charge
; 0x003B

org $1A91F0
Song_of_Time:
{
  !Time4th = $2A
  !TimeParams = $46

  db $E0, $0D ; set sfx instrument - twee

  db !Time4th    ; duration 1/4
  db !TimeParams ; params
  db A3

  db $54         ; duration 1/2
  db !TimeParams ; params
  db D3

  db !Time4th    ; duration 1/4
  db !TimeParams ; params
  db F3
  db A3

  db $54 ; duration 1/2
  db !TimeParams ; params
  db D3

  db !Time4th    ; duration 1/4
  db !TimeParams ; params
  db F3

  db $00 ; end sfx
}
assert pc() <= $1A922B

; =========================================================

org $07A3DB
LinkItem_FluteHook:
  JSR LinkItem_NewFlute
  RTS

; Free Space Bank07
pullpc
ReturnFromFluteHook:
  RTS

; =========================================================

LinkItem_NewFlute:
{
  ; Code for the flute item (with or without the bird activated)
  BIT.b $3A : BVC .y_button_not_held
    DEC.w $03F0 : LDA.w $03F0 : BNE ReturnFromFluteHook
    LDA.b $3A : AND.b #$BF : STA.b $3A
  .y_button_not_held

  ; Check for Switch Swong
  JSR UpdateFluteSong
  JSR Link_CheckNewY_ButtonPress : BCC ReturnFromFluteHook

  ; Success... play the flute.
  LDA.b #$80 : STA.w $03F0

  LDA.w $030F
  CMP.b #$01 : BEQ .song_of_storms
  CMP.b #$02 : BEQ .song_of_healing
  CMP.b #$03 : BEQ .song_of_soaring
  CMP.b #$04 : BEQ .song_of_time

  .song_of_time
  LDA.b #$27 : JSR $802F ; Player_DoSfx3
  LDA.b #$02 : STA $FE
  RTS

  .song_of_healing
  LDA.b #$13 : JSR Player_DoSfx2
  LDA.b #$01 : STA $FE
  RTS

  .song_of_storms
  ; Play the Song of Storms SFX
  LDA.b #$2F : JSR Player_DoSfx2
  JSL OcarinaEffect_SummonStorms
  RTS

  .song_of_soaring
  LDA.b #$3E : JSR Player_DoSfx2

  ; Are we indoors?
  LDA.b $1B : BNE .return

  ; Are we in the dark world? Then become Moosh form.
  LDA.b $8A : AND #$40 : BEQ .light_world
    JSL Link_TransformMoosh
    RTS
  .light_world

  ; Also doesn't work in special areas like Master Sword area.
  LDA.b $10 : CMP.b #$0B : BEQ .return

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

; =========================================================

UpdateFluteSong:
  JSL UpdateFluteSong_Long
  RTS

Link_HandleCardinalCollision_Long:
{
  PHB : PHK : PLB
  JSR $B7C7
  PLB
  RTL
}

print "Bank07 Free Space: ", pc

org $2B8000
OcarinaEffect_SummonStorms:
{
  ; Dismiss the rain in the Zora area where it is already raining
  LDA.w $8A : CMP.b #$1E : BEQ .checkForEvent
              CMP.b #$2E : BEQ .dismissStorms
              CMP.b #$2F : BEQ .dismissStorms
    ; Check for areas which should not be allowed to have rain
    CMP.b #$05 : BEQ .errorBeep
    CMP.b #$06 : BEQ .errorBeep
    CMP.b #$07 : BEQ .errorBeep
    CMP.b #$10 : BEQ .errorBeep
    CMP.b #$18 : BEQ .errorBeep
    CMP.b #$28 : BEQ .errorBeep
    CMP.b #$29 : BEQ .errorBeep

    ; If the rain is already summoned, dismiss it
    LDA.l $7EE00E : BEQ .summonStorms
      .dismissStorms
      LDA #$FF : STA $8C
      LDA #$00 : STA $7EE00E
      STZ $1D
      STZ $9A
      RTL

    .summonStorms
    LDA #$9F : STA $8C
    LDA.b #$01 : STA.b $1D
    LDA.b #$72 : STA.b $9A
    LDA #$01 : STA $7EE00E
    RTL

  .errorBeep
    LDA.b #$3C : STA.w $012E ; Error beep
    RTL

  .checkForEvent
    JSR CheckForZoraEvent : BCC .errorBeep
    JMP .dismissStorms
}

; Y: E8 06, X: 48 0C
CheckForZoraEvent:
{
  LDA $20 : CMP.w #$06E8 : BNE .notZora
  LDA $22 : CMP.w #$0C48 : BNE .notZora
    LDA.b #$01 : STA $04C6
    SEC
    RTS
  .notZora
  CLC
  RTS
}

PlayThunderAndRain:
{
  LDA.b #$01 : STA $012D
  LDX.b #$36 : STX.w $012E
  RTL
}

CheckRealTable:
{
  LDA $7EE00E : CMP #$00 : BEQ .continue
    JML RainAnimation_Overridden_rainOverlaySet
  .continue
  LDA #$05 : STA $012D
  LDA.b $8A : ASL : TAX
  LDA.l Pool_OverlayTable, X
  CMP.b #$9F : BNE .not_rain_area
    RTL
  .not_rain_area

  JML RainAnimation_Overridden_skipMovement
}

ResetOcarinaFlag:
{
  LDA $7EF3C5 : BEQ .continue
     CMP #$01 : BEQ .continue
    REP #$30
    LDA #$0000 : STA.l $7EE00E
    SEP #$30
  .continue
  LDA.w $0416 : ASL A
  RTL
}

; $030F - Current Song RAM
; 00 - No Song
; 01 - Song of Storms
; 02 - Song of Healing
; 03 - Song of Soaring
; 04 - Song of Time

; Values at $7EF34C determine scrolling behavior
; 01 - No scrolling allowed
; 02 - Scroll between two songs
; 03 - Scroll between three songs
; 04 - Scroll between four songs
UpdateFluteSong_Long:
{
  LDA $7EF34C : CMP.b #$01 : BEQ .not_pressed
    LDA $030F : BNE .song_exists
      ; if this code is running, we have the flute song 1
      LDA #$01 : STA $030F
    .song_exists
    LDA.b $F6
    BIT.b #$20 : BNE .left  ; pressed left
    BIT.b #$10 : BNE .right ; pressed right
      RTL

    .left ; L Button Pressed - Decrement song
    ; LDA.b #$13 : JSR Player_DoSfx2
    DEC $030F
    LDA $030F : CMP #$00 : BEQ .wrap_to_max
      BRA .update_song

    .right ; R Button Pressed - Increment song
    INC $030F
    LDA $7EF34C : CMP.b #$02 : BEQ .max_2
                  CMP.b #$03 : BEQ .max_3
      LDA $030F : CMP.b #$05 : BCS .wrap_to_min
      RTL
    .max_2
    LDA $030F : CMP.b #$03 : BCS .wrap_to_min
      RTL
    .max_3
    LDA $030F : CMP.b #$04 : BCS .wrap_to_min
    .update_song
      RTL

    .wrap_to_max
    LDA $7EF34C : CMP.b #$01 : BEQ .wrap_to_min
                  CMP.b #$02 : BEQ .set_max_to_2
                  CMP.b #$03 : BEQ .set_max_to_3
      LDA #$04 : STA $030F : RTL

    .set_max_to_3
    LDA #$03 : STA $030F : RTL

    .set_max_to_2
    LDA #$02 : STA $030F : RTL

    .wrap_to_min
    LDA #$01 : STA $030F

  .not_pressed
  RTL
}
print  "End of Items/ocarina.asm          ", pc

pushpc ; Bank2B freespace

org $02F210 ; OverworldTransitionScrollAndLoadMap
{
  JSL ResetOcarinaFlag
}

; ZS OW
org $02A4CD
RainAnimation_Overridden:
{
  JSL CheckRealTable : BEQ .rainOverlaySet
    ; LDA.b $8C : CMP.b #$9F :
    ; Check the progress indicator
    LDA.l $7EF3C5 : CMP.b #$02 : BRA .skipMovement
  .rainOverlaySet

  ; If misery mire has been opened already, we're done.
  ; LDA.l $7EF2F0 : AND.b #$20 : BNE .skipMovement
  ; Check the frame counter.
  ; On the third frame do a flash of lightning.
  LDA.b $1A

  CMP.b #$03 : BEQ .lightning ; On the 0x03rd frame, cue the lightning.
  CMP.b #$05 : BEQ .normalLight ; On the 0x05th frame, normal light level.
  CMP.b #$24 : BEQ .thunder ; On the 0x24th frame, cue the thunder.
  CMP.b #$2C : BEQ .normalLight ; On the 0x2Cth frame, normal light level.
  CMP.b #$58 : BEQ .lightning ; On the 0x58th frame, cue the lightning.
  CMP.b #$5A : BNE .moveOverlay ; On the 0x5Ath frame, normal light level.

  .normalLight

  ; Keep the screen semi-dark.
  LDA.b #$72

  BRA .setBrightness

  .thunder

  ; Play the thunder sound when outdoors.
  ; LDX.b #$36 : STX.w $012E
  JSL PlayThunderAndRain

  .lightning

  LDA.b #$32 ; Make the screen flash with lightning.

  .setBrightness

  STA.b $9A

  .moveOverlay

  ; Overlay is only moved every 4th frame.
  LDA.b $1A : AND.b #$03 : BNE .skipMovement
    LDA.w $0494 : INC A : AND.b #$03 : STA.w $0494 : TAX
    LDA.b $E1 : CLC : ADC.l $02A46D, X : STA.b $E1
    LDA.b $E7 : CLC : ADC.l $02A471, X : STA.b $E7
  .skipMovement

  RTL
}
assert pc() <= $02A52D
