; =========================================================
; Sky room sky layer (open-air Sky Tower rooms; see SkyRoom_List below)
;
; The room header selects layer type 1 (editor-owned, private input), which
; puts BG1 on the subscreen. CGADSUB stays $20 (add on the backdrop only), so
; a pit pixel = backdrop $0000 + subscreen BG1 pixel. BG2 pits are char $1E9
; (all colour 0); their collision ($20) is untouched.
;
; After Underworld_LoadRoom has drawn the BG2 buffer ($7E2000), this fills the
; BG1 buffer ($7E4000): under each BG2 $1E9 cell and each pit-lip cell
; ($1DB-$1DF) a sky word from a 32x32 lattice (sheet EA in slot 6, palette 7
; colours 1-3); every other cell gets the blank $01E9. The fill runs before
; any tilemap upload in every caller.
;
; Scope: rooms $90-$95, $A0, $A7 and $B0 (header layer type 1).
; Sheet EA rides Sky secondary group 0A slot 6. The colours use global
; palette14 row 7 entries 1-3; row 6 is retained for chests and common objects.
; Existing row 7 room graphics use entries 13-14, outside the sky entries.
; =========================================================

assert !ENABLE_SKY_TOWER_GRAPHICS == 1, "Sky room sky requires Sky Tower graphics"

; Colour defines + SkyRoom_Clouds. The v3d lattice (370 cells, 1110 bytes) no
; longer fits the bank $2C slack under the Somaria/thin-ice tail asserts, so the
; table lives in the free tail of bank $33 (after Moosh, $33F073; read with LDA.l).
pushpc
org $33F400 ; @hook module=Dungeons kind=data protected_size=1110 name=SkyRoomClouds
assert read4($33F400) == 0 && read4($33F800) == 0, "Sky cloud table slot in bank $33 is not free"
incsrc "Dungeons/sky_room_sky_data.asm"
assert pc() <= $340000, "Sky cloud table overflows bank $33"
pullpc

pushpc

; Secondary group 0A slot 6: legacy 1B -> EA (1B tiles $30-$3F are kept in EA).
assert read1($00DDC2) == $1B, "Sky secondary group0A slot6 changed"
org $00DDC2 ; @hook module=Dungeons kind=data protected_size=1 name=SkyRoomSkySheetSlot6
  db $EA

; Sky palette14 row 7 colours 1-3 (word index 75-77 of the 90-word clone).
; Keep row 6 colours 1-3 from the global2 clone: ordinary chests use them.
org $1BE1A2 ; @hook module=Dungeons kind=data protected_size=6 name=SkyRoomSkyColors
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
  ; Open-air Sky Tower rooms (v3 board): every room with a sky opening.
  ; $A6, $96 and the B1 rooms ($8C $9B $9C $9D) stay enclosed and are not listed.
  LDA.b $A0
  LDX.w #SkyRoom_List_end-SkyRoom_List-2
  .scan
    CMP.l SkyRoom_List,X : BEQ .sky_room
    DEX #2 : BPL .scan
  BRL .done
  .sky_room
  PHB
  SEP #$20 : LDA.b #$7E : PHA : PLB : REP #$20

  ; Pass 1: plain sky (EA tile 0, palette 7) under BG2 $1E9 pit cells and
  ; under the pit-lip chars $1DB-$1DF (sheet 0F, slot 7), whose colour-0
  ; pixels (tooth gaps, side strips, convex corners) would otherwise show
  ; the blank backdrop.
  ; Blank elsewhere.
  LDY.w #$1FFE
  .cell
    LDA.w $2000,Y : AND.w #$03FF : CMP.w #$01E9 : BEQ .sky
    CMP.w #$01DB : BCC .blank
    CMP.w #$01E0 : BCC .sky
  .blank
    LDA.w #$01E9 : BRA .put
  .sky
    LDA.w #$1D80
  .put
    STA.w $4000,Y
    DEY : DEY : BPL .cell

  ; Pass 2: cloud cells, four copies of the 32x32 period, only over sky cells.
  LDX.w #$0000
  .cloud
    LDA.l SkyRoom_Clouds+2,X : AND.w #$003F : ORA.w #$1D80 : PHA
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

SkyRoom_List:
  dw $0090, $0091, $0092, $0093, $0094, $0095, $00A0, $00B0, $00A7
SkyRoom_List_end:
