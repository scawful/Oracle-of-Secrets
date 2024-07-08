; =========================================================
;  Item Selection Code

; Decides which function to jump to.
Menu_ItemIndex:
  db $00
  ;  Bow,     Boomerang, Hookshot, Bombs,      Powder,     Bottle 1
  db $03,     $02,       $0E,      $01,        $0A,        $0B
  ;  Hammer,  Lamp,      Fire Rod, Ice Rod,    Mirror,     Bottle 2
  db $04,     $09,       $05,      $06,        $14,        $0B
  ;  Ocarina, Book,      Somaria,  Byrna,      Feather,    Bottle3
  db $08,     $0C,       $12,      $0D,        $07,        $0B
  ;  Deku,    Zora,      Wolf,     Bunny Hood, Stone Mask, Bottle4
  db $11,     $0F,       $08,      $10,        $13,        $0B

; =========================================================
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
  db $7EF350 ; Cane of Somaria / Cane of Byrna
  db $7EF351 ; Fishing Rod / Portal Rod
  db $7EF34D ; Roc's Feather 
  db $7EF35E ; Bottle 3

  db $7EF349 ; Deku Mask 
  db $7EF347 ; Zora Mask
  db $7EF358 ; Wolf Mask 
  db $7EF348 ; Bunny Hood
  db $7EF352 ; Stone Mask
  db $7EF35F ; Bottle #4

; =========================================================

Menu_ItemCursorPositions:
  dw menu_offset(6,2)  ; bow
  dw menu_offset(6,5)  ; boom
  dw menu_offset(6,8)  ; hookshot
  dw menu_offset(6,12) ; bombs
  dw menu_offset(6,15) ; deku mask
  dw menu_offset(6,18) ; bottle1

  dw menu_offset(9,2)  ; hammer 
  dw menu_offset(9,5)  ; lamp
  dw menu_offset(9,8)  ; firerod
  dw menu_offset(9,12) ; icerod
  dw menu_offset(9,15) ; goron
  dw menu_offset(9,18) ; bottle2

  dw menu_offset(12,2)  ; shovel 
  dw menu_offset(12,5)  ; feather 
  dw menu_offset(12,8)  ; somaria
  dw menu_offset(12,12) ; byrna / fishing rod
  dw menu_offset(12,15) ; bunny hood
  dw menu_offset(12,18) ; bottle3

  dw menu_offset(15,2)  ; powder 
  dw menu_offset(15,5)  ; book 
  dw menu_offset(15,8)  ; flute
  dw menu_offset(15,12) ; mirror
  dw menu_offset(15,15) ; stone mask 
  dw menu_offset(15,18) ; bottle4

; =========================================================


Menu_FindNextItem:
{
  LDY.w $0202 : INY
  CPY.b #$19 : BCC .no_reset
  LDY.b #$01
.no_reset 
  STY.w $0202
  LDX.w Menu_AddressIndex-1, Y
  LDA.l $7EF300,             X
  BEQ   Menu_FindNextItem
  RTS
}

; =========================================================

Menu_FindPrevItem:
{
  LDY.w $0202 : DEY : BNE .no_reset
  LDY.b #$18
.no_reset 
  STY.w $0202
  LDX.w Menu_AddressIndex-1, Y
  LDA.l $7EF300,             X
  BEQ   Menu_FindPrevItem
  RTS
}

; =========================================================

Menu_FindNextDownItem:
{
  LDA.w $0202 : CLC : ADC.b #$06
  CMP.b #$19 : BCC .no_reset
  SBC.b #$18
.no_reset 
  TAY   : STY.w $0202
  LDX.w Menu_AddressIndex-1, Y
  LDA.l $7EF300,             X
  BEQ   Menu_FindNextItem
  RTS 
}

; =========================================================

Menu_FindNextUpItem:
{
  LDA.w $0202 : SEC : SBC.b #$06
  BPL   .no_reset : BNE .no_reset
  CLC   : ADC.b #$18
.no_reset 
  TAY   : STY.w $0202
  CPY.b #$19 : BCS .reset_up
  LDX.w Menu_AddressIndex-1, Y
  LDA.l $7EF300,             X
  BEQ   Menu_FindNextItem
  RTS 
.reset_up
  LDY.b #$01
  STY.w $0202
  LDX.w Menu_AddressIndex-1, Y
  LDA.l $7EF300,             X
  BEQ   Menu_FindNextItem
  RTS 
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
  SEP   #$30
  LDY.w $0202 : BNE .all_good
    ; Loop through the SRM of each item to see if we have
    ; one of them so we can start with that one selected.
    .lookForAlternateItem
    LDY.b #$00

    .loop
      INY : CPY.b #$25 : BCS .bad
        LDX.w Menu_AddressIndex-1, Y
        LDA.l $7EF300,             X
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
  LDX.w Menu_AddressIndex-1, Y
  LDA.l $7EF300,             X
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
  db $50 ; Cane of Somaria / Cane of Byrna
  db $51 ; Fishing Rod
  db $4D ; Roc's Feather 
  db $5E ; Bottle 3

  db $49 ; Deku Mask 
  db $47 ; Zora Mask
  db $58 ; Wolf Mask 
  db $48 ; Bunny Hood
  db $52 ; Stone Mask
  db $5F ; Bottle #4

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

pushpc 

org $0DDEB0
ItemMenu_CheckForOwnership:
{
  JSL DoWeHaveThisItem_Override
  RTS
}

org $0DE399
SearchForEquippedItem:
{
  JSL SearchForEquippedItem_Override
  RTS
}
warnpc $0DE3C7

; =========================================================

pullpc