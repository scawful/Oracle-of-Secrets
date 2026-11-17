; Room0078 repeatable Hammer opportunity. Long entries keep DBR from the
; bank05 sprite caller; every absolute operand is mirrored WRAM. M/X=8.
; Timers C/E are native zeroed/decremented per-slot timers, unused by Lanmola.
!Goron78_SurfaceFrames = 24
!Goron78_StaggerFrames = 48
!Goron78_StaggerCooldown = 96

Goron78_MoundReady:
{
  PHP
  JSL Goron78_IsRoom : BCC .legacy
  PLP
  LDA.b #$06 : STA.w SprAction,X
  LDA.b #!Goron78_SurfaceFrames : STA.w SprTimerC,X
  STZ.w SprHeight,X
  STZ.w SprXSpeed,X : STZ.w SprYSpeed,X : STZ.w SprTimerF,X
  RTL
  .legacy
  PLP
  JML Goron78_BeginFly
}

; Carry from the accepted native melee hit is not sufficient: weapon tinks
; also return carry. Require fresh positive queued damage, actual Hammer
; impact (not net/fist; $0300 step 1 or 2, hitbox live at step 2), active
; head and a ready cooldown. A Hammer hit always staggers: queued damage that
; would reach zero HP is cancelled (the native apply step at $0EF0&$7F==$18
; subtracts $0CE2), so the Hammer alone never kills a surfaced head here.
Goron78_SurfaceTick:
{
  JSL Goron78_IsRoom : BCC .done
  LDA.w SprDeath,X : PHA
  JSL Sprite_CheckDamageFromPlayer
  BCC .miss
  PLA : BNE .normal
  LDA.w $0301 : AND.b #$0A : CMP.b #$02 : BNE .normal
  LDA.w $0300 : DEC A : CMP.b #$02 : BCS .normal
  LDA.w $037A : AND.b #$10 : BNE .normal
  LDA.w SprTimerE,X : BNE .normal
  LDA.w SprType,X : CMP.b #$54 : BNE .normal
  LDA.w SprState,X : CMP.b #$09 : BNE .normal
  LDA.w SprAction,X : CMP.b #$06 : BNE .normal
  LDA.w SprDeath,X : BPL .normal
  LDA.w $0CE2,X : BEQ .normal
  CMP.w SprHealth,X : BCC .stagger
  STZ.w $0CE2,X
  .stagger
  LDA.b #$07 : STA.w SprAction,X
  LDA.b #!Goron78_StaggerFrames : STA.w SprTimerC,X
  LDA.b #!Goron78_StaggerCooldown : STA.w SprTimerE,X
  RTL
  .miss
  PLA
  .normal
  JSL Sprite_CheckDamageToPlayer
  LDA.w SprAction,X : CMP.b #$06 : BNE .done
  LDA.w SprTimerC,X : BNE .done
  JML Goron78_BeginFly
  .done
  RTL
}

; Existing sword/Hammer damage remains available; stagger never refreshes
; itself and suppresses contact damage only during this recovery phase.
Goron78_StaggerTick:
{
  JSL Goron78_IsRoom : BCC .done
  JSL Sprite_CheckDamageFromPlayer
  LDA.w SprAction,X : CMP.b #$07 : BNE .done
  LDA.w SprTimerC,X : BNE .done
  JML Goron78_BeginFly
  .done
  RTL
}

Goron78_BeginFly:
{
    JSL Lanmola_SpawnShrapnel

    LDA.b #$13 : STA $012D

    TXY
    JSL GetRandomInt : AND.b #$07 : TAX
    JSL Goron78_SelectLanmolaX ; Get random X pos to have the lanmola fly to. ;.randXPos

    JSL GetRandomInt : AND.b #$07 : TAX
    LDA $7EEAB0, X : STA.w SprMiscB, Y ; Get random Y pos to have the lanmola fly to. ;.randYPos
    TYX

    LDA.b #$02 : STA.w SprAction, X

    LDA.b #$18 : STA $0F80, X

    STZ.w SprMiscF, X
    STZ.w SprMiscG, X

  JML Goron78_ScatterLong
}

; Keep northern endpoints unchanged. Lower endpoints gain ground-projection
; clearance from A's ore and room perimeter; retain eight X choices and all
; three initial starts. Preserve incoming carry, as GetRandomInt consumes it.
Goron78_SelectLanmolaY:
{
  PHP
  JSL Goron78_IsRoom : BCC .vanilla
  LDA.w SprYH,Y : CMP.b #$0F : BNE .vanilla
  PLP
  LDA.l .south,X
  RTL
  .vanilla
  PLP
  LDA.l $7EEAB0,X
  RTL
  .south
  db $70,$74,$78,$7C,$80,$84,$88,$90
}
Goron78_HammerHelperEnd:
assert pc() <= $310000, "Room78 Hammer helper exceeds bank30 sprite stream"
