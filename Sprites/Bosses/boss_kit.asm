; =========================================================
; BossKit: shared boss code
;
; A frame load meter, garnish FX that never steal a live slot, a drifting
; trail attack, a 4-link chain draw (necks, tails) and an earthquake.
; Twinrova, Kydreeok, the vampire bat and fire keese use it.
; Replaces the Trinexx-derived helpers that used to live in
; Core/sprite_functions.asm (Sprite_Twinrova_FireAttack/IceAttack,
; AddFireGarnish, AddIceGarnishV2, TrinexxBreath_AltEntry).
;
; Budget rules every boss follows:
;   1. The director sprite (one per fight) calls BossKit_FrameEnd once per
;      frame, after its own work. It samples the PPU line counter.
;   2. Starting new work (an attack, a take-off, debris) asks
;      BossKit_CanSpend first. Work already running always finishes.
;   3. Garnish FX are capped per parent sprite and skip when no slot is free.
;
; Calling convention: JSL, 8-bit A/X/Y, X = the calling sprite (kept).
; Scratch: $00-$0F.
; =========================================================

; WRAM $7FF380-$7FF384: vanilla-free UNUSED_7FF180 block (Core/symbols.asm).
BossKit_LoadLine  = $7FF380 ; lines after NMI at the last sample, $FF = past the next NMI
BossKit_LoadPeak  = $7FF381 ; highest sample since BossKit_Reset
BossKit_Shed      = $7FF382 ; frames left that refuse new work
BossKit_ShedCount = $7FF383 ; samples over the soft line since BossKit_Reset (wraps)
BossKit_Quake     = $7FF384 ; frames of earthquake left; store a length to start one

; NMI starts on line 225 and the frame has 262 lines. A sample past the soft
; line leaves too little time for garnish, HUD and OAM work before the next NMI.
; Kydreeok 2026-10-19: the sample sits about 31 lines before the main loop
; ends (meter peak 182, frame end max 213), so 205 sheds near line 236.
!BossKit_SoftLine  = 205
; A frame that ran past the next NMI samples a small number of lines; nothing
; in sprite processing runs this early in a frame that started on time.
!BossKit_WrapFloor = 48
!BossKit_ShedTime  = 24
!BossKit_TrailLife = $50
; Native ice plots its floor tile at $50 after decrementing its lifetime.
; Preserve the pre-BossKit $7F start so that threshold remains reachable.
!BossKit_IceTrailLife = $7F

; 16-bit A: sign-extend the low byte.
macro BossKit_Sext16()
  AND.w #$00FF : EOR.w #$0080 : SEC : SBC.w #$0080
endmacro

BossKit_Reset:
{
  LDA.b #$00
  STA.l BossKit_LoadLine : STA.l BossKit_LoadPeak
  STA.l BossKit_Shed : STA.l BossKit_ShedCount
  STA.l BossKit_Quake
  RTL
}

; Carry set: new work may start. Carry clear: shed it this frame.
BossKit_CanSpend:
{
  LDA.l BossKit_Shed : BEQ .yes
    CLC
    RTL
  .yes
  SEC
  RTL
}

BossKit_FrameEnd:
{
  PHX
  LDA.w $2137                  ; latch the H/V counters (WRIO bit 7 is set)
  LDA.w $213F                  ; reset the OPVCT low/high flip-flop
  LDA.w $213D : STA.b $00      ; V counter bits 0-7
  LDA.w $213D : AND.b #$01 : STA.b $01 ; V counter bit 8
  REP #$20
  LDA.b $00 : SEC : SBC.w #225 : BCS .after_nmi
    CLC : ADC.w #262
  .after_nmi
  CMP.w #!BossKit_WrapFloor : BCS .in_frame
    LDA.w #$00FF
  .in_frame
  CMP.w #$0100 : BCC .fits
    LDA.w #$00FF
  .fits
  SEP #$20
  STA.l BossKit_LoadLine
  CMP.l BossKit_LoadPeak : BCC .not_peak
    STA.l BossKit_LoadPeak
  .not_peak
  CMP.b #!BossKit_SoftLine : BCC .light
    LDA.b #!BossKit_ShedTime : STA.l BossKit_Shed
    LDA.l BossKit_ShedCount : INC A : STA.l BossKit_ShedCount
    BRA .quake
  .light
  LDA.l BossKit_Shed : BEQ .quake
    DEC A : STA.l BossKit_Shed

  .quake
  LDA.l BossKit_Quake : BEQ .done
    DEC A : STA.l BossKit_Quake : BNE .shake
      REP #$20
      STZ.w $011A : STZ.w $011C
      SEP #$20
      BRA .done
    .shake
    ; Vanilla earthquake offsets (Dark Link uses the same table).
    REP #$20
    LDA.b $1A : AND.w #$0001 : ASL A : TAX
    LDA.l $01C961, X : STA.w $011A
    LDA.l $01C965, X : STA.w $011C
    SEP #$20
  .done
  PLX
  RTL
}

; ---------------------------------------------------------
; Garnish FX

; A = garnish ID, $08 = lifetime, $09 = cap of live garnishes for this parent.
; Spawns at the sprite: X, Y+$10 (vanilla trail spot). Carry set if spawned.
BossKit_FxAtSprite:
{
  PHA
  STZ.b $00
  LDA.b #$10 : STA.b $01
  PLA
}
; A = garnish ID, $00/$01 = signed X/Y offset from the sprite,
; $08 = lifetime, $09 = cap. Carry set if spawned.
BossKit_FxAtOffset:
{
  PHA
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  STA.b $04
  LDA.b $00 : AND.w #$00FF : CMP.w #$0080 : BCC .x_positive
    ORA.w #$FF00
  .x_positive
  CLC : ADC.b $04 : STA.b $04
  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  STA.b $06
  LDA.b $01 : AND.w #$00FF : CMP.w #$0080 : BCC .y_positive
    ORA.w #$FF00
  .y_positive
  CLC : ADC.b $06 : STA.b $06
  SEP #$20
  PLA
}
; A = garnish ID, $04/$05 = X, $06/$07 = Y, $08 = lifetime, $09 = cap.
; Never steals a live slot. Carry set if spawned.
BossKit_SpawnFx:
{
  STA.b $0A
  PHX
  STX.b $0B                    ; parent slot
  STZ.b $0C                    ; live garnishes owned by this parent
  LDY.b #$FF                   ; free slot found, $FF = none
  LDX.b #$1D
  .scan
    LDA.l $7FF800, X : BNE .live
      TXY
      BRA .next
    .live
    LDA.l $7FF92C, X : CMP.b $0B : BNE .next
      INC.b $0C
  .next
  DEX : BPL .scan

  LDA.b $0C : CMP.b $09 : BCS .refused
  TYA : BMI .refused
  TAX
  LDA.b $0A : STA.l $7FF800, X : STA.w $0FB4
  LDA.b $0B : STA.l $7FF92C, X
  LDA.b $04 : STA.l $7FF83C, X
  LDA.b $05 : STA.l $7FF878, X
  LDA.b $06 : STA.l $7FF81E, X
  LDA.b $07 : STA.l $7FF85A, X
  LDA.b $08 : STA.l $7FF90E, X
  PLX
  SEC
  RTL
  .refused
  PLX
  CLC
  RTL
}

; ---------------------------------------------------------
; Trail attacks: the sprite drifts toward the player and drops a fire or
; ice garnish every 8 frames. A = cap of live garnishes for this sprite.

BossKit_FireTrail:
{
  PHA
  JSR BossKit_MoveUnlessBlocked
  PLA : STA.b $09
  INC.w SprDelay, X : LDA.w SprDelay, X : AND.b #$07 : BNE .drift
    LDA.b #!BossKit_TrailLife : STA.b $08
    LDA.b #$10 : JSL BossKit_FxAtSprite : BCC .drift
      LDA.b #$2A : JSL Sound_SetSfx2PanLong
  .drift
  JML BossKit_Drift
}

BossKit_IceTrail:
{
  PHA
  JSR BossKit_MoveUnlessBlocked
  PLA : STA.b $09
  INC.w SprDelay, X : LDA.w SprDelay, X : AND.b #$07 : BNE .drift
    LDA.b #!BossKit_IceTrailLife : STA.b $08
    LDA.b #$0C : JSL BossKit_FxAtSprite : BCC .drift
      LDA.b #$14 : JSL Sound_SetSfx3PanLong
  .drift
  JML BossKit_Drift
}

BossKit_MoveUnlessBlocked:
{
  JSL Sprite_CheckTileCollision : BNE .blocked
    JSL Sprite_Move
  .blocked
  RTS
}

; Jitter the speed every 8 frames, steer toward the player, bounce off walls.
; Same feel as vanilla TrinexxBreath ($1DBC9B), which the old helper copied.
BossKit_Drift:
{
  PHB : PHK : PLB
  LDA.b $1A : AND.b #$07 : BNE .no_jitter
    JSL GetRandomInt : AND.b #$03 : TAY
    LDA.w .jitter_x, Y : CLC : ADC.w SprXSpeed, X : STA.w SprXSpeed, X
    LDA.w .jitter_y, Y : CLC : ADC.w SprYSpeed, X : STA.w SprYSpeed, X
  .no_jitter

  JSL Sprite_BounceFromTileCollision
  LDA.b $1A : AND.b #$03 : BNE .no_steer
    JSL Sprite_IsToRightOfPlayer
    LDA.w SprXSpeed, X : CMP.w .target, Y : BEQ .no_steer
      CLC : ADC.w .steer_x, Y : STA.w SprXSpeed, X
  .no_steer

  JSL Sprite_IsBelowPlayer
  LDA.w SprYSpeed, X : CMP.w .target, Y : BEQ .exit
    CLC : ADC.w .steer_y, Y : STA.w SprYSpeed, X
  JSL Sprite_CheckTileCollision : BEQ .exit
    LDY.b #$10
    JSL Sprite_FloatTowardPlayer
  .exit
  PLB
  RTL

  .target
    db 16, -16
  .steer_x
    db  1, -1
  .steer_y
    db  0, -1
  .jitter_x
    db $02, $FE, $04, $FC
  .jitter_y
    db $01, $FF, $02, $FE
}

; ---------------------------------------------------------
; Chain draw: 4 links of one 16x16 tile from the sprite toward an anchor.
; Link i sits at i/4 of the way (link 4 is on the anchor). The middle links
; bow by $0C/$0D (full on link 2, half on links 1 and 3).
; Call after the sprite's own tiles, with ($90),Y on the next OAM entry.
; In:  $00/$02 = sprite screen X/Y (from Sprite_PrepOamCoord)
;      $04/$05 = anchor minus sprite, signed X/Y (keep within +-120)
;      $06 = char, $07 = properties, $0C/$0D = signed bow X/Y
; Out: Y advanced by 16 (4 OAM entries).
BossKit_DrawChain:
{
  PHX
  LDA.b $04 : CMP.b #$80 : ROR A : CMP.b #$80 : ROR A : STA.b $08
  LDA.b $05 : CMP.b #$80 : ROR A : CMP.b #$80 : ROR A : STA.b $09
  LDA.b $0C : CMP.b #$80 : ROR A : STA.b $0A
  LDA.b $0D : CMP.b #$80 : ROR A : STA.b $0B
  STZ.b $04 : STZ.b $05
  LDX.b #$00
  .link
    LDA.b $04 : CLC : ADC.b $08 : STA.b $04 : STA.b $0E
    LDA.b $05 : CLC : ADC.b $09 : STA.b $05 : STA.b $0F
    CPX.b #$03 : BEQ .bowed
    CPX.b #$01 : BEQ .full_bow
      LDA.b $0E : CLC : ADC.b $0A : STA.b $0E
      LDA.b $0F : CLC : ADC.b $0B : STA.b $0F
      BRA .bowed
    .full_bow
      LDA.b $0E : CLC : ADC.b $0C : STA.b $0E
      LDA.b $0F : CLC : ADC.b $0D : STA.b $0F
    .bowed

    REP #$20
    LDA.b $0E : AND.w #$00FF : CMP.w #$0080 : BCC .x_positive
      ORA.w #$FF00
    .x_positive
    CLC : ADC.b $00 : STA ($90), Y
    AND.w #$0100 : PHA         ; X bit 8 for the high table
    INY
    LDA.b $0F : AND.w #$00FF : CMP.w #$0080 : BCC .y_positive
      ORA.w #$FF00
    .y_positive
    CLC : ADC.b $02 : STA ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .on_screen
      LDA.b #$F0 : STA ($90), Y
    .on_screen
    INY : LDA.b $06 : STA ($90), Y
    INY : LDA.b $07 : STA ($90), Y
    PLA : PLA : ORA.b #$02 : STA.b $0E ; 16x16 plus X bit 8
    PHY
    TYA : LSR A : LSR A : TAY
    LDA.b $0E : STA ($92), Y
    PLY : INY
  INX : CPX.b #$04 : BCS .done ; the loop is too long for BCC
    JMP .link
  .done
  PLX
  RTL
}
