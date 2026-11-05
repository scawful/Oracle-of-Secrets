; Magic wake and pose snapshots share the $46 child dispatch in bank $2A.
; All local entries inherit M=8, X/Y=8, DB=$2A. No garnish slots are touched:
; the native falling-floor effect needs that pool until it writes each pit.
; Mode4: stationary bat wake, 32 ticks, four nodes, final eight harmless.
; Mode5: harmless body/bat pose snapshot, 12 ticks, two nodes.

GanonMagic_TryAfterimage:
{
  LDA.w SprAction, X : CMP.b #$01 : BEQ .moving
  CMP.b #$03 : BNE .exit
  .moving
  LDA.w SprXSpeed, X : ORA.w SprYSpeed, X : BEQ .exit
  LDA.w SprTimerB, X : BNE .exit
  LDA.b #$08 : STA.w SprTimerB, X
  LDA.b #$05 : JSR GanonMagic_Spawn
  .after_spawn
  .exit
  RTS
}

GanonMagic_TryBatEffects:
{
  LDA.w SprTimerB, X : BNE .exit
  LDA.b #$08 : STA.w SprTimerB, X
  LDA.b #$04 : JSR GanonMagic_Spawn
  LDA.b #$05 : JSR GanonMagic_Spawn
  .after_spawn
  .exit
  RTS
}

; A=mode, X=emitter. Count active effects before using the normal allocator.
; Full capacity skips the effect and never evicts a sprite or changes combat.
GanonMagic_Spawn:
{
  PHA
  STA.b $0E
  STZ.b $0F
  LDY.b #$0F
  .count
  LDA.w SprState, Y : BEQ .next
  LDA.w SprType, Y : CMP.b #Sprite_GanonBall : BNE .next
  LDA.w SprAction, Y : CMP.b $0E : BNE .next
    INC.b $0F
  .next
  DEY : BPL .count
  LDA.b $0E : CMP.b #$04 : BNE .ghost_cap
    LDA.b $0F : CMP.b #$04 : BCS .full
    BRA .allocate
  .ghost_cap
    LDA.b $0F : CMP.b #$02 : BCS .full
  .allocate
  LDA.b #Sprite_GanonBall : JSL Sprite_SpawnDynamically : BPL .spawned
  .full
  PLA
  CLC
  RTS

  .spawned
  PLA : STA.w SprAction, Y
  LDA.w SprX, X : STA.w SprX, Y
  LDA.w SprXH, X : STA.w SprXH, Y
  LDA.w SprY, X : STA.w SprY, Y
  LDA.w SprYH, X : STA.w SprYH, Y
  LDA.w SprHeight, X : STA.w SprHeight, Y
  LDA.w SprFloor, X : STA.w SprFloor, Y
  LDA.w SprFrame, X : STA.w SprFrame, Y
  LDA.b #$00
  STA.w SprXSpeed, Y
  STA.w SprYSpeed, Y
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
  LDA.b #$01 : STA.w SprHealth, Y
  STA.w SprBump, Y
  LDA.b #$C0 : STA.w SprGfxProps, Y
  ; Bit2 ignores weapons; bit1 bypasses generic KillFriends death/OAM reset.
  ; Owner guards below remove the effect directly when Ganondorf dies.
  LDA.b #$46 : STA.w SprDefl, Y
  LDA.w SprType, X : CMP.b #Sprite_Ganondorf : BNE .bat_owner
    TXA : STA.w SprMiscD, Y
    BRA .properties
  .bat_owner
    LDA.w SprMiscD, X : STA.w SprMiscD, Y
    LDA.b #$01 : STA.w SprSubtype, Y
  .properties
  LDA.w SprAction, Y : CMP.b #$04 : BNE .afterimage
    LDA.b #$20 : STA.w SprTimerA, Y
    LDA.b #$59 : STA.w SprHitbox, Y
    LDA.b #$40 : STA.w SprNbrOAM, Y
    BRA .done
  .afterimage
    LDA.b #$0C : STA.w SprTimerA, Y
    LDA.b #$40 : STA.w SprHitbox, Y
    ; Moving body poses use six pieces; the bat uses one. Both are harmless.
    LDA.w SprSubtype, Y : BNE .bat
      LDA.b #$85 : BRA .oam
    .bat
      LDA.b #$80
    .oam
    STA.w SprNbrOAM, Y
  .done
  SEC
  RTS
}

GanonMagic_Main:
{
  JSR GanonBall_InsideArena : BCS .kill
  LDY.w SprMiscD, X : CPY.b #$10 : BCS .kill
  LDA.w SprState, Y : CMP.b #$09 : BNE .kill
  LDA.w SprType, Y : CMP.b #Sprite_Ganondorf : BNE .kill
  LDA.w SprAction, Y : CMP.b #$06 : BEQ .kill
  LDA.w SprTimerA, X : BEQ .kill
  LDA.w SprAction, X : CMP.b #$04 : BNE .exit
  LDA.w SprTimerA, X : CMP.b #$09 : BCC .exit
  JSL Sprite_CheckDamageToPlayerSameLayer
  .exit
  RTS
  .kill
  STZ.w SprState, X
  RTS
}

GanonMagic_DrawWake:
{
  LDA.w SprTimerA, X : BEQ .exit
  CMP.b #$19 : BCC .ember
    ; The first eight ticks retain the bat silhouette at its old position.
    JSR Ganon_DrawFrame
    RTS
  .ember
  CMP.b #$05 : BCS .small
  AND.b #$01 : BNE .exit
  .small
  JSR GanonBall_DrawSmall
  .exit
  RTS
}

GanonMagic_DrawAfterimage:
{
  LDA.w SprTimerA, X : BEQ .done
  LDA.w SprSubtype, X : BEQ .body
    LDA.b $1A : AND.b #$02 : BNE .done
    BRA .draw
  .body
  ; At most one full-body ghost draws per frame, even with two snapshots.
  STX.b $00
  LDY.b #$0F
  .higher
  CPY.b $00 : BEQ .first
  LDA.w SprState, Y : BEQ .next
  LDA.w SprType, Y : CMP.b #Sprite_GanonBall : BNE .next
  LDA.w SprAction, Y : CMP.b #$05 : BNE .next
  LDA.w SprSubtype, Y : BNE .next
    LDA.b $1A : AND.b #$04 : BEQ .done
    BRA .draw
  .next
  DEY : BPL .higher
  .first
  LDA.b $1A : AND.b #$04 : BNE .done
  .draw
  JSR Ganon_DrawFrame
  .done
  RTS
}
