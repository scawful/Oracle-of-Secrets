; =========================================================
; File: Overworld/sky_tile_types.asm
; Purpose: Selected Sky map collision using the native Tile8 ID domain.
; Author: Codex; table from the retained private Sky v5 source.
; =========================================================
; @source: usdasm Overworld_GetTileTypeAtLocation and private Sky v5 table.
; @verified: Source port only; native route activation remains unqualified.
;
; Four native reads enter with M/X16 and X = Tile8 ID. Preserve P, X/Y,
; DBR and D; the final LDA supplies N/Z exactly as the replaced instruction.
; Long WRAM reads keep the selector independent of the caller's direct page.

if !ENABLE_SKY_OVERWORLD_ROUTE == 1
assert !ENABLE_SKY_OVERWORLD_GRAPHICS == 1, "Sky route requires its source graphics"

; Single source of truth for outdoors selected Sky maps ($84-$87, $8C-$8F).
; Clobbers 16-bit A; preserves X, Y, DBR, D, and stack (branch target sets N/Z).
macro SkyTileType_BranchIfSky(sky_label, vanilla_label)
  LDA.l $7E001B : AND.w #$00FF : BNE <vanilla_label>
  LDA.l $7E008A : AND.w #$00FF
  CMP.w #$0084 : BCC <vanilla_label>
  CMP.w #$0088 : BCC <sky_label>
  CMP.w #$008C : BCC <vanilla_label>
  CMP.w #$0090 : BCS <vanilla_label>
endmacro

SkyTileType:
{
  PHP
  %SkyTileType_BranchIfSky(.sky, .vanilla)
.sky
  PLP
  LDA.l SkyTileTypes, X
  RTL
.vanilla
  PLP
  LDA.l $0E9459, X
  RTL
}

; Tile types use original VRAM-slot character IDs, not global source-sheet IDs.
; $1AD opens the selected arch threshold; other authored Sky attributes stay.
SkyTileTypes:
  db $01, $27, $27, $27, $27, $27, $00, $20, $01, $01, $01, $01, $01, $01, $01, $01 ; $000-$00F
  db $01, $00, $01, $01, $01, $01, $00, $20, $27, $27, $27, $01, $00, $64, $00, $01 ; $010-$01F
  db $01, $01, $01, $01, $20, $01, $00, $00, $27, $27, $27, $00, $00, $00, $00, $01 ; $020-$02F
  db $00, $00, $00, $01, $01, $01, $00, $00, $02, $00, $02, $00, $00, $00, $00, $00 ; $030-$03F
  db $01, $01, $01, $01, $1A, $01, $27, $01, $01, $27, $01, $65, $27, $00, $27, $27 ; $040-$04F
  db $27, $27, $01, $18, $1A, $01, $27, $27, $01, $27, $02, $27, $27, $27, $27, $27 ; $050-$05F
  db $27, $27, $27, $01, $01, $20, $27, $27, $02, $27, $00, $27, $27, $27, $27, $27 ; $060-$06F
  db $27, $27, $27, $01, $01, $01, $02, $27, $27, $00, $00, $27, $27, $27, $27, $27 ; $070-$07F
  db $01, $65, $00, $00, $00, $01, $18, $65, $01, $01, $00, $48, $00, $65, $65, $02 ; $080-$08F
  db $01, $01, $00, $00, $01, $01, $10, $65, $02, $01, $22, $48, $00, $65, $65, $02 ; $090-$09F
  db $48, $00, $00, $00, $65, $27, $27, $00, $27, $22, $27, $27, $00, $27, $27, $27 ; $0A0-$0AF
  db $27, $00, $00, $20, $27, $20, $20, $00, $01, $22, $01, $27, $02, $20, $00, $00 ; $0B0-$0BF
  db $02, $02, $02, $02, $01, $02, $02, $02, $02, $02, $02, $00, $00, $02, $02, $00 ; $0C0-$0CF
  db $02, $01, $02, $02, $00, $01, $00, $02, $02, $02, $02, $02, $01, $00, $02, $00 ; $0D0-$0DF
  db $02, $01, $02, $46, $00, $01, $02, $02, $00, $02, $02, $01, $00, $00, $00, $00 ; $0E0-$0EF
  db $01, $01, $02, $02, $01, $01, $02, $00, $02, $02, $02, $00, $02, $00, $00, $00 ; $0F0-$0FF
  db $02, $02, $42, $01, $01, $02, $02, $01, $02, $00, $00, $22, $00, $00, $00, $00 ; $100-$10F
  db $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $22, $00, $00, $00, $00 ; $110-$11F
  db $02, $02, $02, $02, $65, $02, $02, $02, $02, $01, $00, $00, $00, $00, $00, $00 ; $120-$12F
  db $02, $02, $02, $02, $65, $02, $02, $02, $02, $01, $00, $00, $00, $00, $00, $00 ; $130-$13F
  db $01, $02, $02, $01, $02, $01, $01, $02, $00, $01, $01, $00, $00, $00, $01, $00 ; $140-$14F
  db $02, $01, $00, $02, $01, $02, $01, $01, $02, $02, $01, $00, $00, $00, $00, $00 ; $150-$15F
  db $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $22, $00, $00, $00, $00, $00 ; $160-$16F
  db $01, $02, $43, $01, $01, $01, $01, $01, $02, $02, $02, $00, $00, $00, $00, $00 ; $170-$17F
  db $50, $50, $54, $0E, $57, $27, $20, $20, $20, $27, $20, $02, $20, $20, $27, $20 ; $180-$18F
  db $50, $50, $54, $02, $20, $2A, $56, $27, $01, $20, $02, $20, $27, $20, $01, $20 ; $190-$19F
  db $27, $02, $52, $27, $02, $01, $12, $18, $55, $55, $00, $00, $48, $00, $02, $00 ; $1A0-$1AF
  db $27, $02, $01, $20, $01, $01, $27, $20, $01, $27, $00, $00, $48, $02, $02, $00 ; $1B0-$1BF
  db $08, $08, $09, $09, $29, $29, $02, $01, $02, $02, $02, $02, $02, $08, $1A, $02 ; $1C0-$1CF
  db $08, $08, $09, $09, $02, $02, $09, $01, $09, $09, $09, $48, $09, $01, $00, $4B ; $1D0-$1DF
  db $02, $01, $02, $00, $08, $02, $02, $00, $00, $00, $00, $01, $02, $00, $20, $00 ; $1E0-$1EF
  db $02, $29, $00, $02, $02, $02, $02, $00, $20, $27, $01, $22, $00, $00, $08, $00 ; $1F0-$1FF

SkyTileTypesEnd:
assert SkyTileTypesEnd-SkyTileTypes == $0200
; The native M16 LDA reads two bytes at char $1FF before its caller masks A.
; Preserve that last high byte without reading into the following routine.
  db read1($0E9659)
assert (SkyTileTypes&$FFFF)+$0201 <= $10000

; Block Shovel / Wolf Mask digging ($037A == $01) from overwriting Sky cloud
; void tile $0034 with dug ground $0DC9 while keeping ordinary overworld digging.
; Entered at $1BBE3E with M=16, X=16, X = map16 offset, 1,S = matched Tile16.
SkyTileType_GuardVoidDig:
{
  LDA.l $7E037A : AND.w #$00FF : CMP.w #$0001 : BNE .not_dig
  LDA 1,S : CMP.w #$0034 : BNE .allow_dig
  %SkyTileType_BranchIfSky(.block_void_dig, .allow_dig)
.block_void_dig
  PLA
  LDA.w #$0000
  SEP #$30
  RTL
.allow_dig
  JML $1BBE49
.not_dig
  JML $1BBE3B
}

pushpc
assert read4($00886E) == $0E9459BF, "GetTileType table read moved"
org $00886E ; @hook module=Overworld name=SkyTileType_GetTileType kind=jsl target=SkyTileType expected_m=16 expected_x=16 protected_size=4
  JSL SkyTileType
assert pc() == $008872
assert read4($1BBEFD) == $0E9459BF, "TileAction table read moved"
org $1BBEFD ; @hook module=Overworld name=SkyTileType_TileAction kind=jsl target=SkyTileType expected_m=16 expected_x=16 protected_size=4
  JSL SkyTileType
assert pc() == $1BBF01
assert read4($1BBF2A) == $0E9459BF, "HammerSFX table read moved"
org $1BBF2A ; @hook module=Overworld name=SkyTileType_HammerSFX kind=jsl target=SkyTileType expected_m=16 expected_x=16 protected_size=4
  JSL SkyTileType
assert pc() == $1BBF2E
assert read4($1BC04E) == $0E9459BF, "SmashRockPile table read moved"
org $1BC04E ; @hook module=Overworld name=SkyTileType_SmashRockPile kind=jsl target=SkyTileType expected_m=16 expected_x=16 protected_size=4
  JSL SkyTileType
assert pc() == $1BC052
assert read4($1BBE3E) == $29037AAD, "TileInteract_DashLift dig gate moved"
assert read4($1BBE42) == $01C900FF, "TileInteract_DashLift dig gate tail moved"
assert read3($1BBE46) == $F2D000, "TileInteract_DashLift dig branch moved"
org $1BBE3E ; @hook module=Overworld name=SkyTileType_GuardVoidDig kind=jml target=SkyTileType_GuardVoidDig expected_m=16 expected_x=16 protected_size=11
  JML SkyTileType_GuardVoidDig
  NOP #7
assert pc() == $1BBE49
pullpc
endif
