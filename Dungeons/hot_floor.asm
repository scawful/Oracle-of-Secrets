; Hot Floor (underworld tile type $DE)
;
; Hurts Link like spike floor, except:
;   - Garo Master form ($02B2 == $08, Masks/all_masks.asm mask list)
;   - airborne: feather / cape hop ($5D == $02)
;   - Deku hover ($5D == $0A, set by PrepareQuakeSpell in Masks/mask_routines.asm)
;   - riding a minecart ($35, !LinkInCart in Sprites/Objects/minecart.asm)
; Masks and Sprites are included after Dungeons, so raw addresses are used.
;
; Allocation: fixed bank $07 tail $07FFA0-$07FFFF. Items/ocarina.asm asserts
; that the bank $07 free-space chain stays below $07FFA0.

if !ENABLE_HOT_FLOOR == 1

pushpc

; Underworld tile behavior vector for type $DE (vanilla TileBehavior_Nothing).
org $07D7D8+($DE*2) ; @hook module=Dungeons name=HotFloor_Vector kind=data
  dw TileBehavior_HotFloor

; Sprite tile class: $00 = sprites walk on hot floor (was $01, wall).
org $1DF6CF+$DE ; @hook module=Dungeons name=HotFloor_SpriteClass kind=data
  db $00

org $07FFA0
; Entered from TileDetection_Execute_underworld with 16-bit A and X/Y.
TileBehavior_HotFloor:
{
  SEP #$20
  LDA.w $02B2 : CMP.b #$08 : BEQ .safe ; Garo Master form
  LDA.b $5D   : CMP.b #$02 : BEQ .safe ; feather / cape hop
                CMP.b #$0A : BEQ .safe ; Deku hover
  LDA.b $35   : BNE .safe              ; minecart rider
  REP #$20
  JMP $DDCA                            ; TileBehavior_SpikeFloor

  .safe
  REP #$20
  RTS
}
assert pc() <= $080000, "HotFloor overflows bank $07"

pullpc

endif
