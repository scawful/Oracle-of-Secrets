; =========================================================
; Finale World-Split Breach Portal ($4B <-> $0B) &
; Volatile Finale Continue Point (Bank $34 free space)
;
; 1. FinaleBreach_IsUnlocked:
;    Carry Set once the Finale world-split breach is open:
;      - MakuTreeQuest ($7EF3D4) bit 1 (!MakuTree_HasSeed), OR
;      - OOSPROG ($7EF3D6) bit 7 (!Story_FortressComplete), OR
;      - OW event flag for DW $4B ($7EF280+$4B) bit 5 ($20, Fortress open).
;
; 2. FinaleBreach_TrySpotWarp (hook at $07D15C, TileDetect_MainHandler .no_warp_tile):
;    Allows crossing between Kalyxo Castle (LW $0B, 16-bit Light World) and
;    Fortress of Secrets (DW $4B, GBC Eon Abyss) at their shared unobstructed
;    courtyard spot (row 32, col 28 -> world X=$07C0, Y=$0400; 3x3 all-$00
;    walkable ground on both 2x2 maps, verified in live ROM).
;    - Works alongside or before a painted TileType $4B pad (LupoPadGate_Check
;      at $07D151 handles physical TileType $4B pads on LW $0B with SFX2.$3C
;      if stepped on before unlock).
;    - Crossing DW $4B -> LW $0B is always allowed.
;    - Crossing LW $0B -> DW $4B requires FinaleBreach_IsUnlocked; routes through
;      vanilla $07D156 (JSR Mirror_TryToWarp) so A4 AbyssVortex_CaptureOrigin
;      automatically arms SpecialOverworld_VortexWorld = $40 and spawns the
;      clickable $6C return vortex in DW $4B.
;
; 3. FinaleContinue_LoadCheckpointOrWorld (hook at $028192, Module05_LoadFile):
;    Volatile session checkpoint armed in WRAM FinaleContinueCheckpoint ($7EC139)
;    by Kydreeok_PostHealRestBeat / Kydreeok_Remnant after Song of Healing.
;    On GameOver -> Continue ($010A != 0) while Kydreeok's kill flag ($7EF005
;    bit 3) is set and Beast Ganon is not yet defeated (GanondorfFight != 2),
;    reloads Entrance $7B (Room $0002 with underworld song bank $15 and the
;    open pit plate directly into Room $0000 Ganondorf -> Beast Ganon) instead
;    of kicking Link back to the Dark World overworld / Fortress entrance.
;    Save & Quit / File Select ($010A == 0) clears the volatile flag and runs
;    ordinary LoadCheckpointOrWorld unchanged.
; =========================================================

; Volatile WRAM byte inside vanilla-unused $7EC132-$7EC13F
; (immediately after SpecialOverworld_VortexWorld = $7EC138).
FinaleContinueCheckpoint = $7EC139
!FinaleContinue_Magic    = $A5

; Shared unobstructed courtyard breach coordinate on both 2x2 maps:
;   LW $0B (Kalyxo Castle grand cobblestone avenue, r=32, c=28)
;   DW $4B (Fortress of Secrets inner courtyard plaza, r=32, c=28)
; Center tile world origin = ($07C0, $0400); 3x3 neighborhood
; ($07B0..$07DF, $03F0..$041F) is all-$00 walkable on both maps.
!FinaleBreach_CenterX = $07C0
!FinaleBreach_CenterY = $0400
!FinaleBreach_MinX    = $07B8
!FinaleBreach_SpanX   = $0011 ; [$07B8..$07C8]
!FinaleBreach_MinY    = $03F4
!FinaleBreach_SpanY   = $0011 ; [$03F4..$0404] (Link feet $03FC..$040C)

; ---------------------------------------------------------
; Carry Set = Finale breach unlocked; Carry Clear = locked.
; Entry/Exit: M=8, X=8, DB/X/Y preserved; clobbers A.
FinaleBreach_IsUnlocked:
{
  LDA.l MakuTreeQuest : AND.b #!MakuTree_HasSeed : BNE .unlocked
  LDA.l OOSPROG : AND.b #!Story_FortressComplete : BNE .unlocked
  LDA.l $7EF280+$4B : AND.b #$20 : BNE .unlocked
    CLC
    RTL
  .unlocked
  SEC
  RTL
}

; ---------------------------------------------------------
; Hook at $07D15C (TileDetect_MainHandler .no_warp_tile).
; Replaces 6 bytes: STZ.w $02DB : LDA.w $0357.
; Entry: M=8, X=8, DB=$07. Preserves X, Y, M/X widths, DB.
; Normal return: A = $0357 (matching displaced LDA.w $0357).
; Warp trigger: drops JSL return and JMLs $07D156 (JSR Mirror_TryToWarp).
FinaleBreach_TrySpotWarp:
{
  LDA.b $1B : BNE .not_breach
  LDA.b $8A
  CMP.b #$0B : BEQ .check_coords
  CMP.b #$4B : BNE .not_breach

  .check_coords
  REP #$20
  LDA.b $22 : SEC : SBC.w #!FinaleBreach_MinX
  CMP.w #!FinaleBreach_SpanX : BCS .outside_16
  LDA.b $20 : SEC : SBC.w #!FinaleBreach_MinY
  CMP.w #!FinaleBreach_SpanY : BCS .outside_16
  SEP #$20

  ; Inside the shared ($07C0, $0400) courtyard breach window.
  ; DW $4B -> LW $0B is always open; LW $0B -> DW $4B requires unlock.
  LDA.b $8A : CMP.b #$4B : BEQ .check_ready
    JSL FinaleBreach_IsUnlocked : BCC .not_breach

  .check_ready
  ; Post-warp invulnerability ($031F, set to $90 by MirrorWarp_Initialize,
  ; including returns via Sprite $6C): latch NOWARP so Link must step off
  ; the breach spot before crossing again (prevents ping-pong).
  LDA.w $031F : BEQ .check_state
    LDA.b #$01 : STA.w NOWARP
    BRA .keep_latch
  .check_state
  LDA.b $4D : BNE .keep_latch
  LDA.b $10 : CMP.b #$09 : BNE .keep_latch
  LDA.b $11 : BNE .keep_latch
  LDA.w NOWARP : BNE .keep_latch

  ; Trigger vanilla Mirror_TryToWarp ($07D156 -> JSR Mirror_TryToWarp : BRL .clear_tall_grass_flag)
  ; so A4 AbyssVortex_CaptureOrigin runs and arms the $6C return vortex cleanly.
  PLA : PLA : PLA
  JML $07D156

  .outside_16
  SEP #$20
  .not_breach
  STZ.w NOWARP
  .keep_latch
  LDA.w $0357
  RTL
}

; ---------------------------------------------------------
; Hook at $028192 (Module05_LoadFile) wrapping LoadCheckpointOrWorld.
; Entry: M=8, X=8, DB/DP unchanged.
FinaleContinue_LoadCheckpointOrWorld:
{
  LDA.l FinaleContinueCheckpoint : CMP.b #!FinaleContinue_Magic : BNE .pass_through
  ; Fresh file load (File Select / Save & Quit) has DEADLOAD ($010A) == 0:
  ; clear volatile checkpoint so new loads never hijack normal routing.
  LDA.w $010A : BEQ .clear_and_pass
  ; Require Kydreeok's saved kill flag (Room $0002 boss bit = $7EF005 bit 3)
  ; and Beast Ganon still undefeated (GanondorfFight != 2).
  LDA.l $7EF005 : AND.b #$08 : BEQ .clear_and_pass
  LDA.l GanondorfFight : CMP.b #$02 : BEQ .clear_and_pass

  ; Finale Continue active: run standard session resets, arm FinaleBeat, and
  ; reload Entrance $7B (Room $0002 with underworld song bank $15 + open plate
  ; directly into Room $0000 Ganondorf -> Beast Ganon).
  JSL Boat_ResetSession
  JSL ItemBindings_AdapterReset
  JSL ItemBindings_RestoreY
if !SPECIAL_OVERWORLD_NATIVE == 1
  JSL Lyra_TailEvent_MigrateSave
endif
  STZ.w GanondorfFight
  STZ.w BossReinject
  LDA.b #$60 : STA.w FinaleBeat
  LDA.b #$40 : STA.l SavedWorld
  LDA.b #$7B : STA.w $010E
  STZ.w $010F
  LDA.b #$01 : STA.w $010A    ; skip recaching nonexistent overworld exit
  STZ.w $04AA : STZ.w $04AB   ; select EntranceData ($7B), not SpawnPointData
  JML $028208                 ; LoadUnderworldRoomRebuildHUD

  .clear_and_pass
  LDA.b #$00 : STA.l FinaleContinueCheckpoint
  .pass_through
  JML LoadCheckpointOrWorld
}

pushpc

; TileDetect_MainHandler (.no_warp_tile): STZ.w $02DB : LDA.w $0357 (6 bytes).
assert read4($07D15C) == $AD02DB9C && read2($07D160) == $0357, "TileDetect_MainHandler .no_warp_tile moved"
org $07D15C ; @hook module=Overworld name=FinaleBreach_TrySpotWarp kind=jsl target=FinaleBreach_TrySpotWarp expected_m=8 expected_x=8 protected_size=6
  JSL FinaleBreach_TrySpotWarp : NOP #2
assert pc() == $07D162

pullpc
