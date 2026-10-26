; =========================================================
; D7 (Dragon Ship) crystal ceremony — Farore takes the maiden's place
;
; Reached only from the legacy paths of the Sky maiden gateways
; (sky_d8_award.asm) when $040C == $18. The vanilla stage machine of sprite
; $AB (crystal growth, emerge, PaletteFilter_SP5F fade-in, speech, exit) is
; kept; only her graphics, palette and speech change:
; - Spawn: sheet $55 (Farore) is decoded into the upload buffer for sprite
;   slot 3 and her aux1 colors go to the OBJ5 target buffer. No follower
;   graphics (vanilla Zelda), $7EF3CC ends 0 as in vanilla.
; - Draw: the buffer goes to VRAM one $200-byte chunk per frame, then from
;   stage 3 her front frame (HyruleDream frame 10) is drawn.
; - Speech: one placeholder message, then stage 8 (KickOutOfDungeon).
; Progression is not set here: KydrogBoss_D7CrystalCommit ($08CC48) raises
; GameState when the crystal is collected, before Module07_18.
; =========================================================

!D7Farore_Sheet = $55     ; Farore sprite sheet (dream scenes)
!D7Farore_Aux1  = $03     ; !DW_FaroreAux1: OBJ5 colors 1-7
!D7Farore_Msg   = $0138   ; temporary rescue text until scawful's line lands
D7Farore_Bank00RTL = $00E33A ; RTL (end of InitializeTilesets)

; Vanilla-byte guards for the routines below: sky_d8_award.asm.

; Entry from SkyD8_MaidenFollowerGfx, M=8 X=8, Y = maiden slot, X kept.
; The maiden's $0F50 is still $0B (palette 5, name table 1): the vanilla D7
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

; Entry from SkyD8_MaidenDraw, M=8 X=8, X = maiden slot, $0FD8/$0FDA
; already moved by the crystal backdrop offsets ($0422/$0424).
; NMI sends the $19 chunk with VMADDH only, so no chunk is queued while a
; HUD ($16) or tilemap ($14) upload is pending.
; Exit: $1ECE26 (.invisible: polyhedral flag, cutscene stages).
D7Farore_Draw:
{
  LDA.w $0412 : CMP.b #$10 : BCS .uploaded
  LDA.b $16 : ORA.b $14 : BNE .uploaded
    PHX
    JSL $00DEFF ; Graphics_IncrementalVRAMUpload
    PLX
  .uploaded
  LDA.w $0D80, X : CMP.b #$03 : BCC .invisible
    PHB : PHK : PLB
    REP #$20
    LDA.w #D7Farore_Oam : STA.b $08
    LDA.w #$0002 : STA.b $06
    SEP #$30
    JSL $05DF75 ; SpriteDraw_Tabulated_player_deferred
    PLB
  .invisible
  JML $1ECE26
}

; HyruleDream frame 10 (front). Props come from $0F50 ($0B) EOR $0B89.
D7Farore_Oam:
  dw 0, -8 : db $E8, $00, $00, $02
  dw 0,  4 : db $EA, $00, $00, $02

; Entry from SkyD8_MaidenSpeech (stage 5), M=8 X=8, X = maiden slot.
; One message, then stage 8 runs once the box closes ($11 == 0).
; Exit: $1ECF07 (vanilla all-crystals MapIcon tail, RTS).
D7Farore_Speech:
{
  LDA.b #!D7Farore_Msg : LDY.b #!D7Farore_Msg>>8
  JSL $05E219 ; Sprite_ShowMessageUnconditional
  LDA.b #$08 : STA.w $0D80, X
  JML $1ECF07
}
