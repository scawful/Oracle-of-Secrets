;==============================================================================
; Sprite Properties
;==============================================================================
!SPRID              = $7B; The sprite ID you are overwriting (HEX)
!NbrTiles           = 6 ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 0  ; Number of Health the sprite have
!Damage             = 0  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 0  ; Unused in this template (can be 0 to 7)
!Hitbox             = 0  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 0  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_Kydrog_Prep, Sprite_Kydrog_Long)

;==============================================================================

Sprite_Kydrog_Long:
{
  PHB : PHK : PLB

  JSR Sprite_Kydrog_Draw ; Call the draw code
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_Kydrog_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}
;==============================================================================

Sprite_Kydrog_Prep:
{
  PHB : PHK : PLB
    
  ; Add more code here to initialize data
  LDA.l $7EF300
  BEQ .PlayIntro
    STZ.w $0DD0, X ; Kill the sprite 
.PlayIntro

  PLB
  RTL
}

;==============================================================================

Sprite_Kydrog_Main:
{
  LDA.w SprAction, X; Load the SprAction
  JSL UseImplicitRegIndexedLocalJumpTable; Goto the SprAction we are currently in

  dw Kydrog_StartCutscene
  dw Kydrog_AttractPlayer
  dw Kydrog_SpawnOffspring
  dw Kydrog_WarpPlayerAway


  Kydrog_StartCutscene:
  {
    LDA WALKSPEED : STA.b $57 ; Slow Link down for the cutscene
    LDA.b #$08 : STA.b $49 ; Auto-movement north

    LDA.b $20 ; Link's Y Position
    CMP.b #72 ; Y = 6C
    BCC .linkistoofar

    LDA.b #$80
    STA.w SprTimerA, X ; set timer A to 0x10
    %GotoAction(1)

  .linkistoofar

    RTS
  }

  Kydrog_AttractPlayer:
  {
    LDA.w SprTimerA, X : BNE +
    LDA #$00 : STA $7EF303
    %ShowUnconditionalMessage($21)
    %GotoAction(2)
  +
    RTS
  }

  Kydrog_SpawnOffspring:
  {
    LDA.b #$02 : STA.b $B6 ; Update story flag for Farore
    STZ.b $49 ; Stop Link from moving 
    %GotoAction(3)
    RTS
  }

  Kydrog_WarpPlayerAway:
  {
    ; Set game state to part 03 
    ; LDA.b #$03 : STA $7EF3C5

    ; Put us in the Dark World.
    LDA $7EF3CA : EOR.b #$40 : STA $7EF3CA

    JSL $00FC41 ; Sprite_LoadGfxProperties
    ; JSL $00FC62 ; Sprite_LoadGfxProperties.justLightWorld 

    STZ $037B : STZ $3C : STZ $3A : STZ $03EF

    ; Link can't move
    LDA.b #$01 : STA $02E4

    ; The module to return to is #$08 (preoverworld)
    LDA.b #$08 : STA $010C

    ; Set the map I want 
    LDA.b #$20 : STA $A0 : STZ $A1
    
    ; Set us to the warp state 
    LDA.b #$15 : STA $10

    ; Clear submodules
    STZ $11 : STZ $B0

    ; Remove Impa follower 
    LDA.b #$00 : STA $7EF3CC

    ; Set the flag to remove Farore and Kydrog from Maku area
    LDA #$01 : STA.l $7EF300

    RTS
  }
}

;==============================================================================

Sprite_Kydrog_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06


  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
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
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : STA ($90), Y

  PHY 
      
  TYA : LSR #2 : TAY
      
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
      
  PLY : INY
      
  PLX : DEX : BPL .nextTile

  PLX

  RTS

;==============================================================================

.start_index
  db $00
.nbr_of_tiles
  db 5
.x_offsets
  dw -8, 8, 8, -8, -8, 8
.y_offsets
  dw -12, -12, 4, 4, 20, 20
.chr
  db $CC, $CE, $EE, $EC, $E8, $EA
.properties
  db $3B, $3B, $3B, $3B, $3B, $3B
.sizes
  db $02, $02, $02, $02, $02, $02
}

; I forget what this is lol 
; org $02ECF8
;   dw $0029

; ==============================================================================

; 169BC 
; org $02E9BC
;   LoadOverworldFromSpecialOverworld:

; org $029E65
;   JSR LoadOverworldFromSpecialOverworld
