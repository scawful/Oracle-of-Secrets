;===========================================================
; Ice Rod freezes water
; Written by Conn
;===========================================================

IceRodTileRam = $03EF

if not(defined("SPECIAL_OVERWORLD_RESIDENT_ENABLED"))
  !SPECIAL_OVERWORLD_RESIDENT_ENABLED = 0
endif

; Ancilla_CheckTileCollision_targeted_continue, native M8/X8, DBR=$08,
; D=$0000. Replay STA/TAY; Y must still be the sampled type on return.
; Outdoor caller has ALREADY divided sample X ($02) by 8. $00 is Y pixels.
org $088A5D ; @hook module=Items name=IceRod_TerrainContact kind=jsl target=LinkItem_IceRod expected_m=8 expected_x=8 protected_size=4
  JSL LinkItem_IceRod

org $0EFBA0
LinkItem_IceRod:
{
  STA.w $03E4, X : TAY
  LDA.b $1B : BNE .return             ; indoor coordinates have a different ABI
  LDA.w $008C : BEQ .return           ; retain Conn's ordinary-map eligibility
  LDA.w $03A3 : CMP.b #$06 : BNE .return
  CPX.b #$04 : BNE .return
  LDA.w $03E8 : CMP.b #$08 : BEQ .water
  CMP.b #$03 : BNE .return
.water
  LDA.w $0303 : CMP.b #$06 : BNE .return
  LDA.w $0304 : CMP.b #$06 : BNE .return
  BRA .freeze
.return
  RTL
.freeze
  PHP : REP #$30
  PHA : PHX : PHY : PHB : PHD
  PEA.w $0000 : PLD : CLD
  LDA.b $00 : PHA
  LDA.b $02 : PHA
  LDA.b $06 : PHA
  LDA.b $0C : PHA

  ; Exactly the native sampled-coordinate formula; do not divide $02 again.
  ; Masks intentionally wrap the resident 64x64 buffer at area quadrants.
  LDA.b $00 : SEC : SBC.w $0708 : AND.w $070A
  ASL : ASL : ASL : STA.b $06
  LDA.b $02 : SEC : SBC.w $070C : AND.w $070E : ORA.b $06
  CMP.w #$2000 : BCS .done
  BIT.w #$0001 : BNE .done
  TAX
  JSR IceRod_TileIsAllWater : BCC .done
  JSR IceRod_IceIsBound : BCC .done

  ; Native $1000 stripe queue ends before room stripes at $1100. One tile
  ; appends 16 bytes plus its terminator; refuse another DMA mode/full queue.
  LDA.b $14 : AND.w #$00FF : CMP.w #$0002 : BCS .done
  LDA.w $1000 : CMP.w #$00E1 : BCS .done
  BIT.w #$0001 : BNE .done
  LDA.w #$00B7
  JSL Overworld_DrawMap16_Persist
  SEP #$20
  LDA.b #$01 : STA.b $14
  REP #$20
.done
  PLA : STA.b $0C
  PLA : STA.b $06
  PLA : STA.b $02
  PLA : STA.b $00
  PLD : PLB : PLY : PLX : PLA : PLP
  RTL
}

; In X=terrain offset, Y=Tile16 word index; out A=word, Y=physical page,
; C=explicit resident row. Preserve X. Native fallback is intentionally
; distinguished from a row when qualifying new ice in a special area.
IceRod_ReadTerrainWord:
{
if !SPECIAL_OVERWORLD_RESIDENT_ENABLED == 1
  JSL Lyra_ResidentReadTerrainWord
else
  PHX
  TYX : LDA.l $BD8000, X : PHA
  LDA.l $7E008A : AND.w #$00FF
  CMP.w #$0080 : BCC .native
  CMP.w #$00C0 : BCC .page
.native
  LDA.w #$FFFF
.page
  TAY : PLA : PLX
  CLC
endif
  RTS
}
assert pc() <= $0EFC80, "Ice Rod contact/query overruns native ice behavior patch"

org $0EFCB0
; In M16/X16, X=terrain offset. Preserve X/Y. All FOUR quarters must be
; water in the sampled physical page's dictionary/type domain (vine fix).
IceRod_TileIsAllWater:
{
  PHY
  LDA.l $7E2000, X : CMP.w #$1000 : BCS .invalid
  ASL : ASL : ASL : TAY
.next
  PHY
  JSR IceRod_ReadTerrainWord
  JSR IceRod_WordType
  PLY
  CMP.w #$0008 : BEQ .water
  CMP.w #$0003 : BNE .not_water
.water
  INY : INY
  TYA : AND.w #$0006 : BNE .next
  PLY : SEC : RTS
.not_water
.invalid
  PLY : CLC : RTS
}

; Existing ice is $00B7 / four $1D83 words. Do not invent a replacement in
; a resident profile: require explicit rows there, and exact existing words.
IceRod_IceIsBound:
{
  PHY
  LDY.w #$05B8
.next
  PHY
  JSR IceRod_ReadTerrainWord
  BCS .word
  CPY.w #$FFFF : BNE .unbound
.word
  CMP.w #$1D83 : BNE .unbound
  PLY : INY : INY
  CPY.w #$05C0 : BNE .next
  PLY : SEC : RTS
.unbound
  PLY : PLY : CLC : RTS
}
assert pc() <= $0EFD02, "Ice Rod terrain checks overrun retired DMA slot"

org $0EFD02
; A=Tile8 word, Y=sampled physical page. Use the same selected Sky type
; table as the native collision reader, without substituting Link's page.
IceRod_WordType:
{
  PHX
  AND.w #$01FF : TAX
if !ENABLE_SKY_OVERWORLD_ROUTE == 1
  TYA
  ; Clear only the low two page bits and bit 3: $84-$87 / $8C-$8F.
  AND.w #$FFF4 : CMP.w #$0084 : BNE .native
.sky
  LDA.l SkyTileTypes, X : BRA .type
.native
endif
  LDA.l $0E9459, X
.type
  AND.w #$00FF
  PLX : RTS
}
assert pc() <= $0EFD20, "Ice Rod type lookup exceeds the retired DMA allocation"

; bug fix to not swim through tiles but jump onto them
; TileBehavior_GanonIce
org $07DC9E ; @hook module=Items
  JSL $0EFC80
  NOP

org $0EFC80
  LDA $0A
  TSB $0343
  TSB $0348
  RTL

; bug fix to stop gliding on shallow water when leaving ice tile
org $07DD1B ; @hook module=Items
  JSL $0EFC90
  RTS

org $0EFC90
  LDA $0A
  TSB $0359
  LDA $0350
  CMP #$0100
  BNE $03
  STZ $034A
  RTL


org $0E95DC ; get a 0e written here (first byte) to enable gliding on new tiles
  ASL $5757

org $0F85B8 ; get new tile values (83 1d) written 4 times here
  STA $1D, S
  STA $1D, S
  STA $1D, S
  STA $1D, S
