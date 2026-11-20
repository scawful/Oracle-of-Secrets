; ---------------------[ Time system ]---------------------

; Sprite_Main.dont_reset_drag
; Executes every frame to update the clock.
; Stack contract: HUD_ClockDisplay uses PHP/PLP only; RunClock and DrawClockToHud
; must not perform unbalanced PHA/PLA/PHX/PLX/PHY/PLY so that PLP restores the same P.
org $068361 ; @hook module=Overworld
  JSL HUD_ClockDisplay
pullpc
HUD_ClockDisplay:
{
  PHP ; Preserve caller M/X flags
  JSR RunClock
  if !ENABLE_GLADE_AMBUSH == 1
    JSL KydrogLanding_Tick ; Abyss landing pan (Sprites/Bosses/kydrog.asm)
  endif
  JSL SongTintTick ; After RunClock: repaints over an hourly palette refresh
    JSL DreamWisdom_HUDHidden : BCS .no_clock ; Wisdom scene: HUD blank
  JSR DrawClockToHud
    .no_clock
  ; Vanilla calls Garnish_ExecuteUpperSlots_long from Sprite_Main with 8-bit
  ; A/X/Y (LDX.b #$1D / CPX.b #$0E). With 16-bit X the upper slots ($0F-$1D)
  ; never ran: thrown pot/bush debris (garnish $16) froze invisibly (2026-09-26).
  SEP #$30
    JSL RichardQuest_Tick ; Overworld/richard_quest.asm
  JSL $09B06E ; Restore Garnish_ExecuteUpperSlots_long
  PLP
  RTL
}

; Zarby Intro and Credits fix
pushpc
org $0CC265 ; Intro_FadeLogoIn ; @hook module=Overworld
  JSL LogoFadeInSetClock
pullpc
LogoFadeInSetClock:
{
  if !SPECIAL_OVERWORLD_PALETTE_ENABLED == 1
  JSL Oracle_SpecialOverworldPaletteReset
  endif
  LDA.b #$00 : STA.l SpecialOverworld_VortexWorld
  JSL $00ED7C ; IntroLogoPaletteFadeIn
  LDA.b #$08 : STA.l TimeState.Hours ; Set the time to 6:00am
  LDA.b #$3F : STA.l TimeState.Speed ; Set the time speed
  LDA.b #$01 : STA.l TimeState.GfxDirty
  RTL
}

pushpc
org $0CCA59 ; @hook module=Overworld
  JSL ResetClockTriforceRoom
pullpc
ResetClockTriforceRoom:
{
  if !SPECIAL_OVERWORLD_PALETTE_ENABLED == 1
  JSL Oracle_SpecialOverworldPaletteReset
  endif
  LDA.b #$00 : STA.l SpecialOverworld_VortexWorld
  JSL $00E384 ; LoadCommonSprites_long
  LDA.b #$00 : STA.l TimeState.Hours ; low hours for palette?
  LDA.b #$00 : STA.l TimeState.Minutes ; high hours for palette?
  LDA.b #$01 : STA.l TimeState.GfxDirty
  RTL
}

DrawClockToHudLong:
{
  JSR DrawClockToHud
  RTL
}

; Format TimeState.Hours (0..23) and TimeState.Minutes (0..59) into the
; 6-tile bottom-center BG3 row-26 clock buffer HudClockBuffer ($7EC858..$7EC863,
; VRAM $634D cols 13-18) using 12-hour time with leading-zero suppression and
; Majora's Mask-style Sun (06:00..17:59, Pal 5 gold $3415) / Moon (18:00..05:59,
; Pal 3 cool blue/silver $2C15) icon on CHR tile $015.
; Sets $16 = 1 only when the displayed time actually changes during active
; gameplay ($10 in {$07, $09, $0B}); skips $16 on menu/dialogue/map ($0E) and
; marks HudClockLastMinutes = $FF so the first frame back in gameplay syncs.
; Contract: preserves caller P, X, Y and DBR; A clobbered.
DrawClockToHud:
{
  PHP
  REP #$10 : PHX : PHY
  SEP #$30

  ; Fast-path: skip rebuild + $16 upload when Hours/Minutes are unchanged
  ; and the colon sentinel ($24AB at +6) confirms HudClockBuffer is valid.
  LDA.l HudClockBuffer+6 : CMP.b #$AB : BNE .rebuild
  LDA.l HudClockBuffer+7 : CMP.b #$24 : BNE .rebuild
  LDA.l TimeState.Hours : CMP.l HudClockLastHours : BNE .rebuild
  LDA.l TimeState.Minutes : CMP.l HudClockLastMinutes : BNE .rebuild
    JMP .done

  .rebuild
  LDA.l TimeState.Hours
  STA.l HudClockLastHours
  CMP.b #$18 : BCC .hours_ok
    LDA.b #$00
  .hours_ok

  ; Day (06..17) -> Sun ($34 = Pal 5 gold), Night (00..05, 18..23) -> Moon ($2C = Pal 3 blue/silver).
  ; Matches CheckIfNight ($06 <= Hours < $12).
  LDY.b #$2C
  CMP.b #$06 : BCC .icon_pal_ready
  CMP.b #$12 : BCS .icon_pal_ready
    LDY.b #$34
  .icon_pal_ready

  ; Convert 24-hour (0..23) -> 12-hour (1..12): 0->12, 1..12->1..12, 13..23->1..11.
  CMP.b #$00 : BNE .not_midnight
    LDA.b #$0C
    BRA .hour12_ready
  .not_midnight
  CMP.b #$0D : BCC .hour12_ready
    SEC : SBC.b #$0C
  .hour12_ready

  ; Format hour digits + icon without leading zero on single-digit hours (1..9).
  CMP.b #$0A : BCC .single_digit_hour
    ; Two-digit hour (10..12): cols 13-15 = [Icon][1][0..2]
    SEC : SBC.b #$0A
    ORA.b #$90 : STA.l HudClockBuffer+4
    LDA.b #$24 : STA.l HudClockBuffer+5
    LDA.b #$91 : STA.l HudClockBuffer+2
    LDA.b #$24 : STA.l HudClockBuffer+3
    LDA.b #$15 : STA.l HudClockBuffer+0
    TYA        : STA.l HudClockBuffer+1
    BRA .draw_colon_and_mins

  .single_digit_hour
    ; Single-digit hour (1..9): cols 13-15 = [blank $207F][Icon][1..9]
    ORA.b #$90 : STA.l HudClockBuffer+4
    LDA.b #$24 : STA.l HudClockBuffer+5
    LDA.b #$15 : STA.l HudClockBuffer+2
    TYA        : STA.l HudClockBuffer+3
    LDA.b #$7F : STA.l HudClockBuffer+0
    LDA.b #$20 : STA.l HudClockBuffer+1

  .draw_colon_and_mins
  ; Col 16 (+6): white HUD colon ':' ($24AB)
  LDA.b #$AB : STA.l HudClockBuffer+6
  LDA.b #$24 : STA.l HudClockBuffer+7

  ; Minutes (0..59) -> always two digits (e.g. :05, :34) at cols 17-18
  LDA.l TimeState.Minutes
  STA.l HudClockLastMinutes
  CMP.b #$3C : BCC .mins_ok
    LDA.b #$00
  .mins_ok

  LDX.b #$00
  .div10
    CMP.b #$0A : BCC .mins_split
    SEC : SBC.b #$0A
    INX
    BRA .div10
  .mins_split
  ORA.b #$90 : STA.l HudClockBuffer+$0A
  LDA.b #$24 : STA.l HudClockBuffer+$0B
  TXA : ORA.b #$90 : STA.l HudClockBuffer+8
  LDA.b #$24 : STA.l HudClockBuffer+9

  ; Trigger NMI HUD upload only in active gameplay ($07/$09/$0B).
  ; Outside gameplay (menu/dialogue/map $0E, transitions), defer VRAM upload
  ; by invalidating HudClockLastMinutes so the first gameplay frame syncs.
  LDA.b $10
  CMP.b #$07 : BEQ .upload
  CMP.b #$09 : BEQ .upload
  CMP.b #$0B : BEQ .upload
    LDA.b #$FF : STA.l HudClockLastMinutes
    BRA .done
  .upload
  LDA.b #$01 : STA.b $16

  .done
  REP #$10 : PLY : PLX
  PLP
  RTS
}

; ---------------------------------------------------------
; NMI: after the HUD rows 0-4 DMA, stream bottom row 26 from contiguous WRAM
; (HudCornerBuffer rupees cols 2-6 + keys cols 28-29 + HudClockBuffer 12h clock
; cols 13-18) and upload 2bpp HUD CHR tiles $014 (item-box strip) + $015
; (Sun during 06:00..17:59 or Moon during 18:00..05:59) in one 32-byte DMA.
; Hidden HUD ($7EC73A == #$7F: Opening_HideHUD, Dream Wisdom): stream 26 bytes
; of $207F blank cells from $7EC700 to all three bottom segments and skip CHR.
; In: from $008B82, A 8-bit, X/Y 16-bit, DBR $00, DMA0 mode $01 -> $2118,
; VMAIN $80. Out: A = $01; X/Y clobbered (the NMI reloads them).
HUD_NMIUpload:
{
  LDA.b #$01 : STA.w $420B                      ; replaced: HUD rows 0-4

  ; Dialogue / sign / menu ($10 == #$0E): skip extra BG3 row-26 & CHR DMAs so
  ; VBlank stays clear during BG3 text streaming (prevents sign transfer flicker).
  LDA.b $10 : CMP.b #$0E : BNE .not_overlay
    LDA.b #$00 : STA.l HudChrCache
if defined("ENABLE_HORSE_FORM")
if !ENABLE_HORSE_FORM == 1
    LDA.l Horse_HudState : BPL .overlay_ret
      LDA.b #$8F : STA.l Horse_HudState         ; force frame-1 repaint when dialogue/menu closes
  .overlay_ret
endif
endif
    LDA.b #$01 : RTL

  .not_overlay
  ; Invalidate static CHR cache on module change ($10) or submodule transition ($11 != 0).
  CMP.l HudChrContext : BNE .invalidate_chr
  LDA.b $11 : BEQ .chr_ctx_ok
  .invalidate_chr
    LDA.b #$00 : STA.l HudChrCache
    LDA.b $10 : STA.l HudChrContext
  .chr_ctx_ok

  assert HudClockBuffer == HudCornerBufferEnd
  LDX.w #HudCornerBuffer&$FFFF
  LDA.l $7EC73A : CMP.b #$7F : BNE .shown
    LDA.b #$00 : STA.l HudChrCache              ; hidden HUD: force CHR re-upload on unhide
    LDX.w #$C700                                ; hidden HUD: blank cells
  .shown
  STX.w $4302
  LDA.b #$7E : STA.w $4304
  LDY.w #$6342 : STY.w $2116                    ; BG3 row 26, cols 2-6 (rupees)
  LDY.w #$000A : STY.w $4305
  LDA.b #$01 : STA.w $420B
  LDY.w #$635C : STY.w $2116                    ; BG3 row 26, cols 28-29 (keys)
  LDY.w #$0004 : STY.w $4305                    ; continues at HudCornerBuffer+$0A
  STA.w $420B
  LDY.w #$634D : STY.w $2116                    ; BG3 row 26, cols 13-18 (clock)
  LDY.w #$000C : STY.w $4305                    ; continues at HudClockBuffer ($7EC858)
  STA.w $420B

  CPX.w #$C700 : BNE +
    BRL .maybe_carrots_hidden
  +
    ; Dirty-flagged 32B Sun/Moon CHR upload ($70A0): skips DMA on steady HUD ticks.
    LDY.w #HUD_StripAndMoonTiles&$FFFF          ; default: night (Moon, tag 2)
    LDX.w #$0002
    LDA.l TimeState.Hours
    CMP.b #$06 : BCC .check_icon_cache
    CMP.b #$12 : BCS .check_icon_cache
      LDY.w #HUD_StripAndSunTiles&$FFFF         ; day 06:00..17:59 (Sun, tag 1)
      LDX.w #$0001
    .check_icon_cache
    TXA
    EOR.l HudChrCache : AND.b #$03 : BEQ .icon_chr_ok
      LDA.l HudChrCache : AND.b #$FC : STA.l HudChrCache
      TXA : ORA.l HudChrCache : STA.l HudChrCache
      LDX.w #$70A0 : STX.w $2116                ; HUD CHR tiles $014-$015
      STY.w $4302
      LDA.b #HUD_StripAndSunTiles>>16 : STA.w $4304
      LDY.w #$0020 : STY.w $4305                ; 32 bytes ($014 strip + $015 icon)
      LDA.b #$01 : STA.w $420B
    .icon_chr_ok
if defined("ENABLE_HORSE_FORM")
if !ENABLE_HORSE_FORM == 1
    LDA.l Horse_HudState : BNE +
      LDA.b #$01 : RTL
    +
    LDA.l Horse_HudState : BMI +
      BRL .carrots_blank
    +
    LDA.l $7E02B2 : CMP.b #$09 : BEQ +
      BRL .carrots_blank
    +
      LDA.b #$7E : STA.w $4304
      LDY.w #HudCarrotTopBuffer&$FFFF : STY.w $4302
      LDY.w #$630E : STY.w $2116                ; BG3 row 24, cols 14-18 (carrot leaves)
      LDY.w #$000A : STY.w $4305
      LDA.b #$01 : STA.w $420B
      LDY.w #$632E : STY.w $2116                ; BG3 row 25, cols 14-18 (carrot bodies, contiguous)
      LDY.w #$000A : STY.w $4305
      STA.w $420B
      ; Dirty-flagged 64B Carrot CHR upload ($7A48/$7A10): once per mount/transition.
      LDA.l HudChrCache : BPL +
        LDA.b #$01 : RTL
      +
        ORA.b #$80 : STA.l HudChrCache
        LDA.b #Horse_CarrotFullChr>>16 : STA.w $4304
        LDY.w #Horse_CarrotFullChr&$FFFF : STY.w $4302
        LDY.w #$7A48 : STY.w $2116              ; BG3 tiles $0149-$014A (full carrot top/bot)
        LDY.w #$0020 : STY.w $4305
        LDA.b #$01 : STA.w $420B
        LDY.w #Horse_CarrotEmptyChr&$FFFF : STY.w $4302
        LDY.w #$7A10 : STY.w $2116              ; BG3 tiles $0142-$0143 (empty carrot top/bot)
        LDY.w #$0020 : STY.w $4305
        STA.w $420B
      LDA.b #$01 : RTL

  .maybe_carrots_hidden
    LDA.l Horse_HudState : BEQ .done
    LDA.l Horse_HudState : BPL .carrots_blank
      LDA.b #$8F : STA.l Horse_HudState         ; repaint once HUD unhides
    BRA .carrots_blank_keep_state

  .carrots_blank
    LDA.b #$00 : STA.l Horse_HudState
  .carrots_blank_keep_state
    LDA.b #$7E : STA.w $4304
    LDY.w #$C700 : STY.w $4302
    LDY.w #$630E : STY.w $2116
    LDY.w #$000A : STY.w $4305
    LDA.b #$01 : STA.w $420B
    LDY.w #$C700 : STY.w $4302
    LDY.w #$632E : STY.w $2116
    LDY.w #$000A : STY.w $4305
    STA.w $420B
else
  .maybe_carrots_hidden
endif
else
  .maybe_carrots_hidden
endif
  .done
  LDA.b #$01
  RTL
}

; Contiguous 32-byte 2bpp CHR bundles for VRAM $70A0-$70AF (tiles $014-$015).
; Tile $014: item-box border strip (top edge $2014 / V-flipped bottom $A014).
; Tile $015: Majora's Mask-inspired 8x8 Sun (Pal 5 gold) or Crescent Moon (Pal 3 blue/silver).
HUD_StripAndSunTiles:
HUD_StripTile:
  db $00, $00, $00, $00, $00, $00, $00, $00
  db $FF, $FF, $00, $FF, $FF, $00, $00, $FF
HUD_SunTile:
  db $28, $38, $28, $7C, $C6, $BA, $01, $FF
  db $C6, $BA, $2A, $7E, $28, $38, $10, $10

HUD_StripAndMoonTiles:
  db $00, $00, $00, $00, $00, $00, $00, $00
  db $FF, $FF, $00, $FF, $FF, $00, $00, $FF
HUD_MoonTile:
  db $38, $38, $4C, $74, $98, $E8, $98, $E8
  db $98, $E8, $9E, $E6, $42, $7E, $3C, $3C
assert (HUD_StripAndSunTiles>>16) == (HUD_StripAndMoonTiles>>16)

if defined("ENABLE_HORSE_FORM")
if !ENABLE_HORSE_FORM == 1
; Two-tone 2-row OoT-tilt Epona HUD carrot 2bpp CHR bundles (Bank $34).
; Full Top ($0149, Pal 7 emerald leaf) + Full Bot ($014A, Pal 2 warm amber body)
; Empty Top ($0142, Pal 4 grey leaf) + Empty Bot ($0143, Pal 4 shaded grey silhouette)
Horse_CarrotFullChr:
  db $00,$00,$00,$00,$00,$00,$0A,$0A, $1F,$15,$2E,$32,$3C,$24,$7C,$64
  db $5E,$62,$5E,$6A,$7C,$44,$58,$68, $70,$50,$60,$60,$00,$00,$00,$00
Horse_CarrotEmptyChr:
  db $00,$00,$00,$00,$00,$00,$0A,$0A, $1F,$15,$3E,$22,$3C,$24,$7C,$64
  db $7E,$42,$66,$42,$6C,$44,$78,$48, $70,$50,$60,$60,$00,$00,$00,$00
assert pc()-Horse_CarrotFullChr == 64
assert (Horse_CarrotFullChr>>16) == (Horse_CarrotEmptyChr>>16)
endif
endif

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
  LDA $10 : CMP #$07 : BEQ .non_ow_increasing ; dungeon/building?
            CMP #$09 : BEQ .overworld ; overworld?
            CMP #$0B : BEQ .overworld ; special overworld?
            CMP #$0E : BEQ .dialog  ; dialog box?
              STA.l TimeState.GfxLastMode
              CLC : RTS
    .non_ow_increasing
    STA.l TimeState.GfxLastMode
    BRA .counter_increasing

    .overworld
    ; Sprite gfx reload gate: TimeSystem_GfxGate (Items/ocarina.asm, bank $2B;
    ; bank $34 has no room). M=8 in and out, X width kept, A clobbered.
    JSL TimeSystem_GfxGate

    .skip_reload_gfx
    LDA $11 : CMP #$23 : BNE .mosaic ; HDMA transfer? (warping)
      ; Lol what?
    .mosaic

    CMP #$0D : BMI .counter_increasing ; Mosaic ?
      CLC : RTS

    .dialog
    STA.l TimeState.GfxLastMode
    ; check submodule to prevent the counter from increasing if save/menu open
    LDA $11 : CMP #$02 : BEQ .counter_increasing ; NPC/signs speech
      CLC : RTS

  .counter_increasing
  SEC : RTS
}

TimeSystem_UpdateGBCLink:
{
  ; The clock also runs indoors. Match the dungeon loader and mask-removal
  ; base-form policy instead of reapplying GBC art from the return's world.
  JSL LinkGraphics_ApplyD8Base : BCS .light_world
  ; GBC Link code
  LDA.l SavedWorld : BEQ .light_world
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
    ; Begin also restores reference holes before an indoor departure.
    if !SPECIAL_OVERWORLD_PALETTE_ENABLED == 1
    JSL Oracle_SpecialOverworldPaletteBegin
    endif
    ; check indoors/outdoors
    LDA $1B	: BEQ .outdoors
      ; Rejected indoor Begin is balanced without touching the fade buffer.
      if !SPECIAL_OVERWORLD_PALETTE_ENABLED == 1
      JSL Oracle_SpecialOverworldPaletteCompleteBuffer
      endif
      RTS
    .outdoors

    JSL RomToPaletteBuffer	; update buffer palette
    if !SPECIAL_OVERWORLD_PALETTE_ENABLED == 1
    JSL Oracle_SpecialOverworldPaletteCompleteBuffer
    endif
    JSL PaletteBufferToEffective	; update effective palette

    ; Refresh explicitly even in diagnostic builds with Masks disabled.
    ; An hourly tint change does not change overlays: keep $1C/$1D, $99/$9A,
    ; fixed color and BG scroll exactly as the active overlay configured them.
    JSL RefreshOverworldBackdrop
    LDA.b #$01 : STA.l TimeState.GfxDirty
    INC.b $15
    RTS
}

CheckForSongOfTime:
{
  ; Check if Song of Time was activated
  LDA.b SongFlag : CMP.b #$02 : BEQ .song_of_time
    ; Speed 0 is only valid while the song is active. A song listener or
    ; Save & Quit can clear SongFlag before 6am/6pm; without this, time
    ; stays fast for the rest of the session (Discord 2024-08-25).
    LDA.l TimeState.Speed : BNE +
      LDA.b #$3F : STA.l TimeState.Speed
    BRA +
  .song_of_time
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
  JSL MagicBean_AdvanceDailyGrowth_Long
  RTS
}

; Contract: Does NOT preserve P. Callers must set REP/SEP as needed after JSL.
; Return: A = game state / phase (0, 1, 2, or 3). P state unspecified.
; Callers: LoadOverworldSprites_Interupt (ZSCustomOverworld.asm) does REP #$30 after JSL.
CheckIfNight:
{
  JSR LoadPeacetimeSprites : BCS +
    RTL
  +
  LDA.l GameState : CMP.b #$02 : BCC .day_time
    ; Farore met (GameState 2) but Kydrog's ambush not played yet: keep the
    ; day list. Only it holds Farore and Kydrog in the Forest Glade ($80);
    ; the night list has neither, so at night Link auto-walked into the Maku
    ; Tree's $20 with InCutScene still 1 (input locked): softlock.
    LDA.l KydrogFaroreRemoved : BEQ .day_time
    LDA TimeState.Hours : CMP.b #$12 : BCS .night_time
      LDA TimeState.Hours : CMP.b #$06 : BCC .night_time
      .day_time
      LDA.l GameState
      ; GameState 3 uses the GameState-2 day list until the ending
      ; (decisions.org: GameState 3 changes nothing in the overworld yet).
      CMP.b #!GameState_FaroreRescued : BCC +
        LDA.b #!GameState_KydrogComplete
      +
      RTL
  .night_time
  LDA.b #$03
  RTL
}

; Contract: Does NOT preserve P. Sets SEP #$30 on entry; returns with REP #$30 on all paths.
; Return: A = game state / phase (16-bit). Currently no active callers (hook sites commented out for ZSOWv3).
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

org $02FF80 ; free space on bank $02 ; @hook module=Overworld
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
  if !SPECIAL_OVERWORLD_NATIVE == 1
  LyraCall_SpritePalette_0 = pc()
  JSL.l Lyra_ReadSpritePalette
  else
  LDA.l $7EFD40,X
  endif
  STA.b $00

  if !SPECIAL_OVERWORLD_NATIVE == 1
  LyraCall_PaletteSet_0 = pc()
  JSL.l Lyra_ReadPaletteSet
  else
  LDA.l OverworldPalettesScreenToSet_New,X
  endif
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
org $1BEF3D : JSL LoadDayNightPaletteEffect ; @hook module=Overworld name=LoadDayNightPaletteEffect kind=jsl target=LoadDayNightPaletteEffect

; Palettes_LoadMultiple.next_color
org $1BEF61 : JSL LoadDayNightPaletteEffect ; @hook module=Overworld name=LoadDayNightPaletteEffect kind=jsl target=LoadDayNightPaletteEffect

; Palettes_LoadMultiple_Arbitrary.next_color
org $1BEF84 : JSL LoadDayNightPaletteEffect ; @hook module=Overworld name=LoadDayNightPaletteEffect kind=jsl target=LoadDayNightPaletteEffect

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
    LDA.w !SmallestBlue
  .no_blue_sign_change
  STA.l TimeState.BlueVal

  ; Subtract amount to green field based on a table
  LDA.l TimeState.SubColor : AND #$03E0 : STA.l TimeState.GreenVal
  SEC : SBC.l .green, X : STA.l TimeState.TempColor

  ; Mask out everything except the green bits
  AND #$03E0 : CMP.l TimeState.TempColor : BEQ .no_green_sign_change ; overflow ?
    LDA.w !SmallestGreen
  .no_green_sign_change
  STA.l TimeState.GreenVal

  ; substract amount to red field based on a table
  LDA.l TimeState.SubColor : AND #$001F : STA.l TimeState.RedVal
  SEC : SBC.l .red, X : STA.l TimeState.TempColor

  ; mask out everything except the red bits
  AND #$001F : CMP.l TimeState.TempColor : BEQ .no_red_sign_change ; overflow ?
    LDA.w !SmallestRed
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

; Contract: any M/X width; caller has established outdoors. Preserve P/X/Y/DBR.
; A and TimeState color scratch are clobbered. Upload scheduling stays with caller.
RefreshOverworldBackdrop:
{
  PHP
  REP #$30
  PHX
  JSL ReadOverworldBackdropColor
  JSL BackgroundFix
  PLX
  PLP
  RTL
}

; Contract: M=16, X=16. Returns raw BGR555 in A, clobbers X.
; ZS has 160 word entries; $80-$9F require offsets $0100-$013E.
; The bridge shares area $80 and is distinguished by fake exit room $0181.
ReadOverworldBackdropColor:
{
  LDA.b $8A : AND.w #$00FF
Lyra_CurrentBackdropLegacy:
  CMP.w #$00A0 : BCS .invalid_area
  CMP.w #$0080 : BNE .area_color
    LDA.b $A0 : CMP.w #$0181 : BNE .reload_area
      LDA.l $288149 ; Pool_BGColorTable_Bridge
      RTL
  .reload_area
  LDA.b $8A : AND.w #$00FF
  .area_color
  ASL : TAX
  LDA.l $288000, X ; Pool_BGColorTable
  RTL
  .invalid_area
  LDA.w #$0000
  RTL
}

; Contract: M=16, any X width. Raw color in A; tinted color out.
; Preserve X for palette loaders. Zero is black, not a request to retain
; the previous area's color. Seed SubColor here, never inherit old scratch.
TintBackdropColor:
{
  STA.l TimeState.SubColor
  CMP.w #$0000 : BEQ .black
    PHX
    JSL ColorSubEffect
    PLX
  .black
  RTL
}

BackgroundFix:
{
  JSL TintBackdropColor
  STA.l PalCgram500_HUD
  STA.l PalBuf300_HUD
  STA.l PalCgram540_BG
  STA.l PalBuf340_BG
  RTL
}

MosaicFix:
{
  ; Fade targets only: writing the main buffer here doubles PaletteFilter.
  JSL TintBackdropColor
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
  PHA : SEP #$20 : LDA.b #$01 : STA.l TimeState.GfxDirty : REP #$20 : PLA
  RTL
}

ColorBgFix:
{
  ; $0ED618 already tinted A through InitColorLoad2/MosaicFix. The other
  ; active entry, $0ED5F4, supplies literal black. Replay the displaced store
  ; without tinting again; vanilla $0ED5FD-$0ED605 writes the other buffers.
  ; Contract: M=16. Preserve A, X, Y, P and DBR.
  STA.l PalCgram500_HUD
  RTL
}

; Contract: Does NOT modify P explicitly. Return P = entry P. Stack: no push/pull; JSR-safe.
; Return: C set = use peacetime sprites; C clear = use normal phase. A clobbered.
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
  LDA.b #$00 : STA.l SpecialOverworld_VortexWorld
  LDA.b #$08 : STA.l TimeState.Hours
  LDA.b #$01 : STA.l TimeState.GfxDirty
  ; Clear Dark World GBC / mask form across both Pause and Game Over Save & Quit.
  LDA.b #$00 : STA.l $7E02B2
  LDA.b #$10 : STA.l $7E00BC
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
    PHA : SEP #$20 : LDA.b #$01 : STA.l TimeState.GfxDirty : REP #$20 : PLA
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
  LDA.b #$01 : STA.l TimeState.GfxDirty
  LDA.l $7EC017
  RTL
}

pushpc

; SetBGColorMainBuffer
org $0ED5F9 : JSL ColorBgFix ; @hook module=Overworld name=ColorBgFix kind=jsl target=ColorBgFix
assert pc() <= $0ED5FD ; The remaining vanilla stores must stay intact.

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
org $1BEE2D : JSL GlovesFix ; @hook module=Overworld name=GlovesFix kind=jsl target=GlovesFix

; org $0ABA5A
; TODO: Handle overworld map palette for flashing icons

; Module0E_03_00_DarkenAndPrep
org $0ED956 : JSL FixDungeonMapColors ; @hook module=Overworld name=FixDungeonMapColors kind=jsl target=FixDungeonMapColors

; UnderworldMap_RecoverGFX
org $0AEFA6 : JSL RestoreTimeForDungeonMap ; @hook module=Overworld name=RestoreTimeForDungeonMap kind=jsl target=RestoreTimeForDungeonMap

; RefreshLinkEquipmentPalettes
org $0ED745 : JSL FixShockPalette ; @hook module=Overworld name=FixShockPalette kind=jsl target=FixShockPalette

; GameOver_SaveAndQuit:
org $09F604 : JSL FixSaveAndQuit ; @hook module=Overworld name=FixSaveAndQuit kind=jsl target=FixSaveAndQuit

; Vanilla NMI_UploadGameOverText ($009038, triggered by $09F430 $17=#$16)
; DMAs TILEMAPA ($7E2000/$7E3400) over BG3 CHR $7800-$7BFF (sheet $69,
; tiles $100-$17F), corrupting the HUD X|Y wood divider ($214F) and custom
; item icons ($130-$17F: Gust Jar, Ball & Chain, Portal Rod) during Game Over.
; Game Over menu text lives in $180-$1FD ($7C00-$7FEF), uploaded cleanly by
; RenderText_PostDeathSaveOptions ($17=#$02, NMI_UploadBG3Text).
org $009038 ; @hook module=Overworld name=HUD_GameOverPreserveSheet69 kind=patch expected_m=8 expected_x=8
  assert read1($009038) == $C2 && read1($009039) == $20 && read1($00903A) == $A9 && read2($00903B) == $7800, "Expected NMI_UploadGameOverText at $009038"
  STZ.w $0710
  RTS
assert pc() == $00903C
