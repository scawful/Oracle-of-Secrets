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
; Majora's Mask Overhead Deku Flower-Leaf Propellers (Bank $35 code + Bank $38 GFX)
; Active only while Deku Link (!CurrentMask == #$01) hovers
; ($5D == #$0A, DekuFloating != 0).
; Streams active 16x16 frame (128 B) into Shield VRAM slot
; $4070/$4170 (OAM tile $07) — Deku Link hides Shield and Gust Jar
; cannot run during hover, so zero VRAM conflict.
;
; 12-Frame Directional & 2-Phase Animation (driven by LinkFaceDir $2F, FallTimer $5C, $1A):
;   Front / Back ($2F = $00 Up / $02 Down -> frames 0..5):
;     Phase 1 (FallTimer >= #$50): Steady levitating spin (frames 0..3)
;     Phase 2a ($20..$4F):         End-of-hover flapping (frames 4<->5 every 4f)
;     Phase 2b (< #$20):           Frantic panic flapping (frames 4<->5 every 2f)
;   Side Profile ($2F = $04 Left / $06 Right -> frames 6..11, staggered 3/4 depth):
;     Phase 1 (FallTimer >= #$50): Sleek foreshortened side rotor spin (frames 6..9)
;     Phase 2a/2b (< #$50):        Side-profile fall-flapping (frames 10<->11)
; =========================================================

; Place 12-frame GFX ($0600 = 1,536 B) in Bank $38 tail ($38F800..$38FDFF).
; Wolf Mask ends ~$38F0CD (~1.8 KiB free before $38F800, 512 B free after $38FE00;
; 0 ZScream overlap), keeping Bank $35 Deku code well below Booki/Pols Voice ($35F800).
pushpc
org $38F800
DekuFlowerWingsGfx:
  incbin "Data/graphics/items/deku_flower_wings.4bpp"
DekuFlowerWingsGfxEnd:
assert DekuFlowerWingsGfxEnd-DekuFlowerWingsGfx == $0600, "Deku flower wings GFX must be 12 x 16x16 frames (1536B)"
assert (DekuFlowerWingsGfx>>16) == ((DekuFlowerWingsGfxEnd-1)>>16), "Deku flower wings DMA source crosses bank"
assert pc() <= $390000, "Deku flower wings GFX crossed bank $38"
pullpc

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
  ; 2-phase frame selection (0..5), strictly mirrored in DekuWings_DrawHoverOam:
  ;   FallTimer >= $50 -> spin frames 0..3: ($1A >> 1) & 3
  ;   FallTimer $20..$4F -> flap frames 4..5: 4 + (($1A >> 2) & 1)
  ;   FallTimer <  $20 -> panic flap frames 4..5: 4 + (($1A >> 1) & 1)
  LDA.b FallTimer : CMP.b #$50 : BCS .spin_phase
    CMP.b #$20 : BCC .flap_fast
      LDA.b $1A : LSR #2 : BRA .flap_done
    .flap_fast
    LDA.b $1A : LSR A
    .flap_done
    AND.b #$01 : ORA.b #$04 : BRA .chk_side
  .spin_phase
  LDA.b $1A : LSR A : AND.b #$03

  .chk_side
  ; Select Side Profile frame bank (+6 -> frames 6..11) when facing Left ($04) or Right ($06).
  PHA
  LDA.b LinkFaceDir : AND.b #$04 : BEQ .front_back
    PLA : CLC : ADC.b #$06 : BRA .have_frame
  .front_back
  PLA

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
; Draws twin overhead 16x16 Deku Flower-Leaves in Region C across all 4 facings
; using SP-7 (Deku palette, tile $07):
;   - Up/Down:    Symmetric twin overhead flower-leaves (Slot 0 normal, Slot 1 H-flipped).
;   - Left/Right: Staggered 3/4 side-profile overhead pair (Slot 0 Near in front,
;                 Slot 1 Far shifted back & 2px higher behind; BOTH face flight dir).
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
  ;   Phase 1 (FallTimer >= $50): serene 1px levitation bob ($0F), spread=0 ($0E)
  ;   Phase 2 (FallTimer <  $50): Flap-Up (-2px Y, spread=0) <-> Flap-Down (+2px Y, spread=1)
  LDA.b FallTimer : CMP.b #$50 : BCS .phase_levitate
    CMP.b #$20 : BCC .flap_fast
      LDA.b $1A : LSR #2 : BRA .flap_parity
    .flap_fast
    LDA.b $1A : LSR A
    .flap_parity
    AND.b #$01 : BNE .flap_down
      STZ.b $0E
      LDA.b #$FE ; -2 px on Flap-Up (F4 / S4)
      BRA .have_bob
    .flap_down
    LDA.b #$01 : STA.b $0E ; +-1 px splay on Flap-Down (F5 / S5)
    LDA.b #$02             ; +2 px on Flap-Down (F5 / S5)
    BRA .have_bob

  .phase_levitate
  STZ.b $0E
  LDA.b $1A : LSR #3 : AND.b #$03 : TAX
  LDA.w .bob_y, X

  .have_bob
  STA.b $0F ; signed 8-bit bob_y (-2..+2)

  ; Screen base: $00/$01 = LinkSX16, $02/$03 = BaseSY16 = (LinkY - CamY) - AirZ
  REP #$20
  LDA.b $22 : SEC : SBC.b $E2 : STA.b $00
  LDA.b $20 : SEC : SBC.b $E8
  SEC : SBC.b $06
  STA.b $02
  SEP #$20

  ; Precompute ALL Slot 0 & Slot 1 coordinates and attributes in $00..$09 BEFORE
  ; calling OAM_AllocateFromRegionC, because vanilla $0DBB0A clobbers $0C..$0F.
  ;   $00/$01 = X0, $02/$03 = Y0, $04 = attr0, $05 = attr1, $06/$07 = X1, $08/$09 = Y1.
  LDX.b $0D

  ; Slot 1 Y16 ($08/$09) = BaseSY16 + signext(.dir_dy1[dir] + bob_y)
  LDA.b $0F : CLC : ADC.w .dir_dy1, X : STA.b $08
  BPL .dy1_pos
    LDA.b #$FF : BRA .dy1_hi
  .dy1_pos
  LDA.b #$00
  .dy1_hi
  STA.b $09

  ; Slot 0 Y16 ($0A/$0B -> $02/$03) = BaseSY16 + signext(.dir_dy0[dir] + bob_y)
  LDA.b $0F : CLC : ADC.w .dir_dy0, X : STA.b $0A
  BPL .dy0_pos
    LDA.b #$FF : BRA .dy0_hi
  .dy0_pos
  LDA.b #$00
  .dy0_hi
  STA.b $0B

  REP #$20
  LDA.b $02 : CLC : ADC.b $08 : STA.b $08 ; $08/$09 = Y1
  LDA.b $02 : CLC : ADC.b $0A : STA.b $02 ; $02/$03 = Y0
  SEP #$20

  ; Slot 0 X16 ($0A/$0B -> $00/$01) = LinkSX16 + signext(.dir_dx0[dir] + (spread ? .dir_sp0[dir] : 0))
  LDA.b $0E : BEQ .dx0_nosp
    LDA.w .dir_dx0, X : CLC : ADC.w .dir_sp0, X : BRA .dx0_sign
  .dx0_nosp
  LDA.w .dir_dx0, X
  .dx0_sign
  STA.b $0A
  BPL .dx0_pos
    LDA.b #$FF : BRA .dx0_hi
  .dx0_pos
  LDA.b #$00
  .dx0_hi
  STA.b $0B

  ; Slot 1 X16 ($06/$07) = LinkSX16 + signext(.dir_dx1[dir] + (spread ? .dir_sp1[dir] : 0))
  LDA.b $0E : BEQ .dx1_nosp
    LDA.w .dir_dx1, X : CLC : ADC.w .dir_sp1, X : BRA .dx1_sign
  .dx1_nosp
  LDA.w .dir_dx1, X
  .dx1_sign
  STA.b $06
  BPL .dx1_pos
    LDA.b #$FF : BRA .dx1_hi
  .dx1_pos
  LDA.b #$00
  .dx1_hi
  STA.b $07

  REP #$20
  LDA.b $00 : CLC : ADC.b $06 : STA.b $06 ; $06/$07 = X1
  LDA.b $00 : CLC : ADC.b $0A : STA.b $00 ; $00/$01 = X0
  SEP #$20

  ; BG priority from $EE + Deku SP-7 ($0E), NT=0, plus per-facing slot H-flip
  LDA.b $EE : AND.b #$03 : TAX
  LDA.w .prio_tbl, X : ORA.b #$0E : STA.b $04
  LDX.b $0D
  ORA.w .dir_flip1, X : STA.b $05 ; Slot 1 attr
  LDA.b $04 : ORA.w .dir_flip0, X : STA.b $04 ; Slot 0 attr

  ; Allocate 2 OAM slots (8 B) from Region C (above Link & ground sprites, post-Ancilla safe).
  ; OAM_AllocateFromRegionC leaves Y non-zero and clobbers $0C..$0F; reload Y after JSL.
  LDA.b #$08 : JSL OAM_AllocateFromRegionC

  ; Slot 0 (Left wing on Up/Down; Near/Front flower on Left/Right -> drawn ON TOP)
  REP #$20
  LDA.b $00 : STA.b $0A
  LDA.b $02 : STA.b $0C
  SEP #$20
  LDY.b #$00 : LDX.b #$00
  LDA.b $04
  JSR .emit_wing

  ; Slot 1 (Right wing on Up/Down; Far/Back flower on Left/Right -> drawn BEHIND)
  REP #$20
  LDA.b $06 : STA.b $0A
  LDA.b $08 : STA.b $0C
  SEP #$20
  LDY.b #$04 : LDX.b #$01
  LDA.b $05
  JSR .emit_wing

  .exit
  REP #$20
  PLA : STA.b $0E : PLA : STA.b $0C : PLA : STA.b $0A : PLA : STA.b $08
  PLA : STA.b $06 : PLA : STA.b $04 : PLA : STA.b $02 : PLA : STA.b $00
  SEP #$20
  PLY : PLX
  PLB
  RTL

  ; Emit one 16x16 flower OAM slot with smooth [-15..255] X and [-15..223] Y clipping.
  ; In: A=attr, Y=low OAM offset (0/4), X=high OAM slot (0/1), $0A=X16, $0C=Y16.
  ; Uses $0E=attr, $0F=hi_oam ($02/$03); preserves $00..$09.
  .emit_wing
  STA.b $0E ; attr
  REP #$20
  ; Check Y in [-15..223]: (Y16 + 15) < 239
  LDA.b $0C : CLC : ADC.w #$000F : CMP.w #$00EF : BCS .clip
  ; Check X in [-15..255]
  LDA.b $0A : BPL .x_pos
    CMP.w #$FFF1 : BCC .clip
    SEP #$20
    LDA.b #$03 : STA.b $0F ; 16x16 + X-msb=1
    BRA .write
  .x_pos
  CMP.w #$0100 : BCS .clip
  SEP #$20
  LDA.b #$02 : STA.b $0F ; 16x16, X-msb=0
  BRA .write

  .clip
  SEP #$20
  LDA.b #$00 : STA.b ($90), Y : INY
  LDA.b #$F0 : STA.b ($90), Y : INY
  LDA.b #$07 : STA.b ($90), Y : INY
  LDA.b $0E  : STA.b ($90), Y
  TXA : TAY
  LDA.b #$02 : STA.b ($92), Y
  RTS

  .write
  LDA.b $0A : STA.b ($90), Y : INY
  LDA.b $0C : STA.b ($90), Y : INY
  LDA.b #$07 : STA.b ($90), Y : INY
  LDA.b $0E : STA.b ($90), Y
  TXA : TAY
  LDA.b $0F : STA.b ($92), Y
  RTS

  .bob_y
    db 0, -1, -1, 0
  ; Per-facing overhead Deku Flower-Leaf tables indexed by (LinkFaceDir >> 1) & 3:
  ;   0=Up, 1=Down, 2=Left, 3=Right
  ; Up/Down: symmetric twin overhead flower-leaves (Slot 0 left normal, Slot 1 right H-flipped).
  ; Left/Right: staggered 3/4 side-profile overhead pair (Slot 0 near/front in front,
  ;             Slot 1 far/back shifted back & 2px higher behind; BOTH face flight direction).
  .dir_dx0
    db -13, -13,  -4,   4
  .dir_dx1
    db  13,  13,   3,  -3
  .dir_dy0
    db  -7,  -6,  -8,  -8
  .dir_dy1
    db  -7,  -6, -10, -10
  .dir_sp0
    db  -1,  -1,  -1,   1
  .dir_sp1
    db   1,   1,   1,  -1
  .dir_flip0
    db $00, $00, $00, $40
  .dir_flip1
    db $40, $40, $00, $40
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
