; =========================================================
; Twinrova Boss Sprite
; =========================================================

!SPRID              = $CE ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 06  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 00  ; Unused in this Twinrova (can be 0 to 7)
!Hitbox             = 03  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 01  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 00  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 01  ; 00 = normal sprite, 01 = sprite is a boss
%Set_Sprite_Properties(Sprite_Twinrova_Prep, Sprite_Twinrova_Long)

; =========================================================

Sprite_Twinrova_Long:
{
  PHB : PHK : PLB

  JSR Sprite_Twinrova_Draw ; Call the draw code
  JSL Sprite_DrawShadow

  JSL Sprite_CheckActive ; Check if game is not paused
  BCC .SpriteIsNotActive ; Skip Main code is sprite is innactive

  JSR Sprite_Twinrova_CheckIfDead ; Check if sprite is dead
  JSR Sprite_Twinrova_Main        ; Call the main sprite code

.SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

; =========================================================

Sprite_Twinrova_CheckIfDead:
{
  LDA $0D80, X : CMP.b #$0A : BEQ .not_dead

  ; If health is negative, set back to zero
  LDA $0E50, X : CMP.b #$44 : BCC .healthNotNegative
    LDA.b #$00 : STA $0E50, X

.healthNotNegative

  LDA $0E50, X : BNE .not_dead
    PHX 

    LDA.b #$04 : STA $0DD0, X ; Kill sprite boss style
    LDA.b #$0A : STA $0D80, X ; Go to Twinrova_Dead stage

    PLX
.not_dead
  RTS
}

; =========================================================

Sprite_Twinrova_Prep:
{
    PHB : PHK : PLB
    
    ; PrepareBattle
    LDA.l $7EF3CC : CMP.b #$06 : BEQ .despawn
      LDA.b #$40 : STA $0E50, X ; Health
      LDA.b #$04 : STA $0CD2, X ; Bump damage type (4 hearts, green tunic)

      %SetSpriteSpeedX(15)
      %SetSpriteSpeedX(15)

      LDA #$10 : STA $08
      LDA #$10 : STA $09
      STZ $0D80, X

      PLB
      RTL
  .despawn
    STZ.w $0DD0, X
    PLB
    RTL
}

; =========================================================

!AnimSpeed = 8

macro      Twinrova_Front()
  %PlayAnimation(0,1,!AnimSpeed)
endmacro

macro Twinrova_Back()
  %PlayAnimation(2,3,!AnimSpeed)
endmacro

macro Twinrova_Ready()
  %PlayAnimation(4,6,!AnimSpeed)
endmacro

macro Twinrova_Attack()
  %PlayAnimation(7,7,!AnimSpeed)
endmacro

macro Show_Koume()
  %PlayAnimation(8,8,!AnimSpeed)
endmacro

macro Show_Kotake()
  %PlayAnimation(9,9,!AnimSpeed)
endmacro

macro Twinrova_Hurt()
  %PlayAnimation(10,11,!AnimSpeed)
endmacro

; =========================================================

; Phase 0: Blind Maiden turns into Twinrova.
;          Initially should be invisible, then
;          transfer in Twinrova gfx and run dialogue.
;
; Phase 1: Twinrova is one entity, moving around the room
;          and shooting fire and ice attacks at Link.
;          Similar to the Trinexx attacks.
;
; Phase 2: Twinrova alternates between Koume (fire) and 
;          Kotake (ice) forms. Koume changes the arena
;          to a fire arena. Similar to Ganon fight changes.

Sprite_Twinrova_Main:
{
  LDA.w SprAction, X
  JSL   UseImplicitRegIndexedLocalJumpTable
  
  dw Twinrova_Init          ; 0x00
  dw Twinrova_MoveState     ; 0x01
  dw Twinrova_MoveForwards  ; 0x02
  dw Twinrova_MoveBackwards ; 0x03
  dw Twinrova_PrepareAttack ; 0x04
  dw Twinrova_FireAttack    ; 0x05
  dw Twinrova_IceAttack     ; 0x06
  dw Twinrova_Hurt          ; 0x07
  dw Twinrova_KoumeMode     ; 0x08
  dw Twinrova_KotakeMode    ; 0x09
  dw Twinrova_Dead          ; 0x0A

  ; 0x00
  Twinrova_Init:
  {
      ; %Twinrova_Front()
      JSR ApplyTwinrovaGraphics
      %GotoAction(01)
      RTS
  }

  ; 0x01
  Twinrova_MoveState:
  {
      LDA $0E50, X : CMP.b #$20 : BCS .phase_1
      ; -------------------------------------------
      ; Phase 2
      LDA SprTimerE, X : BNE .kotake
        LDA #$70 : STA SprTimerD, X
        %GotoAction(8) ; Koume Mode
        RTS
      .kotake
        LDA #$70 : STA SprTimerD, X
        %GotoAction(9) ; Kotake Mode
        RTS

    ; ---------------------------------------------
    .phase_1
      LDA $0DA0 : BEQ .not_flashing
        LDA.b #$20 : STA.w SprTimerD, X
        %GotoAction(7) ; Goto Twinrova_Hurt
      RTS
    .not_flashing

      JSL GetRandomInt : AND.b #$3F : BNE +
        LDA.b #$20 : STA.w SprTimerD, X
        STZ   $AC
        %GotoAction(4) ; Prepare Attack
        RTS
    +

      JSL GetRandomInt : AND.b #$3F : BNE ++
        LDA.b #$20 : STA.w SprTimerD, X
        LDA   #$01 : STA $AC
        %GotoAction(4) ; Prepare Attack
        RTS
    ++

      JSL Sprite_IsBelowPlayer ; Check if sprite is below player
      TYA : BNE .MoveBackwards ; If 1, 
        %GotoAction(2)
        RTS
    .MoveBackwards
      %GotoAction(3)
      RTS
  }

  ; 0x02 - TODO: Implement Twinrova_MoveForwards
  Twinrova_MoveForwards:
  {
      %Twinrova_Front()

      PHX 
      JSL Sprite_CheckDamageFromPlayerLong
      %DoDamageToPlayerSameLayerOnContact()
      PLX 

      JSL Sprite_DamageFlash_Long
      JSL Sprite_BounceTowardPlayer

      %GotoAction(1)
      RTS
  }

  ; 0x03 - TODO: Implement Twinrova_MoveBackwards
  Twinrova_MoveBackwards:
  {
      %Twinrova_Back()

      PHX 
      JSL Sprite_CheckDamageFromPlayerLong
      %DoDamageToPlayerSameLayerOnContact()
      PLX 

      JSL Sprite_DamageFlash_Long
      JSL Sprite_BounceTowardPlayer

      %GotoAction(1)
      RTS
  }

  ; 0x04
  Twinrova_PrepareAttack:
  {
      %StartOnFrame(7)
      %Twinrova_Attack()

      PHX 
      JSL Sprite_CheckDamageFromPlayerLong
      %DoDamageToPlayerSameLayerOnContact()
      PLX 

      LDA $0CAA : AND.b #$03 : STA $0CAA
      LDA SprTimerD, X : BNE +
        LDA $0CAA : ORA.b #$03 : STA $0CAA
        LDA.b #$40 : STA.w SprTimerD, X
        LDA   $AC : BEQ .fire
          %GotoAction(6) ; Ice Attack
          RTS
      .fire
          %GotoAction(5)
    +
      RTS
  }

  ; 0x05
  Twinrova_FireAttack:
  {
      %StartOnFrame(4)
      %Twinrova_Ready()

      JSR Sprite_Twinrova_FireAttack

      LDA.w SprTimerD, X : BNE +
        %GotoAction(1)
    +
      RTS
  }

  ; 0x06
  Twinrova_IceAttack:
  {
      %StartOnFrame(4)
      %Twinrova_Ready()

      JSR Sprite_Twinrova_IceAttack

      LDA.w SprTimerD, X : BNE +
        %GotoAction(1)
    +
      RTS
  }

  ; 0x07
  Twinrova_Hurt:
  {
      %StartOnFrame(10)
      %Twinrova_Hurt()
      
      PHX
      JSL Sprite_CheckDamageFromPlayerLong
      %DoDamageToPlayerSameLayerOnContact()
      PLX 

      JSL Sprite_DamageFlash_Long
      
      LDA.w SprTimerD, X : BNE +
        %GotoAction(1)
    +
      RTS
  }

  ; 0x08
  Twinrova_KoumeMode:
  {
      %StartOnFrame(8)
      %Show_Koume()

      PHX
      JSL Sprite_CheckDamageFromPlayerLong
      %DoDamageToPlayerSameLayerOnContact()
      PLX 

      JSL Sprite_DamageFlash_Long
      JSL Sprite_BounceTowardPlayer

      LDA SprTimerD, X : BNE +
        %GotoAction(1)
    +
      RTS
  }

  ; 0x09
  Twinrova_KotakeMode:
  {
      %StartOnFrame(9)
      %Show_Kotake()

      PHX
      JSL Sprite_CheckDamageFromPlayerLong
      %DoDamageToPlayerSameLayerOnContact()
      PLX 

      JSL Sprite_DamageFlash_Long
      JSL Sprite_BounceTowardPlayer

      LDA SprTimerD, X : BNE +
        %GotoAction(1)
    +
      RTS
  }

  ; 0x0A
  Twinrova_Dead:
  {
      %StartOnFrame(10)
      %Twinrova_Hurt()
      RTS
  }
}

; =========================================================

; Reused function from TrinexxBreath.
TrinexxBreath_AltEntry:
{
    LDA $1A : AND.b #$03 : BNE .no_shake
      JSL Sprite_IsToRightOfPlayer
      LDA $0D50, X : CMP .x_speed_targets, Y : BEQ .no_shake
        CLC : ADC.w $8000, Y : STA $0D50, X

  .no_shake
    JSL Sprite_CheckTileCollision : BEQ .exit
    JSL Sprite_BounceTowardPlayer

  .exit
    RTS

  .x_speed_targets
    db 8, -16
}

Sprite_Twinrova_FireAttack:
{ 
    JSL Sprite_CheckTileCollision : BNE .no_collision
    JSL Sprite_Move
  .no_collision
    JSR AddFireGarnish
    JMP TrinexxBreath_AltEntry
}

; $1DBDD6 - TrinexxFire_AddFireGarnish
AddFireGarnish:
{
    INC $0E80, X : LDA $0E80, X : AND.b #$07 : BNE .return
      LDA.b #$2A : JSL Sound_SetSfx2PanLong
      LDA.b #$1D : PHX : TXY : TAX : STA $00

  .next_slot
    LDA $7FF800, X : BEQ .free_slot
      DEX : BPL .next_slot
        DEC $0FF8 : BPL .use_search_index
          LDA $00 : STA $0FF8

  .use_search_index
    LDX $0FF8

  .free_slot
    LDA.b #$10 : STA $7FF800, X : STA $0FB4
    TYA : STA $7FF92C, X
    
    LDA.w SprX, Y : STA $7FF83C, X
    LDA.w SprXH, Y : STA $7FF878, X
    LDA.w SprY, Y : CLC : ADC.b #$10 : STA $7FF81E, X
    LDA.w SprYH, Y : ADC.b #$00 : STA $7FF85A, X
    
    LDA.b #$7F : STA $7FF90E, X
    STX $00
    PLX

  .return
    RTS
}

; $1DBD65 - TrinexxBreath_ice_add_ice_garnish
AddIceGarnishV2:
{
    INC $0E80, X : LDA $0E80, X : AND.b #$07 : BNE .return
      LDA.b #$14 : JSL Sound_SetSfx3PanLong
      LDA.b #$1D : PHX : TXY : TAX : STA $00

  .next_slot
    LDA $7FF800, X : BEQ .free_slot
      DEX : BPL .next_slot
        DEC $0FF8 : BPL .use_search_index
          LDA.b #$00 : STA $0FF8

  .use_search_index
    LDX $0FF8

  .free_slot
    LDA.b #$0C : STA $7FF800, X : STA $0FB4
    TYA : STA $7FF92C, X
    
    LDA.w SprX, Y : STA $7FF83C, X
    LDA.w SprXH, Y : STA $7FF878, X
    LDA.w SprY, Y : CLC : ADC.b #$10 : STA $7FF81E, X
    LDA.w SprYH, Y : ADC.b #$00 : STA $7FF85A, X
    
    LDA.b #$7F : STA $7FF90E, X : STX $00
    
    PLX

  .return
    RTS
}

Sprite_Twinrova_IceAttack:
{
    JSL Sprite_CheckTileCollision : BNE .no_collision
      JSL Sprite_Move
  .no_collision
    JSR AddIceGarnishV2
    JMP TrinexxBreath_AltEntry
}

; =========================================================

; Overwrite vanilla Trinexx ice garnish
; Plays like a simple ice cloud animation now.

pushpc

org $09B5DE
  Garnish_PrepOamCoord:

org $09B70C
  Garnish_SetOamPropsAndLargeSize:

org $09B459
  Garnish_CheckPlayerCollision:

org $09B5D6
  Garnish_SetOamPropsAndSmallSize:

org $09B33F
TrinexxIce_Pool:
{
  .chr
    db $2E
    db $2E
    db $2C
    db $2C
  .properties
    db $35
    db $35
    db $35
    db $35
}

org $09B34F
Garnish_TrinexxIce:
{
  ; special animation 0x0C
  LDA $7FF90E, X : LSR #2 : AND.b #$03 : TAY
  LDA TrinexxIce_Pool_properties, Y : STA $04
  JSR Garnish_PrepOamCoord

  LDA $00       : STA ($90), Y
  LDA $02 : INY : STA ($90), Y
  
  LDA $7FF90E, X : LSR #5 : PHX : TAX
  LDA TrinexxIce_Pool_chr, X : INY : STA ($90), Y
  LDA.b #$35 : ORA $04 : PLX
  
  JMP Garnish_SetOamPropsAndLargeSize
}
warnpc $09B3B8

; Ice Garnish 
org $0DB266+$CD
  db $04

pullpc

; =========================================================

Sprite_Twinrova_Draw:
{
    JSL Sprite_PrepOamCoord
    JSL Sprite_OAM_AllocateDeferToPlayer

    LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
    LDA .start_index, Y : STA $06

    ; Store Palette thing 
    LDA $0DA0, X : STA $08

    PHX
    LDX   .nbr_of_tiles, Y ;amount of tiles -1
    LDY.b #$00
  .nextTile

    PHX ; Save current Tile Index?
        
    TXA : CLC : ADC $06 ; Add Animation Index Offset

    PHA ; Keep the value with animation index offset?

    ASL A : TAX

    REP #$20

    LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
    AND.w #$0100 : STA $0E
    INY
    LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
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

    ; Set palette flash modifier 
    LDA .properties, X : ORA $08 : STA ($90), Y

    PHY 
        
    TYA : LSR #2 : TAY
        
    SEP #$20 ;set A back to 8bit but not X and Y
    LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
        
    PLY : INY
        
    PLX : DEX : BPL .nextTile

    SEP #$30

    PLX

    RTS


; =========================================================
  .start_index
    db $00, $04, $08, $0C, $10, $14, $18, $1C, $22, $26, $2A, $2E
  .nbr_of_tiles
    db 3, 3, 3, 3, 3, 3, 3, 5, 3, 3, 3, 3
  .x_offsets
    dw -8, 8, 8, -8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -16, 0, 16, -16, 0, 16
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
  .y_offsets
    dw -8, -8, 8, 8
    dw -7, -7, 9, 9
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -7, -7, 9, 9
    dw -6, -6, 10, 10
    dw -8, -8, -8, 8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -7, -7, 9, 9
  .chr
    db $00, $02, $22, $24
    db $04, $06, $24, $26
    db $08, $0A, $28, $2A
    db $0C, $0E, $28, $2A
    db $44, $46, $64, $66
    db $48, $4A, $68, $6A
    db $4C, $4E, $6C, $6E
    db $88, $8A, $8C, $A8, $AA, $AC
    db $80, $82, $A0, $A2
    db $84, $86, $A4, $A6
    db $40, $42, $60, $62
    db $40, $42, $60, $62
  .properties
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
  .sizes
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02, $02, $00
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
}

; =========================================================

ApplyTwinrovaGraphics:
{
    PHX 

    REP #$20             ; A = 16, XY = 8
    LDX #$80 : STX $2100 ; turn the screen off (required)

    LDX #$80 : STX $2115   ; Set the video port register every time we write it increase by 1
    LDA #$5000 : STA $2116 ; Destination of the DMA $5800 in vram <- this need to be divided by 2
    LDA #$1801 : STA $4300 ; DMA Transfer Mode and destination register 
                           ; "001 => 2 registers write once (2 bytes: p, p+1)"
    LDA.w #TwinrovaGraphics : STA $4302     ; Source address where you want gfx from ROM
    LDX.b #TwinrovaGraphics>>16 : STX $4304
    LDA   #$2000 : STA $4305                ; size of the transfer 4 sheets of $800 each
    LDX   #$01 : STX $420B                  ; Do the DMA 

    LDX #$0F : STX $2100 ;turn the screen back on

    SEP #$30

    PLX

    RTS

  TwinrovaGraphics:
    incbin twinrova.bin
}

pushpc

; =========================================================
; Blind Maiden spawn code

org $0DB818
  SpritePrep_LoadProperties:

; Follower_BasicMover.dont_scare_kiki
org $09A1E4
Follower_BasicMover:
{
    ; Check if the follower is the blind maiden
    LDA.l $7EF3CC : CMP.b #$06 : BNE .no_blind_transform
      ; Check if we are in room 0xAC
      REP #$20 
      LDA.b $A0 : CMP.w #$00AC : BNE .no_blind_transform
        ; Check room flag 0x65
        LDA.l $7EF0CA : AND.w #$0100 : BEQ .no_blind_transform
          SEP #$20
          JSL Follower_CheckBlindTrigger : BCC .no_blind_transform
  .blind_transform
    ; Load follower animation step index from $02CF
    LDX.w $02CF
    LDA.w $1A28, X : STA.b $00 ; Follower XL
    LDA.w $1A3C, X : STA.b $01 ; Follower XH
    LDA.w $1A00, X : STA.b $02 ; Follower YL
    LDA.w $1A14, X : STA.b $03 ; Follower YH

    ; Dismiss the follower and spawn Twinrova
    LDA.b #$00 : STA.l $7EF3CC
    JSL Blind_SpawnFromMaiden

    ; Close the shutter door 
    INC.w $0468

    ; Clear door tilemap position for some reason
    STZ.w $068E : STZ.w $0690

    ; TODO: Find out what submodule this is.
    LDA.b #$05 : STA.b $11

     ; SONG 15
    LDA.b #$15 : STA.w $012C

    RTS
  .no_blind_transform
}

; =========================================================

org $099E90
Follower_CheckBlindTrigger:
{
    PHB : PHK : PLB

    ; Cache the follower's position
    LDX.w $02CF
    LDA.w $1A00, X : STA.b $00
    LDA.w $1A14, X : STA.b $01
    LDA.w $1A28, X : STA.b $02
    LDA.w $1A3C, X : STA.b $03
    STZ.b $0B

    ; Check if the follower is within the trigger area
    LDA.w $1A50, X : STA.b $0A : BPL .positive_z
      LDA.b #$FF : STA.b $0B

  .positive_z
    REP #$20

    LDA.b $00 : CLC : ADC.b $0A : CLC : ADC.w #$000C : STA.b $00
    LDA.b $02 : CLC : ADC.w #$0008 : STA.b $02
    LDA.w #$1568 : SEC : SBC.b $00 : BPL .positive_x
      EOR.w #$FFFF : INC A
  .positive_x
    CMP.w #$0018 : BCS .fail
      LDA.w #$1980 : SEC : SBC.b $02 : BPL .positive_y
        EOR.w #$FFFF : INC A

  .positive_y
    CMP.w #$0018
    BCS .fail

  .success
    SEP #$20
    PLB : SEC
    RTL

  .fail
    SEP #$20
    PLB : CLC
    RTL
}

; =========================================================

org $1DA03C
Blind_SpawnFromMaiden:
{
  LDX.b #$00 ; Load the boss into sprite index 0

  ; Set the sprite to alive and active
  LDA.b #$09 : STA.w $0DD0,X

  ; SPRITE CE
  LDA.b #$CE : STA.w $0E20,X

  ; Load the position cache from the maiden follower
  LDA.b $00 : STA.w $0D10,X
  LDA.b $01 : STA.w $0D30,X
  LDA.b $02 : SEC : SBC.b #$10 : STA.w $0D00,X
  LDA.b $03 : STA.w $0D20,X
  JSL SpritePrep_LoadProperties

  ; Set SprTimerC
  LDA.b #$C0 : STA.w $0E10,X

  ; Set SprGfx
  LDA.b #$15 : STA.w $0DC0,X

  ; Set SprMiscC and bulletproof properties
  LDA.b #$02 : STA.w $0DE0,X : STA.w $0BA0,X

  ; Set the 2nd key / heart piece items taken room flag 
  LDA.w $0403 : ORA.b #$20 : STA.w $0403

  ; Clear blinds head spin flag
  STZ.w $0B69

  RTL
}

; =========================================================

SpritePrep_Blind_PrepareBattle:
{
    #_1DA081: LDA.l $7EF3CC
    #_1DA085: CMP.b #$06 ; FOLLOWER 06
    #_1DA087: BEQ .despawn

    #_1DA089: LDA.w $0403
    #_1DA08C: AND.b #$20
    #_1DA08E: BEQ .despawn

    #_1DA090: LDA.b #$60
    #_1DA092: STA.w $0E10,X

    #_1DA095: LDA.b #$01
    #_1DA097: STA.w $0DB0,X

    #_1DA09A: LDA.b #$02
    #_1DA09C: STA.w $0DE0,X

    #_1DA09F: LDA.b #$04
    #_1DA0A1: STA.w $0EB0,X

    #_1DA0A4: LDA.b #$07
    #_1DA0A6: STA.w $0DC0,X

    #_1DA0A9: STZ.w $0B69

    #_1DA0AC: RTL

  .despawn
    #_1DA0AD: STZ.w $0DD0,X

    #_1DA0B0: RTL
}
; =========================================================


BlindLaser_SpawnTrailGarnish:
{
    #_1DA0B1: LDA.w $0E80,X
    #_1DA0B4: AND.b #$00
    #_1DA0B6: BNE .exit

    #_1DA0B8: PHX
    #_1DA0B9: TXY

    #_1DA0BA: LDX.b #$1D

  .next_slot
    #_1DA0BC: LDA.l $7FF800,X
    #_1DA0C0: BEQ .free_slot

    #_1DA0C2: DEX
    #_1DA0C3: BPL .next_slot

    #_1DA0C5: DEC.w $0FF8
    #_1DA0C8: BPL .use_search_index

    #_1DA0CA: LDA.b #$1D
    #_1DA0CC: STA.w $0FF8

  .use_search_index
    #_1DA0CF: LDX.w $0FF8

  .free_slot
    #_1DA0D2: LDA.b #$0F ; GARNISH 0F
    #_1DA0D4: STA.l $7FF800,X
    #_1DA0D8: STA.w $0FB4

    #_1DA0DB: LDA.w $0DC0,Y
    #_1DA0DE: STA.l $7FF9FE,X

    #_1DA0E2: TYA
    #_1DA0E3: STA.l $7FF92C,X

    #_1DA0E7: LDA.w $0D10,Y
    #_1DA0EA: STA.l $7FF83C,X

    #_1DA0EE: LDA.w $0D30,Y
    #_1DA0F1: STA.l $7FF878,X

    #_1DA0F5: LDA.w $0D00,Y
    #_1DA0F8: CLC
    #_1DA0F9: ADC.b #$10
    #_1DA0FB: STA.l $7FF81E,X

    #_1DA0FF: LDA.w $0D20,Y
    #_1DA102: ADC.b #$00
    #_1DA104: STA.l $7FF85A,X

    #_1DA108: LDA.b #$0A
    #_1DA10A: STA.l $7FF90E,X

    #_1DA10E: PLX

  .exit
    #_1DA10F: RTS
}

pullpc