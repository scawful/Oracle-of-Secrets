; =========================================================
; D7 (Dragon Ship) crystal ceremony — Farore takes the maiden's place
;
; Hooks only the D7 paths of sprite $AB ($040C == $18); the Sky gateways
; (sky_d8_award.asm) at $1ECD8B/$1ECE1B/$1ECECE are left as they are. The
; vanilla stage machine (crystal growth, emerge, PaletteFilter_SP5F fade-in,
; speech, exit) is kept; only her graphics, palette and speech change:
; - Spawn: sheet $55 (Farore) is decoded into the upload buffer for sprite
;   slot 3 and her aux1 colors go to the OBJ5 target buffer. No follower
;   graphics (vanilla Zelda), $7EF3CC ends 0 as in vanilla.
; - Upload: the buffer goes to VRAM one $200-byte chunk per frame.
; - Draw: from stage 3 her front frame (HyruleDream frame 10).
; - Speech: one placeholder message, then stage 8 (KickOutOfDungeon).
; Progression is not set here: KydrogBoss_D7CrystalCommit ($08CC48) raises
; GameState when the crystal is collected, before Module07_18.
; CI seeds the readN() guards below (.github/workflows/test-rom.yml), so
; they use literal addresses only.
; =========================================================

!D7Farore_Sheet = $55     ; Farore sprite sheet (dream scenes)
!D7Farore_Aux1  = $03     ; !DW_FaroreAux1: OBJ5 colors 1-7
!D7Farore_Msg   = $0138   ; temporary rescue text until scawful's line lands
D7Farore_Bank00RTL = $00E33A ; RTL (end of InitializeTilesets)

assert read1($00E33A) == $6B, "Bank $00 RTL trampoline moved"
assert read1($00E772) == $B9 || read1($00E772) == $5C, "Decompress_sprite_arbitrary moved"
assert read2($00DFB8) == $0C84, "Do3To4Low16Bit moved"
assert read1($00DEFF) == $AE, "Graphics_IncrementalVRAMUpload moved"
assert read2($1BECC5) == $31C2, "Palettes_Load_SpriteAux1 moved"

pushpc

; CrystalCutscene_SpawnMaiden, D7 branch: LDA.b #$09 : STA.w $0F50,Y
assert read4($1ECD92) == $509909A9, "Maiden D7 palette override moved"
assert read1($1ECD96) == $0F, "Maiden D7 palette override moved"
assert read2($1ECDAD) == $289C, "Maiden offset setup moved"
org $1ECD92 : JML D7Farore_Spawn ; @hook module=Dungeons name=D7Farore_Spawn kind=jml target=D7Farore_Spawn expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=5
NOP
assert pc() == $1ECD97

; Sprite_AB_CrystalMaiden entry: REP #$20 : LDA.w $0FD8
assert read4($1ECE03) == $D8AD20C2, "Maiden entry moved"
assert read1($1ECE07) == $0F, "Maiden entry moved"
assert read1($1ECE08) == $38, "Maiden entry SEC moved"
org $1ECE03 : JML D7Farore_Upload ; @hook module=Dungeons name=D7Farore_Upload kind=jml target=D7Farore_Upload expected_m=8 expected_x=8 expected_exit_m=16 expected_exit_x=8 protected_size=5
NOP
assert pc() == $1ECE08

; Sprite_AB_CrystalMaiden visible draw: JSL SpriteDraw_Maiden ($0DCE5F)
assert read4($1ECE22) == $0DCE5F22, "Maiden draw call moved"
org $1ECE22 : JSL D7Farore_Draw ; @hook module=Dungeons name=D7Farore_Draw kind=jsl target=D7Farore_Draw expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=4
assert pc() == $1ECE26

; CrystalMaiden_GiveSpeech, D7 (Y == $0E) branch: LDA.l $7EF37A
assert read4($1ECEEB) == $7EF37AAF, "Maiden D7 speech branch moved"
assert read1($1ECF07) == $AF, "Maiden speech MapIcon tail moved"
org $1ECEEB : JML D7Farore_Speech ; @hook module=Dungeons name=D7Farore_Speech kind=jml target=D7Farore_Speech expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=4
assert pc() == $1ECEEF

pullpc

; Entry $1ECD92 (D7 only), M=8 X=8, Y = maiden slot, X kept.
; The maiden's $0F50 stays $0B (palette 5, name table 1): the vanilla D7
; override to $09 is skipped.
; Exit: $1ECDAD (maiden scroll offsets), X/Y as on entry.
D7Farore_Spawn:
{
  PHX : PHY
  PHB
  LDA.b #$00 : PHA : PLB
  ; Decompress_sprite_arbitrary ($00E772, RTS): sheet Y -> $7E7800.
  STZ.b $00
  LDA.b #$78 : STA.b $01
  LDA.b #$7E : STA.b $02
  LDY.b #!D7Farore_Sheet
  PHK : PEA.w .decoded-1
  PEA.w D7Farore_Bank00RTL-1
  JML $00E772
  .decoded
  ; Do3To4Low16Bit ($00DFB8, RTS): 64 tiles, plane 3 = 0, into the upload
  ; buffer for slot 3 ($7F1800 = chunks $0C-$0F).
  LDA.b #$7E : STA.b $02 : STA.b $05
  REP #$31
  LDA.w #$7800 : LDX.w #$1800 : LDY.w #$0040
  PHK : PEA.w .converted-1
  PEA.w D7Farore_Bank00RTL-1
  JML $00DFB8
  .converted
  SEP #$30
  ; Palettes_Load_SpriteAux1 reads $0AAD and writes the OBJ5 target buffer;
  ; CrystalMaiden_DelaySpeech fades it in.
  LDA.w $0AAD : PHA
  LDA.b #!D7Farore_Aux1 : STA.w $0AAD
  JSL $1BECC5
  PLA : STA.w $0AAD
  PLB
  LDA.b #$0C : STA.w $0412
  LDA.b #!D7Farore_Sheet : STA.l LASTSPRSET3
  LDA.b #$00 : STA.l $7EF3CC
  PLY : PLX
  JML $1ECDAD
}

; Entry $1ECE03 (every maiden frame), M=8 X=8, X = maiden slot.
; NMI sends the $19 chunk with VMADDH only, so no chunk is queued while a
; HUD ($16) or tilemap ($14) upload is pending.
; Exit: $1ECE08 with M=16 and A = $0FD8, as the replaced code leaves them.
D7Farore_Upload:
{
  LDA.w $040C : CMP.b #$18 : BNE .done
  LDA.w $0412 : CMP.b #$10 : BCS .done
  LDA.b $16 : ORA.b $14 : BNE .done
    PHX
    JSL $00DEFF ; Graphics_IncrementalVRAMUpload
    PLX
  .done
  REP #$20
  LDA.w $0FD8
  JML $1ECE08
}

; JSL from $1ECE22 (stage >= 3), M=8 X=8, X = maiden slot, $0FD8/$0FDA
; already moved by the crystal backdrop offsets ($0422/$0424).
; Other dungeons: vanilla SpriteDraw_Maiden. Returns with RTL.
D7Farore_Draw:
{
  LDA.w $040C : CMP.b #$18 : BEQ .farore
    JML $0DCE5F ; SpriteDraw_Maiden
  .farore
  PHB : PHK : PLB
  REP #$20
  LDA.w #D7Farore_Oam : STA.b $08
  LDA.w #$0002 : STA.b $06
  SEP #$30
  JSL $05DF75 ; SpriteDraw_Tabulated_player_deferred
  PLB
  RTL
}

; HyruleDream frame 10 (front). Props come from $0F50 ($0B) EOR $0B89.
D7Farore_Oam:
  dw 0, -8 : db $E8, $00, $00, $02
  dw 0,  4 : db $EA, $00, $00, $02

; Entry $1ECEEB (stage 5, D7 only), M=8 X=8, X = maiden slot.
; One message, then stage 8 runs once the box closes ($11 == 0).
; Exit: $1ECF07 (vanilla all-crystals MapIcon tail, RTS).
D7Farore_Speech:
{
  LDA.b #!D7Farore_Msg : LDY.b #!D7Farore_Msg>>8
  JSL $05E219 ; Sprite_ShowMessageUnconditional
  LDA.b #$08 : STA.w $0D80, X
  JML $1ECF07
}
