; Special-overworld Soaring reuses the native Travel Bird pickup (AddTravelBird,
; Ancilla $27), the native Mode 7 Flute Map picker (Module $0E, Submodule $0A)
; over the Lyra Sea World Map with 8 spread-out numbered pins 1..8 across all
; four quadrants, and native Bird drop-off (FluteMenu_FadeInAndQuack ->
; SpawnLandingDuck -> AncillaAdd_Duck_drop_off) after Module $08 loads the
; destination's native $32-byte cached-exit record ($7EC140).
;
; Pins 1..8 ($1AF0 = 0..7):
;   0 (Pin 1): Korok Cove     ($81, NW)           - visited-unlock (bit 0 = $01)
;   1 (Pin 2): Royal Garrison ($83, North)        - baseline hub   (bit 1 = $02)
;   2 (Pin 3): Zora Quay      ($99, West Harbor)  - baseline hub   (bit 2 = $04)
;   3 (Pin 4): Goron Coast    ($B0, SW)           - baseline hub   (bit 3 = $08)
;   4 (Pin 5): Crescent Isle  ($B3, South-Center) - visited-unlock (bit 4 = $10)
;   5 (Pin 6): Courage Isle   ($A6, East)         - visited-unlock (bit 5 = $20)
;   6 (Pin 7): Frost Glacier  ($BE, SE)           - visited-unlock (bit 6 = $40)
;   7 (Pin 8): Sky Spire      ($8C, NE Clouds)    - SkySoaringLearned == $A5 ($80)
;
; Volatile WRAM:
;   $7EC13E: SpecialSoaring_LoadStep (1B in unused $7EC132-$7EC13F; 0=idle,
;            1..3=Module $08 submodule step+1 while $0200==7 loads destination).
;
; Placed in Bank $5F tail ($5FDB00+, after SpecialOverworld_QualityCodeEnd)
; so Bank $2B keeps generous headroom alongside Items/ocarina.asm.

!SpecialSoaring_Count    = 8
!SpecialSoaring_SkyIndex = 7
SpecialSoaring_LoadStep  = $7EC13E

pushpc
if !DISABLE_OVERWORLD == 0
assert SpecialOverworld_QualityCodeEnd <= $5FDB00, "SpecialOverworld_QualityCodeEnd overruns $5FDB00"
endif
org $5FDB00 ; @manifest-org-bank=$5F
SpecialSoaring_CodeStart:

; Called by song03 (Items/ocarina.asm) after indoor and Dark World checks, M8/X8.
; Spawns the native Travel Bird (Ancilla $27) so it swoops down, picks Link up,
; carries him off-screen, and transitions natively into Module $0E / Sub $0A
; (saving unified Module $09 in $010C).
SpecialSoaring_Open:
{
  LDA.b $8A : CMP.b #$80 : BCC .done
  CMP.b #$C0 : BCS .done
  ; Do not spawn a second Travel Bird if one is already active.
  LDX.b #$04
  .check_bird
    LDA.l $7E0C4A, X : CMP.b #$27 : BEQ .done
    DEX : BPL .check_bird
  ; Clear stale loader step & item-anim latch ($037A) so MaybeUploadBirdGraphicsToOam
  ; always streams Bird tiles cleanly.
  LDA.b #$00
  STA.l SpecialSoaring_LoadStep
  STA.l $7E037A
  ; If riding Epona, dismount silently before the Bird swoops in so Link's
  ; normal sprite bank ($10) and SP3 palette are clean for pickup.
if !ENABLE_HORSE_FORM == 1
  LDA.l $7E02B2 : CMP.b #$09 : BNE +
    JSL HorseForm_SilentDismount
  +
endif
  LDY.b #$04
  LDA.b #$27
  JSL AddTravelBird
  ; Guarantee the Travel Bird pickup animation spawns even when all 5 ancilla
  ; slots ($0C4A..$0C4E) are temporarily busy with transient FX (sparkles,
  ; splashes, grass debris): evict slot 4 and retry once if $27 did not spawn.
  LDX.b #$04
  .verify_bird
    LDA.l $7E0C4A, X : CMP.b #$27 : BEQ .bird_ready
    DEX : BPL .verify_bird
  LDA.b #$00 : STA.l $7E0C4E
  LDY.b #$04
  LDA.b #$27
  JSL AddTravelBird
  .bird_ready
  LDA.b #$00 : STA.l $7E03F8
  .done
  RTL
}

; Clears Travel Bird pickup locks and volatile soaring state when the player
; cancels (B/X) on the Mode 7 Lyra Sea Map or hits a defensive fallback.
; Safe from any M/X width or DBR; preserves X, Y, P.
SpecialSoaring_CancelCleanup:
{
  PHP : SEP #$30 : PHX
  ; Remove any stray Travel Bird ancilla so it cannot linger on return.
  LDX.b #$04
  .clear_bird
    LDA.l $7E0C4A, X : CMP.b #$27 : BNE .next_slot
      LDA.b #$00 : STA.l $7E0C4A, X
    .next_slot
    DEX : BPL .clear_bird
  ; If the Travel Bird grabbed Link before the 128-frame Ocarina timer ($03F0)
  ; finished (e.g. near the left screen edge), restore full BGM volume ($F3).
  LDA.l $7E03F0 : BEQ .no_bgm_restore
    LDA.l $7E012C : BNE .no_bgm_restore
      LDA.b #$F3 : STA.l $7E012C
  .no_bgm_restore
  LDA.b #$00
  STA.l SpecialSoaring_LoadStep
  STA.b $4B                             ; Link visible again
  STA.b $5D                             ; LinkState_Default
  STA.l $7E02DA                         ; clear bird-carry grab pose
  STA.l $7E02E4                         ; unlock movement & menu
  STA.l $7E037B                         ; clear bird invulnerability lock
  STA.l $7E02F9                         ; unhide follower / clear camera lock
  STA.l $7E0300
  STA.l $7E0301
  STA.l $7E037A
  STA.l $7E03F0                         ; clear Ocarina hold timer
  STA.l $7E0FC1                         ; unfreeze sprites/NPCs
  LDA.b $3A : AND.b #$BF : STA.b $3A    ; release Y-button lock
  PLX : PLP
  RTL
}

; Called via JSL from TravelPicker_LoadSelectedScreen ($0AB8C5) when $8A is in
; $80..$BF, after WorldMap_RestoreGraphics has completed FBlank and BGMODE=$09
; restoration ($0200 == 7). Reads pin index 0..7 from $1AF0 on frame 1, drives
; Module $08 ($0283BF) to load the destination's native $32-byte exit cache
; (preserving all Special OW resident graphics/palettes/overlays), then hands
; off to native FluteMenu_FadeInAndQuack ($0200 = 9) -> SpawnLandingDuck
; (AncillaAdd_Duck_drop_off) for a clean Travel Bird drop-off!
; Exit: C set = transport active/armed, C clear = rejected (cancel cleanup done).
SpecialSoaring_ExecuteTransport:
{
  PHP : SEP #$30
  LDA.l SpecialSoaring_LoadStep : BEQ .prepare
    JMP .run_module08

  .prepare
  LDA.w $1AF0
  STZ.w $1AF0
  CMP.b #!SpecialSoaring_Count : BCS .reject
  ; Verify selected pin bit against unlocked mask:
  ;   (SpecialTravelSpotsVisited & $7F) | $0E, plus $80 iff SkySoaringLearned == $A5.
  TAX
  LDA.l SpecialTravelSpotsVisited : AND.b #$7F : ORA.b #$0E
  PHA
  LDA.l SkySoaringLearned : CMP.b #!SKY_SOARING_LEARNED : BNE .mask_ready
    PLA : ORA.b #$80 : PHA
  .mask_ready
  PLA
  AND.l TravelDest_Bits, X : BNE .allowed
  .reject
    JSL SpecialSoaring_CancelCleanup
    PLP : CLC : RTL

  .allowed
  ; Save pin index (in X) while preparing cache & cleaning transient states.
  TXA : PHA
  ; Restore backed-up $7EC108..$7EC10B return cache before leaving map mode.
  JSL SpecialOverworld_RestoreMapPos
  STZ.w $0AA5
  STZ.w $0AA9
  STZ.w $0AB2
  ; Dismiss active ferry/horse/swimming state before landing on dry ground.
if !ENABLE_KALYXO_BOAT == 1
  JSL Boat_ResetSession
endif
if !ENABLE_HORSE_FORM == 1
  LDA.w $02B2 : CMP.b #$09 : BNE +
    JSL HorseForm_SilentDismount
  +
endif
  STZ.w $0345 : STZ.w $0351
  JSL Link_ResetSwimmingState
  PLA
  PHB
  REP #$30
  AND.w #$00FF : ASL : TAX
  LDA.l SpecialSoaring_CacheOffsets, X : TAX
  SEP #$20
  LDA.b #$7E : PHA : PLB
  REP #$20
  LDY.w #$0000
  .copy
  LDA.l SpecialSoaring_Caches, X : STA.w $C140, Y
  INX #2 : INY #2 : CPY.w #$0032 : BCC .copy
  ; The native cached-exit loader uses this full record, including camera,
  ; tilemap origin and fresh scroll modifiers. Reuse the existing synthetic
  ; cached-exit selector; it is not a room or an entrance allocation.
  STZ.w $0696 : STZ.w $0698
  LDA.w #!GoronCheckpoint_CacheRoom : STA.b $A0
  STZ.w $010A : STZ.w $04AA
  STZ.w $0FFF
  SEP #$30
  PLB
  LDA.b #$00 : STA.l SavedWorld
  STZ.w $03F0
  LDA.b $3A : AND.b #$BF : STA.b $3A
  STZ.w $0300 : STZ.w $0301 : STZ.w $037A
  STZ.w $031F : STZ.w $03EF : STZ.w $0132
  STZ.b $5D
  ; Keep Link hidden & locked for Bird drop-off during Module $08 load & fade-in.
  LDA.b #$0C : STA.b $4B
  LDA.b #$01 : STA.w $02DA : STA.w $02E4 : STA.w $037B : STA.w $02F9
  STZ.b $B0 : STZ.b $9B
  LDA.b #$80 : STA.b $13
  LDA.b #$01 : STA.l SpecialSoaring_LoadStep

  .run_module08
  ; Step native Module $08 ($0283BF) under FBlank until it signals $10 == #$10
  ; (properties, resident Special OW GFX/palettes, sprites, overlay, tilemap all loaded).
  LDA.l SpecialSoaring_LoadStep : DEC : STA.b $11
  LDA.b #$08 : STA.b $10
  PHB
  LDA.b #$00 : PHA : PLB
  JSL $0283BF
  PLB
  SEP #$30
  LDA.b $10 : CMP.b #$10 : BEQ .loaded
    LDA.b $11 : INC : STA.l SpecialSoaring_LoadStep
    LDA.b #$0E : STA.b $10
    LDA.b #$0A : STA.b $11
    PLP : SEC : RTL

  .loaded
  LDA.b #$00 : STA.l SpecialSoaring_LoadStep
  ; Refresh Link/mask tunic palette and queue CGRAM upload before fade-in.
  JSL Palette_ArmorAndGloves
  INC.b $15
  ; Play map-close swoosh, set destination ambient SFX, and switch/restore BGM
  ; (matches BirdTravel_LoadTargetArea_Interupt).
  LDA.b #$10 : STA.w $012F
  LDX.b $8A
  LDA.l !OverworldMusicCache, X : LSR #4 : BNE .has_amb
    LDA.b #$05
  .has_amb
  STA.w $012D
  LDA.l !OverworldMusicCache, X : AND.b #$0F : BEQ .same_song
    CMP.w $0130 : BEQ .same_song
      STA.w $012C
      BRA .music_done
  .same_song
  LDA.b #$F3 : STA.w $012C
  .music_done
  STZ.w $0132
  ; Guarantee SpawnLandingDuck ($0AB982 -> AncillaAdd_Duck_drop_off) always has
  ; a free slot and no stray $27, preventing any hidden/locked landing softlock.
  PHX
  LDX.b #$04
  .clear_landing_bird
    LDA.l $7E0C4A, X : CMP.b #$27 : BNE .next_landing_slot
      LDA.b #$00 : STA.l $7E0C4A, X
    .next_landing_slot
    DEX : BPL .clear_landing_bird
  LDA.b #$00 : STA.l $7E0C4E
  PLX
  ; Preserve Module $08's clean HDMA mask ($9B) for SpawnLandingDuck's restore.
  LDA.b $9B : STA.l $7EC229
  ; Ensure Bird-carry locks stay armed while FluteMenu_FadeInAndQuack brightens
  ; $13 (0 -> $0F) and triggers SpawnLandingDuck (AncillaAdd_Duck_drop_off).
  STZ.b $5D
  LDA.b #$0C : STA.b $4B
  LDA.b #$01 : STA.w $02DA : STA.w $02E4 : STA.w $037B : STA.w $02F9
  STZ.b $13
  STZ.b $B0
  LDA.b #$09 : STA.w $010C
  LDA.b #$0E : STA.b $10
  LDA.b #$0A : STA.b $11
  LDA.b #$09 : STA.w $0200              ; FluteMenu_FadeInAndQuack -> SpawnLandingDuck
  PLP : SEC
  RTL
}

; Special Overworld ($80-$BF) region membership -> SpecialTravelSpotsVisited ($7EF438) bits
; (stored in Bank $5F tail to keep Bank $2B headroom generous for travel_destinations.asm):
;   $01 (Pin 1): Korok Cove     ($81/$82/$89/$8A) - visited-unlock
;   $02 (Pin 2): Royal Garrison ($83/$8B)         - baseline hub
;   $04 (Pin 3): Zora Quay      ($90/$91/$98/$99/$A0/$A1) - baseline hub
;   $08 (Pin 4): Goron Coast    ($B0/$B1/$B8/$B9) - baseline hub
;   $10 (Pin 5): Crescent Isle  ($B3/$B4/$BB/$BC) - visited-unlock
;   $20 (Pin 6): Courage Isle   ($A6/$A7/$AE/$AF) - visited-unlock
;   $40 (Pin 7): Frost Glacier  ($BE/$BF)         - visited-unlock
;   ($80 Pin 8 = Sky $8C is strictly gated on SkySoaringLearned == $A5, never set here.)
SpecialTravelDest_Areas:
  db $81, $82, $89, $8A
  db $83, $8B
  db $90, $91, $98, $99, $A0, $A1
  db $B0, $B1, $B8, $B9
  db $B3, $B4, $BB, $BC
  db $A6, $A7, $AE, $AF
  db $BE, $BF
SpecialTravelDest_AreasEnd:
SpecialTravelDest_Masks:
  db $01, $01, $01, $01
  db $02, $02
  db $04, $04, $04, $04, $04, $04
  db $08, $08, $08, $08
  db $10, $10, $10, $10
  db $20, $20, $20, $20
  db $40, $40
assert (SpecialTravelDest_AreasEnd-SpecialTravelDest_Areas) == (pc()-SpecialTravelDest_Masks)

; Lyra Sea Mode 7 World Map pin coordinates (1:16 world scale -> x128..383, y128..383;
; full 4-quadrant spread, >= 69.5 map-px pairwise separation across all 8 pins,
; all 8 cleanly inside the Mode 7 viewport with zero bottom-border overhang):
;   0 (Pin 1): Korok Cove     ($81, NW)      -> X=$02B0, Y=$01C0
;   1 (Pin 2): Royal Garrison ($83, North)   -> X=$0700, Y=$0140
;   2 (Pin 3): Zora Quay      ($99, West)    -> X=$0290, Y=$0710
;   3 (Pin 4): Goron Coast    ($B0, SW)      -> X=$01F0, Y=$0C80
;   4 (Pin 5): Crescent Isle  ($B3, South)   -> X=$06A0, Y=$0DA0
;   5 (Pin 6): Courage Isle   ($A6, East)    -> X=$0E20, Y=$0A20
;   6 (Pin 7): Frost Glacier  ($BE, SE)      -> X=$0DD0, Y=$0E80
;   7 (Pin 8): Sky Spire      ($8C, NE Sky)  -> X=$0B80, Y=$02B0
SpecialSoaring_PinXLo:
  db $B0, $00, $90, $F0, $A0, $20, $D0, $80
SpecialSoaring_PinXHi:
  db $02, $07, $02, $01, $06, $0E, $0D, $0B
SpecialSoaring_PinYLo:
  db $C0, $40, $10, $80, $A0, $20, $80, $B0
SpecialSoaring_PinYHi:
  db $01, $01, $07, $0C, $0D, $0A, $0E, $02

SpecialSoaring_CacheOffsets:
  dw $0000, $0032, $0064, $0096, $00C8, $00FA, $012C, $015E

SpecialSoaring_Caches:
  ; Native $32-byte exit records consumed by LoadCachedEntranceProperties ($02E5D4).
  ; All 8 landing pads verified against live ROM Tile16 + collision + priority (low-pri walkable,
  ; wx - sx == $0078 exact center for smooth Travel Bird drop-off touchdown at Z=0):
  ; 0 (Pin 1): Korok Cove ($81, 64x64 Large): origin ($0200,$0000), cache (20,16) -> foot (20,17) 5x5 open grass 48.
  dw $0081,$0016,$00B0,$02C8,$0100,$0340,$0081,$0598
  dw $011F,$0347,$0000,$031E,$0200,$0500,$FF20,$0400,$0100,$0600
  dw $2000,$0E02,$0000,$0000,$0000,$0000,$0000
  ; 1 (Pin 2): Royal Garrison ($83, 32x64 Tall): origin ($0600,$0000), cache (16,20) -> foot (16,21) 5x5 courtyard 00.
  dw $0083,$0016,$00F0,$0688,$0140,$0700,$0083,$0790
  dw $015F,$0707,$0000,$031E,$0600,$0700,$FF20,$0400,$0500,$0800
  dw $2000,$0E24,$0000,$0000,$0000,$0000,$0000
  ; 2 (Pin 3): Zora Quay ($99, 32x32 Small): origin ($0200,$0600), cache (9,17) -> foot (9,18) 5x5 harbor beach 00.
  dw $0099,$0016,$06C0,$0218,$0710,$0290,$0099,$0602
  dw $072F,$0297,$0600,$071E,$0200,$0300,$0520,$0800,$0100,$0400
  dw $2000,$2F0B,$0000,$0000,$0000,$0000,$0000
  ; 3 (Pin 4): Goron Coast ($B0, 64x64 Large): origin ($0000,$0C00), cache (31,8) -> foot (31,9) 7x6 flat plateau 00.
  dw $00B0,$0016,$0C30,$0178,$0C80,$01F0,$00B0,$01AE
  dw $0C9F,$01F7,$0C00,$0F1E,$0000,$0300,$0B20,$1000,$FF00,$0400
  dw $2000,$1B30,$0000,$0000,$0000,$0000,$0000
  ; 4 (Pin 5): Crescent Island ($B3, 64x64 Large): origin ($0600,$0C00), cache (29,43) -> foot (29,44) 5x5 open grass 48.
  dw $00B3,$0016,$0E60,$0758,$0EB0,$07D0,$00B3,$132A
  dw $0ECF,$07D7,$0C00,$0F1E,$0600,$0900,$0B20,$1000,$0500,$0A00
  dw $2000,$1B30,$0000,$0000,$0000,$0000,$0000
  ; 5 (Pin 6): Courage Island ($A6, 64x64 Large): origin ($0C00,$0800), cache (34,34) -> foot (34,35) 3x3 open grass 00.
  dw $00A6,$0016,$09D0,$0DA8,$0A20,$0E20,$00A6,$0EB4
  dw $0A3F,$0E27,$0800,$0B1E,$0C00,$0F00,$0720,$0C00,$0B00,$1000
  dw $2000,$1B30,$0000,$0000,$0000,$0000,$0000
  ; 6 (Pin 7): Frost Glacier ($BE, 64x32 Wide): origin ($0C00,$0E00), cache (31,21) -> foot (31,22) 5x5 snow plaza 00.
  dw $00BE,$0016,$0F00,$0D78,$0F50,$0DF0,$00BE,$082E
  dw $0F6F,$0DF7,$0E00,$0F1E,$0C00,$0F00,$0D20,$1000,$0B00,$1000
  dw $2000,$1B30,$0000,$0000,$0000,$0000,$0000
  ; 7 (Pin 8): Sky Spire ($8C, 32x32 Small): origin ($0800,$0200), cache (14,11) -> foot (14,12) 3x3 grass 40; Sky gated.
  dw $008C,$0016,$0260,$0868,$02B0,$08E0,$008C,$030C
  dw $02CF,$08E7,$0200,$031E,$0800,$0900,$0120,$0400,$0700,$0A00
  dw $2000,$1002,$0000,$0000,$0000,$0000,$0000
assert pc()-SpecialSoaring_Caches == $0190
SpecialSoaring_CodeEnd:
print "Bank5F Soaring Code End:          ", pc, " (", dec($5FFFFF-pc()), " B free)"
assert pc() <= $5FFFFF, "Special Overworld soaring code exceeds bank $5F"
pullpc

; The selected teaching action uses the native message lifecycle. No hooks or
; code are emitted until its approved message is explicitly bound in source.
incsrc "Items/sky_watch_log.asm"
