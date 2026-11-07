; Private D4: $11 subtype3 warden, $B8 subtype2 protector/3 living Princess.
; No dialogue/new SRAM. Room46 tag0A opens shutters after normal enemy death.
; Warden A=gait,B=attack choice,C=facing R/L/D/U,D=valve-used latch.
; Protector A=valve latch,TimerB=gesture; Action=Healing only.
D4Zora_CodeStart:
incsrc "Core/Generated/d4_zora_sprite_sheets/frame_tables.asm"

D4Zora_IsRescueActor:
{
  LDA.w ROOM : CMP.b #$46 : BNE .no
  LDA.w ROOM+1 : BNE .no
  LDA.w SprSubtype, X : CMP.b #$02 : BEQ .yes
  CMP.b #$03 : BNE .no
  .yes
  SEC : RTL
  .no
  CLC : RTL
}

D4Zora_Prep:
{
  PHB : PHK : PLB
  JSR D4Zora_LoadPalettes
  LDA.b #$83 : STA.w SprNbrOAM, X
  LDA.b #$42 : STA.w SprHitbox, X
  STZ.w SprDefl, X
  STZ.w SprTileDie, X
  STZ.w SprAction, X
  STZ.w SprFrame, X
  STZ.w $0DC0, X
  STZ.w SprMiscA, X
  STZ.w SprTimerB, X
  LDA.w SprSubtype, X : CMP.b #$02 : BNE .done
  LDA.b #$81 : STA.w SprNbrOAM, X
  LDA.l $7EF302 : BEQ .done
  STZ.w SprState, X
  .done
  PLB : RTL
}

D4Zora_Long:
{
  PHB : PHK : PLB
  LDA.w SprSubtype, X : CMP.b #$03 : BNE .protector
  JSR Sprite_ZoraPrincess_Draw
  JSL Sprite_CheckActive : BCC .done
  JSL Sprite_PlayerCantPassThrough
  BRA .done
  .protector
  LDA.b #!D4Zora_Frame_protector_rest : STA.w SprFrame, X
  LDA.w SprTimerB, X : BEQ .healing_frame
  LDA.b #!D4Zora_Frame_protector_idle_side : STA.w SprFrame, X
  .healing_frame
  LDA.w SprAction, X : CMP.b #$01 : BNE .draw
  LDA.b #!D4Zora_Frame_protector_healing : STA.w SprFrame, X
  .draw
  JSR D4Zora_Draw
  JSL Sprite_CheckActive : BCC .done
  JSR D4Zora_ProtectorMain
  .done
  PLB : RTL
}

D4Zora_ProtectorMain:
{
  JSL Sprite_PlayerCantPassThrough
  LDA.l $7EF302 : BEQ .not_owned
  STZ.w SprState, X
  RTS
  .not_owned
  LDA.w SprAction, X : CMP.b #$01 : BEQ .healing
  ; Assist never enters Healing or consumes a song. Include the death poof
  ; in the warden-alive check so a premature Healing cannot award the Mask.
  PHX
  LDX.b #$0F
  .scan
  LDA.w SprState, X : BEQ .next
  LDA.w SprType, X : CMP.b #$11 : BNE .next
  LDA.w SprSubtype, X : CMP.b #$03 : BEQ .blocked
  .next
  DEX : BPL .scan
  PLX
  JSL GetDistance8bit_Long : CMP.b #$30 : BCS .done
  LDA.w SprFloor, X : CMP.b $EE : BNE .done
  LDA.b SongFlag : CMP.b #$01 : BNE .done
  STZ.b SongFlag
  LDA.b #$60 : STA.w SprTimerD, X
  LDA.b #$01 : STA.w SprAction, X
  RTS
  .blocked
  PLX
  .done
  RTS
  .healing
  LDA.w SprTimerD, X : BNE .done
  LDA.b #$01 : STA.l $7EF302
  PHX
  LDY.b #$0F : STZ.w $02E9
  JSL Link_ReceiveItem
  PLX
  STZ.w SprState, X
  RTS
}

D4Warden_Prep:
{
  PHB : PHK : PLB
  JSR D4Zora_LoadPalettes
  LDA.b #$0E : STA.w SprNbrOAM, X ; maximum15, including vent steam
  LDA.b #$18 : STA.w SprHealth, X
  LDA.b #$03 : STA.w SprBump, X
  LDA.b #$07 : STA.w SprHitbox, X ; vanilla32x40 at(-8,-16)
  LDA.b #$40 : STA.w SprGfxProps, X
  STZ.w SprDefl, X
  STZ.w SprTileDie, X
  STZ.w SprPrize, X
  STZ.w SprAction, X
  STZ.w SprMiscA, X
  STZ.w SprMiscB, X
  STZ.w SprMiscD, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  LDA.b #$02 : STA.w SprMiscC, X
  LDA.b #!D4Zora_Frame_front_walk_0 : STA.w SprFrame, X
  LDA.l $7EF302 : BEQ .done
  STZ.w SprState, X
  .done
  PLB : RTL
}

D4Warden_Long:
{
  PHB : PHK : PLB
  LDA.w SprState, X : CMP.b #$06 : BEQ .done
  JSR D4Zora_Draw
  JSL Sprite_CheckActive : BCC .done
  JSR D4Warden_Main
  .done
  PLB : RTL
}

; Carry set only in upper-left arena, excluding gallery and rescue room.
D4Warden_LinkInArena:
{
  LDA.w SprFloor, X : CMP.b $EE : BNE .no
  LDA.b $23 : AND.b #$01 : BNE .no
  LDA.b $21 : AND.b #$01 : BNE .no
  LDA.b $22 : CMP.b #$20 : BCC .no
  CMP.b #$E0 : BCS .no
  LDA.b $20 : CMP.b #$30 : BCC .no
  CMP.b #$E0 : BCS .no
  SEC : RTS
  .no
  CLC : RTS
}

D4Warden_Main:
{
  LDA.w SprAction, X : CMP.b #$07 : BCC .armored
  LDA.w SprGfxProps, X : AND.b #$BF : STA.w SprGfxProps, X
  BRA .damage
  .armored
  LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X
  .damage
  JSL Sprite_CheckDamageFromPlayer
  LDA.w SprState, X : CMP.b #$09 : BEQ .active
  RTS
  .active
  LDA.w SprAction, X : CMP.b #$03 : BEQ .dispatch
  CMP.b #$06 : BEQ .dispatch
  JSL Sprite_PlayerCantPassThrough
  .dispatch
  LDA.w SprAction, X
  JSL JumpTableLocal
  dw .dormant,.approach,.charge_brace,.charge,.slam_windup
  dw .slam_hold,.slam_strike,.slam_stuck,.slam_recover,.vent
  .dormant
  JSR D4Warden_LinkInArena : BCC .done
  JSR D4Warden_StartApproach
  RTS
  .approach
  JSR D4Warden_LinkInArena : BCS .approach_active
  STZ.w SprAction, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  RTS
  .approach_active
  LDA.w SprMiscA, X : AND.b #$0F : BNE .walk
  JSL Sprite_DirectionToFacePlayer : TYA : STA.w SprMiscC, X
  LDA.b #$08 : JSL Sprite_ApplySpeedTowardsPlayer
  .walk
  INC.w SprMiscA, X
  JSR D4Warden_SelectWalk
  JSL Sprite_CheckTileCollision : BNE .decision
  JSR D4Warden_MoveBounded
  .decision
  LDA.w SprTimerA, X : BNE .done
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  JSL Sprite_DirectionToFacePlayer : TYA : STA.w SprMiscC, X
  LDA.w SprMiscB, X : BEQ .choose_charge
  JSL GetDistance8bit_Long : CMP.b #$50 : BCS .choose_charge
  LDA.b #$04 : STA.w SprAction, X
  LDA.b #$0C : STA.w SprTimerA, X
  RTS
  .choose_charge
  ; Capture aim at the cue; no pursuit or retargeting through40fwindup.
  LDA.b #$20 : JSL Sprite_ApplySpeedTowardsPlayer
  LDA.b #$02 : STA.w SprAction, X
  LDA.b #$28 : STA.w SprTimerA, X
  .done
  RTS
  .charge_brace
  LDA.b #$00 : JSR D4Warden_SelectCharge
  LDA.w SprTimerA, X : BEQ .start_charge
  RTS
  .start_charge
  LDA.b #$03 : STA.w SprAction, X
  LDA.b #$18 : STA.w SprTimerA, X
  RTS
  .charge
  LDA.w SprTimerA, X : LSR #3 : AND.b #$01 : INC A
  JSR D4Warden_SelectCharge
  JSL Sprite_CheckDamageToPlayerSameLayer
  JSL Sprite_CheckTileCollision : BNE .enter_vent
  JSR D4Warden_MoveBounded : BCS .enter_vent
  LDA.w SprTimerA, X : BEQ .enter_vent
  RTS
  .enter_vent
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  LDA.b #$09 : STA.w SprAction, X
  LDA.b #$38 : STA.w SprTimerA, X
  RTS
  .slam_windup
  LDA.b #$00 : JSR D4Warden_SelectSlam
  LDA.w SprTimerA, X : BEQ .start_hold
  RTS
  .start_hold
  LDA.b #$05 : STA.w SprAction, X
  LDA.b #$1C : STA.w SprTimerA, X
  RTS
  .slam_hold
  LDA.b #$01 : JSR D4Warden_SelectSlam
  LDA.w SprTimerA, X : BEQ .start_strike
  RTS
  .start_strike
  LDA.b #$06 : STA.w SprAction, X
  LDA.b #$04 : STA.w SprTimerA, X
  RTS
  .slam_strike
  LDA.b #$02 : JSR D4Warden_SelectSlam
  JSR D4Warden_AnchorDamage
  LDA.w SprTimerA, X : BEQ .start_stuck
  RTS
  .start_stuck
  LDA.b #$07 : STA.w SprAction, X
  LDA.b #$28 : STA.w SprTimerA, X
  RTS
  .slam_stuck
  LDA.b #$03 : JSR D4Warden_SelectSlam
  LDA.w SprTimerA, X : BEQ .start_pull
  RTS
  .start_pull
  LDA.b #$08 : STA.w SprAction, X
  LDA.b #$10 : STA.w SprTimerA, X
  RTS
  .slam_recover
  LDA.b #$04 : JSR D4Warden_SelectSlam
  LDA.w SprTimerA, X : BEQ .finish_slam
  RTS
  .finish_slam
  JSR D4Warden_NextAttack
  RTS
  .vent
  JSR D4Warden_SelectVent
  JSR D4Warden_TryValveAssist
  LDA.w SprTimerA, X : BEQ .finish_vent
  RTS
  .finish_vent
  JSR D4Warden_NextAttack
  RTS
}

D4Warden_StartApproach:
{
  LDA.b #$01 : STA.w SprAction, X
  LDA.b #$30 : STA.w SprTimerA, X
  STZ.w SprMiscA, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  RTS
}
D4Warden_NextAttack:
{
  LDA.w SprMiscB, X : EOR.b #$01 : STA.w SprMiscB, X
  JSR D4Warden_StartApproach
  RTS
}

; A=phase, direction R/L/D/U. Preserve actor X.
D4Warden_SelectCharge:
{
  STA $0A
  LDA.w SprMiscC, X : ASL #2 : CLC : ADC $0A
  PHX : TAX : LDA.l D4Warden_ChargeFrames, X
  PLX : STA.w SprFrame, X
  RTS
}
D4Warden_SelectWalk:
{
  LDA.w SprMiscA, X : LSR #3 : AND.b #$03 : STA $0A
  LDA.w SprMiscC, X : ASL #2 : CLC : ADC $0A
  PHX : TAX : LDA.l D4Warden_WalkFrames, X
  PLX : STA.w SprFrame, X
  RTS
}
D4Warden_SelectSlam:
{
  STA $0A
  LDA.w SprMiscC, X : STA $0B : ASL #2 : CLC : ADC $0B : CLC : ADC $0A
  PHX : TAX : LDA.l D4Warden_SlamFrames, X
  PLX : STA.w SprFrame, X
  RTS
}
D4Warden_SelectVent:
{
  LDA.w SprMiscC, X
  PHX : TAX : LDA.l D4Warden_VentFrames, X
  PLX : STA.w SprFrame, X
  RTS
}

; Tile collision precedes this. Keep the actor in the upper-left floor and
; roll back only this frame if a soft room bound would be crossed.
D4Warden_MoveBounded:
{
  LDA.w SprX, X : PHA
  LDA.w SprY, X : PHA
  JSL Sprite_Move
  LDA.w SprX, X : CMP.b #$30 : BCC .blocked
  CMP.b #$D1 : BCS .blocked
  LDA.w SprY, X : CMP.b #$50 : BCC .blocked
  CMP.b #$D1 : BCS .blocked
  PLA : PLA
  CLC : RTS
  .blocked
  PLA : STA.w SprY, X
  PLA : STA.w SprX, X
  SEC : RTS
}

; Existing24x24box centered on the anchor beside the boot. The actor is
; bounded away from low-byte wrap; restore body position/hitbox immediately.
D4Warden_AnchorDamage:
{
  LDA.w SprX, X : PHA
  LDA.w SprY, X : PHA
  LDY.w SprMiscC, X
  LDA.w SprX, X : CLC : ADC .dx, Y : STA.w SprX, X
  LDA.w SprY, X : CLC : ADC.b #$0B : STA.w SprY, X
  LDA.b #$09 : STA.w SprHitbox, X
  JSL Sprite_CheckDamageToPlayerSameLayer
  LDA.b #$07 : STA.w SprHitbox, X
  PLA : STA.w SprY, X
  PLA : STA.w SprX, X
  RTS
  .dx
  db 9,-9,-14,14
}

; One assist at half HP extends a vent to112f. Sprite presence is checked
; directly because the protector may be in the offscreen rescue quadrant.
D4Warden_TryValveAssist:
{
  LDA.w SprMiscD, X : BNE .done
  LDA.w SprHealth, X : CMP.b #$0D : BCS .done
  PHX
  LDX.b #$0F
  .scan
  LDA.w SprState, X : CMP.b #$09 : BNE .next
  LDA.w SprType, X : CMP.b #$B8 : BNE .next
  LDA.w SprSubtype, X : CMP.b #$02 : BNE .next
  LDA.b #$01 : STA.w SprMiscA, X
  LDA.b #$30 : STA.w SprTimerB, X
  PLX
  LDA.b #$01 : STA.w SprMiscD, X
  LDA.b #$70 : STA.w SprTimerA, X
  LDA.b #$05 : JSL SpriteSFX_QueueSFX2WithPan
  RTS
  .next
  DEX : BPL .scan
  PLX
  .done
  RTS
}

; Write only colours1..7 in lower OBJ rows3–6, both source/display buffers.
D4Zora_LoadPalettes:
{
  PHX
  REP #$20
  LDX.b #$0C
  .next
  LDA.l D4Zora_Palette_protector_head, X
  STA.l $7EC462, X : STA.l $7EC662, X
  LDA.l D4Zora_Palette_protector_body, X
  STA.l $7EC482, X : STA.l $7EC682, X
  LDA.l D4Zora_Palette_warden_armor, X
  STA.l $7EC4A2, X : STA.l $7EC6A2, X
  LDA.l D4Zora_Palette_warden_iron, X
  STA.l $7EC4C2, X : STA.l $7EC6C2, X
  DEX : DEX : BPL .next
  SEP #$20
  INC.b $15
  PLX
  RTS
}

; M/X=8 entry/exit. $06..08=long pointer; $09=record offset;
; $0A=signedY; $0B/C=sign-extended offset; $0D=remaining pieces.
D4Zora_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer
  PHX
  LDA.w SprFrame, X : TAX
  LDA.l D4Zora_FrameCounts, X : STA $0D
  TXA : ASL : TAX
  REP #$20
  LDA.l D4Zora_FramePointers, X : STA $06
  SEP #$20
  LDA.b #!D4Zora_FrameBank : STA $08
  STZ $09
  LDY.b #$00
  .next
  PHY
  LDY $09
  LDA [$06], Y : STA $0B
  INY : LDA [$06], Y : STA $0A
  INY : LDA [$06], Y : STA $04
  INY : LDA [$06], Y : STA $05
  INY : STY $09
  PLY
  STZ $0C
  LDA $0B : BPL .positive_x
  DEC $0C
  .positive_x
  REP #$20
  LDA $00 : CLC : ADC $0B : STA ($90), Y
  AND.w #$0100 : STA $0E
  SEP #$20
  INY
  LDA $0A : STA $0B
  STZ $0C
  LDA $0A : BPL .positive_y
  DEC $0C
  .positive_y
  REP #$20
  LDA $02 : CLC : ADC $0B : STA ($90), Y
  CLC : ADC.w #$0010 : CMP.w #$0100
  SEP #$20
  BCC .visible
  LDA.b #$F0 : STA ($90), Y
  .visible
  INY : LDA $04 : STA ($90), Y
  INY : LDA $05 : STA ($90), Y
  PHY
  TYA : LSR #2 : TAY
  LDA.b #$02 : ORA $0F : STA ($92), Y
  PLY : INY
  DEC $0D : BNE .next
  PLX
  RTS
}
D4Zora_CodeEnd:
