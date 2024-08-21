; =========================================================
; Korok Sprite 

!SPRID              = Sprite_Korok
!NbrTiles           = 08  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 01  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 03  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 01  ; 01 = your sprite continue to live offscreen
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

%Set_Sprite_Properties(Sprite_Korok_Prep, Sprite_Korok_Long) 

Sprite_Korok_Long:
{
  PHB : PHK : PLB

  LDA $0AA5 : BEQ .done
    LDA.w SprSubtype, X 
    CMP.b #$00 : BEQ .draw_makar
    CMP.b #$01 : BEQ .draw_hollo
    CMP.b #$02 : BEQ .draw_rown
    .draw_makar
      JSR Sprite_Korok_DrawMakar
      BRA .done
    .draw_hollo
      JSR Sprite_Korok_DrawHollo
      BRA .done
    .draw_rown
      JSR Sprite_Korok_DrawRown
      BRA .done
  .done
  
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_Korok_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

Sprite_Korok_Prep:
{
  PHB : PHK : PLB
  JSL GetRandomInt : AND.b #$03 : STA.w SprSubtype, X
  PLB
  RTL
}

KorokWalkSpeed = $02

Sprite_Korok_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw Sprite_Korok_Idle
  dw Sprite_Korok_WalkingDown
  dw Sprite_Korok_WalkingUp
  dw Sprite_Korok_WalkingLeft
  dw Sprite_Korok_WalkingRight
  dw Sprite_Korok_Liftable

  Sprite_Korok_Idle:
  {
    %PlayAnimation(0, 0, 10)

    LDA $0AA5 : BNE + 
      PHX
      JSL ApplyKorokSpriteSheets
      PLX
      LDA.b #$01 : STA.w $0AA5
    +
    
    %ShowSolicitedMessage($001D) : BCC .no_talk
      JSL GetRandomInt : AND.b #$03 
      STA.w SprAction, X
      RTS
    .no_talk
    JSL Sprite_PlayerCantPassThrough
    
    RTS
  }

  Sprite_Korok_WalkingDown:
  {
    %PlayAnimation(0, 2, 10)
    LDA.b #KorokWalkSpeed : STA SprYSpeed, X
    JSL Sprite_Move
    LDA.w SprTimerB, X : BNE + 
      JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X
    +
    RTS
  }

  Sprite_Korok_WalkingUp:
  {
    %PlayAnimation(3, 5, 10)
    LDA.b #-KorokWalkSpeed : STA SprYSpeed, X
    JSL Sprite_Move
    LDA.w SprTimerB, X : BNE + 
      JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X
    +
    RTS
  }

  Sprite_Korok_WalkingLeft:
  {
    %PlayAnimation(6, 8, 10)
    LDA.b #KorokWalkSpeed : STA SprXSpeed, X
    JSL Sprite_Move
    LDA.w SprTimerB, X : BNE + 
      JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X
    +
    RTS
  }

  Sprite_Korok_WalkingRight:
  {
    %PlayAnimation(9, 11, 10)
    LDA.b #-KorokWalkSpeed : STA SprXSpeed, X
    JSL Sprite_Move

    LDA.w SprTimerB, X : BNE + 
      JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X
    +
    RTS
  }

  Sprite_Korok_Liftable:
  {
    JSL Sprite_Move
    JSL Sprite_CheckIfLifted
    JSL ThrownSprite_TileAndSpriteInteraction_long
    RTS
  }

}

; =========================================================
; Korok Draw Codes

; 0-2 : Walking Down
; 3-5 : Walking Up
; 6-8 : Walking Left
; 9-11 : Walking Right

Sprite_Korok_DrawMakar:
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

  ; Korok Makar
  .start_index
  db $00, $02, $04, $07, $0A, $0D, $10, $13, $16, $19, $1C, $1F
  .nbr_of_tiles
  db 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 8, 0
  dw 0, 0, 8
  dw 0, 8, 0
  dw 0, 8, 0
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 8, 0
  dw 0, 8, 0
  dw 0, 8, 0
  .y_offsets
  dw -8, 0
  dw -8, 0
  dw -8, 8, 8
  dw 0, -8, -8
  dw -8, -8, 0
  dw -8, -8, 0
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  .chr
  db $00, $10
  db $00, $02
  db $00, $20, $21
  db $04, $38, $39
  db $38, $39, $06
  db $38, $39, $08
  db $22, $28, $29
  db $24, $28, $29
  db $26, $28, $29
  db $22, $28, $29
  db $24, $28, $29
  db $26, $28, $29
  .properties
  db $2B, $2B
  db $2B, $2B
  db $2B, $6B, $6B
  db $2B, $2B, $2B
  db $2B, $2B, $2B
  db $2B, $2B, $2B
  db $2B, $2B, $2B
  db $2B, $2B, $2B
  db $2B, $2B, $2B
  db $6B, $6B, $6B
  db $6B, $6B, $6B
  db $6B, $6B, $6B
  .sizes
  db $02, $02
  db $02, $02
  db $02, $00, $00
  db $02, $00, $00
  db $00, $00, $02
  db $00, $00, $02
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
}

Sprite_Korok_DrawHollo:
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

  ; Korok Hollo
  .start_index
  db $00, $02, $04, $06, $09, $0C, $0E, $10, $12, $14, $16, $18
  .nbr_of_tiles
  db 1, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0, 8
  dw 0, 8, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  .y_offsets
  dw 0, -8
  dw -8, 0
  dw -8, 0
  dw 0, -8, -8
  dw -8, -8, 0
  dw 0, -8
  dw 0, -8
  dw 0, -8
  dw 0, -8
  dw 0, -8
  dw 0, -8
  dw 0, -8
  .chr
  db $1A, $0A
  db $0C, $1C
  db $0A, $0E
  db $2E, $3A, $3B
  db $3A, $3B, $4C
  db $5E, $4E
  db $4A, $7E
  db $6A, $7E
  db $6C, $7E
  db $6A, $7E
  db $6C, $7E
  db $4A, $7E
  .properties
  db $2B, $2B
  db $2B, $2B
  db $2B, $2B
  db $2B, $2B, $2B
  db $2B, $2B, $2B
  db $2B, $2B
  db $2B, $2B
  db $2B, $2B
  db $2B, $2B
  db $6B, $6B
  db $6B, $6B
  db $6B, $6B
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $00, $00
  db $00, $00, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
}

Sprite_Korok_DrawRown:
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

  ; Korok Rown
  .start_index
  db $00, $02, $04, $06, $09, $0C, $0F, $11, $13, $15, $17, $19
  .nbr_of_tiles
  db 1, 1, 1, 2, 2, 2, 1, 1, 1, 1, 1, 1
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  .y_offsets
  dw -8, 0
  dw 0, -8
  dw 0, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8
  dw -8, 0
  dw 0, -8
  dw 0, -8
  dw 0, -8
  dw 0, -8
  .chr
  db $82, $92
  db $84, $82
  db $86, $82
  db $A4, $B2, $B3
  db $A6, $B2, $B3
  db $A6, $B2, $B3
  db $98, $88
  db $88, $8A
  db $8C, $88
  db $98, $88
  db $8A, $88
  db $8C, $88
  .properties
  db $27, $27
  db $27, $27
  db $27, $27
  db $27, $27, $27
  db $27, $27, $27
  db $67, $27, $27
  db $27, $27
  db $27, $27
  db $27, $27
  db $67, $67
  db $67, $67
  db $67, $67
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
}