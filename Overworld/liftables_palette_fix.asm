; =============================================================================
; Overworld Liftables Palette & Revealed-Tile16 Fix (Bank $34)
;
; Pure-ASM fixes (zero base-ROM writes) for QUEUE325:
;
; 1. Lifted Overworld Scenery OAM Palettes & Live BG-Derived CGRAM Sync
;    (Sprite $EC / ThrowableScenery, Garnish $16 debris):
;    - Dark World ($40-$7F) uses CommonSprite[$0B] where both Bush ($46) and
;      Small Rock/Skull ($44) use 4bpp indices 9/11/12. Vanilla assigns both
;      to SP6 ($0C, Env[8]), so editing Env[8][11..12] to brown for DW bushes
;      turned lifted DW sage-green Small Light Rocks ($020F) muddy brown!
;    - Fix: Outdoors in Dark World ($8A & $40 != 0), route Small Light Rock
;      ($0DB0=1) to SP0 ($00) instead of SP6 ($0C) when translucency $0ABD==0,
;      separating DW rocks (SP0) from DW bushes (SP6).
;    - Sync the active lifted object's exact SP6[9..15] / SP0[9..15] colors
;      directly from the map's live BG palette in $7EC300 (aux) and $7EC500
;      (live CGRAM) -- automatically preserving MainPal biome variants (DW
;      MainPal 1 & 2, LW Snow $03-$07, SW Snow $84, SW Slate $86/$8C, LW Heavy
;      Rock $0239), Special Overworld Record 411 packed palettes, and TimeSystem
;      day/night tinting. Only increments $15 when a live CGRAM word changes.
;    - Indoors ($1B != 0): 100% vanilla behavior (zero CGRAM writes).
;
; 2. Pure-ASM Bank $1B Revealed-Tile16 Lookup Fixes:
;    - Recognize DW Sign Tile16 $017D (DW $51/$5B/$5C/$6B) alongside LW Sign
;      $0101 in Overworld_HandleLiftableTiles so lifting a DW sign removes it
;      instead of infinitely cloning it.
;    - On DW area $63 ($63/$64/$6B/$6C, slot-6 Sheet $F8 where 18F/19F are
;      overwritten scenery and 1AF/1BF are blank), reveal standard DW grass
;      $0172 under cut/lifted/bombed/dashed bushes ($0036) and lifted sign
;      ($017D) instead of corrupted $0DC7 / blank $0DC6.
;    - Ignore overwritten Tile16 $072A (brick wall masonry on LW $22, all
;      quadrants t00) in Bank $1B bush/cut/bomb/powder/lift checks so attacks
;      cannot destroy the wall on LW $22 into cut-bush $0DC8.
; =============================================================================

pushpc

; 1a. Sprite_SpawnThrowableTerrain_silently ($0681A9, 6B):
;     Replaces: LDA.w SpriteDraw_ThrownItem_palette,Y : STA.w $0F50,X
assert read4($0681A9) == $9DAACAB9 && read2($0681AD) == $0F50, "Sprite_SpawnThrowableTerrain_silently palette store moved"
org $0681A9 ; @hook module=Overworld name=Liftables_InitPalette kind=jsl target=Liftables_InitPalette expected_m=8 expected_x=8 protected_size=6
  JSL Liftables_InitPalette
  NOP #2
assert pc() == $0681AF

; 1b. Sprite_EC_ThrownItem draw palette ($06AB38, 5B):
;     Replaces: ORA.w SpriteDraw_ThrownItem_palette,X : STA.b ($90),Y
assert read4($06AB38) == $91AACA1D && read1($06AB3C) == $90, "Sprite_EC_ThrownItem palette apply moved"
org $06AB38 ; @hook module=Overworld name=Liftables_ApplyDrawPalette kind=jsl target=Liftables_ApplyDrawPalette expected_m=8 expected_x=8 protected_size=5
  JSL Liftables_ApplyDrawPalette
  NOP
assert pc() == $06AB3D

; 1c. SpriteDraw_ThrownItem_Gigantic ($06AB79, 6B):
;     Replaces: LDA.w .offset_shadow,Y : STA.w $0F50,X
assert read4($06AB79) == $9DAB6EB9 && read2($06AB7D) == $0F50, "SpriteDraw_ThrownItem_Gigantic palette store moved"
org $06AB79 ; @hook module=Overworld name=Liftables_ApplyGiganticPalette kind=jsl target=Liftables_ApplyGiganticPalette expected_m=8 expected_x=8 protected_size=6
  JSL Liftables_ApplyGiganticPalette
  NOP #2
assert pc() == $06AB7F

; 2a. HandleItemTileAction_Overworld powder check ($1BBDC4, 5B):
;     Skip overwritten $072A (brick wall on LW $22) -> jump to .not_bush ($1BBDEC)
assert read4($1BBDC4) == $D0072AC9 && read1($1BBDC8) == $23, "Powder $072A check moved"
org $1BBDC4 ; @hook module=Overworld name=Liftables_PowderSkip072A kind=patch expected_m=16 expected_x=16 protected_size=5
  JMP.w $BDEC
  NOP #2
assert pc() == $1BBDC9

; 2b. HandleItemTileAction_Overworld sword check ($1BBE36, 5B):
;     Skip overwritten $072A (brick wall on LW $22) -> fall into OverworldTileAction_Exit
assert read4($1BBE36) == $F0072AC9 && read1($1BBE3A) == $52, "Sword $072A check moved"
org $1BBE36 ; @hook module=Overworld name=Liftables_SwordSkip072A kind=patch expected_m=16 expected_x=16 protected_size=5
  NOP #5
assert pc() == $1BBE3B

; 2c. OverworldTileAction_Bush revealed Tile16 selection ($1BBEAF, 11B):
;     Reveal $0172 on DW $63 (Sheet $F8), else $0DC7.
assert read4($1BBEAF) == $C90DC7A0 && read4($1BBEB3) == $03D0072A && read3($1BBEB7) == $0DC8A0, "OverworldTileAction_Bush reveal moved"
org $1BBEAF ; @hook module=Overworld name=Liftables_SelectBushReveal kind=jsl target=Liftables_SelectBushReveal expected_m=16 expected_x=16 protected_size=11
  JSL Liftables_SelectBushReveal
  NOP #7
assert pc() == $1BBEBA

; 2d. Overworld_HandleLiftableTiles small-object dispatch ($1BBFE3, 37B):
;     Adds DW sign $017D, DW $63 grass reveal $0172, skips overwritten $072A.
assert read4($1BBFE3) == $C90DC7A0 && read4($1BC000) == $D00101C9 && read3($1BC005) == $0DC6A0, "Overworld_HandleLiftableTiles small dispatch moved"
org $1BBFE3 ; @hook module=Overworld name=Liftables_MatchSmallLiftable kind=jml target=Liftables_MatchSmallLiftable expected_m=16 expected_x=16 protected_size=37
  JML Liftables_MatchSmallLiftable
  NOP #33
assert pc() == $1BC008

; 2e. Overworld_SmashRockPile Pegasus-dash bush check ($1BC055, 8B):
;     Reveal $0172 on DW $63 (Sheet $F8), else $0DC7.
assert read4($1BC055) == $C90DC7A0 && read4($1BC059) == $ABF00036, "Overworld_SmashRockPile dash bush check moved"
org $1BC055 ; @hook module=Overworld name=Liftables_DashBushCheck kind=jml target=Liftables_DashBushCheck expected_m=16 expected_x=16 protected_size=8
  JML Liftables_DashBushCheck
  NOP #4
assert pc() == $1BC05D

; 2f. Overworld_BombTile greenery dispatch ($1BC176, 33B):
;     Reveal $0172 on DW $63 (Sheet $F8), skip overwritten $072A, preserve $037E.
assert read4($1BC176) == $A20DC7A0 && read4($1BC18C) == $D0037EC9 && read3($1BC191) == $0DC5A0, "Overworld_BombTile greenery dispatch moved"
org $1BC176 ; @hook module=Overworld name=Liftables_BombTileMatch kind=jml target=Liftables_BombTileMatch expected_m=16 expected_x=16 protected_size=33
  JML Liftables_BombTileMatch
  NOP #29
assert pc() == $1BC197

; 3. Map32UpdateTiles Graveyard push reveals ($02AD0A-$02AD41, Q326 Option A):
;    Base ROM Tile16s $0DD3-$0DDE were overwritten by water/cliffs placed 140x on
;    SW $87/$B5/$BD. The 12 restored vanilla grave reveals live in globally
;    unreferenced slots $0EB1-$0EB8 (corpse dirt + Grave 13 stairs) and
;    $0F83-$0F86 (Grave 14 t20 pit); $0DD1/$0DD2 top edges and $0918-$091B
;    cave stairs at $02AD2A remain untouched.
assert read4($02AD0A) == $0DD40DD3 && read4($02AD12) == $0DD80DD7 && read4($02AD1A) == $0DD20DD1 && read4($02AD22) == $0DD20DD1, "Map32UpdateTiles grave reveals (corpse/stairs) moved"
org $02AD0A ; @hook module=Overworld name=Liftables_GraveyardRevealsTop kind=patch expected_m=16 expected_x=16 protected_size=32
  dw $0EB1, $0EB2, $0EB3, $0EB4 ; open grave with corpse bottom half (was $0DD3-$0DD6)
  dw $0EB5, $0EB6, $0EB7, $0EB8 ; open grave with stairs bottom half (was $0DD7-$0DDA)
  dw $0DD1, $0DD2, $0EB1, $0EB2 ; open grave with corpse top half
  dw $0DD1, $0DD2, $0EB5, $0EB6 ; open grave with stairs top half
assert pc() == $02AD2A

assert read4($02AD32) == $0DDC0DDB && read4($02AD3A) == $0DD20DD1, "Map32UpdateTiles grave reveals (pit) moved"
org $02AD32 ; @hook module=Overworld name=Liftables_GraveyardRevealsPit kind=patch expected_m=16 expected_x=16 protected_size=16
  dw $0F83, $0F84, $0F85, $0F86 ; open grave with pit bottom half (was $0DDB-$0DDE)
  dw $0DD1, $0DD2, $0F83, $0F84 ; open grave with pit top half
assert pc() == $02AD42

pullpc

; =============================================================================
; Bank $34 Implementation (M=8/X=8 for sprite hooks, M=16/X=16 for Bank $1B)
; =============================================================================

; Entry: M=8, X=8, DB=$06, X = sprite slot (0..15), Y = $0DB0,X (0..7)
; Exit:  M=8, X=8, X/Y/DB preserved, $7E0F50,X updated.
Liftables_ApplyGiganticPalette:
Liftables_InitPalette:
{
  JSR Liftables_ResolvePaletteAndSync
  STA.l $7E0F50,X
  RTL
}

; Entry: M=8, X=8, DB=$06, A = ($90),Y & $F0, X = $0DB0,slot (0..5), Y = $03
; Exit:  M=8, X=8, A = written OAM attr byte, X/Y/DB preserved.
Liftables_ApplyDrawPalette:
{
  PHA
  PHY
  TXY
  JSR Liftables_ResolvePaletteAndSync
  PLY
  ORA $01,S
  STA $01,S
  PLA
  STA.b ($90),Y
  RTL
}

; Entry: M=8, X=8, Y = object type ($0DB0,slot)
; Exit:  M=8, X=8, A = resolved OAM palette byte ($00 or $0C), X/Y/DB preserved.
;        Outdoors ($1B == 0), lazily syncs target SP6/SP0 colors from live BG
;        palettes ($7EC300/$7EC500) and increments $15 only if live CGRAM changed.
Liftables_ResolvePaletteAndSync:
{
  PHX : PHY : PHB
  PHK : PLB

  ; Indoors ($1B != 0) or unknown type (>= 8): exact vanilla palette, no CGRAM writes.
  LDA.l $7E001B : BNE .vanilla_only
  CPY.b #$08 : BCS .vanilla_only

  ; Bit 6 of $8A distinguishes Dark World / Eon Abyss ($40-$7F) from LW ($00-$3F) & SW ($80-$BF).
  LDA.l $7E008A : AND.b #$40 : BNE .dark_world

  ; --- Light World ($00-$3F) & Special Overworld ($80-$BF) ---
  LDA.w Liftables_OamPal_LW,Y : PHA
  BNE .lw_do_sync
    LDA.l $7E0ABD : BNE .pop_done
  .lw_do_sync
  TYA : ASL A : TAX
  REP #$30
  TXA : AND.w #$00FF : TAX
  LDA.w Liftables_SyncPtrs_LW,X
  BEQ .sync_done_16
    TAX
    JSR Liftables_SyncPairsRun
    BEQ .sync_done_16
      SEP #$20
      LDA.l $7E0015 : INC A : STA.l $7E0015
      REP #$20
  .sync_done_16
  SEP #$30
  .pop_done
  PLA
  PLB : PLY : PLX
  RTS

  ; --- Dark World / Eon Abyss ($40-$7F) ---
  .dark_world
  LDA.w Liftables_OamPal_DW,Y
  BNE .dw_push_and_sync
    LDA.l $7E0ABD : BEQ .dw_sp0_ok
      ; Translucency active: keep vanilla $0C for Y=1, skip SP0 CGRAM write.
      CPY.b #$01 : BNE .dw_trans_done
        LDA.b #$0C
      .dw_trans_done
      PLB : PLY : PLX
      RTS
  .dw_sp0_ok
  LDA.b #$00
  .dw_push_and_sync
  PHA
  TYA : ASL A : TAX
  REP #$30
  TXA : AND.w #$00FF : TAX
  LDA.w Liftables_SyncPtrs_DW,X
  BEQ .sync_done_16
    TAX
    JSR Liftables_SyncPairsRun
    BEQ .sync_done_16
      SEP #$20
      LDA.l $7E0015 : INC A : STA.l $7E0015
      REP #$20
  BRA .sync_done_16

  .vanilla_only
  CPY.b #$08 : BCS .vanilla_oob
    LDA.w Liftables_OamPal_LW,Y
    PLB : PLY : PLX
    RTS
  .vanilla_oob
  TYA : TAX
  LDA.l $06AACA,X
  PLB : PLY : PLX
  RTS
}

; Entry: M=16, X=16, DB = Bank $34, X = local pointer to (src_off, dst_off) pairs (0-terminated)
; Exit:  M=16, X=16, A = dirty flag (0 = unchanged, 1 = live $7EC500 modified). Zero DP writes!
Liftables_SyncPairsRun:
{
  LDA.w #$0000 : PHA                  ; $01,S = dirty
  .loop
    LDA.w $0000,X                     ; src_off
    BEQ .done
    PHA                               ; $01,S = src_off, $03,S = dirty
    LDA.w $0002,X                     ; dst_off
    PHA                               ; $01,S = dst_off, $03,S = src_off, $05,S = dirty
    TXA : CLC : ADC.w #$0004 : PHA    ; $01,S = next_X, $03,S = dst_off, $05,S = src_off, $07,S = dirty

    ; Copy aux buffer target: $7EC300[src] -> $7EC300[dst]
    LDA $05,S : TAX
    LDA.l $7EC300,X : TAY
    LDA $03,S : TAX
    TYA
    STA.l $7EC300,X

    ; Copy live CGRAM: $7EC500[src] -> $7EC500[dst] (mark dirty only on change)
    LDA $05,S : TAX
    LDA.l $7EC500,X : TAY
    LDA $03,S : TAX
    TYA
    CMP.l $7EC500,X : BEQ .same
      STA.l $7EC500,X
      LDA.w #$0001 : STA $07,S
    .same

    PLA : TAX                         ; X = next_X
    PLA                               ; pop dst_off
    PLA                               ; pop src_off
    BRA .loop
  .done
  PLA                                 ; A = dirty
  RTS
}

; OAM palette attributes indexed by $0DB0,X (0..7):
;   0=Sign, 1=SmallLightRock, 2=LightBush, 3=GrassPoof,
;   4=DarkBush, 5=SmallHeavyRock, 6=BigLightRock, 7=BigHeavyRock
Liftables_OamPal_LW:
  db $0C, $0C, $0C, $00, $00, $00, $0C, $00

Liftables_OamPal_DW:
  db $0C, $00, $0C, $00, $00, $00, $0C, $00

Liftables_SyncPtrs_LW:
  dw Liftables_Pairs_LW_Sign          ; 0: Sign ($0101, BG[4] -> SP6[9,13])
  dw Liftables_Pairs_LW_LightRock     ; 1: Small Light Rock ($020F, BG[5] -> SP6[9,10,14,15])
  dw Liftables_Pairs_LW_Bush          ; 2: Light Bush ($0036, BG[6] -> SP6[9,11,12,13])
  dw Liftables_Pairs_LW_Grass         ; 3: Tall Grass Poof ($037E, BG[6] -> SP0[9,11,12])
  dw $0000                            ; 4: Dark Bush (unused)
  dw Liftables_Pairs_LW_HeavyRock     ; 5: Small Heavy Rock ($0239, BG[2] -> SP0[9,10,14,15])
  dw Liftables_Pairs_LW_LightRock     ; 6: Big Light Rock ($036D-$0375, BG[5] -> SP6[9,10,14,15])
  dw Liftables_Pairs_LW_HeavyRock     ; 7: Big Heavy Rock ($023B-$023E, BG[2] -> SP0[9,10,14,15])

Liftables_SyncPtrs_DW:
  dw Liftables_Pairs_DW_Sign          ; 0: DW Sign ($017D, BG[2] -> SP6[9,13,14])
  dw Liftables_Pairs_DW_LightRock     ; 1: DW Small Light Rock/Skull ($020F, BG[5] -> SP0[9,11,12])
  dw Liftables_Pairs_DW_Bush          ; 2: DW Light Bush ($0036, BG[6] -> SP6[9,11,12])
  dw $0000                            ; 3: Grass Poof
  dw $0000                            ; 4: Dark Bush
  dw Liftables_Pairs_DW_HeavyRock     ; 5: DW Small Heavy Rock/Skull ($0239, BG[2] -> SP0[9,11,12])
  dw Liftables_Pairs_LW_LightRock     ; 6: DW Big Light Rock (BG[5] -> SP6[9,10,14,15])
  dw Liftables_Pairs_LW_HeavyRock     ; 7: DW Big Heavy Rock (BG[2] -> SP0[9,10,14,15])

; Pair format: dw bg_src_offset, spr_dst_offset (relative to $7EC300 / $7EC500), 0-terminated.
Liftables_Pairs_LW_Sign:
  dw $0082, $01D2                     ; BG[4][1] -> SP6[9]  (outline)
  dw $0088, $01DA                     ; BG[4][4] -> SP6[13] (sign wood)
  dw $0000

Liftables_Pairs_LW_LightRock:
  dw $00A2, $01D2                     ; BG[5][1] -> SP6[9]  (outline)
  dw $00A4, $01D4                     ; BG[5][2] -> SP6[10] (shadow)
  dw $00A8, $01DC                     ; BG[5][4] -> SP6[14] (highlight)
  dw $00A6, $01DE                     ; BG[5][3] -> SP6[15] (midtone)
  dw $0000

Liftables_Pairs_LW_Bush:
  dw $00C2, $01D2                     ; BG[6][1] -> SP6[9]  (outline)
  dw $00CA, $01D6                     ; BG[6][5] -> SP6[11] (dark foliage)
  dw $00CC, $01D8                     ; BG[6][6] -> SP6[12] (bright foliage)
  dw $00CE, $01DA                     ; BG[6][7] -> SP6[13] (top highlight pixel)
  dw $0000

Liftables_Pairs_LW_Grass:
  dw $00C2, $0112                     ; BG[6][1] -> SP0[9]  (outline)
  dw $00CA, $0116                     ; BG[6][5] -> SP0[11] (dark grass)
  dw $00CC, $0118                     ; BG[6][6] -> SP0[12] (bright grass)
  dw $0000

Liftables_Pairs_LW_HeavyRock:
  dw $0042, $0112                     ; BG[2][1] -> SP0[9]  (outline)
  dw $0044, $0114                     ; BG[2][2] -> SP0[10] (shadow)
  dw $0048, $011C                     ; BG[2][4] -> SP0[14] (highlight)
  dw $0046, $011E                     ; BG[2][3] -> SP0[15] (midtone)
  dw $0000

Liftables_Pairs_DW_Sign:
  dw $0042, $01D2                     ; BG[2][1] -> SP6[9]  (outline)
  dw $0046, $01DA                     ; BG[2][3] -> SP6[13] (wood mid)
  dw $0048, $01DC                     ; BG[2][4] -> SP6[14] (wood highlight)
  dw $0000

Liftables_Pairs_DW_LightRock:
  dw $00A2, $0112                     ; BG[5][1] -> SP0[9]  (outline)
  dw $00A6, $0116                     ; BG[5][3] -> SP0[11] (sage/mint skull body)
  dw $00A8, $0118                     ; BG[5][4] -> SP0[12] (sage/mint skull highlight)
  dw $0000

Liftables_Pairs_DW_Bush:
  dw $00C2, $01D2                     ; BG[6][1] -> SP6[9]  (outline)
  dw $00C6, $01D6                     ; BG[6][3] -> SP6[11] (shrub dark)
  dw $00C8, $01D8                     ; BG[6][4] -> SP6[12] (shrub light)
  dw $0000

Liftables_Pairs_DW_HeavyRock:
  dw $0042, $0112                     ; BG[2][1] -> SP0[9]  (outline)
  dw $0044, $0116                     ; BG[2][2] -> SP0[11] (heavy skull dark)
  dw $0048, $0118                     ; BG[2][4] -> SP0[12] (heavy skull highlight)
  dw $0000

; =============================================================================
; Bank $1B Revealed-Tile16 Helpers (M=16, X=16)
; =============================================================================

; Entry: M=16, X=16, A = original Tile16, X = map16 offset.
; Exit:  Y = $0172 on DW area $63 (Sheet $F8), else $0DC7. Preserves A and X.
Liftables_SelectBushReveal:
{
  PHA
  LDA.l $7E008A : AND.w #$00FF
  CMP.w #$0063 : BNE .normal
    LDY.w #$0172
    PLA : RTL
  .normal
  LDY.w #$0DC7
  PLA : RTL
}

; Entry: M=16, X=16, A = Tile16 at $7E2000,X, X = map16 offset.
; Exit:  JML $1BC008 (.small_object) with Y = revealed Tile16, or JML $1BC027 (.not_small_object).
Liftables_MatchSmallLiftable:
{
  CMP.w #$0036 : BNE .not_bush
    JSL Liftables_SelectBushReveal
    JML $1BC008
  .not_bush
  CMP.w #$020F : BEQ .is_rock
  CMP.w #$0239 : BNE .not_rock
  .is_rock
    LDY.w #$0DCA
    JML $1BC008
  .not_rock
  CMP.w #$0101 : BEQ .is_sign
  CMP.w #$017D : BNE .not_matched
  .is_sign
    PHA
    LDA.l $7E008A : AND.w #$00FF
    CMP.w #$0063 : BNE .sign_normal
      LDY.w #$0172
      PLA : JML $1BC008
    .sign_normal
    LDY.w #$0DC6
    PLA : JML $1BC008
  .not_matched
  JML $1BC027
}

; Entry: M=16, X=16, A = Tile16 at $7E2000,X, X = map16 offset.
Liftables_DashBushCheck:
{
  CMP.w #$0036 : BNE .not_bush
    JSL Liftables_SelectBushReveal
    JML $1BC008
  .not_bush
  JML $1BC05D
}

; Entry: M=16, X=16, A = Tile16 at $7E2000,X.
Liftables_BombTileMatch:
{
  CMP.w #$0036 : BNE .not_bush
    JSL Liftables_SelectBushReveal
    LDX.w #$0002
    JML $1BC197
  .not_bush
  CMP.w #$037E : BNE .check_cave
    LDY.w #$0DC5
    LDX.w #$0003
    JML $1BC197
  .check_cave
  JML $1BC1D6
}

print "End of liftables_palette_fix.asm   ", pc
