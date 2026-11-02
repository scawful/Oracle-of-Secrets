; =========================================================
;  Item Selection Code

; Decides which function to jump to.
Menu_ItemIndex:
  db $00
  ;  Bow,     Boomerang, Hookshot, Bombs,      Powder,     Bottle 1
  db $03,     $02,       $0E,      $01,        $0A,        $0B
  ;  Hammer,  Lamp,      Fire Rod, Ice Rod,    Mirror,     Bottle 2
  db $04,     $09,       $05,      $06,        $14,        $0B
  ;  Ocarina, Book,      Somaria,  Fishing,      Feather,    Bottle3
  db $08,     $0C,       $12,      $0D,        $07,        $0B
  ;  Deku,    Zora,      Wolf,     Bunny Hood, Stone Mask, Bottle4
  db $11,     $0F,       $08,      $10,        $13,        $0B
if !ENABLE_PORTAL_ROD_CELL == 1
  ;  $19: Portal Rod cell, same routine as the Fishing
  ;  Rod ($0D, LinkItem_FishingRodAndPortalRod picks the rod by $0202)
  db $0D
endif

; =========================================================
if !ENABLE_GOLDSTAR_CELL == 1
  db $0E ; $1A Goldstar uses the existing hookshot/chain handler
  db $0D ; $1B Byrna shares the rod action, with separate ownership
  db $01 ; $1C Bombchu: native bomb action
  db $0E ; $1D Switch Hook: native chain action
  db $00 ; $1E Garo: Equipment binding only
endif
Menu_ItemIndex_End:

; Decides which graphics is drawn
Menu_AddressIndex:
  db $7EF340 ; Bow
  db $7EF341 ; Boomerang
  db $7EF342 ; Hookshot / Goldstar
  db $7EF343 ; Bombs
  db $7EF344 ; Powder
  db $7EF35C ; Bottle 1

  db $7EF34B ; Hammer
  db $7EF34A ; Lamp
  db $7EF345 ; Fire Rod
  db $7EF346 ; Ice Rod
  db $7EF353 ; Magic Mirror
  db $7EF35D ; Bottle 2

  db $7EF34C ; Ocarina ; shovel 7EF34F
  db $7EF34E ; Book of Secrets
  db $7EF350 ; Cane of Somaria
  db $7EF351 ; Fishing Rod / Portal Rod
  db $7EF34D ; Roc's Feather
  db $7EF35E ; Bottle 3

  db $7EF349 ; Deku Mask
  db $7EF347 ; Zora Mask
  db $7EF358 ; Wolf Mask
  db $7EF348 ; Bunny Hood
  db $7EF352 ; Stone Mask
  db $7EF35F ; Bottle #4
if !ENABLE_PORTAL_ROD_CELL == 1
  db PortalRodOwned&$FF ; $19 Portal Rod ($7EF3A6)
endif
if !ENABLE_GOLDSTAR_CELL == 1
  db GoldstarOwned&$FF ; $1A
  db ByrnaOwned&$FF    ; $1B
  db BombchuOwned&$FF  ; $1C
  db SwitchHookOwned&$FF ; $1D
  db GaroMaskOwned&$FF ; $1E
endif

; =========================================================

Menu_ItemCursorPositions:
  ; Row 1
  dw menu_offset(6,2)  ; bow
  dw menu_offset(6,5)  ; boom
  dw menu_offset(6,8)  ; hookshot
  dw menu_offset(6,12) ; bombs
  dw menu_offset(6,15) ; powder
  dw menu_offset(6,18) ; bottle1

  ; Row 2
  dw menu_offset(9,2)  ; hammer
  dw menu_offset(9,5)  ; lamp
  dw menu_offset(9,8)  ; fire rod
  dw menu_offset(9,12) ; ice rod
  dw menu_offset(9,15) ; mirror
  dw menu_offset(9,18) ; bottle2

  ; Row 3
  dw menu_offset(12,2)  ; ocarina
  dw menu_offset(12,5)  ; book
  dw menu_offset(12,8)  ; somaria
if !ENABLE_GOLDSTAR_CELL == 1
  dw (15*64)+(5*2)      ; $10 Fishing, bottom row second cell
else
  dw menu_offset(12,12) ; Fishing (legacy position)
endif
  dw menu_offset(12,15) ; feather
  dw menu_offset(12,18) ; bottle3

  ; Row 4
  dw menu_offset(15,2)  ; deku mask
  dw menu_offset(15,5)  ; zora mask
  dw menu_offset(15,8)  ; wolf mask
  dw menu_offset(15,12) ; bunny hood
  dw menu_offset(15,15) ; stone mask
  dw menu_offset(15,18) ; bottle4
if !ENABLE_PORTAL_ROD_CELL == 1
  ; $19 Portal Rod: fifth custom-grid cell, first cell in the legacy layout.
  ; Arithmetic keeps the menu registry's editable entries distinct.
if !ENABLE_GOLDSTAR_CELL == 1
  dw (15*64)+(15*2)
else
  dw (15*64)+(2*2)
endif
endif
if !ENABLE_GOLDSTAR_CELL == 1
  dw (15*64)+(2*2)  ; $1A Goldstar, bottom row first cell
  dw (12*64)+(12*2) ; $1B Byrna, beside Somaria
  dw (15*64)+(12*2) ; $1C Bombchu, directly below Bombs
  dw (15*64)+(8*2)  ; $1D Switch Hook, directly below Hookshot
  dw (15*64)+(18*2) ; $1E unused normal cursor; Garo lives on Equipment
endif

; =========================================================

Menu_FindNextItem:
{
if !ENABLE_GOLDSTAR_CELL == 1
  LDA.b #$01
  JMP Menu_CustomGridMove
else
  SEP #$30                   ; Ensure 8-bit A, X, Y
  LDY.b #$18                 ; Max 24 items to check (use Y as counter)
  .loop
    LDA.w $0202 : INC A
    CMP.b #$19 : BCC .no_reset
      LDA.b #$01
    .no_reset
    STA.w $0202
    TAX : DEX                ; X = position - 1 (for table index)
    LDA.l Menu_AddressLong, X : TAX  ; Load offset from table
    LDA.l $7EF300, X         ; Load item value
if !ENABLE_MENU_PAGE3 == 1
    JSR Menu_Page3_GridFilter ; masks count as empty cells
endif
    BNE .found               ; Item exists, done
    DEY : BNE .loop          ; Keep searching
  .found
  RTS
endif
}

; =========================================================

Menu_FindPrevItem:
{
if !ENABLE_GOLDSTAR_CELL == 1
  LDA.b #$FF
  JMP Menu_CustomGridMove
else
  SEP #$30                   ; Ensure 8-bit A, X, Y
  LDY.b #$18                 ; Max 24 items to check (use Y as counter)
  .loop
    LDA.w $0202 : DEC A : BNE .no_reset
      LDA.b #$18
    .no_reset
    STA.w $0202
    TAX : DEX                ; X = position - 1 (for table index)
    LDA.l Menu_AddressLong, X : TAX  ; Load offset from table
    LDA.l $7EF300, X         ; Load item value
if !ENABLE_MENU_PAGE3 == 1
    JSR Menu_Page3_GridFilter ; masks count as empty cells
endif
    BNE .found               ; Item exists, done
    DEY : BNE .loop          ; Keep searching
  .found
  RTS
endif
}

; =========================================================

Menu_FindNextDownItem:
{
if !ENABLE_GOLDSTAR_CELL == 1
  LDA.b #$06
  JMP Menu_CustomGridMove
else
  SEP #$30                        ; Ensure 8-bit mode
  LDA.w $0202 : CLC : ADC.b #$06
  CMP.b #$19 : BCC .no_reset
    SBC.b #$18
  .no_reset
  STA.w $0202
  TAX : DEX                       ; X = position - 1
  LDA.l Menu_AddressLong, X : TAX ; Load offset from table
  LDA.l $7EF300, X
if !ENABLE_MENU_PAGE3 == 1
  JSR Menu_Page3_GridFilter       ; masks count as empty cells
  BNE +
    JMP Menu_FindNextItem         ; If empty, scan horizontally
  +
else
  BEQ Menu_FindNextItem           ; If empty, scan horizontally
endif
  RTS
endif
}

; =========================================================

Menu_FindNextUpItem:
{
if !ENABLE_GOLDSTAR_CELL == 1
  LDA.b #$FA
  JMP Menu_CustomGridMove
else
  SEP #$30                        ; Ensure 8-bit mode
  LDA.w $0202 : SEC : SBC.b #$06
  BEQ .wrap                       ; If zero, wrap
  BPL .no_reset                   ; If positive (1+), valid
  .wrap
    CLC : ADC.b #$18              ; Wrap to bottom row
  .no_reset
  STA.w $0202
  TAX : DEX                       ; X = position - 1
  LDA.l Menu_AddressLong, X : TAX ; Load offset from table
  LDA.l $7EF300, X
if !ENABLE_MENU_PAGE3 == 1
  JSR Menu_Page3_GridFilter       ; masks count as empty cells
  BNE +
    JMP Menu_FindNextItem         ; If empty, scan horizontally
  +
else
  BEQ Menu_FindNextItem           ; If empty, scan horizontally
endif
  RTS
endif
}


; =========================================================

Menu_DeleteCursor:
{
  REP   #$30
  LDX.w Menu_ItemCursorPositions-2, Y

Menu_DeleteCursor_AltEntry:
  LDA.w #$20F5
  STA.w $1108, X : STA.w $1148, X
  STA.w $114E, X : STA.w $110E, X
  STA.w $11C8, X : STA.w $1188, X
  STA.w $118E, X : STA.w $11CE, X
  SEP   #$30
  STZ   $0207
  RTS
}

; =========================================================

Menu_InitItemScreen:
{
if !ENABLE_GOLDSTAR_CELL == 1
  JSR Menu_SplitValidateSelection
  STZ.w $0207
  LDA.b #$04 : STA.w $0200
  RTS
endif
  SEP   #$30
  LDY.w $0202 : BNE .all_good
    ; Loop through the SRM of each item to see if we have
    ; one of them so we can start with that one selected.
    .lookForAlternateItem
    LDY.b #$00

    .loop
      INY : CPY.b #$19 : BCS .bad  ; Only 24 items (1-24), stop at 25
        TYA : TAX : DEX            ; X = Y - 1 (for table index)
        LDA.l Menu_AddressLong, X : TAX
        LDA.l $7EF300, X
    BEQ .loop

    STY.w $0202
    BRA .all_good

    .bad
    ; If we made it here that means there are no items
    ; available but one was still selected. This should
    ; never happen under normal vanilla circumstances.
    STZ.w $0202

    STZ   $0207
    LDA.b #$04
    STA.w $0200
    RTS

  .all_good
  ; Double check we still have the item that was selected.
  ; This is to prevent a bug where we can get stuck in an
  ; infinite loop later on.
  TYA : TAX : DEX                  ; X = Y - 1 (for table index)
  LDA.l Menu_AddressLong, X : TAX
  LDA.l $7EF300, X
  CMP.b #$01 : BCC .lookForAlternateItem
    STZ   $0207
    LDA.b #$04
    STA.w $0200
    RTS
}

; =========================================================

Menu_AddressLong:
  db $40 ; Bow
  db $41 ; Boomerang
  db $42 ; Hookshot
  db $43 ; Bombs
  db $44 ; Powder
  db $5C ; Bottle 1

  db $4B ; Hammer
  db $4A ; Lamp
  db $45 ; Fire Rod
  db $46 ; Ice Rod
  db $53 ; Magic Mirror
  db $5D ; Bottle 2

  db $4C ; Ocarina (formerly shovel 4F)
  db $4E ; Book
  db $50 ; Cane of Somaria
  db $51 ; Fishing Rod
  db $4D ; Roc's Feather
  db $5E ; Bottle 3

  db $49 ; Deku Mask
  db $47 ; Zora Mask
  db $58 ; Wolf Mask
  db $48 ; Bunny Hood
  db $52 ; Stone Mask
  db $5F ; Bottle 4
if !ENABLE_PORTAL_ROD_CELL == 1
  db PortalRodOwned&$FF ; $19 Portal Rod ($7EF3A6)
endif
if !ENABLE_GOLDSTAR_CELL == 1
  db GoldstarOwned&$FF ; $1A
  db ByrnaOwned&$FF    ; $1B
  db BombchuOwned&$FF  ; $1C
  db SwitchHookOwned&$FF ; $1D
  db GaroMaskOwned&$FF ; $1E
endif

GotoNextItem_Local:
{
  ; Load our currently equipped item, and move to the next one
  ; If we reach our limit (21), set it back to the bow and arrow slot.
  LDA $0202 : INC A : CMP.b #$18 : BCC .dont_reset
    LDA.b #$01
  .dont_reset
  ; Otherwise try to equip the item in the next slot
  STA $0202
  RTS
}

DoWeHaveThisItem_Override:
{
  LDY.w $0202 : LDX.w Menu_AddressLong-1, Y
  LDA.l $7EF300, X : CMP.b #$00 : BNE .have_this_item
    CLC
    RTL
  .have_this_item
  SEC
  RTL
}

TryEquipNextItem_Override:
{
  .keep_looking
    JSR GotoNextItem_Local
  JSL DoWeHaveThisItem_Override : BCC .keep_looking
  RTS
}

SearchForEquippedItem_Override:
{
  PHB : PHK : PLB
  SEP   #$30
if !ENABLE_ONE_RING == 1
  JSR OneRing_MigrateSlots ; file load (Module05) and RefreshIcon
endif
if !ENABLE_EQUIPMENT_MENU == 1
  ; $030F is volatile WRAM and survives a warm file switch (Save and Quit ->
  ; another file). Clear it so the loaded file's SavedOcarinaSong decides;
  ; otherwise the previous file's song would be written into this file.
  ; Harmless on RefreshIcon: the saved byte is kept in sync with $030F.
  STZ.w CurrentSong
  JSL UpdateFluteSong_Long ; restore/validate the saved song on file load
endif

if !ENABLE_GOLDSTAR_CELL == 1
  JSL GoldstarInventory_Migrate
  JSR Menu_SplitValidateSelection
  REP #$30 : PLB : RTL
endif
  LDY.b #$18
  .next_check
  LDX.w Menu_AddressLong-1, Y
  LDA.l $7EF300, X : CMP.b #$00 : BNE .item_available
  DEY : BPL .next_check

  ; In this case we have no equippable items
  STZ $0202 : STZ $0203 : STZ $0204

  .we_have_that_item
  REP #$30
  PLB
  RTL

  .item_available
  ; Is there an item currently equipped (in the HUD slot)?
  LDA.w $0202 : BNE .alreadyEquipped
    ; If not, set the equipped item to the Lamp
    LDA.b #$08 : STA $0202

  .alreadyEquipped
  JMP .exit
  .keep_looking
    JSR GotoNextItem_Local
  JSL DoWeHaveThisItem_Override : BCC .keep_looking
  BCS .we_have_that_item
  JSR TryEquipNextItem_Override
  .exit

  REP #$30
  PLB
  RTL
}

if !ENABLE_ONE_RING == 1
; One ring (decisions.org 2026-09-28): saves from before the rule can hold
; rings in RingSlot2/3. Keep one worn ring: an empty slot 1 takes slot 2's
; ring, else slot 3's; then clear slots 2-3. Nothing else writes slots 2-3
; with the flag on, so after the first run (file load) this changes nothing.
; 8-bit A. Keeps X, Y.
OneRing_MigrateSlots:
{
  LDA.l RingSlot1 : BNE .clear
    LDA.l RingSlot2 : BNE .move
    LDA.l RingSlot3 : BEQ .clear
    .move
    STA.l RingSlot1
  .clear
  LDA.b #$00 : STA.l RingSlot2 : STA.l RingSlot3
  RTS
}
endif

pushpc

org $0DDEB0 ; @hook module=Menu
ItemMenu_CheckForOwnership:
{
  JSL DoWeHaveThisItem_Override
  RTS
}

org $0DE399 ; @hook module=Menu
SearchForEquippedItem:
{
  JSL SearchForEquippedItem_Override
  RTS
}
assert pc() <= $0DE3C7

pullpc


if !ENABLE_GOLDSTAR_CELL == 1
; Validate logical IDs, not physical cells. Used after old-save migration,
; file load and menu initialization, including Goldstar-only inventories.
Menu_SplitValidateSelection:
{
  SEP #$30
  LDA.w $0202 : JSR .owned : BCS .done
  LDY.b #$01
  .scan
  TYA : JSR .owned : BCS .found
  INY : CPY.b #$1E : BCC .scan
  LDY.b #$00
  .found
  STY.w $0202
  .done
  RTS
  .owned
  CMP.b #$01 : BCC .no
  CMP.b #$1E : BCS .no
  CMP.b #$13 : BCC .check
  CMP.b #$18 : BCC .no
  .check
  CMP.b #$1B : BCC .ordinary
    TAX : DEX
    LDA.l Menu_AddressLong,X : TAX
    LDA.l $7EF300,X : CMP.b #$01 : BNE .no
    SEC : RTS
  .ordinary
  TAX : DEX
  LDA.l Menu_AddressLong, X : TAX
  LDA.l $7EF300, X : BEQ .no
  SEC : RTS
  .no
  CLC : RTS
}
endif

if !ENABLE_GOLDSTAR_CELL == 1
; Physical cells are independent of saved logical IDs. Keep $0202 logical
; even while deleting the old bracket; masks retain IDs $13-$17 elsewhere.
Menu_CustomGridItems:
  db $01,$02,$03,$04,$05,$06
  db $07,$08,$09,$0A,$0B,$0C
  db $0D,$0E,$0F,$1B,$11,$12
  db $1A,$10,$1D,$1C,$19,$18

; X = zero-based physical cell; C set and A = its owned logical ID.
; Keeps X/Y, uses $01. Invalid Byrna values are not ownership.
Menu_CustomGridOwned:
{
  PHX
  LDA.w Menu_CustomGridItems,X : BEQ .no
  STA.b $01
  CMP.b #$1B : BCC .ordinary
    TAX : DEX
    LDA.w Menu_AddressLong,X : TAX
    LDA.l $7EF300,X : CMP.b #$01 : BNE .no
    BRA .yes
  .ordinary
  TAX : DEX
  LDA.w Menu_AddressLong,X : TAX
  LDA.l $7EF300,X : BEQ .no
  .yes
  LDA.b $01
  PLX : SEC : RTS
  .no
  PLX : CLC : RTS
}

; A = +1/-1/+6/-6. The vertical empty-cell fallback remains a forward scan.
; Search is bounded to 24 cells; an empty inventory leaves selection intact.
; Uses $00-$01, destroys X/Y; entry and exit M/X=8 like the old helpers.
Menu_CustomGridMove:
{
  SEP #$30
  STA.b $00
  LDX.b #$00
  .locate
  LDA.w Menu_CustomGridItems,X : CMP.w $0202 : BEQ .located
  INX : CPX.b #$18 : BCC .locate
  LDX.b #$17
  LDA.b #$01 : STA.b $00
  .located
  LDY.b #$18
  .scan
  TXA : CLC : ADC.b $00 : BMI .wrap_low
  CMP.b #$18 : BCC .candidate
  SBC.b #$18
  BRA .candidate
  .wrap_low
  CLC : ADC.b #$18
  .candidate
  TAX
  JSR Menu_CustomGridOwned : BCS .found
  LDA.b $00 : CMP.b #$06 : BEQ .horizontal
  CMP.b #$FA : BNE .again
  .horizontal
  LDA.b #$01 : STA.b $00
  .again
  DEY : BNE .scan
  RTS
  .found
  STA.w $0202
  RTS
}
endif
