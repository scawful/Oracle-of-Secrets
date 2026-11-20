; =========================================================
; Mounted Horse Helpers (Bank $53, $53D000-$53DFFF slice).
; Included from Sprites/NPCs/horse.asm before $53E000 assert.
; Provides:
;   - Horse_DmaRider / Horse_DmaPart4Narrow: dropable-safe VRAM layout
;     keeping animated Rupee ($0B/$1B = VRAM $40B0/$41B0) untouched.
;   - HorseClearance_TryNudge: safe 1px orthogonal corner-slide nudge.
;   - HorseForm_ThrottleHostiles / Horse_IsThrottleableHostile: strict
;     mounted overworld hostile-enemy cap (!Horse_MountedEnemyCap = 1)
;     with exhaustive NPC/boss/pickup/target whitelist.
;   - HorseForm_TrampleBushes / Horse_TryTrampleBushAt: mounted grounded
;     overworld bush trampling ($0036 only) via native HandleItemTileAction_Overworld.
; =========================================================

!HorseHelpers_CurrentMask = $02B2
!HorseHelpers_MaskId      = $09
Horse_HandleItemTileAction_Overworld = $1BBD7A

if not(defined("Horse_OverhaulWramDefined"))
  !Horse_OverhaulWramDefined = 1
  Horse_AnchorDir         = $7F5670
  Horse_Carrots           = $7F5671
  Horse_SpurTimer         = $7F5672
  Horse_RegenTimer        = $7F5673
  Horse_HudState          = $7F5674
  Horse_JumpPrevX         = $7F5675
  Horse_JumpPrevY         = $7F5677
  Horse_JumpCamActive     = $7F5679
  Horse_PrioCacheX        = $7F567A
  Horse_PrioCacheY        = $7F567C
  Horse_PrioCacheDir      = $7F567E
  Horse_PrioCacheArea     = $7F567F
  Horse_PrioCacheState    = $7F5680
  Horse_PrioCacheResult   = $7F5681
  Horse_PrioCacheValid    = $7F5682
  Horse_TrampleCacheX     = $7F5683
  Horse_TrampleCacheY     = $7F5685
  Horse_TrampleCacheDir   = $7F5687
  Horse_TrampleCacheArea  = $7F5688
  Horse_TrampleCacheValid = $7F5689
  Horse_NpcLastDir        = $7F568A
  Horse_PalCachedColor    = $7F568B
  Horse_PalCachedHour     = $7F568D
  Horse_PalCacheValid     = $7F568E
  Horse_NorthCacheValid   = $7F568F
  Horse_NorthCacheRes     = $7F5690
  Horse_NorthCacheArea    = $7F5691
  Horse_NorthCacheY8      = $7F5692
  Horse_NorthCacheXL      = $7F5694
  Horse_NorthCacheXR      = $7F5696
  Horse_NorthCacheT16L    = $7F5698
  Horse_NorthCacheT16R    = $7F569A
  Horse_CgiCacheValid     = $7F569C
  Horse_FrameFenceCheckedDir = $7F569D
  Horse_CgiCache          = $7F56A0
  Horse_SafeTile16Cache   = $7F5720
  Horse_SafeTile16Valid   = $7F57A0
  Horse_PrioFenceCacheHdr = $7F57A1
  Horse_PrioFenceCacheRes = $7F57A3
  Horse_PrioFenceCacheXZ  = $7F57A4
  Horse_PrioFenceCacheYZ  = $7F57A6
endif

; Entry: M8/X16, DBR=$00, X = HorseGraphics offset of Rider group (256B:
;   +$00 HeadTop 64B, +$40 BodyTop 64B, +$80 HeadBot 64B, +$C0 BodyBot 64B).
; Uploads Rider Head -> $4080/$4180 ($08,$09/$18,$19) and Rider Body ->
; $40C0/$41C0 ($0C,$0D/$1C,$1D), leaving $40A0-$40BF/$41A0-$41BF untouched.
Horse_DmaRider:
{
  LDA.b #HorseGraphics>>16 : STA.w $4304
  STX.w $4302
  LDY.w #$0040 : STY.w $4305
  LDY.w #$4080 : STY.w $2116 : LDA.b #$01 : STA.w $420B   ; Head Top -> $4080

  REP #$20 : TXA : CLC : ADC.w #$0040 : STA.w $4302 : SEP #$20
  LDY.w #$0040 : STY.w $4305
  LDY.w #$40C0 : STY.w $2116 : LDA.b #$01 : STA.w $420B   ; Body Top -> $40C0

  REP #$20 : TXA : CLC : ADC.w #$0080 : STA.w $4302 : SEP #$20
  LDY.w #$0040 : STY.w $4305
  LDY.w #$4180 : STY.w $2116 : LDA.b #$01 : STA.w $420B   ; Head Bot -> $4180

  REP #$20 : TXA : CLC : ADC.w #$00C0 : STA.w $4302 : SEP #$20
  LDY.w #$0040 : STY.w $4305
  LDY.w #$41C0 : STY.w $2116 : LDA.b #$01 : STA.w $420B   ; Body Bot -> $41C0
  RTS
}

; Entry: M8/X16, DBR=$00, X = HorseGraphics offset of 8-part frame's part 4
;   (frames 8, 9, 16: verified 8px wide, TR=0 & BR=0).
; Uploads ONLY TL (+$00, 32B) -> $40A0 (CHR $0A) and BL (+$40, 32B) -> $41A0
; (CHR $1A), leaving Rupee dropable cell $0B/$1B ($40B0/$41B0) untouched.
Horse_DmaPart4Narrow:
{
  LDA.b #HorseGraphics>>16 : STA.w $4304
  STX.w $4302
  LDY.w #$0020 : STY.w $4305
  LDY.w #$40A0 : STY.w $2116 : LDA.b #$01 : STA.w $420B   ; TL -> $40A0 (CHR $0A)

  REP #$20 : TXA : CLC : ADC.w #$0040 : STA.w $4302 : SEP #$20
  LDY.w #$0020 : STY.w $4305
  LDY.w #$41A0 : STY.w $2116 : LDA.b #$01 : STA.w $420B   ; BL -> $41A0 (CHR $1A)
  RTS
}

; Relocated from horse_ground_clearance.asm (same bank $53) for headroom.
; Writes one OAM entry at Y ($0800+Y) and $0A20+(Y>>2). Requires DBR=$00. Keeps Y.
; Inputs (M=16): $08=screen X (signed), $0E=screen Y (signed), $0B=tile, $0A=attr, $0C=size (0 or 2).
HorseOam_WriteSlot:
{
  LDA.b $0E : CLC : ADC.w #$0010 : CMP.w #$0100 : BCS .offscreen
  LDA.b $08 : CLC : ADC.w #$0010 : CMP.w #$0110 : BCS .offscreen
  TYA : LSR #2 : TAX
  SEP #$20
  LDA.b $08 : STA.w $0800, Y        ; X low
  LDA.b $0E : STA.w $0801, Y        ; Y
  LDA.b $0B : STA.w $0802, Y        ; tile
  LDA.b $0A : STA.w $0803, Y        ; attr
  LDA.b $09 : AND.b #$01              ; high bit of Screen X ($08/$09)
  ORA.b $0C                           ; size bit ($02 or $00)
  STA.w $0A20, X
  REP #$20
  RTS

  .offscreen
  TYA : LSR #2 : TAX
  SEP #$20
  LDA.b #$F0 : STA.w $0801, Y
  LDA.b #$01 : STA.w $0A20, X
  REP #$20
  RTS
}

HorseOam_HideAll:
{
  LDA.w $0352 : LSR #2 : TAX
  LDA.w #$0101
  LDY.b #5
- STA.w $0A20, X
  INX : INX
  DEY : BPL -
  RTS
}

; Emits narrow 8x16 part 4 ($0A top 8x8, $1A bottom 8x8) on 8-part frames (8, 9, 16).
; In:  M=8, X=16, DBR=$00, $08=px, $09=py, $0D=frame, $04=baseX, $06=baseY, Y=OAM off.
; Out: M=16, X=16, Y advanced by +8 (two 8x8 entries). Preserves $00-$07, $0D.
Horse_EmitPart4Narrow:
{
  LDA.b #$06 : STA.b $0A
  LDA.b $2F : CMP.b #4 : BNE .not_flip
    REP #$20 : LDA.b $0D : AND.w #$00FF : TAX : SEP #$20
    LDA.l HorseFrame_Width, X : SEC : SBC.b #8 : SEC : SBC.b $08 : STA.b $08
    LDA.b #$46 : STA.b $0A
  .not_flip
  LDA.b $09 : BEQ .upper : BMI .upper
    LDA.b $0A : ORA.b $65 : BRA +
  .upper
    LDA.b $0A : ORA.b $64
  +
  STA.b $0A
  STZ.b $0C                           ; 8x8 size ($00)
  LDA.b #$0A : STA.b $0B              ; top 8x8 CHR $0A
  LDA.b $09 : PHA
  REP #$20
  LDA.b $08 : AND.w #$00FF
  BIT.w #$0080 : BEQ + : ORA.w #$FF00 : +
  CLC : ADC.b $04 : STA.b $08         ; $08 = 16-bit screen X
  SEP #$20 : PLA : REP #$20 : AND.w #$00FF
  BIT.w #$0080 : BEQ + : ORA.w #$FF00 : +
  CLC : ADC.b $06 : STA.b $0E         ; $0E = 16-bit screen Y (top)
  JSR HorseOam_WriteSlot
  INY #4
  SEP #$20
  LDA.b #$1A : STA.b $0B              ; bottom 8x8 CHR $1A
  REP #$20
  LDA.b $0E : CLC : ADC.w #$0008 : STA.b $0E
  JSR HorseOam_WriteSlot
  INY #4
  RTS
}

; Relocated from Masks/horse_form.asm (same bank $53) to keep $538000-$53CFFF roomy.
; Sparse horse parts, signed source offsets and width-aware horizontal mirroring.
; 6/7-part frames use 16x16 CHR $00,$02,$04,$06,$26,$2A,$2C.
; 8-part frames (8, 9, 16) emit narrow 8x16 part 4 ($0A/$1A) via Horse_EmitPart4Narrow,
; keeping Rupee dropable $0B/$1B ($40B0/$41B0) untouched; parts 5..7 use $26,$2A,$2C.
Horse_EmitEponaBody:
{
  REP #$30
  LDA.b $0D : AND.w #$00FF : TAX
  SEP #$20
  LDA.l HorseFrame_Count, X : PHA     ; 2,S = part count (6..8)
  LDA.b $2F : CMP.b #4 : BEQ .init_flip
    LDA.b #$FF : BRA .push_flip
  .init_flip
    LDA.l HorseFrame_Width, X : SEC : SBC.b #16
  .push_flip
  PHA                                 ; 1,S = flip width-16 (0..32) or $FF
  REP #$20
  TXA : ASL #3 : TAX                  ; X = frame * 8 table base
  SEP #$20
  .loop
    LDA.l HorsePiece_X, X : STA.b $08
    LDA.l HorsePiece_Y, X : STA.b $09
    TXA : AND.b #7 : STA.b $0C        ; $0C = part index (0..7)
    CMP.b #4 : BNE .not_p4
    LDA 2,S : CMP.b #8 : BNE .chr_direct
      PHX
      JSR Horse_EmitPart4Narrow
      PLX
      REP #$20
      BRA .part_done
    .not_p4
    CMP.b #5 : BCC .chr_direct
    LDA 2,S : CMP.b #8 : BNE .chr_direct
      LDA.b $0C : DEC
      BRA .chr_load
    .chr_direct
    LDA.b $0C
    .chr_load
    PHX
    XBA : LDA.b #$00 : XBA : TAX
    LDA.l HorseMounted_Chr, X : STA.b $0B
    PLX
    LDA 1,S : BMI .not_flip
      SEC : SBC.b $08 : STA.b $08
      LDA.b #$46 : BRA .set_attr
    .not_flip
    LDA.b #$06
    .set_attr
    STA.b $0A
    LDA.b $09 : BEQ .upper_prio : BMI .upper_prio
      LDA.b $0A : ORA.b $65 : BRA +
    .upper_prio
      LDA.b $0A : ORA.b $64
    +
    STA.b $0A
    LDA.b #2 : STA.b $0C
    LDA.b $09 : STA.b $0E
    BMI + : LDA.b #$00 : BRA ++ : + : LDA.b #$FF : ++ : STA.b $0F
    BIT.b $08 : BMI + : LDA.b #$00 : BRA ++ : + : LDA.b #$FF : ++ : STA.b $09
    REP #$20
    LDA.b $08 : CLC : ADC.b $04 : STA.b $08
    LDA.b $0E : CLC : ADC.b $06 : STA.b $0E
    PHX
    JSR HorseOam_WriteSlot
    PLX
    INY #4
    .part_done
    INX
    TXA : AND.w #7 : BEQ .done
    SEP #$20
    CMP 2,S : BCS +
      BRL .loop
    +
    REP #$20
    .done
  PLA
  RTS
}

; Mid-screen enemy despawning removed: patrol enemies must never vanish out of
; thin air while riding. Preserved as a benign no-op entry for existing callers.
HorseForm_ThrottleHostiles:
{
  RTS
}

; Contiguous 32-byte 2bpp BG3 HUD carrot tiles ($0149 full, $016E depleted outline).
; Uploaded only while mounted during HUD NMI ($16). Relocated to $53DExx for tail headroom.
Horse_CarrotFullChr:
  db $02,$07, $09,$0F, $1E,$12, $2E,$32, $3C,$24, $58,$68, $70,$50, $E0,$E0
Horse_CarrotEmptyChr:
  db $07,$02, $09,$09, $12,$12, $22,$22, $24,$24, $48,$48, $50,$50, $E0,$E0
assert pc()-Horse_CarrotFullChr == 32

; Linear 49-entry speed decay offsets (frames 0..48) -> cardinal $22..$32, diag $1C..$29.
Horse_SpurCardinalBonus:
  db  0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5
  db  6, 6, 6, 7, 7, 7, 8, 8, 8, 9, 9, 9,10,10,10,11
  db 11,11,12,12,12,13,13,13,14,14,14,15,15,15,16,16,16
assert pc()-Horse_SpurCardinalBonus == 49

Horse_SpurDiagBonus:
  db  0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 4, 4, 4
  db  4, 5, 5, 5, 5, 6, 6, 6, 6, 7, 7, 7, 8, 8, 8, 8
  db  9, 9, 9, 9,10,10,10,11,11,11,11,12,12,12,12,13,13
assert pc()-Horse_SpurDiagBonus == 49

; Hooked at Overworld_OperateCameraScroll ($02BB90) right after PHB.
; Feeds exact jump-frame displacement ($20 - PrevY, $22 - PrevX) into $30/$31.
Horse_SyncJumpCamera:
{
  SEP #$20
  LDA.l Horse_JumpCamActive : BEQ .exit
    LDA.b #$00 : STA.l Horse_JumpCamActive
    REP #$20
    LDA.b $20 : SEC : SBC.l Horse_JumpPrevY
    SEP #$20 : STA.b $30
    REP #$20
    LDA.b $22 : SEC : SBC.l Horse_JumpPrevX
    SEP #$20 : STA.b $31
  .exit
  LDA.b #$02 : PHA : PLB
  REP #$20
  RTL
}

; Handles grounded B dismount when safe (not jumping, minigame, cutscene, frozen, or doorway).
Horse_TryBDismount:
{
  LDA.b $F4 : AND.b #$80 : BEQ .no
  LDA.b #$80 : TRB.b $F4
  LDA.l Horse_State : ORA.l Horse_JumpTimer : BNE .no
  LDA.l HorseGame_State : BNE .no
  LDA.l InCutScene : BNE .no
  LDA.w $02E4 : ORA.b $1D : ORA.b $6C : ORA.w $0FFC : ORA.b $5D : BNE .no
  LDA.b #$80 : TRB.b $F6
  JSL HorseForm_Dismount
  SEC
  RTS
  .no
  CLC
  RTS
}
HorseMountedHelpers_End:

; =========================================================
; Epona Bush Trampling (Bank $53, $53F000-$53F3FF slice)
; Placed after horse_minigame ($53E900-$53EFF0) to keep $53D000-$53DFFF roomy.
; =========================================================
pushpc
org $53F000
; Probes leading hoof/body edges ahead of Link's native collision box
; ($07CD7B) for cuttable Overworld bushes (Tile16 $0036 ONLY) before
; Link_ControlHandler runs, cutting them via vanilla
; HandleItemTileAction_Overworld ($1BBD7A -> OverworldTileAction_Bush)
; with $0301=$0000 and $037A=$0000:
;   - Replaces $0036 in $7E2000 + queues VRAM BG update via Overworld_DrawMap16
;   - Preserves Liftables_SelectBushReveal (DW $63 -> $0172, else $0DC7)
;     and Overworld_RevealSecret (rupees, hearts, arrows, hidden holes/stairs)
;   - Spawns Sprite $EC leaf-burst debris + bush-cut SFX2.1E + drop roll
;   - Spawns NO Ancilla $3F poof ($0301 bit 6 = 0 -> Horse_SlotsBusy stays clear)
; Rejects rocks, signs, pegs, fences, trees, walls, tall grass ($037E), and
; overwritten LW $22 brick wall ($072A).
;
; Entry/Exit: M=8, X=8, DBR=$00. Preserves X, Y, DBR, DP $00-$0F, P (M8/X8).
HorseForm_TrampleBushes:
{
  LDA.w !HorseHelpers_CurrentMask : CMP.b #!HorseHelpers_MaskId : BNE .early_exit
  LDA.b $1B : BNE .early_exit
  LDA.b $10 : CMP.b #$09 : BEQ +
  CMP.b #$0B : BNE .early_exit
  +
  LDA.b $11 : ORA.b $5D : ORA.b $4D : ORA.b $6C : BNE .early_exit
  LDA.w $0FFC : ORA.w $02E4 : BNE .early_exit
  LDA.l HorseGame_State
  CMP.b #$01 : BEQ .early_exit
  CMP.b #$03 : BEQ .early_exit
  LDA.l Horse_State : ORA.l Horse_JumpTimer : BNE .early_exit
  LDA.b $F0 : AND.b #$0F : BNE .check_cache
  .early_exit
  RTS

  .check_cache
  ; Fast skip if Link's world pixel (X,Y), input nibble, and area match last clear probe.
  LDA.l Horse_TrampleCacheValid : BEQ .active
  LDA.b $8A : CMP.l Horse_TrampleCacheArea : BNE .active
  LDA.b $F0 : AND.b #$0F : CMP.l Horse_TrampleCacheDir : BNE .active
  REP #$20
  LDA.b $22 : CMP.l Horse_TrampleCacheX : BNE .active_m8
  LDA.b $20 : CMP.l Horse_TrampleCacheY : BNE .active_m8
    SEP #$20
    RTS
  .active_m8
  SEP #$20

  .active
  PHP : PHB
  REP #$30
  PHX : PHY
  LDA.b $02 : PHA : LDA.b $06 : PHA
  LDA.b $0A : PHA : LDA.b $0C : PHA : LDA.b $0E : PHA
  SEP #$30
  LDA.b #$00 : PHA : PLB              ; ensure DBR=$00

  LDA.b $F0 : AND.b #$0F : STA.b $0E  ; live post-clearance D-pad nibble
  STZ.b $0F                           ; non-zero once any bush is cut this frame

  ; Check each held cardinal direction (0=N, 1=S, 2=W, 3=E): 2 leading probes each.
  ; Perpendicular span is 15px (<= 16px Tile16) so no bush can slip between points.
  LDX.b #$03
  .dir_loop
    LDA.b $0E : AND.l .dir_mask, X : BEQ .next_dir
    PHX
    REP #$30
    TXA : AND.w #$0003 : ASL : TAX      ; X = dir * 2 (0, 2, 4, 6)
    LDA.b $22 : CLC : ADC.l .p0_dx, X : STA.b $0C
    LDA.b $20 : CLC : ADC.l .p0_dy, X : STA.b $0A
    JSR .try_probe
    LDA.b $22 : CLC : ADC.l .p1_dx, X : STA.b $0C
    LDA.b $20 : CLC : ADC.l .p1_dy, X : STA.b $0A
    JSR .try_probe
    SEP #$30
    PLX
  .next_dir
    DEX : BPL .dir_loop

  ; Diagonal movement (both V=$0C and H=$03 held): also probe leading diagonal corner.
  LDA.b $0E : AND.b #$0C : BEQ .restore
  LDA.b $0E : AND.b #$03 : BEQ .restore
    REP #$30
    LDX.w #$0000                        ; 0=NE, 2=NW, 4=SE, 6=SW
    LDA.b $0E : BIT.w #$0004 : BEQ + : LDX.w #$0004 : +
    LDA.b $0E : BIT.w #$0002 : BEQ + : INX #2 : +
    LDA.b $22 : CLC : ADC.l .diag_dx, X : STA.b $0C
    LDA.b $20 : CLC : ADC.l .diag_dy, X : STA.b $0A
    JSR .try_probe
    SEP #$20

  .restore
  LDA.b $0F : BNE .cache_invalidate
    REP #$20
    LDA.b $22 : STA.l Horse_TrampleCacheX
    LDA.b $20 : STA.l Horse_TrampleCacheY
    SEP #$20
    LDA.b $0E : STA.l Horse_TrampleCacheDir
    LDA.b $8A : STA.l Horse_TrampleCacheArea
    LDA.b #$01 : STA.l Horse_TrampleCacheValid
    BRA .pop_regs
  .cache_invalidate
    LDA.b #$00 : STA.l Horse_TrampleCacheValid
  .pop_regs
  REP #$30
  PLA : STA.b $0E : PLA : STA.b $0C : PLA : STA.b $0A
  PLA : STA.b $06 : PLA : STA.b $02
  PLY : PLX
  SEP #$30
  PLB : PLP
  RTS

  ; In: M=16, X=16, $0C=X16, $0A=Y16. Out: M=16, X=16; preserves X, Y, $0E.
  .try_probe
  PHX
  LDA.b $0A : SEC : SBC.w $0708 : AND.w $070A : ASL #3 : STA.b $06
  LDA.b $0C : LSR #3 : STA.b $02
  SEC : SBC.w $070C : AND.w $070E : CLC : ADC.b $06 : TAX
  LDA.l $7E2000, X : CMP.w #$0036 : BEQ +
    PLX
    RTS
  +
  SEP #$30
  JSR Horse_TryTrampleBushAt
  REP #$30
  PLX
  RTS

  .dir_mask : db $08, $04, $02, $01   ; N, S, W, E
  ; Offsets 4px ahead of Link's native collision box ($07CD7B: X+0..+15, Y+8..+24)
  ;              North  South  West   East
  .p0_dx   : dw $0000, $0000, $FFFC, $0013
  .p0_dy   : dw $0004, $001C, $0008, $0008
  .p1_dx   : dw $000F, $000F, $FFFC, $0013
  .p1_dy   : dw $0004, $001C, $0017, $0017
  ;              NE     NW     SE     SW
  .diag_dx : dw $0013, $FFFC, $0013, $FFFC
  .diag_dy : dw $0004, $0004, $001C, $001C
}

; Tests world pixel ($0C=X16, $0A=Y16) for cuttable Overworld bush Tile16 $0036
; inside the current area and viewport, and invokes HandleItemTileAction_Overworld.
; Entry/Exit: M=8, X=8, DBR=$00. Preserves X, Y, DBR, DP $0E.
Horse_TryTrampleBushAt:
{
  PHX
  REP #$30
  ; O(1) $7E2000 lookup FIRST: >99% of moving probes are not bush Tile16 $0036.
  LDA.b $0A : SEC : SBC.w $0708 : AND.w $070A : ASL #3 : STA.b $06
  LDA.b $0C : LSR #3 : STA.b $02
  SEC : SBC.w $070C : AND.w $070E : CLC : ADC.b $06 : TAX
  LDA.l $7E2000, X : CMP.w #$0036 : BEQ .is_bush
    SEP #$30
    PLX
    RTS

  .is_bush
  ; Only bush $0036 probes pay for area/viewport/queue bounds and vanilla cut call.
  SEP #$10
  PHY
  LDA.b $00 : PHA : LDA.b $04 : PHA : LDA.b $08 : PHA
  JSR HorseForm_ConstrainGroundInput_point_outside_area : BCS .miss16
  LDA.b $0A : SEC : SBC.b $E8 : CMP.w #$00E0 : BCS .miss16
  LDA.b $0C : SEC : SBC.b $E2 : CMP.w #$0100 : BCS .miss16
  LDA.w $1000 : CMP.w #$00D0 : BCS .miss16

  ; Prepare $00=Ypx ($02=Xpx>>3 already stored) and invoke vanilla bush cut.
  LDA.b $0A : STA.b $00
  LDA.b $0E : PHA                     ; preserve 16-bit $0E/$0F across $1BBD7A
  SEP #$30
  LDA.w $0301 : PHA : STZ.w $0301
  LDA.w $037A : PHA : STZ.w $037A
  PHB
  JSL Horse_HandleItemTileAction_Overworld ; returns M=8, X=8
  PLB
  PLA : STA.w $037A
  PLA : STA.w $0301
  REP #$20
  PLA : STA.b $0E
  PLA : STA.b $08 : PLA : STA.b $04 : PLA : STA.b $00
  SEP #$20
  LDA.b #$01 : STA.b $0F              ; signal bush cut for HorseForm_TrampleBushes
  PLY : PLX
  RTS

  .miss16
  PLA : STA.b $08 : PLA : STA.b $04 : PLA : STA.b $00
  SEP #$20
  PLY : PLX
  RTS
}
; Relocated from Masks/horse_ground_clearance.asm so $53E000-$53E7FF retains headroom.
HorseForm_CheckLandingWalkable_Impl:
{
  LDX.b #$02                          ; check 3 points: 2, 1, 0
  .pt_loop
    PHX
    TXA : ASL : TAX
    REP #$20
    LDA.l Horse_JumpEndX : CLC : ADC.l .off_x, X : STA.b $0C
    LDA.l Horse_JumpEndY : CLC : ADC.l .off_y, X : STA.b $0A
    JSR .test_walkable : BCC .blocked_pop
    PLX
    DEX : BPL .pt_loop

  LDA.l Horse_JumpDir : BNE .not_north
    LDX.b #$02                        ; North jump: also verify top half (4,2) & (11,2) walkable
    .north_loop
      PHX
      REP #$20
      LDA.l Horse_JumpEndX : CLC : ADC.l .off_x, X : STA.b $0C
      LDA.l Horse_JumpEndY : CLC : ADC.w #$0002 : STA.b $0A
      JSR .test_walkable : BCC .blocked_pop
      PLX
      DEX : DEX : BPL .north_loop
    BRA .ok

  .not_north
  LDX.b #$02                          ; S/W/E jump: verify lower body (4,22) & (11,22) not $01/$02 solid
  .south_loop
    REP #$20
    LDA.l Horse_JumpEndX : CLC : ADC.l .off_x, X : STA.b $0C
    LDA.l Horse_JumpEndY : CLC : ADC.w #$0016 : STA.b $0A
    SEP #$20
    JSR Horse_QueryTileAt             ; M=8, X=8, X preserved
    CMP.b #$01 : BEQ .blocked
    CMP.b #$02 : BEQ .blocked
    DEX : DEX : BPL .south_loop
  .ok
  SEC
  RTS

  .blocked_pop
  PLX
  .blocked
  CLC
  RTS

  ; In: M=16, DP $0A/$0C set. Out: M=8, C=1 if walkable, clobbers X.
  .test_walkable
  SEP #$20
  JSR Horse_QueryTileAt
  CMP.b #$58 : BCS .not_walk
  TAX
  LDA.l HorseWalkableAttr, X : BEQ .not_walk
  SEC
  RTS
  .not_walk
  CLC
  RTS

  .off_x
  dw 4, 11, 8
  .off_y
  dw 12, 12, 8
}

; Safe 1px orthogonal corner-slide nudge for HorseForm_ConstrainGroundInput.
HorseClearance_TryNudge:
{
  PHX : PHY
  ASL : TAX                           ; X = 0 (-X), 2 (+X), 4 (-Y), 6 (+Y)
  REP #$20
  LDA.b $22 : CLC : ADC.l .step_x, X : STA.b $08 ; $08 = candX
  LDA.b $20 : CLC : ADC.l .step_y, X : STA.b $06 ; $06 = candY

  LDA.b $08 : CLC : ADC.w #$0008 : STA.b $0C
  LDA.b $06 : CLC : ADC.w #$000C : STA.b $0A
  JSR HorseForm_ConstrainGroundInput_point_outside_area : BCS .abort_a16
  SEP #$20
  JSR Horse_QueryTileAt               ; X preserved, A = tiletype
  CMP.b #$58 : BCS .abort
  PHX : TAX : LDA.l HorseWalkableAttr, X : PLX
  CMP.b #$00 : BEQ .abort

  REP #$20
  LDA.b $08 : CLC : ADC.l .flank_x, X : STA.b $0C
  LDA.b $06 : CLC : ADC.l .flank_y, X : STA.b $0A
  JSR HorseForm_ConstrainGroundInput_query_side
  CMP.b #$01 : BEQ .abort
  CMP.b #$02 : BEQ .abort

  REP #$20
  LDA.b $08 : CLC : ADC.l .foot_x, X : STA.b $0C
  LDA.b $06 : CLC : ADC.l .foot_y, X : STA.b $0A
  JSR HorseForm_ConstrainGroundInput_query_side
  CMP.b #$01 : BEQ .abort
  CMP.b #$02 : BEQ .abort

  REP #$20
  LDA.b $08 : STA.b $22
  LDA.b $06 : STA.b $20
  .abort_a16
  SEP #$20
  .abort
  PLY : PLX
  RTS

  ;          -X     +X     -Y     +Y
  .step_x : dw $FFFF, $0001, $0000, $0000
  .step_y : dw $0000, $0000, $FFFF, $0001
  .flank_x: dw $FFFA, $0015, $0008, $0008
  .flank_y: dw $000A, $000A, $FFF6, $0013
  .foot_x : dw $0002, $000D, $0008, $0008
  .foot_y : dw $000C, $000C, $0008, $0016
}

; Fast Tile16 lookup without calling vanilla $00882E (same bank $53).
; Inputs: DP $0A = 16-bit world Y px, DP $0C = 16-bit world X px (M/X=8).
; Outputs: DP $04 = 16-bit Tile16 ID (M/X=8); X/Y/B/P and DP $06 preserved.
Horse_QueryTile16Only:
{
  PHP : REP #$30 : PHX : PHA
  LDA.b $06 : PHA
  LDA.b $0A : SEC : SBC.l $7E0708 : AND.l $7E070A : ASL #3 : STA.b $06
  LDA.b $0C : LSR #3 : SEC : SBC.l $7E070C : AND.l $7E070E : ORA.b $06 : TAX
  LDA.l $7E2000, X : STA.b $04
  PLA : STA.b $06
  PLA : PLX : PLP
  RTS
}
HorseBushTrample_End:
assert pc() <= $53F400, "Horse bush trampling exceeded its bounded bank53 slice ($53F000-$53F3FF)"
pullpc

; =========================================================
; Epona Overhaul Systems ($53F400-$53FFFF free Bank $53 tail)
; =========================================================
pushpc
org $53F400

; North & South parked Epona NPC tail rows (pieces 4..5, 512B each -> VRAM $5080/$5180)
; Sliced verbatim from existing Masks/gfx/horse_sparse.4bpp; no new 4bpp art invented.
HorseNpcNorthTail:
  incbin "gfx/horse_sparse.4bpp":$0300..$0340
  incbin "gfx/horse_sparse.4bpp":$0380..$03C0
  fillbyte $00 : fill 128
  incbin "gfx/horse_sparse.4bpp":$0340..$0380
  incbin "gfx/horse_sparse.4bpp":$03C0..$0400
  fillbyte $00 : fill 128
assert pc()-HorseNpcNorthTail == 512

HorseNpcSouthTail:
  incbin "gfx/horse_sparse.4bpp":$0D80..$0DC0
  incbin "gfx/horse_sparse.4bpp":$0E00..$0E40
  fillbyte $00 : fill 128
  incbin "gfx/horse_sparse.4bpp":$0DC0..$0E00
  incbin "gfx/horse_sparse.4bpp":$0E40..$0E80
  fillbyte $00 : fill 128
assert pc()-HorseNpcSouthTail == 512

!Horse_MaxCarrots      = 5
!Horse_SpurDuration    = 48
!Horse_NormalRegen     = 75
!Horse_EmptyRegen      = 135
!Horse_HudCarrotFull   = $3549 ; Pal 5 ($3400) | Tile $0149
!Horse_HudCarrotEmpty  = $316E ; Pal 4 ($3000) | Tile $016E
!Horse_HudBlankCell    = $207F

; Called via JSL from LinkState_BunnyHoodRun ($20AF20) when !CurrentMask == #$09.
; In:  M=8, any X width, X = SubVelocityValues index (0..$10).
; Out: A = effective sub-velocity, C=0, caller X width preserved.
HorseSpeed_GetSubVel:
{
  PHP : PHB
  PHK : PLB                           ; DBR = $53 for local ,Y table indexing
  SEP #$30
  PHX : PHY
  LDA.w HorseSpeedTable, X
  PHA                                 ; preserve base speed
  LDA.l Horse_SpurTimer : BEQ .done_pop
    CMP.b #49 : BCC +
      LDA.b #48
    +
    TAY
    CPX.b #$00 : BEQ .cardinal
    CPX.b #$0C : BEQ .cardinal
    CPX.b #$01 : BEQ .diag
    CPX.b #$0D : BNE .done_pop
  .diag
    PLA : CLC : ADC.w Horse_SpurDiagBonus, Y
    BRA .done
  .cardinal
    PLA : CLC : ADC.w Horse_SpurCardinalBonus, Y
    BRA .done
  .done_pop
    PLA
  .done
  PLY : PLX
  PLB : PLP
  CLC
  RTL
}

; Renders 5 carrot pips on BG3 HUD Row 3 cols 2-6 ($7EC7C4..$7EC7CC) ONLY while
; mounted outdoors with active HUD; clears cleanly to $207F otherwise.
; Queues $16 ONLY when state/pip changes or $7EC7C4 mismatches (zero steady-state overhead).
; Safe from any M/X width, any DBR; preserves A/X/Y/P/DBR.
Horse_SyncCarrotHud:
{
  PHP : PHB
  REP #$30
  PHA : PHX : PHY
  SEP #$20
  LDA.b #$00 : PHA : PLB

  ; Determine whether HUD carrots should be visible
  LDA.w !HorseHelpers_CurrentMask : CMP.b #!HorseHelpers_MaskId : BNE .want_blank
  LDA.b $1B : BNE .want_blank
  LDA.b $10 : CMP.b #$0E : BEQ .want_blank
  LDA.l $7EC73A : CMP.b #$7F : BEQ .want_blank

  ; Mounted outdoors: desired = $80 | clamped_carrots (0..5)
  LDA.l Horse_Carrots
  CMP.b #!Horse_MaxCarrots+1 : BCC +
    LDA.b #!Horse_MaxCarrots
    STA.l Horse_Carrots
  +
  REP #$20
  AND.w #$00FF
  TAY                                 ; Y = 0..5 full carrots (16-bit)
  SEP #$20
  TYA
  ORA.b #$80                          ; A = $80 | carrots
  LDX.w #!Horse_HudCarrotFull
  CPY.w #$0000 : BNE .check_dirty
    LDX.w #!Horse_HudCarrotEmpty
    BRA .check_dirty

  .want_blank
  LDY.w #$FFFF                        ; blank marker
  LDA.b #$00                          ; desired = 0
  LDX.w #!Horse_HudBlankCell          ; expected $7EC7C4 word

  .check_dirty
  CMP.l Horse_HudState : BNE .apply
  PHA
  REP #$20
  TXA
  CMP.l $7EC7C4 : BEQ .clean_pop
    SEP #$20
    PLA
    BRA .apply
  .clean_pop
  SEP #$20
  PLA
  BRA .exit

  .apply
  STA.l Horse_HudState
  CMP.b #$00 : BEQ .write_blank
    ; Write 5 pips: slots 0..Y-1 get Full ($3549), remaining up to 5 get Empty ($316E).
    ; Y holds 0..5. Build 16-bit cell offset in X = 0,2,4,6,8 while decrementing Y.
    REP #$20
    LDX.w #$0000
    .pip_loop
      CPY.w #$0000 : BEQ .pip_empty
        LDA.w #!Horse_HudCarrotFull
        DEY
        BRA .pip_store
      .pip_empty
        LDA.w #!Horse_HudCarrotEmpty
      .pip_store
      STA.l $7EC7C4, X
      INX #2
      CPX.w #$000A : BCC .pip_loop
    BRA .queue_nmi

  .write_blank
    REP #$20
    LDA.w #!Horse_HudBlankCell
    LDX.w #$0008
    .blank_loop
      STA.l $7EC7C4, X
      DEX #2 : BPL .blank_loop

  .queue_nmi
  SEP #$20
  LDA.b $10 : CMP.b #$0E : BEQ .exit
    LDA.b #$01 : STA.b $16

  .exit
  REP #$30
  PLY : PLX : PLA
  PLB : PLP
  RTL
}

; Handles A spur carrot spend + unconditional block/rock/bush lifting suppression.
; Runs AFTER HorseGame_KidStartCheck so Ranch Kid prompt keeps working on A.
; In: M=8, X=8, DBR=$00.
Horse_PreMoveControlTick:
{
  ; Always consume A lift/grab/dash flags while mounted so Link NEVER lifts rocks/bushes/pots!
  BIT.b $F6 : BPL .suppress_lift
  LDA.l Horse_State : ORA.l Horse_JumpTimer : BNE .suppress_lift
  LDA.l HorseGame_State : CMP.b #$04 : BEQ .suppress_lift
  LDA.l InCutScene : BNE .suppress_lift
  LDA.w $02E4 : ORA.b $6C : ORA.w $0FFC : ORA.b $5D : BNE .suppress_lift

  ; Valid A spur press!
  LDA.l Horse_Carrots : BEQ .empty_carrots
    DEC : STA.l Horse_Carrots
    LDA.b #!Horse_SpurDuration : STA.l Horse_SpurTimer
    LDA.l Horse_Carrots : BNE .normal_regen
      LDA.b #!Horse_EmptyRegen : STA.l Horse_RegenTimer
      BRA .spur_sfx
    .normal_regen
      LDA.l Horse_RegenTimer : BNE .spur_sfx
      LDA.b #!Horse_NormalRegen : STA.l Horse_RegenTimer
    .spur_sfx
    LDA.b #$20 : STA.w $012E          ; SFX2.20 crisp gallop burst cue
    BRA .suppress_lift

  .empty_carrots
    LDA.w $012E : BNE .suppress_lift
      LDA.b #$3C : STA.w $012E        ; soft empty cue if channel free

  .suppress_lift
  LDA.b #$80
  TRB.b $F6                           ; clear new A press before Link_HandleAPress
  TRB.b $F2                           ; clear held A so grab/pull cannot engage
  TRB.b $3B                           ; clear Link A-latch
  STZ.b $3C                           ; no sword/carry hold
  STZ.w $0308                         ; clear carry/lift substate
  STZ.w $0376                         ; clear grab/pull/dash state
  STZ.w $02EC                         ; clear liftable timer/state
  BIT.b $3A : BVS +
    LDA.b #$01 : TRB.b $50            ; never leave grab/A dir-lock stuck while mounted
  +
  LDA.b $5D : CMP.b #$11 : BNE +
    STZ.b $5D                         ; force exit LinkState 11 (carrying/grabbing)
  +
  RTS
}

; Updates spur decay, stop/bonk reset, gradual carrot regen, and HUD sync.
; Runs AFTER CheckFenceJump + ConstrainGroundInput. In: M=8, X=8, DBR=$00.
Horse_PostMoveDecayTick:
{
  LDA.l Horse_SpurTimer : BEQ .regen
    ; Keep spur active across mid-air jumps.
    LDA.l Horse_State : ORA.l Horse_JumpTimer : BNE .tick_spur
    ; Reset speed burst on damage/recoil ($5D==2 or $4D!=0).
    LDA.b $5D : CMP.b #$02 : BEQ .reset_spur
    LDA.b $4D : BNE .reset_spur
    ; Reset speed burst when stopped (D-pad released) or bonked solid non-fence obstacle.
    LDA.b $F0 : AND.b #$0F : BNE .tick_spur
    LDA.l Horse_PushTimer : BNE .tick_spur
    .reset_spur
      LDA.b #$00 : STA.l Horse_SpurTimer
      BRA .regen
    .tick_spur
      LDA.l Horse_SpurTimer : DEC : STA.l Horse_SpurTimer

  .regen
  LDA.l Horse_SpurTimer : BNE .hud    ; regen begins once burst decays
  LDA.l Horse_Carrots : CMP.b #!Horse_MaxCarrots : BCS .hud
    LDA.l Horse_RegenTimer : BNE .dec_regen
      LDA.b #!Horse_NormalRegen : STA.l Horse_RegenTimer
    .dec_regen
    DEC : STA.l Horse_RegenTimer : BNE .hud
      LDA.l Horse_Carrots : INC : STA.l Horse_Carrots
      CMP.b #!Horse_MaxCarrots : BCS .hud
        LDA.b #!Horse_NormalRegen : STA.l Horse_RegenTimer

  .hud
  JSL Horse_SyncCarrotHud
  RTS
}

; Cached fence-priority test (moves logic into $53F400+ tail + skips 8 tile probes
; whenever LinkX, LinkY, $2F, $8A, and Horse_State match last frame).
; Entry/Exit: M=8, X=8, DBR=$00 (preserves registers & DP).
Horse_ApplyFencePriority_Impl:
{
  PHP
  LDA.l Horse_PrioCacheValid : BEQ .miss
  LDA.b $8A : CMP.l Horse_PrioCacheArea : BNE .miss
  LDA.l Horse_State : CMP.l Horse_PrioCacheState : BNE .miss
  REP #$20
  LDA.b $22 : CMP.l Horse_PrioCacheX : BNE .miss_m8
  LDA.b $20 : CMP.l Horse_PrioCacheY : BNE .miss_m8
    SEP #$20
    LDA.l Horse_PrioCacheResult
    BEQ .cache_none
    CMP.b #$01 : BEQ .cache_north
      LDA.b $65 : ORA.b #$30 : STA.b $65
    .cache_north
      LDA.b $64 : ORA.b #$30 : STA.b $64
    .cache_none
    PLP
    RTS

  .miss_m8
  SEP #$20
  .miss
  REP #$30
  PHX : PHY
  LDA.b $04 : PHA : LDA.b $06 : PHA : LDA.b $08 : PHA : LDA.b $0A : PHA
  LDA.b $0C : PHA : LDA.b $0E : PHA
  ; Fast 2x3 Tile16 fence-scan cache keyed by ($8A, X_zone, (Y+6)&$FFF0).
  LDA.b $22 : AND.w #$000F : TAX
  LDA.l .xz, X : AND.w #$00FF : STA.b $04
  LDA.b $22 : AND.w #$FFF0 : ORA.b $04 : STA.b $04
  LDA.b $20 : CLC : ADC.w #$0006 : AND.w #$FFF0 : STA.b $06
  LDA.b $8A : AND.w #$00FF : ORA.w #$0100 : STA.b $08
  CMP.l Horse_PrioFenceCacheHdr : BNE .pf_miss
  LDA.b $04 : CMP.l Horse_PrioFenceCacheXZ : BNE .pf_miss
  LDA.b $06 : CMP.l Horse_PrioFenceCacheYZ : BNE .pf_miss
    SEP #$20
    LDA.l Horse_PrioFenceCacheRes : BNE + : BRL .north_check_m8 : +
    BRL .hit
  .pf_miss
  LDA.b $04 : STA.l Horse_PrioFenceCacheXZ
  LDA.b $06 : STA.l Horse_PrioFenceCacheYZ
  LDA.b $08 : STA.l Horse_PrioFenceCacheHdr
  ; Inline 2-row x 3-col Tile16 scan (computes row/col offsets once per axis).
  ; Y + DP $06 form a 2-entry LRU of non-priority Tile16s so checkerboard ground skips re-checks.
  LDA.b $22 : SEC : SBC.w #$0006 : LSR #3 : SEC : SBC.w $070C : AND.w $070E : STA.b $08
  LDA.b $22 : CLC : ADC.w #$0008 : LSR #3 : SEC : SBC.w $070C : AND.w $070E : STA.b $0A
  LDA.b $22 : CLC : ADC.w #$0016 : LSR #3 : SEC : SBC.w $070C : AND.w $070E : STA.b $0C
  LDY.w #$FFFF : STY.b $06
  LDA.b $20 : CLC : ADC.w #$0006 : SEC : SBC.w $0708 : AND.w $070A : ASL #3 : STA.b $0E
  JSR .check_row : BCC + : BRL .pf_hit : +
  LDA.b $20 : CLC : ADC.w #$0016 : SEC : SBC.w $0708 : AND.w $070A : ASL #3
  CMP.b $0E : BEQ +
    STA.b $0E
    JSR .check_row : BCC + : BRL .pf_hit : +
  +
  SEP #$20
  LDA.b #$00 : STA.l Horse_PrioFenceCacheRes
  .north_check_m8
  REP #$20

  ; Fast North cache check before computing any $0708..$070E / $7E2000 offsets.
  LDA.b $20 : SEC : SBC.w #$0004 : AND.w #$FFF8 : STA.b $04 ; $04 = Y8_N
  SEP #$20
  LDA.l Horse_NorthCacheValid : CMP.b #$03 : BNE .north_slow
  LDA.b $8A : CMP.l Horse_NorthCacheArea : BNE .north_slow
  REP #$20
  LDA.b $04 : CMP.l Horse_NorthCacheY8 : BNE .north_slow_m16
  LDA.b $22 : CLC : ADC.w #$0002 : AND.w #$FFF8 : CMP.l Horse_NorthCacheXL : BNE .north_slow_m16
  LDA.b $22 : CLC : ADC.w #$000D : AND.w #$FFF8 : CMP.l Horse_NorthCacheXR : BNE .north_slow_m16
    SEP #$20
    LDA.l Horse_NorthCacheRes : BEQ + : BRL .north_hit : +
    BRL .no_prio

  .north_slow_m16
  SEP #$20
  .north_slow
  REP #$20
  LDA.b $20 : SEC : SBC.w #$0004
  SEC : SBC.w $0708 : AND.w $070A : ASL #3 : STA.b $0E

  SEP #$20
  LDA.l Horse_NorthCacheValid : BEQ .north_reset_m8
  LDA.b $8A : CMP.l Horse_NorthCacheArea : BNE .north_reset_m8
  REP #$20
  LDA.b $04 : CMP.l Horse_NorthCacheY8 : BEQ .north_hdr_ok
    SEP #$20
    .north_reset_m8
    LDA.b #$00 : STA.l Horse_NorthCacheValid : STA.l Horse_NorthCacheRes
    LDA.b $8A : STA.l Horse_NorthCacheArea
    REP #$20
    LDA.b $04 : STA.l Horse_NorthCacheY8
  .north_hdr_ok

  LDY.w #$0000 : JSR .north_check_side : BCC + : BRL .north_hit : +
  LDY.w #$0002 : JSR .north_check_side : BCC + : BRL .north_hit : +
  BRL .no_prio

  ; Shared North solid-base probe for Y=0 (Left +2) / Y=2 (Right +13).
  ; In: M=16, X=16, Y=0|2, $0E=row off. Out: M=8, X=16, C=1 solid. Preserves Y,$0E.
  .north_check_side
  REP #$20
  TYX
  LDA.b $22 : CLC : ADC.l .n_dx, X : AND.w #$FFF8 : STA.b $08
  LSR #3 : SEC : SBC.w $070C : AND.w $070E : ORA.b $0E : TAX : LDA.l $7E2000, X : STA.b $0A
  TYX
  SEP #$20
  LDA.l Horse_NorthCacheValid : AND.l .n_mask, X : BEQ .north_miss_side
  REP #$20
  LDA.b $08 : CMP.l Horse_NorthCacheXL, X : BNE .north_miss_side_m16
  LDA.b $0A : CMP.l Horse_NorthCacheT16L, X : BNE .north_miss_side_m16
    SEP #$20
    LDA.l Horse_NorthCacheRes : AND.l .n_mask, X : BEQ .north_side_clr
    SEC : RTS
    .north_side_clr
    CLC : RTS
  .north_miss_side_m16
  SEP #$20
  .north_miss_side
  REP #$20
  LDA.b $08 : STA.l Horse_NorthCacheXL, X
  LDA.b $0A : STA.l Horse_NorthCacheT16L, X
  SEP #$20
  LDA.l Horse_SafeTile16Valid : BEQ .n_query_m8
  LDA.b $8A : BMI .n_query_m8
  LDA.b $1B : BNE .n_query_m8
  REP #$20
  LDA.b $0A : LSR #4 : EOR.b $0A : AND.w #$001F : ASL #2 : TAX
  LDA.b $0A : CMP.l Horse_SafeTile16Cache+0, X : BNE .n_query_m16
  SEP #$20
  LDA.b $8A : CMP.l Horse_SafeTile16Cache+2, X : BNE .n_query_m8
  LDA.l Horse_SafeTile16Cache+3, X : BEQ .n_query_m8
    TYX
    LDA.l Horse_NorthCacheValid : ORA.l .n_mask, X : STA.l Horse_NorthCacheValid
    BRA .north_side_clr_upd
  .n_query_m8
  REP #$20
  .n_query_m16
  TYX
  LDA.b $20 : SEC : SBC.w #$0004 : STA.b $0A
  LDA.b $22 : CLC : ADC.l .n_dx, X : STA.b $0C
  SEP #$30
  JSR Horse_QueryTileAt
  REP #$10
  TYX
  PHA
  LDA.l Horse_NorthCacheValid : ORA.l .n_mask, X : STA.l Horse_NorthCacheValid
  PLA
  CMP.b #$01 : BEQ .north_side_hit
  CMP.b #$02 : BEQ .north_side_hit
  .north_side_clr_upd
    LDA.l Horse_NorthCacheRes : AND.l .n_invmask, X : STA.l Horse_NorthCacheRes
    CLC : RTS
  .north_side_hit
    LDA.l Horse_NorthCacheRes : ORA.l .n_mask, X : STA.l Horse_NorthCacheRes
    SEC : RTS

  .north_hit
    LDA.b $64 : ORA.b #$30 : STA.b $64
    LDA.b #$01
    BRA .save_cache
  .no_prio
    LDA.b #$00
    BRA .save_cache
  .pf_hit
  SEP #$20
  LDA.b #$01 : STA.l Horse_PrioFenceCacheRes
  .hit
  LDA.b $64 : ORA.b #$30 : STA.b $64
  LDA.b $65 : ORA.b #$30 : STA.b $65
  LDA.b #$02

  .save_cache
  STA.l Horse_PrioCacheResult
  LDA.b $8A : STA.l Horse_PrioCacheArea
  LDA.l Horse_State : STA.l Horse_PrioCacheState
  REP #$20
  LDA.b $22 : STA.l Horse_PrioCacheX
  LDA.b $20 : STA.l Horse_PrioCacheY
  SEP #$20
  LDA.b #$01 : STA.l Horse_PrioCacheValid

  .restore
  REP #$30
  PLA : STA.b $0E : PLA : STA.b $0C : PLA : STA.b $0A
  PLA : STA.b $08 : PLA : STA.b $06 : PLA : STA.b $04
  PLY : PLX : PLP
  RTS

  .n_dx      : dw $0002, $000D
  .n_mask    : db $01, $00, $02, $00
  .n_invmask : db $FE, $00, $FD, $00
  .xz        : db 0,0,0,0,0,0,1,1,2,2,3,3,3,3,3,3

  .check_row
  LDA.b $0E : ORA.b $08 : JSR .chk_t16 : BCS .row_hit
  LDA.b $0E : ORA.b $0A : JSR .chk_t16 : BCS .row_hit
  LDA.b $0C : CMP.b $0A : BEQ .row_miss
  LDA.b $0E : ORA.b $0C
  .chk_t16
  TAX : LDA.l $7E2000, X : CMP.w #$002C : BCC .row_miss
    STA.b $04 : CPY.b $04 : BEQ .row_miss : CMP.b $06 : BEQ .row_miss
      PHY : SEP #$10 : JSR Horse_IsPriorityFenceTile16 : REP #$10 : PLY : BCS .row_hit
      STY.b $06 : LDY.b $04
  .row_miss
  CLC
  .row_hit
  RTS
}

if not(defined("Horse_FrameCount"))
  !Horse_FrameCount = 19
endif

pushpc
org $53EE90
HorseForm_UpdateAnimFrame_Impl:
{
  LDA.b $10 : CMP.b #9 : BNE .select_frame
  LDA.b $11 : BNE .select_frame
  LDA.l Horse_NpcUploadedFrame : CMP.b #$FF : BEQ .select_frame
  LDA.l Horse_UploadedFrame : CMP.b #!Horse_FrameCount : BCS .select_frame
  STA.l Horse_Frame
  RTS
  .select_frame
  LDA.l Horse_State : BEQ + : BRL .in_jump : +
  LDA.b $25 : BMI .chk_neg_z
    LDA.b $24 : BEQ .check_walk
    BRL .in_jump
  .chk_neg_z
  LDA.b $24 : CMP.b #$F0 : BCS .check_walk
    BRL .in_jump

  .check_walk
  LDA.b $F0 : AND.b #$0F : BEQ .idle
  LDA.l Horse_AnimTimer : INC : STA.l Horse_AnimTimer
  LDA.l Horse_SpurTimer : BEQ +
    LDA.l Horse_AnimTimer : INC : STA.l Horse_AnimTimer
  +
  LDA.b $2F : AND.b #$06 : TAX
  JMP (.walk_dir, X)

  .walk_dir
  dw .walk_up, .walk_down, .walk_left_right, .walk_left_right

  .walk_up
  LDA.l Horse_AnimTimer : LSR #2 : AND.b #$01 : CLC : ADC.b #$04
  STA.l Horse_Frame
  RTS

  .walk_down
  LDA.l Horse_AnimTimer : LSR #2 : AND.b #$01 : CLC : ADC.b #$01
  STA.l Horse_Frame
  RTS

  .walk_left_right
  LDA.l Horse_AnimTimer : CMP.b #24 : BCC +
    LDA.b #$00 : STA.l Horse_AnimTimer
  +
  LSR #2 : TAX
  LDA.l .gallop_cycle, X : STA.l Horse_Frame
  RTS
  .gallop_cycle
  db 7, 8, 9, 16, 17, 18

  .idle
  LDA.b #$00 : STA.l Horse_AnimTimer
  LDA.b $2F : AND.b #$06 : LSR A : TAX
  LDA.l .idle_frames, X : STA.l Horse_Frame
  RTS
  .idle_frames
  db 3, 0, 6, 6

  .in_jump
  LDA.b $2F : AND.b #$06 : LSR A : TAX
  CPX.b #$00 : BEQ .jump_n
  CPX.b #$01 : BEQ .jump_s
    LDA.l Horse_State : BEQ .jump_side_dn
    LDA.l Horse_JumpTimer : LSR : BNE + : LDA.b #$08 : +
    CMP.l Horse_JumpStep : BEQ .jump_side_dn : BCC .jump_side_dn
      LDA.b #$0A : STA.l Horse_Frame
      RTS
    .jump_side_dn
    LDA.b #$0B : STA.l Horse_Frame
    RTS
  .jump_s
  LDA.b #$0C : STA.l Horse_Frame
  RTS
  .jump_n
  LDA.b #$0D : STA.l Horse_Frame
  RTS
}

; Resolves outer-corner hits after an edge scan in HorseForm_ConstrainGroundInput.
HorseClearance_ResolveCorner:
{
  CPX.b #$02 : BCS .slide_we
    LDA.b $0F : AND.b #$03 : BNE .done
    LDA.b $06 : CMP.b #$01 : BNE +
      LDA.b #$01 : JMP HorseClearance_TryNudge  ; left corner -> +X
    +
    CMP.b #$04 : BNE .done
      LDA.b #$00 : JMP HorseClearance_TryNudge  ; right corner -> -X
  .slide_we
    LDA.b $0F : AND.b #$0C : BNE .done
    LDA.b $06 : CMP.b #$01 : BNE +
      LDA.b #$03 : JMP HorseClearance_TryNudge  ; top corner -> +Y
    +
    CMP.b #$08 : BNE .done
      LDA.b #$02 : JMP HorseClearance_TryNudge  ; bottom corner -> -Y
  .done
  RTS
}
assert pc() <= $53EFF0, "Horse anim/corner slice overlapped bush trample ($53F000)"
pullpc

; Emits vanilla-style tall grass ($0351=2 -> $C8/$C9/$CA pal 1) or shallow water
; ($0351=1/3 -> $D8/$D9/$DA pal 2) 8x8 tiles at Epona's hoof line when grounded.
; Respects 12-slot player OAM budget (1 centered tile on 8-part frames, else 2 mirrored).
; Entry: M=16, X=16, DBR=$00, $0D=frame, $00=SX16, $02=SY16, Y=OAM off. Exit: M=16, X=16.
Horse_EmitFootReaction_Long:
{
  SEP #$20
  LDA.w $0351 : BEQ .skip
  LDA.l Horse_State : BNE .skip
  LDA.b $25 : BMI .chk_neg_z
    LDA.b $24 : BNE .skip
    BRA .grounded
  .chk_neg_z
  LDA.b $24 : CMP.b #$F0 : BCS .grounded
  .skip
  REP #$20
  RTL

  .grounded
  LDA.l Horse_AnimTimer : LSR #2
  CMP.b #$03 : BCC + : SBC.b #$03 : +
  STA.b $08
  LDA.w $0351 : CMP.b #$02 : BEQ .grass
    LDA.b #$D8 : CLC : ADC.b $08 : STA.b $0B
    LDA.b $65 : AND.b #$30 : ORA.b #$04
    BRA .have_attr
  .grass
    LDA.b #$C8 : CLC : ADC.b $08 : STA.b $0B
    LDA.b $65 : AND.b #$30 : ORA.b #$02
  .have_attr
  STA.b $0A
  STZ.b $0C

  REP #$20
  LDA.b $02 : CLC : ADC.w #$000C : STA.b $0E
  LDA.b $0D : AND.w #$00FF : TAX
  SEP #$20
  LDA.l HorseFrame_Count, X : CMP.b #$08 : REP #$20 : BEQ .single_slot
    LDA.b $00 : STA.b $08
    JSR HorseOam_WriteSlot
    INY #4
    SEP #$20
    LDA.b $0A : ORA.b #$40 : STA.b $0A
    REP #$20
    LDA.b $00 : CLC : ADC.w #$0008 : STA.b $08
    JSR HorseOam_WriteSlot
    INY #4
    RTL
  .single_slot
  LDA.b $00 : CLC : ADC.w #$0004 : STA.b $08
  JSR HorseOam_WriteSlot
  INY #4
  RTL
}

; Combined bounds check + cached TileType query for HorseForm_ConstrainGroundInput.
; Computes area bounds and $7E2000 Tile16 lookup in one pass before Horse_CgiCache.
; In: M=16, X=8, DBR=$00, $0A=Ypx, $0C=Xpx, $0E=dir*2, Y=pt (0..3).
; Out: M=8, X=8, A=TileType ($00 outside area), $04=Tile16. Preserves X,Y,DBR,$00-$03,$06-$0F.
HorseCgi_QuerySideTile:
{
  PHX
  LDA.b $06 : PHA
  LDA.w $070E : EOR.w #$FFFF : STA.b $04
  LDA.b $0C : LSR #3 : SEC : SBC.w $070C : STA.b $06
  AND.b $04 : AND.w #$FFFE : BNE .outside
  LDA.b $0A : SEC : SBC.w $0708 : STA.b $04
  LDA.w $070A : EOR.w #$FFFF : AND.b $04 : AND.w #$FFF0 : BEQ .inside
  .outside
    STZ.b $04
    PLA : STA.b $06
    SEP #$20
    LDA.b #$00
    PLX
    RTS
  .inside
  LDA.b $04 : AND.w $070A : ASL #3 : STA.b $04
  LDA.b $06 : AND.w $070E : ORA.b $04
  REP #$10 : TAX : LDA.l $7E2000, X : STA.b $04

  SEP #$20
  LDA.l Horse_CgiCacheValid : BNE .cache_ready
    SEP #$10
    LDX.b #120
    LDA.b #$FF
    .init_loop
      STA.l Horse_CgiCache+6, X
      TXA : SEC : SBC.b #8 : TAX
      BPL .init_loop
    REP #$10
    LDA.b #$01 : STA.l Horse_CgiCacheValid
  .cache_ready
  REP #$20
  TYA : AND.w #$0003 : STA.b $06
  LDA.b $0E : AND.w #$0006 : ASL : ORA.b $06 : ASL #3 : TAX

  LDA.b $04 : CMP.l Horse_CgiCache+4, X : BNE .miss
  LDA.b $0C : AND.w #$FFF8 : CMP.l Horse_CgiCache+0, X : BNE .miss
  LDA.b $0A : AND.w #$FFF8 : CMP.l Horse_CgiCache+2, X : BNE .miss
  SEP #$20
  LDA.b $8A : CMP.l Horse_CgiCache+6, X : BNE .miss_m8
  REP #$20
  BRA .done_m16

  .miss
  SEP #$20
  .miss_m8
  PHX
  SEP #$10
  JSR Horse_QueryTileAt
  REP #$10
  PLX
  STA.l Horse_CgiCache+7, X
  LDA.b $8A : STA.l Horse_CgiCache+6, X
  REP #$20
  LDA.b $04 : STA.l Horse_CgiCache+4, X
  LDA.b $0C : AND.w #$FFF8 : STA.l Horse_CgiCache+0, X
  LDA.b $0A : AND.w #$FFF8 : STA.l Horse_CgiCache+2, X
  .done_m16
  PLA : STA.b $06
  SEP #$20
  LDA.l Horse_CgiCache+7, X
  SEP #$10
  PLX
  RTS
}

; Verifies Tile16 ($04) in area $8A has no gap, no fence, and all 4 quadrants != $01/$02.
; Entry: M=16, X=8, DBR=$00, $04=Tile16, $0A=Ypx, $0C=Xpx.
; Exit:  M=16, X=8, C=1 safe, C=0 unsafe; preserves $00-$03, $08-$0F, Y.
Horse_CheckTile16Safe_Long:
{
  PHY : PHX
  SEP #$20
  LDA.l Horse_SafeTile16Valid : BNE .ready
    LDX.b #124
    LDA.b #$FF
    .init
      STA.l Horse_SafeTile16Cache+2, X
      DEX #4 : BPL .init
    LDA.b #$01 : STA.l Horse_SafeTile16Valid
  .ready
  REP #$20
  LDA.b $04 : LSR #4 : EOR.b $04 : AND.w #$001F : ASL #2 : TAX
  LDA.b $04 : CMP.l Horse_SafeTile16Cache+0, X : BNE .miss
  SEP #$20
  LDA.b $8A : CMP.l Horse_SafeTile16Cache+2, X : BNE .miss_m8
    LDA.l Horse_SafeTile16Cache+3, X : CMP.b #$01
    REP #$20
    PLX : PLY
    RTL

  .miss
  SEP #$20
  .miss_m8
  PHX
  REP #$20
  LDA.b $04 : PHA
  JSR HorseLong_IsGap : BCS .not_safe_m16
  JSR Horse_IsFenceTile16 : BCS .not_safe_m16
  PEI ($0A) : PEI ($0C)
  LDY.b #$03
  .quad_loop
    REP #$20
    LDA.b $0C : AND.w #$FFF0
    CPY.b #$01 : BEQ .qx8
    CPY.b #$03 : BNE .qx_ok
    .qx8
      ORA.w #$0008
    .qx_ok
    STA.b $0C
    LDA.b $0A : AND.w #$FFF0
    CPY.b #$02 : BCC .qy_ok
      ORA.w #$0008
    .qy_ok
    STA.b $0A
    SEP #$20
    JSR Horse_QueryTileAt
    CMP.b #$01 : BEQ .quad_bad
    CMP.b #$02 : BEQ .quad_bad
    DEY : BPL .quad_loop
  LDY.b #$01
  BRA .pop_xy
  .quad_bad
  LDY.b #$00
  .pop_xy
  REP #$20
  PLA : STA.b $0C : PLA : STA.b $0A
  BRA .store_res

  .not_safe_m16
  LDY.b #$00

  .store_res
  PLA : STA.b $04
  SEP #$20
  PLX
  TYA : STA.l Horse_SafeTile16Cache+3, X
  LDA.b $8A : STA.l Horse_SafeTile16Cache+2, X
  REP #$20
  LDA.b $04 : STA.l Horse_SafeTile16Cache+0, X
  CPY.b #$01
  PLX : PLY
  RTL
}

assert pc() <= $540000, "Epona overhaul Bank $53 tail exceeded $53FFFF"
pullpc
