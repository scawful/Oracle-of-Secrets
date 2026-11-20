; 3-World Soaring (Kalyxo LW $00-$3F, Eon Abyss DW $40-$7F, Lyra Sea SW $80-$BF)
; reuses the native Travel Bird pickup (AddTravelBird, Ancilla $27), the native
; Mode 7 Flute Map picker (Module $0E, Submodule $0A) with cross-world L/R/SELECT
; flipping between Lyra Sea and Kalyxo, and native Bird drop-off after Module $08
; loads the destination's native $32-byte cached-exit record ($7EC140).
;
; Lyra Sea Pins 1..8 ($1AF0 = 0..7):
;   0 (Pin 1): Korok Cove     ($81, NW)           - visited-unlock (bit 0 = $01)
;   1 (Pin 2): Royal Garrison ($83, North)        - baseline hub   (bit 1 = $02)
;   2 (Pin 3): Zora Quay      ($99, West Harbor)  - baseline hub   (bit 2 = $04)
;   3 (Pin 4): Goron Coast    ($B0, SW)           - baseline hub   (bit 3 = $08)
;   4 (Pin 5): Crescent Isle  ($B3, South-Center) - visited-unlock (bit 4 = $10)
;   5 (Pin 6): Courage Isle   ($A6, East)         - visited-unlock (bit 5 = $20)
;   6 (Pin 7): Frost Glacier  ($BE, SE)           - visited-unlock (bit 6 = $40)
;   7 (Pin 8): Sky Spire      ($8C, NE Clouds)    - SkySoaringLearned == $A5 ($80)
;
; Eon Abyss Pins 1..8 ($1AF0 = 0..7):
;   0 (Pin 1): Temporal Pyramid ($40, NW)         - baseline hub   (bit 0 = $01)
;   1 (Pin 2): Abyss Windmill   ($63, Center)     - baseline hub   (bit 1 = $02)
;   2 (Pin 3): Fortress Secrets ($4B, North)      - visited-unlock (bit 2 = $04)
;   3 (Pin 4): Twin Brothers    ($56, NE)         - visited-unlock (bit 3 = $08)
;   4 (Pin 5): Shrine Courage   ($50, West)       - visited-unlock (bit 4 = $10)
;   5 (Pin 6): Lupo Temple      ($5E, East)       - visited-unlock (bit 5 = $20)
;   6 (Pin 7): Forest of Dreams ($58, SW)         - visited-unlock (bit 6 = $40)
;   7 (Pin 8): Abyss Beach      ($76, SE)         - visited-unlock (bit 7 = $80)
;
; Volatile WRAM:
;   $7EC13B..$7EC13D: Soaring_MapSwitchPending, Soaring_OriginWorld, Soaring_ViewWorld
;   $7EC13E:          SpecialSoaring_LoadStep (0=idle, 1..3=Module $08 submodule+1)
;
; Placed in Bank $5F tail ($5FDB00+, after SpecialOverworld_QualityCodeEnd)
; so Bank $2B keeps generous headroom alongside Items/ocarina.asm.

!SpecialSoaring_Count        = 8
!SpecialSoaring_SkyIndex     = 7
!AbyssSoaring_Count          = 8
!AbyssSoaring_BaselineMask   = $03        ; Pins 1 & 2 ($40 Pyramid, $63 Windmill)
SpecialSoaring_LoadStep      = $7EC13E

pushpc
if !DISABLE_OVERWORLD == 0
assert SpecialOverworld_QualityCodeEnd <= $5FDB00, "SpecialOverworld_QualityCodeEnd overruns $5FDB00"
endif
org $5FDB00 ; @manifest-org-bank=$5F
SpecialSoaring_CodeStart:

; Called by song03 (Items/ocarina.asm) when $8A is in $80..$BF, M8/X8.
SpecialSoaring_Open:
{
  LDA.b $8A : CMP.b #$80 : BCC .reject
  CMP.b #$C0 : BCS .reject
  BRA Soaring_SpawnBirdCommon
  .reject
  RTL
}

; Called by song03 (Items/ocarina.asm) when $8A is in $40..$7F, M8/X8.
; Spawns Ancilla $27 (which renders as the GBC Flying Rooster via NMI/Bank08 hooks).
AbyssSoaring_Open:
{
  LDA.b $8A : CMP.b #$40 : BCC .reject
  CMP.b #$80 : BCS .reject
  BRA Soaring_SpawnBirdCommon
  .reject
  RTL
}

Soaring_SpawnBirdCommon:
{
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
  ; normal sprite bank and SP3 palette are clean for pickup.
if !ENABLE_HORSE_FORM == 1
  LDA.l $7E02B2 : CMP.b #$09 : BNE +
    JSL HorseForm_SilentDismount
  +
endif
  LDY.b #$04
  LDA.b #$27
  JSL AddTravelBird
  ; Guarantee the Travel Bird pickup animation spawns even when all 5 ancilla
  ; slots ($0C4A..$0C4E) are busy with transient FX: evict slot 4 and retry once.
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
; cancels (B/X) on the Mode 7 World Map or hits a defensive fallback.
; Safe from any M/X width or DBR; preserves X, Y, P.
SpecialSoaring_CancelCleanup:
{
  PHP : SEP #$30 : PHX
  JSR Soaring_ClearBirdAncillas
  ; If the Travel Bird grabbed Link before the 128-frame Ocarina timer ($03F0)
  ; finished (e.g. near the left screen edge), restore full BGM volume ($F3).
  LDA.l $7E03F0 : BEQ .no_bgm_restore
    LDA.l $7E012C : BNE .no_bgm_restore
      LDA.b #$F3 : STA.l $7E012C
  .no_bgm_restore
  LDA.b #$00
  STA.l SpecialSoaring_LoadStep
  STA.l Soaring_MapSwitchPending
  STA.l Soaring_OriginWorld
  STA.l Soaring_ViewWorld
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

; Clears any active Travel Bird ($27) ancilla slots in $0C4A..$0C4E. M8/X8.
Soaring_ClearBirdAncillas:
{
  LDX.b #$04
  .loop
    LDA.l $7E0C4A, X : CMP.b #$27 : BNE .next
      LDA.b #$00 : STA.l $7E0C4A, X
    .next
    DEX : BPL .loop
  RTS
}

; Dismisses boat/horse/swim state and invalidates ZSCO GFX & overlay caches before
; switching worlds or loading cached destination screens. M8/X8, clobbers A/X.
Soaring_ScrubWorldTransitionState:
{
  JSL SpecialOverworld_RestoreMapPos
  STZ.w $0AA5
  STZ.w $0AA9
  STZ.w $0AB2
  JSL Boat_ResetSession
if !ENABLE_HORSE_FORM == 1
  LDA.w $02B2 : CMP.b #$09 : BNE +
    JSL HorseForm_SilentDismount
  +
endif
  STZ.w $0345 : STZ.w $0351
  JSL Link_ResetSwimmingState
  ; Invalidate ZSCO GFX caches so cross-world flights always reload sheets/tiles.
  LDX.b #$07
  LDA.b #$FE
  .inv_prior
    STA.w TransGFXModule_PriorSheets, X
    DEX : BPL .inv_prior
  LDX.b #$03
  LDA.b #$FF
  .inv_lastbg
    STA.l LASTBGSET0, X
    DEX : BPL .inv_lastbg
  LDA.b #$00 : STA.w AnimatedTileGFXSet
if !SPECIAL_OVERWORLD_PALETTE_ENABLED == 1
  JSL Oracle_SpecialOverworldPaletteReset
endif
  LDA.b #$FF : STA.b $8C                ; clear weather/dark overlay
  STZ.b $1D
  STZ.b $9A
  LDA.b #$20 : STA.b $9C
  LDA.b #$40 : STA.b $9D
  LDA.b #$80 : STA.b $9E
  STZ.b $1B
  STZ.b $B0
  RTS
}

; Called via JSL from TravelPicker_LoadSelectedScreen when Soaring_ViewWorld == 0
; and Soaring_OriginWorld == 2 (Lyra Sea SW -> Kalyxo LW). Scrubs Special OW /
; Sky / water / palette caches before vanilla FluteMenu_LoadSelectedScreen ($0AB8C9).
SpecialSoaring_PrepareReturnToKalyxo:
{
  PHP : SEP #$30 : PHX
  JSR Soaring_ScrubWorldTransitionState
  JSR Soaring_ClearBirdAncillas
  STZ.w $0C4E
  LDA.b #$00
  STA.l SavedWorld
  STA.l $7E0FFF
  STA.l SpecialSoaring_LoadStep
  STA.l Soaring_MapSwitchPending
  STA.l Soaring_OriginWorld
  STA.l Soaring_ViewWorld
  LDA.b #$09 : STA.w $010C
  PLX : PLP
  RTL
}

; Returns C set if cross-world L/R/SELECT flip is permitted in the active session
; (OriginWorld == 2 OR (OriginWorld == 0 && (SpecialTravelSpotsVisited || SkySoaringLearned==$A5))).
; Preserves X, Y; M8/X8, clobbers A.
Soaring_CanFlipWorld:
{
  LDA.l Soaring_OriginWorld : CMP.b #$02 : BEQ .yes
  CMP.b #$00 : BNE .no
    LDA.l SpecialTravelSpotsVisited : BNE .yes
    LDA.l SkySoaringLearned : CMP.b #!SKY_SOARING_LEARNED : BEQ .yes
  .no
  CLC : RTL
  .yes
  SEC : RTL
}

; Draws a crisp "<- [Bird] ->" toggle indicator badge in unused OAM slots 18..20
; at top-right of the Mode 7 Flute Map whenever cross-world flipping is permitted.
; Entry: M=8, X=8, DBR=$0A. Exit: M=8, X=8, DBR preserved.
SpecialSoaring_DrawWorldToggleBadge:
{
  JSL Soaring_CanFlipWorld : BCC .done
  ; Slot 18 ($0848, $0A32): left arrow (tile $3D, H-flip prop $72, 8x8)
  LDA.b #$D6 : STA.w $0848
  LDA.b #$0C : STA.w $0849
  LDA.b #$3D : STA.w $084A
  LDA.b #$72 : STA.w $084B
  STZ.w $0A32
  ; Slot 19 ($084C, $0A33): Bird icon (tile $0E, prop $32, 16x16), subtle 1px bob
  LDA.b #$DE : STA.w $084C
  LDA.b $1A : LSR #4 : AND.b #$01 : CLC : ADC.b #$08 : STA.w $084D
  LDA.b #$0E : STA.w $084E
  LDA.b #$32 : STA.w $084F
  LDA.b #$02 : STA.w $0A33
  ; Slot 20 ($0850, $0A34): right arrow (tile $3D, prop $32, 8x8)
  LDA.b #$EE : STA.w $0850
  LDA.b #$0C : STA.w $0851
  LDA.b #$3D : STA.w $0852
  LDA.b #$32 : STA.w $0853
  STZ.w $0A34
  .done
  RTL
}

; Called via JSL from TravelPicker_LoadSelectedScreen for Special Overworld ($80..$BF).
SpecialSoaring_ExecuteTransport:
{
  PHP : SEP #$30
  LDA.b #$02
  BRA Soaring_ExecuteTransportCommon
}

; Called via JSL from TravelPicker_LoadSelectedScreen for Eon Abyss ($40..$7F).
AbyssSoaring_ExecuteTransport:
{
  PHP : SEP #$30
  LDA.b #$01
  BRA Soaring_ExecuteTransportCommon
}

; Shared Module $08 cached-exit transporter for Special OW (A=2) and Eon Abyss (A=1).
; Entered with PHP : SEP #$30 already on stack. Exit: C set = active/armed, C clear = rejected.
Soaring_ExecuteTransportCommon:
{
  PHA                                   ; push target world (1 = DW, 2 = SW)
  LDA.l SpecialSoaring_LoadStep : BEQ .prepare
    PLA
    JMP .run_module08

  .prepare
  LDA.w $1AF0
  STZ.w $1AF0
  CMP.b #!SpecialSoaring_Count : BCS .reject
  TAX
  LDA.b $01, S : CMP.b #$01 : BEQ .abyss_mask
    LDA.l SpecialTravelSpotsVisited : AND.b #$7F : ORA.b #$0E
    PHA
    LDA.l SkySoaringLearned : CMP.b #!SKY_SOARING_LEARNED : BNE .sw_mask_ready
      PLA : ORA.b #$80 : PHA
    .sw_mask_ready
    PLA
    BRA .check_bit
  .abyss_mask
    LDA.l AbyssTravelSpotsVisited : ORA.b #!AbyssSoaring_BaselineMask
  .check_bit
  AND.l TravelDest_Bits, X : BNE .allowed
  .reject
    PLA
    JSL SpecialSoaring_CancelCleanup
    PLP : CLC : RTL

  .allowed
  TXA : PHA                             ; stack: [target_world, pin_idx]
  JSR Soaring_ScrubWorldTransitionState
  PLA : TAX                             ; X = pin_idx; stack: [target_world]
  LDA.b $01, S                          ; A = target_world (1 or 2)
  PHA : PHX                             ; stack: [target_world, target_world, pin_idx]
  PHB
  REP #$30
  LDA.b $02, S : AND.w #$00FF : ASL : TAX ; offset index in Caches
  ; Read CacheOffsets[pin_idx] then select SpecialSoaring_Caches (2) vs AbyssSoaring_Caches (1).
  LDA.b $03, S : AND.w #$00FF : CMP.w #$0001 : BEQ .dw_offset
    LDA.l SpecialSoaring_CacheOffsets, X : TAX
    BRA .prep_copy
  .dw_offset
    LDA.l AbyssSoaring_CacheOffsets, X : TAX
  .prep_copy
  SEP #$20
  LDA.b #$7E : PHA : PLB
  LDA.b $03, S : CMP.b #$01 : BEQ .copy_dw
  REP #$20
  LDY.w #$0000
  .copy_sw_loop
    LDA.l SpecialSoaring_Caches, X : STA.w $C140, Y
    INX #2 : INY #2 : CPY.w #$0032 : BCC .copy_sw_loop
  BRA .post_copy
  .copy_dw
  REP #$20
  LDY.w #$0000
  .copy_dw_loop
    LDA.l AbyssSoaring_Caches, X : STA.w $C140, Y
    INX #2 : INY #2 : CPY.w #$0032 : BCC .copy_dw_loop

  .post_copy
  ; The native cached-exit loader uses this full record, including camera,
  ; tilemap origin and fresh scroll modifiers.
  STZ.w $0696 : STZ.w $0698
  LDA.w #!GoronCheckpoint_CacheRoom : STA.b $A0
  STZ.w $010A : STZ.w $04AA
  SEP #$30
  STZ.w $0FFF
  PLB
  PLX : PLA                             ; discard [pin_idx, target_world copy]; S now [target_world]
  PLA                                   ; A = target_world (1 or 2)
  CMP.b #$01 : BEQ .set_abyss_world
    LDA.b #$00
    STA.l SavedWorld
    BRA .world_set
  .set_abyss_world
    LDA.b #$40
    STA.l SavedWorld
    LDA.b #$01
    STA.l $7E0FFF
  .world_set
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
  ; Step native Module $08 ($0283BF) under FBlank until it signals $10 == #$10.
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
  LDA.b #$00
  STA.l SpecialSoaring_LoadStep
  STA.l Soaring_MapSwitchPending
  STA.l Soaring_OriginWorld
  STA.l Soaring_ViewWorld
  ; Refresh Link/mask tunic palette and queue CGRAM upload before fade-in.
  JSL Palette_ArmorAndGloves
  INC.b $15
  ; Play map-close swoosh, set destination ambient SFX, and switch/restore BGM.
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
  JSR Soaring_ClearBirdAncillas
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

; Replaces $08DF7F..$08DF84 (LDA.w $DDE4,Y : STA.w $0AF4), M=8, X=8, DBR=$08.
; Maps frame 0 offset $00 -> $01 when outdoors in Eon Abyss ($40-$7F) so NMI
; $008B25 always runs MaybeUploadBirdGraphicsToOam on frame 0 as well (no 4-frame
; vanilla duck flash).
AbyssBird_SetPose:
{
  LDA.w $DDE4, Y
  BNE .store
  PHA
  LDA.b $8A : CMP.b #$40 : BCC .vanilla_zero
  CMP.b #$80 : BCS .vanilla_zero
    PLA : LDA.b #$01 : BRA .store
  .vanilla_zero
  PLA
  .store
  STA.w $0AF4
  RTL
}

; Special Overworld ($80-$BF) region membership -> SpecialTravelSpotsVisited ($7EF438) bits
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

; Eon Abyss ($40-$7F) region membership -> AbyssTravelSpotsVisited ($7EF43A) bits
;   $01 (Pin 1): Temporal Pyramid ($40/$41/$48/$49) - baseline hub
;   $02 (Pin 2): Abyss Windmill   ($63/$64/$6B/$6C) - baseline hub
;   $04 (Pin 3): Fortress Secrets ($4B/$4C/$53/$54) - visited-unlock
;   $08 (Pin 4): Twin Brothers    ($56)             - visited-unlock
;   $10 (Pin 5): Shrine Courage   ($50)             - visited-unlock
;   $20 (Pin 6): Lupo Temple      ($5E/$5F/$66/$67) - visited-unlock
;   $40 (Pin 7): Forest of Dreams ($58/$59/$60/$61) - visited-unlock
;   $80 (Pin 8): Abyss Beach      ($76/$77/$7E/$7F) - visited-unlock
AbyssTravelDest_Areas:
  db $40, $41, $48, $49
  db $63, $64, $6B, $6C
  db $4B, $4C, $53, $54
  db $56
  db $50
  db $5E, $5F, $66, $67
  db $58, $59, $60, $61
  db $76, $77, $7E, $7F
AbyssTravelDest_AreasEnd:
AbyssTravelDest_Masks:
  db $01, $01, $01, $01
  db $02, $02, $02, $02
  db $04, $04, $04, $04
  db $08
  db $10
  db $20, $20, $20, $20
  db $40, $40, $40, $40
  db $80, $80, $80, $80
assert (AbyssTravelDest_AreasEnd-AbyssTravelDest_Areas) == (pc()-AbyssTravelDest_Masks)

; Lyra Sea Mode 7 World Map pin coordinates (1:16 world scale -> x128..383, y128..383)
SpecialSoaring_PinXLo:
  db $B0, $00, $90, $F0, $A0, $20, $D0, $80
SpecialSoaring_PinXHi:
  db $02, $07, $02, $01, $06, $0E, $0D, $0B
SpecialSoaring_PinYLo:
  db $C0, $40, $10, $80, $A0, $20, $80, $B0
SpecialSoaring_PinYHi:
  db $01, $01, $07, $0C, $0D, $0A, $0E, $02

; Eon Abyss Mode 7 World Map pin coordinates (all 8 verified >=56.9 map-px separation)
;   0 (Pin 1): Temporal Pyramid ($40) -> X=$0240, Y=$0170
;   1 (Pin 2): Abyss Windmill   ($63) -> X=$08E0, Y=$0890
;   2 (Pin 3): Fortress Secrets ($4B) -> X=$0890, Y=$0340
;   3 (Pin 4): Twin Brothers    ($56) -> X=$0CE0, Y=$0560
;   4 (Pin 5): Shrine Courage   ($50) -> X=$0160, Y=$0540
;   5 (Pin 6): Lupo Temple      ($5E) -> X=$0E50, Y=$08A0
;   6 (Pin 7): Forest of Dreams ($58) -> X=$01F0, Y=$08F0
;   7 (Pin 8): Abyss Beach      ($76) -> X=$0E40, Y=$0EA0
AbyssSoaring_PinXLo:
  db $40, $E0, $90, $E0, $60, $50, $F0, $40
AbyssSoaring_PinXHi:
  db $02, $08, $08, $0C, $01, $0E, $01, $0E
AbyssSoaring_PinYLo:
  db $70, $90, $40, $60, $40, $A0, $F0, $A0
AbyssSoaring_PinYHi:
  db $01, $08, $03, $05, $05, $08, $08, $0E

SpecialSoaring_CacheOffsets:
  dw $0000, $0032, $0064, $0096, $00C8, $00FA, $012C, $015E
AbyssSoaring_CacheOffsets:
  dw $0000, $0032, $0064, $0096, $00C8, $00FA, $012C, $015E

SpecialSoaring_Caches:
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

AbyssSoaring_Caches:
  ; 0 (Pin 1): Temporal Pyramid ($40, Large): origin ($0000,$0000), cache (36,23) -> 5x5 walkable pad.
  dw $0040,$0016,$0120,$01C8,$0170,$0240,$0040,$0938
  dw $018F,$0247,$0000,$031E,$0000,$0300,$FF20,$0400,$FF00,$0400
  dw $2100,$2000,$0000,$0000,$0000,$0000,$0000
  ; 1 (Pin 2): Abyss Windmill ($63, Large): origin ($0600,$0800), cache (46,9) -> 5x5 walkable pad.
  dw $0063,$0016,$0840,$0868,$0890,$08E0,$0063,$020C
  dw $08AF,$08E7,$0800,$0B1E,$0600,$0900,$0720,$0C00,$0500,$0A00
  dw $2100,$2000,$0000,$0000,$0000,$0000,$0000
  ; 2 (Pin 3): Fortress ($4B, Large): origin ($0600,$0200), cache (41,20) -> 5x5 walkable pad.
  dw $004B,$0016,$02F0,$0818,$0340,$0890,$004B,$0782
  dw $035F,$0897,$0200,$051E,$0600,$0900,$0120,$0600,$0500,$0A00
  dw $2100,$2000,$0000,$0000,$0000,$0000,$0000
  ; 3 (Pin 4): Twin Brothers ($56, Small): origin ($0C00,$0400), cache (14,22) -> 5x5 walkable pad.
  dw $0056,$0016,$0510,$0C68,$0560,$0CE0,$0056,$088C
  dw $057F,$0CE7,$0400,$051E,$0C00,$0D00,$0320,$0600,$0B00,$0E00
  dw $2100,$2000,$0000,$0000,$0000,$0000,$0000
  ; 4 (Pin 5): Shrine Courage ($50, Small): origin ($0000,$0400), cache (22,20) -> 5x5 walkable pad.
  dw $0050,$0016,$04F0,$00E8,$0540,$0160,$0050,$079C
  dw $055F,$0167,$0400,$051E,$0000,$0100,$0320,$0600,$FF00,$0200
  dw $2100,$2000,$0000,$0000,$0000,$0000,$0000
  ; 5 (Pin 6): Lupo Temple ($5E, Large): origin ($0C00,$0600), cache (37,42) -> 5x5 walkable pad.
  dw $005E,$0016,$0850,$0DD8,$08A0,$0E50,$005E,$02BA
  dw $08BF,$0E57,$0600,$091E,$0C00,$0F00,$0520,$0A00,$0B00,$1000
  dw $2100,$2000,$0000,$0000,$0000,$0000,$0000
  ; 6 (Pin 7): Forest of Dreams ($58, Large): origin ($0000,$0600), cache (31,47) -> 5x5 walkable pad.
  dw $0058,$0016,$08A0,$0178,$08F0,$01F0,$0058,$052E
  dw $090F,$01F7,$0600,$091E,$0000,$0300,$0520,$0A00,$FF00,$0400
  dw $2100,$2000,$0000,$0000,$0000,$0000,$0000
  ; 7 (Pin 8): Abyss Beach ($76, Large): origin ($0C00,$0C00), cache (36,42) -> 5x5 walkable pad.
  dw $0076,$0016,$0E50,$0DC8,$0EA0,$0E40,$0076,$02B8
  dw $0EBF,$0E47,$0C00,$0F1E,$0C00,$0F00,$0B20,$1000,$0B00,$1000
  dw $2100,$2000,$0000,$0000,$0000,$0000,$0000
assert pc()-AbyssSoaring_Caches == $0190

GbcTravelBirdGfx:
  incbin "Items/gfx/gbc_travel_bird.4bpp"
assert (GbcTravelBirdGfx>>16) == ((pc()-1)>>16), "GbcTravelBirdGfx must stay within Bank $5F"

SpecialSoaring_CodeEnd:
print "Bank5F Soaring Code End:          ", pc, " (", dec($5FFFFF-pc()), " B free)"
assert pc() <= $5FFFFF, "Special Overworld soaring code exceeds bank $5F"

assert read3($08DF7F) == $DDE4B9 && read3($08DF82) == $0AF48D, "Ancilla27_Duck set_vram_offset ABI moved"
org $08DF7F ; @hook module=Items name=AbyssBird_SetPose kind=jsl target=AbyssBird_SetPose expected_m=8 expected_x=8
  JSL AbyssBird_SetPose
  NOP #2
assert pc() == $08DF85

pullpc

; The selected teaching action uses the native message lifecycle. No hooks or
; code are emitted until its approved message is explicitly bound in source.
incsrc "Items/sky_watch_log.asm"
