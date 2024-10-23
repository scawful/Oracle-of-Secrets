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
    dw Menu_RingBox            ; 09
    dw Menu_Exit               ; 0A
    dw Menu_InitiateScrollDown ; 0B
    dw Menu_MagicBag           ; 0C
    dw Menu_SongMenu           ; 0D
}

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
    LDA $3A : AND.b #$80 : STA $3A
    LDA $50 : AND.b #$FE : STA $50
    LDA.b #$80 : STA $44 : STA $45
  BRA +
  .wolf_shovel
    LDA.b $3A : AND.b #$80 : STA.b $3A
    LDA.b $50 : AND.b #$FE : STA.b $50
  +
  STZ.w $030D ; SWEAT
  STZ.w $0300 ; ITEMSTEP
  STZ.w $037A ; USEY2
  STZ.w $0301 ; USEY1
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
  JSR Menu_DrawMagicRings
  JSR Menu_DrawPlaytimeLabel

  JSR Menu_DrawHeartPieces
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
  LDA.w $0202 : BEQ .do_no_input
    ; Scroll through joypad 1 inputs
    ASL : TAY : LDA.b $F4
    LSR : BCS .move_right
    LSR : BCS .move_left
    LSR : BCS .move_down
    LSR : BCS .move_up

    LDA.w $0202 : CMP.b #$05 : BNE +
      LDA.b $F6 : BIT.b #$80 : BEQ +
        STZ.w $020B
        LDA.b #$0C : STA.w $0200 ; Magic Bag
    +
    LDA.w $0202 : CMP.b #$0D : BNE ++
      LDA.b $F6 : BIT.b #$80 : BEQ ++
        LDA.b #$0D : STA.w $0200
          JSR Menu_DeleteCursor
          JSR Menu_DrawSongMenu
          SEP #$30
          JMP .exit
    ++

    LDA.b $F6 : BIT.b #$40 : BEQ +++
      JSR Menu_DeleteCursor
      JSR Menu_DrawRingBox
      STZ.w $020B
      LDA.b #$09 : STA.w $0200 ; Ring Box
      JMP .exit
    +++
  .do_no_input
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
  JSR Menu_DrawCursor

  JSR Menu_DrawItemName
  SEP #$20
  .exit
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
    LDA.w #$000A : STA.w $0200
    RTS

  .notDoneScrolling
  DEX : DEX : STX.w MenuScrollLevelV
  RTS
}

; =========================================================
; CHECK BOTTLE

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
  RTS
}

; =========================================================
; 0A MENU EXIT

Menu_Exit:
{
  JSL LinkState_ResetMaskAnimated
  JSR Menu_CheckBottle
  REP #$20

  ; reset submodule
  STZ $0200

  ; go back to the submodule we came from
  LDA.w $010C : STA.b $10

  ; set $0303 by using $0202 to index table on exit
  ; set $0304 to prevent item + 1 animation exploits
  LDX $0202
  LDA.w Menu_ItemIndex, X : STA $0303 : STA.w $0304

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

; =========================================================
; 0C MENU MAGIC BAG

Menu_MagicBag:
{
  JSR Menu_DrawMagicBag
  JSR Menu_DrawMagicItems
  SEP #$30

  INC $0207
  LDA.b $F4
  LSR : BCS .move_right
  LSR : BCS .move_left
  LSR : BCS .move_down
  LSR : BCS .move_up
  BRA .continue

  .move_up
  .move_right
    REP #$30
    LDX.w Menu_MagicBagCursorPositions-2, Y
    JSR Menu_DeleteCursor_AltEntry
    INC.w $020B
    LDA.w $020B : CMP.b #$06 : BCS .zero
    BRA .continue

  .move_down
  .move_left
    REP #$30
    LDX.w Menu_MagicBagCursorPositions-2, Y
    JSR Menu_DeleteCursor_AltEntry
    LDA.w $020B : CMP.b #$00 : BEQ .continue
    DEC.w $020B
    BRA .continue
  .zero
  STZ.w $020B
  .continue
  JSR DrawCollectibleNamesAndCount
  LDA.w $020B
  ASL : TAY
  REP #$10
  LDX.w Menu_MagicBagCursorPositions, Y
  JSR Menu_DrawCursor
  JSR Submenu_Return

  LDA.b #$22 : STA.w $0116
  LDA.b #$01 : STA.b $17

  RTS
}

Menu_MagicBagCursorPositions:
  dw menu_offset(8,6)   ; banana
  dw menu_offset(8,10)  ; pineapple
  dw menu_offset(8,14)  ; goron rock meat
  dw menu_offset(12,6)  ; seashells
  dw menu_offset(12,10) ; honeycombs
  dw menu_offset(12,14) ; deku sticks

; =========================================================
; 0D MENU SONG MENU

Menu_SongMenu:
{
  REP #$30
  JSR Menu_DrawMusicNotes

  INC $0207
  LDA.w CurrentSong : BEQ +
  ASL : TAY
  LDA.b $F4
  LSR : BCS .move_right
  LSR : BCS .move_left
  LSR : BCS .move_down
  LSR : BCS .move_up
  +
  JMP .continue

  .move_right
  .move_up
    REP   #$30
    LDX.w Menu_SongIconCursorPositions-2, Y
    JSR Menu_DeleteCursor_AltEntry
    LDA.w CurrentSong : CMP.b #$04 : BEQ .reset
      INC.w CurrentSong
      LDA.w CurrentSong
      PHA
      LDA $7EF34C : CMP.b #$01 : BEQ .max_1
                    CMP.b #$02 : BEQ .max_2
                    CMP.b #$03 : BEQ .max_3
        PLA
        CMP.b #$05 : BCS .wrap_to_min
        JMP .continue
      .max_1
      PLA : CMP.b #$02 : BCS .wrap_to_min
      .max_2
      PLA : CMP.b #$03 : BCS .wrap_to_min
      JMP .continue
      .max_3
      PLA : CMP.b #$04 : BCS .wrap_to_min
      JMP .continue
      .wrap_to_max
      LDA $7EF34C : CMP.b #$01 : BEQ .wrap_to_min
                    CMP.b #$02 : BEQ .set_max_to_2
                    CMP.b #$03 : BEQ .set_max_to_3
      LDA #$04 : STA.w CurrentSong : JMP .continue

      .set_max_to_3
      LDA #$03 : STA.w CurrentSong : JMP .continue

      .set_max_to_2
      LDA #$02 : STA.w CurrentSong : JMP .continue

      .wrap_to_min
      LDA #$01 : STA.w CurrentSong
      BRA .continue

  .move_left
  .move_down
    REP   #$30
    LDX.w Menu_SongIconCursorPositions-2, Y
    JSR Menu_DeleteCursor_AltEntry
    LDA.w CurrentSong : CMP.b #$01 : BEQ .reset
      DEC.w CurrentSong
      LDA.w CurrentSong
      CMP #$00 : BEQ .wrap_to_max
      BRA .continue
    .reset
    LDA #$01 : STA.w CurrentSong

  .continue

  JSR Menu_DrawItemName
  SEP #$30
  LDA.w CurrentSong
  ASL : TAY
  REP #$10
  LDX.w Menu_SongIconCursorPositions-2, Y
  JSR Menu_DrawCursor
  JSR Submenu_Return
  SEP #$20

  LDA.b #$22 : STA.w $0116
  LDA.b #$01 : STA.b $17

  RTS
}

Menu_SongIconCursorPositions:
  dw menu_offset(8,4)
  dw menu_offset(8,8)
  dw menu_offset(8,12)
  dw menu_offset(8,16)

; =========================================================
; 09 MENU RING BOX

Menu_RingBox:
{
  JSR Menu_DrawRingBox
  JSR Menu_DrawMagicRingsInBox
  INC $0207

  LDA.b $F4
  LSR : BCS .move_right
  LSR : BCS .move_left
  LSR : BCS .move_down
  LSR : BCS .move_up
  BRA .continue

  .move_up
  .move_right
    REP   #$30
    LDX.w Menu_RingIconCursorPositions-2, Y
    JSR Menu_DeleteCursor_AltEntry
    INC.w $020B
    LDA.w $020B : CMP.b #$06 : BCS .zero
    BRA .continue
  .move_left
  .move_down
    REP   #$30
    LDX.w Menu_RingIconCursorPositions-2, Y
    JSR Menu_DeleteCursor_AltEntry
    LDA.w $020B : CMP.b #$00 : BEQ .continue
    DEC.w $020B
    BRA .continue
  .zero
    STZ.w $020B
  .continue

  JSR DrawMagicRingNames
  LDA.w $020B
  ASL : TAY
  REP #$10
  LDX.w Menu_RingIconCursorPositions, Y
  JSR Menu_DrawCursor
  JSR RingMenu_Controls
  SEP #$20

  LDA.b #$22 : STA.w $0116
  LDA.b #$01 : STA.b $17

  RTS
}

Menu_RingIconCursorPositions:
  dw menu_offset(8,6)
  dw menu_offset(8,10)
  dw menu_offset(8,14)
  dw menu_offset(12,6)
  dw menu_offset(12,10)
  dw menu_offset(12,14)

RingMenu_StoreRingToSlotStack:
{
  ; TODO: Check how many ring slots we currently have

  ; Check if the ring is already in a slot
  STA.b $00
  LDA.b $00 : CMP.l RingSlot1 : BEQ .return
  LDA.b $00 : CMP.l RingSlot2 : BEQ .return
  LDA.b $00 : CMP.l RingSlot3 : BEQ .return
  PHA
  ; Check the SRAM for an available ring slot
  ; If none is available we shift the stack
  ; $7EF38C-7EF38E (Size 03)

  LDA.l RingSlot1 : BEQ .slot1_available
  LDA.l RingSlot2 : BEQ .slot2_available
  LDA.l RingSlot3 : BEQ .slot3_available

  ; Shift the stack
  LDA.l RingSlot2 : STA.l RingSlot1
  LDA.l RingSlot3 : STA.l RingSlot2
  .slot3_available
  PLA : STA.l RingSlot3
  .return
  RTS

  .slot1_available
  PLA : STA.l RingSlot1
  RTS
  .slot2_available
  PLA : STA.l RingSlot2
  RTS
}

RingMenu_Controls:
{
  ; Load the current ring selected (0-5) into A
  REP #$30
  LDA.w $020B
  AND.w #$00FF
  SEP #$30
  ; Set the current ring to the cursor position
  TAY                     ; Transfer A to Y for indexing
  LDA.b $F6 : BIT.b #$80 : BEQ +  ; Check if the confirm button is pressed
    LDA .rings, Y         ; Load the ring bitmask
    AND.l MAGICRINGS      ; Check if the ring is owned
    BEQ +                 ; If not, skip setting the ring
      INY #2
      TYA                 ; Transfer Y to A
      JSR RingMenu_StoreRingToSlotStack
  +

  ; Return to item menu if player presses X
  LDA.b $F6 : BIT.b #$40 : BEQ +
    LDA.b #$01 : STA.w $0200
  +

  ; Close the menu if the player presses start
  LDA.b $F4 : BIT.b #$10 : BEQ +
    LDA.b #$08 : STA.w $0200
  +
  RTS

  .rings
    db $20, $10, $08, $04, $02, $01
}

Submenu_Return:
{
  ; Return to the item menu if they press A
  LDA.b $F6 : BIT.b #$80 : BEQ +
    LDA.b #$02 : STA.w $0200
  +

  ; Close the menu if the player presses start
  LDA.b $F4 : BIT.b #$10 : BEQ +
    LDA.b #$08 : STA.w $0200
  +
  RTS
}

menu_frame: incbin "tilemaps/menu_frame.tilemap"
quest_icons: incbin "tilemaps/quest_icons.tilemap"
incsrc "menu_map_names.asm"
print  "End of Menu/menu.asm              ", pc
incsrc "menu_hud.asm"
print  "End of Menu/menu_hud.asm          ", pc

; =========================================================
