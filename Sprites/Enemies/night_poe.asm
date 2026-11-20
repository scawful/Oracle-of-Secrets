; ==============================================================================
; Sprites/Enemies/night_poe.asm — Nighttime Lantern Poe (Sprite $B4)
; ==============================================================================
; GameyFireBro EoW Poe + Lantern (Data/graphics/sprites/gameyfirebro/eow_poe_lantern)
; wired onto unused vanilla sprite slot $B4 (0 OW / 0 Dungeon placements).
; Bank-neutral in Bank $32 (PHB/PHK/PLB, outward calls are JSL).
;
; Design goals:
;   - Zero-lag nighttime Overworld enemy alongside Epona: no tile-collision
;     sweeps (!Interaction=01); floats freely over fences, cliffs, and water;
;     uses only 2 x 16x16 OAM slots (body + swinging lantern).
;   - Subtype 0 (default): active at night (TimeState.Hours >= 18 or < 6) on
;     Kalyxo LW / Special OW; despawns silently during daytime (06:00-17:59).
;     Always active indoors ($1B != 0) and in Eon Abyss ($40-$7F).
;   - Subtype 1: always active regardless of time of day (dungeons/graveyard).
;   - Behavior: drifts smoothly toward Link (16-bit delta, clamped +/- $14) with
;     vertical float bob and lantern sway; on hit recoil, phases ethereal
;     (SprAction=1, flickering & invulnerable for 28 frames) while drifting
;     sideways before materializing solid again. Gust Jar pullable/capturable
;     (!Health=$06 <= 8).
;   - VRAM: NightPoe_NmiUpload (chained after GustJar_NmiUpload in
;     Items/bombchu.asm) streams 256B (2 x 16x16 blocks) once on demand into
;     Page 1 SP3 tail $5EC0/$5FC0 (CHR $EC) and $5EE0/$5FE0 (CHR $EE), leaving
;     Epona ($5000/$5100 & $4080-$41DF), Gust Jar ($4070/$4090), Bombchu
;     ($42E0/$43E0), Lily Pad ($4420/$4520/$47C0), and pickups ($4600-$47FF)
;     completely untouched. Uses universal OAM Palette 4 ($08).
; ==============================================================================

!SPRID              = Sprite_NightPoe
!NIGHT_POE_NMI_UPLOAD = 1
!NbrTiles           = 03  ; 4 slots (2 x 16x16 body+lantern; 4-tile death poof headroom)
!Harmless           = 00  ; Real enemy: damages Link, killable, Gust Jar pullable
!HVelocity          = 00
!Health             = 06  ; 3 Fighter Sword hits; <= 8 so Gust Jar captures
!Damage             = 04  ; Half-heart contact damage
!DeathAnimation     = 00  ; Standard enemy death poof + prize drop
!ImperviousAll      = 00
!SmallShadow        = 00
!Shadow             = 00
!Palette            = 04  ; Universal OAM Pal 4 (lavender/violet LW, spectral aqua DW)
!Hitbox             = 00  ; Standard 16x16 hitbox
!Persist            = 00  ; Despawns cleanly when outrun on Epona
!Statis             = 00
!CollisionLayer     = 00
!CanFall            = 00
!DeflectArrow       = 00
!WaterSprite        = 00
!Blockable          = 00
!Prize              = 02  ; Standard hearts / rupees / magic drops
!Sound              = 00
!Interaction        = 01  ; Ghost: skip tile collision sweeps (zero-lag with Epona)
!Statue             = 00
!DeflectProjectiles = 00
!ImperviousArrow    = 00
!ImpervSwordHammer  = 00
!Boss               = 00

%Set_Sprite_Properties(Sprite_NightPoe_Prep, Sprite_NightPoe_Long)

NightPoe_CodeStart:

; ------------------------------------------------------------------------------
; Prep: enforce day/night gate on LW/SW Overworld for Subtype 0; request VRAM.
; ------------------------------------------------------------------------------
Sprite_NightPoe_Prep:
{
  PHB : PHK : PLB
  LDA.w SprSubtype, X : AND.b #$01 : STA.w SprMiscD, X
  BNE .spawn_ok ; Subtype 1: always active (graveyard / dungeons / haunts)

  LDA.b $1B : BNE .spawn_ok ; Indoors: always active
  LDA.b $8A
  CMP.b #$40 : BCC .check_night
  CMP.b #$80 : BCC .spawn_ok ; Eon Abyss ($40-$7F): always active

.check_night
  ; Night is 18:00-23:59 ($12+) or 00:00-05:59 (< $06).
  LDA.l TimeState.Hours
  CMP.b #$06 : BCC .spawn_ok
  CMP.b #$12 : BCS .spawn_ok
    STZ.w SprState, X
    PLB
    RTL

.spawn_ok
  STZ.w SprAction, X
  STZ.w SprTimerA, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprMiscA, X ; 0 = facing Left (native EoW Poe art faces left), 1 = Right
  STZ.w SprMiscB, X
  TXA : ASL #4 : STA.w SprMiscC, X ; staggered float-bob phase per sprite slot
  JSR NightPoe_RequestVram
  PLB
  RTL
}

; Mark VRAM upload pending ($80) and record current area/indoor tuple.
NightPoe_RequestVram:
{
  JSR NightPoe_GetAreaKey ; A = area/room low, Y = indoor|room_hi
  STA.l NightPoe_LastArea
  TYA : STA.l NightPoe_LastInd
  LDA.b #$80 : STA.l NightPoe_VramState
  RTS
}

; Re-request VRAM if area/room changed since upload or VRAM was cleared.
NightPoe_EnsureVram:
{
  LDA.l NightPoe_VramState : BEQ .need
  JSR NightPoe_GetAreaKey
  CMP.l NightPoe_LastArea : BNE .need
  TYA : CMP.l NightPoe_LastInd : BNE .need
  RTS
.need
  JMP NightPoe_RequestVram
}

; Out: A = area ($8A) outdoors or room low ($A0) indoors;
;      Y = $00 outdoors or ($80 | ($A1 & $01)) indoors. Preserves X.
NightPoe_GetAreaKey:
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
Sprite_NightPoe_Long:
{
  PHB : PHK : PLB
  LDA.w SprState, X : CMP.b #$06 : BEQ .dying
    JSR Sprite_NightPoe_Draw
.dying
  JSL Sprite_CheckActive : BCC .return
    JSR Sprite_NightPoe_Main
.return
  PLB
  RTL
}

; ------------------------------------------------------------------------------
; Zero-lag AI:
;   Action 0 = Solid ghost pursuit (16-bit Link delta, clamp +/- $14, combat)
;   Action 1 = Ethereal phase-shift after hit (28 frames flicker, invulnerable)
; ------------------------------------------------------------------------------
Sprite_NightPoe_Main:
{
  JSR NightPoe_EnsureVram
  INC.w SprMiscC, X

  LDA.w SprAction, X : BNE .phased

  ; --- Action 0: Solid Ghost Pursuit ---
  ; Accelerate smoothly every 2 frames so pursuit feels floaty and responsive.
  LDA.w SprMiscC, X : AND.b #$01 : BNE .move_solid
    JSR NightPoe_SteerTowardLink
.move_solid
  JSL Sprite_MoveLong

  JSL Sprite_CheckDamageFromPlayer
  LDA.w SprRecoil, X : BEQ .check_contact
    ; Hit! Phase ethereal for 28 frames and drift laterally out of sword arc.
    LDA.b #$01 : STA.w SprAction, X
    LDA.b #$1C : STA.w SprTimerA, X
    LDA.w SprXSpeed, X : EOR.b #$FF : INC A : STA.w SprXSpeed, X
    RTS

.check_contact
  JSL Sprite_CheckDamageToPlayer
  RTS

.phased
  ; --- Action 1: Ethereal Phase-Shift (invulnerable, flickering sideways drift) ---
  JSL Sprite_MoveLong
  LDA.w SprTimerA, X : BNE .still_phased
    STZ.w SprAction, X
.still_phased
  RTS
}

; Compute 16-bit delta to Link ($22/$20), update facing SprMiscA (0=L, 1=R),
; and step SprXSpeed / SprYSpeed by +/- 1 clamped to [-$14..+$14] (+/- 1.25 px/f).
NightPoe_SteerTowardLink:
{
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  LDA.w SprY, X : STA.b $02
  LDA.w SprYH, X : STA.b $03

  ; Horizontal steering & facing
  REP #$20
  LDA.b $22 : SEC : SBC.b $00
  SEP #$20
  BEQ .do_y
  BMI .go_left
    LDA.b #$01 : STA.w SprMiscA, X ; face Right
    LDA.w SprXSpeed, X
    BMI .inc_x
    CMP.b #$14 : BCS .do_y
.inc_x
    INC A : STA.w SprXSpeed, X
    BRA .do_y
.go_left
  STZ.w SprMiscA, X ; face Left
  LDA.w SprXSpeed, X
  BPL .dec_x
  CMP.b #$ED : BCC .do_y ; clamp symmetrically at -$14 ($EC)
.dec_x
  DEC A : STA.w SprXSpeed, X

.do_y
  ; Vertical steering (target LinkY - 4 so Poe hovers at chest/head height)
  REP #$20
  LDA.b $20 : SEC : SBC.w #$0004
  SEC : SBC.b $02
  SEP #$20
  BEQ .done
  BMI .go_up
    LDA.w SprYSpeed, X
    BMI .inc_y
    CMP.b #$14 : BCS .done
.inc_y
    INC A : STA.w SprYSpeed, X
    RTS
.go_up
  LDA.w SprYSpeed, X
  BPL .dec_y
  CMP.b #$ED : BCC .done ; clamp symmetrically at -$14 ($EC)
.dec_y
  DEC A : STA.w SprYSpeed, X
.done
  RTS
}

; ------------------------------------------------------------------------------
; Draw: 2 x 16x16 OAM sprites (Poe body CHR $EC + swinging lantern CHR $EE).
; Uses universal OAM Palette 4 ($08) on Page 1 ($01) with flash-safe palette
; XOR so SprFlash never flips nametable bit 0.
; ------------------------------------------------------------------------------
Sprite_NightPoe_Draw:
{
  ; Wait until NMI finishes uploading our 256B tiles (never flash garbage).
  LDA.l NightPoe_VramState : CMP.b #$01 : BNE .skip

  ; Ethereal phase-shift flicker: hide on alternating 2-frame ticks.
  LDA.w SprAction, X : BEQ .solid_vis
  LDA.b $1A : AND.b #$02 : BNE .skip
.solid_vis

  JSL Sprite_PrepOamCoord : BCC .on_screen
.skip
  RTS

.on_screen
  JSL Sprite_OAM_AllocateDeferToPlayer

  ; Screen base ($00/$01 = X, $02/$03 = Y) = SprWorld - Camera ($E2/$E8)
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  LDA.w SprY, X : STA.b $02
  LDA.w SprYH, X : STA.b $03
  REP #$20
  LDA.b $00 : SEC : SBC.b $E2 : STA.b $00
  LDA.b $02 : SEC : SBC.b $E8 : STA.b $02
  SEP #$20

  ; 8-step vertical ghost float bob (-2..+2 px)
  LDA.w SprMiscC, X : LSR #3 : AND.b #$07 : TAY
  LDA.w .bob_y, Y : STA.b $04
  STZ.b $05
  BPL .bob_pos
    DEC.b $05
.bob_pos
  REP #$20
  LDA.b $02 : CLC : ADC.b $04 : STA.b $02
  SEP #$20

  ; Flash-safe property byte in $0D:
  ;   Base = Priority 2 ($20) | Page 1 ($01) | H-flip ($40 if facing right)
  ;   Palette bits = ((SprFlash,X << 1) ^ $08) & $0E (OAM Pal 4 = $08)
  LDA.w SprFlash, X : ASL A : EOR.b #$08 : AND.b #$0E : STA.b $0C
  LDA.b #$21 ; facing Left (native EoW art faces left)
  LDY.w SprMiscA, X : BEQ .prop_ok
    LDA.b #$61 ; H-flip for facing Right
.prop_ok
  ORA.b $0C : STA.b $0D

  ; --- OAM Slot 0: Poe Body (CHR $EC, 16x16) at ($00/$01, $02/$03) ---
  LDY.b #$00
  LDA.b $00 : STA.b $08
  LDA.b $01 : STA.b $09
  LDA.b $02 : STA.b $0A
  LDA.b $03 : STA.b $0B
  LDA.b #$EC : STA.b $0E
  JSR NightPoe_Emit16x16

  ; --- OAM Slot 1: Swinging Lantern (CHR $EE, 16x16) ---
  ; Positioned 9 px ahead of facing direction and +4 + sway px below body top.
  LDA.w SprMiscC, X : LSR #4 : AND.b #$03 : TAY
  LDA.w .sway_y, Y : CLC : ADC.b #$04 : STA.b $04
  STZ.b $05
  LDA.w SprMiscA, X : BNE .lantern_right
    LDA.b #$F7 : STA.b $06 ; -9 px (left)
    LDA.b #$FF : STA.b $07
    BRA .lantern_pos
.lantern_right
  LDA.b #$09 : STA.b $06 ; +9 px (right)
  STZ.b $07
.lantern_pos
  REP #$20
  LDA.b $00 : CLC : ADC.b $06 : STA.b $08
  LDA.b $02 : CLC : ADC.b $04 : STA.b $0A
  SEP #$20
  LDY.b #$04
  LDA.b #$EE : STA.b $0E
  JSR NightPoe_Emit16x16
  RTS

.bob_y
  db 0, 1, 2, 1, 0, $FF, $FE, $FF
.sway_y
  db 0, 1, 0, $FF
}

; Emit one 16x16 OAM sprite at OAM byte offset Y (0 or 4).
; In: $08/$09 = screen X16, $0A/$0B = screen Y16, $0D = prop, $0E = CHR.
; True SNES 9-bit 16x16 clipping:
;   X in 0..255 ($0000..$00FF)  -> X=$08, HI=$02 (16x16, X-MSB=0)
;   X in -15..-1 ($FFF1..$FFFF) -> X=$08, HI=$03 (16x16, X-MSB=1 left clip)
;   X <= -16 or X >= 256        -> hidden (X=0, Y=$F0, HI=$00)
NightPoe_Emit16x16:
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
; NMI VRAM Streamer — chained from Bombchu_NmiUpload right after GustJar_NmiUpload.
; Entry: M=8, X=16, DBR=$00; DMA0=$1801, VMAIN=$80.
; Exit:  A, X, Y, P, DBR preserved; $4304=$7E, $4302=$0ADC restored cleanly.
; Fast path: 4 cycles when NightPoe_VramState bit 7 is clear (idle or uploaded).
; ------------------------------------------------------------------------------
NightPoe_NmiUpload:
{
  PHP : PHA
  LDA.l NightPoe_VramState : BPL .fast_exit

  ; Upload only during active gameplay modules ($07 Indoors, $09 OW, $0B Special OW).
  LDA.b $10 : CMP.b #$07 : BEQ .mod_ok
  CMP.b #$09 : BEQ .mod_ok
  CMP.b #$0B : BEQ .mod_ok
.fast_exit
  PLA : PLP : RTL

.mod_ok
  PHX : PHY
  LDA.b #NightPoe_GfxStart>>16 : STA.w $4304

  ; Poe Body 16x16 -> VRAM $5EC0 (top $EC/$ED) & $5FC0 (bot $FC/$FD)
  LDX.w #$5EC0 : LDY.w #NightPoe_BodyTop : JSR .dma_row
  LDX.w #$5FC0 : LDY.w #NightPoe_BodyBot : JSR .dma_row

  ; Poe Lantern 16x16 -> VRAM $5EE0 (top $EE/$EF) & $5FE0 (bot $FE/$FF)
  LDX.w #$5EE0 : LDY.w #NightPoe_LanternTop : JSR .dma_row
  LDX.w #$5FE0 : LDY.w #NightPoe_LanternBot : JSR .dma_row

  LDA.b #$01 : STA.l NightPoe_VramState

  ; Restore animated BG DMA defaults for $008B5C
  LDA.b #$7E : STA.w $4304
  REP #$20
  LDA.w $0ADC : STA.w $4302
  SEP #$20
  PLY : PLX : PLA : PLP
  RTL

  ; Transfer 64 bytes from Y -> VRAM word X on DMA0 ($1801, VMAIN=$80).
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
; GameyFireBro EoW Poe + Lantern 4BPP tiles (256 bytes = 2 x 16x16 blocks).
; Source: Data/graphics/sprites/gameyfirebro/eow_poe_lantern/sheet.4bpp
; (tiles $08/$09/$18/$19 body + $0A/$0B/$1A/$1B lantern), remapped cleanly to
; Universal OAM Palette 4 ({0:0, 1:5, 2:7, 3:7, 4:6, 5:1, 6:4, 7:2, 8:4, 9:1}).
; Verified byte-exact by Tests/test_night_poe.py.
; ------------------------------------------------------------------------------
NightPoe_GfxStart:
NightPoe_BodyTop:
  db $01,$00,$01,$00,$0E,$01,$3F,$00,$5C,$23,$5E,$21,$FF,$00,$DD,$00
  db $01,$00,$01,$00,$0F,$00,$30,$00,$63,$00,$7F,$00,$BF,$00,$BF,$00
  db $80,$00,$40,$80,$60,$80,$20,$C0,$10,$E0,$B8,$F0,$58,$F0,$BC,$78
  db $80,$00,$C0,$00,$A0,$00,$E0,$00,$F0,$00,$F8,$00,$F8,$00,$FC,$00
NightPoe_BodyBot:
  db $AB,$40,$7F,$00,$5E,$00,$40,$00,$C0,$40,$A3,$80,$D7,$00,$00,$00
  db $FF,$00,$7F,$00,$7F,$00,$7F,$00,$FF,$00,$FF,$00,$DF,$00,$00,$00
  db $9C,$78,$BC,$78,$88,$70,$A6,$78,$F9,$7E,$7E,$3C,$FC,$30,$30,$00
  db $FC,$00,$FC,$00,$F8,$00,$FE,$00,$FF,$00,$FE,$00,$FC,$00,$30,$00
NightPoe_LanternTop:
  db $01,$00,$03,$01,$07,$02,$0F,$00,$1F,$0F,$3F,$1F,$1F,$00,$1F,$00
  db $01,$00,$03,$00,$07,$00,$0F,$00,$1F,$00,$3F,$00,$1F,$00,$17,$00
  db $80,$00,$C0,$00,$E0,$40,$F0,$00,$F8,$F0,$FC,$F8,$F8,$00,$F8,$80
  db $80,$00,$40,$00,$E0,$00,$F0,$00,$F8,$00,$FC,$00,$F8,$00,$E8,$00
NightPoe_LanternBot:
  db $1F,$01,$1E,$03,$1E,$03,$1C,$03,$1D,$02,$0F,$00,$0F,$07,$0F,$00
  db $17,$00,$16,$00,$16,$00,$14,$00,$14,$00,$0F,$00,$0F,$00,$0F,$00
  db $F8,$80,$F8,$00,$78,$80,$B8,$40,$98,$60,$F0,$00,$F0,$E0,$F0,$00
  db $A8,$00,$28,$00,$28,$00,$28,$00,$08,$00,$F0,$00,$F0,$00,$F0,$00
NightPoe_GfxEnd:

assert NightPoe_GfxEnd-NightPoe_GfxStart == $0100, "Night Poe GFX must be 256 bytes (2 x 16x16)"
assert (NightPoe_GfxStart>>16) == ((NightPoe_GfxEnd-1)>>16), "Night Poe DMA source crossed bank"

NightPoe_CodeEnd:
print "Night Poe bytes: ", dec(NightPoe_CodeEnd-NightPoe_CodeStart)
