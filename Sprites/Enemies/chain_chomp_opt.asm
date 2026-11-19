; ==============================================================================
; Chain Chomp ($CA) 16-Slot Safety Fix + Hot-Loop Optimization
; ==============================================================================
; Vanilla Sprite_CA_ChainChomp (usdasm bank_1D.asm $1DBE3C..$1DC210) has three
; structural problems:
;   1. ChainChomp_ChainOffset ($1DBE3C) only defines 8 entries ($00..$70) for
;      sprite slots 0..7. Any $CA spawned in slots 8..15 (e.g. Room $0B2's 3rd
;      Chain Chomp at index 9) indexes past the table into SpritePrep_Chainchomp
;      opcodes ($DA, $A0, $05, $BF, $3C, ...), corrupting $7FFC00/$7FFD00 or
;      aliasing another Chomp's chain buffer and breaking .operand indexing.
;   2. ChainChomp_MoveChain ($1DC02A) runs 6 iterations ($0D = 5..0) starting
;      at link +2 (updating +2..+12), reading opcode $BD past .operand on the
;      undrawn 6th link, recomputing abs(dx)/abs(dy) every iteration, and
;      stalling 84 NOPs per call (168 NOPs/frame during lunge).
;   3. ChainChomp_HandleLeash ($1DC0F2) and SpriteDraw_ChainChomp ($1DC1AA)
;      use long WRAM addressing, per-link REP/SEP churn, and per-link OAM index
;      division, making each $CA ~4.5x heavier than ordinary enemies (~30k mc).
;
; This module hooks all four bank-$1D Chain Chomp chain routines cleanly:
;   - Uses (slot << 4) ($00..$F0) in $7FFC00/$7FFD00 so all 16 sprite slots
;     0..15 have disjoint 16-byte buffers (6 links x 2 bytes = 12 bytes/axis).
;   - Pipelines hardware multiplier WRMPYA/WRMPYB across the 5 non-head links
;     ($CD, $9A, $66, $33, $08) with identical arithmetic to vanilla and zero
;     inter-link NOP stalls (>30 CPU cycles between STY $4203 and LDA $4217).
;   - Unrolls leash clamping (links 1..5) and link OAM emission (links 0..5)
;     with DBR=$7F and 16-bit tile+attr writes for bit-identical visuals/physics.
; ==============================================================================

pushpc

; SpritePrep_Chainchomp ($1DBE44, called via JSL from Sprite_Prep, M/X=8).
assert read4($1DBE44) == $BF05A0DA, "SpritePrep_Chainchomp preimage moved"
org $1DBE44 ; @hook module=Sprites name=ChainChomp_PrepLong kind=jml target=ChainChomp_PrepLong expected_m=8 expected_x=8 protected_size=4
  JML ChainChomp_PrepLong
assert pc() == $1DBE48

; ChainChomp_MoveChain ($1DC02A, called via JSR from Meander/Lunge, M/X=8, DBR=$1D).
assert read4($1DC02A) == $850D90BD, "ChainChomp_MoveChain preimage moved"
org $1DC02A ; @hook module=Sprites name=ChainChomp_MoveChainLong kind=jsl target=ChainChomp_MoveChainLong expected_m=8 expected_x=8 protected_size=5
  JSL ChainChomp_MoveChainLong
  RTS
assert pc() == $1DC02F

; ChainChomp_HandleLeash ($1DC0F2, called via JSR from Sprite_CA_ChainChomp, M/X=8, DBR=$1D).
assert read4($1DC0F2) == $BE3CBDDA, "ChainChomp_HandleLeash preimage moved"
org $1DC0F2 ; @hook module=Sprites name=ChainChomp_HandleLeashLong kind=jsl target=ChainChomp_HandleLeashLong expected_m=8 expected_x=8 protected_size=5
  JSL ChainChomp_HandleLeashLong
  RTS
assert pc() == $1DC0F7

; SpriteDraw_ChainChomp chain-link draw tail ($1DC1AA, after head SpriteDraw_SingleLarge_long, M/X=8, DBR=$1D).
assert read4($1DC1AA) == $290E00BD, "SpriteDraw_ChainChomp link tail preimage moved"
org $1DC1AA ; @hook module=Sprites name=ChainChomp_DrawLinksLong kind=jsl target=ChainChomp_DrawLinksLong expected_m=8 expected_x=8 protected_size=5
  JSL ChainChomp_DrawLinksLong
  RTS
assert pc() == $1DC1AF

pullpc

; ------------------------------------------------------------------------------
; 1. ChainChomp_PrepLong (M=8, X=8, X = sprite slot 0..15)
; Initializes all 6 chain links (offsets +0..+$0A) in $7FFC00/$7FFD00 for any
; sprite slot 0..15, then stores anchor coords identically to vanilla.
; ------------------------------------------------------------------------------
ChainChomp_PrepLong:
{
  PHX : PHB
  TXA : ASL #4 : TAX                ; X = slot * $10 ($00..$F0)
  LDA.b #$7F : PHA : PLB            ; DBR = $7F for fast 16-bit WRAM stores
  REP #$20
  LDA.l $7E0FD8
  STA.w $FC00,X : STA.w $FC02,X : STA.w $FC04,X
  STA.w $FC06,X : STA.w $FC08,X : STA.w $FC0A,X
  LDA.l $7E0FDA
  STA.w $FD00,X : STA.w $FD02,X : STA.w $FD04,X
  STA.w $FD06,X : STA.w $FD08,X : STA.w $FD0A,X
  SEP #$20
  PLB : PLX

  LDA.w $0D10,X : STA.w $0D90,X
  LDA.w $0D30,X : STA.w $0DA0,X
  LDA.w $0D00,X : STA.w $0DB0,X
  LDA.w $0D20,X : STA.w $0ED0,X
  RTL
}

; ------------------------------------------------------------------------------
; 2. ChainChomp_HandleLeashLong (M=8, X=8, DBR=$1D, X = sprite slot 0..15)
; Anchors link 0 at ($0FD8, $0FDA) and clamps links 1..5 sequentially within
; [-8, +7] px of their predecessor on each axis (exact vanilla physics).
; ------------------------------------------------------------------------------
macro ChainChomp_ClampLink(base, off, id)
  SEC : SBC.w <base>+<off>,X
  CMP.w #$0008 : BPL .hi_<id>
  CMP.w #$FFF8 : BPL .keep_<id>
    LDA.b $00 : CLC : ADC.w #$0008 : STA.w <base>+<off>,X : STA.b $00 : BRA .end_<id>
  .hi_<id>
    LDA.b $00 : SEC : SBC.w #$0008 : STA.w <base>+<off>,X : STA.b $00 : BRA .end_<id>
  .keep_<id>
    LDA.w <base>+<off>,X : STA.b $00
  .end_<id>
endmacro

ChainChomp_HandleLeashLong:
{
  PHX : PHB
  TXA : ASL #4 : TAX
  LDA.b #$7F : PHA : PLB
  REP #$20

  LDA.l $7E0FD8
  STA.w $FC00,X : STA.b $00
  %ChainChomp_ClampLink($FC00, $02, x1)
  %ChainChomp_ClampLink($FC00, $04, x2)
  %ChainChomp_ClampLink($FC00, $06, x3)
  %ChainChomp_ClampLink($FC00, $08, x4)
  %ChainChomp_ClampLink($FC00, $0A, x5)

  LDA.l $7E0FDA
  STA.w $FD00,X : STA.b $00
  %ChainChomp_ClampLink($FD00, $02, y1)
  %ChainChomp_ClampLink($FD00, $04, y2)
  %ChainChomp_ClampLink($FD00, $06, y3)
  %ChainChomp_ClampLink($FD00, $08, y4)
  %ChainChomp_ClampLink($FD00, $0A, y5)

  SEP #$20
  PLB : PLX
  RTL
}

; ------------------------------------------------------------------------------
; 3. ChainChomp_MoveChainLong (M=8, X=8, DBR=$1D, X = sprite slot 0..15)
; Moves links 1..5 (+$02..+$0A) 1 px toward anchor + (head - anchor) * mult,
; with exact vanilla multipliers ($CD, $9A, $66, $33, $08) and sign math.
; Hardware multiplier WRMPYA ($4202) is written once per axis; WRMPYB ($4203)
; for link k+1 is kicked right after reading RDMPYH ($4217) for link k so the
; 8-cycle hardware latency overlaps completely with link k's 16-bit update.
; ------------------------------------------------------------------------------
macro ChainChomp_StepPos(base, anchor_dp, off, next_mult, id)
  LDA.w $4217
  if <next_mult> != 0
    LDY.b #<next_mult> : STY.w $4203
  endif
  CLC : ADC.b <anchor_dp> : STA.b $08
  LDA.b #$00 : ADC.b <anchor_dp>+1 : STA.b $09
  REP #$20
  LDA.l <base>+<off>,X : CMP.b $08 : BEQ .ok_<id>
  BPL .dec_<id>
    INC A : INC A
  .dec_<id>
    DEC A : STA.l <base>+<off>,X
  .ok_<id>
  SEP #$20
endmacro

macro ChainChomp_StepNeg(base, anchor_dp, off, next_mult, id)
  LDA.w $4217
  if <next_mult> != 0
    LDY.b #<next_mult> : STY.w $4203
  endif
  EOR.b #$FF : CLC : ADC.b <anchor_dp> : STA.b $08
  LDA.b #$FF : ADC.b <anchor_dp>+1 : STA.b $09
  REP #$20
  LDA.l <base>+<off>,X : CMP.b $08 : BEQ .ok_<id>
  BPL .dec_<id>
    INC A : INC A
  .dec_<id>
    DEC A : STA.l <base>+<off>,X
  .ok_<id>
  SEP #$20
endmacro

ChainChomp_MoveChainLong:
{
  LDA.w $0D90,X : STA.b $00
  LDA.w $0DA0,X : STA.b $01
  LDA.w $0DB0,X : STA.b $02
  LDA.w $0ED0,X : STA.b $03

  PHX : PHB
  TXA : ASL #4 : TAX
  LDA.b #$00 : PHA : PLB            ; DBR = $00 -> fast $4202/$4203/$4217

  LDA.l $7FFC00,X : SEC : SBC.b $00 : STA.b $04
  LDA.l $7FFD00,X : SEC : SBC.b $02 : STA.b $05

  ; --- X axis (links 1..5 at $7FFC02..$7FFC0A) ---
  LDA.b $04 : BPL + : BRL .x_neg : +
    STA.w $4202
    LDA.b #$CD : STA.w $4203
    NOP #4
    %ChainChomp_StepPos($7FFC00, $00, $02, $9A, xp1)
    %ChainChomp_StepPos($7FFC00, $00, $04, $66, xp2)
    %ChainChomp_StepPos($7FFC00, $00, $06, $33, xp3)
    %ChainChomp_StepPos($7FFC00, $00, $08, $08, xp4)
    %ChainChomp_StepPos($7FFC00, $00, $0A, $00, xp5)
    BRL .do_y

  .x_neg
    EOR.b #$FF : INC A : STA.w $4202
    LDA.b #$CD : STA.w $4203
    NOP #4
    %ChainChomp_StepNeg($7FFC00, $00, $02, $9A, xn1)
    %ChainChomp_StepNeg($7FFC00, $00, $04, $66, xn2)
    %ChainChomp_StepNeg($7FFC00, $00, $06, $33, xn3)
    %ChainChomp_StepNeg($7FFC00, $00, $08, $08, xn4)
    %ChainChomp_StepNeg($7FFC00, $00, $0A, $00, xn5)

  .do_y
  ; --- Y axis (links 1..5 at $7FFD02..$7FFD0A) ---
  LDA.b $05 : BPL + : BRL .y_neg : +
    STA.w $4202
    LDA.b #$CD : STA.w $4203
    NOP #4
    %ChainChomp_StepPos($7FFD00, $02, $02, $9A, yp1)
    %ChainChomp_StepPos($7FFD00, $02, $04, $66, yp2)
    %ChainChomp_StepPos($7FFD00, $02, $06, $33, yp3)
    %ChainChomp_StepPos($7FFD00, $02, $08, $08, yp4)
    %ChainChomp_StepPos($7FFD00, $02, $0A, $00, yp5)
    BRL .done

  .y_neg
    EOR.b #$FF : INC A : STA.w $4202
    LDA.b #$CD : STA.w $4203
    NOP #4
    %ChainChomp_StepNeg($7FFD00, $02, $02, $9A, yn1)
    %ChainChomp_StepNeg($7FFD00, $02, $04, $66, yn2)
    %ChainChomp_StepNeg($7FFD00, $02, $06, $33, yn3)
    %ChainChomp_StepNeg($7FFD00, $02, $08, $08, yn4)
    %ChainChomp_StepNeg($7FFD00, $02, $0A, $00, yn5)

  .done
  PLB : PLX
  RTL
}

; ------------------------------------------------------------------------------
; 4. ChainChomp_DrawLinksLong (M=8, X=8, DBR=$1D, X = sprite slot 0..15)
; Draws all 6 chain links (OAM slots 1..6) from $7FFC00/$7FFD00 with identical
; screen coords, lunge jitter ($0E00,X & 1), offscreen Y clip ($F0), tile ($8B),
; and attribute (($05 & $F0) | $0D) as vanilla SpriteDraw_ChainChomp.
; Note: Caller DBR ($1D, mirroring WRAM $0000-$1FFF) MUST stay intact so
; ($90),Y and ($92),Y write to the low-WRAM OAM buffers ($7E0800/$7E0A20).
; ------------------------------------------------------------------------------
macro ChainChomp_DrawOneLink(link_off, oam_off, hi_off, id)
  LDA.l $7FFC00+<link_off>,X : SEC : SBC.b $0A
  LDY.b #<oam_off> : STA.b ($90),Y
  AND.w #$0100 : XBA
  SEP #$20
  LDY.b #<hi_off> : STA.b ($92),Y
  REP #$20
  LDA.l $7FFD00+<link_off>,X : SEC : SBC.b $0C
  LDY.b #<oam_off>+1 : STA.b ($90),Y
  CLC : ADC.w #$0010 : CMP.w #$0100 : BCC .vis_<id>
    LDA.w #$00F0 : STA.b ($90),Y
  .vis_<id>
  LDA.b $06 : INY : STA.b ($90),Y
endmacro

ChainChomp_DrawLinksLong:
{
  LDA.w $0E00,X : AND.b #$01 : CLC : ADC.b #$04 : STA.b $08 : STZ.b $09
  LDA.b #$8B : STA.b $06
  LDA.b $05 : AND.b #$F0 : ORA.b #$0D : STA.b $07

  PHX
  TXA : ASL #4 : TAX

  REP #$20
  LDA.b $E2 : SEC : SBC.b $08 : STA.b $0A
  LDA.b $E8 : SEC : SBC.b $08 : STA.b $0C

  %ChainChomp_DrawOneLink($00, $04, $01, l0)
  %ChainChomp_DrawOneLink($02, $08, $02, l1)
  %ChainChomp_DrawOneLink($04, $0C, $03, l2)
  %ChainChomp_DrawOneLink($06, $10, $04, l3)
  %ChainChomp_DrawOneLink($08, $14, $05, l4)
  %ChainChomp_DrawOneLink($0A, $18, $06, l5)

  SEP #$20
  PLX
  RTL
}
