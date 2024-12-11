; =========================================================
; Followers

; 20 steps of animation and movement caching for followers
FollowerYL      = $7E1A00
FollowerYH      = $7E1A14

FollowerXL      = $7E1A28
FollowerXH      = $7E1A3C

FollowerZ       = $7E1A50
FollowerLayer   = $7E1A64

; Follower head/body gfx offsets
; Down:0x00 LR:0x80 Up:0x20
FollowerHeadOffset    = $7E0AE8
FollowerHeadOffsetH   = $7E0AE9

; Walk LR:0x60,0x80 0xA0:Down 0xC0:Up
FollowerBodyOffset    = $7E0AEA
FollowerBodyOffsetH   = $7E0AEB

Follower_WatchLink:
{
  JSL Sprite_IsToRightOfPlayer : TYA : BEQ .right
    LDA.b #$40 : STA.w FollowerHeadOffset
    LDA.b #$60 : STA.w FollowerBodyOffset
    RTS
  .right
  LDA.b #$00 : STA.w FollowerHeadOffset
  LDA.b #$A0 : STA.w FollowerBodyOffset
  RTS
}

; Follower head
Flwhgfxt        = $7E0AEC
Flwhgfxth       = $7E0AED
Flwhgfxb        = $7E0AEE
Flwhgfxbh       = $7E0AEF

; Follower body
Flwbgfxt        = $7E0AF0
Flwbgfxth       = $7E0AF1
Flwbgfxb        = $7E0AF2
Flwbgfxbh       = $7E0AF3

; Index from 0x00 to 0x13 for follower animation step index. Used for reading data.
Flwanimir       = $7E02CF

; Flag set when using hookshot with a follower. Forces game mode check.
FollowerHook    = $7E02D0

; Caches FLWANIMIW when hookshotting is finished.
FollowerHookI   = $7E02D1

; Countdown timer preventing followers from being regrabbed after dropping for a brief period.
FLWGRABTIME     = $7E02D2

; Index from 0x00 to 0x13 for follower animation step index. Used for writing data.
FLWANIMIW       = $7E02D3

; Cache of follower properties
FollowCacheYL   = $7EF3CD
FollowCacheYH   = $7EF3CE
FollowCacheXL   = $7EF3CF
FollowCacheXH   = $7EF3D0

LoadFollowerGraphics = $00D423

; org $099F99
; #Follower_AIVectors:
; Follower_BasicMover   ; 0x01 - Zelda (Impa)
; Follower_OldMan       ; 0x02 - Old man that stops following you
; Follower_OldManUnused ; 0x03 - Unused old man
; Follower_OldMan       ; 0x04 - Normal old man
; Follower_Telepathy    ; 0x05 - Zelda rescue telepathy
; Follower_BasicMover   ; 0x06 - Blind maiden
; Follower_BasicMover   ; 0x07 - Frogsmith
; Follower_BasicMover   ; 0x08 - Smithy
; Follower_BasicMover   ; 0x09 - Locksmith (Zora Baby)
; Follower_BasicMover   ; 0x0A - Kiki
; Follower_OldManUnused ; 0x0B - Minecart Follower
; Follower_BasicMover   ; 0x0C - Purple chest
; Follower_BasicMover   ; 0x0D - Super bomb
; Follower_Telepathy    ; 0x0E - Master Sword telepathy

; =========================================================
; Zora Baby Follower Sprite
; Uses Sprite 0x39 Locksmith in Bank06

ZoraBaby_RevertToSprite:
{
  PHA

  LDA.b #$39 : JSL Sprite_SpawnDynamically

  PLA

  PHX
  TAX
  LDA.w $1A64, X : AND.b #$03 : STA.w SprMiscE,Y : STA.w SprMiscC,Y
  LDA.w $1A00, X : CLC : ADC.b #$02 : STA.w SprY,Y
  LDA.w $1A14, X : ADC.b #$00 : STA.w SprYH,Y
  LDA.w $1A28, X : CLC : ADC.b #$10 : STA.w SprX,Y
  LDA.w $1A3C, X : ADC.b #$00 : STA.w SprXH,Y
  LDA.b $EE : STA.w $0F20,Y
  LDA.b #$01 : STA.w SprBulletproof,Y : STA.w $0E80,Y
  LDA.b #$04 : STA.w SprAction, Y
  LDA.b #$FF : STA.w SprTimerB, Y
  PLX

  LDA.b #$00 : STA.l $7EF3CC

  STZ.b $5E

  RTS
}

CheckForZoraBabyTransitionToSprite:
{
  LDA.l $7EF3CC : CMP.b #$09 : BNE .not_zora
    ; If we are standing on a star tile
    LDA.w $0114 : CMP.b #$3B : BNE +
      LDA.b #$00
      JSR ZoraBaby_RevertToSprite
    +

    ; If we are outdoors, clear the follower
    LDA.b $1B : BNE +
      LDA.b #$00 : STA.l $7EF3CC
    +
  .not_zora
  LDX.b $10
  LDY.b $11
  RTL
}

CheckForZoraBabyFollower:
{
  LDA.l $7EF3CC : CMP.b #$09 : BNE .not_zora
    LDA.b #$00
    RTL
  .not_zora
  LDA.b $05
  AND.b #$20
  RTL
}

UploadZoraBabyGraphicsPrep:
{
  PHX
  LDA.b #$09 : STA.l $7EF3CC
  LDA.b #$A0 : STA.w $0AEA
  JSL $00D423
  LDA.b #$00 : STA.l $7EF3CC
  PLX
  LDA.b #$02 : STA.w SprAction, X
  LDA.l $7EF3C9
  RTL
}

; =========================================================
; Check if the Zora baby is on top of the water gate switch
; Returns carry set if the Zora baby is on top of the switch

ZoraBaby_CheckForWaterSwitchSprite:
{
  PHX
  LDX #$10
  -
  LDA.w SprType, X
  CMP #$21 : BEQ ZoraBaby_CheckForWaterGateSwitch_found_switch
  DEX : BPL -
  ; Water gate switch not found
  PLX
  .not_on_switch
  CLC
  RTS
}

ZoraBaby_CheckForWaterGateSwitch:
{
  PHX

  LDX #$10
  -
  LDA.w SprType, X : CMP #$04 : BEQ .found_switch
  DEX : BPL -
  ; Water gate switch not found
  PLX
  .not_on_switch
  CLC
  RTS

  .found_switch
  TXY
  PLX

  ; X is the Zora baby Sprite
  ; Y is the Water gate switch Sprite
  ; Check if the Zora baby is on top of the switch
  LDA.w SprX, X : CLC : ADC #$09 : CMP.w SprX, Y : BCC .not_on_switch
  LDA.w SprX, X : SEC : SBC #$09 : CMP.w SprX, Y : BCS .not_on_switch
  LDA.w SprY, X : CLC : ADC #$12 : CMP.w SprY, Y : BCC .not_on_switch
  LDA.w SprY, X : SEC : SBC #$12 : CMP.w SprY, Y : BCS .not_on_switch
  SEC
  RTS
}

ZoraBaby_GlobalBehavior:
{
  JSL Sprite_BehaveAsBarrier
  JSR Follower_WatchLink
  LDA.w SprAction, X : CMP.b #$02 : BEQ +
    JSL Sprite_CheckIfLifted
    JSL ThrownSprite_TileAndSpriteInteraction_long
    JSL Sprite_Move

    JSR ZoraBaby_CheckForWaterGateSwitch : BCC ++
      ; Face head up towards switch
      LDA.b #$20 : STA.w FollowerHeadOffset
      ; Set end of switch graphics
      LDA.b #$0D : STA.w SprGfx, Y
      ; Set the water gate tag
      LDA.b #$01 : STA.w $0642
      ; Goto ZoraBaby_PullSwitch
      LDA.b #$05 : STA.w SprAction, X
    ++

    JSR ZoraBaby_CheckForWaterSwitchSprite : BCC +
      ; Set end of switch graphics
      LDA.b #$01 : STA.w SprAction, Y
      ; Goto ZoraBaby_PullSwitch
      LDA.b #$05 : STA.w SprAction, X
      LDA.w SprX, X : CLC : ADC #$10 : STA.w SprX, X
  +
  RTL
}

pushpc

; Make Zora sway like a girl
org $09AA5E : JSL CheckForZoraBabyFollower

; Follower_BasicMover
; Jump to ZoraBaby sprite on star tile
org $09A19C : JSL CheckForZoraBabyTransitionToSprite

; Make Zora follower blue palette
org $09A902 : db $02

; Zora Baby char data offset
org $09A8CF : org $00C0

; Zora Baby Sprite Idle OAM data
org $06BD9C
  dw   0,  -8 : db $20, $03, $00, $02
  dw   0,   0 : db $22, $03, $00, $02

org $068D59
SpritePrep_Locksmith:
{
  INC.w SprBulletproof, X

  ; Clear sprite if we already have Zora baby
  LDA.l $7EF3CC : CMP.b #$09 : BNE .not_already_following
    STZ.w SprState, X
    RTS
  .not_already_following

  CMP.b #$0C : BNE .no_purple_chest
    LDA.b #$02 : STA.w SprAction, X
  .no_purple_chest

  JSL UploadZoraBabyGraphicsPrep : AND.b #$10 : BEQ .exit
    LDA.b #$04 : STA.w SprAction, X
  .exit

  RTS
}
assert pc() <= $068D7F

SpriteDraw_Locksmith = $06BDAC
Sprite_CheckIfActive_Bank06 = $06D9EC

; Overrides Sprite_39_Locksmith
org $06BCAC
Sprite_39_ZoraBaby:
{
  JSR SpriteDraw_Locksmith
  JSR Sprite_CheckIfActive_Bank06
  JSL ZoraBaby_GlobalBehavior

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw LockSmith_Chillin
  dw ZoraBaby_FollowLink          ; Becomes Follower
  dw ZoraBaby_OfferService        ; I can help! (Follow/Stay)
  dw ZoraBaby_RespondToAnswer     ; Goto FollowLink or JustPromiseOkay
  dw ZoraBaby_AgreeToWait
  dw ZoraBaby_PullSwitch
  dw ZoraBaby_PostSwitch

  ; =======================================================

  LockSmith_Chillin:
  {
    LDY.b #$01 : LDA.b #$07 ; MESSAGE 0107
    JSL Sprite_ShowSolicitedMessage

    LDA.w SprX, X
    PHA

    SEC : SBC.b #$10 : STA.w SprX, X

    JSR Sprite_Get16BitCoords_Local

    LDA.b #$01 : STA.w SprXSpeed, X : STA.w SprYSpeed, X

    JSL Sprite_CheckTileCollision_long : BNE .dont_stalk_link
      INC.w SprAction, X
      LDA.l $7EF3CC : CMP.b #$00 : BEQ .dont_stalk_link
        LDA.b #$05 : STA.w SprAction, X
    .dont_stalk_link
    PLA
    STA.w SprX, X

    RTS
  }

  ; =======================================================

  ZoraBaby_FollowLink:
  {
    LDA.b #$09 : STA.l $7EF3CC

    PHX
    STZ.w $02F9
    JSL LoadFollowerGraphics
    JSL Follower_Initialize
    PLX

    LDA.b #$40
    STA.w $02CD
    STZ.w $02CE
    STZ.w SprState, X

    RTS
  }

  ; =======================================================

  ZoraBaby_OfferService:
  {
    JSL CheckIfLinkIsBusy : BCS .exit
      LDY.b #$01 : LDA.b #$09 ; MESSAGE 0109
      JSL Sprite_ShowSolicitedMessage : BCC .exit
        INC.w SprAction, X
    .exit
    RTS
  }

  ; =======================================================

  ZoraBaby_RespondToAnswer:
  {
    LDA.w $1CE8 : BNE .rejected
      LDY.b #$01 : LDA.b #$0C ; MESSAGE 010C
      JSL Sprite_ShowMessageUnconditional
      LDA.b #$01 : STA.w SprAction, X
      RTS

      ; LDA.l $7EF3C9
      ; ORA.b #$10
      ; STA.l $7EF3C9

    .rejected
    LDY.b #$01 : LDA.b #$0A ; MESSAGE 010A
    JSL Sprite_ShowMessageUnconditional

    LDA.b #$FF : STA.w SprTimerB, X
    INC.w SprAction, X

    RTS
  }

  ; =======================================================

  ZoraBaby_AgreeToWait:
  {
    LDA.b #$A0 : STA.w $0AEA
    LDY.b #$01 : LDA.b #$0B ; MESSAGE 010B
    JSL Sprite_ShowSolicitedMessage
    LDA.w SprTimerB, X : BNE +
      STZ.w SprAction, X
    +
    RTS
  }

  ; =======================================================

  ZoraBaby_PullSwitch:
  {
    LDY.b #$01 : LDA.b #$07 ; MESSAGE 0107
    JSL Sprite_ShowMessageUnconditional
    ; LDA.b #$01 : STA.b $B1
    ; JSL $01B8BF
    INC.w SprAction, X
    RTS
  }

  ZoraBaby_PostSwitch:
  {
    RTS
  }
}
print "End of Sprite 39 Locksmith        ", pc
assert pc() <= $06BD9C

pullpc

; =========================================================
; Old Man Follower Sprite

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
org $1EE9FF : LDY.b #$13 : STZ.w $02E9

; FindEntrance
org $1BBD3C : CMP.w #$04

; Underworld_LoadEntrance
org $02D98B : CMP.w #$02

org $1EE8F1
SpritePrep_OldMan:
{
  PHB : PHK : PLB
  JSR .main
  PLB
  RTL

  .main
  INC.w SprBulletproof, X
  JSL OldMan_ExpandedPrep : BCS .not_home
    LDA.b #$02 : STA.w $0E80, X
    RTS
  .not_home

  LDA.l $7EF3CC : CMP.b #$00 : BNE .dont_spawn

    ; Check for lv2 hookshot instead of mirror
    LDA.l $7EF342 : CMP.b #$02 : BNE .spawn
      STZ.w SprState, X
    .spawn
    ; FOLLOWER 04
    LDA.b #$04 : STA.l $7EF3CC

    PHX
    JSL LoadFollowerGraphics
    PLX

    LDA.b #$00 : STA.l $7EF3CC
    RTS

  .dont_spawn
  STZ.w SprState, X

  PHX
  JSL LoadFollowerGraphics
  PLX

  RTS
}

org $09A4C8
Follower_HandleTriggerData:
{
  .room_id
  dw $00D1 ; ROOM 00D1 - old man cave
  dw $00FE ; ROOM 0061 - castle lobby
  dw $00FD ; ROOM 0051 - castle throne room
  dw $00FD ; ROOM 0002 - pre-sanc
  dw $00DB ; ROOM 00DB - TT entrance
  dw $00AB ; ROOM 00AB - to TT attic
  dw $0022 ; ROOM 0022 - sewer rats

  .coordinates_uw
  dw $1A78, $0233, $0001, $0099, $0004 ; Old man - MESSAGE 0099
  dw $1BC0, $0378, $0002, $009A, $0004 ; Old man - MESSAGE 009A
  dw $1A78, $0378, $0004, $009B, $0004 ; Old man - MESSAGE 009B

  dw $1FF8, $039D, $0001, $0021, $0001 ; Zelda - MESSAGE 0021
  dw $1FF8, $039D, $0002, $0021, $0001 ; Zelda - MESSAGE 0021
  dw $1FF8, $0238, $0004, $0021, $0001 ; Zelda - MESSAGE 0021

  dw $1D78, $1F7F, $0001, $0022, $0001 ; Zelda - MESSAGE 0022

  dw $1D78, $1F7F, $0001, $0023, $0001 ; Zelda - MESSAGE 0023
  dw $1D78, $1F7F, $0002, $002A, $0001 ; Zelda - MESSAGE 002A

  dw $1BD8, $16FC, $0001, $0124, $0006 ; Blind maiden - MESSAGE 0124

  dw $1520, $167C, $0001, $0124, $0006 ; Blind maiden - MESSAGE 0124

  dw $05AC, $04FC, $0001, $0029, $0001 ; Zelda - MESSAGE 0029

  ; -------------------------------------------------------

  .overworld_id
  dw $0005 ; OW 05 - West DM (Updated)
  dw $002F ; OW 2F - Tail Palace
  dw $0000 ; OW 00 - Lost woods

  .coordinates_ow
  dw $0178, $0A63, $0001, $009D, $0004 ; Old man - MESSAGE 009D
  ;              Y      X
  dw $0A88, $0F41, $0000, $FFFF, $000A ; Kiki
  dw $0B37, $0F40, $0001, $FFFF, $000A ; Kiki
  dw $0A62, $0E5B, $0002, $FFFF, $000A ; Kiki

  dw $00E8, $0090, $0000, $0028, $000E ; MS telepathy - MESSAGE 0028

  ; -------------------------------------------------------

  .room_boundaries_check
  dw $0000, $001E, $003C, $0046
  dw $005A, $0064, $006E, $0078

  .ow_boundaries_check
  dw $0000, $000A, $0028, $0032
}

pullpc

Kiki_CheckIfScared:
{
  ; If Links health is too low, kiki will run away from him
  ; rather than when he takes damage as it currently is.
  LDA.b $4D : BEQ .not_scared
    LDA.w $031F : BEQ .not_scared
    LDA.l $7EF36D : CMP.b #$02 : BNE .not_scared
      SEC
      RTL
  .not_scared
  CLC
  RTL
}

pushpc

; Kiki
dont_scare_kiki = $09A1E4
org $09A1C6
JSL Kiki_CheckIfScared
BCC dont_scare_kiki
NOP #3

; TODO: Update Kiki jump pos
org $1EE2E9
Kiki_WalkOnRoof:
.speed_x ; bleeds into next
  db   0,   0

.speed_y
  db  -9,   9,   0,   0

org $1EE576
Kiki_HopToSpot:
.target_y
  dw $0661
  dw $064C
  dw $0624

.target_x
  dw $0F4F
  dw $0F70
  dw $0F5D

org $1EE5E9
Kiki_WalkOnRoof_Ext:
.step
  db $02, $01, $FF
.timer
  db  82,   0

pullpc

; =========================================================
; Minecart Follower Sprite

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

Minecart_AnimDirection:
  db $02, $00, $02, $00

MinecartFollower_TransitionToSprite:
{
  LDA.b #$A3
  JSL Sprite_SpawnDynamically
  TYX
  JSL Sprite_SetSpawnedCoords
  LDA.w !MinecartDirection : CMP.b #$00 : BEQ .vert_adjust
                             CMP.b #$02 : BEQ .vert_adjust
    LDA.w POSY : CLC : ADC #$08 : STA.w SprY, X
    LDA.w POSX : STA.w SprX, X
    JMP .finish_prep
  .vert_adjust
  LDA.w POSY : STA.w SprY, X
  LDA.w POSX : CLC : ADC #$02 : STA.w SprX, X
  .finish_prep
  LDA.w POSYH : STA.w SprYH, X
  LDA.w POSXH : STA.w SprXH, X
  LDA.w !MinecartDirection : CLC : ADC.b #$04 : STA.w SprSubtype, X

  LDA Minecart_AnimDirection, X : STA $0D90, X
  JSL Sprite_Minecart_Prep
  LDA.b #$00 : STA.l $7EF3CC
  RTS
}

; Minecart Follower Main Routine and Draw
DrawMinecartFollower:
{
  JSL $099EFC ; Follower_Initialize

  LDX !MinecartDirection
  LDA Minecart_AnimDirection, X : STA $02CF

  JSR FollowerDraw_CachePosition
  JSR MinecartFollower_Top
  JSR MinecartFollower_Bottom

  ; Check the current submodule in the underworld
  LDA.b $11 : BNE .dont_spawn
    LDA !LinkInCart : BEQ .dont_spawn
      LDA.b #$09 : STA.b LinkState
      ;JSR MinecartFollower_TransitionToSprite
  .dont_spawn
  RTS
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
  AND.b #$20
  LSR A
  LSR A
  TAY

  LDA.b $05
  AND.b #$03
  STA.b $04

  STZ.b $72
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

  LDA.w $02D7
  INC A
  CMP.b #$03
  BNE .set_repri

  LDA.b #$00

  .set_repri
  STA.w $02D7

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
  ; LDA.b #$10 : STA.b $5E
  PLB
  RTL
}

CheckForFollowerInterroomTransition:
{
  LDA.w !LinkInCart : BEQ .not_in_cart
    LDA.b #$0B : STA $7EF3CC
  .not_in_cart
  JSL $01873A ; Underworld_LoadRoom
  RTL
}

CheckForFollowerIntraroomTransition:
{
  STA.l $7EC007
  LDA.w !LinkInCart : BEQ .not_in_cart
    LDA.b #$0B : STA $7EF3CC
  .not_in_cart
  RTL
}

; 0x08
LinkState_Minecart:
{
  PHB : PHK : PLB
  STZ.b $2A
  STZ.b $2B
  STZ.b $6B
  STZ.b $48

  ; Move Link based on the direction of the cart
  LDA.w !MinecartDirection : BNE .not_north
    LDY.b #$00
    LDA.w .drag_y_low, Y : CLC : ADC.w $0B7E : STA.w $0B7E
    LDA.w .drag_y_high, Y : ADC.w $0B7F : STA.w $0B7F
    STZ.w LinkFaceDir
  .not_north
  CMP.b #$01 : BNE .not_east
    LDY #$03
    LDA.w .drag_x_low,  Y : CLC : ADC.w DragYL : STA.w DragYL
    LDA.w .drag_x_high, Y : ADC.w DragYH : STA.w DragYH
    LDA.b #$06 : STA.w LinkFaceDir
  .not_east
  CMP.b #$02 : BNE .not_south
    LDY #$01
    LDA.w .drag_y_low,  Y : CLC : ADC.w $0B7E : STA.w $0B7E
    LDA.w .drag_y_high, Y : ADC.w $0B7F : STA.w $0B7F
    LDA.b #$02 : STA.w LinkFaceDir
  .not_south
  CMP.b #$03 : BNE .not_west
    LDY #$02
    LDA.w .drag_x_low,  Y : CLC : ADC.w DragYL : STA.w DragYL
    LDA.w .drag_x_high, Y : ADC.w DragYH : STA.w DragYH
  .not_west

  JSL Link_HandleCardinalCollision_Long
  JSL Link_HandleVelocityAndSandDrag

  STZ.w $0302

  ; JSL Link_HandleMovingAnimation_FullLongEntry
  JSL HandleIndoorCameraAndDoors
  JSL Link_CancelDash

  ; Pos - Cache Pos = difference
  LDA.w LinkX : SEC : SBC $3F : STA $31
  LDA.w LinkY : SEC : SBC $3E : STA $30

  PLB
  RTL
  .drag_x_high
  db 0,   0,  -1,   0

  .drag_x_low
  db 0,   0,  -1,   1

  .drag_y_low
  db -1,   1,   0,   0

  .drag_y_high
  db -1,   0,   0,   0
}

pushpc

org $07A5F7
  JSL LinkState_Minecart
  RTS

assert pc() <= $07A64B

; Follower_OldManUnused
org $09A41F
  JSL CheckForMinecartFollowerDraw
  RTS

; Module07_02_01_LoadNextRoom
org $028A5B : JSL CheckForFollowerInterroomTransition

; UnderworldTransition_Intraroom_PrepTransition
org $0289BF : JSL CheckForFollowerIntraroomTransition

pullpc
