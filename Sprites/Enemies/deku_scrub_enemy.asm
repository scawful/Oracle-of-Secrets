
!SPRID              = $14 ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 08  ; Number of Health the sprite have
!Damage             = 04  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 00  ; Unused in this template (can be 0 to 7)
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
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_DekuScrubEnemy_Prep, Sprite_DekuScrubEnemy_Long);

Sprite_DekuScrubEnemy_Long:
{
    PHB : PHK : PLB

    JSR Sprite_DekuScrubEnemy_Draw ; Call the draw code
    JSL Sprite_CheckActive   ; Check if game is not paused
    BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

    JSR Sprite_DekuScrubEnemy_Main ; Call the main sprite code

  .SpriteIsNotActive
    PLB ; Get back the databank we stored previously
    RTL ; Go back to original code
}


Sprite_DekuScrubEnemy_Prep:
{
    PHB : PHK : PLB

    LDA SprSubtype, X : CMP #$01 : BNE .normal_scrub
      LDA #$06 : STA SprAction, X ; Pea Shot State
  .normal_scrub 

    PLB
    RTL
}

; 0-2 - Spitting
; 3-6 - Spinning
; 7-7 - Crouching
; 8-9 - Dazed
; 10-12 - Pea Shooter Anim
; 13 - Hiding
Sprite_DekuScrubEnemy_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable
  
  dw DekuScrubEnemy_Hiding
  dw DekuScrubEnemy_Attack
  dw DekuScrubEnemy_PostAttack
  dw DekuScrubEnemy_Recoil
  dw DekuScrubEnemy_Dazed
  dw DekuScrubEnemy_Subdued

  dw DekuScrubEnemy_PeaShot

  ; 0x00
  DekuScrubEnemy_Hiding:
  {
      %StartOnFrame(13)
      %PlayAnimation(13,13,1)

      JSL Sprite_PlayerCantPassThrough

      JSL Sprite_IsBelowPlayer : TYA
        CMP #$00 : BNE .is_below_player
          ; Check if the player is too close
          LDA $22 : STA $02
          LDA $20 : STA $03
          LDA SprX, X : STA $04
          LDA SprY, X : STA $05
          JSR GetDistance8bit : CMP.b #$18 : BCC .too_close
            ; The player is below the scrub, so it should pop up
            LDA #$20 : STA SprTimerA, X
            %GotoAction(1)
      .too_close
    .is_below_player
      RTS
  }

  ; 0x01
  DekuScrubEnemy_Attack:
  {
      %StartOnFrame(0)
      %PlayAnimation(0,2,8)

      JSL Sprite_PlayerCantPassThrough
      
      LDA SprTimerA, X : BNE .not_done
        JSR SpawnPeaShot
        LDA #$80 : STA SprTimerA, X
        INC.w SprAction, X
    .not_done

      LDA $22 : STA $02
      LDA $20 : STA $03
      LDA SprX, X : STA $04
      LDA SprY, X : STA $05
      JSR GetDistance8bit : CMP #$18 : BCS .not_too_close
        %GotoAction(0)
    .not_too_close
      RTS 
  }

  ; 0x02
  DekuScrubEnemy_PostAttack:
  {
    %StartOnFrame(0)
    %PlayAnimation(0,0,4)

    JSL Sprite_PlayerCantPassThrough

    LDA.w $0D10,X : STA.b $00
    LDA.w $0D30,X  : STA.b $08

    LDA.b #$04 : STA.b $02
    STZ $03

    LDA.w $0D00,X :  STA.b $01
    LDA.w $0D20,X : STA.b $09
    
    PHX 
    LDA Offspring1_Id : TAX
    JSL Sprite_SetupHitBox
    PLX

    JSL CheckIfHitBoxesOverlap : BCC .no_dano
      INC.w SprAction, X
 .no_dano
    ; Wait while the pea shot is on screen
    ; Link may redirect it towards us 
    LDA SprTimerA, X : BNE .not_done
      ; If the pea shot and deku scrub hitboxes intersect
      ; We will go to recoil 
      PHX 
      LDA Offspring1_Id : TAX
      JSL Sprite_SetupHitBox
      PLX
      JSL CheckIfHitBoxesOverlap : BCC .not_done2
        %GotoAction(4)
        RTS
      .not_done2
  
      ; However, he may also dodge it and try to attack
      ; So if he gets too close, we go back to hiding
      %GotoAction(0)
  .not_done
    RTS
  }

  ; 0x03
  DekuScrubEnemy_Recoil:
  {
      %StartOnFrame(3)
      %PlayAnimation(3,6,6)

      JSL Sprite_PlayerCantPassThrough

      ; Kill the pea shot
      PHX
      LDA Offspring1_Id : TAX
      STZ.w $0DD0, X
      PLX

      ; Play the spinning animation for a bit before proceeding
      LDA SprTimerA, X : BNE .not_done
      LDA #$40 : STA SprTimerA, X
        INC.w SprAction, X
    .not_done
      
      RTS 
  }

  ; 0x04
  DekuScrubEnemy_Dazed:
  {
      %StartOnFrame(8)
      %PlayAnimation(8,9,11)

      JSL Sprite_PlayerCantPassThrough

      LDA SprTimerA, X : BNE .not_done
        INC.w SprAction, X
    .not_done

      RTS 
  }

  ; 0x05
  DekuScrubEnemy_Subdued:
  {
    %StartOnFrame(7)
    %PlayAnimation(7,7,1)

    JSL Sprite_PlayerCantPassThrough

    RTS 
  }

  ; 0x06
  DekuScrubEnemy_PeaShot:
  {
      %StartOnFrame(10)
      %PlayAnimation(10,12,3)

      %DoDamageToPlayerSameLayerOnContact()

      JSL Sprite_MoveVert

      JSL Sprite_CheckDamageFromPlayerLong : BCC .no_damage
        ; Apply force in the opposite direction
        LDA #-16 : STA SprYSpeed, X
    .no_damage
      RTS 
  }
}

SpawnPeaShot:
{
    LDA.b #$14
    JSL Sprite_SpawnDynamically : BMI .return ;89

    LDA.b #$01 : STA $0E30, Y
    LDA.b #$06 : STA $0D80, Y

    PHX
        
    ; Spawn Location
    REP #$20
    LDA $0FD8 
    SEP #$20
    STA $0D10, Y : XBA : STA $0D30, Y

    REP #$20
    LDA $0FDA : CLC : ADC.w #$000C
    SEP #$20
    STA $0D00, Y : XBA : STA $0D20, Y

    TYX
    
    STZ $0D70, X

    LDA #$10 : STA SprYSpeed, X
    STA SprYRound, X

    STX.w Offspring1_Id
        
    PLX

  .return
    RTS
}


Sprite_DekuScrubEnemy_Draw:
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


  .start_index
    db $00, $03, $05, $07, $09, $0B, $0D, $0F, $11, $15, $19, $1A, $1B, $1C
  .nbr_of_tiles
    db 2, 1, 1, 1, 1, 1, 1, 1, 3, 3, 0, 0, 0, 1
  .x_offsets
    dw 0, 0, 8
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0, -4, 12
    dw 0, 0, -4, 12
    dw 4
    dw 4
    dw 4
    dw 0, 0
  .y_offsets
    dw -8, 8, 8
    dw -8, 0
    dw -8, 0
    dw 0, -8
    dw 0, -16
    dw 0, -8
    dw -8, 0
    dw 0, -8
    dw 0, -8, -8, 0
    dw 0, -8, 0, -8
    dw 4
    dw 4
    dw 4
    dw 0, -4
  .chr
    db $84, $B4, $B5
    db $84, $94
    db $84, $A6
    db $AC, $9C
    db $A8, $88
    db $AA, $9A
    db $98, $A8
    db $AE, $9E
    db $AC, $9C, $87, $87
    db $AC, $9C, $87, $87
    db $86
    db $96
    db $97
    db $94, $84
  .properties
    db $3B, $3B, $3B
    db $3B, $3B
    db $3B, $3B
    db $3B, $3B
    db $3B, $3B
    db $3B, $3B
    db $7B, $7B
    db $3B, $3B
    db $3B, $3B, $3B, $3B
    db $3B, $3B, $3B, $3B
    db $3B
    db $3B
    db $3B
    db $3B, $3B
  .sizes
    db $02, $00, $00
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02, $00, $00
    db $02, $02, $00, $00
    db $00
    db $00
    db $00
    db $02, $02
}