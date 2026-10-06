; =========================================================
; Korok NPCs (Forest Spirits)
;
; NARRATIVE ROLE: Friendly forest spirits who inhabit Korok Cove and
;   East Kalyxo regions. They provide hints and side content. Multiple
;   visual variants
;   add personality to the forest areas.
;
; TERMINOLOGY: "Korok" = Korok
;   - "Makar" - Subtype 0, musician Korok (Wind Waker reference)
;   - "Hollo" - Subtype 1, potion-making Korok
;   - "Rown" - Subtype 2, gardener Korok
;
; VARIANTS (via SprSubtype, randomly assigned in Prep):
;   0x00: Makar - Uses Sprite_Korok_DrawMakar
;   0x01: Hollo - Uses Sprite_Korok_DrawHollo
;   0x02: Rown - Uses Sprite_Korok_DrawRown
;
; STATES:
;   0: Idle - Standing, show dialogue on interaction
;   1: WalkingDown - Random wander south
;   2: WalkingUp - Random wander north
;   3: WalkingLeft - Random wander west
;   4: WalkingRight - Random wander east
;   5: Liftable - Can be picked up by Link
;
; MESSAGES:
;   0x1D - Generic Korok greeting
;
; GRAPHICS:
;   Uses custom sprite sheets loaded via ApplyKorokSpriteSheets
;   Flag $0AA5 tracks if sheets are loaded
;
; MOVEMENT:
;   KorokWalkSpeed = 2
;   Random direction changes via GetRandomInt
;   SprTimerB controls direction duration
;
; RELATED:
;   - East Kalyxo region (planned Korok minigame)
;   - Korok Cove (maps 0x81-8A)
;   - Korok minigame: single special map (beat sheet, 2026-02-12 ruling)
;
; TODO:
;   - Implement Korok minigame tracking
;   - Add unique dialogue per variant
;   - Add hide-and-seek reward system
; =========================================================

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
  if !ENABLE_KOROK_POLISH == 1
    ; Load the sheets before the first draw, and again after the world map
    ; replaced them (FixMaskPaletteOnExit clears $0AA5, world_map.asm).
    JSR Sprite_Korok_EnsureSheets
  endif
  LDA $0AA5 : BEQ .done
    LDA.w SprSubtype, X : BEQ .draw_makar
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
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    if !ENABLE_KOROK_POLISH == 1
      JSR Sprite_Korok_PolishMain
    else
      JSR Sprite_Korok_Main
    endif
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Korok_Prep:
{
  PHB : PHK : PLB
  if !ENABLE_KOROK_POLISH == 1
    ; Variant from the placement, so each Korok keeps its look between
    ; visits: ((X + Y) low byte >> 5) & 3, with 3 folded to Hollo.
    ; Map $81 today: (688,480) Makar, (784,544) Hollo, (880,736) Rown on the
    ; west island; (1152,608) Hollo, (1328,592) Makar on the east island.
    LDA.w SprX, X : CLC : ADC.w SprY, X : LSR #5 : AND.b #$03
    CMP.b #$03 : BNE +
      LDA.b #$01
    +
    STA.w SprSubtype, X
    ; Home position (low bytes) for the wander leash.
    LDA.w SprX, X : STA.w SprMiscA, X
    LDA.w SprY, X : STA.w SprMiscB, X
    JSL GetRandomInt : AND.b #$3F : ORA.b #$40 : STA.w SprTimerA, X
  else
    JSL GetRandomInt : AND.b #$03 : STA.w SprSubtype, X
  endif
  PLB
  RTL
}

if !ENABLE_KOROK_POLISH == 1
; Contract: X = sprite slot, M/X 8-bit. Preserves X.
Sprite_Korok_EnsureSheets:
{
  LDA.w $0AA5 : BNE +
    PHX
    JSL ApplyKorokSpriteSheets
    PLX
    LDA.b #$01 : STA.w $0AA5
  +
  RTS
}

KorokPolishWalkSpeed = $04
KorokPolishLeash     = $10 ; px from home before the next stroll turns back

; Friendly-spirit loop: stand facing front, stroll a few pixels in one of the
; four directions on a timer, stay near home, stop at walls, talk from any
; state. SprTimerA = time left in the current state (idle or stroll).
Sprite_Korok_PolishMain:
{
  %ShowSolicitedMessage($001D) : BCC .no_talk
    STZ.w SprAction, X
    STZ.w SprFrame, X
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    LDA.b #$80 : STA.w SprTimerA, X
    RTS
  .no_talk
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Sprite_Korok_PolishIdle
  dw Sprite_Korok_PolishStrollLeft
  dw Sprite_Korok_PolishStrollRight
  dw Sprite_Korok_PolishStrollUp
  dw Sprite_Korok_PolishStrollDown

  Sprite_Korok_PolishIdle:
  {
    STZ.w SprFrame, X
    LDA.w SprTimerA, X : BNE .wait
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    JSL GetRandomInt : AND.b #$01 : BNE .vertical
      ; Signed offset from home (low bytes; the leash is far below 128 px).
      LDA.w SprX, X : SEC : SBC.w SprMiscA, X
      JSR Sprite_Korok_PolishPickDir : BCS .go_left
        LDA.b #$02 : STA.w SprAction, X
        LDA.b #$09 : STA.w SprFrame, X
        LDA.b #KorokPolishWalkSpeed : STA.w SprXSpeed, X
        BRA .start_stroll
      .go_left
        LDA.b #$01 : STA.w SprAction, X
        LDA.b #$06 : STA.w SprFrame, X
        LDA.b #-KorokPolishWalkSpeed : STA.w SprXSpeed, X
        BRA .start_stroll
    .vertical
      LDA.w SprY, X : SEC : SBC.w SprMiscB, X
      JSR Sprite_Korok_PolishPickDir : BCS .go_up
        LDA.b #$04 : STA.w SprAction, X
        LDA.b #KorokPolishWalkSpeed : STA.w SprYSpeed, X
        BRA .start_stroll
      .go_up
        LDA.b #$03 : STA.w SprAction, X
        STA.w SprFrame, X
        LDA.b #-KorokPolishWalkSpeed : STA.w SprYSpeed, X
    .start_stroll
    LDA.b #$0A : STA.w SprTimerB, X
    JSL GetRandomInt : AND.b #$1F : ORA.b #$18 : STA.w SprTimerA, X
    .wait
    RTS
  }

  Sprite_Korok_PolishStrollLeft:
  {
    %PlayAnimation(6, 8, 10)
    BRA Sprite_Korok_PolishStroll
  }

  Sprite_Korok_PolishStrollRight:
  {
    %PlayAnimation(9, 11, 10)
    BRA Sprite_Korok_PolishStroll
  }

  Sprite_Korok_PolishStrollUp:
  {
    %PlayAnimation(3, 5, 10)
    BRA Sprite_Korok_PolishStroll
  }

  Sprite_Korok_PolishStrollDown:
  {
    %PlayAnimation(0, 2, 10)
  }

  Sprite_Korok_PolishStroll:
  {
    JSL Sprite_Move
    JSL Sprite_CheckTileCollision
    LDA.w SprCollision, X : BNE .stop
    LDA.w SprTimerA, X : BNE .keep_walking
    .stop
    STZ.w SprAction, X
    STZ.w SprFrame, X
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    JSL GetRandomInt : AND.b #$3F : ORA.b #$40 : STA.w SprTimerA, X
    .keep_walking
    RTS
  }
}

; In:  A = signed offset from home on one axis (low bytes).
; Out: C set = step toward negative (left/up), C clear = positive (right/down).
;      Past the leash the step always points home; otherwise it is random.
Sprite_Korok_PolishPickDir:
{
  BMI .negative
    CMP.b #KorokPolishLeash : BCS .done
    BRA .random
  .negative
    CMP.b #-KorokPolishLeash : BCC .done
  .random
  JSL GetRandomInt : LSR A
  .done
  RTS
}
endif

KorokWalkSpeed = $02

Sprite_Korok_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

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
    LDA.b #KorokWalkSpeed : STA.w SprYSpeed, X
    JSL Sprite_Move
    LDA.w SprTimerB, X : BNE +
      JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X
    +
    RTS
  }

  Sprite_Korok_WalkingUp:
  {
    %PlayAnimation(3, 5, 10)
    LDA.b #-KorokWalkSpeed : STA.w SprYSpeed, X
    JSL Sprite_Move
    LDA.w SprTimerB, X : BNE +
      JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X
    +
    RTS
  }

  Sprite_Korok_WalkingLeft:
  {
    %PlayAnimation(6, 8, 10)
    LDA.b #KorokWalkSpeed : STA.w SprXSpeed, X
    JSL Sprite_Move
    LDA.w SprTimerB, X : BNE +
      JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X
    +
    RTS
  }

  Sprite_Korok_WalkingRight:
  {
    %PlayAnimation(9, 11, 10)
    LDA.b #-KorokWalkSpeed : STA.w SprXSpeed, X
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
  LDA .properties, X
  if !ENABLE_KOROK_POLISH == 1
    ; OBJ palette 3 holds the Korok colors in Korok Cove (same as Rown);
    ; the table's palette 5 draws Makar teal and green.
    AND.b #$F1 : ORA.b #$06
  endif
  STA ($90), Y

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
  if !ENABLE_KOROK_POLISH == 1
  ; Walk up: back view from the unused set ($44/$46/$48 + crest).
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 0, 8
  else
  dw 0, 0, 8
  dw 0, 8, 0
  dw 0, 8, 0
  endif
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
  if !ENABLE_KOROK_POLISH == 1
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  else
  dw 0, -8, -8
  dw -8, -8, 0
  dw -8, -8, 0
  endif
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
  if !ENABLE_KOROK_POLISH == 1
  db $44, $68, $69
  db $46, $78, $79
  db $48, $68, $69
  else
  db $04, $38, $39
  db $38, $39, $06
  db $38, $39, $08
  endif
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
  if !ENABLE_KOROK_POLISH == 1
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  else
  db $02, $00, $00
  db $00, $00, $02
  db $00, $00, $02
  endif
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

  if !ENABLE_KOROK_POLISH == 1
  ; Korok Hollo (polish): the unused round-mask set, tiles $40-$79.
  ; Front $40+$50 / $42 + crest $68,$78; back $44/$46/$48 + crest;
  ; left $62/$64/$66 + crest $70/$71; right = left mirrored.
  .start_index
  db $00, $02, $05, $08, $0B, $0E, $11, $14, $17, $1A, $1D, $20
  .nbr_of_tiles
  db 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2
  .x_offsets
  dw 0, 0
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 0, 8
  dw 0, 8, 0
  dw 0, 8, 0
  dw 0, 8, 0
  .y_offsets
  dw -8, 0
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  dw 0, -8, -8
  .chr
  db $40, $50
  db $42, $68, $69
  db $42, $78, $79
  db $44, $68, $69
  db $46, $78, $79
  db $48, $68, $69
  db $62, $70, $71
  db $64, $70, $71
  db $66, $70, $71
  db $62, $70, $71
  db $64, $70, $71
  db $66, $70, $71
  .properties
  db $27, $27
  db $27, $27, $27
  db $27, $27, $27
  db $27, $27, $27
  db $27, $27, $27
  db $27, $27, $27
  db $27, $27, $27
  db $27, $27, $27
  db $27, $27, $27
  db $67, $67, $67
  db $67, $67, $67
  db $67, $67, $67
  .sizes
  db $02, $02
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $00, $00
  else
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
  endif
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

  if !ENABLE_KOROK_POLISH == 1
  ; Korok Rown (polish): whole 16x24 frames from its own tiles.
  ; Front $82/$80, back $8A/$8C/$8E, left $84/$86/$88, right mirrored.
  .start_index
  db $00, $02, $04, $06, $08, $0A, $0C, $0E, $10, $12, $14, $16
  .nbr_of_tiles
  db 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  .y_offsets
  dw -8, 0
  dw -8, 0
  dw -8, 0
  dw -8, 0
  dw -8, 0
  dw -8, 0
  dw -8, 0
  dw -8, 0
  dw -8, 0
  dw -8, 0
  dw -8, 0
  dw -8, 0
  .chr
  db $82, $92
  db $80, $90
  db $82, $92
  db $8A, $9A
  db $8C, $9C
  db $8E, $9E
  db $84, $94
  db $86, $96
  db $88, $98
  db $84, $94
  db $86, $96
  db $88, $98
  .properties
  db $27, $27
  db $27, $27
  db $27, $27
  db $27, $27
  db $27, $27
  db $27, $27
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
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  else
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
  endif
}
