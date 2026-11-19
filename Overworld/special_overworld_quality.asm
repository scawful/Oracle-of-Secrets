; =========================================================
; Special Overworld Quality, Music, Sprite-Palette Safety &
; Abyss Return Vortex ($6C) Hooks (Bank $5F tail after Transitions)
;
; Implements QUEUE329 + A4:
;   1. SpecialOverworld_InitMusicTail ($02C4BC): fills !OverworldMusicCache
;      [$A0-$BF] from the rev5 phase tables and supplies biome-matched default
;      music ($5C Great Sea, $55 Lost Woods, $5D Mountain, $56 Frozen Hyrule)
;      whenever a tail map's ROM byte has low nibble $00 (unauthored silence),
;      preserving any non-zero authored music byte.
;   2. SafeOverworldSpritePalIndex ($0ED5C9): clamps out-of-bounds sprite_pal
;      IDs >= $14 (the $0ED580 table has 20 entries $00-$13; legacy $02E701
;      rows $90-$9E contain uninitialized bytes $C2/$9C/$AC/$AD/$C1/$7E/$A5/$8F)
;      to $01 instead of reading Bank $0E opcodes into $0AAD/$0AAE.
;   3. SpecialOverworld_ReadSpriteGfxByArea / ReadSpecialSpriteGfx: clamps
;      out-of-bounds sprite_gfx IDs >= $90 (SpriteBlockset at $00DB57 has 144
;      entries $00-$8F, including custom $8E LyraTempleZora/sheet $E7 and $8F
;      D4 Warden/sheets $DF-$E2) to $01 instead of reading past table bounds.
;   4. A4 Abyss Return Vortex ($6C): allows Kalyxo -> Eon Abyss warp pads to
;      spawn a clickable $6C return vortex in Eon Abyss while suppressing it
;      on the intro Pyramid drop, on Special Overworld ($80-$BF), and without
;      spawning a duplicate vortex on Kalyxo when returning through $6C.
; =========================================================

pushpc
assert SpecialOverworld_TransitionsCodeEnd <= $5FD900, "SpecialOverworld_TransitionsCodeEnd overruns $5FD900"
org $5FD900 ; @manifest-org-bank=$5F
SpecialOverworld_QualityCodeStart:

if !SPECIAL_OVERWORLD_NATIVE == 1

; Replaces JML Lyra_InitMusicTail at $02C4BC (M=8, X=16, saved DBR at 1,S).
; Copies !LYRA_CURRENT_TABLE_music_phase{0..3}[$A0..$BF] into !OverworldMusicCache
; and substitutes a biome-matched default whenever the low music nibble is $00.
SpecialOverworld_InitMusicTail:
{
  PHP : REP #$30 : PHA : PHX : PHY
  SEP #$30
  JSL Oracle_CheckIfNight
  CMP.b #$01 : BEQ .phase1
  CMP.b #$02 : BEQ .phase2
  CMP.b #$03 : BCS .phase3

  REP #$10 : LDX.w #!LYRA_CURRENT_FIRST
.phase0Loop:
  LDA.l !LYRA_CURRENT_TABLE_music_phase0, X
  JSR .fallback_if_silent
  STA.l !OverworldMusicCache, X
  INX : CPX.w #!LYRA_CURRENT_END : BCC .phase0Loop
  BRA .done

.phase1:
  REP #$10 : LDX.w #!LYRA_CURRENT_FIRST
.phase1Loop:
  LDA.l !LYRA_CURRENT_TABLE_music_phase1, X
  JSR .fallback_if_silent
  STA.l !OverworldMusicCache, X
  INX : CPX.w #!LYRA_CURRENT_END : BCC .phase1Loop
  BRA .done

.phase2:
  REP #$10 : LDX.w #!LYRA_CURRENT_FIRST
.phase2Loop:
  LDA.l !LYRA_CURRENT_TABLE_music_phase2, X
  JSR .fallback_if_silent
  STA.l !OverworldMusicCache, X
  INX : CPX.w #!LYRA_CURRENT_END : BCC .phase2Loop
  BRA .done

.phase3:
  REP #$10 : LDX.w #!LYRA_CURRENT_FIRST
.phase3Loop:
  LDA.l !LYRA_CURRENT_TABLE_music_phase3, X
  JSR .fallback_if_silent
  STA.l !OverworldMusicCache, X
  INX : CPX.w #!LYRA_CURRENT_END : BCC .phase3Loop

.done:
  REP #$30 : PLY : PLX : PLA : PLP
  SEP #$10 : PLB : RTL

; M=8, X=16 (X in $00A0..$00BF). Returns non-silent music/ambience byte in A.
.fallback_if_silent:
  PHA
  AND.b #$0F : BNE .keep_rom
    PLA
    LDA.l .TailMusicDefaults-$A0, X
    RTS
  .keep_rom:
  PLA
  RTS

; Biome-matched default music bytes for tail maps $A0-$BF (high nibble $5 = silent ambience):
;   $5C -> Great Sea ($10 via NMI_GreatSeaSongRemap)
;   $55 -> Lost Woods v2 ($05, Deku Coast $A8-$A9)
;   $5D -> Mountain / Goron ($0D, Goron Desert $B0-$B1/$B8-$B9)
;   $56 -> Frozen Hyrule ($11 via NMI_GreatSeaSongRemap, Snow Island $BE-$BF)
.TailMusicDefaults:
  db $5C, $5C, $5C, $5C, $5C, $5C, $5C, $5C ; $A0-$A7: Zora Coast, Lyra Sea, Courage N
  db $55, $55, $5C, $5C, $5C, $5C, $5C, $5C ; $A8-$AF: Deku ($A8-$A9), Lyra Sea, Courage S
  db $5D, $5D, $5C, $5C, $5C, $5C, $5C, $5C ; $B0-$B7: Goron N ($B0-$B1), Crescent/Tower N
  db $5D, $5D, $5C, $5C, $5C, $5C, $56, $56 ; $B8-$BF: Goron S ($B8-$B9), Harbor/Tower S, Snow ($BE-$BF)
}
assert (.TailMusicDefaults&$FFFF) >= $80A0, "TailMusicDefaults-$A0 crosses bank boundary"

; Bounds-guard overworld sprite_gfx against SpriteBlockset ($00DB57, 144 entries $00-$8F).
; Preserves intentional custom spritesets $8E (LyraTempleZora, sheet $E7) and $8F (D4 Warden,
; sheets $DF-$E2) while clamping any uninitialized >= $90 byte to $01.
; Entry/Exit: M=8, X=8, A = clamped spriteset ID (N/Z from A), X/Y/DB preserved.
SpecialOverworld_ReadSpriteGfxByArea:
{
  JSL Lyra_ReadSpriteGfxByArea
  CMP.b #$90 : BCC .done
    LDA.b #$01
  .done:
  RTL
}

SpecialOverworld_ReadSpecialSpriteGfx:
{
  JSL Lyra_ReadSpecialSpriteGfx
  CMP.b #$90 : BCC .done
    LDA.b #$01
  .done:
  RTL
}

endif ; !SPECIAL_OVERWORLD_NATIVE == 1

; ---------------------------------------------------------
; Safe Overworld Sprite Palette Lookup ($0ED5C9)
; ---------------------------------------------------------
; Replaces LDA.b $00 : ASL : TAX (4 bytes) in OverworldPalettesLoader ($0ED5A8).
; The $0ED580 table contains only 20 entries ($00-$13); clamp out-of-bounds
; values (such as legacy $02E701 $90-$9E garbage) to $01 (standard outdoor).
; Entry/Exit: M=8, X=8, DBR/Y preserved; A and X set to clamped index * 2.
SafeOverworldSpritePalIndex:
{
  LDA.b $00
  CMP.b #$14 : BCC .valid
    LDA.b #$01
  .valid:
  ASL : TAX
  RTL
}

; ---------------------------------------------------------
; A4: Abyss Return Vortex ($6C) Bidirectional Lifecycle
; ---------------------------------------------------------

; Hook at $07A97E (Mirror_TryToWarp, M=8, X=8, DB=$07).
; Replaces 28 bytes ($07A97E..$07A999).
; Saves Link's coordinates into $1ABF/$1ACF/$1ADF/$1AEF for BOTH:
;   - Kalyxo ($00-$3F) warp pad -> Eon Abyss ($40-$7F): arms VortexWorld = $40
;   - Eon Abyss ($40-$7F) Mirror -> Kalyxo ($00-$3F):   arms VortexWorld = $01
; Suppresses vortex on Special Overworld ($80-$BF): sets VortexWorld = $00.
AbyssVortex_CaptureOrigin:
{
  LDA.b $8A : AND.b #$40 : STA.b $7B
  LDA.b $8A : CMP.b #$80 : BCS .no_vortex
    LDA.b $20 : STA.l $7E1ADF
    LDA.b $21 : STA.l $7E1AEF
    LDA.b $22 : STA.l $7E1ABF
    LDA.b $23 : STA.l $7E1ACF
    LDA.b $7B : BNE .to_lw
      LDA.b #$40 : STA.l SpecialOverworld_VortexWorld
      RTL
    .to_lw:
    LDA.b #$01 : STA.l SpecialOverworld_VortexWorld
    RTL
  .no_vortex:
  LDA.b #$00 : STA.l SpecialOverworld_VortexWorld
  RTL
}

; Called from PreOverworld_LoadProperties_Interupt (ZSCustomOverworld.asm:1908)
; and Overworld_FinishMirrorWarp (ZSCustomOverworld.asm:2716). M=8, X=8.
;   - Special Overworld ($80-$BF): never spawn $6C.
;   - Eon Abyss ($40-$7F): spawn $6C ONLY when VortexWorld == $40 (warp-pad arrival).
;     Intro Pyramid drop has VortexWorld == $00, so it remains suppressed.
;   - Kalyxo ($00-$3F): spawn $6C ONLY when VortexWorld == $01 (DW->LW Mirror arrival).
;     After consuming a DW $6C back to Kalyxo, VortexWorld == $00 so no duplicate or
;     ghost $6C spawns on arrival or subsequent house exits.
SpecialOverworld_ReinitWarpVortex:
{
  LDA.b $8A
  CMP.b #$80 : BCS .skip
  CMP.b #$40 : BCC .light_world
    LDA.l SpecialOverworld_VortexWorld
    CMP.b #$40 : BNE .skip
    BRA .spawn
  .light_world:
  LDA.l SpecialOverworld_VortexWorld
  CMP.b #$01 : BNE .skip
  .spawn:
  JSL.l $09AF89 ; Sprite_ReinitWarpVortex
  .skip:
  RTL
}

; Hook at $05AF75 (Sprite_6C_MirrorPortal world guard, M=8, X=8, DB=$05).
; Replaces LDA.l $7EF3CA (4B) before BNE $05AFDF (despawn).
; Returns A=$00 (Z=1 = keep alive) in Light World ($7EF3CA == 0), OR in
; Eon Abyss ($7EF3CA == $40) while VortexWorld == $40 and $8A < $80.
; Otherwise returns A=$01 (Z=0 -> BNE $05AFDF despawns $6C).
AbyssVortex_Sprite6CWorldCheck:
{
  LDA.l SavedWorld : BEQ .alive
    LDA.b $8A : CMP.b #$80 : BCS .despawn
    LDA.l SpecialOverworld_VortexWorld
    CMP.b #$40 : BEQ .alive
  .despawn:
  LDA.b #$01
  RTL
  .alive:
  LDA.b #$00
  RTL
}

; Hook at $05AFD9 (Sprite_6C_MirrorPortal trigger warp, M=8, X=8, DB=$05).
; Replaces LDA.b $8A : AND.b #$40 : STA.b $7B (6 bytes).
; Consumes VortexWorld -> $00 so returning through $6C in either direction
; never spawns a duplicate vortex on the destination side.
AbyssVortex_ConsumeOnEnter:
{
  LDA.b $8A : AND.b #$40 : STA.b $7B
  LDA.b #$00 : STA.l SpecialOverworld_VortexWorld
  RTL
}

SpecialOverworld_QualityCodeEnd:
print "Bank5F Quality Code End:          ", pc, " (", dec($5FFFFF-pc()), " B free)"
assert pc() <= $5FFFFF, "Special Overworld quality code exceeds bank $5F"

; ---------------------------------------------------------
; Fixed Bank $05 / Bank $07 / Bank $0E Hooks
; ---------------------------------------------------------

; Clamp out-of-bounds sprite_pal >= $14 in OverworldPalettesLoader
assert read4($0ED5C9) == $AA0A00A5, "OverworldPalettesLoader sprite_pal index moved"
org $0ED5C9 ; @hook module=Overworld name=SafeOverworldSpritePalIndex kind=jsl target=Oracle_SafeOverworldSpritePalIndex expected_m=8 expected_x=8 protected_size=4
  JSL SafeOverworldSpritePalIndex
assert pc() == $0ED5CD

; Capture warp origin coordinates & world for both LW->DW warp pads and DW->LW Mirror
assert read4($07A97E) == $40298AA5 && read4($07A982) == $14F07B85, "Mirror_TryToWarp coord capture moved"
org $07A97E ; @hook module=Overworld name=AbyssVortex_CaptureOrigin kind=jsl target=Oracle_AbyssVortex_CaptureOrigin expected_m=8 expected_x=8 protected_size=28
  JSL AbyssVortex_CaptureOrigin
  BRA .abyss_vortex_capture_done
  NOP #22
.abyss_vortex_capture_done:
assert pc() == $07A99A

; Allow Sprite $6C to stay alive in Eon Abyss when armed by a LW->DW warp pad
assert read4($05AF75) == $7EF3CAAF && read2($05AF79) == $64D0, "Sprite_6C world guard moved"
org $05AF75 ; @hook module=Overworld name=AbyssVortex_Sprite6CWorldCheck kind=jsl target=Oracle_AbyssVortex_Sprite6CWorldCheck expected_m=8 expected_x=8 protected_size=4
  JSL AbyssVortex_Sprite6CWorldCheck
assert pc() == $05AF79

; Consume VortexWorld when Link steps into Sprite $6C
assert read4($05AFD9) == $40298AA5 && read2($05AFDD) == $7B85, "Sprite_6C enter warp world capture moved"
org $05AFD9 ; @hook module=Overworld name=AbyssVortex_ConsumeOnEnter kind=jsl target=Oracle_AbyssVortex_ConsumeOnEnter expected_m=8 expected_x=8 protected_size=6
  JSL AbyssVortex_ConsumeOnEnter
  NOP #2
assert pc() == $05AFDF

pullpc
