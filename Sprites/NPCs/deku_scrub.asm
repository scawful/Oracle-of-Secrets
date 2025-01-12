; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_DekuScrubNPCs
!NbrTiles           = 06  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this DekuScrub (can be 0 to 7)
!Hitbox             = 03  ; 00 to 31, can be viewed in sprite draw tool
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

%Set_Sprite_Properties(Sprite_DekuScrub_Prep, Sprite_DekuScrub_Long)

Sprite_DekuScrub_Long:
{
  PHB : PHK : PLB
  JSR Sprite_DekuScrub_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_DekuScrub_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_DekuScrub_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X

  ; Peacetime Deku Scrub NPCs
  LDA.b AreaIndex : CMP.b #$2E : BNE .check_next
    ; Deku Butler
    LDA.b #$07 : STA.w SprAction, X
    JMP +
  .check_next
  CMP.b #$2F : BNE .continue
    LDA.b #$08 : STA.w SprAction, X
    JMP +
  .continue

  LDA.w SprSubtype, X : CMP.b #$01 : BEQ .DekuButler
                        CMP.b #$02 : BEQ .DekuPrincess
  LDA.l $7EF301 : BEQ +
    LDA.b #$04 : STA.w SprAction, X
    JMP +
  .DekuButler
    LDA.b #$05 : STA.w SprAction, X
    JMP ++
  .DekuPrincess
    LDA.b #$06 : STA.w SprAction, X
    ++
    ; Check if tail palace is cleared
    LDA.l Crystals : AND #$10 : BEQ +
      STZ.w SprState, X
  +
  PLB
  RTL
}

Sprite_DekuScrub_Main:
{
  LDA.w SprAction, X
  JSL   UseImplicitRegIndexedLocalJumpTable

  dw EstadoInactivo
  dw QuiereCuracion
  dw DarMascara
  dw Regalo
  dw Withered
  dw DekuButler
  dw DekuPrincess

  dw DekuButler_Peacetime
  dw DekuPrinces_Peacetime

  EstadoInactivo:
  {
    %PlayAnimation(0, 1, 16)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($140) : BCC .no_hablaba
      %GotoAction(1)
    .no_hablaba
    RTS
  }

  QuiereCuracion:
  {
    %PlayAnimation(0, 1, 16)
    LDA $FE : BEQ .ninguna_cancion
      STZ $FE
      LDA.b #$C0 : STA.w SprTimerD, X
      %GotoAction(2)
    .ninguna_cancion
    RTS
  }

  DarMascara:
  {
    %PlayAnimation(0, 1, 16)
    LDA.w SprTimerD, X : BNE +
      %ShowUnconditionalMessage($141)
      LDA.b #$C0 : STA.w SprTimerD, X
      %GotoAction(3)
    +
    RTS
  }

  Regalo:
  {
    LDA.w SprTimerD, X : BNE +
      LDY   #$11 : STZ $02E9     ; Give the Deku Mask
      JSL   Link_ReceiveItem
      LDA.b #$01 : STA.l $7EF301
      %GotoAction(4)
    +
    RTS
  }

  Withered:
  {
    %PlayAnimation(2, 2, 10)
    RTS
  }

  DekuButler:
  {
    %PlayAnimation(3, 3, 10)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($080)
    RTS
  }

  DekuPrincess:
  {
    %PlayAnimation(4, 4, 10)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($0C3)
    RTS
  }

  DekuButler_Peacetime:
  {
    %StartOnFrame(3)
    %PlayAnimation(3, 3, 10)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($1B9) : BCC +
      LDA.b #$02 : STA.l MapIcon
    +
    RTS
  }

  DekuPrinces_Peacetime:
  {
    %StartOnFrame(4)
    %PlayAnimation(4, 4, 10)
    JSL Sprite_PlayerCantPassThrough
    %ShowSolicitedMessage($1BA) : BCC +
      LDA.b #$02 : STA.l MapIcon
    +
    RTS
  }
}

Sprite_DekuScrub_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

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
  LDA .properties, X : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
    db $00, $04, $08, $0C, $10
  .nbr_of_tiles
    db 3, 3, 3, 3, 3
  .x_offsets
    dw 4, 4, -4, -4
    dw 4, -4, -4, 4
    dw -8, -8, 8, 8
    dw -4, 4, -4, 4
    dw -4, -4, 4, 4
  .y_offsets
    dw 4, -4, -4, 4
    dw 4, 4, -4, -4
    dw 4, -12, -12, 4
    dw -12, -12, 4, 4
    dw 4, -12, 4, -12
  .chr
    db $2E, $0E, $0E, $2E
    db $2C, $2C, $0C, $0C
    db $20, $00, $02, $22
    db $04, $05, $24, $25
    db $27, $07, $27, $07
  .properties
    db $3B, $7B, $3B, $7B
    db $3B, $7B, $3B, $7B
    db $3B, $3B, $3B, $3B
    db $3B, $3B, $3B, $3B
    db $3B, $3B, $7B, $7B
  .sizes
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02

; .start_index
;   db $00, $04
; .nbr_of_tiles
;   db 3, 3
; .x_offsets
;   dw 4, -4, -4, 4
;   dw 4, -4, -4, 4
; .y_offsets
;   dw 0, 0, -8, -8
;   dw 0, 0, -8, -8
; .chr
;   db $2C, $2C, $0C, $0C
;   db $2E, $2E, $0E, $0E
; .properties
;   db $33, $73, $33, $73
;   db $33, $73, $33, $73
; .sizes
;   db $02, $02, $02, $02
;   db $02, $02, $02, $02
}

