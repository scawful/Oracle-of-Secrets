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
; =========================================================

!Horse_MountedEnemyCap = 1

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

  SEP #$20
  LDA.b $08 : STA.w $0800, Y        ; X low
  LDA.b $0E : STA.w $0801, Y        ; Y
  LDA.b $0B : STA.w $0802, Y        ; tile
  LDA.b $0A : STA.w $0803, Y        ; attr

  LDA.b $09 : AND.b #$01              ; high bit of Screen X ($08/$09)
  ORA.b $0C                           ; size bit ($02 or $00)
  PHA
  REP #$20
  TYA : LSR #2 : TAX
  SEP #$20
  PLA : STA.w $0A20, X
  REP #$20
  RTS

  .offscreen
  SEP #$20
  LDA.b #$F0 : STA.w $0801, Y
  REP #$20
  TYA : LSR #2 : TAX
  SEP #$20
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
  LDA.b $0D : AND.w #$00FF : ASL #3 : TAX
  .loop
    PHX
    SEP #$20
    LDA.l HorsePiece_X, X : STA.b $08
    LDA.l HorsePiece_Y, X : STA.b $09
    TXA : AND.b #7 : STA.b $0C                ; $0C = part index (0..7)
    REP #$20 : LDA.b $0D : AND.w #$00FF : TAX : SEP #$20
    LDA.l HorseFrame_Count, X : CMP.b #8 : BNE .chr_direct
    LDA.b $0C : CMP.b #4 : BEQ .narrow_p4
    BCC .chr_direct                           ; 8-part 0..3 -> 0..3
      DEC                                     ; 8-part 5,6,7 -> HorseMounted_Chr[4,5,6]
      BRA .chr_load
    .narrow_p4
      JSR Horse_EmitPart4Narrow
      BRA .part_done
    .chr_direct
    LDA.b $0C
    .chr_load
    REP #$20 : AND.w #$00FF : TAX : SEP #$20
    LDA.l HorseMounted_Chr, X : STA.b $0B
    LDA.b #$06 : STA.b $0A
    LDA.b $2F : CMP.b #4 : BNE .not_flip
      REP #$20 : LDA.b $0D : AND.w #$00FF : TAX : SEP #$20
      LDA.l HorseFrame_Width, X : SEC : SBC.b #16 : SEC : SBC.b $08 : STA.b $08
      LDA.b #$46 : STA.b $0A
    .not_flip
    LDA.b $09 : BEQ .upper_prio : BMI .upper_prio
      LDA.b $0A : ORA.b $65 : BRA +
    .upper_prio
      LDA.b $0A : ORA.b $64
    +
    STA.b $0A
    LDA.b #2 : STA.b $0C
    LDA.b $09 : PHA
    REP #$20
    LDA.b $08 : AND.w #$00FF
    BIT.w #$0080 : BEQ + : ORA.w #$FF00 : +
    CLC : ADC.b $04 : STA.b $08
    SEP #$20 : PLA : REP #$20 : AND.w #$00FF
    BIT.w #$0080 : BEQ + : ORA.w #$FF00 : +
    CLC : ADC.b $06 : STA.b $0E
    JSR HorseOam_WriteSlot
    INY #4
    .part_done
    PLX : INX
    REP #$20 : TXA : AND.w #7 : BEQ .done
    STA.b $08
    PHX
    LDA.b $0D : AND.w #$00FF : TAX
    LDA.b $08 : SEP #$20 : CMP.l HorseFrame_Count, X : REP #$20
    PLX : BCS .done
    BRL .loop
    .done
  RTS
}

; Resolves outer-corner hits after an edge scan in HorseForm_ConstrainGroundInput.
; In: M=8, X=8, DBR=$00, X=dir (0=N,1=S,2=W,3=E), $06=blocked corner mask, $0F=orig pad.
; Out: M=8, X=8; preserves X; nudges $22/$20 by 1px when single-corner & orthogonal.
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

; Safe 1px orthogonal corner-slide nudge for HorseForm_ConstrainGroundInput.
; Called ONLY when a single outer corner probe hit a solid tile while all middle
; probes and the opposite corner were clear and the perpendicular axis is idle.
; In:  M=8, X=8, DBR=$00, A = nudge index (0=-X, 1=+X, 2=-Y, 3=+Y).
; Out: M=8, X=8; nudges $22 or $20 by +-1 px ONLY if candidate feet are
;      walkable inside the current area and neither the flank nor footprint
;      hits a solid ($01/$02) tile. Preserves X/Y; clobbers A, $04, $08-$0C.
HorseClearance_TryNudge:
{
  PHX : PHY
  ASL : TAX                           ; X = 0 (-X), 2 (+X), 4 (-Y), 6 (+Y)
  REP #$20
  LDA.b $22 : CLC : ADC.l .step_x, X : STA.b $08 ; $08 = candX
  LDA.b $20 : CLC : ADC.l .step_y, X : STA.b $06 ; $06 = candY

  ; Check 1: candidate foot center (candX+8, candY+12) must be inside current
  ; area and walkable (HorseWalkableAttr == 1: rejects water, pits, ledges, solids).
  LDA.b $08 : CLC : ADC.w #$0008 : STA.b $0C
  LDA.b $06 : CLC : ADC.w #$000C : STA.b $0A
  JSR HorseForm_ConstrainGroundInput_point_outside_area : BCS .abort_a16
  SEP #$20
  JSR Horse_QueryTileAt               ; X preserved, A = tiletype
  CMP.b #$58 : BCS .abort
  PHX : TAX : LDA.l HorseWalkableAttr, X : PLX
  CMP.b #$00 : BEQ .abort

  ; Check 2: flank leading point in nudge direction must not be solid $01/$02.
  REP #$20
  LDA.b $08 : CLC : ADC.l .flank_x, X : STA.b $0C
  LDA.b $06 : CLC : ADC.l .flank_y, X : STA.b $0A
  JSR HorseForm_ConstrainGroundInput_query_side ; M8, A = attr (clear if outside area)
  CMP.b #$01 : BEQ .abort
  CMP.b #$02 : BEQ .abort

  ; Check 3: native Link footprint edge in nudge direction must not be solid $01/$02.
  REP #$20
  LDA.b $08 : CLC : ADC.l .foot_x, X : STA.b $0C
  LDA.b $06 : CLC : ADC.l .foot_y, X : STA.b $0A
  JSR HorseForm_ConstrainGroundInput_query_side
  CMP.b #$01 : BEQ .abort
  CMP.b #$02 : BEQ .abort

  ; Safe to apply 1px corner-slide nudge without changing facing $2F.
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

; Smoothly caps ordinary hostile overworld patrol enemies to !Horse_MountedEnemyCap
; while mounted in settled Module $09 Overworld play (outside minigame/cutscenes).
; Excess patrol enemies are cleared via STZ $0DD0,X while leaving their $7FEF80
; alive bit set so Overworld_LoadSprites will not thrash-respawn them until area reload.
; In/Out: M=8, X=8, DBR=$00. Preserves X/Y/DBR; A clobbered.
HorseForm_ThrottleHostiles:
{
  LDA.b $10 : CMP.b #$09 : BNE .exit
  LDA.b $11 : BNE .exit
  LDA.l HorseGame_State : BNE .exit
  LDA.l InCutScene : BNE .exit
  PHX : PHY
  LDY.b #$00                          ; Y = count of kept ordinary hostile enemies
  LDX.b #$0F
  .slot
    JSR Horse_IsThrottleableHostile : BCC .next
    CPY.b #!Horse_MountedEnemyCap : BCC .keep
      STZ.w $0DD0, X                  ; despawn excess patrol enemy cleanly
      BRA .next
    .keep
    INY
  .next
    DEX : BPL .slot
  PLY : PLX
  .exit
  RTS
}

; Strict hostility & whitelist filter for mounted overworld enemy throttling.
; In:  M=8, X=8, DBR=$00, X = sprite slot (0..15).
; Out: C=1 ONLY if slot X is an active ordinary hostile overworld patrol enemy.
; Preserves X and Y; A clobbered.
Horse_IsThrottleableHostile:
{
  LDA.w $0DD0, X : CMP.b #$09 : BNE .no       ; active state $09 only
  LDA.w $0E40, X : BMI .no                    ; !Harmless (bit 7): NPCs, pickups, props
  LDA.w $0E60, X : AND.b #$40 : BNE .no       ; !ImperviousAll (bit 6): invuln NPCs/statues/doors
  LDA.w $0B6B, X : AND.b #$02 : BNE .no       ; !Boss (bit 1): bosses
  LDA.w $0F60, X : AND.b #$60 : BNE .no       ; !Statis ($40) / !Persist ($20)
  LDA.w $0CAA, X : AND.b #$A0 : BNE .no       ; runtime Persist ($80, incl. archery targets) / !Statue ($20)
  LDA.w $0BA0, X : BNE .no                    ; SprBulletproof: fairies, invuln NPCs, Epona
  LDA.w $0E20, X : CMP.b #$D8 : BCS .no       ; $D8-$FF: pickups, drops, fairies, keys, hearts, objects
  PHX
  LDX.b #(Horse_ProtectedSpriteIds_End-Horse_ProtectedSpriteIds)-1
  .chk
    CMP.l Horse_ProtectedSpriteIds, X : BEQ .protected
    DEX : BPL .chk
  PLX
  SEC
  RTS
  .protected
  PLX
  .no
  CLC
  RTS
}

; Explicit protection table covering every vanilla & Oracle of Secrets NPC,
; talker, quest actor, follower, boss, switch, portal, and benign creature
; (including those with Harmless=0 or Boss=0 in property tables).
Horse_ProtectedSpriteIds:
  db $03 ; Sprite_Portal
  db $07 ; Sprite_BeanVendor / VillageElder / Pull Switch
  db $0A ; Sprite_EonOwl / KaeporaGaebora
  db $0B ; Cucco
  db $0E ; Piratian NPC
  db $14 ; Sprite_BusinessScrub / Grate
  db $22 ; Tingle
  db $25 ; Sprite_VillageDog
  db $2A ; Sweeping Lady
  db $2D ; Horse NPC / Fishing Floater
  db $3C ; Ranch Kid / Kid in Kakariko
  db $51 ; Armos Statue
  db $52 ; Collectible / King Zora
  db $59 ; Lost Woods Bird
  db $5A ; Lost Woods Squirrel
  db $6C ; Mirror Portal
  db $73 ; Sprite_Farore
  db $74 ; Runner
  db $77 ; Sprite_DekuLeaf
  db $79 ; Bee
  db $7A ; Sprite_Kydreeok
  db $88 ; Sprite_Manhandla
  db $8E ; Sprite_SwapDiamond
  db $A9 ; Sprite_Wolfos miniboss
  db $AC ; Apple
  db $B0 ; Sprite_SwitchTrack
  db $B2 ; Windmill Guy / Good Bee
  db $C1 ; Sprite_DarkLink
  db $C3 ; Sprite_D8Boss
  db $CB ; Sprite_KydrogBoss
  db $CE ; Sprite_Twinrova
  db $CF ; Sprite_KydreeokHead
  db $D3 ; Sprite_Ganondorf
Horse_ProtectedSpriteIds_End:
