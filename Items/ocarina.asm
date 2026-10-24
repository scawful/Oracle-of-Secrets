; =========================================================
; Ocarina Multiple Song Select
;
; $030F - Current Song RAM
; 00 - No Song
; 01 - Song of Healing
; 02 - Song of Storms
; 03 - Song of Soaring
; 04 - Song of Time

; SFX2_Accomp
; SFX2 13 (Previous $3E)
org $1A8C60 : db $00

; SFX2_13
org $1A9750
Song_of_Healing:
{
  %SetInstrument($0D) ; Ocarina
  db $2A ; length of quarter note
  db $46
  db B3, A3, F3
  db B3, A3, F3
  db B3, A3
  db $15 ; make this half of whatever you made quarter note
  db E3, D3
  db $7F ; make this triple whatever you made quarter note (max value 7F)
  db E3
  db End
}
assert pc() <= $1A9765

; =========================================================
; D F D - D F D - E F E - F E C
; D F d D F d e f e f e c

org $1A92F7 ; SFX2_2F
Song_of_Storms:
{
  !Storms_Duration = $0F
  !Storms_Params = $46

  !Storms_Duration2 = $1E
  !Storms_Params2 = $3C

  %SetInstrument($0D)

  db !Storms_Duration
  db !Storms_Params ; duration 1/4
  db D3, F3
  db !Storms_Duration2
  db !Storms_Params ; duration 1/2
  db D3

  db !Storms_Duration
  db !Storms_Params ; duration 1/4
  db D3, F3
  db !Storms_Duration2
  db !Storms_Params ; duration 1/2
  db D3

  db !Storms_Duration
  db !Storms_Params2 ; duration 1/4
  db E3, F3, E3

  db F3, E3
  db !Storms_Duration2
  db !Storms_Params2 ; duration 1/2
  db C3
  db End
}
assert pc() <= $1A931F

; =========================================================

; A, D, F, A, D, F
; SFX3_27 Agahnim charge
; 0x003B

org $1A91F0
Song_of_Time:
{
  !Time4th = $2A
  !TimeParams = $46

  %SetInstrument($0D)
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

  db End
}
assert pc() <= $1A922B

; =========================================================

AddTravelBird = $0994FE
AddWeathervaneExplosion = $098D11
Player_DoSfx1 = $078021
Overworld_ReloadSubscreenOverlayAndAdvance_long = $02B1F4

org $07A3DB ; @hook module=Items
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
if !ENABLE_MENU_OCARINA_BLANK_SLOT == 1
    ; No song learned (SongBits = 0): error beep only, no song, SongFlag
    ; unchanged. Same as vanilla's unusable Mushroom in LinkItem_Powder:
    ; $07A2A8 LDA #$3C : JSR PlaySFX_Set2 ($078028), then $07A30C clears
    ; $3A bit 6 (set by CheckYButtonPress $07B073) so the next Y press works.
    LDA.l SongBits : AND.b #!Song_All : BNE .has_song
      LDA.b #$3C : JSR Player_DoSfx2
      LDA.b $3A : AND.b #$BF : STA.b $3A
      RTS
    .has_song
endif
    ; Success... play the flute.
    LDA.b #$80 : STA.w $03F0

    LDA.w $030F : CMP.b #$01 : BEQ .song_of_healing
                  CMP.b #$02 : BEQ .song_of_storms
                  CMP.b #$03 : BEQ .song_of_soaring
                  CMP.b #$04 : BEQ .song_of_time
                  JMP .song_of_healing
    .song_of_time
    LDA.b #$27 : JSR $802F ; Player_DoSfx3
    LDA.b #$02 : STA.b SongFlag
if !ENABLE_OCARINA_SONG_TINT == 1
    ; Purple tint for Song of Time (~32 frames)
    LDA.b #$20 : STA.l SongTintTimer
    LDA.b #$62 : STA.l SongTintColor : STA.b $9A
endif
    RTS

    .song_of_healing
    LDA.b #$13 : JSR Player_DoSfx2
    LDA.b #$01 : STA.b SongFlag
if !ENABLE_OCARINA_SONG_TINT == 1
    ; Green tint for Song of Healing (~32 frames)
    LDA.b #$20 : STA.l SongTintTimer
    LDA.b #$52 : STA.l SongTintColor : STA.b $9A
endif
    RTS

    .song_of_storms
    ; Play the Song of Storms SFX
    LDA.b #$2F : JSR Player_DoSfx2
    LDA.b #$03 : STA.b SongFlag
    JSL OcarinaEffect_SummonStorms
    ; Song of Storms tint handled by rain system ($9A = $72)
    RTS

  .song_of_soaring
  LDA.b #$3E : JSR Player_DoSfx2
if !ENABLE_OCARINA_SONG_TINT == 1
  ; White flash for Song of Soaring (~16 frames)
  LDA.b #$10 : STA.l SongTintTimer
  LDA.b #$32 : STA.l SongTintColor : STA.b $9A
endif

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

  ; The old Soaring count (>=4) never took the count=2 weathervane path.
  ; Independent songs keep the old count, so preserve the travel-bird path.
  BRA .travel_bird_already_released
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
  ; FIRST: Check if rain is already active - always allow dismissal
  ; This must come before area checks so you can dismiss from any area
  LDA.l $7EE00E : BNE .dismiss_storms

  ; Area checks only apply when trying to SUMMON rain
  LDA.w $8A : CMP.b #$00 : BNE +
                JMP .check_for_magic_bean
              +
              CMP.b #$2E : BEQ .jump_error_beep  ; Zora areas already have rain
              CMP.b #$2F : BEQ .jump_error_beep
    ; Check for areas which should not be allowed to have rain
    CMP.b #$05 : BEQ .jump_error_beep
    CMP.b #$06 : BEQ .jump_error_beep
    CMP.b #$07 : BEQ .jump_error_beep
    CMP.b #$10 : BEQ .jump_error_beep
    CMP.b #$18 : BEQ .jump_error_beep
    CMP.b #$28 : BEQ .jump_error_beep
    CMP.b #$29 : BNE .no_error_beep

  .jump_error_beep
    JMP .error_beep

  .no_error_beep

  ; Fall through to summon rain
  JMP .summon_storms

  .dismiss_storms
      ; Check for Zora Temple Waterfall area — show first-time hint
      LDA.w $8A : CMP.b #$1E : BNE .normal_dismiss
        LDA.l ZoraWaterfallHint : BNE .skip_waterfall_hint
          LDA #$01 : STA.l ZoraWaterfallHint
          ; TODO: replace with dedicated waterfall hint message when authored.
          ; Using an existing Sea Zora message avoids a blank placeholder.
          LDA.b #$A6 : LDY.b #$01 ; TODO(dialogue): replace with dedicated waterfall hint text
          JSL Sprite_ShowMessageUnconditional
        .skip_waterfall_hint

      ; Check for Zora Temple Waterfall Trigger
      ; High Precision Zone (16x16 pixels)
      ; Target: Y=$06A8, X=$0CB7 (At the statue)
      ; Range: Y=$06A0-$06B0, X=$0CB0-$0CC0
      
      ; Y Coordinate Check
      LDA.b $21 : CMP.b #$06 : BNE .normal_dismiss ; High Byte
      LDA.b $20 : CMP.b #$A0 : BCC .normal_dismiss ; Low Byte < $A0 (Too North/Close)
                  CMP.b #$B0 : BCS .normal_dismiss ; Low Byte >= $B0 (Too South)

      ; X Coordinate Check
      LDA.b $23 : CMP.b #$0C : BNE .normal_dismiss ; High Byte
      LDA.b $22 : CMP.b #$B0 : BCC .normal_dismiss ; Low Byte < $B0 (Too West)
                  CMP.b #$C0 : BCS .normal_dismiss ; Low Byte >= $C0 (Too East)

      ; Trigger Found!
      JMP .trigger_zora_waterfall

    .normal_dismiss
      ; Clear the flag first so the reload routine loads default overlay
      LDA #$00 : STA $7EE00E
      ; Trigger overlay reload - will load area default (pyramid or other)
      JSL Overworld_ReloadSubscreenOverlayAndAdvance_long
      ; Hide the subscreen and disable color math
      STZ $1D
      STZ $9A
      LDA #$FF : STA $8C
      RTL

    .trigger_zora_waterfall
      ; Clear Rain State
      LDA #$00 : STA $7EE00E
      STZ $1D ; Hide Rain Overlay
      STZ $9A ; Clear Color Math
      LDA #$FF : STA $8C ; Clear Overlay ID
      
      ; Setup Zora Temple Cutscene
      STZ.b $B0        ; Reset Animation Timer
      LDA.b #$01 : STA.w $04C6 ; Set Overlay Index (01 = Zora Temple)
      LDA.b #$16 : STA.b $11   ; Set Submodule to "Open Entrance" ($16)
      
      INC.b $15 ; Force Palette Refresh
      
      RTL

    .summon_storms
    ; Set the flag first so the reload routine sees it
    LDA #$01 : STA $7EE00E
    ; Trigger overlay reload - will load rain due to $7EE00E flag
    JSL Overworld_ReloadSubscreenOverlayAndAdvance_long
    ; Set up visibility and color math
    LDA #$9F : STA $8C
    LDA.b #$01 : STA.b $1D
    LDA.b #$72 : STA.b $9A
    RTL

  .error_beep
  LDA.b #$3C : STA.w $012E ; Error beep
  RTL

  .check_for_magic_bean
  ; Sprite_CheckForPresence reads the sprite ID from $00, not A, and skips
  ; the slot in X; the ocarina is not a sprite, so pass X = $FF. Before this,
  ; the result depended on leftover $00, so the song could do nothing in $00.
  LDA.b #Sprite_BeanVendor : STA.b $00
  LDX.b #$FF
  JSL Sprite_CheckForPresence : BCC .storms_after_bean
    ; Water a planted bean once. Bit $04 = watered, as in bean_vendor.asm
    ; (Core/sram.asm has the $02/$04 names swapped).
    LDA.l MagicBeanProg : AND.b #$01 : BEQ .storms_after_bean
    LDA.l MagicBeanProg : AND.b #$04 : BNE .storms_after_bean
      LDA.l MagicBeanProg
      ORA.b #$04
      STA.l MagicBeanProg
      LDA.b #$2D : STA.w $012F
  .storms_after_bean
  JMP .summon_storms
}

PlayThunderAndRain:
{
  LDA.b #$01 : STA $012D
  LDX.b #$36 : STX.w $012E
  RTL
}

; Tick the song tint timer each frame.
; Decrements SongTintTimer; while active, applies SongTintColor to $9A.
; When timer expires, restores $9A to $00 (unless rain is active).
; Safe to call from any M/X width (forces 8-bit A).
SongTintTick:
{
  PHP
  SEP #$20
if !ENABLE_OCARINA_SONG_TINT == 0
  LDA.b #$00 : STA.l SongTintTimer
  BRA .done
endif
  LDA.l SongTintTimer : BEQ .done
    DEC : STA.l SongTintTimer : BNE .apply
      ; Timer just expired — clear tint (unless storms keep it)
      LDA.l $7EE00E : BNE .done
      STZ.b $9A
      BRA .done
    .apply
    LDA.l SongTintColor : STA.b $9A
  .done
  PLP
  RTL
}

; Rain animation (lightning, thunder, overlay scroll) handled natively
; by ZSOWv3 RainAnimation at $02A4CD when $8C == $9F.
; Song of Storms sets $8C via OcarinaEffect_SummonStorms.

ResetOcarinaFlag:
{
  ; NOTE: Removed automatic clearing of $7EE00E on screen transitions.
  ; Rain flag is now only cleared when player plays Song of Storms again.
  ; The visibility is controlled in ZSCustomOverworld.asm.
  ; Song tint ticking handled in HUD_ClockDisplay (Overworld/time_system.asm).
  LDA.w $0416 : ASL A
  RTL
}

; Independent four-song ownership, adapted from PR #220. Keep helpers out
; of the sprite banks; $42D400 begins the Moon Pearl dream implementation.
pushpc
org $42D000
Ocarina_SongMask:
  db $00, !Song_Healing, !Song_Storms, !Song_Soaring, !Song_Time
Ocarina_CountToBits:
  db $01, $03, $07, $0F

; A low byte = candidate song. Returns it when learned (1-4), otherwise the
; lowest learned song, or 0. Any M/X; preserves X/Y and M/X. A 16-bit caller
; keeps its high byte and must AND #$00FF. No DBR assumption.
Ocarina_ResolveSong_Long:
{
  PHX : PHP
  SEP #$30
  CMP.b #$05 : BCS .lowest
  TAX
  LDA.l Ocarina_SongMask, X : AND.l SongBits : BEQ .lowest
  TXA
  BRA .done
.lowest
  LDA.l SongBits : AND.b #!Song_All : BEQ .done
  LDX.b #$00
.scan
  INX : LSR : BCC .scan
  TXA
.done
  PLP : PLX
  RTL
}

; A low byte = current song; C set = next, clear = previous. Returns the
; next learned song, wrapping, or 0. Any M/X; preserves X/Y and M/X.
Ocarina_StepSong_Long:
{
  PHX : PHP
  SEP #$30
  TAX
  LDA.l SongBits : AND.b #!Song_All : BEQ .done
  BCC .previous
.next
  CPX.b #$04 : BCC .next_ok
    LDX.b #$00
  .next_ok
  INX
  LDA.l Ocarina_SongMask, X : AND.l SongBits : BEQ .next
  BRA .found
.previous
  CPX.b #$02 : BCC .previous_wrap
  CPX.b #$05 : BCC .previous_ok
  .previous_wrap
    LDX.b #$05
  .previous_ok
  DEX
  LDA.l Ocarina_SongMask, X : AND.l SongBits : BEQ .previous
.found
  TXA
.done
  PLP : PLX
  RTL
}

; Migrate an old Flute count (2-5, clamped) only while SongBits is zero,
; then resolve CurrentSong. Equipment restores an empty selection from the
; saved song. Any M/X; preserves X/Y and M/X; clobbers A. No DBR assumption.
Ocarina_ValidateSong_Long:
{
  PHX : PHP
  SEP #$30
  LDA.l SongBits : BNE .converted
  LDA.l Flute : CMP.b #$02 : BCC .converted
  CMP.b #$06 : BCC .count_ok
    LDA.b #$05
  .count_ok
  TAX
  LDA.l Ocarina_CountToBits-2, X : STA.l SongBits
.converted
if !ENABLE_EQUIPMENT_MENU == 1
  LDA.l CurrentSong : BNE .resolve
  LDA.l SavedOcarinaSong
.resolve
  JSL Ocarina_ResolveSong_Long
  STA.l CurrentSong : STA.l SavedOcarinaSong
else
  LDA.l CurrentSong
  JSL Ocarina_ResolveSong_Long
  STA.l CurrentSong
endif
  PLP : PLX
  RTL
}

; Existing teachers retain their count-shaped CMP chains without growing
; bank $30. Return 0 without an Ocarina, else 1 + consecutive learned songs
; from Healing, stopping at the first gap. Any M/X; keeps X/Y and M/X.
Ocarina_SongsInOrder_Long:
{
  JSL Ocarina_ValidateSong_Long
  PHX : PHP
  SEP #$30
  LDA.l Flute : BEQ .done
  LDA.l SongBits : LDX.b #$01
.count
  LSR : BCC .gap
  INX : CPX.b #$05 : BCC .count
.gap
  TXA
.done
  PLP : PLX
  RTL
}

; A low byte = one !Song_* mask. Migrate BEFORE setting a bit so an old
; Healing count cannot be lost when Zelda grants Time. Any M/X; keeps X/Y
; and P; clobbers A. Repeated grants preserve all previously learned songs.
Ocarina_LearnSong_Long:
{
  PHP
  SEP #$20
  PHA
  JSL Ocarina_ValidateSong_Long
  PLA
  ORA.l SongBits : STA.l SongBits
  PLP
  RTL
}

; Called while the Ocarina is equipped. Equipment owns selection; the
; diagnostic legacy profile steps only learned songs with L/R.
UpdateFluteSong_Long:
{
  JSL Ocarina_ValidateSong_Long
if !ENABLE_EQUIPMENT_MENU == 0
  LDA.l CurrentSong : BEQ .done
  LDA.b $F6 : BIT.b #$20 : BNE .left
  BIT.b #$10 : BEQ .done
  LDA.l CurrentSong : SEC
  BRA .step
.left
  LDA.l CurrentSong : CLC
.step
  JSL Ocarina_StepSong_Long
  STA.l CurrentSong
.done
endif
  RTL
}
assert pc() <= $42D400, "Song ownership helpers crossed Moon Pearl dream allocation"
pullpc
%log_end("Items/ocarina.asm", !LOG_ITEMS)

pushpc ; Bank2B freespace

; OverworldTransitionScrollAndLoadMap
org $02F210 : JSL ResetOcarinaFlag ; @hook module=Items name=ResetOcarinaFlag kind=jsl target=ResetOcarinaFlag

; ZSOWv3 RainAnimation at $02A4CD handles all rain visuals natively.
; See Overworld/ZSCustomOverworld.asm:RainAnimation for the active code.
