; This file contains the custom logic for the guard capture sequence.
; WIP

; 1. Place the new, expanded logic in a free bank ($1E).
freedata bank $1E

; This routine captures the player and warps them to a specific dungeon entrance.
; It is a modified version of the WallMaster capture logic.
; Expects the desired entrance ID to be in the A register.
Oracle_CaptureAndWarp:
{
  STA.w $010E        ; Set the target entrance ID

  ; Mark player as captured (one-shot flag)
  LDA.l CastleAmbushFlags : ORA.b #!CastleAmbush_HasBeenCaptured
  STA.l CastleAmbushFlags

  ; Set spawn point to Prison — die/continue will return here
  LDA.b #!Spawn_Prison
  STA.l SpawnPoint

  LDA.b #$05         ; Game Mode 05: (hole/whirlpool transition)
  STA.b $10          ; Set the game mode

  STZ.b $2F          ; Clear Link's action state
  STZ.b $5D          ; Clear Link's state (e.g., walking)

  LDA.b #$02
  STA.b $71          ; Set transition/camera flag

  RTL
}

; This is a custom version of the Guard_Main routine from bank $05.
; It is hooked to add the capture-and-warp logic.
Hooked_Guard_Main:
{
  ; First, execute the two instructions that were overwritten by our JSL hook.
  LDA.w $0DC0, X
  PHA

  ; --- Start of Ported Vanilla Code ---
  LDY.w SprMiscC, X
  PHY

  LDA.w SprTimerB, X
  BEQ .looking_around

  LDA.w $05C234, Y ; SpriteDirections_Bank05, Y
  STA.w SprMiscC, X

  LDA.w $05C23A, Y ; SpriteDrawSteps_Bank05, Y
  STA.w $0DC0, X

.looking_around
  JSR $05C4B8 ; Guard_HandleAllAnimation

  PLA
  STA.w SprMiscC, X

  PLA
  STA.w $0DC0, X

  LDA.w $0DD0, X
  CMP.b #$05
  BNE .Guard_NotFalling

  LDA.b $11
  BNE .Return

  JSR $05C4B5 ; Guard_TickTwiceAndUpdateBody
  JMP $05C4B5 ; Guard_TickTwiceAndUpdateBody

.Guard_NotFalling
  JSR $05C1E1 ; Sprite_CheckIfActive_Bank05
  JSL $05C55E ; Guard_ParrySwordAttacks

  ; --- MINISH EVASION ---
  ; D3 prison guards (subtype >= $05) cannot detect Minish Link.
  ; Skip damage check entirely so Link takes no damage and triggers no alert.
if !ENABLE_D3_PRISON_SEQUENCE == 1
  LDA.w SprSubtype, X : AND.b #$07 : CMP.b #$05 : BCC .not_prison_guard
    LDA.l !CurrentMask : CMP.b #$05 : BEQ .not_triggered
  .not_prison_guard
endif

  JSL $07E934 ; Sprite_CheckDamageToLink_long
  BCS .hit_im

  LDA.w $0FDC
  BEQ .not_triggered

.hit_im
  ; --- CAPTURE SEQUENCE ---
  ; Only D3 castle guards (subtype >= $05) trigger the capture sequence.
  ; All other guards fall through to vanilla alert/recoil behavior.
  LDA.w SprSubtype, X
  AND.b #$07
  CMP.b #$05
  BCC .vanilla_alert

  ; One-shot: don't re-capture if player already captured
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_HasBeenCaptured
  BNE .vanilla_alert

  ; Capture and warp to Kalyxo Castle Prison (entrance $32)
  LDA.b #$32
  JSL Oracle_CaptureAndWarp
  RTL

  .vanilla_alert
  ; --- END MODIFICATION ---

.not_triggered
  LDA.w $0EA0, X
  BEQ .not_recoiling

  CMP.b #$04
  BCC .not_recoiling

  LDA.b #$04
  STA.w SprAction, X

  LDA.b #$80

.continue
  JSR $05C4AF ; Guard_SetTimerAndAssertTileHitbox

.not_recoiling
  JSR $05C291 ; Sprite_CheckIfRecoiling_Bank05

  LDA.w SprSubtype, X
  AND.b #$07
  CMP.b #$05
  BCS .cant_go_over_short_tiles

  LDA.w SprCollision, X
  BNE .tile_collision

  JSR $05C1D4 ; Sprite_Move_XY_Bank05

.tile_collision
  JSR $05C2A5 ; Sprite_CheckTileCollision_Bank05

  BRA .continue_after_move

.cant_go_over_short_tiles
  JSR $05C1D4 ; Sprite_Move_XY_Bank05

.continue_after_move
  LDA.w SprAction, X
  CMP.b #$04
  BEQ .not_chasing

  STZ.w $0ED0, X

.not_chasing
  REP #$30

  AND.w #$00FF
  ASL A
  TAY

  LDA.w $05C2C6, Y ; .vectors, Y
  DEC A
  PHA

  SEP #$30

.Return
  RTS
  ; --- End of Ported Vanilla Code ---
}
freedata clean

; 2. Go to the vanilla code address and inject the jump.
; The original instructions were LDA.w $0DC0,X (3 bytes) and PHA (1 byte).
; A JSL is 4 bytes, so this is a perfect 1-to-1 replacement in size.
;
; Guardrail: hook is feature-gated so regressions can be isolated quickly.
if !ENABLE_D3_PRISON_SEQUENCE == 1
pushpc
org $05C227 ; Start of vanilla Guard_Main ; @hook module=Sprites
  JSL Hooked_Guard_Main
pullpc
endif
