; =========================================================
; Dream entry effect (!ENABLE_DREAM_ENTRY_FX)
;
; scawful 2026-10-18: the dream start "could use a more trippy undertale vibe
; ... showing off the pendant that triggered it and some like medallion style
; fx". Runs in Maple's hut after the sleep (and the Wisdom narration), once per
; frame from Maple_DreamEntry (maple.asm), which warps when carry is set.
;
;   1-72     the dream's pendant rises from Link, four sparkles circle it, the
;            room starts to sway
;   73-108   three medallion flashes in the pendant's colour, Ether sound; the
;            pendant spins
;   109-188  the sway grows to 22 px, the colours cycle, mosaic, then white
;
; The screen stays white through the warp's fade-out: WarpPad does not touch
; the fixed colour or $99/$9A. DreamFX_RoomLoaded (Part00_RoomSprites, room
; load) puts the hut's colour math back, as if the effect had not run.
;
; Pendant: item receipt graphics $23 (WriteTo4BPPBuffer_item_gfx) go to
; $7EBD40, which NMI uploads with Link's tiles to OBJ chars $24/$25/$34/$35.
; Drawn like AncillaDraw_ItemReceipt: char $24, attr (prop << 1) | $30.
; Sway: HDMA channel 6 writes BG2HOFS and channel 5 BG1HOFS every line, from
; one table rebuilt each frame. Channel 6 also keeps the text shade off; no
; text box is open here. The NMI DMA uses channels 0-4.
; =========================================================

; Vanilla free WRAM $7FF180-$7FF7FF (Core/ram.asm UNUSED_7FF180). The experiment
; scene uses parts of it only inside its own module; 2P uses $7FF400-$7FF5FF,
; the text shade $7FF350-$7FF367.
DreamFX_State   = $7FF180 ; !DreamFX_Running, !DreamFX_Restore, else idle
DreamFX_Timer   = $7FF181 ; frames since the start
DreamFX_Amp     = $7FF182 ; sway amplitude, half pixels
DreamFX_Save99  = $7FF183 ; hut CGWSEL, CGADSUB, COLDATA R/G/B, NOMENU
DreamFX_Save9A  = $7FF184
DreamFX_Save9C  = $7FF185 ; 3 bytes, $9C-$9E
DreamFX_SaveFFC = $7FF188
DreamFX_Row     = $7FF190 ; 32 words: sway offset by line mod 32
DreamFX_Wave    = $7FF600 ; HDMA table: 2 x ($F0, 112 words), $00 ($1C3 bytes)

!DreamFX_Running = $D7
!DreamFX_Restore = $D8

!DreamFX_Flash = 73       ; first flash
!DreamFX_Melt  = 109      ; sway grows, colours cycle
!DreamFX_End   = 189      ; warp

pushpc
org $2BF000
; Bank $2B: the items code ends near $2B9D19; Items/all_items.asm asserts it
; stays below $2BF000.

; Out: carry set = done (warp now). Keeps X.
DreamFX_Run:
{
  PHB : PHK : PLB
  PHX
  SEP #$30
  LDA.l DreamFX_State : CMP.b #!DreamFX_Running : BEQ .running
    JSR DreamFX_Start
  .running
  LDA.l DreamFX_Timer : INC A : STA.l DreamFX_Timer
  CMP.b #!DreamFX_End : BCS .finish
  JSR DreamFX_SetWave
  JSR DreamFX_SetColor
  JSR DreamFX_DrawPendant
  PLX : PLB
  CLC
  RTL

  .finish
  LDA.b $9B : AND.b #$9F : STA.b $9B      ; HDMA channels 5 and 6 off
  LDA.l DreamFX_SaveFFC : STA.w $0FFC
  LDA.b #!DreamFX_Restore : STA.l DreamFX_State
  PLX : PLB
  SEC
  RTL
}

DreamFX_Start:
{
  LDA.b #!DreamFX_Running : STA.l DreamFX_State
  LDA.b #$00 : STA.l DreamFX_Timer : STA.l DreamFX_Amp
  LDA.b $99 : STA.l DreamFX_Save99
  LDA.b $9A : STA.l DreamFX_Save9A
  LDA.b $9C : STA.l DreamFX_Save9C
  LDA.b $9D : STA.l DreamFX_Save9C+1
  LDA.b $9E : STA.l DreamFX_Save9C+2
  LDA.w $0FFC : STA.l DreamFX_SaveFFC
  LDA.b #$01 : STA.w $0FFC                ; no menu during the effect
  ; Fixed colour math everywhere, added to BG1, BG2, OBJ and backdrop (not
  ; BG3: the HUD stays). Black for now.
  STZ.b $99
  LDA.b #$33 : STA.b $9A
  LDA.b #$20 : STA.b $9C
  LDA.b #$40 : STA.b $9D
  LDA.b #$80 : STA.b $9E

  LDA.b #$23                             ; item receipt: pendant
  if !ENABLE_MOON_PEARL_DREAM == 1
    LDY.w CurrentDream : CPY.b #!DreamZelda_Id : BNE +
      LDA.b #$1F                         ; Moon Pearl, not a fourth pendant
    +
  endif
  JSL $00D4ED                            ; WriteTo4BPPBuffer_item_gfx

  ; HDMA: write-twice mode, direct, from the table in bank $7F.
  LDA.b #$02 : STA.w $4350 : STA.w $4360
  LDA.b #$0D : STA.w $4351                ; channel 5: BG1HOFS
  LDA.b #$0F : STA.w $4361                ; channel 6: BG2HOFS
  LDA.b #DreamFX_Wave>>0  : STA.w $4352 : STA.w $4362
  LDA.b #DreamFX_Wave>>8  : STA.w $4353 : STA.w $4363
  LDA.b #DreamFX_Wave>>16 : STA.w $4354 : STA.w $4364
  LDA.b #$F0 : STA.l DreamFX_Wave : STA.l DreamFX_Wave+$E1 ; 112 lines each
  LDA.b #$00 : STA.l DreamFX_Wave+$1C2
  JSR DreamFX_BuildWave                   ; amplitude 0: the plain scroll
  ; The table holds BG2's scroll. BG1 shares it when both scroll together.
  LDA.b #$40 : STA.b $00
  REP #$20
  LDA.w $0120 : CMP.w $011E
  SEP #$20
  BNE +
    LDA.b #$60 : STA.b $00
  +
  LDA.b $9B : ORA.b $00 : STA.b $9B
  RTS
}

; Amplitude by beat, then the table.
DreamFX_SetWave:
{
  LDA.l DreamFX_Timer
  CMP.b #!DreamFX_Melt : BCS .melt
    LSR #5 : ASL A                        ; 0-3 px
    BRA .set
  .melt
    SEC : SBC.b #!DreamFX_Melt
    LSR A : CLC : ADC.b #$06              ; 3 px, then +1 px every 4 frames
  .set
  STA.l DreamFX_Amp
  ; Fall through.
}

; Each line = BG2 scroll + amplitude * sin(line + 2t) (period 32 lines).
DreamFX_BuildWave:
{
  LDA.l DreamFX_Amp : STA.b $0F
  LDX.b #$3E
  .row
    JSR DreamFX_MulSine
    REP #$20
    AND.w #$00FF : CMP.w #$0080 : BCC +
      ORA.w #$FF00
    +
    STA.l DreamFX_Row, X
    SEP #$20
    DEX : DEX : BPL .row

  REP #$30
  LDA.w $011E : STA.b $00                 ; what NMI writes to BG2HOFS
  LDA.l DreamFX_Timer : ASL #2 : AND.w #$003E : TAX
  LDY.w #$0001
  PEA.w $7F7F : PLB : PLB
  .line
    LDA.w DreamFX_Row&$FFFF, X : CLC : ADC.b $00 : STA.w DreamFX_Wave&$FFFF, Y
    INX : INX : TXA : AND.w #$003E : TAX
    INY : INY
    CPY.w #$00E1 : BNE +
      INY                                 ; second block's line count
    +
    CPY.w #$01C2 : BCC .line
  PHK : PLB
  SEP #$30
  RTS
}

; COLDATA mirrors $9C-$9E: medallion flashes, then cycling colours and white.
DreamFX_SetColor:
{
  LDA.l DreamFX_Timer
  CMP.b #!DreamFX_Flash : BCC .done
  CMP.b #!DreamFX_Melt : BCS .melt
    SEC : SBC.b #!DreamFX_Flash           ; 0-35
    BNE +
      JSL $0DBB67                         ; Link_CalculateSFXPan
      ORA.b #$26 : STA.w $012F            ; SFX3.26, the Ether medallion
      LDA.b #$00
    +
    - CMP.b #12 : BCC + : SBC.b #12 : BRA - : +
    TAX
    LDA.w .flash, X : STA.b $00           ; the pendant's channel
    LSR #2 : STA.b $01                    ; the other two
    LDY.w CurrentDream                    ; 0 Wisdom red, 1 Power blue, 2 Courage green
    LDA.b $01 : CPY.b #$00 : BNE + : LDA.b $00 : +
    ORA.b #$20 : STA.b $9C
    LDA.b $01 : CPY.b #$02 : BNE + : LDA.b $00 : +
    ORA.b #$40 : STA.b $9D
    LDA.b $01 : CPY.b #$01 : BNE + : LDA.b $00 : +
    ORA.b #$80 : STA.b $9E
  .done
    RTS

  .melt
  SEC : SBC.b #!DreamFX_Melt : STA.b $02  ; 0-79
  SEC : SBC.b #48 : BCS +                 ; white: 0, then +2 a frame from 48
    LDA.b #$00
  +
  ASL A : STA.b $03
  LDA.b $02 : ASL A            : JSR .channel : ORA.b #$20 : STA.b $9C
  LDA.b $02 : ASL A : ADC.b #22 : JSR .channel : ORA.b #$40 : STA.b $9D
  LDA.b $02 : ASL A : ADC.b #42 : JSR .channel : ORA.b #$80 : STA.b $9E
  ; Mosaic on BG1/BG2 from 40 frames in, size +1 every 4 frames, up to 7.
  LDA.b $02 : SEC : SBC.b #40 : BCC .no_mosaic
    LSR #2 : CMP.b #$08 : BCC +
      LDA.b #$07
    +
    ASL #4 : ORA.b #$03 : STA.b $95
  .no_mosaic
  RTS

  ; A = sine word index. Out: 0-7 cycle plus white ($03), at most 31.
  .channel
  AND.b #$3E : TAX
  LDA.w DreamFX_Sine, X : CLC : ADC.b #$80 : LSR #5
  CLC : ADC.b $03 : CMP.b #$20 : BCC +
    LDA.b #$1F
  +
  RTS

  .flash ; one flash, 12 frames
  db 28, 22, 16, 11, 7, 4, 2, 1, 0, 0, 0, 0
}

; The pendant over Link and four sparkles around it (5 OAM entries, region C:
; in front of everything).
DreamFX_DrawPendant:
{
  REP #$20
  LDA.b $22 : SEC : SBC.b $E2 : STA.b $04 ; Link on screen
  LDA.b $20 : SEC : SBC.b $E8 : STA.b $06
  SEP #$20
  ; Rise from Link's chest 1/4 px a frame, 16 px at most (the bed is just
  ; under the HUD), with a 0-3 px bob.
  LDA.l DreamFX_Timer : CMP.b #64 : BCC +
    LDA.b #64
  +
  LSR #2 : STA.b $08
  LDA.l DreamFX_Timer : ASL A : AND.b #$3E : TAX
  LDA.w DreamFX_Sine, X : CLC : ADC.b #$80 : LSR #6 : STA.b $09
  LDA.b $06 : CLC : ADC.b #2 : SEC : SBC.b $08 : CLC : ADC.b $09 : STA.b $0A

  LDX.w CurrentDream : LDA.w .prop, X : STA.b $0B
  LDA.l DreamFX_Timer : CMP.b #!DreamFX_Flash : BCC +
    AND.b #$04 : BEQ +
      LDA.b $0B : ORA.b #$40 : STA.b $0B  ; spin: h-flip every 4 frames
  +

  LDA.b #$14 : JSL OAM_AllocateFromRegionC
  LDY.b #$00
  LDA.b $04 : STA.b ($90), Y : INY
  LDA.b $0A : STA.b ($90), Y : INY
  LDA.b #$24 : STA.b ($90), Y : INY
  LDA.b $0B : STA.b ($90), Y : INY
  LDA.b $05 : AND.b #$01 : ORA.b #$02 : STA.b ($92) ; 16x16

  ; Sparkles: radius 12 px, a quarter turn apart, one turn per 32 frames.
  LDA.b $0B : AND.b #$BF : STA.b $0B
  LDA.b #24 : STA.b $0F
  .sparkle
    TYA : ASL #2 : STA.b $0C
    LDA.l DreamFX_Timer : ASL A : CLC : ADC.b $0C : AND.b #$3E : STA.b $0C
    CLC : ADC.b #$10 : AND.b #$3E : TAX   ; cosine
    JSR DreamFX_MulSine
    CLC : ADC.b $04 : CLC : ADC.b #$04 : STA.b ($90), Y : INY
    LDX.b $0C
    JSR DreamFX_MulSine
    CLC : ADC.b $0A : CLC : ADC.b #$04 : STA.b ($90), Y : INY
    LDA.b #$92 : STA.b ($90), Y : INY     ; sword-up sparkle
    LDA.b $0B : STA.b ($90), Y : INY
    PHY
    TYA : LSR #2 : DEC A : TAY
    LDA.b #$00 : STA.b ($92), Y           ; 8x8
    PLY
    CPY.b #$14 : BCC .sparkle
  RTS

  .prop ; by CurrentDream: the hut's OBJ palettes 1 red, 2 blue, 4 green
  db $32, $34, $38
  if !ENABLE_MOON_PEARL_DREAM == 1
    db $34 ; Moon Pearl: normal item-receipt palette 2
  endif
}

; Part00_RoomSprites, end of every room's sprite list (before the fade-in).
DreamFX_RoomLoaded:
{
  LDA.l DreamFX_State : CMP.b #!DreamFX_Restore : BNE .done
    LDA.l DreamFX_Save99   : STA.b $99
    LDA.l DreamFX_Save9A   : STA.b $9A
    LDA.l DreamFX_Save9C   : STA.b $9C
    LDA.l DreamFX_Save9C+1 : STA.b $9D
    LDA.l DreamFX_Save9C+2 : STA.b $9E
    LDA.b #$00 : STA.l DreamFX_State
  .done
  RTL
}

; In: X = sine word index, $0F = factor. Out: A = sine * factor / 256, signed.
; CPU multiplier: the Mode 7 one shares its write latch with BG1HOFS, which
; HDMA channel 5 writes every line.
DreamFX_MulSine:
{
  LDA.w DreamFX_Sine+1, X : STA.b $0E     ; $FF when negative
  LDA.w DreamFX_Sine, X : BPL +
    EOR.b #$FF : INC A
  +
  STA.w $4202
  LDA.b $0F : STA.w $4203
  NOP #4                                  ; product after 8 cycles
  LDA.w $4217
  BIT.b $0E : BPL +
    EOR.b #$FF : INC A
  +
  RTS
}

; sin(2 pi k / 32) * 127, as words (8-bit reads take the signed low byte).
DreamFX_Sine:
  dw 0, 25, 49, 71, 90, 106, 117, 125
  dw 127, 125, 117, 106, 90, 71, 49, 25
  dw 0, -25, -49, -71, -90, -106, -117, -125
  dw -127, -125, -117, -106, -90, -71, -49, -25

assert pc() <= $2C0000, "Dream entry FX left bank $2B"
pullpc
