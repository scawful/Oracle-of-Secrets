; =========================================================
; Deku Mask
; Press R to transform into Deku Link
; Press Y to perform a spin and jump, allowing you to hover
; for a short period of time, as well as drop bombs while
; hovering with the Y button, and cancelling the hover with
; the B button.
; =========================================================

UpdateDekuPalette:
{
  REP #$30   ; change 16bit mode
  LDX #$001E

  .loop
  LDA.l deku_palette, X
  PHX
  STA.l TimeState.SubColor
  JSL ColorSubEffect
  PLX
  STA $7EC6E0, X
  DEX : DEX : BPL .loop

  SEP #$30 ; go back to 8 bit mode
  INC $15  ; update the palette
  RTL      ; or RTS depending on where you need it
}

deku_palette:
  dw $6739, $15C5, $150E, $26C9, $17AA, $21F4, $17DF, $42DB
  dw $14A5, $14BC, $14B2, $14A5, $7FFF, $7A18, $178C

; =========================================================
; Majora's Mask Hand-Held Deku Flower Hover Wings (Bank $35)
; Active only while Deku Link (!CurrentMask == #$01) hovers
; ($5D == #$0A, DekuFloating != 0).
; Streams active 16x16 frame (128 B) into Shield VRAM slot
; $4070/$4170 (OAM tile $07) — Deku Link hides Shield and Gust Jar
; cannot run during hover, so zero VRAM conflict.
;
; 2-Phase Hover Animation (driven by FallTimer $5C & $1A):
;   Phase 1 (FallTimer >= #$50): Steady levitating glide (frames 0..3 spin)
;   Phase 2a ($20..$4F):         End-of-hover flapping (frames 4<->5 every 4f)
;   Phase 2b (< #$20):           Frantic panic flapping (frames 4<->5 every 2f)
; =========================================================

DekuFlowerWingsGfx:
  incbin "Data/graphics/items/deku_flower_wings.4bpp"
DekuFlowerWingsGfxEnd:
assert DekuFlowerWingsGfxEnd-DekuFlowerWingsGfx == $0300, "Deku flower wings GFX must be 6 x 16x16 frames (768B)"
assert (DekuFlowerWingsGfx>>16) == ((DekuFlowerWingsGfxEnd-1)>>16), "Deku flower wings DMA source crosses bank"

; Chained at the tail of Horse_NmiUpload ($008B5C).
; Entry: M=8, X=16, DBR=$00; DMA0=$1801, VMAIN=$80.
; Fast-exits in 5 cycles (+RTL) whenever DekuFloating == 0.
; Exit: X, Y, P, DBR preserved; $4304=#$7E & $4302=$0ADC restored.
!DEKU_WINGS_NMI_DEFINED = 1
DekuWings_NmiUpload:
{
  LDA.b DekuFloating : BNE .chk_mask
    RTL
  .chk_mask
  LDA.w !CurrentMask : CMP.b #$01 : BEQ .chk_state
    RTL
  .chk_state
  LDA.b $5D : CMP.b #$0A : BEQ .chk_mod
    RTL
  .chk_mod
  LDA.b $10 : CMP.b #$07 : BEQ .upload
  CMP.b #$09 : BEQ .upload
  CMP.b #$0B : BEQ .upload
    RTL

  .upload
  PHP
  SEP #$20 : REP #$10
  PHX : PHY

  LDA.b #DekuFlowerWingsGfx>>16 : STA.w $4304
  ; 2-phase frame selection (strictly mirrored in DekuWings_DrawHoverOam):
  ;   FallTimer >= $50 -> frames 0..3: ($1A >> 1) & 3
  ;   FallTimer $20..$4F -> frames 4..5: 4 + (($1A >> 2) & 1)
  ;   FallTimer <  $20 -> frames 4..5: 4 + (($1A >> 1) & 1)
  LDA.b FallTimer : CMP.b #$50 : BCS .spin_phase
    CMP.b #$20 : BCC .flap_fast
      LDA.b $1A : LSR #2 : BRA .flap_done
    .flap_fast
    LDA.b $1A : LSR A
    .flap_done
    AND.b #$01 : ORA.b #$04 : BRA .have_frame
  .spin_phase
  LDA.b $1A : LSR A : AND.b #$03
  .have_frame
  REP #$20
  AND.w #$00FF : ASL #7
  CLC : ADC.w #DekuFlowerWingsGfx : TAY

  ; Top row (64 B: TL + TR) -> VRAM word $4070 (OAM tile $07 top)
  LDX.w #$4070 : STX.w $2116
  STY.w $4302
  LDA.w #$0040 : STA.w $4305
  SEP #$20
  LDA.b #$01 : STA.w $420B

  ; Bottom row (64 B: BL + BR) -> VRAM word $4170 (OAM tile $07 bottom)
  REP #$20
  LDX.w #$4170 : STX.w $2116
  TYA : CLC : ADC.w #$0040 : STA.w $4302
  LDA.w #$0040 : STA.w $4305
  SEP #$20
  LDA.b #$01 : STA.w $420B

  ; Cleanly restore DMA0 bank ($7E) and animated BG tile source ($0ADC)
  LDA.b #$7E : STA.w $4304
  REP #$20
  LDA.w $0ADC : STA.w $4302
  SEP #$20

  PLY : PLX
  PLP
  RTL
}

; Post-Ancilla OAM renderer called from DekuLink_SpinOrRecoil (PlayerOam_Main).
; Draws twin hand-held 16x16 Deku Flower Wings in Region C anchored directly
; into Deku Link's hands across all 4 facings using SP-7 (Deku palette, tile $07).
; Entry/Exit: M=8, X=8; preserves DBR, X, Y, and zero-page $00..$0F.
DekuWings_DrawHoverOam:
{
  PHB : PHK : PLB
  PHX : PHY
  REP #$20
  LDA.b $00 : PHA : LDA.b $02 : PHA : LDA.b $04 : PHA : LDA.b $06 : PHA
  LDA.b $08 : PHA : LDA.b $0A : PHA : LDA.b $0C : PHA : LDA.b $0E : PHA
  SEP #$20

  ; Gameplay modules only, no submodule transition, Link visible.
  LDA.b $11 : BNE .exit_near
  LDA.b $10 : CMP.b #$07 : BEQ .mod_ok
  CMP.b #$09 : BEQ .mod_ok
  CMP.b #$0B : BNE .exit_near
  .mod_ok
  LDA.b $4B : CMP.b #$0C : BEQ .exit_near
  LDA.b $55 : BEQ .visible
  .exit_near
  BRL .exit

  .visible
  ; AirZ ($06/$07): $24 when airborne (clamped to 0 if negative sentinel $FFxx >= $F0)
  LDA.b $25 : BMI .neg_z
    LDA.b $24 : BRA .have_z
  .neg_z
  LDA.b $24 : CMP.b #$F0 : BCC .have_z
    LDA.b #$00
  .have_z
  STA.b $06 : STZ.b $07

  ; Facing direction index ($0D = (LinkFaceDir >> 1) & 3: 0=Up, 1=Down, 2=Left, 3=Right)
  LDA.b LinkFaceDir : LSR A : AND.b #$03 : STA.b $0D

  ; 2-phase motion (synchronized with DekuWings_NmiUpload):
  ;   Phase 1 (FallTimer >= $50): serene 1px levitation bob, spread=0
  ;   Phase 2 (FallTimer <  $50): Flap-Up (-2px Y, spread=0) <-> Flap-Down (+2px Y, spread=1)
  LDA.b FallTimer : CMP.b #$50 : BCS .phase_levitate
    CMP.b #$20 : BCC .flap_fast
      LDA.b $1A : LSR #2 : BRA .flap_parity
    .flap_fast
    LDA.b $1A : LSR A
    .flap_parity
    AND.b #$01 : BNE .flap_down
      STZ.b $0E
      LDA.b #$FE ; -2 px on Flap-Up (Frame 4)
      BRA .have_bob
    .flap_down
    LDA.b #$01 : STA.b $0E ; +-1 px outward thrust on Flap-Down (Frame 5)
    LDA.b #$02             ; +2 px on Flap-Down (Frame 5)
    BRA .have_bob

  .phase_levitate
  STZ.b $0E
  LDA.b $1A : LSR #3 : AND.b #$03 : TAX
  LDA.w .bob_y, X

  .have_bob
  ; Total signed vertical offset ($08/$09) = dir_dy[dir] + bob_y (range -2..+4)
  LDX.b $0D
  CLC : ADC.w .dir_dy, X : STA.b $08
  BPL .dy_pos
    LDA.b #$FF : BRA .dy_hi
  .dy_pos
  LDA.b #$00
  .dy_hi
  STA.b $09

  ; Screen base: $00 = LinkSX16, $02 = WingSY16 = (LinkY - CamY) - AirZ + dy_total
  REP #$20
  LDA.b $22 : SEC : SBC.b $E2 : STA.b $00
  LDA.b $20 : SEC : SBC.b $E8
  SEC : SBC.b $06
  CLC : ADC.b $08
  STA.b $02
  SEP #$20

  ; Precompute Left Wing X16 ($06/$07) and Right Wing X16 ($08/$09) BEFORE
  ; calling OAM_AllocateFromRegionC, because vanilla $0DBB0A clobbers $0C..$0F.
  LDX.b $0D
  LDA.w .dir_dx_l, X : SEC : SBC.b $0E : STA.b $06
  BPL .xl_pos
    LDA.b #$FF : BRA .xl_hi
  .xl_pos
  LDA.b #$00
  .xl_hi
  STA.b $07
  LDA.w .dir_dx_r, X : CLC : ADC.b $0E : STA.b $08
  STZ.b $09

  REP #$20
  LDA.b $00 : CLC : ADC.b $06 : STA.b $06
  LDA.b $00 : CLC : ADC.b $08 : STA.b $08
  SEP #$20

  ; BG priority from $EE + Deku SP-7 ($0E), NT=0
  LDA.b $EE : AND.b #$03 : TAX
  LDA.w .prio_tbl, X : ORA.b #$0E : STA.b $04

  ; Allocate 2 OAM slots (8 B) from Region C (above Link & ground sprites, post-Ancilla safe).
  ; OAM_AllocateFromRegionC leaves Y non-zero and clobbers $0C..$0F; reload Y after JSL.
  LDA.b #$08 : JSL OAM_AllocateFromRegionC

  ; Slot 0 (Left hand wing): normal orientation
  REP #$20
  LDA.b $06 : STA.b $0A
  SEP #$20
  LDY.b #$00 : LDX.b #$00
  LDA.b $04
  JSR .emit_wing

  ; Slot 1 (Right hand wing): H-flipped for mirrored hand grip & counter-rotation
  REP #$20
  LDA.b $08 : STA.b $0A
  SEP #$20
  LDY.b #$04 : LDX.b #$01
  LDA.b $04 : ORA.b #$40
  JSR .emit_wing

  .exit
  REP #$20
  PLA : STA.b $0E : PLA : STA.b $0C : PLA : STA.b $0A : PLA : STA.b $08
  PLA : STA.b $06 : PLA : STA.b $04 : PLA : STA.b $02 : PLA : STA.b $00
  SEP #$20
  PLY : PLX
  PLB
  RTL

  ; Emit one 16x16 wing OAM slot with smooth [-15..255] X and [-15..223] Y clipping.
  ; In: A=attr, Y=low OAM offset (0/4), X=high OAM slot (0/1), $0A=X16, $02=Y16.
  .emit_wing
  STA.b $05 ; attr
  REP #$20
  ; Check Y in [-15..223]: (Y16 + 15) < 239
  LDA.b $02 : CLC : ADC.w #$000F : CMP.w #$00EF : BCS .clip
  ; Check X in [-15..255]
  LDA.b $0A : BPL .x_pos
    CMP.w #$FFF1 : BCC .clip
    SEP #$20
    LDA.b #$03 : STA.b $0C ; 16x16 + X-msb=1
    BRA .write
  .x_pos
  CMP.w #$0100 : BCS .clip
  SEP #$20
  LDA.b #$02 : STA.b $0C ; 16x16, X-msb=0
  BRA .write

  .clip
  SEP #$20
  LDA.b #$00 : STA.b ($90), Y : INY
  LDA.b #$F0 : STA.b ($90), Y : INY
  LDA.b #$07 : STA.b ($90), Y : INY
  LDA.b $05  : STA.b ($90), Y
  TXA : TAY
  LDA.b #$02 : STA.b ($92), Y
  RTS

  .write
  LDA.b $0A : STA.b ($90), Y : INY
  LDA.b $02 : STA.b ($90), Y : INY
  LDA.b #$07 : STA.b ($90), Y : INY
  LDA.b $05 : STA.b ($90), Y
  TXA : TAY
  LDA.b $0C : STA.b ($92), Y
  RTS

  .bob_y
    db 0, -1, -1, 0
  ; Per-facing hand anchor offsets indexed by (LinkFaceDir >> 1) & 3: Up, Down, Left, Right
  .dir_dx_l
    db -12, -12, -10, -9
  .dir_dx_r
    db  12,  12,   9, 10
  .dir_dy
    db   0,   2,   2,  2
  .prio_tbl
    db $20, $10, $30, $20
}

print "End of Masks/deku_mask.asm        ", pc
assert pc() >= $358000 && pc() <= $35F800, "Deku mask reached the Booki/Pols Voice sprite slot in bank $35"

; =========================================================

org $07A64B           ; formerly Quake
LinkItem_DekuMask:
{
  ; Don't use magic unless deku form
  LDA.w $02B2 : CMP.b #$01 : BNE .continue
    ; Don't shoot while transform is active
    LDA.w $0C4E : BNE .continue
      JSR Link_CheckNewY_ButtonPress : BCC .continue
        LDA $3A : AND.b #$BF : STA $3A
        LDX.b #$02
        JSR LinkItem_EvaluateMagicCost : BCC .return
          JSL DekuLink_ShootBubbleOrStartHover
          RTS

  .continue
  ; Don't transform while shooting
  LDA.w $0C52 : CMP.b #$0E : BEQ .return
    LDA.b #$01
    JSL Link_TransformMask
  .return
  RTS
}

assert pc() <= $07A6BE

; =========================================================

Link_HandleChangeInZVelocity = $078926
Link_HandleChangeInZVelocity_preset =  $078932

PlaySFX_Set2 = $078028
PlaySFX_Set3 = $07802F

org $07A6BE ; @hook module=Masks
LinkState_UsingQuake:
{
  .anim_step
    db $00, $01, $02, $03
    db $00, $01, $02, $03
    db $10, $10, $00, $00 ; 16

  .anim_timer
    db   5,   5,   5,   5
    db   5,   5,   5,   5
    db   5,   5,   5,  19

  JSR $F514 ; CacheCameraPropertiesIfOutdoors

  STZ.b $27 : STZ.b $28 ; Reset recoil X and Y

  ; SPIN STEP CHECK
  LDA.w LinkSpinStep : CMP.b #$0A : BNE .not_ascending
    LDA.w $0362 : STA.b $29
    LDA.w $0363 : STA.w $02C7
    LDA.w $0364 : STA.b $24

    LDA.b #$02 : STA.b $00 : STA.b $4D

    JSR Link_HandleChangeInZVelocity_preset
    JSL LinkHop_FindArbitraryLandingSpot

    ; Link recoil Z value, hop Z value
    LDA.b LinkRecoilZ : STA.w $0362
    LDA.w $02C7 : STA.w $0363

    ; Z Position of Link
    LDA.b $24 : STA.w $0364 : BMI .still_ascending

      ; End of ASCEND -------------------------------------
      LDY.b #$00 : LDA.b LinkRecoilZ : BPL .done_ascending
        LDY.b #$00 ; Thrust Sword Down OAM Frame Set

      .done_ascending
        STY.w $031C : BRA .exit
      ; ---------------------------------------------------

  .not_ascending
    DEC.b $3D : BPL .special

    .still_ascending
    INC.w LinkSpinStep
    LDX.w LinkSpinStep
    CPX.b #$04 : BNE .skip_swish_sfx
      PHX : LDA.b #$23 : JSR PlaySFX_Set3 : PLX
    .skip_swish_sfx
    CPX.b #$0C : BNE .dont_reset_step
      LDA.b #$0B : STA.w LinkSpinStep
      TAX
    .dont_reset_step
    LDA.w .anim_timer,X : STA.b $3D
    LDA.w .anim_step,X : STA.w $031C

    LDA.w $0324 : BNE .special ; Prevent repeat spellcast check
    CPX.b #$0B : BNE .special ; Animation step check

      ; -------------------------------------------------
      ; Prevent repeat spellcast set
      LDA.b #$01 : STA.w $0324
      LDA.b #$12 : STA.w LinkZ
      LDA.b #$FF : STA.w FallTimer
      LDA.b #$01 : STA.w DekuFloating
      ; -------------------------------------------------

  .exit
  RTS

  .special
  LDA.b DekuFloating : BEQ +
    DEC $5C
    JSL DekuLink_HoverBasedOnInput
  +
  RTS
}

assert pc() <= $07A779

; LinkHop_FindArbitraryLandingSpot
; Allow LinkState 0x0A to use velocity
; Previously would skip velocity for LinkState 0x0A
org $07E38B
  LDA.b $5D : CMP.b #$09
