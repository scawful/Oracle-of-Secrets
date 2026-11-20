; ==============================================================================
; Sprites/Enemies/lyra_sea_enemies.asm — Lyra Sea Cheep-Cheep & Blooper ($AB)
; ==============================================================================
; GameyFireBro Cheep-Cheep & Blooper (Data/graphics/sprites/gameyfirebro/cheep_blooper)
; wired onto unused vanilla sprite slot $AB (0 OW / 0 Dungeon placements).
; Bank-neutral in Bank $32 (PHB/PHK/PLB, outward calls are JSL).
;
; Subtypes (SprSubtype & 1 -> SprMiscD):
;   0 = Sprite_CheepCheep: swims in Lyra Sea / D4 water ($08/$09/$4B), then
;       leaps in a parabolic Z-height arc (SprHeight) flapping between frames
;       0 and 1 (CHR $E8/$EA, Universal OAM Pal 1: red/orange/gold/white).
;   1 = Sprite_Blooper: iconic rhythmic squid — sinks/aims briefly with spread
;       tentacles (CHR $CA), then jets diagonally toward Link with sleek tucked
;       tentacles (CHR $C8, Universal OAM Pal 2: white/aqua/dark), staying in water.
;
; VRAM (2-frame staged NMI DMA <= 256B/frame, chained from NightPoe_NmiUpload
; in Bank $32 — zero Bank $2B cost, 4-cycle fast exit when idle/live):
;   Stage $80 -> $81: Cheep-Cheep 256B -> $5E80/$5F80 ($E8) & $5EA0/$5FA0 ($EA)
;   Stage $81 -> $01: Blooper     256B -> $5C80/$5D80 ($C8) & $5CA0/$5DA0 ($CA)
; Leaves NightPoe ($EC/$EE), Epona ($5000/$5100), Gust Jar ($4070/$4090),
; Bombchu ($42E0/$43E0), Lily Pad ($4420/$4520/$47C0), and pickups ($4600-$47FF)
; completely untouched.
; ==============================================================================

!SPRID                  = Sprite_CheepCheep
!LYRA_SEA_NMI_UPLOAD    = 1
!NbrTiles               = 03  ; 4 slots (16x16 body + shadow + 4-tile death poof)
!Harmless               = 00  ; Real enemy: damages Link, killable, Gust Jar pullable
!HVelocity              = 00
!Health                 = 04  ; 2 Fighter Sword hits; <= 8 so Gust Jar captures
!Damage                 = 04  ; Half-heart contact damage
!DeathAnimation         = 00  ; Standard enemy death poof + prize drop
!ImperviousAll          = 00
!SmallShadow            = 00
!Shadow                 = 00  ; Drawn dynamically only while Cheep-Cheep is airborne
!Palette                = 01  ; Pal 1 for Cheep-Cheep; Draw selects Pal 2 for Blooper
!Hitbox                 = 00  ; 16x16 enemy hitbox
!Persist                = 00
!Statis                 = 00
!CollisionLayer         = 00
!CanFall                = 00
!DeflectArrow           = 00
!WaterSprite            = 00
!Blockable              = 00
!Prize                  = 02  ; Hearts / rupees / magic
!Sound                  = 00
!Interaction            = 01  ; Custom water probe so Cheep-Cheep can leap over reefs
!Statue                 = 00
!DeflectProjectiles     = 00
!ImperviousArrow        = 00
!ImpervSwordHammer      = 00
!Boss                   = 00

%Set_Sprite_Properties(Sprite_LyraSea_Prep, Sprite_LyraSea_Long)

LyraSea_CodeStart:

; ------------------------------------------------------------------------------
; Prep: cache subtype (0=Cheep-Cheep, 1=Blooper), init timers, queue VRAM.
; ------------------------------------------------------------------------------
Sprite_LyraSea_Prep:
{
  PHB : PHK : PLB
  LDA.w SprSubtype, X : AND.b #$01 : STA.w SprMiscD, X
  STZ.w SprAction, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprHeight, X
  STZ.w SprMiscA, X ; 0 = facing Left (native Cheep art faces left), 1 = Right
  STZ.w SprMiscB, X ; Cheep vertical leap velocity (signed px/step)
  TXA : ASL #3 : STA.w SprMiscC, X ; staggered animation phase per slot

  LDA.w SprMiscD, X : BNE .prep_blooper
    LDA.b #$30 : STA.w SprTimerA, X ; swim before first leap
    BRA .queue_vram
.prep_blooper
  LDA.b #$18 : STA.w SprTimerA, X ; brief float/aim before first jet dash
.queue_vram
  JSR LyraSea_RequestVram
  PLB
  RTL
}

LyraSea_RequestVram:
{
  JSR LyraSea_GetAreaKey
  STA.l LyraSea_LastArea
  TYA : STA.l LyraSea_LastInd
  LDA.b #$80 : STA.l LyraSea_VramState
  RTS
}

LyraSea_EnsureVram:
{
  LDA.l LyraSea_VramState : BEQ .need
  JSR LyraSea_GetAreaKey
  CMP.l LyraSea_LastArea : BNE .need
  TYA : CMP.l LyraSea_LastInd : BNE .need
  RTS
.need
  JMP LyraSea_RequestVram
}

; Out: A = area ($8A) outdoors or room low ($A0) indoors;
;      Y = $00 outdoors or ($80 | ($A1 & $01)) indoors. Preserves X.
LyraSea_GetAreaKey:
{
  LDA.b $1B : BNE .indoors
    LDA.b $8A
    LDY.b #$00
    RTS
.indoors
  LDA.b $A1 : AND.b #$01 : ORA.b #$80 : TAY
  LDA.b $A0
  RTS
}

; ------------------------------------------------------------------------------
; Main entry: skip custom draw over death poof (SprState == $06).
; ------------------------------------------------------------------------------
Sprite_LyraSea_Long:
{
  PHB : PHK : PLB
  LDA.w SprState, X : CMP.b #$06 : BEQ .dying
    JSR Sprite_LyraSea_Draw
.dying
  JSL Sprite_CheckActive : BCC .return
    JSR Sprite_LyraSea_Main
.return
  PLB
  RTL
}

Sprite_LyraSea_Main:
{
  JSR LyraSea_EnsureVram
  INC.w SprMiscC, X

  LDA.w SprMiscD, X : BNE .blooper
    JSR LyraSea_CheepMain
    BRA .combat
.blooper
  JSR LyraSea_BlooperMain

.combat
  JSL Sprite_CheckDamageFromPlayer
  JSL Sprite_CheckDamageToPlayer
  RTS
}

; ------------------------------------------------------------------------------
; Subtype 0: Cheep-Cheep
;   Action 0 = Swim toward Link (respects water tiles $08/$09/$4B) until TimerA=0
;   Action 1 = Parabolic leap (SprHeight arcs up & down, ignores water walls!)
; ------------------------------------------------------------------------------
LyraSea_CheepMain:
{
  LDA.w SprAction, X : BNE .airborne

  ; --- Action 0: Submerged Swim ---
  STZ.w SprHeight, X
  LDA.w SprMiscC, X : AND.b #$03 : BNE .swim_move
    JSR LyraSea_AimHorizontal
    JSR LyraSea_AimVerticalSlow
.swim_move
  JSR LyraSea_CheckWaterAhead : BCC .water_ok
    ; Flip direction away from shore/cliff while submerged
    LDA.w SprXSpeed, X : EOR.b #$FF : INC A : STA.w SprXSpeed, X
    LDA.w SprYSpeed, X : EOR.b #$FF : INC A : STA.w SprYSpeed, X
    LDA.w SprMiscA, X : EOR.b #$01 : STA.w SprMiscA, X
.water_ok
  JSL Sprite_MoveLong

  LDA.w SprTimerA, X : BNE .swim_done
    ; Launch parabolic leap!
    LDA.b #$01 : STA.w SprAction, X
    LDA.b #$04 : STA.w SprMiscB, X ; initial upward Z velocity (+4 px/step)
    LDA.b #$01 : STA.w SprHeight, X
    LDA.b #$28 : STA.w $012E       ; SFX2.$28 water splash
    ; Surge horizontally toward Link during leap
    JSR LyraSea_FaceLink
    LDA.w SprMiscA, X : BNE .leap_right
      LDA.b #$EA : STA.w SprXSpeed, X ; -$16 (-1.375 px/f)
      BRA .leap_y
.leap_right
    LDA.b #$16 : STA.w SprXSpeed, X   ; +$16 (+1.375 px/f)
.leap_y
    STZ.w SprYSpeed, X
.swim_done
  RTS

.airborne
  ; --- Action 1: Airborne Parabolic Leap ---
  ; Flies cleanly over reefs, Lily Pads, and KORL; updates Z height every 2 frames.
  JSL Sprite_MoveLong
  LDA.w SprMiscC, X : AND.b #$01 : BNE .air_done
    LDA.w SprHeight, X : CLC : ADC.w SprMiscB, X
    BEQ .landed
    BMI .landed
    STA.w SprHeight, X
    ; Apply gravity (-1 to Z velocity every 4 frames)
    LDA.w SprMiscC, X : AND.b #$03 : BNE .air_done
      LDA.w SprMiscB, X : DEC A : STA.w SprMiscB, X
      RTS
.landed
  STZ.w SprHeight, X
  STZ.w SprMiscB, X
  STZ.w SprAction, X
  LDA.b #$38 : STA.w SprTimerA, X
  LDA.b #$28 : STA.w $012E ; splash back into Lyra Sea
.air_done
  RTS
}

; ------------------------------------------------------------------------------
; Subtype 1: Blooper
;   Action 0 = Slow downward drift (tentacles spread, TimerA=$18)
;   Action 1 = Crisp diagonal jet dash toward Link (tentacles tucked, TimerA=$1A)
; ------------------------------------------------------------------------------
LyraSea_BlooperMain:
{
  STZ.w SprHeight, X
  LDA.w SprAction, X : BNE .jetting

  ; --- Action 0: Float / Sink Telegraph ---
  STZ.w SprXSpeed, X
  LDA.b #$06 : STA.w SprYSpeed, X ; gentle downward drift
  JSR LyraSea_CheckWaterAhead : BCS .float_wait
    JSL Sprite_MoveLong
.float_wait
  LDA.w SprTimerA, X : BNE .blooper_done
    ; Trigger diagonal jet dash toward Link!
    LDA.b #$01 : STA.w SprAction, X
    LDA.b #$1A : STA.w SprTimerA, X
    JSR LyraSea_FaceLink
    LDA.w SprMiscA, X : BNE .jet_right
      LDA.b #$E8 : STA.w SprXSpeed, X ; -$18 (-1.5 px/f)
      BRA .jet_y
.jet_right
    LDA.b #$18 : STA.w SprXSpeed, X   ; +$18 (+1.5 px/f)
.jet_y
    ; Classic Blooper jet: upward diagonal unless Link is far below (>= 24px).
    LDA.w SprY, X : STA.b $02
    LDA.w SprYH, X : STA.b $03
    REP #$20
    LDA.b $20 : SEC : SBC.b $02
    BMI .jet_up16
    CMP.w #$0018 : BCC .jet_up16
    SEP #$20
    LDA.b #$12 : STA.w SprYSpeed, X
    RTS
.jet_up16
    SEP #$20
    LDA.b #$EC : STA.w SprYSpeed, X ; -$14 (-1.25 px/f upward pulse)
    RTS

.jetting
  ; --- Action 1: Jet Dash ---
  JSR LyraSea_CheckWaterAhead : BCC .jet_move
    ; Stop cleanly at shore/cliff edge so Blooper never enters dry land
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    BRA .jet_timer
.jet_move
  JSL Sprite_MoveLong
.jet_timer
  LDA.w SprTimerA, X : BNE .blooper_done
    STZ.w SprAction, X
    LDA.b #$18 : STA.w SprTimerA, X
.blooper_done
  RTS
}

; Update SprMiscA,X (0=Left, 1=Right) from 16-bit Link X delta.
LyraSea_FaceLink:
{
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  REP #$20
  LDA.b $22 : SEC : SBC.b $00
  SEP #$20
  BMI .left
    LDA.b #$01 : STA.w SprMiscA, X
    RTS
.left
  STZ.w SprMiscA, X
  RTS
}

; Set gentle submerged Cheep horizontal speed (+/- $10) toward Link.
LyraSea_AimHorizontal:
{
  JSR LyraSea_FaceLink
  LDA.w SprMiscA, X : BNE .right
    LDA.b #$F0 : STA.w SprXSpeed, X ; -$10 (-1.0 px/f)
    RTS
.right
  LDA.b #$10 : STA.w SprXSpeed, X   ; +$10 (+1.0 px/f)
  RTS
}

; Set gentle vertical tracking (+/- $08) toward Link Y.
LyraSea_AimVerticalSlow:
{
  LDA.w SprY, X : STA.b $02
  LDA.w SprYH, X : STA.b $03
  REP #$20
  LDA.b $20 : SEC : SBC.b $02
  SEP #$20
  BEQ .zero
  BMI .up
    LDA.b #$08 : STA.w SprYSpeed, X
    RTS
.up
  LDA.b #$F8 : STA.w SprYSpeed, X
  RTS
.zero
  STZ.w SprYSpeed, X
  RTS
}

; C=1 if the tile 8 px ahead along current velocity is NOT floatable water
; ($08 deep water, $09 shallow water, $4B deep sea/channel). Preserves X.
LyraSea_CheckWaterAhead:
{
  LDA.w SprX, X : CLC : ADC.b #$08 : STA.b $02
  LDA.w SprXH, X : ADC.b #$00 : STA.b $03
  LDA.w SprXSpeed, X : BEQ .chk_y
  BMI .probe_left
    LDA.b $02 : CLC : ADC.b #$08 : STA.b $02
    LDA.b $03 : ADC.b #$00 : STA.b $03
    BRA .chk_y
.probe_left
  LDA.b $02 : SEC : SBC.b #$08 : STA.b $02
  LDA.b $03 : SBC.b #$00 : STA.b $03

.chk_y
  LDA.w SprY, X : CLC : ADC.b #$08 : STA.b $00
  LDA.w SprYH, X : ADC.b #$00 : STA.b $01
  LDA.w SprYSpeed, X : BEQ .do_probe
  BMI .probe_up
    LDA.b $00 : CLC : ADC.b #$08 : STA.b $00
    LDA.b $01 : ADC.b #$00 : STA.b $01
    BRA .do_probe
.probe_up
  LDA.b $00 : SEC : SBC.b #$08 : STA.b $00
  LDA.b $01 : SBC.b #$00 : STA.b $01

.do_probe
  PHX
  LDA.w SprFloor, X
  JSL Sprite_GetTileAttr
  PLX
  CMP.b #$08 : BEQ .is_water
  CMP.b #$09 : BEQ .is_water
  CMP.b #$4B : BEQ .is_water
    SEC
    RTS
.is_water
  CLC
  RTS
}

; ------------------------------------------------------------------------------
; Draw: 1 x 16x16 OAM sprite (plus shadow when Cheep-Cheep is airborne).
;   Cheep-Cheep (sub 0): CHR $E8 / $EA, Universal OAM Pal 1 ($02), H-flip right
;   Blooper     (sub 1): CHR $C8 (jet) / $CA (spread), Universal OAM Pal 2 ($04)
; ------------------------------------------------------------------------------
Sprite_LyraSea_Draw:
{
  ; Never flash unuploaded VRAM while 2-frame NMI stream is in flight.
  LDA.l LyraSea_VramState : CMP.b #$01 : BNE .skip

  JSL Sprite_PrepOamCoord : BCC .on_screen
.skip
  RTS

.on_screen
  JSL Sprite_OAM_AllocateDeferToPlayer

  ; Compute screen X/Y = SprWorld - Camera ($E2/$E8), minus SprHeight on Y.
  ; Preserve $00-$05 (Sprite_PrepOamCoord outputs) so Sprite_DrawShadow keeps
  ; screen X ($00/$01) and OAM priority bits ($05).
  LDA.w SprX, X : STA.b $08
  LDA.w SprXH, X : STA.b $09
  LDA.w SprY, X : STA.b $0A
  LDA.w SprYH, X : STA.b $0B
  LDA.w SprHeight, X : STA.b $0C : STZ.b $0D
  REP #$20
  LDA.b $08 : SEC : SBC.b $E2 : STA.b $08
  LDA.b $0A : SEC : SBC.b $E8 : SEC : SBC.b $0C : STA.b $0A
  SEP #$20

  LDA.w SprMiscD, X : BNE .draw_blooper

  ; --- Cheep-Cheep CHR & Property ---
  ; Flap faster when leaping (>>2) than swimming (>>4).
  LDA.w SprAction, X : BEQ .cheep_slow
    LDA.w SprMiscC, X : LSR #2
    BRA .cheep_frame
.cheep_slow
  LDA.w SprMiscC, X : LSR #4
.cheep_frame
  AND.b #$01 : ASL A : CLC : ADC.b #$E8 : STA.b $0E ; $E8 or $EA

  ; Flash-safe Universal OAM Pal 1 ($02) on Page 1 ($01), Priority 2 ($20)
  LDA.w SprFlash, X : ASL A : EOR.b #$02 : AND.b #$0E : STA.b $0C
  LDA.b #$21 ; facing Left (native art faces left)
  LDY.w SprMiscA, X : BEQ .cheep_prop
    LDA.b #$61 ; H-flip facing Right
.cheep_prop
  ORA.b $0C : STA.b $0D
  BRA .emit

.draw_blooper
  ; --- Blooper CHR & Property ---
  ; Action 1 (jetting) = sleek tucked $C8; Action 0 (floating) = spread $CA.
  LDA.b #$CA
  LDY.w SprAction, X : BEQ .blooper_chr
    LDA.b #$C8
.blooper_chr
  STA.b $0E
  ; Flash-safe Universal OAM Pal 2 ($04) on Page 1 ($01), Priority 2 ($20)
  LDA.w SprFlash, X : ASL A : EOR.b #$04 : AND.b #$0E : ORA.b #$21 : STA.b $0D

.emit
  LDY.b #$00
  JSR LyraSea_Emit16x16

  ; Draw ground/water shadow only while Cheep-Cheep is airborne.
  LDA.w SprHeight, X : BEQ .done
    JSL Sprite_DrawShadow
.done
  RTS
}

; True SNES 9-bit 16x16 OAM X clipping ([-15..255]):
;   0..255 ($0000..$00FF)  -> X=$08, HI=$02 (16x16, X-MSB=0)
;  -15..-1 ($FFF1..$FFFF)  -> X=$08, HI=$03 (16x16, X-MSB=1 left clip)
;  <= -16 or >= 256        -> hidden (X=0, Y=$F0, HI=$00)
LyraSea_Emit16x16:
{
  LDA.b $09 : BEQ .x_pos
  CMP.b #$FF : BNE .hide_tile
  LDA.b $08 : CMP.b #$F1 : BCC .hide_tile
    STA.b ($90), Y
    LDA.b #$03 : STA.b $0F
    BRA .check_y
.x_pos
  LDA.b $08 : STA.b ($90), Y
  LDA.b #$02 : STA.b $0F
.check_y
  INY
  LDA.b $0B : BNE .hide_y
  LDA.b $0A : CMP.b #$E0 : BCS .hide_y
  STA.b ($90), Y
  BRA .write_chr
.hide_tile
  LDA.b #$00 : STA.b ($90), Y
  INY
.hide_y
  LDA.b #$F0 : STA.b ($90), Y
  STZ.b $0F
.write_chr
  INY
  LDA.b $0E : STA.b ($90), Y
  INY
  LDA.b $0D : STA.b ($90), Y
  PHY
  TYA : LSR #2 : TAY
  LDA.b $0F : STA.b ($92), Y
  PLY
  RTS
}

; ------------------------------------------------------------------------------
; 2-Frame Staged NMI VRAM Streamer — tail-called from NightPoe_NmiUpload (Bank $32).
; Entry: M=8, X=16, DBR=$00; DMA0=$1801, VMAIN=$80. Peak DMA <= 256B/frame.
; Exit:  A, X, Y, P, DBR preserved; $4304=$7E, $4302=$0ADC restored cleanly.
; ------------------------------------------------------------------------------
LyraSea_NmiUpload:
{
  PHP : PHA
  LDA.l LyraSea_VramState : BPL .fast_exit

  ; Upload only during active gameplay modules ($07 Indoors, $09 OW, $0B Special OW).
  LDA.b $10 : CMP.b #$07 : BEQ .mod_ok
  CMP.b #$09 : BEQ .mod_ok
  CMP.b #$0B : BEQ .mod_ok
.fast_exit
  PLA : PLP
  if defined("PIG_MOBLIN_NMI_UPLOAD")
    JML PigMoblin_NmiUpload
  else
    RTL
  endif

.mod_ok
  PHX : PHY
  LDA.b #LyraSea_GfxStart>>16 : STA.w $4304

  LDA.l LyraSea_VramState : CMP.b #$81 : BEQ .stage2

  ; --- Stage 1 ($80 -> $81): Cheep-Cheep 256B -> $5E80/$5F80 ($E8) & $5EA0/$5FA0 ($EA) ---
  LDX.w #$5E80 : LDY.w #LyraSea_CheepF0Top : JSR .dma_row
  LDX.w #$5F80 : LDY.w #LyraSea_CheepF0Bot : JSR .dma_row
  LDX.w #$5EA0 : LDY.w #LyraSea_CheepF1Top : JSR .dma_row
  LDX.w #$5FA0 : LDY.w #LyraSea_CheepF1Bot : JSR .dma_row
  LDA.b #$81 : STA.l LyraSea_VramState
  BRA .restore

.stage2
  ; --- Stage 2 ($81 -> $01): Blooper 256B -> $5C80/$5D80 ($C8) & $5CA0/$5DA0 ($CA) ---
  LDX.w #$5C80 : LDY.w #LyraSea_BlooperF0Top : JSR .dma_row
  LDX.w #$5D80 : LDY.w #LyraSea_BlooperF0Bot : JSR .dma_row
  LDX.w #$5CA0 : LDY.w #LyraSea_BlooperF1Top : JSR .dma_row
  LDX.w #$5DA0 : LDY.w #LyraSea_BlooperF1Bot : JSR .dma_row
  LDA.b #$01 : STA.l LyraSea_VramState

.restore
  LDA.b #$7E : STA.w $4304
  REP #$20
  LDA.w $0ADC : STA.w $4302
  SEP #$20
  PLY : PLX : PLA : PLP
  RTL

.dma_row
  STX.w $2116
  STY.w $4302
  REP #$20
  LDA.w #$0040 : STA.w $4305
  SEP #$20
  LDA.b #$01 : STA.w $420B
  RTS
}

; ------------------------------------------------------------------------------
; GameyFireBro Cheep-Cheep & Blooper 4BPP tiles (512 bytes = 4 x 16x16 blocks).
; Source: Data/graphics/sprites/gameyfirebro/cheep_blooper/sheet.4bpp
;   Cheep-Cheep ($00/$01/$10/$11 & $02/$03/$12/$13) -> Universal OAM Pal 1
;   Blooper     ($04/$05/$14/$15 & $06/$07/$16/$17) -> Universal OAM Pal 2
; Verified byte-exact by Tests/test_lyra_sea_enemies.py.
; ------------------------------------------------------------------------------
LyraSea_GfxStart:
LyraSea_CheepF0Top:
  db $07,$00,$08,$07,$3F,$00,$7E,$13,$FF,$01,$FF,$01,$FF,$01,$FF,$01
  db $07,$00,$0F,$00,$3F,$00,$52,$00,$81,$00,$A9,$00,$A9,$00,$81,$00
  db $C0,$00,$60,$C0,$B0,$60,$58,$B0,$AC,$D8,$94,$E8,$9C,$E8,$3C,$C0
  db $C0,$00,$E0,$00,$F0,$00,$78,$00,$BC,$00,$9C,$00,$9C,$00,$3C,$00
LyraSea_CheepF0Bot:
  db $7E,$03,$74,$0B,$CA,$35,$B2,$4D,$82,$7D,$44,$3B,$38,$07,$07,$00
  db $7A,$00,$4C,$00,$B7,$00,$FF,$00,$BB,$00,$45,$00,$38,$00,$07,$00
  db $7E,$80,$FE,$00,$7F,$80,$3F,$C0,$0F,$F0,$1F,$E0,$26,$C0,$C0,$00
  db $42,$00,$82,$00,$C5,$00,$F9,$00,$C9,$00,$99,$00,$26,$00,$C0,$00
LyraSea_CheepF1Top:
  db $07,$00,$08,$07,$3F,$00,$7E,$13,$FF,$01,$FF,$01,$FF,$01,$FF,$01
  db $07,$00,$0F,$00,$3F,$00,$52,$00,$81,$00,$A9,$00,$A9,$00,$81,$00
  db $C0,$00,$60,$C0,$B0,$60,$58,$B0,$BC,$C0,$BC,$C0,$FC,$80,$FC,$00
  db $C0,$00,$E0,$00,$F0,$00,$78,$00,$BC,$00,$A4,$00,$C4,$00,$84,$00
LyraSea_CheepF1Bot:
  db $7E,$03,$74,$0B,$CA,$35,$B2,$4D,$B2,$4D,$82,$7D,$44,$3B,$3F,$00
  db $7A,$00,$4C,$00,$B7,$00,$FF,$00,$FB,$00,$BB,$00,$44,$00,$3F,$00
  db $F8,$00,$3E,$C0,$0F,$F0,$0F,$F0,$0F,$F0,$1F,$E0,$26,$C0,$C0,$00
  db $C8,$00,$FE,$00,$E9,$00,$E9,$00,$C9,$00,$99,$00,$26,$00,$C0,$00
LyraSea_BlooperF0Top:
  db $01,$00,$07,$00,$0B,$00,$1F,$00,$3C,$00,$53,$00,$8F,$00,$DF,$40
  db $01,$00,$06,$00,$0C,$00,$10,$00,$23,$00,$6F,$00,$FF,$00,$B3,$00
  db $80,$00,$E0,$00,$D0,$00,$F8,$00,$3C,$00,$CA,$00,$F1,$00,$FB,$02
  db $80,$00,$60,$00,$30,$00,$08,$00,$C4,$00,$F6,$00,$FF,$00,$CD,$00
LyraSea_BlooperF0Bot:
  db $7F,$00,$3F,$00,$1F,$00,$2F,$00,$37,$10,$15,$00,$1D,$08,$0E,$00
  db $6D,$00,$2D,$00,$13,$00,$3C,$00,$2D,$00,$1F,$00,$17,$00,$0E,$00
  db $FE,$00,$FC,$00,$F8,$00,$F4,$00,$EC,$08,$A8,$00,$B8,$10,$70,$00
  db $B6,$00,$B4,$00,$C8,$00,$3C,$00,$B4,$00,$F8,$00,$E8,$00,$70,$00
LyraSea_BlooperF1Top:
  db $00,$00,$00,$00,$01,$00,$07,$00,$0B,$00,$1F,$00,$3C,$00,$53,$00
  db $00,$00,$00,$00,$01,$00,$06,$00,$0C,$00,$10,$00,$23,$00,$6F,$00
  db $00,$00,$00,$00,$80,$00,$E0,$00,$D0,$00,$F8,$00,$3C,$00,$CA,$00
  db $00,$00,$00,$00,$80,$00,$60,$00,$30,$00,$08,$00,$C4,$00,$F6,$00
LyraSea_BlooperF1Bot:
  db $8F,$00,$DF,$40,$7F,$00,$3F,$00,$4F,$00,$7B,$20,$3F,$1A,$1E,$00
  db $FF,$00,$B3,$00,$6D,$00,$33,$00,$7C,$00,$5F,$00,$25,$00,$1E,$00
  db $F1,$00,$FB,$02,$FE,$00,$FC,$00,$F2,$00,$DE,$04,$FC,$58,$78,$00
  db $FF,$00,$CD,$00,$B6,$00,$CC,$00,$3E,$00,$FA,$00,$A4,$00,$78,$00
LyraSea_GfxEnd:

assert LyraSea_GfxEnd-LyraSea_GfxStart == $0200, "LyraSea GFX must be 512 bytes (4 x 16x16)"
assert (LyraSea_GfxStart>>16) == ((LyraSea_GfxEnd-1)>>16), "LyraSea DMA source crossed bank"

LyraSea_CodeEnd:
print "Lyra Sea Enemies bytes: ", dec(LyraSea_CodeEnd-LyraSea_CodeStart)
