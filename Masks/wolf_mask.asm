; =========================================================
; Wolf Mask
; Dig for treasure ability (shovel)
; =========================================================

UpdateWolfPalette:
{
  REP #$30   ; change 16bit mode
  LDX #$001E

  .loop
    LDA.l WolfPalette, X
    PHX
    STA.l TimeState.SubColor
    JSL ColorSubEffect
    PLX
    STA $7EC6E0, X
  DEX : DEX : BPL .loop

  SEP #$30 ; go back to 8 bit mode
  INC $15  ; update the palette
  RTL      ; or RTS depending on where you need it
}

; =========================================================

WolfPalette:
  dw $7BDE, $7FFF, $2F7D, $19B5, $3A9C, $14A5, $1A3D, $14B6
  dw $4650, $362A, $3F4E, $162B, $318A, $39CC, $1CE7, $76D1
  dw $6565, $7271, $14B5, $459B, $3D95, $22D0, $567C, $1890
  dw $7616, $0000

; =========================================================

; Guaranteed Ranch cache; other digs retain the original RNG and carry gate.
; Entry: M=8/X=8, DBR=$07, C from AncillaAdd_ShovelDirt (set = full).
; The vanilla shovel caller saves its phase X across this JSL.
WolfDig_SpawnPrize:
{
  PHP
  BCS .random
  LDA $02B2 : CMP.b #$03 : BNE .random
  LDA $1B : BNE .random
  LDA $8A : BNE .random ; Ranch large-map parent $00
  LDA.l WORLDFLAG : BNE .random ; ordinary world only
  BRA .target

  .random
  PLP
  JML $1DFD4B ; DigGame_SpawnPrize; preserve incoming C/M/X/DBR

  .target
  PHX : PHY
  REP #$20
  LDA $2F : AND.w #$00FF : TAX
  ; Same Y=2 probe offsets as TileDetect_MainHandler, indexed by facing.
  LDA.l $07D02C,X : CLC : ADC $22 : AND.w #$FFF0
  CMP.w #$0130 : BNE .other_tile
  LDA.l $07CFDC,X : CLC : ADC $20 : AND.w #$FFF0
  CMP.w #$0090 : BNE .other_tile
  SEP #$20
  LDA.l WolfDigFlags : AND.b #!WolfDig_RanchCache : BNE .done

  ; Item receipt needs one of the first five ancilla slots. A full pool
  ; leaves the cache unclaimed so it can be dug again after effects clear.
  LDX.b #$04
  .slot
  LDA $0C4A,X : BEQ .grant
  DEX : BPL .slot
  BRA .done

  .grant
  LDA.l WolfDigFlags : ORA.b #!WolfDig_RanchCache : STA.l WolfDigFlags
  STZ $02E9
  LDY.b #$36 ; vanilla 20-rupee item receipt, no new message
  JSL Link_ReceiveItem

  .done
  PLY : PLX : PLP
  RTL

  .other_tile
  SEP #$20
  PLY : PLX : PLP
  JML $1DFD4B
}
assert pc() <= $398000 ; do not cross the Wolf bank

; =========================================================

LinkItem_Flute = $07A3DB
LinkItem_Shovel =  $07A32C

; LinkItem_Shovel
org $07A3B2
  NOP #5

; Replace only the vanilla prize call; the dirt/tile checks stay intact.
org $07A3B7 ; @hook module=Masks name=WolfDig_SpawnPrize kind=jsl target=WolfDig_SpawnPrize expected_m=8 expected_x=8
  JSL WolfDig_SpawnPrize
assert pc() == $07A3BB

; DigGame_SpawnPrize
org $1DFD5E
  NOP #5

; =========================================================

org $07A313
LinkItem_ShovelAndFlute:
{
  ; Play flute or use the Wolf Mask
if !ENABLE_MASK_R_BINDING == 1
  JSL MaskBinding_IsOcarina : NOP
  BNE .use_wolf_mask
else
  LDA $0202 : CMP.b #$0D : BNE .use_wolf_mask
endif
    BRL LinkItem_Flute
  .use_wolf_mask
  JMP LinkItem_WolfMask
}
; assert pc() <= $07A31F

; =========================================================

; Bank 07 Free Space
pullpc

LinkItem_WolfMask:
{
  LDA $02B2 : CMP #$03 : BNE .equip
    JSR LinkItem_Shovel
  .equip
  LDA.b #$03
  JSL Link_TransformMask
  .return
  RTS
}

print "End of Masks/wolf_mask.asm        ", pc
pushpc

