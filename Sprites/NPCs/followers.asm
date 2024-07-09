; =========================================================
; Old Man Follower Sprite 
; 

POSY            = $7E0020
POSYH           = $7E0021
POSX            = $7E0022
POSXH           = $7E0023

; 20 steps of animation and movement caching for followers
FOLLOWERYL      = $7E1A00
FOLLOWERYH      = $7E1A14

FOLLOWERXL      = $7E1A28
FOLLOWERXH      = $7E1A3C

FOLLOWERZ       = $7E1A50
FOLLOWERLAYER   = $7E1A64

; Follower head/body gfx offsets
FLWHO           = $7E0AE8
FLWHOH          = $7E0AE9
FLWBO           = $7E0AEA
FLWBOH          = $7E0AEB

; Follower head
FLWHGFXT        = $7E0AEC
FLWHGFXTH       = $7E0AED
FLWHGFXB        = $7E0AEE
FLWHGFXBH       = $7E0AEF

; Follower body
FLWBGFXT        = $7E0AF0
FLWBGFXTH       = $7E0AF1
FLWBGFXB        = $7E0AF2
FLWBGFXBH       = $7E0AF3

; Index from 0x00 to 0x13 for follower animation step index. Used for reading data.
FLWANIMIR       = $7E02CF

; Cache of follower properties
FOLLOWCYL       = $7EF3CD
FOLLOWCYH       = $7EF3CE
FOLLOWCXL       = $7EF3CF
FOLLOWCXH       = $7EF3D0

LoadFollowerGraphics = $00D423

; org $099F99
; #Follower_AIVectors:
;   #_099F99: dw Follower_BasicMover   ; 0x01 - Zelda (Impa)
;   #_099F9B: dw Follower_OldMan       ; 0x02 - Old man that stops following you
;   #_099F9D: dw Follower_OldManUnused ; 0x03 - Unused old man
;   #_099F9F: dw Follower_OldMan       ; 0x04 - Normal old man
;   #_099FA1: dw Follower_Telepathy    ; 0x05 - Zelda rescue telepathy
;   #_099FA3: dw Follower_BasicMover   ; 0x06 - Blind maiden
;   #_099FA5: dw Follower_BasicMover   ; 0x07 - Frogsmith
;   #_099FA7: dw Follower_BasicMover   ; 0x08 - Smithy
;   #_099FA9: dw Follower_BasicMover   ; 0x09 - Locksmith
;   #_099FAB: dw Follower_BasicMover   ; 0x0A - Kiki
;   #_099FAD: dw Follower_OldManUnused ; 0x0B - Minecart Follower
;   #_099FAF: dw Follower_BasicMover   ; 0x0C - Purple chest
;   #_099FB1: dw Follower_BasicMover   ; 0x0D - Super bomb
;   #_099FB3: dw Follower_Telepathy    ; 0x0E - Master Sword telepathy

; ---------------------------------------------------------

; Old man sprite wont spawn in his home room 
; if you have the follower 
OldMan_ExpandedPrep:
{
  ; ROOM 00E4
  LDA.l $7EF3CC : CMP.b #$04 : BEQ .not_home
    LDA.b $A0 : CMP.b #$E4 : BNE .not_home
      CLC 
      RTL
  .not_home
  SEC
  RTL
}

pushpc 

; Old man gives link the "shovel" 
; Now the goldstar hookshot upgrade
org $1EE9FF
  LDY.b #$13 ; ITEMGET 1A
  STZ.w $02E9

; FindEntrance
org $1BBD3C
  CMP.w #$04

; Underworld_LoadEntrance
org $02D98B
  CMP.w #$02

org $1EE8F1
SpritePrep_OldMan:
{
  PHB
  PHK
  PLB
  JSR .main
  PLB
  RTL

  .main
  INC.w $0BA0,X

  
  ; LDA.b $A0 : CMP.b #$E4 ; ROOM 00E4
  JSL OldMan_ExpandedPrep : BCS .not_home
    LDA.b #$02 : STA.w $0E80,X
    RTS

  .not_home
  LDA.l $7EF3CC : CMP.b #$00 : BNE .dont_spawn

  ; Check for lv2 hookshot instead of mirror
  LDA.l $7EF342 : CMP.b #$02 : BNE .spawn

  STZ.w $0DD0,X

  .spawn
  ; FOLLOWER 04
  LDA.b #$04 : STA.l $7EF3CC

  PHX
  JSL LoadFollowerGraphics
  PLX

  LDA.b #$00
  STA.l $7EF3CC

  RTS
  .dont_spawn
  STZ.w $0DD0,X

  PHX
  JSL LoadFollowerGraphics
  PLX

  RTS
}

org $09A4C8
Follower_HandleTriggerData:
{
  .room_id
  #_09A4C8: dw $00D1 ; ROOM 00D1 - old man cave
  #_09A4CA: dw $00FE ; ROOM 0061 - castle lobby
  #_09A4CC: dw $00FD ; ROOM 0051 - castle throne room
  #_09A4CE: dw $00FD ; ROOM 0002 - pre-sanc
  #_09A4D0: dw $00DB ; ROOM 00DB - TT entrance
  #_09A4D2: dw $00AB ; ROOM 00AB - to TT attic
  #_09A4D4: dw $0022 ; ROOM 0022 - sewer rats

  .coordinates_uw
  #_09A4D6: dw $1A78, $0233, $0001, $0099, $0004 ; Old man - MESSAGE 0099
  #_09A4E0: dw $1BC0, $0378, $0002, $009A, $0004 ; Old man - MESSAGE 009A
  #_09A4EA: dw $1A78, $0378, $0004, $009B, $0004 ; Old man - MESSAGE 009B

  #_09A4F4: dw $1FF8, $039D, $0001, $0021, $0001 ; Zelda - MESSAGE 0021
  #_09A4FE: dw $1FF8, $039D, $0002, $0021, $0001 ; Zelda - MESSAGE 0021
  #_09A508: dw $1FF8, $0238, $0004, $0021, $0001 ; Zelda - MESSAGE 0021

  #_09A512: dw $1D78, $1F7F, $0001, $0022, $0001 ; Zelda - MESSAGE 0022

  #_09A51C: dw $1D78, $1F7F, $0001, $0023, $0001 ; Zelda - MESSAGE 0023
  #_09A526: dw $1D78, $1F7F, $0002, $002A, $0001 ; Zelda - MESSAGE 002A

  #_09A530: dw $1BD8, $16FC, $0001, $0124, $0006 ; Blind maiden - MESSAGE 0124

  #_09A53A: dw $1520, $167C, $0001, $0124, $0006 ; Blind maiden - MESSAGE 0124

  #_09A544: dw $05AC, $04FC, $0001, $0029, $0001 ; Zelda - MESSAGE 0029

  ; ---------------------------------------------------------

  .overworld_id
  #_09A54E: dw $0005 ; OW 05 - West DM (Updated)
  #_09A550: dw $002F ; OW 2F - Tail Palace
  #_09A552: dw $0000 ; OW 00 - Lost woods

  .coordinates_ow
  #_09A554: dw $0178, $0A63, $0001, $009D, $0004 ; Old man - MESSAGE 009D
  ;              Y      X
  #_09A55E: dw $0A88, $0F41, $0000, $FFFF, $000A ; Kiki
  #_09A568: dw $0B37, $0F40, $0001, $FFFF, $000A ; Kiki
  #_09A572: dw $0A62, $0E5B, $0002, $FFFF, $000A ; Kiki

  #_09A57C: dw $00E8, $0090, $0000, $0028, $000E ; MS telepathy - MESSAGE 0028

  ; ---------------------------------------------------------

  .room_boundaries_check
  #_09A586: dw $0000, $001E, $003C, $0046
  #_09A58E: dw $005A, $0064, $006E, $0078

  .ow_boundaries_check
  #_09A596: dw $0000, $000A, $0028, $0032
}

pullpc


FollowerDraw_CalculateOAMCoords:
{
  REP #$20
  LDA.b $02 : STA.b ($90),Y
  INY

  CLC : ADC.w #$0080 : CMP.w #$0180 : BCS .off_screen
    LDA.b $02 : AND.w #$0100 : STA.b $74
    LDA.b $00 : STA.b ($90),Y

    CLC : ADC.w #$0010 : CMP.w #$0100 : BCC .on_screen

  .off_screen:
  LDA.w #$00F0 : STA.b ($90),Y

  .on_screen:
  SEP #$20
  INY
  RTS
}

MinecartFollower_Top:
{
    SEP #$30
    JSR FollowerDraw_CalculateOAMCoords
    LDA #$08
    JSL OAM_AllocateFromRegionB

    LDA $02CF : TAY 
    LDA .start_index, Y : STA $06
    
    PHX
    LDX .nbr_of_tiles, Y ; amount of tiles -1
    LDY.b #$00
  .nextTile

    PHX                 ; Save current Tile index
    TXA : CLC : ADC $06 ; Add Animation Index Offset
    PHA                 ; Keep the value with animation index offset
    ASL A : TAX

    REP #$20

    LDA $02 : CLC : ADC .x_offsets, X : STA ($90), Y
    AND.w #$0100 : STA $0E
    INY
    LDA $00 : CLC : ADC .y_offsets, X : STA ($90), Y
    CLC   : ADC #$0010 : CMP.w #$0100
    SEP   #$20
    BCC   .on_screen_y

    LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
    STA   $0E
  .on_screen_y

    PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
    INY
    LDA .chr, X : STA ($90), Y
    INY
    LDA .properties, X : STA ($90), Y

    PHY 
        
    TYA : LSR #2 : TAY
        
    LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
        
    PLY : INY
    PLX : DEX : BPL .nextTile

    PLX

    RTS

  .start_index:
      db $00, $02, $04, $06
  .nbr_of_tiles:
      db 1, 1, 1, 1
  .x_offsets:
      dw -8, 8
      dw -8, 8
      dw -8, 8
      dw -8, 8
  .y_offsets:
      dw -12, -12
      dw -11, -11
      dw -8, -8
      dw -7, -7
  .chr:
      db $40, $40
      db $40, $40
      db $42, $42
      db $42, $42
  .properties:
      db $3D, $7D
      db $3D, $7D
      db $3D, $7D
      db $3D, $7D
}

MinecartFollower_Bottom:
{
    SEP #$30

    JSR FollowerDraw_CalculateOAMCoords
    LDA #$08
    JSL OAM_AllocateFromRegionC
    LDA $02CF : TAY 
    LDA .start_index, Y : STA $06

    PHX
    LDX .nbr_of_tiles, Y ; amount of tiles -1
    LDY.b #$00
  .nextTile

    PHX ; Save current Tile Index?
    TXA : CLC : ADC $06 ; Add Animation Index Offset
    PHA ; Keep the value with animation index offset?
    ASL A : TAX

    REP #$20

    LDA $02 : CLC : ADC .x_offsets, X : STA ($90), Y
    AND.w #$0100 : STA $0E
    INY
    LDA $00 : CLC : ADC .y_offsets, X : STA ($90), Y
    CLC   : ADC #$0010 : CMP.w #$0100
    SEP   #$20
    BCC   .on_screen_y

    LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
    STA   $0E
  .on_screen_y

    PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
    INY
    LDA .chr, X : STA ($90), Y
    INY
    LDA .properties, X : STA ($90), Y

    PHY 
        
    TYA : LSR #2 : TAY
        
    LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
        
    PLY : INY
    PLX : DEX : BPL .nextTile

    PLX

    RTS

  .start_index:
      db $00, $02, $04, $06
  .nbr_of_tiles:
      db 1, 1, 1, 1
  .x_offsets:
      dw -8, 8
      dw -8, 8
      dw -8, 8
      dw -8, 8
  .y_offsets:
      dw 4, 4
      dw 5, 5
      dw 8, 8
      dw 9, 9
  .chr:
      db $60, $60
      db $60, $60
      db $62, $62
      db $62, $62
  .properties:
      db $3D, $7D
      db $3D, $7D
      db $3D, $7D
      db $3D, $7D
}

; Minecart Follower Main Routine and Draw
DrawMinecartFollower:
{
  JSL $099EFC ; Follower_Initialize

  LDX $012B 
  LDA .direction_to_anim, X
  STA $02CF

  JSR FollowerDraw_CachePosition
  JSR MinecartFollower_Top
  JSR MinecartFollower_Bottom

  LDA.b $11 : BNE .dont_spawn
    LDA !LinkInCart : BEQ .dont_spawn
      LDA.b #$A3 
      JSL Sprite_SpawnDynamically
      TYX
      JSL Sprite_SetSpawnedCoords
      LDA.w !MinecartDirection : CMP.b #$00 : BEQ .vert_adjust
                                 CMP.b #$02 : BEQ .vert_adjust
        LDA POSY : CLC : ADC #$08 : STA.w SprY, X
        LDA POSX : STA.w SprX, X
        JMP .finish_prep
      .vert_adjust
        LDA POSY : STA.w SprY, X
        LDA POSX : CLC : ADC #$02 : STA.w SprX, X
      .finish_prep
      LDA POSYH : STA.w SprYH, X
      LDA POSXH : STA.w SprXH, X
      LDA.w !MinecartDirection : CLC : ADC.b #$03 : STA.w SprSubtype, X

      LDA .direction_to_anim, X : STA $0D90, X
      JSL Sprite_Minecart_Prep
      LDA.b #$00 : STA.l $7EF3CC
  .dont_spawn
  RTS

.direction_to_anim
  db $02, $00, $02, $00
}

FollowerDraw_CachePosition:
{
  LDX.b #$00

  LDA.w $1A00, X : STA.b $00
  LDA.w $1A14, X : STA.b $01
  LDA.w $1A28, X : STA.b $02
  LDA.w $1A3C, X : STA.b $03
  LDA.w $1A64, X : STA.b $05

  ; -------------------------
  #_09A95B: AND.b #$20
  #_09A95D: LSR A
  #_09A95E: LSR A
  #_09A95F: TAY

  #_09A960: LDA.b $05
  #_09A962: AND.b #$03
  #_09A964: STA.b $04

  #_09A966: STZ.b $72
  ; Vanilla game would check some priority and collision
  ; variables based on the follower here and manipulate $72
  ; if the player was immobile. 
  
  CLC : ADC $04 : STA $04
  TYA : CLC : ADC $04 : STA $04
  ; -------------------------
  
  REP #$20
  LDA $0FB3 : AND.w #$00FF : ASL A : TAY
  LDA $20 : CMP $00 : BEQ .check_priority_for_region
                      BCS .use_region_b
      BRA .use_region_a
  .check_priority_for_region
    LDA $05 : AND.w #$0003 : BNE .use_region_b
    .use_region_a
      LDA.w .oam_region_offsets_a, Y
      BRA   .set_region
    .use_region_b
      LDA.w .oam_region_offsets_b, Y

  .set_region

  PHA
  
  LSR #2 : CLC : ADC.w #$0A20 : STA $92
  PLA    : CLC : ADC.w #$0800 : STA $90
  
  LDA $00 : SEC : SBC $E8 : STA $06
  LDA $02 : SEC : SBC $E2 : STA $08
  
  SEP #$20

  #_09AA85: LDA.w $02D7
  #_09AA88: INC A
  #_09AA89: CMP.b #$03
  #_09AA8B: BNE .set_repri

  #_09AA8D: LDA.b #$00

  .set_repri
  #_09AA8F: STA.w $02D7

  LDA $02D7 : ASL #2 : STA $05
  TXA : CLC : ADC $05 : TAX
  
  REP #$20
  
  LDA $06 : CLC : ADC.w #$0010 : STA $00
  LDA $08 : STA $02
  STZ $74
  
  SEP #$20

  RTS

  .oam_region_offsets_a
    dw $0170
    dw $00C0

  .oam_region_offsets_b
    dw $01C0
    dw $0110
}


CheckForMinecartFollowerDraw:
{
  PHB : PHK : PLB
  LDA.l $7EF3CC : CMP.b #$0B : BNE .not_minecart
    JSR DrawMinecartFollower
    
  .not_minecart
    ; LDA.b #$10
    ; STA.b $5E
    PLB 
    RTL
}

CheckForFollowerInterroomTransition:
{
  PHB : PHK : PLB
  LDA.w !LinkInCart : BEQ .not_in_cart
    LDA.b #$0B : STA $7EF3CC
  .not_in_cart
  PLB
  JSL $01873A ; Underworld_LoadRoom
  RTL
}

CheckForFollowerIntraroomTransition:
{
  STA.l $7EC007
  PHB : PHK : PLB
  LDA.w !LinkInCart : BEQ .not_in_cart
    LDA.b #$0B : STA $7EF3CC
  .not_in_cart
  PLB
  RTL
}

pushpc

; Follower_OldManUnused
org $09A41F
  JSL CheckForMinecartFollowerDraw
  RTS

; Module07_02_01_LoadNextRoom
org $028A5B
  JSL CheckForFollowerInterroomTransition

org $0289BF
  JSL CheckForFollowerIntraroomTransition

pullpc