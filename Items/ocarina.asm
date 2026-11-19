; =========================================================
; Ocarina Multiple Song Select
;
; $030F - Current Song RAM
; 00 - No Song
; 01 - Song of Healing  (SFX2.$13)
; 02 - Song of Storms   (SFX2.$2F)
; 03 - Song of Soaring  (SFX2.$3E)
; 04 - Song of Time     (SFX3.$27)
; 05 - Song of Secrets  (SFX1.$19)
; 06 - Epona's Song     (SFX1.$1B; replaces Elegy of Stone)
;
; Hardware pitch & timing ground truth (Bank $19/$1A SPC700 SFX engine):
;   - 1 SFX tick = 9.143 ms (Timer 0 = $10 [2ms], step $38 -> 256/56 * 2ms).
;   - SFX Inst $0D (SRCN $0D 16-sample loop, ADSR $F9 $6E, Mult $03) plays
;     exactly +7 semitones (a perfect 5th) above Core/music_macros.asm labels:
;       G4=$AB -> D5 (587Hz), A4=$AD -> E5 (659Hz), A4s=$AE -> F5 (699Hz),
;       C5=$B0 -> G5 (784Hz), D5=$B2 -> A5 (880Hz), E5=$B4  -> B5 (989Hz),
;       F5=$B5 -> C6 (1047Hz), G5=$B7 -> D6 (1175Hz), A5=$B9 -> E6 (1320Hz),
;       A5s=$BA -> F6 (1397Hz).
;   - Stream bytes: $E0 <inst>, <dur $01-$7F> [<vol $00-$7F>], <note>, $00 End.

; Disable paired accompaniment voices for overwritten SFX2 slots:
;   SFX2.$13 (was $3E vanilla flute echo) -> $1A8C60 = $00
;   SFX2.$2F (was $38 water splash)       -> $1A8C7C = $00
org $1A8C60 : db $00
org $1A8C7C : db $00

; =========================================================
; 1. Song of Healing — SFX2.$13 ($1A9750..$1A9764, 21B budget)
; Concert MM melody (3/4 waltz, A minor):
;   B5 A5 F5 | B5 A5 F5 | B5 A5 (E5 D5) | E5~~~
; 280 ticks (~2.56s), 19 bytes.
org $1A9750
Song_of_Healing:
{
  %SetInstrument($0D) ; Ocarina
  db $18, $76         ; quarter (~219ms), full lead volume
  db E5, D5, A4s      ; concert B5 - A5 - F5
  db E5, D5, A4s      ; concert B5 - A5 - F5
  db E5, D5           ; concert B5 - A5
  db $0C              ; eighth (~110ms)
  db A4, G4           ; concert E5 - D5
  db $40, $6C         ; dotted-half sustain (~585ms), gentle release
  db A4               ; concert E5
  db End
}
assert pc() <= $1A9765

; =========================================================
; 3. Song of Soaring — SFX2.$3E ($1A9765..$1A977C, 24B budget)
; Concert MM melody (rising soaring triad + ethereal wind echo):
;   F5 B5 D6~ | F5 B5 D6~~ | (echo) F5 B5 D6~~
; 230 ticks (~2.10s), 23 bytes.
org $1A9765
Song_of_Soaring:
{
  %SetInstrument($0D)
  db $10, $76, A4s, E5 ; concert F5 - B5
  db $28, $7C, G5      ; concert D6~ (soaring peak)
  db $10, $76, A4s, E5 ; concert F5 - B5
  db $32, $7C, G5      ; concert D6~~
  db $0C, $46, A4s, E5 ; airy sky echo (F5 - B5)
  db $34, G5           ; echo D6~~ fade
  db End
}
assert pc() <= $1A977D

; =========================================================
; 2. Song of Storms — SFX2.$2F ($1A92F7..$1A931E, 40B budget)
; Concert OoT/MM melody (3/4 Windmill waltz, D minor):
;   D5 F5 D6~ | D5 F5 D6~ | E6. F6 E6 F6 | E6 C6 A5~
; 294 ticks (~2.69s), 30 bytes.
org $1A92F7 ; SFX2_2F
Song_of_Storms:
{
  %SetInstrument($0D)
  db $0C, $76, G4, A4s              ; concert D5 - F5 (eighths)
  db $30, $7C, G5                   ; concert D6~ (half, accented octave leap!)
  db $0C, $76, G4, A4s              ; concert D5 - F5
  db $30, $7C, G5                   ; concert D6~
  db $24, $7C, A5                   ; concert E6. (dotted quarter)
  db $0C, $72, A5s, A5, A5s, A5, F5 ; concert F6 - E6 - F6 - E6 - C6
  db $36, $74, D5                   ; concert A5~ (clean tonic resolution)
  db End
}
assert pc() <= $1A931F

; =========================================================
; 4. Song of Time — SFX3.$27 ($1A91F0..$1A922A, 59B budget)
; Concert OoT/MM melody (4/4 stately Dorian hymn):
;   A5 D5~ F5 | A5 D5~ F5 | (A5 C6) B5 G5 (F5 G5) | A5 D5~~
; 330 ticks (~3.02s), 32 bytes.
org $1A91F0
Song_of_Time:
{
  %SetInstrument($0D)
  db $16, $76, D5      ; concert A5 (quarter)
  db $2C, G4           ; concert D5~ (half)
  db $16, A4s, D5      ; concert F5 - A5
  db $2C, G4           ; concert D5~ (half)
  db $16, A4s          ; concert F5
  db $0B, $7C, D5, F5  ; concert A5 - C6 (rising eighths)
  db $16, E5, C5       ; concert B5 - G5
  db $0B, $72, A4s, C5 ; concert F5 - G5
  db $16, $76, D5      ; concert A5
  db $36, $6C, G4      ; concert D5~~ (resolved tonic)
  db End
}
assert pc() <= $1A922B

; =========================================================
; 5. Song of Secrets (SFX1.$19) & 6. Epona's Song (SFX1.$1B)
; Placed in the verified-unreferenced 100-byte Bank $1A unused SFX block
; ($1A9B2E..$1A9B91, Core/sfx.asm SFXU277E/SFXU279D/SFXU27C9; already inside
; the vanilla $1A8B6C..$1A9C00 ARAM upload, zero pointers into this range).
org $1A9B2E
; Concert A minor / Dorian cavern motif (keeps A-E-A-C-B-A DNA + soft echo):
;   A5 E5 A5 C6~ | B5 G5 A5~~ | (echo) C6 B5 A5~
; 234 ticks (~2.14s), 26 bytes.
Song_of_Secrets:
{
  %SetInstrument($0D)
  db $10, $74, D5, A4, D5 ; concert A5 - E5 - A5
  db $24, $7C, F5         ; concert C6~ (mysterious peak)
  db $10, $76, E5         ; concert B5
  db $10, $70, C5         ; concert G5 (Dorian dip)
  db $36, $78, D5         ; concert A5~~ (home shimmer)
  db $0C, $44, F5, E5     ; cavern echo (C6 - B5)
  db $26, D5              ; echo A5~
  db End
}
; Concert OoT/MM Epona's Song (pastoral D major / B minor lullaby):
;   D6 B5 A5~ | D6 B5 A5~ | D6 B5 A5 B5 A5~~
; 296 ticks (~2.71s), 28 bytes. Alias Elegy_of_Stone retained for symbols.
Epona_Song:
Elegy_of_Stone:
{
  %SetInstrument($0D)
  db $14, $76, G5, E5     ; concert D6 - B5
  db $28, $72, D5         ; concert A5~
  db $14, $78, G5, E5     ; concert D6 - B5
  db $28, $72, D5         ; concert A5~
  db $14, $7C, G5         ; concert D6 (gentle lift)
  db $14, $74, E5, D5, E5 ; concert B5 - A5 - B5
  db $38, $6C, D5         ; concert A5~~ (warm sustain)
  db End
}
assert pc() <= $1A9B92

; SFX1 $19/$1B were unused/duplicate requests. Disable their paired voices;
; the original Flute Boy's $0B/$0C pointers and every active SFX stay intact.
org $1A8BA0 : dw Song_of_Secrets-$1A73B0
org $1A8BA4 : dw Epona_Song-$1A73B0
org $1A8BC8 : db $00
org $1A8BCA : db $00

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
    ; Restore full BGM volume ($F3) once the Ocarina song finishes, unless a
    ; track switch or fade command is already queued in $012C.
    LDA.w $012C : BNE .y_button_not_held
      LDA.b #$F3 : STA.w $012C
  .y_button_not_held

  ; Check for Switch Swong
  JSR UpdateFluteSong
  JSR Link_CheckNewY_ButtonPress : BCC ReturnFromFluteHook
    ; No song learned ($7EF34C < 2): error beep only, no song, SongFlag
    ; unchanged. Same as vanilla's unusable Mushroom in LinkItem_Powder:
    ; $07A2A8 LDA #$3C : JSR PlaySFX_Set2 ($078028), then $07A30C clears
    ; $3A bit 6 (set by CheckYButtonPress $07B073) so the next Y press works.
    ; UpdateFluteSong just validated CurrentSong: 0 = no learned song.
    LDA.w $030F : BNE .has_song
      LDA.b #$3C : JSR Player_DoSfx2
      LDA.b $3A : AND.b #$BF : STA.b $3A
      RTS
    .has_song
    ; Success... play the flute. Duck BGM to half volume ($F2) so loud
    ; overworld tracks never overpower the Ocarina melody, and emit all 6
    ; songs center-panned (no Player_DoSfx* X-position stereo drop).
    LDA.b #$80 : STA.w $03F0
    LDA.w $012C : BNE +
      LDA.b #$F2 : STA.w $012C
    +

    LDA.w $030F : CMP.b #$01 : BEQ .song_of_healing
                  CMP.b #$02 : BEQ .song_of_storms
                  CMP.b #$03 : BEQ .song_of_soaring
                  CMP.b #$04 : BEQ .song_of_time
                  CMP.b #$05 : BNE +
                    JSL OcarinaEffect_Secrets
                    RTS
                  +
                  CMP.b #$06 : BNE +
                    JSL OcarinaEffect_Epona
                    RTS
                  +
                  JMP .song_of_healing
    .song_of_time
    LDA.b #$27 : STA.w $012F
    LDA.b #$02 : STA.b SongFlag
    RTS

    .song_of_healing
    LDA.b #$13 : STA.w $012E
    LDA.b #$01 : STA.b SongFlag
    RTS

    .song_of_storms
    ; Play the Song of Storms SFX (centered stereo)
    LDA.b #$2F : STA.w $012E
    LDA.b #$03 : STA.b SongFlag
    JSL OcarinaEffect_SummonStorms
    ; Song of Storms tint handled by rain system ($9A = $72)
    RTS

  .song_of_soaring
  LDA.b #$3E : STA.w $012E

  ; Are we indoors?
  LDA.b $1B : BNE .return

  ; Are we in the dark world? Then become Moosh form.
  LDA.b $8A : AND #$40 : BEQ .light_world
    JSL Link_TransformMoosh
    RTS
  .light_world

  ; Special Overworld ($80-$BF) uses Special Soaring under unified Module $09.
if !ENABLE_SPECIAL_OVERWORLD_SOARING == 1
  LDA.b $8A : CMP.b #$80 : BCC .normal_soaring
  CMP.b #$C0 : BCS .normal_soaring
    JSL SpecialSoaring_Open
    RTS
  .normal_soaring
else
  LDA.b $10 : CMP.b #$0B : BEQ .return
endif

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

  ; No visited destination yet: error sound, no bird.
  LDA.l TravelSpotsVisited : BNE .has_destination
    LDA.b #$3C : STA.w $012E
    RTS
  .has_destination

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

; The restored cane uses vanilla bank-$07 JSR helpers and the shared rod action.
incsrc "Items/byrna.asm"

; Secret scroll chests (item receipt $33, vanilla Dungeon Map) set
; ScrollsFound ($7EF3BF) by dungeon ID instead of DungeonMapSet1/2 ($7EF368-$7EF369).
; Placed in the measured bank-$07 item extension ($07FDEA..$07FFA0) because
; banks $2B (assert <= $2BE000) and $2C (assert <= $2CF700) are full.
; Entry $0986A7: M=8, X=8, DBR=$09, Y=item receipt ID.
ItemReceipt_SecretScroll:
{
  CPY.b #$33 : BEQ .secret_scroll
  JML $0986BC ; .not_dungeon_item

.secret_scroll
  LDA.l $7E040C
  LDX.b #(.dungeon_ids_end-.dungeon_ids)-1
.find_dungeon
  CMP.l .dungeon_ids, X : BEQ .matched
  DEX : BPL .find_dungeon
  JML $0986B9 ; .handle_gfx (no SRAM write for cave/unknown ID)

.matched
  LDA.l ScrollsFound
  ORA.l .scroll_bits, X
  STA.l ScrollsFound
  JML $0986B9 ; .handle_gfx

.dungeon_ids
  db $0C, $0A, $10, $16, $12, $0E, $18, $04
.dungeon_ids_end

.scroll_bits
  db !Scroll_D1_MushroomGrotto
  db !Scroll_D2_TailPalace
  db !Scroll_D3_KalyxoCastle
  db !Scroll_D4_ZoraTemple
  db !Scroll_D5_GlaciaEstate
  db !Scroll_D6_GoronMines
  db !Scroll_D7_DragonShip
  db !Scroll_D8_SkyTower
}
ItemReceipt_SecretScroll_End:

pushpc
assert read4($0986A7) == $11D033C0, "AncillaAdd_ItemReceipt map check moved"
org $0986A7 ; @hook module=Items name=ItemReceipt_SecretScroll kind=jml target=ItemReceipt_SecretScroll expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=4
  JML ItemReceipt_SecretScroll
assert pc() == $0986AB
pullpc

; Dungeons/hot_floor.asm owns $07FFA0-$07FFFF.
assert pc() <= $07FFA0, "Bank $07 free-space chain reached the hot floor slot ($07FFA0)"
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
  ; Water whichever planted bean spot matches the current outdoor screen ($00/$2D/$15/$33).
  JSL MagicBean_WaterCurrentSpot_Long
  JMP .storms_after_bean
  .storms_after_bean
  JMP .summon_storms
}

PlayThunderAndRain:
{
  LDA.b #$01 : STA $012D
  LDX.b #$36 : STX.w $012E
  RTL
}

; Song tints add a color to the BG palette: the backdrop and BG1/BG2 colors
; $20-$7F, not the BG3 HUD or sprites. Colors are painted from the palette
; buffer ($7EC300), which already holds the day/night shade, into the uploaded
; palette ($7EC500); ending a tint puts the buffer colors back. Color math is
; left alone, so overlays, rain and lightning keep their own blending.
; Outdoors the added color shrinks as the day/night shade deepens: full by day,
; half at the darkest hours (scaled by ColorSubEffect's green step).
SongTint_Table:
  ; frames, red, green, blue added to each color (0-31)
  db $20, $02, $09, $03 ; !SongTint_Healing: green, when a character reacts
  db $20, $09, $07, $01 ; !SongTint_Secrets: gold, when a secret opens

; A (8-bit) = !SongTint_* index. A second song repaints with its own color.
; Safe to call from any M/X width.
SongTint_Start:
{
  PHP
  REP #$10 : PHX : PHY
  SEP #$30
  STA.l SongTintColor
  ASL : ASL : TAX
  LDA.l SongTint_Table,X : STA.l SongTintTimer
  LDA.b $1B : STA.l SongTintContext
  JSR SongTint_ReadPlace : STA.l SongTintContext+1
  LDA.b #$00 : JSR SongTint_Colors
  LDA.b #$01 : STA.l TimeState.GfxDirty
  REP #$10 : PLY : PLX
  PLP
  RTL
}

; Tick the song tint each frame (HUD_ClockDisplay, after RunClock). It waits
; while a submodule ($11) owns the palette: transitions, fades, warps.
; Safe to call from any M/X width.
SongTintTick:
{
  PHP
  REP #$10 : PHX : PHY
  SEP #$30
if !ENABLE_OCARINA_SONG_TINT == 0
  LDA.b #$00 : STA.l SongTintTimer
  BRA .done
endif
  LDA.l SongTintTimer : BEQ .done
  LDA.b $11 : BNE .done
  JSR SongTint_InPlace : BCC .end
  ; Outdoors a pending upload ($15) means the day/night refresh or another
  ; writer rebuilt the palette from the buffer this frame: paint over it.
  LDA.b $1B : BNE +
  LDA.b $15 : BEQ +
    LDA.b #$00 : JSR SongTint_Colors
  +
  LDA.l SongTintTimer : DEC : STA.l SongTintTimer : BNE .done
  .end
  LDA.b #$00 : STA.l SongTintTimer
  LDA.b #$01 : JSR SongTint_Colors
  LDA.b #$01 : STA.l TimeState.GfxDirty
  .done
  REP #$10 : PLY : PLX
  PLP
  RTL
}

; 8-bit A/X/Y from here down.
; Carry set while Link is still in the area or room the tint started in.
SongTint_InPlace:
{
  LDA.b $1B : CMP.l SongTintContext : BNE .moved
  JSR SongTint_ReadPlace : CMP.l SongTintContext+1 : BNE .moved
  SEC
  RTS
  .moved
  CLC
  RTS
}

; A = 0 paints the tint over the buffer colors. A = 1 restores the buffer
; color wherever the uploaded color still holds the tint, so a new area,
; room or scene palette is kept. Uses $00-$09 as scratch and puts them back.
SongTint_Colors:
{
  REP #$30
  PEI ($00) : PEI ($02) : PEI ($04) : PEI ($06) : PEI ($08)
  AND.w #$00FF : STA.b $08
  ; $06 = strength in 16ths: 16 indoors, 16 - green shade step (0-8) outdoors.
  LDA.w #$0010 : STA.b $06
  LDA.b $1B : AND.w #$00FF : BNE +
    LDA.l TimeState.Hours : AND.w #$00FF : ASL : TAX
    LDA.l ColorSubEffect_green,X : LSR : LSR : LSR : LSR : LSR
    EOR.w #$FFFF : SEC : ADC.w #$0010 : STA.b $06
  +
  LDA.l SongTintColor : AND.w #$00FF : ASL : ASL : TAX
  LDA.l SongTint_Table+3,X : AND.w #$001F : JSR .scale
  XBA : ASL : ASL : STA.b $04
  LDA.l SongTint_Table+2,X : AND.w #$001F : JSR .scale
  ASL : ASL : ASL : ASL : ASL : STA.b $02
  LDA.l SongTint_Table+1,X : AND.w #$001F : JSR .scale
  STA.b $00
  LDX.w #$0000
  .color
    ; Add each channel to the buffer color, saturating at 31.
    LDA.l $7EC300,X : AND.w #$001F : CLC : ADC.b $00
    CMP.w #$0020 : BCC + : LDA.w #$001F : +
    STA.b $06
    LDA.l $7EC300,X : AND.w #$03E0 : CLC : ADC.b $02
    CMP.w #$0400 : BCC + : LDA.w #$03E0 : +
    TSB.b $06
    LDA.l $7EC300,X : AND.w #$7C00 : CLC : ADC.b $04
    CMP.w #$8000 : BCC + : LDA.w #$7C00 : +
    ORA.b $06
    LDY.b $08 : BNE .restore
      STA.l $7EC500,X
      BRA .next
    .restore
    CMP.l $7EC500,X : BNE .next
      LDA.l $7EC300,X : STA.l $7EC500,X
    .next
    INX : INX
    CPX.w #$0002 : BNE + : LDX.w #$0040 : + ; skip the BG3 HUD colors
    CPX.w #$0100 : BCC .color
  PLA : STA.b $08
  PLA : STA.b $06
  PLA : STA.b $04
  PLA : STA.b $02
  PLA : STA.b $00
  SEP #$30
  INC.b $15
  RTS

  ; A = amount (0-31) -> A = amount * $06 / 16. Clobbers Y and $00.
  .scale
  STA.b $00
  LDA.w #$0000
  LDY.b $06
  - : CLC : ADC.b $00 : DEY : BNE -
  LSR : LSR : LSR : LSR
  RTS
}

; A = overworld area ($8A) outdoors, room ($A0) indoors.
SongTint_ReadPlace:
{
  LDA.b $1B : BEQ .outdoors
    LDA.b $A0
    RTS
  .outdoors
  LDA.b $8A
  RTS
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
  ; If an Ocarina song was still ducking BGM ($03F0 != 0) when transitioning
  ; screens, restore full BGM volume ($F3) unless another music command is queued.
  LDA.w $03F0 : BEQ +
    STZ.w $03F0
    LDA.w $012C : BNE +
      LDA.b #$F3 : STA.w $012C
  +
  LDA.w $0416 : ASL A
  RTL
}

; Values at $7EF34C determine Ocarina/song progression
; 00 - No Ocarina
; 01 - Ocarina (no songs)
; 02 - 1 song (Healing)
; 03 - 2 songs (Healing, Storms)
; 04 - 3 songs (Healing, Storms, Soaring)
; 05 - 4 songs (Healing, Storms, Soaring, Time)
; 06 - 5 songs (+ Secrets)
; 07 - 6 songs (+ Stone)
UpdateFluteSong_Long:
{
  ; Equipment chooses the song. L/R must not also change it in the world.
  ; CurrentSong ($030F) is volatile; SavedOcarinaSong ($7EF3AB) keeps the
  ; choice across save/reload. Restore from it when $030F is 0, validate
  ; against the learned count (garbage or unlearned -> song 1), then sync.
  ; Learned songs are no longer a contiguous 1..count-1 range (song 6 is
  ; its own bit), so validation picks the lowest learned song instead.
  LDA.w CurrentSong : BNE .epona_check
  LDA.l SavedOcarinaSong : STA.w CurrentSong
.epona_check
  JSL Ocarina_ValidSong_Long
  STA.w CurrentSong : STA.l SavedOcarinaSong
  RTL
  LDA.l $7EF34C : CMP.b #$02 : BCC .equipment_none
  CMP.b #$08 : BCC .equipment_count
  LDA.b #$07
.equipment_count
  DEC : PHA
  LDA.w CurrentSong : BNE .equipment_check
  LDA.l SavedOcarinaSong : STA.w CurrentSong
.equipment_check
  LDA.w CurrentSong : BEQ .equipment_first
  CMP.b $01,S : BCC .equipment_valid
  BEQ .equipment_valid
.equipment_first
  LDA.b #$01 : STA.w CurrentSong
.equipment_valid
  PLA
  LDA.w CurrentSong : STA.l SavedOcarinaSong
  RTL
.equipment_none
  STZ.w CurrentSong
  LDA.b #$00 : STA.l SavedOcarinaSong
  RTL
}

; In: A = song 1-6, 8-bit A. Out: C set = learned. Keeps A, X, Y.
; Songs 1-5: learned when song < $7EF34C (the teacher count; unchanged).
; Song 6 = Epona's Song: learned only by !SideQuest2_EponaSong. A count of 7
; (old Elegy of Stone saves/cheats) no longer teaches song 6.
Ocarina_SongLearned_Long:
{
  PHA
  CMP.b #$01 : BCC .no
  CMP.b #$07 : BCS .no
  CMP.b #$06 : BEQ .epona
  CMP.l $7EF34C : BCS .no
.yes
  PLA : SEC : RTL
.epona
  LDA.l SideQuestProg2 : AND.b #!SideQuest2_EponaSong : BNE .yes
.no
  PLA : CLC : RTL
}

; Out: A = CurrentSong when it is learned, else the lowest learned song,
; else 0 (no song). 8-bit A. Keeps X, Y. Writes nothing; any data bank.
Ocarina_ValidSong_Long:
{
  LDA.l $7E0000+CurrentSong
  JSL Ocarina_SongLearned_Long : BCS .done
  LDA.b #$01
.next
  JSL Ocarina_SongLearned_Long : BCS .done
  INC : CMP.b #$07 : BCC .next
  LDA.b #$00
.done
  RTL
}

; Epona's Song calls Epona (decisions.org 2026-11-16). Melody: slot-6 notes
; ($1B, Elegy's) until Epona's Song is scored. Refused calls play the error chime.
OcarinaEffect_Epona:
{
  STZ.b SongFlag
  LDA.b #$1B : STA.l $7E012D
if !ENABLE_HORSE_FORM == 1 && !ENABLE_HORSE_PARK_ANYWHERE == 1
  JSL HorseCall_Long : BCS .called
endif
  LDA.b #$3C : STA.l $7E012E
.called
  RTL
}
incsrc "Items/song_secrets_stone.asm"
if !ENABLE_SPECIAL_OVERWORLD_SOARING == 1
  incsrc "Items/special_soaring.asm"
endif
; Called by TimeSystem_CheckCanRun .overworld (Overworld/time_system.asm, bank $34)
; from HUD_ClockDisplay's PHP/PLP wrapper. Calls Sprite_LoadGraphicsProperties
; ($00FC62) only when module, area, phase (CheckIfNight), song tint or
; TimeState.GfxDirty changed, instead of every overworld frame.
; Contract: entry M=8, any X; exit M=8, X unchanged; A clobbered; DBR unchanged
; (long addressing only). CheckIfNight leaves P alone; SEP #$20 is defensive.
TimeSystem_GfxGate:
{
  LDA.l TimeState.GfxDirty : BNE .reload
  LDA.b $10 : CMP.l TimeState.GfxLastMode : BNE .reload
  LDA.b $8A : CMP.l TimeState.GfxLastArea : BNE .reload
  JSR .tint : CMP.l TimeState.GfxLastTint : BNE .reload
  JSL CheckIfNight : SEP #$20
  CMP.l TimeState.GfxLastPhase : BEQ .done
  .reload
  PHP : REP #$30 ; vanilla routine expects M=16, X=16
  JSL $00FC62 ; Sprite_LoadGraphicsProperties
  PLP
  LDA.b $10 : STA.l TimeState.GfxLastMode
  LDA.b $8A : STA.l TimeState.GfxLastArea
  JSR .tint : STA.l TimeState.GfxLastTint
  JSL CheckIfNight : SEP #$20
  STA.l TimeState.GfxLastPhase
  LDA.b #$00 : STA.l TimeState.GfxDirty
  .done
  RTL

  ; A = $80|color while a song tint runs, else 0.
  .tint
  LDA.l SongTintTimer : BEQ +
    LDA.l SongTintColor : ORA.b #$80
  +
  RTS
}

%log_end("Items/ocarina.asm", !LOG_ITEMS)

pushpc ; Bank2B freespace

; OverworldTransitionScrollAndLoadMap
org $02F210 : JSL ResetOcarinaFlag ; @hook module=Items name=ResetOcarinaFlag kind=jsl target=ResetOcarinaFlag

; ZSOWv3 RainAnimation at $02A4CD handles all rain visuals natively.
; See Overworld/ZSCustomOverworld.asm:RainAnimation for the active code.

