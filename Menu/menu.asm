;===========================================================
;           The Legend of Zelda: Oracle of Secrets
;           ------------NEW Custom Menu ------------
;
; Details:  Complete overhaul of original LTTP menu
;           Two Pane Oot/MM inspired design
;           Original item layout and designs
;           Detailed Quest Status screen
;           Player name, location name, and death count
;           
; Significant thanks to Kan for helping me craft this menu!
;   
;===========================================================

pushpc
org $1BD662  ; update in game hud colors 
  dw hexto555($814f16), hexto555($552903)
org $1BD66A
  dw hexto555($d51d00), hexto555($f9f9f9)
org $1DB672
  dw hexto555($d1a452), hexto555($f9f9f9)
org $1DB67A
  dw hexto555($5987e0), hexto555($f9f9f9)
org $1DB682
  dw hexto555($7b7b83), hexto555($bbbbbb)
org $1DB68A
  dw hexto555($a58100), hexto555($dfb93f)
org $0098AB  ; menu override 
  db $D8>>1  
org $00F877 
  db Menu_Entry>>0
org $00F883 
  db Menu_Entry>>8
org $00F88F 
  db Menu_Entry>>16
org $808B6B 
  LDX.w #$6040
org $8DDFB2 
  LDA.l Menu_ItemIndex, X
pullpc

org $248000
Menu_Tilemap:
  incbin "tilemaps/menu_frame.tilemap"
Menu_QuestIcons:
  incbin "tilemaps/quest_icons.tilemap"

incsrc "menu_gfx_table.asm"
incsrc "menu_draw_items.asm"
incsrc "menu_text.asm"
incsrc "menu_palette.asm"

Menu_Entry:
  PHB : PHK : PLB 
  LDA.w $0200
  ASL
  TAX
  JSR (.vectors,X)
  SEP #$20
  PLB
  RTL
incsrc "menu_vectors.asm"

; ===================================================================================
; 00 MENU INIT GRAPHICS 

Menu_InitGraphics:
{
  LDA.w $0780 : STA.w $00
  INC $0200
}

; ===================================================================================
; 01 MENU UPLOAD RIGHT 

Menu_UploadRight:
{
  JSR Menu_DrawBackground
  JSR Menu_DrawQuestItems
  JSR Menu_DrawCharacterName
  JSR DrawQuestIcons
  JSR DrawTriforceIcon
  JSR DrawPendantIcons
  JSR DrawDeathCounter
  JSR DrawPlaytimeLabel
  JSR DrawScrollsLabel

  ;; heart piece empty, move this later 
  LDX.w #$2484 : STX.w $149E    ; draw empty top left
  LDX.w #$6484 : STX.w $14A0    ; draw empty top right 
  LDX.w #$2485 : STX.w $14DE    ; draw empty bottom left
  LDX.w #$6485 : STX.w $14E0    ; draw empty bottom right

  JSR DrawHeartPieces
  JSR DrawMusicNotes
  JSR Menu_DrawQuestStatus
  JSR Menu_DrawAreaNameTXT
  JSR DrawLocationName

  SEP #$30
  LDA.b #$23 : STA.w $0116
  LDA.b #$01 : STA.b $17
  INC.w $0200
  RTS
}

; ===================================================================================
; 02 MENU UPLOAD LEFT 

Menu_UploadLeft:
{
  JSR Menu_DrawBackground
  JSR DrawYItems
  JSR Menu_DrawSelect
  JSR Menu_DrawItemName
  
  ; INSERT PALETTE -------
  LDX.w #$3E
.loop
  LDA.w Menu_Palette, X
  STA.l $7EC502, X
  DEX : DEX
  BPL .loop
  
  SEP #$30
  ;-----------------------
  LDA.b #$22 : STA.w $0116
  LDA.b #$01 : STA.b $17 : STA.b $15 ; added for palette
  INC.w $0200
  RTS       
}
   
; ===================================================================================
; 03 MENU SCROLL DOWN 

Menu_Scroll:
    dw 0, -3, -5, -7, -10, -12, -15, -20, -28, -40, -50, -60, -75, -90, -100, -125, -150, -175, -190, -200, -210, -220, -225, -230, -232, -234, -238

Menu_ScrollDown:
{
  LDA.b #$11 : STA.w $012F
  SEP #$10
  REP #$20

  LDX.w MenuScrollLevelV
  INX : INX
  LDA.w Menu_Scroll, X 
  STA.b $EA
  CMP.w #$FF12 : BNE .loop

  JMP Menu_InitItemScreen

.loop
  STX.w MenuScrollLevelV
  RTS
}

; ===================================================================================
; 04 MENU ITEM SCREEN 

Menu_ItemIndex:
  db $03 ; slingshot
  db $02 ; boomerang
  db $0E ; hookshot 
  db $01 ; bombs
  db $11 ; deku mask 
  db $0B ; bottle1
  db $05 ; firerod (nimbus)
  db $06 ; icerod 
  db $09 ; lamp 
  db $04 ; hammer 
  db $0F ; bombos / goron 
  db $4B ; bottle2
  db $12 ; somaria
  db $0D ; byrna
  db $0C ; book 
  db $07 ; feather 
  db $10 ; bunny hood
  db $8B ; bottle3
  db $08 ; ocarina 
  db $14 ; mirror
  db $0B ; shovel
  db $0A ; powder 
  db $13 ; stone mask
  db $CB ; bottle4

Menu_AddressIndex:
  db $7EF340 ; bow
  db $7EF341 ; boom
  db $7EF342 ; hookshot 
  db $7EF343 ; bombs
  db $7EF348 ; deku mask 
  db $7EF35C ; bottle1
  db $7EF345 ; firerod (nimbus)
  db $7EF346 ; icerod 
  db $7EF34A ; lamp 
  db $7EF34B ; hammer 
  db $7EF347 ; bombos / goron 
  db $7EF35D ; bottle2
  db $7EF350 ; somaria
  db $7EF351 ; byrna
  db $7EF34E ; book 
  db $7EF34D ; feather 
  db $7EF349 ; bunny hood
  db $7EF35E ; bottle3
  db $7EF34C ; ocarina 
  db $7EF353 ; mirror
  db $7EF34F ; shovel
  db $7EF344 ; powder 
  db $7EF352 ; stone mask
  db $7EF35F ; bottle4

Menu_ItemCursorPositions:
  dw menu_offset(6,1) ; bow
  dw menu_offset(6,4) ; boom
  dw menu_offset(6,7) ; hookshot
  dw menu_offset(6,10) ; bombs
  dw menu_offset(6,13) ; deku mask
  dw menu_offset(6,16) ; bottle1
  dw menu_offset(9,1) ; firerod
  dw menu_offset(9,4) ; icerod
  dw menu_offset(9,7) ; lamp
  dw menu_offset(9,10) ; hammer 
  dw menu_offset(9,13) ; goron
  dw menu_offset(9,16) ; bottle2
  dw menu_offset(12,1) ; somaria
  dw menu_offset(12,4) ; byrna
  dw menu_offset(12,7) ; book 
  dw menu_offset(12,10) ; feather 
  dw menu_offset(12,13) ; bunny hood
  dw menu_offset(12,16) ; bottle3
  dw menu_offset(15,1) ; flute
  dw menu_offset(15,4) ; mirror
  dw menu_offset(15,7) ; shovel 
  dw menu_offset(15,10) ; powder 
  dw menu_offset(15,13) ; stone mask 
  dw menu_offset(15,16) ; bottle

; ----------------------
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
; ----------------------
Menu_FindPrevItem:
  LDY.w $0202 : DEY : BNE .no_reset 
  LDY.b #$18
.no_reset 
  STY.w $0202
  LDX.w Menu_AddressIndex-1, Y
  LDA.l $7EF300, X
  BEQ Menu_FindPrevItem
  RTS
; ----------------------
Menu_FindNextDownItem:
  LDA.w $0202 : CLC : ADC.b #$06 
  CMP.b #$19 : BCC .no_reset
  SBC.b #$18
.no_reset 
  TAY : STY.w $0202
  LDX.w Menu_AddressIndex-1, Y 
  LDA.l $7EF300, X
  BEQ Menu_FindNextUpItem
  RTS 
; ----------------------
Menu_FindNextUpItem:
  LDA.w $0202 : SEC : SBC.b #$06 
  BPL .no_reset : BNE .no_reset
  CLC : ADC.b #$18 
.no_reset 
  TAY : STY.w $0202
  LDX.w Menu_AddressIndex-1, Y 
  LDA.l $7EF300, X
  BEQ Menu_FindNextDownItem
  RTS 
; ----------------------
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
; ----------------------
Menu_InitItemScreen:
{
  SEP #$30
  LDY.w $0202 : BNE .all_good

  .loop
  INY : CPY.b #$25 : BCS .bad 
  LDX.w Menu_AddressIndex-1, Y
  LDA.l $7EF300, X 
  BEQ .loop 

  STY.w $0202
  BRA .all_good 

  .bad
  STZ.w $0202

  .all_good 

  STZ $0207
  LDA.b #$04
  STA.w $0200
  RTS
}
; ----------------------
Menu_ItemScreen:
{
  JSR Menu_CheckHScroll

  INC $0207
  LDA.w $0202 : BEQ .no_inputs

  ASL : TAY 
  LDA.b $F4
  LSR : BCS .move_right
  LSR : BCS .move_left
  LSR : BCS .move_down
  LSR : BCS .move_up
  BRA .no_inputs

.move_right
  JSR Menu_DeleteCursor
  JSR Menu_FindNextItem
  BRA .draw_cursor
  
.move_left
  JSR Menu_DeleteCursor
  JSR Menu_FindPrevItem
  BRA .draw_cursor

.move_down 
  JSR Menu_DeleteCursor
  JSR Menu_FindNextDownItem
  BRA .draw_cursor

.move_up 
  JSR Menu_DeleteCursor
  JSR Menu_FindNextUpItem
  BRA .draw_cursor

.draw_cursor
  LDA.b #$20 : STA.w $012F ; cursor move sound effect 
.no_inputs

  SEP #$30
  LDA.w $0202
  ASL : TAY
  REP #$10
  LDX.w Menu_ItemCursorPositions-2, Y

  LDA.b #$20 : BIT.w $0207

  REP #$20

  BEQ .no_delete 

  LDA.w #$20F5
  STA.w $1108, X
  STA.w $1148, X
  STA.w $114E, X 
  STA.w $110E, X 
  STA.w $11C8, X 
  STA.w $1188, X
  STA.w $118E, X 
  STA.w $11CE, X 
  BRA .done


.no_delete 
  LDA.w #$3060 : STA.w $1108, X ; corner 
  LDA.w #$3070 : STA.w $1148, X

  LDA.w #$7060 : STA.w $110E, X ; corner 
  LDA.w #$7070 : STA.w $114E, X

  LDA.w #$3070 : STA.w $1188, X 
  LDA.w #$B060 : STA.w $11C8, X ; corner 

  LDA.w #$7070 : STA.w $118E, X 
  LDA.w #$F060 : STA.w $11CE, X ; corner 

.done
  JSR Menu_DrawItemName
  SEP #$20
  LDA.b #$22 : STA.w $0116
  LDA.b #$01 : STA.b $17

  RTS
}

; ===================================================================================
; 05 MENU SCROLL TO 

Menu_ScrollTo:
{
  SEP #$20 
  JSR Menu_ScrollHorizontal
  BCC .not_done

  INC.w $0200

.not_done
  RTS
}

; ===================================================================================
; 06 MENU STATS SCREEN 

Menu_StatsScreen:
{
  JSR Menu_CheckHScroll
  RTS
}

; =====================================

Menu_CheckHScroll:
{
  LDA.b $F4
  BIT.b #$10 : BNE .leave_menu
  LDA.b $F6
  BIT.b #$20 : BNE .left
  BIT.b #$10 : BNE .right

  RTS

.left
  REP #$20
  LDA.w #$FFF8
  BRA .merge

.right
  REP #$20
  LDA.w #$0008

.merge 
  STA.w MenuScrollHDirection

  SEP #$30
  INC.w $0200
  LDA.b #$06 : STA.w $012F
  RTS

.leave_menu
  LDA.b #$08
  STA.w $0200
  RTS
}

; =====================================

Menu_ScrollHorizontal:
{
  REP #$21                    ; set A to 16 bit, clear carry flag

  LDA.w $E4                   ; BG3 Horizontal Scroll Value
  ADC.w MenuScrollHDirection  ; Direction set by Menu_CheckHScroll
  AND.w #$01FF                
  STA.b $E4   
  AND.w #$00FF
  BNE .loop

  SEC
  RTS

.loop
  CLC 
  RTS
}

; ===================================================================================
; 07 MENU SCROLL FROM 

Menu_ScrollFrom:
{
  JSR Menu_ScrollHorizontal
  BCC .not_done

  JMP Menu_InitItemScreen

.not_done
  RTS
}

; ===================================================================================
; 08 MENU SCROLL UP 

Menu_ScrollUp:
{ 
  LDA.b #$12 : STA.w $012F ; play menu exit sound effect 
  SEP #$10
  REP #$20

  LDX.w MenuScrollLevelV
  LDA.w Menu_Scroll, X 
  STA.b $EA
  BNE .loop
  STZ.b $E4

  INC.w $0200
  RTS

.loop
  DEX : DEX : STX.w MenuScrollLevelV

  JSL Menu_UpdateHudItem
  RTS
}

; ===================================================================================
; incomplete :(
Menu_CheckBottle:
{
  ;; 7F5021 7ED101
  STZ.w $7F5021
  LDA.w $0202 : CMP.b #$15 : BNE .not_shovel 
  LDA.b #$0001 : STA.w $7F5021

.not_shovel

  LDA.w $0202 : CMP.b #$19 : BNE .not_flute 
  LDA.w $7EF34C : JML $70A31D

.not_flute 

  RTS 
}

; ===================================================================================
; 09 MENU EXIT 

Menu_Exit:
{
  ;set $0303 by using $0202 to index table on exit
  JSR Menu_CheckBottle
  LDY.w $0202 : BEQ .no_item
  DEY 
  LDA.w Menu_ItemIndex, Y
  STA.w $0303

.no_item
  REP #$20
  STZ $0200
  ;;STZ $11
  LDA.w $010C
  STA.b $10

  LDX.b #$3E
  .loop 

      LDA.l $7EC300, X : STA.l $7EC500, X
      DEX : DEX 
  BPL .loop

  INC.b $15
  INC.b $16

  RTS
}
; ===================================================================================
; XX MENU HIJACK HUD 

HudItems:
  dw BowsGFX
  dw BoomsGFX
  dw HookGFX
  dw BombsGFX
  dw DekuMaskGFX
  dw BottlesGFX
  dw Fire_rodGFX
  dw Ice_rodGFX
  dw LampGFX
  dw HammerGFX
  dw GoronMaskGFX
  dw BottlesGFX
  dw SomariaGFX
  dw ByrnaGFX
  dw BookGFX
  dw JumpFeatherGFX
  dw BunnyHoodGFX 
  dw BottlesGFX
  dw OcarinaGFX
  dw MirrorGFX
  dw ShovelGFX
  dw PowderGFX
  dw StoneMaskGFX
  dw BottlesGFX

  ; LDA.w $0202
  ; ASL : TAX
  ; LDY.w HudItems-2, X

Menu_UpdateHudItem:
{
  PHB
  PHK
  PLB
  ; print pc
  ; SEP #$30
  ; LDA.b #$7E : STA.b $0C ; set the indirect bank 
  ; REP #$30

  ; LDA.w $0202
  ; ASL : TAX
  ; LDY.w HudItems-2, X
  ; STY.b $00 

  ; LDY.w $0202
  ; LDX.w Menu_AddressIndex-1, Y
  ; LDA.l $7EF300, X
  ; STA.w $08

  ; LDA.b [$08]
  ; ADC.b $00
  ; TAY 

  REP #$30
  LDA.w $0202
  ASL : TAX
  LDY.w HudItems-2, X

  LDA.w $0000,Y : STA.l $7EC778
  LDA.w $0002,Y : STA.l $7EC77A
  LDA.w $0004,Y : STA.l $7EC7B8
  LDA.w $0006,Y : STA.l $7EC7BA
  SEP #$30

  PLB
  RTL
}

; ===================================================================================

Menu_DrawBackground:
{
  REP #$30
  LDX.w #$FE ; $1700-17FF 

.loop
  LDA.w Menu_Tilemap, X
  STA.w $1000, X
  LDA.w Menu_Tilemap+$100, X
  STA.w $1100, X
  LDA.w Menu_Tilemap+$200, X
  STA.w $1200, X
  LDA.w Menu_Tilemap+$300, X
  STA.w $1300, X
  LDA.w Menu_Tilemap+$400, X
  STA.w $1400, X
  LDA.w Menu_Tilemap+$500, X
  STA.w $1500, X
  LDA.w Menu_Tilemap+$600, X
  STA.w $1600, X
  LDA.w Menu_Tilemap+$700, X
  STA.w $1700, X

  DEX : DEX
  BPL .loop

  RTS
}

;===============================================================================

incsrc "lw_map_names.asm"