; =========================================================
; Lyra Sea Zora temple ($90): Sea Zora $B8 draws the River Zora front
; from sheet E7 (cells C0/C2), as the D4 refuge River witness does.
; The map must load sprite set $8E ([4B,49,4C,74]) so E7 sits in slot 4.
; Behaviour and dialogue stay the vanilla Sea Zora ($1A4/$1A5/$1A6).
; Included right after d4_pressure_warden.asm (same bank: JMP D4Zora_DrawEntries).
; M/X=8 in and out.
; =========================================================

LyraTempleZora_IsActor:
{
  LDA.b INDOORS : BNE .no
  LDA.b OWSCR : CMP.b #$90 : BNE .no
  LDA.w SprSubtype, X : BNE .no
  SEC : RTL
  .no
  CLC : RTL
}

LyraTempleZora_Draw:
{
  PHB : PHK : PLB
  ; Area loads rebuild the palettes after sprite prep: bind the colours
  ; once in active gameplay (same pattern as D4Refuge_Long).
  LDA.w SprMiscA, X : BNE .draw
  JSL Sprite_CheckActive : BCC .draw
  JSR LyraTempleZora_LoadPalettes
  LDA.b #$01 : STA.w SprMiscA, X
  .draw
  JSR LyraTempleZora_DrawRiver
  PLB : RTL
}

; D4Refuge_DrawRiver pieces moved 8 px right (X $00) so the body sits on
; the vanilla Sprite_DrawShadow that Sprite_Zora_Long draws after us.
LyraTempleZora_DrawRiver:
{
  JSL Sprite_PrepOamCoord
  LDA.b #$08 : JSL OAM_AllocateFromRegionA
  PHX
  LDA.b #$02 : STA $0D
  REP #$20
  LDA.w #.pieces : STA $06
  SEP #$20
  PHK : PLA : STA $08
  JMP D4Zora_DrawEntries
  .pieces
  db $00, $F0, $C0, $37
  db $00, $F8, $C2, $39
}

; Only the two rows the River front uses (props $37 = row 3, $39 = row 4).
LyraTempleZora_LoadPalettes:
{
  PHX
  REP #$20
  LDX.b #$0C
  .next
  LDA.l D4Zora_Palette_protector_head, X
  STA.l $7EC462, X : STA.l $7EC662, X
  LDA.l D4Zora_Palette_protector_body, X
  STA.l $7EC482, X : STA.l $7EC682, X
  DEX : DEX : BPL .next
  SEP #$20
  INC.b $15
  PLX
  RTS
}
