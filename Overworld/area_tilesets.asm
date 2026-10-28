; Selected per-area collision cache and raw BG sheets in the graphics suffix.
; Native shared assets retain their existing owner in custom_gfx.asm.
AreaTileset_CodeBase = $E2E000
AreaTileset_CodeLimit = $E30000
assert !ENABLE_OW_AREA_TILESETS == 1
assert defined("LYRA_AREA_TILESETS_BOUND") && !LYRA_AREA_TILESETS_BOUND == 1, "Per-area source binding required"
assert defined("LYRA_AREA_TILESETS_ORIGIN") && defined("LYRA_AREA_TILESETS_END"), "Per-area owned origins required"
assert !LYRA_AREA_TILESETS_ORIGIN == AreaTileset_CodeBase && !LYRA_AREA_TILESETS_END == AreaTileset_CodeLimit
if not(defined("LYRA_AREA_FERRY_BOUND"))
  !LYRA_AREA_FERRY_BOUND = 0
endif
assert !LYRA_AREA_FERRY_BOUND == 0 || !LYRA_AREA_FERRY_BOUND == 1
pushpc
org !LYRA_AREA_TILESETS_ORIGIN
AreaTileset_CodeStart = pc()
; Per-area overworld tile types and raw BG sheets (!ENABLE_OW_AREA_TILESETS).
;
; The four OverworldTileTypes reads below use a WRAM copy at
; AreaTileset_TileTypes instead of the ROM table. Each overworld area load (the
; CheckForChangeGraphicsNormalLoadBoat calls in ZSCustomOverworld.asm) refills
; the copy from the ROM table, applies the area's tile type ranges, then DMAs
; the area's raw BG sheets. Normal scroll transitions refill the tile types
; only (AreaTileset_LoadTypes): the screen is on there, so an area with sheets
; must be entered by a mosaic, door, warp or bird.
;
; Not TILEATTR ($7EFE00): LoadDefaultTileTypes fills most of it once, at file
; load (#_028160), and dungeons rely on it from then on.
;
; AreaTileset_AreaProfile: one byte per area ($8A, the parent area for wide
; and large areas). Profile 0 = ROM tile types and no sheets.

!AreaTileset_RomTileTypes = $0E9459 ; OverworldTileTypes, 512 bytes

; $7FD000-$7FD1FF, in the free block between the message pointers
; ($7F71C0, 3 bytes per message) and PALSAVE ($7FDD80).
AreaTileset_TileTypes = $7FD000

; All four reads run with A = 16, X = 16 and X = char & $1FF; each reads
; Map16Definitions, so none runs in the underworld. Operand change only.

; Tile type range: chars first..first+count-1 take bytes from source.
; Source must sit in this bank (MVN uses a fixed source bank).
macro AreaTileset_Types(first, count, source)
  assert <count> > 0, "AreaTileset_Types: empty range"
  assert <first>+<count> <= $200, "AreaTileset_Types: range past char $1FF"
  assert <source>>>16 == AreaTileset_Load>>16, "AreaTileset_Types: source outside this bank"
  dw <first>, <count>, <source>
endmacro

; Raw 4bpp sheet: size bytes from source to VRAM word address vram.
macro AreaTileset_Sheet(vram, size, source)
  dw <vram>, <size> : dl <source>
endmacro

; Any M/X. Keeps A, X, Y, DBR and P.
; Loads with the screen off or in mosaic: tile types, then sheets.
AreaTileset_Load:
{
  PHP : CLD
  REP #$30
  PHA : PHX : PHY
  PHB

  JSR AreaTileset_FillTypes : BEQ .done
  .next_sheet
    LDA.w $0000, X : BMI .done ; $FFFF ends the list
    STA.l $002116
    LDA.w $0002, X : STA.l $004305
    LDA.w $0004, X : STA.l $004302
    LDA.w #$1801 : STA.l $004300
    SEP #$20
    LDA.w $0006, X : STA.l $004304
    LDA.b #$80 : STA.l $002115
    LDA.b #$01 : STA.l $00420B
    REP #$20
    TXA : CLC : ADC.w #7 : TAX
    BRA .next_sheet

  .done
  PLB
  PLY : PLX : PLA
  PLP
  RTL
}

; Any M/X. Keeps A, X, Y, DBR and P.
; Normal scroll transitions (CheckForChangeGraphicsTransitionLoad) keep the
; screen on, so tile types only, no sheet DMA.
AreaTileset_LoadTypes:
{
  PHP : CLD
  REP #$30
  PHA : PHX : PHY
  PHB
  JSR AreaTileset_FillTypes
  PLB
  PLY : PLX : PLA
  PLP
  RTL
}

; A = 16, X = 16. Refills AreaTileset_TileTypes for area $8A.
; Returns DBR = this bank and X = the area's sheet list, Z set when none.
AreaTileset_FillTypes:
{
  ; ROM tile types -> AreaTileset_TileTypes. MVN leaves DBR = $7F.
  ; asar writes MVN operands in byte order: destination bank, then source.
  LDA.w #$01FF
  LDX.w #!AreaTileset_RomTileTypes&$FFFF
  LDY.w #AreaTileset_TileTypes&$FFFF
  MVN AreaTileset_TileTypes>>16, !AreaTileset_RomTileTypes>>16

  PHK : PLB
  LDA.l $7E008A : AND.w #$00FF : TAX
  LDA.w AreaTileset_AreaProfile, X : AND.w #$00FF : BEQ .none
  ASL #2 : TAX
  LDA.w AreaTileset_Profiles+2, X : PHA
  LDA.w AreaTileset_Profiles+0, X : TAX

  .next_types
    LDA.w $0000, X : BMI .types_done ; $FFFF ends the list
    PHX
    CLC : ADC.w #AreaTileset_TileTypes&$FFFF : TAY
    LDA.w $0004, X : PHA
    LDA.w $0002, X : DEC
    PLX
    MVN AreaTileset_TileTypes>>16, AreaTileset_Load>>16
    PHK : PLB
    PLA : CLC : ADC.w #6 : TAX
    BRA .next_types
  .types_done

  PLX ; sheet list; sets Z for the caller
  RTS

  .none
  TAX ; A = 0
  RTS
}

AreaTileset_AreaProfile:
  ;  x0   x1   x2   x3   x4   x5   x6   x7   x8   x9   xA   xB   xC   xD   xE   xF
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $00
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $10
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $20
if !LYRA_AREA_FERRY_BOUND == 1
  db $02 ; $30: bound ferry collision and sheets
else
  db $01 ; $30: unchanged native boat profile
endif
  db      $00, $00, $00, $00, $00, $00, $00, $01, $00, $00, $00, $00, $00, $00, $00 ; $31-$3F
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $40
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $50
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $60
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $70
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $80
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $90
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $A0
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $B0
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $C0
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $D0
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $E0
  db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; $F0
assert pc() == AreaTileset_AreaProfile+$100

; Per profile: tile type list, sheet list.
AreaTileset_Profiles:
  dw $0000, $0000                                  ; 0: none
  dw AreaTileset_NoTypes, AreaTileset_BoatSheets   ; 1: boat ($30 Kalyxo Docks, $38 Dragon Ship)
if !LYRA_AREA_FERRY_BOUND == 1
  dw AreaTileset_FerryTypes, AreaTileset_FerrySheets ; 2: private bound ferry ($30)
endif

AreaTileset_NoTypes:
  dw $FFFF

; Same transfers as the old hardcoded $38/$30 boat load.
AreaTileset_BoatSheets:
  %AreaTileset_Sheet($2C00, $2000, BoatBitmap)
  %AreaTileset_Sheet($5000, $2000, AdditionalBitmap)
  dw $FFFF

if !LYRA_AREA_FERRY_BOUND == 1
; Root emits these forward-bound assets in the suffix after the module.
assert FerryArea30Types >= $E2E200 && FerryArea30Types+$59 <= !LYRA_AREA_TILESETS_END, "Ferry types outside owned data suffix"
assert FerryArea30Bitmap >= $E2E200 && FerryArea30Bitmap+$0B20 <= !LYRA_AREA_TILESETS_END, "Ferry bitmap outside owned data suffix"
assert FerryArea30Types+$59 <= FerryArea30Bitmap || FerryArea30Bitmap+$0B20 <= FerryArea30Types, "Ferry type/bitmap sources overlap"
AreaTileset_FerryTypes:
  %AreaTileset_Types($0100, $0059, FerryArea30Types)
  dw $FFFF
AreaTileset_FerrySheets:
  %AreaTileset_Sheet($2C00, $2000, BoatBitmap)
  %AreaTileset_Sheet($3000, $0B20, FerryArea30Bitmap)
  %AreaTileset_Sheet($5000, $2000, AdditionalBitmap)
  dw $FFFF
endif

AreaTileset_CodeEnd = pc()
assert pc() <= $E2E200, "Per-area module overlaps generated ferry data"
assert pc() <= !LYRA_AREA_TILESETS_END, "Per-area code/tables exceed owned suffix"
if !LYRA_CURRENT_MODE == 1
  assert SharedGraphicsRuntimeEnd <= !LYRA_AREA_TILESETS_ORIGIN, "Shared graphics overlap per-area suffix"
endif
pullpc
pushpc
org $00886E ; @hook module=Overworld name=AreaTileset_GetTileTypeAtLocation kind=patch skip_abi=1 note=operand_only
  assert read4($00886E) == $0E9459BF, "Native OW tile-type preimage changed"
  LDA.l AreaTileset_TileTypes, X
assert pc() == $008872
org $1BBEFD ; @hook module=Overworld name=AreaTileset_TileAction kind=patch skip_abi=1 note=operand_only
  assert read4($1BBEFD) == $0E9459BF, "Native OW tile-type preimage changed"
  LDA.l AreaTileset_TileTypes, X
assert pc() == $1BBF01
org $1BBF2A ; @hook module=Overworld name=AreaTileset_PickHammerSFX kind=patch skip_abi=1 note=operand_only
  assert read4($1BBF2A) == $0E9459BF, "Native OW tile-type preimage changed"
  LDA.l AreaTileset_TileTypes, X
assert pc() == $1BBF2E
org $1BC04E ; @hook module=Overworld name=AreaTileset_GetLiftableTileType kind=patch skip_abi=1 note=operand_only
  assert read4($1BC04E) == $0E9459BF, "Native OW tile-type preimage changed"
  LDA.l AreaTileset_TileTypes, X
assert pc() == $1BC052
pullpc
