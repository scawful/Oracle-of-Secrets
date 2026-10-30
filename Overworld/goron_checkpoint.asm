; Prepared file2 start outside Goron Mines. Module05 enters M8/X8, DB/DP
; unchanged. Selector07 is one-shot: native Save & Quit persists House00.
; The original factory SRAM repeats the outside start until that first save.
!GoronCheckpoint_CacheRoom = $0151 ; Native cached-exit room; no entrance owns it

LoadCheckpointOrWorld:
{
if !ENABLE_KALYXO_BOAT == 1
  JSL Boat_ResetSession
endif
  if defined("PROJECT_BG128_ENABLED")
    if !PROJECT_BG128_ENABLED == 1
      JSL ProjectBGPalette_RestoreAndInvalidate ; Warm file/Continue: restore before invalidating.
    endif
  endif
  if !LYRA_CURRENT_EVENTS_ENABLED == 1
    JSL Lyra_TailEvent_MigrateSave
  endif
  if !REGIONAL_CHECKPOINTS_ENABLED == 1
    JSL Checkpoint_Load
    BCC .not_regional
      RTL
    .not_regional
  endif
  LDA.l SpawnPoint : CMP.b #!Spawn_GoronCheckpoint : BNE .legacy
    ; Consume even a malformed marker before the seven-record spawn arrays.
    LDA.b #!Spawn_LinksHouse : STA.l SpawnPoint
    LDA.l GameState : CMP.b #$02 : BNE .legacy
    LDA.l SavedWorld : BNE .legacy
    LDA.l FollowerId : BNE .legacy ; No follower can be relocated by this checkpoint
    BRA .checkpoint
  .legacy
    ; Preserve the original policy's A/N/Z for Module05's BEQ at028196.
    JSL LoadDarkWorldIntro
    JML $028196

  .checkpoint
    ; Same HUD calls as native Module05's outdoor branch at02819C.
    JSL $0DE395 ; SearchForEquippedItem_long
    JSL $0DFA6C ; RebuildHUD_long2
    JSL $0DDD32 ; UpdateEquippedItem_long

    ; The normal Module08 loader consumes the full native exit cache. Keep
    ; position, scroll, tilemap origin and camera triggers in one record.
    PHP
    REP #$20
    LDX.b #$30
    .copy
      LDA.l GoronCheckpoint_Cache, X : STA.l $7EC140, X
    DEX #2 : BPL .copy
    STZ.w $0696
    STZ.w $0698
    LDA.w #!GoronCheckpoint_CacheRoom : STA.b $A0
    PLP

Checkpoint_EnterPreparedCache:
    STZ.w $010A
    STZ.w $04AA
    LDA.b #$80 : STA.b $13
    STZ.b $9B
    STZ.b $11
    STZ.b $B0
    LDA.b #$08 : STA.b $10
    ; JML added no return frame: return directly to Module05's long caller.
    RTL
}

LyraHost_LoadCheckpointOrWorld_End = pc()

; Native cached-exit image, consumed by $02E5D4. Public-side floor east of
; the Goron on large area36; keep the ordinary room98 exit unchanged.
; Scroll = position -120/-80; triggers = position +7/+31. Bounds come from
; area's Pool tables and are recomputed by NewOverworld_SetCameraBounds.
; AA1/AA2=20/62; AA3 is overwritten from7EFCC0,36 by02AB0D before GFX use.
; Zero modifiers initialize fresh camera-stripe progress, like SwordWarp_Cache.
macro RegionalCheckpoint_GoronControlCache()
  dw $0036, $0016               ; Area, main/subscreen
  dw $0DD8, $0CA8               ; Scroll Y/X
  dw $0E28, $0D20               ; Link Y/X
  dw $0036, $0E94               ; Area, tilemap origin
  dw $0E47, $0D27               ; Camera triggers Y/X
  dw $0C00, $0F1E, $0C00, $0F00 ; Camera bounds0600-0606
  dw $0B20, $1000, $0B00, $1000 ; Camera bounds0610-0616
  dw $2000, $0062               ; Graphics bytes0AA0-0AA3
  dw $0000                      ; Unused cache word
  dw $0000, $0000, $0000, $0000 ; Fresh scroll modifiers
endmacro
GoronCheckpoint_Cache:
  %RegionalCheckpoint_GoronControlCache()
assert pc()-GoronCheckpoint_Cache == $32
