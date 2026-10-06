; =========================================================
; Part 0 storm (!ENABLE_PART0_STORM)
;
; One saved story bit drives the Part 0 weather: the rain overlay, the rain
; sound and the dimmed world map. scawful's ruling (2026-09-25): keep the
; rain; a sunny first morning is wrong for this opening.
;
;   Bit:   StoryProgress2 ($7EF3C6) bit 7, !Story2_Part0Storm (Core/sram.asm).
;   Set:   HouseTag_WakeUpPlayer (Dungeons/custom_tag.asm), new-game wake-up.
;   Clear: Part0Storm_EndIfBackOnKalyxo, when Link is back on Kalyxo after
;          the Abyss: storm bit set, Story2_KydrogEncounter set (Kydrog's
;          banishment, Sprites/Bosses/kydrog.asm) and saved world
;          $7EF3CA = $00 (light world): the first light world arrival
;          after the banishment, whatever the exit. Today that is the DW $6A
;          warp tile (mirror-warp path, MirrorWarp_Initialize $02B236 sets
;          $7EF3CA to $00); scawful's sword warp home (decisions.org) will
;          replace it and needs no change here as long as it sets $7EF3CA. Checked by every reader below, so any route
;          back (portal, continue in the light world) ends the storm. A
;          failed warp (mirror bonk) also ends it; no visible effect, since
;          the storm never shows in the Abyss.
;          Playtest 2026-09-26 (scawful): "rain dismisses when we meet
;          farore" - the storm now lasts through the Farore beat and the
;          Abyss and ends when Link is back on Kalyxo.
;
; The storm is Kalyxo weather: no rain overlay, rain sound or dim map in the
; Abyss (areas $40-$7F). Readers check the current area ($8A bit 6).
;
; Readers (all replace a "GameState < 2" check):
;   - Overworld_ReloadSubscreenOverlay, ActivateSubScreen
;     (Overworld/ZSCustomOverworld.asm): rain overlay $9F, SFX1 $01.
;   - AdjustOverworldAmbiance ($02C4B6): every light world area gets the rain
;     ambience nibble, so area transitions, map exit and bird travel
;     (LoadAmbientSound) keep playing rain. The music nibble is unchanged.
;   - WorldMap_FadeOut ($0ABA04): half-blended dark map ($99=$80, $9A=$61).
;     Map exit runs Overworld_ReloadSubscreenOverlay, which restores rain.
; Interiors stay silent: UnderworldAdjustRainSFX ($02838C) keeps the 09-14
; patch in Overworld/overworld.asm (scawful ruling 2026-09-25).
;
; Included from Overworld/overworld.asm (bank $34 free space) only when the
; flag is on.
; =========================================================

; ---------------------------------------------------------
; Carry clear while the storm is active here, set otherwise.
; Active = storm bit set and the current area is on Kalyxo ($8A bit 6 = 0).
; Ends the storm first if Link is back on Kalyxo after the Abyss.
; Replaces "LDA.l GameState : CMP.b #$02" in front of a vanilla BCS, so the
; storm takes the old "GameState < 2" path. Clobbers A (low byte).
; Keeps the caller's M/X and X. DB is not used.
Part0Storm_CarryClearIfStorm:
{
  PHP
  REP #$10
  PHX
  SEP #$20
  JSR Part0Storm_EndIfBackOnKalyxo
  LDA.b $8A : AND.b #$40 : BNE .no_storm
  LDA.l StoryProgress2 : AND.b #!Story2_Part0Storm : BEQ .no_storm
    PLX
    PLP
    CLC
    RTL
  .no_storm
  PLX
  PLP
  SEC
  RTL
}

; ---------------------------------------------------------
; AdjustOverworldAmbiance tail ($02C4B6, M=8 X=16).
; Replaced code: LDA.b $00 : STA.l $7F5B80.
; While the storm is active, SFX1 nibble of light world areas $00-$3F = $1
; (rain). X/Y are free here (vanilla reloads them after the call).
; On the portal home this runs in MirrorWarp_FinalizeAndLoadDestination
; ($02B297) before the destination's SFX1 is read from $7F5B00, so the storm
; is over (here at the latest) and Link arrives without rain.
Part0Storm_AdjustAmbience:
{
  PHP
  SEP #$20
  REP #$10
  LDA.b $00 : STA.l $7F5B80
  JSR Part0Storm_EndIfBackOnKalyxo
  LDA.l StoryProgress2 : AND.b #!Story2_Part0Storm : BEQ .done
    LDX.w #$003F
    .next_area
      LDA.l $7F5B00, X : AND.b #$0F : ORA.b #$10 : STA.l $7F5B00, X
    DEX : BPL .next_area
  .done
  PLP
  RTL
}

; ---------------------------------------------------------
; Back on Kalyxo after the Abyss: clear the storm bit and strip the rain
; nibble from the light world ambience table, so the next area transition
; does not restart the rain sound.
; Needs M=8, X=16. Clobbers A and X. Local (JSR) helper.
Part0Storm_EndIfBackOnKalyxo:
{
  LDA.l StoryProgress2 : AND.b #!Story2_Part0Storm : BEQ .done
  LDA.l StoryProgress2 : AND.b #!Story2_KydrogEncounter : BEQ .done
  LDA.l SavedWorld : BNE .done ; $40 while Link is in the Abyss
    LDA.l StoryProgress2 : AND.b #$FF^!Story2_Part0Storm : STA.l StoryProgress2
    LDX.w #$003F
    .next_area
      LDA.l $7F5B00, X : AND.b #$F0 : CMP.b #$10 : BNE .keep_area
        LDA.l $7F5B00, X : AND.b #$0F : STA.l $7F5B00, X
      .keep_area
    DEX : BPL .next_area
  .done
  RTS
}

pushpc

; AdjustOverworldAmbiance: LDA.b $00 : STA.l $7F5B80 (6 bytes).
org $02C4B6 ; @hook module=Overworld name=Part0Storm_AdjustAmbience kind=jsl target=Part0Storm_AdjustAmbience expected_m=8 expected_x=16
  JSL Part0Storm_AdjustAmbience : NOP #2
assert pc() == $02C4BC

; WorldMap_FadeOut: LDA.l $7EF3C5 : CMP.b #$02 (6 bytes), BCS at $0ABA0A kept.
org $0ABA04 ; @hook module=Overworld name=Part0Storm_MapTint kind=jsl target=Part0Storm_CarryClearIfStorm expected_m=8 expected_x=8
  JSL Part0Storm_CarryClearIfStorm : NOP #2
assert pc() == $0ABA0A

pullpc

print  "End of storm.asm                  ", pc
