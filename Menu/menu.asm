; =========================================================
;       The Legend of Zelda: Oracle of Secrets
;        ------------ Custom Menu ------------
;
;  - Navigate between two menus with L and R
;  - New item layout and draw routines
;  - Detailed quest status screen
;  - Player name, location names
;  - Custom HUD with new magic meter
; =========================================================


pushpc
; update in game hud colors 
org $1BD662 : dw hexto555($814f16), hexto555($552903)
org $1BD66A : dw hexto555($d51d00), hexto555($f9f9f9)
org $1DB672 : dw hexto555($d0a050), hexto555($f9f9f9)
org $1DB67A : dw hexto555($5987e0), hexto555($f9f9f9)
org $1DB682 : dw hexto555($7b7b83), hexto555($bbbbbb)
org $1DB68A : dw hexto555($a58100), hexto555($dfb93f)

; Free ROM in Bank 00
org $0098AB : db $6C
org $0098AC : db $64

; Module RunInterface 0E.01: Item Menu
org $00F877 : db Menu_Entry>>0
org $00F883 : db Menu_Entry>>8
org $00F88F : db Menu_Entry>>16

; NMI_DoUpdates.skip_sprite_updates
; Stored to VMADDR
org $808B6B : LDX.w #$6040

; UpdateEquippedItem
org $8DDFB2 : LDA.l Menu_ItemIndex, X
pullpc

; =========================================================
; Menu Bank 

org $2D8000
incsrc "menu_gfx_table.asm"
incsrc "menu_text.asm"
incsrc "menu_palette.asm"

; =========================================================
; SUBROUTINE TABLE

Menu_Entry:
{
  PHB : PHK : PLB 
  LDA.w $0200 : ASL : TAX
  JSR (.vectors,X)

  SEP #$20
  PLB
  RTL
}
.vectors
  dw Menu_InitGraphics       ; 00
  dw Menu_UploadRight        ; 01
  dw Menu_UploadLeft         ; 02
  dw Menu_ScrollDown         ; 03
  dw Menu_ItemScreen         ; 04
  dw Menu_ScrollTo           ; 05
  dw Menu_StatsScreen        ; 06 
  dw Menu_ScrollFrom         ; 07
  dw Menu_ScrollUp           ; 08
  dw Menu_CheckBottle        ; 09
  dw Menu_Exit               ; 0A
  dw Menu_InitiateScrollDown ; 0B
  dw Menu_MagicBag           ; 0C

; =========================================================
; 00 MENU INIT GRAPHICS 

Menu_InitGraphics:
{
  LDA.w $0780 : STA.w $00
  LDA.w $0202 
  CMP.b #$10 : BNE .not_fishing
    JSL DismissRodFromMenu
  .not_fishing
  CMP.b #$06 : BEQ .bottle
  CMP.b #$0C : BEQ .bottle
  CMP.b #$12 : BEQ .bottle
  CMP.b #$18 : BEQ .bottle
  CMP.b #$15 : BEQ .wolf_shovel
  BRA +
  .bottle
    STZ $030D
    STZ $0300
    STZ $037A
    LDA $3A : AND.b #$80 : STA $3A
    LDA $50 : AND.b #$FE : STA $50
    LDA.b #$80 : STA $44 : STA $45
  BRA + 
  .wolf_shovel
    STZ.w $030D
    STZ.w $0300
    STZ.w $037A
    LDA.b $3A : AND.b #$80 : STA.b $3A
    LDA.b $50 : AND.b #$FE : STA.b $50
  +
  INC $0200
}

; =========================================================
; 01 MENU UPLOAD RIGHT 

incsrc "menu_draw.asm"

Menu_UploadRight:
{
  JSR Menu_DrawBackground
  JSR Menu_DrawQuestItems
  JSR Menu_DrawCharacterName
  JSR Menu_DrawBigKey
  JSR Menu_DrawBigChestKey

  JSR Menu_DrawQuestIcons
  JSR Menu_DrawTriforceIcons
  JSR Menu_DrawPendantIcons

  JSR Menu_DrawPlaytimeLabel

  JSR Menu_DrawHeartPieces
  JSR Menu_DrawMusicNotes
  JSR Menu_DrawQuestStatus
  JSR Menu_DrawAreaNameTXT
  JSR DrawLocationName

  SEP #$30
  LDA.b #$23 : STA.w $0116
  LDA.b #$01 : STA.b $17
  INC.w $0200
  RTS
}

; =========================================================
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
   
; =========================================================
; 03 MENU SCROLL DOWN 

Menu_Scroll:
  dw 0, -3, -5, -7, -10, -12, -15, -20
  dw -28, -40, -50, -60, -75, -90, -100
  dw -125, -150, -175, -190, -200, -210
  dw -220, -225, -230, -232, -234, -238

Menu_ScrollDown:
{
  LDA.b #$11 : STA.w $012F
  SEP #$10
  REP #$20

  LDX.w MenuScrollLevelV
  INX : INX
  LDA.w Menu_Scroll, X 
  STA.b $EA
  CMP.w #$FF12 : BNE .notDoneScrolling
    JMP Menu_InitItemScreen

  .notDoneScrolling
  STX.w MenuScrollLevelV
  RTS
}

; =========================================================
; 04 MENU ITEM SCREEN 

incsrc "menu_select_item.asm"

Menu_ItemScreen:
{
  JSR Menu_CheckHScroll

  INC $0207
  LDA.w $0202 : BEQ .no_inputs
    ; Scroll through joypad 1 inputs 
    ASL : TAY : LDA.b $F4 
    LSR : BCS .move_right
    LSR : BCS .move_left
    LSR : BCS .move_down
    LSR : BCS .move_up

    LDA.w $0202 : CMP.b #$05 : BNE +
      LDA.b $F6 : BIT.b #$80 : BEQ +
        LDA.b #$0C : STA.w $0200 ; Magic Bag
    +
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
    ; Delete cursor
    LDA.w #$20F5
    STA.w $1108, X : STA.w $1148, X
    STA.w $114E, X : STA.w $110E, X 
    STA.w $11C8, X : STA.w $1188, X
    STA.w $118E, X : STA.w $11CE, X 
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

; =========================================================
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

; =========================================================
; 06 MENU STATS SCREEN 

incsrc "menu_scroll.asm"

Menu_StatsScreen:
{
  JSR Menu_CheckHScroll

  RTS
}

; =========================================================
; 07 MENU SCROLL FROM 

Menu_ScrollFrom:
{
  JSR Menu_ScrollHorizontal
  BCC .not_done
    JMP Menu_InitItemScreen

  .not_done
  RTS
}

; =========================================================
; 08 MENU SCROLL UP 

Menu_ScrollUp:
{ 
  SEP #$10
  REP #$20

  LDX.w MenuScrollLevelV
  LDA.w Menu_Scroll, X 
  STA.b $EA : BNE .notDoneScrolling
    STZ.b $E4
    INC.w $0200
    RTS

  .notDoneScrolling
  DEX : DEX : STX.w MenuScrollLevelV
  RTS
}

; =========================================================
; 09 CHECK BOTTLE 

Menu_CheckBottle:
{
  LDA.w $0202 : CMP.b #$06 : BNE .not_first 
  LDA.b #$0001 : JMP .prepare_bottle

.not_first
  LDA.w $0202 : CMP.b #$0C : BNE .not_second
  LDA.b #$0002 : JMP .prepare_bottle

.not_second 
  LDA.w $0202 : CMP.b #$12 : BNE .not_third
  LDA.b #$0003 : JMP .prepare_bottle

.not_third
  LDA.w $0202 : CMP.b #$18 : BNE .not_any
  LDA.b #$0004

.prepare_bottle
  STA.l $7EF34F

.not_any 
  INC.w $0200
  RTS 
}

; =========================================================
; 0A MENU EXIT 

Menu_Exit:
{
  JSL LinkState_ResetMaskAnimated
  REP #$20

  ; reset submodule
  STZ $0200

  ; go back to the submodule we came from 
  LDA.w $010C : STA.b $10

  ; set $0303 by using $0202 to index table on exit
  LDX $0202 
  LDA.w Menu_ItemIndex, X : STA $0303

  LDX.b #$3E
  .loop
    LDA.l $7EC300, X 
    STA.l $7EC500, X
    DEX : DEX 
  BPL .loop

  INC.b $15
  INC.b $16

  RTS
}

; =========================================================
; 0B MENU COPY TO RIGHT

Menu_InitiateScrollDown:
{
  REP #$20

  ; Clear out the whole buffer.
  LDX.b #$FE ; $1700-17FF 

  .loop
    LDA.w #$387F
    STA.w $1000, X
    STA.w $1100, X
    STA.w $1200, X
    STA.w $1300, X
    STA.w $1400, X
    STA.w $1500, X
    STA.w $1600, X
    STA.w $1700, X

    DEX : DEX
  BNE .loop

  ; TODO: The BPL wasn't working so figure out why and 
  ; fix it instead of doing this abomination.
  STA.w $1000
  STA.w $1100
  STA.w $1200
  STA.w $1300
  STA.w $1400
  STA.w $1500
  STA.w $1600
  STA.w $1700

  SEP #$20

  JSL $0DFA58 ; HUD_Rebuild_Long

  ; Draw one frame of the clock so it doesn't just
  ; pop in when scrolling down.
  JSL DrawClockToHudLong

  ; The whole HUD fits on 4 rows so I'm only going to
  ; copy 4 here. Also we start 2 in because thats the
  ; left we need to go.

  LDX.b #$3A
  .loop1
    LDA $7EC702, X : STA $1082, X
  DEX : BNE .loop1

  LDX.b #$3A
  .loop2
    LDA $7EC742, X : STA $10C2, X
  DEX : BNE .loop2

  LDX.b #$3A
  .loop3
    LDA $7EC782, X : STA $1102, X
  DEX : BNE .loop3

  LDX.b #$3A
  .loop4
    LDA $7EC7C2, X : STA $1142, X
  DEX : BNE .loop4

  LDA.b #$24 : STA.w $0116
  LDA.b #$01 : STA.b $17

  LDA.b #$08 : STA.w $0200

  LDA.b #$12 : STA.w $012F ; play menu exit sound effect 

  RTS
}

Menu_MagicBag:
{
  
  JSR Menu_DrawMagicBag
  JSR Menu_DrawMagicItems
  SEP #$30

  LDA.b $F6 : BIT.b #$80 : BEQ +
    LDA.b #$02 : STA.w $0200
  +

  LDA.b #$22 : STA.w $0116
  LDA.b #$01 : STA.b $17

  RTS
}


menu_frame: incbin "tilemaps/menu_frame.tilemap"
quest_icons: incbin "tilemaps/quest_icons.tilemap"
incsrc "menu_map_names.asm"
incsrc "menu_hud.asm"

; =========================================================