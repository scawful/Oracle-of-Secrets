; Park-anywhere helpers. Included from Sprites/NPCs/horse.asm after HorseNpc_End
; so horse_form.asm stays under $53D000. Assembled only when park flag is on.
; Local mirrors of horse_form.asm constants (sprites assemble before masks).
!HorsePark_SpriteId    = $2D
!HorsePark_DefaultNpcX = $01C0
!HorsePark_DefaultNpcY = $0294

; Write Link outdoor XY + $8A into the park anchor. M=8,X=8,DBR=$00.
HorseForm_SaveOutdoorAnchor_Long:
{
  PHP
  REP #$20
  LDA.b $22 : STA.l Horse_AnchorX
  LDA.b $20 : STA.l Horse_AnchorY
  SEP #$20
  LDA.b $8A : STA.l Horse_AnchorArea
  LDA.b #$01 : STA.l Horse_HasAnchor
  PLP
  RTL
}

; Spawn parked Epona on Horse_AnchorArea, or Ranch-default when no park.
; Same call site as HorseForm_MaintainRanchNpc (unmounted FrameTick).
HorseForm_MaintainParkedNpc_Long:
{
  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB

  LDA.b $1B : BEQ + : BRL .leave_keep_or_clear : +
  LDA.b $10 : CMP.b #$09 : BEQ + : PLB : PLP : RTL : +
  LDA.b $11 : BEQ + : PLB : PLP : RTL : +
  LDA.w $0FFC : BEQ + : PLB : PLP : RTL : +

  LDA.l Horse_HasAnchor : BEQ .ranch_default
  LDA.b $8A : CMP.l Horse_AnchorArea : BEQ + : BRL .leave_keep_park : +
  ; On parked map: Ranch uses sheet/actor gates; off-Ranch uses SlotsBusy only.
  LDA.b $8A : BNE .off_ranch_gates
  JSL Horse_RanchProfileReady : BCS + : PLB : PLP : RTL : +
  JSL Horse_RanchActorsSafe : BCS + : PLB : PLP : RTL : +
  BRA .spawn_scan
  .off_ranch_gates
  JSL Horse_SlotsBusy : BCC + : PLB : PLP : RTL : +
  BRA .spawn_scan

  .ranch_default
  LDA.b $8A : BEQ + : BRL .leave_clear : +
  JSL Horse_RanchProfileReady : BCS + : PLB : PLP : RTL : +
  JSL Horse_RanchActorsSafe : BCS + : PLB : PLP : RTL : +

  .spawn_scan
  PHX : PHY
  %m8()
  LDX.b #$0F
  .scan
    LDA.w $0DD0, X : BEQ .next_slot
    LDA.w $0E20, X : CMP.b #!HorsePark_SpriteId : BEQ .found
  .next_slot
    DEX : BPL .scan

  LDX.b #$00
  LDA.b #!HorsePark_SpriteId : JSL Sprite_SpawnDynamically : BMI .spawn_failed
  LDA.l Horse_HasAnchor : BEQ .use_default_pos
    REP #$20
    LDA.l Horse_AnchorX : STA.b $00
    LDA.l Horse_AnchorY : STA.b $02
    SEP #$20
    BRA .set_coords
  .use_default_pos
    REP #$20
    LDA.w #!HorsePark_DefaultNpcX : STA.b $00
    LDA.w #!HorsePark_DefaultNpcY : STA.b $02
    SEP #$20
  .set_coords
  LDA.b $00 : STA.w SprX, Y
  LDA.b $01 : STA.w SprXH, Y
  LDA.b $02 : STA.w SprY, Y
  LDA.b $03 : STA.w SprYH, Y
  LDA.b #$00
  STA.w $0F20, Y : STA.w $0F70, Y : STA.w $0DE0, Y
  STA.w $0E30, Y : STA.w $0E80, Y
  STA.w SprAction, Y : STA.w SprFrame, Y
  LDA.b #$01 : STA.l Horse_NpcActive : STA.w SprBulletproof, Y
  LDA.b #14  : STA.l Horse_NpcFrame
  LDA.b #$FF : STA.l Horse_NpcUploadedFrame
  JSL Horse_LoadNpcPalette
  BRA .done_scan

  .found
  LDA.b #$01 : STA.l Horse_NpcActive
  BRA .done_scan

  .spawn_failed
  LDA.b #$00 : STA.l Horse_NpcActive

  .done_scan
  PLY : PLX
  PLB : PLP
  RTL

  ; Left parked map: despawn NPC, keep WRAM park for return.
  .leave_keep_park
  LDA.l Horse_NpcActive : BEQ +
    JSL Horse_RestoreSp3Palette
  +
  LDA.b #$00 : STA.l Horse_NpcActive
  PLB : PLP
  RTL

  ; Indoor or no-park leave: clear park when indoors / leaving Ranch default.
  .leave_keep_or_clear
  LDA.l Horse_HasAnchor : BNE .leave_keep_park
  .leave_clear
  LDA.l Horse_NpcActive : BEQ +
    JSL Horse_RestoreSp3Palette
  +
  LDA.b #$00 : STA.l Horse_HasAnchor : STA.l Horse_NpcActive : STA.l Horse_AnchorArea
  PLB : PLP
  RTL
}

; ---------------------------------------------------------
; Off-Ranch NPC cells. The Ranch path restores Epona's cells from ROM Ranch
; data; elsewhere the native page1 chars $00-$1F (VRAM $5000-$51FF) are
; copied to Horse_OffBuf, Epona's cells go in, and the copy goes back when
; she is no longer wanted or another actor draws from those chars.
; ---------------------------------------------------------

; Main loop $008056: Module_MainRouting, then scan the finished OAM buffer.
; Any visible page1 entry with char < $20 that is not Epona ($37 attributes)
; resets Horse_OffClear and hides Epona's entries this frame; the NMI then
; restores the native cells. Registers, widths and DBR preserved.
Horse_FrameEndScan:
{
  JSL $0080B5 ; Module_MainRouting
  PHP : PHB
  REP #$30 : PHA : PHX
  SEP #$20
  LDA.b #$00 : PHA : PLB
  LDA.b $10 : CMP.b #$09 : BNE .reset
  LDA.b $1B : BNE .reset
  REP #$20 : LDA.l Horse_Marker : CMP.w #$4852 : SEP #$20 : BNE .reset
  LDA.l Horse_NpcActive : BEQ .reset
  JSL Horse_RanchProfileReady : BCS .reset
  LDX.w #$01FC
  .scan
    LDA.w $0801, X : CMP.b #$F0 : BEQ .next
    LDA.w $0803, X : LSR : BCC .next              ; page0
    LDA.w $0803, X : AND.b #$3F : CMP.b #$37 : BEQ .next ; Epona (any flip)
    LDA.w $0802, X : CMP.b #$20 : BCC .conflict
    .next
    DEX #4 : BPL .scan
  LDA.l Horse_OffClear : INC : BEQ .done          ; saturate at $FF
  STA.l Horse_OffClear
  BRA .done
  .conflict
  LDX.w #$01FC
  .hide
    LDA.w $0803, X : AND.b #$3F : CMP.b #$37 : BNE .hide_next
    LDA.w $0802, X : CMP.b #$20 : BCS .hide_next
    LDA.b #$F0 : STA.w $0801, X
    .hide_next
    DEX #4 : BPL .hide
  .reset
  LDA.b #$00 : STA.l Horse_OffClear
  .done
  REP #$30 : PLX : PLA
  PLB : PLP
  RTL
}

; NMI, from Horse_NmiUpload .npc when the Ranch profile is not loaded.
; M8/X16, DBR $00. C=1: upload Horse_NpcFrame now (.npc_rows). C=0: done.
; The copy (1KB read) and the upload use separate NMIs for vblank budget.
Horse_OffRanchNpc:
{
  BRA .gates
  .unwant                                         ; kept within branch range of the gates
  JSL Horse_OffRestore
  LDA.b #$FF : STA.l Horse_NpcUploadedFrame
  CLC : RTL

  .gates
  LDA.b $10 : CMP.b #$09 : BNE .unwant
  LDA.b $11 : BNE .unwant
  LDA.b $1B : BNE .unwant
  LDA.l Horse_NpcActive : BEQ .unwant
  LDA.w $02B2 : CMP.b #$09 : BEQ .unwant          ; horse mask on
  LDA.l Horse_HasAnchor : BEQ .unwant
  LDA.b $8A : CMP.l Horse_AnchorArea : BNE .unwant
  JSL Horse_SlotsBusy : BCS .unwant
  LDA.l Horse_OffClear : CMP.b #$02 : BCC .unwant
  LDA.l Horse_NpcFrame : CMP.b #14 : BEQ +
    CMP.b #15 : BNE .unwant
  +
  LDA.l $7EC2FC : CMP.l Horse_OffSheet : BNE .save
  LDA.l Horse_OffState : CMP.b #$A2 : BEQ .uploaded
  CMP.b #$A1 : BNE .save
  LDA.b #$A2 : STA.l Horse_OffState
  LDA.b #$FF : STA.l Horse_NpcUploadedFrame
  .uploaded
  LDA.l Horse_NpcFrame : CMP.l Horse_NpcUploadedFrame : BEQ .none
  SEC : RTL

  .save
  LDA.b #$81 : STA.w $4300                        ; B->A, $2139/$213A
  LDA.b #$39 : STA.w $4301
  ; A VRAM read returns the first word twice (the latch reloads before the
  ; address increments), so read $0402 bytes and drop the leading word.
  LDX.w #Horse_OffDma : STX.w $4302
  LDA.b #Horse_OffDma>>16 : STA.w $4304
  LDX.w #$0402 : STX.w $4305
  LDX.w #$5000 : STX.w $2116                      ; address write prefetches
  LDA.b #$01 : STA.w $420B
  STA.w $4300                                     ; native DMA0: A->B, $2118/9
  LDA.b #$18 : STA.w $4301
  LDA.b #$7E : STA.w $4304
  LDA.l $7EC2FC : STA.l Horse_OffSheet
  LDA.b #$A1 : STA.l Horse_OffState
  LDA.b #$FF : STA.l Horse_NpcUploadedFrame
  .none
  CLC : RTL
}

; NMI, M8/X16. Write the copy back if Epona's cells are in VRAM and slot
; $7EC2FC still holds the copied sheet (a reload already replaced them).
Horse_OffRestore:
{
  LDA.l Horse_OffState : CMP.b #$A2 : BNE .clear
  LDA.l $7EC2FC : CMP.l Horse_OffSheet : BNE .clear
  LDX.w #Horse_OffBuf : STX.w $4302
  LDA.b #Horse_OffBuf>>16 : STA.w $4304
  LDX.w #$0400 : STX.w $4305
  LDX.w #$5000 : STX.w $2116
  LDA.b #$01 : STA.w $420B
  LDA.b #$7E : STA.w $4304
  .clear
  LDA.b #$00 : STA.l Horse_OffState
  RTL
}

if !ENABLE_EPONA_SONG == 1
; Epona's Song call (decisions.org 2026-11-16 "Epona's Song calls Epona").
; Moves the park anchor beside Link and drops a live Epona; the next
; HorseForm_MaintainParkedNpc_Long tick respawns her there.
; Out: C=1 called, C=0 refused (nothing changed). Any M/X/DBR in; A/X/Y,
; P widths, DBR and DP $04/$08/$0A/$0C/$0E preserved.
HorseCall_Long:
{
  PHP : PHB
  REP #$30
  PHA : PHX : PHY
  LDA.b $04 : PHA
  LDA.b $08 : PHA
  LDA.b $0A : PHA
  LDA.b $0C : PHA
  LDA.b $0E : PHA
  SEP #$30
  LDA.b #$00 : PHA : PLB

  ; Outdoors, Light World, normal play, on foot, not swimming, Epona unlocked.
  LDA.b $1B : BNE .refuse_near
  LDA.b $10 : CMP.b #$09 : BNE .refuse_near
  LDA.b $11 : BNE .refuse_near
  LDA.b $8A : CMP.b #$40 : BCS .refuse_near
  LDA.w $02B2 : CMP.b #$09 : BEQ .refuse_near
  LDA.b $5D : CMP.b #$04 : BEQ .refuse_near
  LDA.l $7EF3D8 : AND.b #$01 : BEQ .refuse_near
  JSL Horse_SlotsBusy : BCS .refuse_near
  BRA .gates_ok
  .refuse_near
  BRL .refuse
  .gates_ok

  LDX.b #$00
  .candidate
    REP #$20
    LDA.b $22 : CLC : ADC.l .cand_dx, X : STA.b $08
    LDA.b $20 : CLC : ADC.l .cand_dy, X : STA.b $0E
    ; Whole body on screen (camera is clamped to the area, so no wrap reads).
    LDA.b $08 : SEC : SBC.b $E2 : BMI .next
    CMP.w #$0010 : BCC .next
    CMP.w #$00E0 : BCS .next
    LDA.b $0E : SEC : SBC.b $E8 : BMI .next
    CMP.w #$0024 : BCC .next
    CMP.w #$00C8 : BCS .next
    SEP #$20
    PHX
    LDY.b #(.pt_dy-.pt_dx)-2
    .point
      REP #$20
      TYX
      LDA.b $08 : CLC : ADC.l .pt_dx, X : STA.b $0C
      LDA.b $0E : CLC : ADC.l .pt_dy, X : STA.b $0A
      SEP #$20
      JSR Horse_QueryTileAt           ; A = tile type; X/Y kept
      CPY.b #$06 : BCS .body_point
        CMP.b #$58 : BCS .point_fail  ; feet: walkable ground (mount snaps Link here)
        TAX
        LDA.l HorseWalkableAttr, X : BEQ .point_fail
        BRA .point_ok
      .body_point
        CMP.b #$01 : BEQ .point_fail  ; body: no solid tiles
        CMP.b #$02 : BEQ .point_fail
      .point_ok
      DEY : DEY : BPL .point
    PLX
    BRA .accept
    .point_fail
    PLX
  .next
    SEP #$20
    INX : INX : CPX.b #(.cand_dy-.cand_dx) : BCC .candidate

  .refuse
  REP #$30
  PLA : STA.b $0E
  PLA : STA.b $0C
  PLA : STA.b $0A
  PLA : STA.b $08
  PLA : STA.b $04
  PLY : PLX : PLA
  PLB : PLP
  CLC
  RTL

  .accept
  REP #$20
  LDA.b $08 : STA.l Horse_AnchorX
  LDA.b $0E : STA.l Horse_AnchorY
  SEP #$20
  LDA.b $8A : STA.l Horse_AnchorArea
  LDA.b #$01 : STA.l Horse_HasAnchor
  LDX.b #$0F
  .drop
    LDA.w $0DD0, X : BEQ .drop_next
    LDA.w $0E20, X : CMP.b #!HorsePark_SpriteId : BNE .drop_next
    STZ.w $0DD0, X
    .drop_next
    DEX : BPL .drop
  LDA.b #$00 : STA.l Horse_NpcActive
  REP #$30
  PLA : STA.b $0E
  PLA : STA.b $0C
  PLA : STA.b $0A
  PLA : STA.b $08
  PLA : STA.b $04
  PLY : PLX : PLA
  PLB : PLP
  SEC
  RTL

  ; Right, left, below, above Link (Link XY = Epona XY when mounting).
  .cand_dx
  dw $0020, $FFE0, $0000, $0000
  .cand_dy
  dw $0000, $0000, $0018, $FFE0
  ; First 3 = feet (HorseForm_CheckLandingWalkable points), rest = body grid.
  .pt_dx
  dw 4, 11, 8
  dw -8, 8, 24, -8, 8, 24, -8, 8, 24, -8, 8, 24
  .pt_dy
  dw 12, 12, 8
  dw -28, -28, -28, -12, -12, -12, 4, 4, 4, 16, 16, 16
}
endif
