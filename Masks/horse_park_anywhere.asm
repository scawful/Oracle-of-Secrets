; Park-anywhere helpers. Included from Sprites/NPCs/horse.asm after HorseNpc_End
; so horse_form.asm stays under $53D000. Assembled only when park flag is on.
; Local mirrors of horse_form.asm constants (sprites assemble before masks).
!HorsePark_SpriteId    = $2D
!HorsePark_DefaultNpcX = $01C0
!HorsePark_DefaultNpcY = $0294

; Returns NPC VRAM frame ID matching Horse_AnchorDir (12=N, 13=S, 14=Side E/W).
HorsePark_NpcFrameFromDir:
{
  LDA.l Horse_AnchorDir
  CMP.b #$08 : BCS .side
  AND.b #$06
  BEQ .north
  CMP.b #$02 : BEQ .south
  .side
  LDA.b #14 : RTS
  .north
  LDA.b #12 : RTS
  .south
  LDA.b #13 : RTS
}

; Write Link outdoor XY + $8A + facing $2F into the park anchor only on settled dry ground.
; M=8,X=8,DBR=$00 (enforces M=8 internally; preserves caller P/X/Y/DBR).
HorseForm_SaveOutdoorAnchor_Long:
{
  PHP
  SEP #$20
  LDA.b $1B : BNE .skip
  LDA.b $10 : CMP.b #$09 : BEQ +
  CMP.b #$0B : BNE .skip
  +
  LDA.b $11 : BNE .skip
  LDA.l Horse_State : BNE .skip
  LDA.b $5D : ORA.b $4D : ORA.b $6C : BNE .skip
  LDA.b $5B : CMP.b #$02 : BCS .skip
  LDA.b $25 : BMI .neg_z
    LDA.b $24 : BNE .skip
    BRA .save
  .neg_z
  LDA.b $24 : CMP.b #$F0 : BCC .skip
  .save
  REP #$20
  LDA.b $22 : STA.l Horse_AnchorX
  LDA.b $20 : STA.l Horse_AnchorY
  SEP #$20
  LDA.b $8A : STA.l Horse_AnchorArea
  LDA.b $2F : AND.b #$06 : STA.l Horse_AnchorDir
  LDA.b #$01 : STA.l Horse_HasAnchor
  .skip
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
  LDA.b $10 : CMP.b #$09 : BEQ +
  CMP.b #$0B : BEQ +
  PLB : PLP : RTL
  +
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
  JSL Horse_ParkedBusy : BCC + : PLB : PLP : RTL : +
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
    LDA.w $0E20, X : CMP.b #!HorsePark_SpriteId : BNE .next_slot
    LDA.w SprMiscA, X : CMP.b #$F1 : BNE .found
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
  JSR HorsePark_NpcFrameFromDir : STA.l Horse_NpcFrame
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

; One OAM entry at <entry>+X: shown, page 1, char < $20, outside Epona's own
; 8-entry OAM allocation [Horse_OffOam..Horse_OffOam+$1F] -> .scan_hit. M8/X8, DBR $00.
macro HorseScanOam(entry)
  LDA.w <entry>+1, X : CMP.b #$F0 : BEQ +
  LDA.w <entry>+3, X : LSR : BCC +                ; page 0
  LDA.w <entry>+2, X : CMP.b #$20 : BCS +
    REP #$20
    LDA.w #<entry> : JSR .check_not_epona
    BCC +
    JMP .scan_hit
  +
endmacro

; Main loop $008056: Module_MainRouting, then scan the finished OAM buffer.
; Any visible page1 entry with char < $20 outside sprite $2D's OAM allocation
; hides Epona's entries this frame and makes her run off (Horse_RunOff); the
; NMI then restores the native cells once. Registers, widths, DBR preserved.
Horse_FrameEndScan:
{
  PHP : SEP #$20 : PHA
  LDA.l $7E0010 : CMP.b #$0E : BEQ +
    LDA.b #$00 : STA.l Horse_OffOam : STA.l Horse_OffOam+1
  +
  PLA : PLP
  JSL $0080B5 ; Module_MainRouting
  PHP : PHB
  REP #$30 : PHA : PHX : PHY
  SEP #$20
  LDA.b #$00 : PHA : PLB
  REP #$20 : LDA.l Horse_Marker : CMP.w #$4852 : SEP #$20 : BNE .reset
  ; Safe Overworld-overlay $0E submodules freeze play and leave sprite VRAM
  ; alone: Epona keeps her cells (Horse_OffRanchNpc .hold), nothing to do.
  LDA.b $10 : CMP.b #$0E : BNE .not_pause
    JSL Horse_IsSafeOverlay : BCS .done
    BRA .leaving
  .not_pause
  CMP.b #$09 : BEQ +
  CMP.b #$0B : BNE .leaving
  +
  LDA.b $1B : ORA.b $11 : BNE .leaving
  LDA.l Horse_NpcActive : BEQ .leaving
  JSL Horse_RanchProfileReady : BCS .reset
  JSR .scan_oam : BCS .conflict
  LDA.l Horse_OffClear : INC : BEQ .done          ; saturate at $FF
  STA.l Horse_OffClear
  BRA .done
  ; Module/submodule changed to a non-overlay state: the coming NMI restores
  ; native cells (off-Ranch or Ranch) while this frame's OAM still has Epona.
  ; Hide Epona's 8 OAM slots before NMI so garbled native tiles never flash!
  .leaving
  LDA.l Horse_OffState : CMP.b #$A2 : BEQ .leaving_hide
  LDA.l Horse_NpcUploadedFrame : CMP.b #$FF : BNE .leaving_hide
    LDA.l Horse_OffClear : ORA.l Horse_OffOam : ORA.l Horse_OffOam+1
    BEQ .done
    BRA .reset
  .leaving_hide
  JSR .hide_epona
  BRA .reset
  ; Another actor draws from her cells: hide her this frame and run off.
  .conflict
  JSR .hide_epona
  JSL Horse_RunOff
  .reset
  LDA.b #$00 : STA.l Horse_OffClear : STA.l Horse_OffOam : STA.l Horse_OffOam+1
  .done
if not(defined("NO_KORL_MOUNT"))
  JSL KORL_FrameEndDockedOam
endif
  REP #$30 : PLY : PLX : PLA
  PLB : PLP
  RTL

  ; Carry set when another actor draws from her cells. Eight entries per pass
  ; with an 8-bit index: about half the time of a plain 128-entry loop.
  .scan_oam
  SEP #$10
  LDX.b #$F0
  .scan
    %HorseScanOam($0800) : %HorseScanOam($0804)
    %HorseScanOam($0808) : %HorseScanOam($080C)
    %HorseScanOam($0900) : %HorseScanOam($0904)
    %HorseScanOam($0908) : %HorseScanOam($090C)
    TXA : SEC : SBC.b #$10 : TAX : BCC .scan_clear
    JMP .scan
  .scan_clear
  REP #$10 : CLC
  RTS
  .scan_hit
  REP #$10 : SEC
  RTS

  ; Entry: M=16, X=8 (XH=0), A = <entry> base ($0800..$090C).
  ; Exit:  M=8,  X=8 (X kept), C=1 if outside [Horse_OffOam..Horse_OffOam+$1F].
  .check_not_epona
  PHA
  LDA.l Horse_OffOam : BEQ .not_epona_pop
  TXA
  CLC : ADC 1, S
  SEC : SBC.l Horse_OffOam
  CMP.w #$0020
  PLA
  SEP #$20
  RTS
  .not_epona_pop
  PLA
  SEP #$20
  SEC
  RTS

  .hide_epona
  REP #$20
  LDA.l Horse_OffOam : CMP.w #$0800 : BCC .hide_done
  CMP.w #$09E4 : BCS .hide_done
  TAX
  SEP #$20
  LDY.w #$0007
  LDA.b #$F0
  .hide
    STA.w $0001, X
    INX #4
    DEY : BPL .hide
  .hide_done
  SEP #$20
  RTS
}

; Epona runs off: poof where she stood, sprite gone, park cleared. The next
; NMI restores the native cells once (Horse_NpcActive = 0 -> .unwant) and she
; stays away until Epona's Song sets a new anchor (HorseCall_Long .accept).
; M8, DBR $00 in. A clobbered; X/Y and index width preserved.
Horse_RunOff:
{
  PHP
  REP #$10 : PHX : PHY
  SEP #$30
  LDX.b #$0F
  .slot
    LDA.w $0DD0, X : BEQ .slot_next
    LDA.w $0E20, X : CMP.b #!HorsePark_SpriteId : BNE .slot_next
    JSL Sprite_SpawnPoofGarnish                   ; X kept, Y clobbered
    STZ.w $0DD0, X
    .slot_next
    DEX : BPL .slot
  LDA.b #$15 : STA.w $012E                        ; SFX2.15 poof
  JSL Horse_RestoreSp3Palette
  LDA.b #$00
  STA.l Horse_HasAnchor : STA.l Horse_NpcActive : STA.l Horse_AnchorArea
  REP #$10 : PLY : PLX
  PLP
  RTL
}

; C=1 while parked off-Ranch Epona must stay hidden: a cutscene only.
; Her cells ($5000-$51FF) are not the item cells the mounted horse borrows,
; so a live ancilla (sword sparkle, item shot) is no reason to hide her:
; Horse_SlotsBusy here made her blink out for each one. A real cell conflict
; is found on screen by Horse_FrameEndScan, which sends her off for good.
; Any widths; A/X/Y/P kept except carry.
Horse_ParkedBusy:
{
  PHP : SEP #$20 : PHA
  LDA.l InCutScene : BNE .busy
  PLA : PLP : CLC : RTL
  .busy
  PLA : PLP : SEC : RTL
}

; NMI, from Horse_NmiUpload .npc when the Ranch profile is not loaded.
; M8/X16, DBR $00.
; Out: C=1: upload Horse_NpcFrame now (.npc_rows).
;      C=0, A=1: performed 1KB VRAM save/restore DMA (skip 1KB animated tiles).
;      C=0, A=0: no DMA performed.
; The copy (1KB read) and the upload use separate NMIs for vblank budget.
Horse_OffRanchNpc:
{
  BRA .gates
  .unwant                                         ; kept within branch range of the gates
  JSL Horse_OffRestore                            ; returns A=1 if 1KB restore DMA ran, else 0
  PHA
  LDA.b #$FF : STA.l Horse_NpcUploadedFrame
  PLA
  CLC : RTL

  .gates
  LDA.b $10 : CMP.b #$0E : BNE .not_pause
    JSL Horse_IsSafeOverlay : BCC .unwant
    LDA.b #$00 : CLC : RTL                        ; keep her cells as they are (no DMA)
  .not_pause
  CMP.b #$09 : BEQ +
  CMP.b #$0B : BNE .unwant
  +
  LDA.b $11 : BNE .unwant
  LDA.b $1B : BNE .unwant
  LDA.l Horse_NpcActive : BEQ .unwant
  LDA.w $02B2 : CMP.b #$09 : BEQ .unwant          ; horse mask on
  LDA.l Horse_HasAnchor : BEQ .unwant
  LDA.b $8A : CMP.l Horse_AnchorArea : BNE .unwant
  JSL Horse_ParkedBusy : BCS .unwant
  LDA.l Horse_OffClear : CMP.b #$02 : BCC .unwant
  LDA.l Horse_NpcFrame
  CMP.b #12 : BCC .unwant
  CMP.b #16 : BCS .unwant
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
  LDA.b #$01 : CLC : RTL                          ; 1KB VRAM read ran
  .none
  LDA.b #$00 : CLC : RTL                          ; no DMA ran
}

; NMI, M8/X16. Write the copy back if Epona's cells are in VRAM and slot
; $7EC2FC still holds the copied sheet (a reload already replaced them).
; Out: A=1 if 1KB restore DMA ran, A=0 if no DMA ran.
Horse_OffRestore:
{
  LDA.l Horse_OffState : CMP.b #$A2 : BNE .clear_none
  LDA.l $7EC2FC : CMP.l Horse_OffSheet : BNE .clear_none
  LDX.w #Horse_OffBuf : STX.w $4302
  LDA.b #Horse_OffBuf>>16 : STA.w $4304
  LDX.w #$0400 : STX.w $4305
  LDX.w #$5000 : STX.w $2116
  LDA.b #$01 : STA.w $420B
  LDA.b #$7E : STA.w $4304
  LDA.b #$00 : STA.l Horse_OffState
  LDA.b #$01
  RTL
  .clear_none
  LDA.b #$00 : STA.l Horse_OffState
  RTL
}

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
if !ENABLE_HORSE_CROWD_CHARGE == 1
  JSL HorseCrowd_Check : BCS .refuse_near  ; too many enemies for Epona's OAM
endif
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
  LDA.b $2F : AND.b #$06 : STA.l Horse_AnchorDir
  LDA.b #$05 : STA.l Horse_Carrots
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
