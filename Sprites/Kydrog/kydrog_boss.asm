;==============================================================================
; Sprite Properties
;==============================================================================

!SPRID              = $CB ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 10  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 20  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 00  ; Unused in this KydrogBoss (can be 0 to 7)
!Hitbox             = 00  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
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
!Boss               = $01  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_KydrogBoss_Prep, Sprite_KydrogBoss_Long)

;==============================================================================

Sprite_KydrogBoss_Long:
{
  PHB : PHK : PLB

  JSR Sprite_KydrogBoss_Draw ; Call the draw code
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_KydrogBoss_CheckIfDead ; Check if sprite is dead
  JSR Sprite_KydrogBoss_Main ; Call the main sprite code

.SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

;==============================================================================

Sprite_KydrogBoss_CheckIfDead:
{
  LDA $0D80, X : CMP.b #$09 : BEQ .not_dead

  LDA $0E50, X : BNE .not_dead
    PHX 

    LDA.b #$04 : STA $0DD0, X ;kill sprite boss style

    LDA.b #$09 : STA $0D80, X ;go to KydrogBoss_Death stage

    PLX
.not_dead
  RTS
}

;==============================================================================

Sprite_KydrogBoss_Prep:
{  
  PHB : PHK : PLB
    
  ; Add more code here to initialize data
  LDA.b #$80 : STA $0CAA, X

  LDA.b #$10 : STA $0E50, X ; health
  LDA.b #$03 : STA $0F60, X ; hitbox settings 
  LDA.b #$0F : STA $0CD2, X ; bump damage type (4 hearts, green tunic)
  
  ; Make the sprite take damage from a sword
  LDA $0CAA, X : AND.b #$FB : STA $0CAA, X
  
  ; Make the sprite not invincible 
  LDA $0E60, X : AND.b #$BF : STA $0E60, X

  JSR KydrogBoss_Set_Damage ; Set the damage table

  %SetSpriteSpeedX(15)
  %SetSpriteSpeedX(15)
  %SetHarmless(00)

  PLB
  RTL
}
;==============================================================================

Sprite_KydrogBoss_Main:
{
  LDA.w SprAction, X; Load the SprAction
  JSL UseImplicitRegIndexedLocalJumpTable; Goto the SprAction we are currently in

  dw KydrogBoss_Init          ; 00

  dw KydrogBoss_WalkState     ; 01
  dw KydrogBoss_WalkForward   ; 02
  dw KydrogBoss_WalkLeft      ; 03
  dw KydrogBoss_WalkRight     ; 04
  dw KydrogBoss_WalkBackward  ; 05
  
  dw KydrogBoss_TakeDamage    ; 06
  dw KydrogBoss_TauntPlayer   ; 07
  dw KydrogBoss_SummonStalfos ; 08

  dw KydrogBoss_Death         ; 09



  KydrogBoss_Init:
  {
    %PlayAnimation(0, 0, 16)
    LDA.b #$D0 : STA $0E10, X ;sets timer for start wait

    %GotoAction(1) ;Goto KydrogBoss_WalkForward
    RTS
  }

  KydrogBoss_WalkState:
  {    
  .CheckVertical
    JSL Sprite_IsBelowPlayer ; Check if sprite is below player
    TYA : CMP.b #$01 : BEQ .WalkBackwards ; If so, go to KydrogBoss_WalkBackwards
    %GotoAction(2) ; Goto KydrogBoss_WalkForward
    RTS

  .WalkBackwards
    %GotoAction(5) ; Goto KydrogBoss_WalkBackwards
    RTS

  ; ---------------------------------------------------------------------------
  .CheckHorizontal
    JSL Sprite_IsToRightOfPlayer ; Check if sprite is to the right of player
    TYA : CMP.b #$01 : BEQ .WalkLeft ; If so, go to KydrogBoss_WalkLeft
    ; JSR Sprite_DirectionToFacePlayer : TYA 
    CLC
    %GotoAction(4)
    RTS
  
  .WalkLeft
    %GotoAction(3) ; Goto KydrogBoss_WalkLeft

    RTS
  }

  KydrogBoss_WalkForward:
  {
    %PlayAnimation(0, 2, 16)

    PHX 
    JSL Sprite_CheckDamageFromPlayerLong
    %DoDamageToPlayerSameLayerOnContact()
    PLX 

    JSL Sprite_Damage_FlashLONG
    %MoveTowardPlayer(5)

    %GotoAction(1)
    RTS
  }

  KydrogBoss_WalkLeft:
  {
    %PlayAnimation(3, 5, 16)

    PHX 
    JSL Sprite_CheckDamageFromPlayerLong
    %DoDamageToPlayerSameLayerOnContact()
    PLX 
    JSL Sprite_Damage_FlashLONG

    %MoveTowardPlayer(5)

    %GotoAction(1)
    RTS
  }

  KydrogBoss_WalkRight:
  {
    %PlayAnimation(6, 8, 16)

    PHX 
    JSL Sprite_CheckDamageFromPlayerLong
    %DoDamageToPlayerSameLayerOnContact()
    PLX 

    JSL Sprite_Damage_FlashLONG
    %MoveTowardPlayer(5)

    %GotoAction(1)
    RTS
  }

  KydrogBoss_WalkBackward:
  {
    %PlayAnimation(9, 11, 16)

    PHX 
    JSL Sprite_CheckDamageFromPlayerLong
    %DoDamageToPlayerSameLayerOnContact()
    PLX 

    JSL Sprite_Damage_FlashLONG
    %MoveTowardPlayer(5)

    %GotoAction(1)
    RTS
  }

  ; ---------------------------------------------------------------------------

  KydrogBoss_TakeDamage:
  {
    %PlayAnimation(12, 14, 16)
    %DoDamageToPlayerSameLayerOnContact()
    RTS
  }

  KydrogBoss_TauntPlayer:
  {
    %PlayAnimation(15, 16, 16)
    %DoDamageToPlayerSameLayerOnContact()
    RTS
  }

  KydrogBoss_SummonStalfos:
  {
    %PlayAnimation(17, 17, 16)
    %DoDamageToPlayerSameLayerOnContact()
    RTS
  }

  KydrogBoss_Death: ;0x09
  {

    ; Change the palette to the next in the cycle for the leg
    LDA $0E60, X : INC : CMP.b #$08 : BNE .dontReset
        LDA.b #$00

    .dontReset
    STA $0E60, X

    RTS
  }

  RTS
}

;==============================================================================

Sprite_KydrogBoss_Draw:
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
db $00, $0B, $15, $1F, $27, $2D, $35, $3D, $43, $4C, $57, $66, $71, $7A, $87, $91, $99, $A1
.nbr_of_tiles
db 10, 9, 9, 7, 5, 7, 7, 5, 8, 10, 14, 10, 8, 12, 9, 7, 7, 6
.x_offsets
dw -8, 8, 8, 0, 8, 0, -8, -8, 16, 16, -8
dw -8, 8, -8, 0, 16, 16, -8, 16, 0, 8
dw -8, 8, 0, 16, -8, -8, -8, 16, 0, 8
dw 0, 0, 16, 8, 0, 16, 16, 16
dw 16, 0, 0, 16, 16, 0
dw 0, 16, 8, 16, 0, 16, 12, 0
dw 4, -4, 12, 4, -4, -4, 4, -4
dw 4, -12, 4, -12, -4, 16
dw 4, -4, 4, -4, -4, 12, 12, -4, 12
dw 0, 8, 8, 0, 0, 8, -8, -8, -8, 16, 16
dw 0, 8, 8, 0, 8, 0, 0, 8, 8, -8, -8, -8, 16, 16, 16
dw 0, 8, 8, 0, 0, 8, 16, 16, 16, -8, -8
dw -8, -8, 8, 16, 8, 8, 16, 0, 8
dw 0, -8, 8, 8, -8, -8, 0, 8, 0, 8, 16, 16, 16
dw -8, 16, 8, 8, 16, 0, 16, -8, 0, 8
dw -8, 8, -8, -8, 8, 8, -8, 16
dw -8, 8, 0, 8, -8, 8, -8, 16
dw -12, 4, 12, -4, 0, 16, 8
.y_offsets
dw -20, -20, -4, 4, 4, 12, 4, 12, 4, 12, -4
dw -19, -19, 4, 4, 4, 12, -4, -4, -3, -3
dw -20, -20, 4, 4, 4, 12, -4, -4, -4, -4
dw -20, -4, -4, -4, 4, 4, 12, -20
dw -20, -4, 4, -4, 4, -20
dw -20, -20, -4, -4, 4, 4, 12, -4
dw -20, -20, -4, -4, -4, -12, 4, 4
dw -20, -20, -4, -4, 4, 0
dw -20, -20, -4, -4, 4, 0, 8, -12, -4
dw -20, -20, -12, 0, -4, -4, -8, 0, 8, 0, -8
dw -20, -20, -12, -4, -4, 0, 8, 0, 8, 0, 8, -8, 0, 8, -8
dw -20, -20, -12, 0, -4, -4, -8, 0, 8, 0, -8
dw -24, -8, -24, -8, -8, 0, 0, 8, 8
dw -8, -24, -24, -8, -8, 0, 8, 8, 0, 0, 0, 8, -8
dw -16, -16, -16, -8, -8, 0, 0, 0, -24, -24
dw 0, 0, -16, -24, -16, -24, -16, -16
dw 0, 0, -8, -8, -24, -24, -8, -8
dw -4, -4, -20, -20, 12, 12, 12
.chr
db $87, $87, $A7, $80, $81, $A4, $93, $A3, $96, $A6, $A7
db $87, $87, $B3, $80, $92, $A2, $83, $83, $A8, $A8
db $87, $87, $80, $B2, $A1, $B1, $83, $83, $A8, $A8
db $C9, $E9, $EB, $EA, $C0, $C2, $D2, $CB
db $CE, $EC, $C3, $EE, $C5, $CC
db $C9, $CB, $FA, $FB, $C6, $C8, $D8, $E9
db $C9, $CB, $E9, $EA, $EB, $DB, $E1, $E0
db $CC, $CE, $EC, $EE, $E3, $E5
db $C9, $CB, $FA, $FB, $E6, $E8, $F8, $DE, $E9
db $89, $89, $99, $8E, $A9, $A9, $82, $92, $A2, $B3, $83
db $89, $89, $99, $A9, $A9, $8D, $9D, $8D, $9D, $8C, $9C, $83, $A1, $B1, $82
db $89, $89, $99, $8E, $A9, $A9, $83, $93, $A3, $B2, $83
db $45, $65, $45, $65, $66, $77, $75, $BD, $BE
db $6F, $4E, $4E, $6F, $47, $57, $7C, $7D, $AA, $AB, $6E, $7E, $83
db $84, $84, $85, $95, $5D, $AA, $6D, $6D, $8A, $8A
db $AC, $AE, $50, $40, $50, $40, $52, $52
db $AC, $AE, $63, $63, $42, $42, $60, $60
db $68, $6A, $4B, $49, $70, $72, $71
.properties
db $3B, $7B, $7B, $3B, $3B, $3B, $3B, $3B, $3B, $3B, $3B
db $3B, $7B, $3B, $3B, $3B, $3B, $3B, $7B, $3B, $7B
db $3B, $7B, $7B, $3B, $3B, $3B, $3B, $7B, $3B, $7B
db $3B, $3B, $3B, $3B, $3B, $3B, $3B, $3B
db $3B, $3B, $3B, $3B, $3B, $3B
db $3B, $3B, $3B, $3B, $3B, $3B, $3B, $3B
db $7B, $7B, $7B, $7B, $7B, $7B, $3B, $3B
db $7B, $7B, $7B, $7B, $3B, $3B
db $7B, $7B, $7B, $7B, $3B, $3B, $3B, $7B, $7B
db $3B, $7B, $7B, $3B, $3B, $7B, $7B, $7B, $7B, $7B, $7B
db $3B, $7B, $7B, $3B, $7B, $3B, $3B, $7B, $7B, $3B, $3B, $3B, $7B, $7B, $3B
db $3B, $7B, $7B, $7B, $3B, $7B, $7B, $7B, $7B, $7B, $3B
db $3B, $3B, $7B, $7B, $7B, $3B, $7B, $3B, $3B
db $3B, $3B, $7B, $7B, $3B, $3B, $3B, $3B, $3B, $3B, $3B, $3B, $7B
db $3B, $7B, $7B, $7B, $3B, $3B, $3B, $7B, $3B, $7B
db $3B, $3B, $3B, $3B, $7B, $7B, $3B, $7B
db $3B, $3B, $3B, $7B, $3B, $7B, $3B, $7B
db $3B, $3B, $3B, $3B, $3B, $3B, $3B
.sizes
db $02, $02, $02, $00, $00, $02, $00, $00, $00, $00, $02
db $02, $02, $00, $02, $00, $00, $00, $00, $00, $00
db $02, $02, $02, $00, $00, $00, $00, $00, $00, $00
db $02, $00, $00, $00, $02, $00, $00, $00
db $02, $02, $02, $02, $00, $02
db $02, $00, $00, $00, $02, $00, $00, $00
db $02, $00, $00, $00, $00, $00, $02, $02
db $02, $02, $02, $02, $02, $00
db $02, $00, $00, $00, $02, $00, $00, $00, $00
db $02, $00, $00, $02, $00, $00, $00, $00, $00, $00, $00
db $02, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
db $02, $00, $00, $02, $00, $00, $00, $00, $00, $00, $00
db $02, $02, $02, $00, $00, $00, $00, $00, $00
db $00, $02, $02, $00, $02, $02, $00, $00, $00, $00, $00, $00, $00
db $02, $00, $00, $00, $00, $02, $00, $00, $00, $00
db $02, $02, $02, $02, $02, $02, $00, $00
db $02, $02, $02, $00, $02, $02, $00, $00
db $02, $02, $02, $02, $00, $00, $00

}

;BA: Boomerang
;D1: Damage 1
;D2: Damage 2
;D3: Damage 3
;D4: Damage 4
;D5: Damage 5
;AR: Arrow Damage
;HS: Hookshot Damage
;BM: BombDamage
;SA: Silvers Damage
;PD: Powder Damage
;FR: Fire Rod Damage
;IR: Ice Rod Damage
;BB: Bombos Damage
;EF: Ether Damage
;QU: Quake Damage

KydrogBoss_Set_Damage:
{
    PHX
    LDX.b #$00

    .loop

    LDA .damageProperties, X : STA $7F6880, X 

    INX : CPX.b #$10 : BNE .loop

    PLX

    RTS

    .damageProperties
    db $00, $01, $01, $01, $01, $01, $01, $00, $01, $01, $00, $04, $01, $01, $00, $01
       ;BA   D1   D2   D3   D4   D5   AR   HS   BM   SA   PD   FR   IR   BB   ET   QU
}

; =============================================================================

Sprite_Damage_FlashLONG:
{
    PHB : PHK : PLB

    JSR Sprite_Damage_Flash

    PLB
    RTL
}

; =============================================================================

Sprite_Damage_Flash:
{
  LDA $0EF0, X : BEQ .dontFlash
    ; Change the palette to the next in the cycle
    LDA $0E60, X : INC : CMP.b #$08 : BNE .dontReset
      LDA.b #$00
    
  .dontReset
    STA $0E60, X

    BRA .flash

.dontFlash

  STZ $0E60, X

.flash

  RTS
}