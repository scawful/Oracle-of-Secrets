; =============================================================================
;  Item Selection Code
; =============================================================================

Menu_ItemIndex:
  db $03 ; slingshot
  db $02 ; boomerang
  db $0E ; hookshot 
  db $01 ; bombs
  db $11 ; deku mask 
  db $0B ; bottle1
  db $04 ; hammer 
  db $09 ; lamp 
  db $05 ; firerod (nimbus)
  db $06 ; icerod 
  db $0F ; bombos / goron 
  db $4B ; bottle2
  db $0B ; shovel
  db $07 ; feather 
  db $12 ; somaria
  db $0D ; byrna
  db $10 ; bunny hood
  db $8B ; bottle3
  db $0A ; powder 
  db $0C ; book 
  db $08 ; ocarina 
  db $14 ; mirror
  db $13 ; stone mask
  db $CB ; bottle4

; -----------------------------------------------------------------------------

Menu_AddressIndex:
  db $7EF340 ; bow
  db $7EF341 ; boom
  db $7EF342 ; hookshot 
  db $7EF343 ; bombs
  db $7EF348 ; deku mask 
  db $7EF35C ; bottle1
  db $7EF34B ; hammer 
  db $7EF34A ; lamp 
  db $7EF345 ; firerod (nimbus)
  db $7EF346 ; icerod 
  db $7EF347 ; bombos / goron 
  db $7EF35D ; bottle2
  db $7EF34F ; shovel
  db $7EF34D ; feather 
  db $7EF350 ; somaria
  db $7EF351 ; byrna
  db $7EF349 ; bunny hood
  db $7EF35E ; bottle3
  db $7EF344 ; powder 
  db $7EF34E ; book 
  db $7EF34C ; ocarina 
  db $7EF353 ; mirror
  db $7EF352 ; stone mask
  db $7EF35F ; bottle4

; -----------------------------------------------------------------------------

Menu_ItemCursorPositions:
  dw menu_offset(6,2) ; bow
  dw menu_offset(6,5) ; boom
  dw menu_offset(6,8) ; hookshot
  dw menu_offset(6,12) ; bombs
  dw menu_offset(6,15) ; deku mask
  dw menu_offset(6,18) ; bottle1

  dw menu_offset(9,2) ; hammer 
  dw menu_offset(9,5) ; lamp
  dw menu_offset(9,8) ; firerod
  dw menu_offset(9,12) ; icerod
  dw menu_offset(9,15) ; goron
  dw menu_offset(9,18) ; bottle2

  dw menu_offset(12,2) ; shovel 
  dw menu_offset(12,5) ; feather 
  dw menu_offset(12,8) ; somaria
  dw menu_offset(12,12) ; byrna
  dw menu_offset(12,15) ; bunny hood
  dw menu_offset(12,18) ; bottle3

  dw menu_offset(15,2) ; powder 
  dw menu_offset(15,5) ; book 
  dw menu_offset(15,8) ; flute
  dw menu_offset(15,12) ; mirror
  dw menu_offset(15,15) ; stone mask 
  dw menu_offset(15,18) ; bottle4

; -----------------------------------------------------------------------------

Menu_FindNextItem:
  LDY.w $0202 : INY 
  CPY.b #$19 : BCC .no_reset 
  LDY.b #$01 
.no_reset 
  STY.w $0202
  LDX.w Menu_AddressIndex-1, Y
  LDA.l $7EF300, X
  BEQ Menu_FindNextItem
  RTS

; -----------------------------------------------------------------------------

Menu_FindPrevItem:
  LDY.w $0202 : DEY : BNE .no_reset 
  LDY.b #$18
.no_reset 
  STY.w $0202
  LDX.w Menu_AddressIndex-1, Y
  LDA.l $7EF300, X
  BEQ Menu_FindPrevItem
  RTS
; -----------------------------------------------------------------------------

Menu_FindNextDownItem:
  LDA.w $0202 : CLC : ADC.b #$06 
  CMP.b #$19 : BCC .no_reset
  SBC.b #$18
.no_reset 
  TAY : STY.w $0202
  LDX.w Menu_AddressIndex-1, Y 
  LDA.l $7EF300, X
  BEQ Menu_FindNextItem
  RTS 

; -----------------------------------------------------------------------------

Menu_FindNextUpItem:
  LDA.w $0202 : SEC : SBC.b #$06 
  BPL .no_reset : BNE .no_reset
  CLC : ADC.b #$18 
.no_reset 
  TAY : STY.w $0202
  LDX.w Menu_AddressIndex-1, Y 
  LDA.l $7EF300, X
  BEQ Menu_FindPrevItem
  RTS 

; -----------------------------------------------------------------------------

Menu_DeleteCursor:
  REP #$30
  LDX.w Menu_ItemCursorPositions-2, Y

  LDA.w #$20F5
  STA.w $1108, X
  STA.w $1148, X
  STA.w $114E, X 
  STA.w $110E, X 
  STA.w $11C8, X 
  STA.w $1188, X
  STA.w $118E, X 
  STA.w $11CE, X 
  SEP #$30
  STZ $0207
  RTS 

; -----------------------------------------------------------------------------