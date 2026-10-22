; Independent cast enemy on the existing $46 child dispatch, action 3.
; Local calls inherit M=8, X/Y=8 and DB=$2A. SprMiscD owns the parent slot;
; it never occupies the parent's rally-ball pointer or returns a volley.

Ganondorf_SpawnBat:
{
  LDA.b #Sprite_GanonBall : JSL Sprite_SpawnDynamically : BPL .spawned
    CLC
    RTS ; the parent still finishes its recovery when all slots are occupied
  .spawned
  LDA.w SprX, X : STA.w SprX, Y
  LDA.w SprXH, X : STA.w SprXH, Y
  ; Cast from body center at hover height, with a true 16px child origin.
  LDA.w SprY, X : SEC : SBC.w SprHeight, X : STA.b $00
  LDA.w SprYH, X : SBC.b #$00 : STA.b $01
  LDA.b $00 : SEC : SBC.b #$08 : STA.w SprY, Y
  LDA.b $01 : SBC.b #$00 : STA.w SprYH, Y
  LDA.w SprFloor, X : STA.w SprFloor, Y
  LDA.b #$00
  STA.w SprHeight, Y
  STA.w SprXRound, Y
  STA.w SprYRound, Y
  STA.w SprMiscA, Y
  STA.w SprMiscB, Y
  STA.w SprMiscC, Y
  STA.w SprMiscE, Y
  STA.w SprMiscF, Y
  STA.w SprMiscG, Y
  STA.w SprTimerB, Y
  STA.w SprTimerC, Y
  STA.w SprTimerD, Y
  STA.w SprTimerE, Y
  STA.w SprTimerF, Y
  STA.w SprFlash, Y
  STA.w SprPause, Y
  STA.w SprRecoil, Y
  STA.w SprDeath, Y
  STA.w SprDmgTaken, Y
  STA.w SprSubtype, Y
  TXA : STA.w SprMiscD, Y
  LDA.b #$03 : STA.w SprAction, Y
  LDA.b #!Ganon_FrameBat : STA.w SprFrame, Y
  LDA.b #!Ganon_BatLifetime : STA.w SprTimerA, Y
  ; Keep the room-tag exemption, but clear the orb's weapon immunity.
  LDA.b #$01 : STA.w SprHealth, Y
  LDA.b #$01 : STA.w SprBump, Y
  LDA.b #$80 : STA.w SprGfxProps, Y
  LDA.b #$40 : STA.w SprDefl, Y
  STA.w SprHitbox, Y ; hitbox 0 plus the attack's room-tag exemption
  LDA.b #$01 : STA.w SprNbrOAM, Y
  PHX : TYX
  LDA.b #!Ganon_BatSpeed : JSL Sprite_ApplySpeedTowardsPlayer
  PLX
  LDA.b #$29 : JSL SpriteSFX_QueueSFX3WithPan
  SEC
  RTS
}

GanonBat_Main:
{
  JSR GanonBall_InsideArena : BCS .kill
  LDY.w SprMiscD, X : CPY.b #$10 : BCS .kill
  LDA.w SprState, Y : CMP.b #$09 : BNE .kill
  LDA.w SprType, Y : CMP.b #Sprite_Ganondorf : BNE .kill
  LDA.w SprAction, Y : CMP.b #$06 : BEQ .kill
  LDA.w SprTimerA, X : BEQ .dissipate
  ; Ancilla run before sprites and may already have queued a ranged hit.
  LDA.w SprDeath, X : BMI .dissipate
  LDA.w SprDmgTaken, X : BNE .dissipate
  ; Fixed launch aim gives Link a dodgeable pass instead of continuous homing.
  JSL Sprite_Move
  JSR GanonBall_CheckBackground : BNE .dissipate
  JSL Sprite_CheckDamageFromPlayer : BCS .weapon_hit
  JSL Sprite_CheckDamageToPlayerSameLayer : BCS .dissipate
  JSR GanonMagic_TryBatEffects
  BRA .exit
  .dissipate
  JMP GanonBall_StartDissipation
  .weapon_hit
  ; The shared puff entry cancels the native delayed-damage queue.
  JMP GanonBall_StartDissipation
  .kill
  STZ.w SprState, X
  .exit
  RTS
}

GanonBat_Draw:
{
  LDA.b $1A : LSR #2 : AND.b #$03 : TAY
  LDA.w .frames, Y : STA.w SprFrame, X
  JMP Ganon_DrawFrame
  .frames : db 19, 20, 21, 20
}
