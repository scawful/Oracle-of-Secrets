; Private D4: $11 subtype3 warden, $B8 subtype2 protector/3 living Princess.
; No dialogue/new SRAM. Room46 tag0A opens shutters after normal enemy death.
; Warden death sets room46 boss-defeated bit (word $7EF08C bit11=$0403 bit7),
; so it stays gone after the four-room dead-sprite list forgets room46.
; Warden A=gait,B=attack choice,C=facing R/L/D/U,D=valve-used latch.
; Protector A=valve latch,TimerB=gesture; Action=Healing only.
D4Zora_CodeStart:
incsrc "Core/Generated/d4_zora_sprite_sheets/frame_tables.asm"

; Reuse the native room-entry cache boundary after stairs and doors. A spiral
; stair from the tall basin can retain a scroll offset outside room46's small
; vertical view. The next door scroll then ends before Link crosses quadrants.
; This file is included only with ENABLE_D4_ZORA_REDESIGN; flag0 leaves the
; original eight bytes untouched. Other rooms replay the original cache code.
pushpc
org $028D81 ; @hook module=Dungeons name=D4Zora_CacheRoomCamera kind=jsl target=D4Zora_CacheRoomCamera expected_m=8 expected_x=8 expected_exit_m=16 expected_exit_x=8 protected_size=8
  assert read4($028D81) == $E2A520C2, "D4 camera cache preimage changed"
  assert read4($028D85) == $7EC1808F, "D4 camera cache store preimage changed"
  JSL D4Zora_CacheRoomCamera
  NOP #4
assert pc() == $028D89

; Follower_BasicMover has already reset its timed-message counter and stored
; TEXTID. Its PHY/PLY remain outside this four-byte call. Entry/exit M8/X8,
; DBR=$09 and D=0; pass-through tail-calls the original interface routine.
org $09A01F ; @hook module=Sprites name=D4Zora_FilterBabyReminder kind=jsl target=D4Zora_FilterBabyReminder expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=4
  assert read4($09A01F) == $0FFDAA22, "D4 timed follower message preimage changed"
  JSL D4Zora_FilterBabyReminder
assert pc() == $09A023
pullpc

D4Zora_CacheRoomCamera:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  LDA.l $7E00A0 : CMP.w #$0046 : BNE .restore
  LDA.l $7E040E : AND.w #$001F : CMP.w #$0014 : BNE .restore
  ; Preserve the vanilla scratch word. No Link/actor/progression writes.
  LDA.l $7E0000 : PHA
  LDA.l $7E00A7 : AND.w #$00FF : BNE .horizontal
  LDA.l $7E00E8 : CMP.l $7E0600 : BCC .vertical_min
  CMP.l $7E0604 : BCC .horizontal
  BEQ .horizontal
  LDA.l $7E0604 : BRA .vertical_shift
  .vertical_min
  LDA.l $7E0600
  .vertical_shift
  SEC : SBC.l $7E00E8 : STA.l $7E0000
  JSR .shift_vertical
  .horizontal
  LDA.l $7E00A6 : AND.w #$00FF : BNE .scratch_done
  LDA.l $7E00E2 : CMP.l $7E0608 : BCC .horizontal_min
  CMP.l $7E060C : BCC .scratch_done
  BEQ .scratch_done
  LDA.l $7E060C : BRA .horizontal_shift
  .horizontal_min
  LDA.l $7E0608
  .horizontal_shift
  SEC : SBC.l $7E00E2 : STA.l $7E0000
  JSR .shift_horizontal
  .scratch_done
  PLA : STA.l $7E0000
  .restore
  PLY : PLX : PLA : PLP
  ; Exact displaced REP/LDA/STA; vanilla continues caching Link and bounds.
  REP #$20
  LDA.b $E2 : STA.l $7EC180
  RTL

  .shift_vertical
  LDA.l $7E0000 : CLC : ADC.l $7E00E8 : STA.l $7E00E8
  LDA.l $7E0000 : CLC : ADC.l $7E00E6 : STA.l $7E00E6
  LDA.l $7E0000 : CLC : ADC.l $7E0122 : STA.l $7E0122
  LDA.l $7E0000 : CLC : ADC.l $7E0124 : STA.l $7E0124
  LDA.l $7E0000 : CLC : ADC.l $7E0618 : STA.l $7E0618
  LDA.l $7E0000 : CLC : ADC.l $7E061A : STA.l $7E061A
  RTS

  .shift_horizontal
  LDA.l $7E0000 : CLC : ADC.l $7E00E2 : STA.l $7E00E2
  LDA.l $7E0000 : CLC : ADC.l $7E00E0 : STA.l $7E00E0
  LDA.l $7E0000 : CLC : ADC.l $7E011E : STA.l $7E011E
  LDA.l $7E0000 : CLC : ADC.l $7E0120 : STA.l $7E0120
  LDA.l $7E0000 : CLC : ADC.l $7E061C : STA.l $7E061C
  LDA.l $7E0000 : CLC : ADC.l $7E061E : STA.l $7E061E
  RTS
}

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
  STZ.w SprMiscG, X
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
  JSR D4Zora_PrincessMain
  BRA .done
  .protector
  LDA.b #!D4Zora_Frame_protector_rest : STA.w SprFrame, X
  LDA.w SprTimerB, X : BEQ .healing_frame
  LDA.b #!D4Zora_Frame_protector_idle_side : STA.w SprFrame, X
  .healing_frame
  LDA.w SprAction, X : CMP.b #$01 : BNE .draw
  LDA.b #!D4Zora_Frame_protector_healing : STA.w SprFrame, X
  .draw
  JSR D4Zora_RefreshPalettesOnce
  JSR D4Zora_Draw
  JSL Sprite_CheckActive : BCC .done
  JSR D4Zora_ProtectorMain
  .done
  PLB : RTL
}

D4Zora_PrincessMain:
{
  JSL Sprite_PlayerCantPassThrough
  ; The living Princess can introduce herself after the rescue. Never enter
  ; her legacy Healing/Mask actions or show the soul-freed message ($C6).
  ; As with the protector, a warden death poof still blocks this interaction.
  PHX
  LDX.b #$0F
  .scan
  LDA.w SprState, X : BEQ .next
  LDA.w SprType, X : CMP.b #$11 : BNE .next
  LDA.w SprSubtype, X : CMP.b #$03 : BEQ .blocked
  .next
  DEX : BPL .scan
  PLX
  %ShowSolicitedMessage($0C5)
  RTS
  .blocked
  PLX
  RTS
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
  STZ.w SprMiscG, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  LDA.b #$02 : STA.w SprMiscC, X
  LDA.b #!D4Zora_Frame_front_walk_0 : STA.w SprFrame, X
  LDA.l $7EF302 : BNE .cleared
  LDA.w $0403 : BPL .done
  .cleared
  STZ.w SprState, X
  .done
  PLB : RTL
}

D4Warden_Long:
{
  PHB : PHK : PLB
  LDA.w SprState, X : CMP.b #$06 : BNE .alive
  ; Native room exit copies $0403 to SRAM; Save and Quit in room does not.
  %SetBossDefeated()
  LDA.l $7EF08D : ORA.b #$08 : STA.l $7EF08D
  BRA .done
  .alive
  JSR D4Zora_RefreshPalettesOnce
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

; Write colours1..7 in lower OBJ rows3–6. During room loading/fades, vanilla
; builds C6 display colours additively from C4 targets. Filling both early
; doubles each colour on the natural spiral-stair fade-in. Ordinary-play
; sprite preparation still needs an immediate display update.
D4Zora_LoadPalettes:
{
  PHX
  REP #$20
  LDX.b #$0C
  .next
  LDA.l D4Zora_Palette_protector_head, X
  STA.l $7EC462, X
  LDA.l D4Zora_Palette_protector_body, X
  STA.l $7EC482, X
  LDA.l D4Zora_Palette_warden_armor, X
  STA.l $7EC4A2, X
  LDA.l D4Zora_Palette_warden_iron, X
  STA.l $7EC4C2, X
  DEX : DEX : BPL .next
  SEP #$20
  LDA.l $7E0010 : CMP.b #$07 : BNE .done
  LDA.l $7E0011 : BNE .done
  REP #$20
  LDX.b #$0C
  .display
  LDA.l D4Zora_Palette_protector_head, X : STA.l $7EC662, X
  LDA.l D4Zora_Palette_protector_body, X : STA.l $7EC682, X
  LDA.l D4Zora_Palette_warden_armor, X : STA.l $7EC6A2, X
  LDA.l D4Zora_Palette_warden_iron, X : STA.l $7EC6C2, X
  DEX : DEX : BPL .display
  SEP #$20
  .done
  INC.b $15
  PLX
  RTS
}

; Room46 entry rebuilds rows3–6 after sprite preparation, as in refuge105.
; Rebind once in ordinary active gameplay. SprMiscG is cleared by both preps.
D4Zora_RefreshPalettesOnce:
{
  LDA.w SprMiscG, X : BNE .done
  JSL Sprite_CheckActive : BCC .done
  JSR D4Zora_LoadPalettes
  INC.w SprMiscG, X
  .done
  RTS
}

; M/X=8 entry/exit. $06..08=long pointer; $09=record offset;
; $0A=signedY; $0B/C=sign-extended offset; $0D=remaining pieces.
D4Zora_Draw:
{
  JSL Sprite_PrepOamCoord
  ; Region B's player-defer fallback has only two safe entries at $01F8.
  ; This body needs up to15: reserve from large Region A so size/X9 writes
  ; remain below $0AA0 (graphics state and the Zora dive flag follow OAM).
  LDA.w SprNbrOAM, X : AND.b #$1F : INC A : ASL #2
  JSL OAM_AllocateFromRegionA
  PHX
  LDA.w SprFrame, X : TAX
  LDA.l D4Zora_FrameCounts, X : STA $0D
  TXA : ASL : TAX
  REP #$20
  LDA.l D4Zora_FramePointers, X : STA $06
  SEP #$20
  LDA.b #!D4Zora_FrameBank : STA $08
  ; Shared record loop also draws the two-piece refuge River NPC. Both
  ; entries have already reserved OAM and pushed the original sprite X.
D4Zora_DrawEntries:
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
; Filter only Baby09's timed108 reminder. Keep the follower and native timer,
; carry/throw/switch paths untouched. No new rescue flag or dialogue is needed.
D4Zora_FilterBabyReminder:
{
  PHP : PHA : PHX : PHY
  LDA.l $7EF3CC : CMP.b #$09 : BNE .display
  LDA.l $7E1CF0 : CMP.b #$08 : BNE .display
  LDA.l $7E1CF1 : CMP.b #$01 : BNE .display
  LDA.l $7EF302 : AND.b #$01 : BNE .suppress
  LDA.l $7E00A0 : CMP.b #$46 : BNE .display
  LDA.l $7E00A1 : BNE .display

  LDY.b #$00
  LDX.b #$0F
  .scan
  LDA.l $7E0DD0, X : BEQ .next
  LDA.l $7E0E20, X : CMP.b #$11 : BEQ .warden
  CMP.b #$B8 : BNE .next
  LDA.l $7E0E30, X : CMP.b #$03 : BNE .next
  LDA.l $7E0DD0, X : CMP.b #$09 : BNE .next
  LDY.b #$01
  BRA .next
  .warden
  ; Include state6 death poof, matching the protector's Healing gate.
  LDA.l $7E0E30, X : CMP.b #$03 : BEQ .display
  .next
  DEX : BPL .scan
  CPY.b #$01 : BEQ .suppress

  .display
  PLY : PLX : PLA : PLP
  JML Interface_PrepAndDisplayMessage
  .suppress
  PLY : PLX : PLA : PLP
  RTL
}
; Peaceful refuge roles are explicit B8 subtypes, separate from the legacy
; room105 Princess and the room46 protector/Princess. M/X=8 throughout.
D4Refuge_IsActor:
{
  LDA.w ROOM : CMP.b #$05 : BNE .no
  LDA.w ROOM+1 : CMP.b #$01 : BNE .no
  LDA.w SprSubtype, X : CMP.b #$04 : BCC .no
  CMP.b #$07 : BCS .no
  SEC : RTL
  .no
  CLC : RTL
}

D4Refuge_Prep:
{
  PHB : PHK : PLB
  JSR D4Zora_LoadPalettes
  LDA.b #$81 : STA.w SprNbrOAM, X
  ; Match ordinary talkable NPCs (Bean Vendor): the inherited Princess
  ; box02 leaves a gap at the barrier when approached from above.
  LDA.b #$43 : STA.w SprHitbox, X
  STZ.w SprDefl, X
  STZ.w SprTileDie, X
  STZ.w SprAction, X
  STZ.w SprFrame, X
  STZ.w SprMiscA, X
  STZ.w $0DC0, X
  PLB : RTL
}

D4Refuge_Long:
{
  PHB : PHK : PLB
  LDA.w SprSubtype, X : CMP.b #$04 : BNE .sea
  ; Cave entry rebuilds the display palette after sprite preparation. Wait
  ; for ordinary active gameplay, then bind the River colours once.
  LDA.w SprMiscA, X : BNE .river_draw
  JSL Sprite_CheckActive : BCC .river_draw
  JSR D4Zora_LoadPalettes
  LDA.b #$01 : STA.w SprMiscA, X
  .river_draw
  JSR D4Refuge_DrawRiver
  BRA .active
  .sea
  JSR Sprite_Zora_Draw
  .active
  JSL Sprite_CheckActive : BCC .done
  JSL Sprite_PlayerCantPassThrough
  JSR D4Refuge_Talk
  .done
  PLB : RTL
}

D4Refuge_Talk:
{
  ; D4 clear takes priority over the earned protector reward. The refuge
  ; only reads progression: it never consumes Healing or changes followers.
  LDA.w SprSubtype, X : SEC : SBC.b #$04
  STA $00
  ASL : CLC : ADC $00 : STA $00
  LDA.l Crystals : AND.b #$20 : BNE .cleared
  LDA.l $7EF302 : BEQ .select
  INC $00
  BRA .select
  .cleared
  INC $00 : INC $00
  .select
  LDY $00
  LDA.w .message_low, Y
  LDY.b #$02
  JSL Sprite_ShowSolicitedMessageIfPlayerFacing
  RTS
  .message_low
  db $11, $12, $13 ; River witness: before Healing / healed / D4 clear
  db $14, $15, $16 ; Sea caretaker
  db $17, $18, $19 ; Sea water keeper
}

D4Refuge_DrawRiver:
{
  JSL Sprite_PrepOamCoord
  LDA.b #$08 : JSL OAM_AllocateFromRegionA
  PHX
  LDA.b #$02 : STA $0D
  REP #$20
  LDA.w #.pieces : STA $06
  SEP #$20
  PHK : PLA : STA $08
  JMP D4Zora_DrawEntries
  .pieces
  db $F8, $F0, $C0, $37
  db $F8, $F8, $C2, $39
}
D4Zora_CodeEnd:
