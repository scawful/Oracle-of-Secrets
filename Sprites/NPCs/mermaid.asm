; =========================================================
; Mermaid and Maple NPC

!SPRID              = $F0 ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 02  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
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

%Set_Sprite_Properties(Sprite_Mermaid_Prep, Sprite_Mermaid_Long)


Sprite_Mermaid_Long:
{
  PHB : PHK : PLB

  LDA.w SprMiscE, X : BEQ .MermaidDraw
  CMP.b #$02 : BEQ .LibrarianDraw
    JSR Sprite_Maple_Draw
    JMP .Continue
  .LibrarianDraw
  JSR Sprite_Librarian_Draw
  JMP .Continue
  .MermaidDraw
  JSR Sprite_Mermaid_Draw ; Call the draw code
  .Continue
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_Mermaid_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}


Sprite_Mermaid_Prep:
{
  PHB : PHK : PLB
  LDA.b #$40 : STA.w SprTimerA, X
  STZ.w SprMiscE, X
  LDA.b #$07 : STA.w SprHitbox, X
  LDA.w SprSubtype, X : CMP.b #$01 : BNE +
    ; Maple Sprite
    LDA.b #$01 : STA.w SprMiscE, X
    LDA.b #$03 : STA.w SprAction, X
  +
  CMP.b #$02 : BNE ++
    ; Librarian Sprite
    LDA.b #$02 : STA.w SprMiscE, X
    LDA.b #$06 : STA.w SprAction, X
  ++
  PLB
  RTL
}


Sprite_Mermaid_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable
  dw MermaidWait
  dw MermaidDive
  dw MermaidSwim

  dw MapleIdle
  dw Maple_BoughtMilkBottle
  dw Maple_NotEnoughRupees

  dw LibrarianIdle

  MermaidWait:
  {
    %PlayAnimation(0,0, 20)
    JSL Sprite_PlayerCantPassThrough

    %ShowMessageOnContact($047) : BCC .didnt_talk
      LDA.w SprTimerA, X : BNE +
      LDA.b #$20 : STA.w SprTimerA, X
      INC.w SprAction, X
      +
    .didnt_talk
    RTS
  }

  MermaidDive:
  {
    %PlayAnimation(1,2, 14)

    LDA.w SprX, X : INC : STA.w SprX, X
    LDA.w SprTimerA, X : BNE +
      INC.w SprAction, X
      
      LDA.b #$04 : STA.w SprTimerA, X
    +

    RTS
  }

  MermaidSwim:
  {
    %PlayAnimation(3,3,20)
    JSL Sprite_Move
    LDA.b #10 : STA.w SprXSpeed, X
    JSR SpawnSplash
      LDA.w SprMiscD,X : BNE ++
        STZ.w SprState, X
      ++

      LDA.w SprTimerA, X : BEQ +
        

        LDA.b #-10 : STA.w SprYSpeed, X
        STZ.w SprXSpeed, X
        LDA.b #$01 : STA.w SprMiscD, X
        LDA.b #$04 : STA.w SprTimerA, X
      +
      


    RTS
  }

  MapleIdle:
  {
    %PlayAnimation(0,1,16)
    JSL Sprite_PlayerCantPassThrough

    %ShowSolicitedMessage($0187) : BCC .didnt_talk
      LDA $1CE8 : BNE .player_said_no
        %GotoAction(4)
        RTS

      .player_said_no
      %ShowUnconditionalMessage($018B) ; Come back again!
    .didnt_talk
    RTS
  }

  Maple_BoughtMilkBottle:
  {
    REP #$20
    LDA.l $7EF360
    CMP.w #$13 ; 30 rupees
    SEP #$30
    BCC .not_enough_rupees

      LDA.l $7EF35C : CMP.b #$02 : BEQ .bottle1_available
      LDA.l $7EF35D : CMP.b #$02 : BEQ .bottle2_available
      LDA.l $7EF35E : CMP.b #$02 : BEQ .bottle3_available
      LDA.l $7EF35F : CMP.b #$02 : BEQ .bottle4_available
        %ShowUnconditionalMessage($033)
        %GotoAction(3)
        RTS

      .bottle1_available
      LDA.b #$0A : STA.l $7EF35C
      JMP .finish_storage

      .bottle2_available
      LDA.b #$0A : STA.l $7EF35D
      JMP .finish_storage
      
      .bottle3_available
      LDA.b #$0A : STA.l $7EF35E
      JMP .finish_storage

      .bottle4_available
      LDA.b #$0A : STA.l $7EF35F
      .finish_storage

      REP #$20
      LDA.l $7EF360
      SEC
      SBC.w #$1E ; Subtract 30 rupees
      STA.l $7EF360
      SEP #$30

      %ShowUnconditionalMessage($0188) ; Thank you!
      %GotoAction(3)
      RTS
    .not_enough_rupees
    %GotoAction(6)
    RTS
  }

  Maple_NotEnoughRupees:
  {
    %ShowUnconditionalMessage($0189) ; You don't have enough rupees!
    RTS
  }

  LibrarianIdle:
  {
    %PlayAnimation(0,1,16)
    JSL Sprite_PlayerCantPassThrough
    LDA.l $7EF34E : BNE + 
      %ShowSolicitedMessage($0127)
    +
    RTS
  }


Librarian_CheckForAllMaps:
{
  LDA.l DNGMAP1
  CMP.l #$FFFC
  BNE .not_all_maps
  LDA.l DNGMAP2
  CMP.l #$FFFF
  BEQ .all_maps
  .not_all_maps
  CLC
  RTS
  .all_maps
  SEC
  RTS
}

Sprite_Mermaid_Draw:
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
  db $00, $02, $04, $05
  .nbr_of_tiles
  db 1, 1, 0, 1
  .x_offsets
  dw 0, 0
  dw 4, -4
  dw 0
  dw 0, 0
  .y_offsets
  dw -8, 8
  dw -4, -4
  dw 4
  dw 0, 8
  .chr
  db $0E, $2E
  db $0B, $0C
  db $2B
  db $09, $29
  .properties
  db $79, $79
  db $79, $79
  db $79
  db $79, $79
  .sizes
  db $02, $02
  db $02, $02
  db $02
  db $02, $02
}

Sprite_Maple_Draw:
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

  LDA $00 : STA ($90), Y
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
      
  LDA #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
      
  PLY : INY
      
  PLX : DEX : BPL .nextTile

  PLX

  RTS


  .start_index
  db $00, $02
  .nbr_of_tiles
  db 1, 1
  .y_offsets
  dw -8, 0
  dw 0, -8
  .chr
  db $13, $23
  db $25, $15
  .properties
  db $39, $39
  db $39, $39
}

Sprite_Librarian_Draw:
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
  db $00, $02
  .nbr_of_tiles
  db 1, 1
  .x_offsets
  dw 0, 0
  dw 0, 0
  .y_offsets
  dw 0, -10
  dw -9, 0
  .chr
  db $2A, $24
  db $24, $28
  .properties
  db $39, $39
  db $39, $39
  .sizes
  db $02, $02
  db $02, $02
}