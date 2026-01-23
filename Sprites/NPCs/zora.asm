; =========================================================
; Sea Zora NPC Handler (Multi-Variant Dispatcher)
;
; NARRATIVE ROLE: Central dispatcher for all Zora NPC variants. Routes
;   to the appropriate draw/main routines based on location and world.
;   The Zora race is divided by the Schism - Sea Zoras in Kalyxo,
;   Eon Zoras in the Abyss, and the Princess in D4 (Zora Temple).
;
; TERMINOLOGY: "Zora" = Zora (dispatcher)
;   - "Sea Zora" - Kalyxo NPCs (friendly after reconciliation)
;   - "Eon Zora" - Abyss NPCs (temporally displaced, friendly)
;   - "Zora Princess" - D4 boss room, gives Zora Mask
;   - "Eon Zora Elder" - Subtype 1, Sea Shrine guide
;
; VARIANT DETECTION (via SprMiscG):
;   0x00: Sea Zora (default) - WORLDFLAG = 0, SprSubtype = 0
;   0x01: Zora Princess - ROOM = 0x105
;   0x02: Eon Zora - WORLDFLAG = 1
;   0x03: Eon Zora Elder - SprSubtype = 1
;
; ROUTING LOGIC (Sprite_Zora_Long):
;   1. Check ROOM = 0x105 → Zora Princess (SprMiscG = 1)
;   2. Check WORLDFLAG = 1 → Eon Zora (SprMiscG = 2)
;   3. Check SprSubtype = 1 → Eon Zora Elder (SprMiscG = 3)
;   4. Default → Sea Zora (SprMiscG = 0)
;
; SEA ZORA STATES:
;   0: Forward - Face player
;   1: Right - Face right
;   2: Left - Face left
;
; SEA ZORA MESSAGES:
;   0x1A4 - Default dialogue (face forward)
;   0x1A5 - Alternative dialogue (face sideways)
;   0x1A6 - Post-D4 dialogue (Crystals bit 5 set)
;
; FLAGS READ:
;   ROOM - Check for Zora Temple boss room (0x105)
;   WORLDFLAG - Kalyxo (0) vs Eon Abyss (1)
;   Crystals bit 0x20 - D4 (Zora Temple) complete
;   SprSubtype - Elder variant detection
;
; RELATED:
;   - zora_princess.asm (D4 revelation, Zora Mask)
;   - eon_zora.asm (Abyss variant logic)
;   - eon_zora_elder.asm (Sea Shrine guide)
;   - sram_flag_analysis.md (Zora reconciliation flags)
;   - jiggly-spinning-newt.md (Zora conflict resolution plan)
; =========================================================

Sprite_Zora_Long:
{
  PHB : PHK : PLB

  ; Check what Zora we are drawing
  REP #$30
  LDA.w ROOM : CMP.w #$0105 : BNE .not_princess
    SEP #$30
    JSR Sprite_ZoraPrincess_Draw
    LDA.b #$01 : STA.w SprMiscG, X
    JMP +
  .not_princess
  LDA.w WORLDFLAG : AND.w #$00FF : BEQ .eon_draw
    SEP #$30
    JSR Sprite_EonZora_Draw
    JSL Sprite_DrawShadow
    LDA.b #$02 : STA.w SprMiscG, X
    JMP +
  .eon_draw
  SEP #$30
  LDA.w SprSubtype, X : BNE .special_zora
    JSR Sprite_Zora_Draw
    JSL Sprite_DrawShadow
    STZ.w SprMiscG, X
    JMP +
  .special_zora
  JSR Sprite_EonZoraElder_Draw
  LDA.b #$03 : STA.w SprMiscG, X
  +
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Zora_Handler
  .SpriteIsNotActive

  PLB
  RTL
}

Sprite_Zora_Prep:
{
  PHB : PHK : PLB
  PLB
  RTL
}

Sprite_Zora_Handler:
{
  LDA.w SprMiscG, X
  CMP.b #$01 : BNE .not_princess
    JSR Sprite_ZoraPrincess_Main
    RTS
  .not_princess

  JSL JumpTableLocal

  dw Sprite_Zora_Main
  dw Sprite_ZoraPrincess_Main
  dw Sprite_EonZora_Main
  dw Sprite_EonZoraElder_Main
}

Sprite_Zora_Main:
{
  JSR Zora_TrackHeadToPlayer
  JSL Sprite_PlayerCantPassThrough

  JSR Zora_HandleDialogue

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Zora_Forward
  dw Zora_Right
  dw Zora_Left

  Zora_Forward:
  {
    %PlayAnimation(0,0,10)
    RTS
  }

  Zora_Right:
  {
    %PlayAnimation(1,1,10)
    RTS
  }

  Zora_Left:
  {
    %PlayAnimation(1,1,10)
    RTS
  }
}

Zora_TrackHeadToPlayer:
{
  JSL Sprite_IsToRightOfPlayer : TAY : BEQ .right
    LDA.b #$00 : STA.w SprAction, X
    RTS
  .right
  LDA.b #$01 : STA.w SprAction, X
  RTS
}

Zora_HandleDialogue:
{
  LDA.l Crystals : AND.b #$20 : BEQ +++
    %ShowSolicitedMessage($01A6)
    JMP +
  +++
  LDA.w SprAction, X : BEQ ++
    %ShowSolicitedMessage($01A5)
  JMP +
  ++
  %ShowSolicitedMessage($01A4)
  +
  RTS
}

Sprite_Zora_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
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
  db $00, $02, $04
  .nbr_of_tiles
  db 1, 1, 1
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  .y_offsets
  dw -8, 0
  dw -8, 0
  dw -8, 0
  .chr
  db $DE, $EE
  db $DC, $EC
  db $DC, $EC
  .properties
  db $35, $35
  db $35, $35
  db $75, $75
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02
}
