; =========================================================
; Sky room sky layer (proof: room $A0 only)
;
; The room header selects layer type 1 (editor-owned, private input), which
; puts BG1 on the subscreen. CGADSUB stays $20 (add on the backdrop only), so
; a pit pixel = backdrop $0000 + subscreen BG1 pixel. BG2 pits are char $1E9
; (all colour 0); their collision ($20) is untouched.
;
; After Underworld_LoadRoom has drawn the BG2 buffer ($7E2000), this fills the
; BG1 buffer ($7E4000): under each BG2 $1E9 cell and each pit-lip cell
; ($1DB-$1DE) a sky word from a 32x32 lattice (sheet EA in slot 6, palette 6
; colours 1-3); every other cell gets the blank $01E9. The fill runs before
; any tilemap upload in every caller.
;
; Scope: room $00A0 only. Sheet EA rides Sky secondary group 0A slot 6 (only
; Sky rooms select group 0A); the colours are Sky palette14 row 6 colours 1-3
; (only Sky palette set 08 selects palette14).
; =========================================================

assert !ENABLE_SKY_TOWER_GRAPHICS == 1, "Sky room sky requires Sky Tower graphics"

; Colour defines + SkyRoom_Clouds (emitted here, bank $2C stream).
incsrc "Dungeons/sky_room_sky_data.asm"

pushpc

; Secondary group 0A slot 6: legacy 1B -> EA (1B tiles $30-$3F are kept in EA).
assert read1($00DDC2) == $1B, "Sky secondary group0A slot6 changed"
org $00DDC2 ; @hook module=Dungeons kind=data protected_size=1 name=SkyRoomSkySheetSlot6
  db $EA

; Sky palette14 row 6 colours 1-3 (word index 60-62 of the 90-word clone).
org $1BE184 ; @hook module=Dungeons kind=data protected_size=6 name=SkyRoomSkyColors
  dw !SKY_ROOM_COLOR1, !SKY_ROOM_COLOR2, !SKY_ROOM_COLOR3

; Callers of Underworld_LoadRoom. $028A5B belongs to followers.asm, whose tail
; (or vanilla branch) jumps to SkyRoom_LoadRoom under this flag.
assert read4($028CE5) == $01873A22, "Underworld_InitializeRoomFromSpecial LoadRoom call moved"
org $028CE5 : JSL SkyRoom_LoadRoom ; @hook module=Dungeons name=SkyRoom_LoadRoom_Special kind=jsl target=SkyRoom_LoadRoom expected_m=8 expected_x=8
assert read4($029407) == $01873A22, "Module07_11_02 LoadRoom call moved"
org $029407 : JSL SkyRoom_LoadRoom ; @hook module=Dungeons name=SkyRoom_LoadRoom_Stairs kind=jsl target=SkyRoom_LoadRoom expected_m=8 expected_x=8
assert read4($02C583) == $01873A22, "Underworld_LoadAndDrawRoom LoadRoom call moved"
org $02C583 : JSL SkyRoom_LoadRoom ; @hook module=Dungeons name=SkyRoom_LoadRoom_Draw kind=jsl target=SkyRoom_LoadRoom expected_m=8 expected_x=8

pullpc

; Width-transparent: P, A, X, Y and DBR return as Underworld_LoadRoom left them.
SkyRoom_LoadRoom:
{
  JSL $01873A ; Underworld_LoadRoom
  PHP
  REP #$30
  PHA : PHX : PHY
  LDA.b $A0 : CMP.w #$00A0 : BNE .done
  PHB
  SEP #$20 : LDA.b #$7E : PHA : PLB : REP #$20

  ; Pass 1: plain sky (EA tile 0, palette 6) under BG2 $1E9 pit cells and
  ; under the pit-lip chars $1DB-$1DE (sheet 0F, slot 7), whose colour-0
  ; pixels (tooth gaps, side strips) would otherwise show the blank backdrop.
  ; Blank elsewhere.
  LDY.w #$1FFE
  .cell
    LDA.w $2000,Y : AND.w #$03FF : CMP.w #$01E9 : BEQ .sky
    CMP.w #$01DB : BCC .blank
    CMP.w #$01DF : BCC .sky
  .blank
    LDA.w #$01E9 : BRA .put
  .sky
    LDA.w #$1980
  .put
    STA.w $4000,Y
    DEY : DEY : BPL .cell

  ; Pass 2: cloud cells, four copies of the 32x32 period, only over sky cells.
  LDX.w #$0000
  .cloud
    LDA.l SkyRoom_Clouds+2,X : AND.w #$003F : ORA.w #$1980 : PHA
    LDA.l SkyRoom_Clouds+2,X : AND.w #$00C0 : XBA : ORA 1,S : STA 1,S
    LDA.l SkyRoom_Clouds,X : TAY
    JSR .stamp
    TYA : CLC : ADC.w #$0040 : TAY : JSR .stamp
    TYA : CLC : ADC.w #$0FC0 : TAY : JSR .stamp
    TYA : CLC : ADC.w #$0040 : TAY : JSR .stamp
    PLA
    INX #3
    CPX.w #SkyRoom_CloudsEnd-SkyRoom_Clouds : BCC .cloud

  PLB
  .done
  PLY : PLX : PLA
  PLP
  RTL

  ; Y = BG1 buffer offset; word at 3,S (under the return address).
  .stamp
    LDA.w $4000,Y : CMP.w #$01E9 : BEQ ..skip
    LDA 3,S : STA.w $4000,Y
    ..skip
    RTS
}
