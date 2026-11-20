; ==============================================================================
; Sprites/Objects/lily_pad.asm — Rideable lily pad (Minish Cap Gust Jar, $AD)
; ==============================================================================
; Wired in Sprites/all_sprites.asm (Bank $32, bank-neutral PHK/PLB, outward
; calls are JSL) and registered in Sprites/registry.csv as Sprite_LilyPad ($AD).
;
; Behavior:
;   - Floats on deep/shallow water (tile types $08, $09, $4B). Other tiles,
;     including walkable shore and cliffs, stop that axis and zero velocity
;     so the pad never enters a bank or wall.
;   - While Link's center/feet overlap the 32x24 deck, swim ($5D=$04),
;     pit-fall ($5D=$01), slip ($5B) and deep-water ($0345) are cleared.
;     Pad movement is added to Link. Stepping onto a walkable shore tile
;     (KORL shore table) dismounts in place. A solid/cliff/pit under the
;     feet restores the last on-pad position instead of sticking.
;   - Gust Jar recoil: while Link is aboard (SprMiscA != 0), one impulse per
;     Gust Blast (!GustJarState==2), opposite !GustJarDir, speed =
;     min(tier,3)*2 px/frame (2/4/6). Inhale (!GustJarState==1) builds tier
;     without premature recoil. Glide decays by 1 px/frame.
;   - Draw: 12 8x8 tiles (32x24) from CHR $42/$43/$52/$53/$7C/$7D, OAM
;     priority under Link (Region B, priority 2, universal OAM palette 1:
;     emerald leaf green in LW/UW/Lyra, olive-moss in DW/Abyss). True 9-bit
;     SNES OAM X clipping: screen X in 0..255 uses X-MSB=0, X in -7..-1 uses
;     X-MSB=1 for smooth left-edge clip, and X <= -8 or X >= 256 hides the
;     tile (Y=$F0, HI=0).
;
; Gust Jar WRAM (Items/gust_jar.asm, not modified):
;   $0273 state, $0276 tier, $0277 dir, $027F flags.
;
; Graphics: six 4bpp tiles (192 bytes) uploaded during forced blank via
; LilyPad_UploadTiles (chained from DungeonWeb_UploadCommonArt at $00E726) to
; VRAM words $4420 ($42/$43), $4520 ($52/$53), and $47C0 ($7C/$7D) — verified
; 100% blank on UW GFX_7D ($0AA4=$0A) and gated to Lyra Sea ($8A in $90..$BF)
; outdoors so Kalyxo LW/DW wooden signposts and $60-$65 pickups stay intact.
; ==============================================================================

!SPRID              = Sprite_LilyPad
!NbrTiles           = 11  ; 12 8x8 tiles (32x24)
!Harmless           = 01
!HVelocity          = 00
!Health             = 00
!Damage             = 00
!DeathAnimation     = 01
!ImperviousAll      = 01
!SmallShadow        = 00
!Shadow             = 00
!Palette            = 01
!Hitbox             = 00
!Persist            = 01
!Statis             = 01
!CollisionLayer     = 00
!CanFall            = 00
!DeflectArrow       = 00
!WaterSprite        = 00
!Blockable          = 00
!Prize              = 00
!Sound              = 00
!Interaction        = 01
!Statue             = 00
!DeflectProjectiles = 00
!ImperviousArrow    = 01
!ImpervSwordHammer  = 01
!Boss               = 00

%Set_Sprite_Properties(Sprite_LilyPad_Prep, Sprite_LilyPad_Long)

!LilyGustState = $0273
!LilyGustTier  = $0276
!LilyGustDir   = $0277
!LilyGustFlags = $027F

LilyPad_CodeStart:

; ------------------------------------------------------------------------------
Sprite_LilyPad_Prep:
{
  PHB : PHK : PLB
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprMiscA, X
  STZ.w SprMiscB, X
  STZ.w SprMiscC, X
  STZ.w SprAction, X
  LDA.b #$0B : STA.w SprNbrOAM, X
  PLB
  RTL
}

Sprite_LilyPad_Long:
{
  PHB : PHK : PLB
  LDA.b $10 : CMP.b #$0E : BEQ .return
  JSR Sprite_LilyPad_Draw
  JSL Sprite_CheckActive : BCC .return
    JSR Sprite_LilyPad_Main
.return
  PLB
  RTL
}

Sprite_LilyPad_Main:
{
  INC.w SprMiscC, X
  LDA.w SprMiscA, X : STA.b $0E ; was aboard, before this frame's glide
  JSR LilyPad_Gust
  JSR LilyPad_Move
  LDA.b $0E : BEQ .try_board
    JSR LilyPad_AddDelta
    JSR LilyPad_LinkOnDeck : BCC .dismount
      JSR LilyPad_SuppressHazards
      JSR LilyPad_SaveLink
      BRA .friction
.try_board
  JSR LilyPad_LinkOnDeck : BCC .friction
    LDA.b #$01 : STA.w SprMiscA, X
    JSR LilyPad_SuppressHazards
    JSR LilyPad_SaveLink
    BRA .friction
.dismount
  JSR LilyPad_Dismount
.friction
  JSR LilyPad_Friction
  RTS
}

; ------------------------------------------------------------------------------
; One recoil impulse per Gust Blast (!GustJarState == 2) while Link is aboard.
; Opposite of !GustJarDir. Inhale (state == 1) charges tier without recoiling.
; ------------------------------------------------------------------------------
LilyPad_Gust:
{
  LDA.w SprMiscA, X : BEQ .idle
  LDA.w !LilyGustState : CMP.b #$02 : BNE .idle
  LDA.w SprMiscB, X : BNE .done
  LDA.b #$01 : STA.w SprMiscB, X
  JSR LilyPad_Impulse
  RTS
.idle
  STZ.w SprMiscB, X
.done
  RTS
}

LilyPad_Impulse:
{
  LDA.w !LilyGustTier : BEQ .zero
  CMP.b #$04 : BCC .scaled
    LDA.b #$03
.scaled
  ASL A : STA.b $0A ; 2, 4 or 6
  LDA.w !LilyGustDir : LSR A : TAY
  LDA.w .sign_x, Y : STA.b $08
  LDA.w .sign_y, Y : STA.b $09
  JSR .axis_x
  JSR .axis_y
  RTS
.zero
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  RTS

.axis_x
  LDA.b $08 : BEQ .clear_x
  BMI .neg_x
    LDA.b $0A : STA.w SprXSpeed, X
    RTS
.neg_x
    LDA.b $0A : EOR.b #$FF : INC A : STA.w SprXSpeed, X
    RTS
.clear_x
  STZ.w SprXSpeed, X
  RTS

.axis_y
  LDA.b $09 : BEQ .clear_y
  BMI .neg_y
    LDA.b $0A : STA.w SprYSpeed, X
    RTS
.neg_y
    LDA.b $0A : EOR.b #$FF : INC A : STA.w SprYSpeed, X
    RTS
.clear_y
  STZ.w SprYSpeed, X
  RTS

  ; Indexed by dir>>1. +1 pushes positive world axis. Recoil is opposite facing:
  ; up->+Y, down->-Y, left->+X, right->-X.
.sign_x
  db $00, $00, $01, $FF
.sign_y
  db $01, $FF, $00, $00
}

; ------------------------------------------------------------------------------
; Glide. $04/$05 = applied dx, $06/$07 = applied dy (signed words).
; A leading edge on anything except water ($08/$09/$4B) cancels that axis.
; ------------------------------------------------------------------------------
LilyPad_Move:
{
  JSR LilyPad_MoveX
  JSR LilyPad_MoveY
  RTS
}

LilyPad_MoveX:
{
  STZ.b $04 : STZ.b $05
  LDA.w SprXSpeed, X : STA.b $0F : BEQ .exit
  JSR LilyPad_BlockedX : BCC .slide
    STZ.w SprXSpeed, X
    STZ.b $04 : STZ.b $05
    RTS
.slide
  STZ.b $09
  LDA.b $0F : BPL .add
    DEC.b $09
.add
  LDA.w SprX, X : CLC : ADC.b $0F : STA.w SprX, X
  LDA.w SprXH, X : ADC.b $09 : STA.w SprXH, X
  LDA.b $0F : STA.b $04
  LDA.b $09 : STA.b $05
.exit
  RTS
}

LilyPad_MoveY:
{
  STZ.b $06 : STZ.b $07
  LDA.w SprYSpeed, X : STA.b $0F : BEQ .exit
  ; Preserve MoveX's applied dx ($04/$05): Sprite_GetTileAttr clobbers $00-$07.
  ; PLA/STA do not modify Carry, so BCC still tests LilyPad_BlockedY's result.
  LDA.b $04 : PHA : LDA.b $05 : PHA
  JSR LilyPad_BlockedY
  PLA : STA.b $05 : PLA : STA.b $04
  BCC .slide
    STZ.w SprYSpeed, X
    STZ.b $06 : STZ.b $07
    RTS
.slide
  STZ.b $09
  LDA.b $0F : BPL .add
    DEC.b $09
.add
  LDA.w SprY, X : CLC : ADC.b $0F : STA.w SprY, X
  LDA.w SprYH, X : ADC.b $09 : STA.w SprYH, X
  LDA.b $0F : STA.b $06
  LDA.b $09 : STA.b $07
.exit
  RTS
}

; C=1 if the horizontal leading edge hits a non-water tile. Preserves $0F.
; Sprite_GetTileAttr clobbers $00-$07, so each probe rewrites both coordinates.
LilyPad_BlockedX:
{
  LDA.b #$04 : JSR LilyPad_ProbeLeadingX : BCS .hit
  LDA.b #$14 : JSR LilyPad_ProbeLeadingX
  RTS
.hit
  SEC
  RTS
}

; In: A = unsigned Y offset (4 or $14). Probes destination leading X edge.
LilyPad_ProbeLeadingX:
{
  STA.b $0A
  LDA.w SprY, X : CLC : ADC.b $0A : STA.b $00
  LDA.w SprYH, X : ADC.b #$00 : STA.b $01
  LDA.b $0F : BMI .left
    CLC : ADC.b #$1F : STA.b $0A
    LDA.w SprX, X : CLC : ADC.b $0A : STA.b $02
    LDA.w SprXH, X : ADC.b #$00 : STA.b $03
    BRA .go
.left
    LDA.w SprX, X : CLC : ADC.b $0F : STA.b $02
    LDA.w SprXH, X : ADC.b #$FF : STA.b $03
.go
  JSR LilyPad_TileBlocks
  RTS
}

LilyPad_BlockedY:
{
  LDA.b #$04 : JSR LilyPad_ProbeLeadingY : BCS .hit
  LDA.b #$18 : JSR LilyPad_ProbeLeadingY
  RTS
.hit
  SEC
  RTS
}

; In: A = unsigned X offset. Probes destination leading Y edge.
LilyPad_ProbeLeadingY:
{
  STA.b $0A
  LDA.w SprX, X : CLC : ADC.b $0A : STA.b $02
  LDA.w SprXH, X : ADC.b #$00 : STA.b $03
  LDA.b $0F : BMI .up
    CLC : ADC.b #$17 : STA.b $0A
    LDA.w SprY, X : CLC : ADC.b $0A : STA.b $00
    LDA.w SprYH, X : ADC.b #$00 : STA.b $01
    BRA .go
.up
    LDA.w SprY, X : CLC : ADC.b $0F : STA.b $00
    LDA.w SprYH, X : ADC.b #$FF : STA.b $01
.go
  JSR LilyPad_TileBlocks
  RTS
}

; In: $00=Y16, $02=X16. C=1 when the tile is not floatable water.
; Sprite_GetTileAttr exits M=8/X=8 and may clobber $00-$07. Preserves X and $0F.
LilyPad_TileBlocks:
{
  LDA.b $0F : PHA
  PHX
  LDA.w SprFloor, X
  JSL Sprite_GetTileAttr
  PLX
  CMP.b #$08 : BEQ .water
  CMP.b #$09 : BEQ .water
  CMP.b #$4B : BEQ .water
    PLA : STA.b $0F
    SEC
    RTS
.water
  PLA : STA.b $0F
  CLC
  RTS
}

LilyPad_Friction:
{
  LDA.w SprXSpeed, X : BEQ .y
  BMI .negx
    DEC A : STA.w SprXSpeed, X
    BRA .y
.negx
    INC A : STA.w SprXSpeed, X
.y
  LDA.w SprYSpeed, X : BEQ .done
  BMI .negy
    DEC A : STA.w SprYSpeed, X
    RTS
.negy
    INC A : STA.w SprYSpeed, X
.done
  RTS
}

; ------------------------------------------------------------------------------
; Link deck, carry, dismount.
; ------------------------------------------------------------------------------
LilyPad_AddDelta:
{
  REP #$20
  LDA.b $22 : CLC : ADC.b $04 : STA.b $22
  LDA.b $20 : CLC : ADC.b $06 : STA.b $20
  SEP #$20
  RTS
}

; C=1 when Link's center X and feet Y sit on the 32x24 deck.
LilyPad_LinkOnDeck:
{
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  LDA.w SprY, X : STA.b $02
  LDA.w SprYH, X : STA.b $03
  REP #$20
  ; Center X must sit in [padX, padX+32). Feet Y = LinkY+14, window [padY-4, padY+22).
  LDA.b $22 : CLC : ADC.w #$0008 : STA.b $08
  CMP.b $00 : BCC .off
  LDA.b $00 : CLC : ADC.w #$0020
  CMP.b $08 : BCC .off
  BEQ .off
  ; Check feetY + 4 >= padY without unsigned underflow when padY < 4.
  LDA.b $20 : CLC : ADC.w #$0012
  CMP.b $02 : BCC .off
  LDA.b $20 : CLC : ADC.w #$000E : STA.b $08
  LDA.b $02 : CLC : ADC.w #$0016
  CMP.b $08 : BCC .off
  BEQ .off
  SEP #$20
  SEC
  RTS
.off
  SEP #$20
  CLC
  RTS
}

LilyPad_SuppressHazards:
{
  LDA.b $5D : CMP.b #$04 : BEQ .ground
  CMP.b #$01 : BNE .slip
.ground
  STZ.b $5D
.slip
  STZ.b $5B
  STZ.w $0345
  RTS
}

LilyPad_SaveLink:
{
  LDA.b $22 : STA.w SprMiscD, X
  LDA.b $23 : STA.w SprMiscE, X
  LDA.b $20 : STA.w SprMiscF, X
  LDA.b $21 : STA.w SprMiscG, X
  RTS
}

LilyPad_RestoreLink:
{
  LDA.w SprMiscD, X : STA.b $22
  LDA.w SprMiscE, X : STA.b $23
  LDA.w SprMiscF, X : STA.b $20
  LDA.w SprMiscG, X : STA.b $21
  RTS
}

; Feet tile: 0 solid/cliff (restore), 1 walkable shore, 2 deep water (swim off).
LilyPad_Dismount:
{
  LDA.b $20 : CLC : ADC.b #$0E : STA.b $00
  LDA.b $21 : ADC.b #$00 : STA.b $01
  LDA.b $22 : CLC : ADC.b #$08 : STA.b $02
  LDA.b $23 : ADC.b #$00 : STA.b $03
  PHX
  LDA.w SprFloor, X
  JSL Sprite_GetTileAttr
  PLX
  CMP.b #$08 : BEQ .deep
  CMP.b #$4B : BEQ .deep
  CMP.b #$58 : BCS .solid
  PHY
  TAY
  LDA.w LilyPad_ShoreTable, Y
  PLY
  CMP.b #$00 : BEQ .solid
    STZ.w SprMiscA, X
    LDA.b $5D : BEQ .shore_clear
    CMP.b #$01 : BEQ .shore_clear
    CMP.b #$04 : BNE .shore_keep
.shore_clear
    STZ.b $5D
.shore_keep
    STZ.b $5B
    STZ.w $0345
    RTS
.deep
  STZ.w SprMiscA, X
  LDA.b #$04 : STA.b $5D
  LDA.b #$01 : STA.w $0345
  STZ.b $5B
  RTS
.solid
  JSR LilyPad_RestoreLink
  RTS
}

; 1 = walkable dry shore or shallow water. Mirrors Masks/korl_mount.asm.
LilyPad_ShoreTable:
  db 1,0,0,0,0,1,1,1, 0,1,0,0,0,0,0,0
  db 0,0,0,0,1,1,1,1, 0,0,0,0,0,0,0,0
  db 0,1,0,1,1,1,0,0, 0,0,0,0,0,0,0,0
  db 0,0,0,0,0,0,0,0, 1,1,1,1,1,0,0,0
  db 1,1,1,0,0,1,0,1, 1,1,0,0,1,1,1,1
  db 0,0,0,0,0,0,0,0

; ------------------------------------------------------------------------------
; OAM. Screen origin is sprite world minus camera $E2/$E8, not the raw
; PrepOamCoord low byte, so a negative X cannot wrap to the right edge.
; ------------------------------------------------------------------------------
Sprite_LilyPad_Draw:
{
  JSL Sprite_PrepOamCoord
  LDA.b #$30
  JSL OAM_AllocateFromRegionB

  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  LDA.w SprY, X : STA.b $02
  LDA.w SprYH, X : STA.b $03
  REP #$20
  LDA.b $00 : SEC : SBC.b $E2 : STA.b $00
  LDA.b $02 : SEC : SBC.b $E8 : STA.b $02
  SEP #$20

  LDA.w SprMiscC, X : AND.b #$06 : LSR A : TAY
  LDA.w .bob, Y : STA.b $0C
  STZ.b $0D
  LDA.b $0C : BPL .bob_pos
    DEC.b $0D
.bob_pos

  PHX
  LDX.b #$00
  LDY.b #$00
.tile
  PHX
  TXA : ASL A : TAX
  REP #$20
  LDA.b $00 : CLC : ADC.w .xoff, X : STA.b $08
  LDA.b $02 : CLC : ADC.w .yoff, X : CLC : ADC.b $0C : STA.b $0A
  SEP #$20
  PLX

  ; True 9-bit SNES OAM X clipping for 8x8 tiles:
  ;   0..255 ($0000..$00FF) -> X=$08, HI=0
  ;  -7..-1  ($FFF9..$FFFF) -> X=$08, HI=1 (smooth left-edge clip)
  ;  <= -8 or >= 256        -> hidden (X=0, Y=$F0, HI=0)
  LDA.b $09 : BEQ .x_pos
  CMP.b #$FF : BNE .hide_tile
  LDA.b $08 : CMP.b #$F9 : BCC .hide_tile
    STA.b ($90), Y
    LDA.b #$01 : STA.b $0E
    BRA .y_byte
.x_pos
  STZ.b $0E
  LDA.b $08 : STA.b ($90), Y
.y_byte
  INY
  LDA.b $0B : BNE .hide_y
  LDA.b $0A : CMP.b #$E0 : BCS .hide_y
  STA.b ($90), Y
  BRA .glyph
.hide_tile
  LDA.b #$00 : STA.b ($90), Y
  INY
.hide_y
  LDA.b #$F0 : STA.b ($90), Y
  STZ.b $0E
.glyph
  INY
  LDA.w LilyPad_DrawChr, X : STA.b ($90), Y
  INY
  LDA.w LilyPad_DrawProp, X : STA.b ($90), Y
  PHY
  TYA : LSR #2 : TAY
  LDA.b $0E : STA.b ($92), Y
  PLY
  INY
  INX
  CPX.b #$0C : BCC .tile
  PLX
  RTS

.bob
  db 0, 1, 0, $FF
.xoff
  dw 0, 8, 16, 24
  dw 0, 8, 16, 24
  dw 0, 8, 16, 24
.yoff
  dw 0, 0, 0, 0
  dw 8, 8, 8, 8
  dw 16, 16, 16, 16
}

LilyPad_DrawChr:
  db $42, $43, $43, $42
  db $52, $53, $53, $52
  db $7C, $7D, $7D, $7C
LilyPad_DrawProp:
  db $22, $22, $62, $62 ; Priority 2, Universal OAM Pal 1, H-flip right half
  db $22, $22, $62, $62
  db $22, $22, $62, $62

; ------------------------------------------------------------------------------
; 4bpp OBJ tiles $42/$43/$52/$53/$7C/$7D (192 bytes, left half mirrored to 32x24).
; Universal OAM Palette 1: 5=#282828 outline, 3=#388038 emerald leaf,
; 4=#50B090 sunlit mint rim & veins (LW/UW/Lyra; warm olive-moss in DW/Abyss).
; ------------------------------------------------------------------------------
LilyPad_Tile42: ; top-left rim + curve
  db $07,$00,$18,$00,$20,$00,$4F,$0F,$5E,$1E,$BF,$3F,$B3,$33,$BC,$3C
  db $07,$00,$1F,$00,$3F,$00,$70,$00,$61,$00,$C0,$00,$CC,$00,$C3,$00
LilyPad_Tile43: ; top-inner + center V-notch
  db $F0,$00,$08,$00,$04,$00,$F2,$F0,$F9,$F8,$7D,$7C,$BF,$BE,$DF,$DE
  db $F0,$00,$F8,$00,$FC,$00,$0E,$00,$07,$00,$83,$00,$41,$00,$21,$00
LilyPad_Tile52: ; mid-left rim + veins
  db $BF,$3F,$FF,$7F,$E3,$63,$FC,$7C,$FF,$7F,$FC,$7C,$F3,$73,$FF,$7F
  db $C0,$00,$80,$00,$9C,$00,$83,$00,$80,$00,$83,$00,$8C,$00,$80,$00
LilyPad_Tile53: ; mid-inner leaf hub
  db $6E,$6E,$B4,$B4,$D9,$D9,$67,$67,$9C,$9C,$EB,$EB,$DF,$DF,$BF,$BF
  db $91,$00,$4B,$00,$26,$00,$98,$00,$63,$00,$14,$00,$20,$00,$40,$00
LilyPad_Tile7C: ; bottom-left curve
  db $FF,$7F,$7E,$3E,$7F,$3F,$3F,$1F,$1F,$0F,$0F,$03,$03,$00,$00,$00
  db $80,$00,$41,$00,$40,$00,$20,$00,$10,$00,$0C,$00,$03,$00,$00,$00
LilyPad_Tile7D: ; bottom-inner rim
  db $7F,$7F,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$7F,$7F,$00
  db $80,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$80,$00,$7F,$00

; Entry: M=8, X=8, DBR may be anything (chained from DungeonWeb_UploadCommonArt
; during LoadCommonSprites forced blank with VMAIN=$80). Writes 6 tiles (192 B)
; to verified-safe OBJ slots $42/$43 ($4420), $52/$53 ($4520), $7C/$7D ($47C0),
; restores VMADDR = $4800 for GFX_79/GFX_7A, and preserves X, DBR, P.
LilyPad_UploadTiles:
{
  PHP
  PHB : PHK : PLB
  REP #$30
  PHX

  LDA.w #$4420 : STA.w $2116
  LDX.w #$0000
.row0
  LDA.w LilyPad_Tile42, X : STA.w $2118
  INX #2
  CPX.w #$0040 : BCC .row0

  LDA.w #$4520 : STA.w $2116
  LDX.w #$0000
.row1
  LDA.w LilyPad_Tile52, X : STA.w $2118
  INX #2
  CPX.w #$0040 : BCC .row1

  LDA.w #$47C0 : STA.w $2116
  LDX.w #$0000
.row2
  LDA.w LilyPad_Tile7C, X : STA.w $2118
  INX #2
  CPX.w #$0040 : BCC .row2

  LDA.w #$4800 : STA.w $2116
  PLX
  PLB
  PLP
  RTL
}

LilyPad_CodeEnd:
assert LilyPad_CodeEnd-LilyPad_CodeStart > 0, "Lily pad assembled empty"
print "Lily pad bytes: ", dec(LilyPad_CodeEnd-LilyPad_CodeStart)
