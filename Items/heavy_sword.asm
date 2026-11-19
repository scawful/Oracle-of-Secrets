; Heavy sword = Greatblade, found broken (decisions.org 2026-11-16); name
; and smith text not approved. Broken: Sword level 1. Reforged
; (SwordSlotFlags bit2): level 3. In both states, while the heavy slot is
; equipped: no sword beam, a slower windup, no shield draw and no shield
; block. When reforged, holding B through a spin attack unlocks the balanced
; Hurricane Spin (max 4 extra revs, flat 16/8 MP per rev, half-speed steering,
; and a 45-frame Wind Waker dizzy recovery lock after >= 2 total spins).
; The story blade and broken heavy blade keep vanilla single-spin behavior.
; $7EF35A (shield level) is never written. Assembled in Items bank $2B with
; menu_sword_slots.asm.

!HEAVY_HURRICANE_MAX_REVS     = 4    ; max 4 extra revolutions (5 total spins)
!HEAVY_HURRICANE_COST_NORMAL  = $10  ; 16 MP per extra rev (normal magic)
!HEAVY_HURRICANE_COST_HALF    = $08  ; 8 MP floor (half & quarter magic)
!HEAVY_HURRICANE_DIZZY_FRAMES = $2D  ; 45 frames (~0.75s at 60fps)
!HEAVY_HURRICANE_DIZZY_SFX    = $21  ; SFX2.21 stumble thud ($012E)
!HEAVY_HURRICANE_ERR_SFX      = $3C  ; SFX2.3C out-of-magic error beep ($012E)

; Carry set = heavy slot equipped (bit1) and Sword holds the heavy level
; for its state. Any M/X; keeps A/X/Y and every flag except carry.
HeavySword_Active:
{
  PHP : SEP #$30 : PHA : PHX
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyEquipped : BEQ .no
  LDA.l Sword : TAX
  JSL SwordSlots_IsHeavyLevel : BNE .no
  PLX
  PLA : PLP : SEC
  RTL
.no
  PLX : PLA : PLP : CLC
  RTL
}

; $079C7D, M=8: beam level read. Heavy reports 0, so INC/AND #$FE skips the beam.
HeavySword_BeamLevel:
{
  JSL HeavySword_Active : BCC +
  LDA.b #$00
  RTL
+
  LDA.l Sword
  RTL
}

; $079D21, M/X=8, X = swing step 1-8. Each step lasts timer+1 frames; the
; heavy sword adds 1 frame to windup steps 1-4 (+4 frames per swing).
HeavySword_SwingTimer:
{
  LDA.l $079CBF,X : STA.b $3D
  JSL HeavySword_Active : BCC .done
  CPX.b #$05 : BCS .done
  INC.b $3D
.done
  RTL
}

; $06F18B (projectile block) and $0596CB (fireball block), M=8: shield level
; read. Heavy reports 0 (sets Z) so the shield never blocks.
HeavySword_ShieldLevel:
{
  JSL HeavySword_Active : BCC +
  LDA.b #$00
  RTL
+
  LDA.l $7EF35A
  RTL
}

; Grants the Broken Greatblade (owned, not reforged; plus the initialized
; bit after an old-save sync). Not wired to the smith's partner: the text is
; a draft. Any M/X; keeps A/X/Y.
HeavySword_GrantBroken:
{
  PHP : SEP #$30 : PHA
  LDA.l SwordSlotFlags : BMI +
  JSL SwordSlots_Sync
+
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyReforged^$FF
  ORA.b #!SwordSlot_HeavyOwned|!SwordSlot_Initialized
  STA.l SwordSlotFlags
  PLA : PLP
  RTL
}

; The smiths reforge the Greatblade: sets the reforged bit and, while the
; heavy slot is equipped, raises Sword to the reforged level and reloads its
; tiles/palette. Not wired to the smiths. Any M/X, DP=$0000; keeps A/X/Y.
HeavySword_Reforge:
{
  PHP : SEP #$30 : PHA : PHX : PHY
  LDA.l SwordSlotFlags : BMI +
  JSL SwordSlots_Sync
+
  LDA.l SwordSlotFlags
  ORA.b #!SwordSlot_HeavyOwned|!SwordSlot_HeavyReforged|!SwordSlot_Initialized
  STA.l SwordSlotFlags
  AND.b #!SwordSlot_HeavyEquipped : BEQ +
  LDA.b #!HEAVY_SWORD_LEVEL : STA.l Sword
  JSL SwordSlots_ExitReload
  LDA.b #$01 : STA.b $15              ; upload the new sword palette at NMI
+
  PLY : PLX : PLA : PLP
  RTL
}

; Carry set = Reforged Heavy Sword (Goronblade) is actively equipped.
; Broken Heavy Blade (!SwordSlot_HeavyReforged == 0) and Story Blade return CLC.
; Any M/X; keeps A/X/Y and every flag except carry.
HeavySword_ReforgedActive:
{
  JSL HeavySword_Active : BCC .no
  PHP : SEP #$20 : PHA
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyReforged : BEQ .no_pop
  PLA : PLP : SEC
  RTL
.no_pop
  PLA : PLP
.no
  CLC
  RTL
}

; $07:A8CA, M/X=8, DBR=$07: replaces LDA #$00 : STA $5D at end of LinkState_SpinAttack.
; Continues Hurricane Spin while holding B with Reforged Heavy Sword equipped, up to
; 4 extra revolutions at a flat 16 MP (normal) or 8 MP (half/quarter) magic cost.
; Ending after >= 1 extra rev (>= 2 total spins) triggers a 45-frame dizzy lock.
HeavySword_HurricaneEndCheck:
{
  LDA.b $5D : CMP.b #$03 : BEQ .is_spin
  ; Non-spin state ($1E victory spin -> $00; collision transitions like pit $01 /
  ; swim $04 / ledge $0B-$0E keep their new $5D). Always clear Hurricane flags.
  PHA
  LDA.b #$00
  STA.l HeavySword_HurricaneActive
  STA.l HeavySword_HurricaneRevs
  PLA
  CMP.b #$1E : BNE .keep_other_state
  LDA.b #$00 : STA.b $5D
.keep_other_state
  RTL

.is_spin
  JSL HeavySword_ReforgedActive : BCC .end_spin

  ; Must still hold B without Y/Select/Start ($F0 & $F0 == $80).
  LDA.b $F0 : AND.b #$F0 : CMP.b #$80 : BNE .end_spin

  ; Deep water transitions cleanly into swim state (skip grounded dizzy lock).
  LDA.w $0341 : CMP.b #$01 : BEQ .enter_swim

  ; Abort on invincibility/bonk ($037B != 0), ledge-hop countdown ($0375 != $13), or recoil ($4D != 0).
  LDA.w $037B : BNE .end_spin
  LDA.w $0375 : CMP.b #$13 : BNE .end_spin
  LDA.b $4D : BNE .end_spin

  ; Cap at 4 extra Hurricane revolutions (5 total spins max).
  LDA.l HeavySword_HurricaneRevs
  CMP.b #!HEAVY_HURRICANE_MAX_REVS : BCS .end_spin

  ; Flat magic cost: 16 MP normal ($7EF37B == 0), capped at 8 MP for half/quarter ($7EF37B >= 1).
  LDA.l $7EF37B : BEQ .normal_cost
  LDA.b #!HEAVY_HURRICANE_COST_HALF
  BRA .have_cost
.normal_cost
  LDA.b #!HEAVY_HURRICANE_COST_NORMAL
.have_cost
  STA.b $00
  LDA.l $7EF36E
  SEC : SBC.b $00
  BCS .has_magic
    LDA.b #!HEAVY_HURRICANE_ERR_SFX : STA.w $012E
    BRA .end_spin_keep_sfx

.has_magic
  STA.l $7EF36E
  LDA.l HeavySword_HurricaneRevs : INC A : STA.l HeavySword_HurricaneRevs
  LDA.b #$01 : STA.l HeavySword_HurricaneActive
  LDA.b #$03 : STA.b $5D
  LDA.b #$90 : STA.b $3C              ; re-arm spin attack flag for next rev
  LDA.b #$01 : TSB.b $50              ; keep facing-lock bit across continuation
  LDA.b #$80 : STA.b $3A              ; keep B-button latch across continuation
  RTL

.enter_swim
  LDA.b #$00
  STA.l HeavySword_HurricaneActive
  STA.l HeavySword_HurricaneRevs
  LDA.b #$04 : STA.b $5D
  RTL

.end_spin
  LDA.b #$00 : STA.l HeavySword_HurricaneActive
  LDA.l HeavySword_HurricaneRevs : BEQ .no_dizzy
  LDA.b #$00 : STA.l HeavySword_HurricaneRevs
  LDA.b #!HEAVY_HURRICANE_DIZZY_FRAMES : STA.l HeavySword_DizzyTimer
  LDA.b #!HEAVY_HURRICANE_DIZZY_SFX : STA.w $012E
  BRA .no_dizzy

.end_spin_keep_sfx
  LDA.b #$00 : STA.l HeavySword_HurricaneActive
  LDA.l HeavySword_HurricaneRevs : BEQ .no_dizzy
  LDA.b #$00 : STA.l HeavySword_HurricaneRevs
  LDA.b #!HEAVY_HURRICANE_DIZZY_FRAMES : STA.l HeavySword_DizzyTimer

.no_dizzy
  LDA.b #$00 : STA.b $5D
  RTL
}

; $07:A879, M/X=8, DBR=$07: replaces STZ $67 : JSL Link_HandleVelocity ($07:E245).
; While Hurricane Spin is active, re-arms $3C = #$90 and steers at half walking
; speed by feeding D-pad ($F0 & #$0F) into $67 + diagonal/tile collision ($07:B64F,
; $07:D077 with Y=0) on alternating frames ($1A bit 0 set). Off frames and normal
; spins zero $67 while still running velocity and sword animation every frame.
HeavySword_HurricaneMove:
{
  LDA.l HeavySword_HurricaneActive : BEQ .normal_spin
  LDA.b #$90 : STA.b $3C
  LDA.b $1A : LSR A : BCC .skip_move
  LDA.b $F0 : AND.b #$0F : STA.b $67
  ; Invoke Bank $07 RTS routines via vanilla Link_Main RTL ($07:8020), preserving DBR=$07.
  PHK : PER .after_diag-1
  PEA.w $8020-1
  JML $07B64F                         ; Link_HandleDiagonalCollision
.after_diag
  LDY.b #$00
  PHK : PER .after_tile-1
  PEA.w $8020-1
  JML $07D077                         ; TileDetect_MainHandler (Y=0 center tile)
.after_tile
  JSL $07E245                         ; Link_HandleVelocity
  RTL
.skip_move
.normal_spin
  STZ.b $67
  JSL $07E245                         ; Link_HandleVelocity
  RTL
}

; $07:A882, M/X=8, DBR=$07: replaces LDA #$03 : STA $5D after cardinal collision.
; Keeps $03/$1E for active spins, but preserves state transitions (pit $01, swim $04,
; ice $05, ledge hop $0B-$0E) triggered while steering a Hurricane Spin.
HeavySword_HurricaneKeepState:
{
  LDA.b $5D
  BEQ .keep_spin
  CMP.b #$03 : BEQ .keep_spin
  CMP.b #$1E : BEQ .done
  LDA.b #$00
  STA.l HeavySword_HurricaneActive
  STA.l HeavySword_HurricaneRevs
  LDA.b $50 : AND.b #$FE : STA.b $50
  LDA.b #$80 : STA.b $3A
  RTL
.keep_spin
  LDA.b #$03 : STA.b $5D
.done
  RTL
}

; $07:8102, M/X=8, DBR=$07: replaces LDA $5D : ASL A : TAX before JMP (.vectors,X).
; 1. Keeps Hurricane volatile flags zeroed whenever LinkState ($5D) != $03.
; 2. Runs the 45-frame Wind Waker dizzy recovery lock after Hurricane Spin:
;    - Auto-clears on module/submodule change, damage/recoil, doorway, pit, or non-zero $5D.
;    - Strips movement D-pad and B/Y/A/X/L/R inputs ($F0, $F2, $F4, $F6).
;    - Cycles Link's facing ($2F: 0 -> 4 -> 2 -> 6) every 6 frames.
HeavySword_ControlFrameHook:
{
  LDA.b $5D : CMP.b #$03 : BEQ .in_spin
  LDA.b #$00
  STA.l HeavySword_HurricaneActive
  STA.l HeavySword_HurricaneRevs

  LDA.l HeavySword_DizzyTimer : BEQ .replay
  LDA.b $5D : BNE .clear_dizzy
  LDA.b $10 : CMP.b #$07 : BEQ .mode_ok
  CMP.b #$09 : BNE .clear_dizzy
.mode_ok
  LDA.b $11 : BNE .clear_dizzy        ; screen/room transition
  LDA.b $4D : BNE .clear_dizzy        ; damage recoil
  LDA.w $031F : CMP.b #$3A : BEQ .clear_dizzy ; damage taken this frame
  LDA.b $6C : BNE .clear_dizzy        ; doorway transition
  LDA.b $5B : BNE .clear_dizzy        ; pit fall

  LDA.l HeavySword_DizzyTimer : DEC A : STA.l HeavySword_DizzyTimer

  ; Strip D-pad ($0F) & B/Y ($C0) from $F0/$F4 (keep Start/Select $30),
  ; and strip A/X/L/R ($F0) from $F2/$F6.
  LDA.b $F0 : AND.b #$30 : STA.b $F0
  LDA.b $F4 : AND.b #$30 : STA.b $F4
  LDA.b $F2 : AND.b #$0F : STA.b $F2
  LDA.b $F6 : AND.b #$0F : STA.b $F6

  ; Every 6 frames (timer = 42, 36, 30, 24, 18, 12, 6), wobble facing 0->4->2->6.
  LDA.l HeavySword_DizzyTimer : BEQ .replay
.mod6
  SEC : SBC.b #$06
  BEQ .wobble_dir
  BCS .mod6
  BRA .replay
.wobble_dir
  LDA.b $2F : LSR A : AND.b #$03 : TAX
  LDA.l HeavySword_DizzyNextDir,X
  STA.b $2F
  BRA .replay

.in_spin
.clear_dizzy
  LDA.b #$00 : STA.l HeavySword_DizzyTimer

.replay
  LDA.b $5D : ASL A : TAX
  RTL
}

; Next facing indexed by ($2F >> 1) & 3: Up(0)->Left(4)->Down(2)->Right(6)->Up(0).
HeavySword_DizzyNextDir:
  db $04, $06, $02, $00

pushpc
org $079C7D ; @hook module=Items
  assert read4($079C7D) == $7EF359AF, "HeavySword: $079C7D is not LDA.l $7EF359"
  JSL HeavySword_BeamLevel
org $079D21 ; @hook module=Items
  assert read4($079D21) == $859CBFBD, "HeavySword: $079D21 is not LDA.w SwordSwingTimers,X"
  assert read1($079D25) == $3D, "HeavySword: $079D24 is not STA.b $3D"
  JSL HeavySword_SwingTimer : NOP
org $06F18B ; @hook module=Items
  assert read4($06F18B) == $7EF35AAF, "HeavySword: $06F18B is not LDA.l $7EF35A"
  JSL HeavySword_ShieldLevel
org $0596CB ; @hook module=Items
  assert read4($0596CB) == $7EF35AAF, "HeavySword: $0596CB is not LDA.l $7EF35A"
  JSL HeavySword_ShieldLevel
org $07A879 ; @hook module=Items name=HeavySword_HurricaneMove kind=jsl target=HeavySword_HurricaneMove
  assert read4($07A879) == $45226764, "HeavySword: $07A879 is not STZ $67 : JSL $07E245"
  assert read2($07A87D) == $07E2, "HeavySword: $07A87D is not high bytes of JSL $07E245"
  assert read1($078020) == $6B, "HeavySword: $078020 is not RTL trampoline"
  JSL HeavySword_HurricaneMove
  NOP #2
  assert pc() == $07A87F
org $07A882 ; @hook module=Items name=HeavySword_HurricaneKeepState kind=jsl target=HeavySword_HurricaneKeepState
  assert read4($07A882) == $5D8503A9, "HeavySword: $07A882 is not LDA #$03 : STA $5D"
  JSL HeavySword_HurricaneKeepState
  assert pc() == $07A886
org $07A8CA ; @hook module=Items name=HeavySword_HurricaneEndCheck kind=jsl target=HeavySword_HurricaneEndCheck
  assert read4($07A8CA) == $5D8500A9, "HeavySword: $07A8CA is not LDA #$00 : STA $5D"
  JSL HeavySword_HurricaneEndCheck
  assert pc() == $07A8CE
org $078102 ; @hook module=Items name=HeavySword_ControlFrameHook kind=jsl target=HeavySword_ControlFrameHook
  assert read4($078102) == $AA0A5DA5, "HeavySword: $078102 is not LDA $5D : ASL A : TAX"
  JSL HeavySword_ControlFrameHook
  assert pc() == $078106
pullpc
