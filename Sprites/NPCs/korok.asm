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
; STATES (Sprite_Korok_PolishMain):
;   0: Idle - face front, variant bob/hop/glance, talk turns toward Link
;   1: StrollLeft
;   2: StrollRight
;   3: StrollUp
;   4: StrollDown
;
; MESSAGES:
;   0x1D - Generic Korok greeting
;
; GRAPHICS:
;   Uses custom sprite sheets loaded via ApplyKorokSpriteSheets
;   Flag $0AA5 tracks if sheets are loaded
;
; MOVEMENT:
;   KorokPolishWalkSpeed = 4, leash 16px from the home stashed in Prep
;   SprTimerA is the idle/stroll duration; SprTimerB is the step animation
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
    ; Load the sheets before the first draw, and again after the world map
    ; replaced them (FixMaskPaletteOnExit clears $0AA5, world_map.asm).
    JSR Sprite_Korok_EnsureSheets
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
      JSR Sprite_Korok_PolishMain
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Korok_Prep:
{
  PHB : PHK : PLB
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
  PLB
  RTL
}

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

; Friendly-spirit loop: idle in place, stroll a few pixels on a timer, stay
; near home, stop at walls. Talking faces Link and holds that pose until the
; text box closes, then idle resumes. SprTimerA = time left in this state.
; SprMiscC = 1 while the talk pose is latched. $10 = $0E while text is up.
Sprite_Korok_PolishMain:
{
  %ShowSolicitedMessage($001D) : BCC .no_talk
    STZ.w SprAction, X
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    LDA.b #$01 : STA.w SprMiscC, X
    LDA.b #$10 : STA.w SprTimerD, X
    LDA.b #$80 : STA.w SprTimerA, X
    JSL Sprite_DirectionToFacePlayer
    LDA.w Sprite_Korok_FaceFrame, Y : STA.w SprFrame, X
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

  ; DirectionToFacePlayer Y: 0 right, 1 left, 2 down, 3 up.
  ; Still frame is the first pose of that walk cycle.
  Sprite_Korok_FaceFrame:
    db $09, $06, $00, $03

  Sprite_Korok_PolishIdle:
  {
    LDA.w SprMiscC, X : BEQ .free
      LDA.b $10 : CMP.b #$0E : BEQ .hold
      LDA.w SprTimerD, X : BNE .hold
        STZ.w SprMiscC, X
        STZ.w SprFrame, X
        LDA.w SprTimerA, X : BNE .flavor
          LDA.b #$18 : STA.w SprTimerA, X
        BRA .flavor
      .hold
      RTS
    .free
    LDA.w SprTimerA, X : BEQ .choose
    .flavor
    JSR Sprite_Korok_PolishIdleFlavor
    RTS
    .choose
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
        STZ.w SprFrame, X
        LDA.b #KorokPolishWalkSpeed : STA.w SprYSpeed, X
        BRA .start_stroll
      .go_up
        LDA.b #$03 : STA.w SprAction, X
        STA.w SprFrame, X
        LDA.b #-KorokPolishWalkSpeed : STA.w SprYSpeed, X
    .start_stroll
    LDA.b #$0A : STA.w SprTimerB, X
    JSL GetRandomInt : AND.b #$1F : ORA.b #$18 : STA.w SprTimerA, X
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

; Idle poses while SprTimerA is running. One branch on subtype, no tile loop.
; Makar rocks the two front frames. Hollo lifts the crest for a short hop.
; Rown glances to his left, then back to the front.
Sprite_Korok_PolishIdleFlavor:
{
  LDA.w SprSubtype, X : BEQ .makar
  CMP.b #$01 : BEQ .hollo
    LDA.b $1A : LSR #5 : AND.b #$01 : BEQ .front
      LDA.b #$06 : STA.w SprFrame, X
      RTS
  .hollo
    LDA.b $1A : AND.b #$3F : CMP.b #$08 : BCC .hop
  .front
    STZ.w SprFrame, X
    RTS
  .hop
    LDA.b #$01 : STA.w SprFrame, X
    RTS
  .makar
    LDA.b $1A : LSR #4 : AND.b #$01 : STA.w SprFrame, X
    RTS
}

; In: $02 = 16-bit screen Y from Sprite_PrepOamCoord, M/X 8-bit, X = slot.
; A 1px bob (Makar) or 2px hop (Hollo) while idling. Rown only glances.
; Skipped during stroll and while the talk pose is latched. Preserves X.
Sprite_Korok_ApplyIdleBob:
{
  LDA.w SprAction, X : BNE .done
  LDA.w SprMiscC, X : BNE .done
  LDA.w SprSubtype, X : BEQ .makar
  CMP.b #$01 : BNE .done
    LDA.b $1A : AND.b #$3F : CMP.b #$08 : BCS .done
      REP #$20
      LDA.b $02 : SEC : SBC.w #$0002 : STA.b $02
      SEP #$20
      RTS
  .makar
    LDA.b $1A : AND.b #$10 : BEQ .done
      REP #$20
      LDA.b $02 : DEC : STA.b $02
      SEP #$20
  .done
  RTS
}

; =========================================================
; Korok Draw Codes

; 0-2 : Walking Down
; 3-5 : Walking Up
; 6-8 : Walking Left
; 9-11 : Walking Right

; In: 16-bit A = screen X, Y = OAM cursor, M=16.
; Visible span for a 16px tile is [-16, 256). Farther than that, the 9-bit
; OAM X would wrap the tile onto the opposite edge of the screen.
; Out: Y points at the Y byte. C set and M=8 when the tile was hidden.
;      C clear and M=16 when X was stored ($0F = bit 8).
macro Korok_StoreScreenX()
  PHA
  CLC : ADC.w #$0010 : CMP.w #$0110 : BCC ?visible
    PLA
    SEP #$20
    LDA.b #$00 : STA ($90), Y
    INY
    LDA.b #$F0 : STA ($90), Y
    STZ.b $0E
    STZ.b $0F
    SEC
    BRA ?done
  ?visible
    PLA
    STA ($90), Y
    AND.w #$0100 : STA.b $0E
    INY
    CLC
  ?done
endmacro

Sprite_Korok_DrawMakar:
{
  JSL Sprite_PrepOamCoord : BCC .on_screen
    RTS
  .on_screen
  JSR Sprite_Korok_ApplyIdleBob
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

  LDA $00 : CLC : ADC .x_offsets, X
  %Korok_StoreScreenX() : BCS .x_hidden
    LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .tile_chr
      LDA.b #$F0 : STA ($90), Y
      STA.b $0E
    BRA .tile_chr
  .x_hidden
  .tile_chr

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  ; $27/$67 = priority 2, OBJ palette 3, nametable 1. Same row Hollo and Rown use.
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
  ; Walk-down frame 2: body, then feet $20/$21 left to right (unflipped).
  dw 0, 0, 8
  ; Walk up: back view from the unused set ($44/$46/$48 + crest).
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
  dw -8, 0
  dw -8, 8, 8
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
  db $00, $10
  db $00, $02
  db $00, $20, $21
  db $44, $68, $69
  db $46, $78, $79
  db $48, $68, $69
  db $22, $28, $29
  db $24, $28, $29
  db $26, $28, $29
  db $22, $28, $29
  db $24, $28, $29
  db $26, $28, $29
  ; OBJ palette 3 ($27/$67), the Korok Cove row. Palette 5 ($2B) draws teal.
  .properties
  db $27, $27
  db $27, $27
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
}

Sprite_Korok_DrawHollo:
{
  JSL Sprite_PrepOamCoord : BCC .on_screen
    RTS
  .on_screen
  JSR Sprite_Korok_ApplyIdleBob
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

  LDA $00 : CLC : ADC .x_offsets, X
  %Korok_StoreScreenX() : BCS .x_hidden
    LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .tile_chr
      LDA.b #$F0 : STA ($90), Y
      STA.b $0E
    BRA .tile_chr
  .x_hidden
  .tile_chr

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
}

Sprite_Korok_DrawRown:
{
  JSL Sprite_PrepOamCoord : BCC .on_screen
    RTS
  .on_screen
  JSR Sprite_Korok_ApplyIdleBob
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

  LDA $00 : CLC : ADC .x_offsets, X
  %Korok_StoreScreenX() : BCS .x_hidden
    LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .tile_chr
      LDA.b #$F0 : STA ($90), Y
      STA.b $0E
    BRA .tile_chr
  .x_hidden
  .tile_chr

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
}
