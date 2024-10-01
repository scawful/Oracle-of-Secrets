; =========================================================
; Room tag to initialize the game without the Uncle sprite.

StoryState = $7C

org $01CC18 ; override routine 0x39 "Holes(7)"
  JML HouseTag

org $01CC5A
  HouseTag_Return:

pullpc
HouseTag:
{
  PHX
  LDA $7EF3C6 : BNE .game_has_begun
    JSR HouseTag_Main
  .game_has_begun
  PLX
  JML HouseTag_Return
}

; =========================================================

HouseTag_Main:
{
  LDA.w StoryState

  JSL $008781

  dw HouseTag_TelepathicPlea
  dw HouseTag_WakeUpPlayer
  dw HouseTag_End
}

; =========================================================

HouseTag_TelepathicPlea:
{
  LDA #$08 : STA $7EE000 ; Set the time to 8:00am
  LDA.b #$03 : STA.w $012C ; Play the deku tree music

  ; -------------------------------
  ; Set Link's coordinates to this specific position.
  LDA.b #$40 : STA $0FC2
  LDA.b #$09 : STA $0FC3

  LDA.b #$5A : STA $0FC4
  LDA.b #$21 : STA $0FC5

  ; "Accept our quest, Link!"
  LDA.b #$1F : LDY.b #$00
  JSL $05E219 ; Sprite_ShowMessageUnconditional
  INC.b StoryState

  RTS
}

; =========================================================

HouseTag_WakeUpPlayer:
{
  ; Lighten the screen gradually and then wake Link up partially
  LDA $1A : AND.b #$03 : BNE .delay
    LDA $9C : CMP.b #$00 : BEQ .colorTargetReached

      DEC $9C : DEC $9D

  .delay
  RTS

  .colorTargetReached

  INC $0D80, X
  INC $037D
  INC $037C
  LDA.b #$57 : STA $20
  LDA.b #$21 : STA $21
  ;LDA.b #$01 : STA $02E4

  STZ $02E4 ; awake from slumber
  INC.b StoryState

  ; Make it so Link's uncle never respawns in the house again.
  LDA $7EF3C6 : ORA.b #$10 : STA $7EF3C6

  ; Set the game mode
  LDA #$00 : STA $7EF3C5   ; (0 - intro, 1 - pendants, 2 - crystals)
  LDA #$00 : STA $7EF3CC   ; disable telepathic message
  JSL Sprite_LoadGfxProperties
  RTS
}

; =========================================================

HouseTag_End:
{
  LDA $B6 : BNE .hasMetFarore
    LDA #$00 : STA.w StoryState

  .hasMetFarore
  RTS
}

print  "End of house_tag.asm              ", pc

pushpc

; =========================================================
; Fixed color fade-in effect
; TODO: Investigate if this is the best way to fix this.

; Module06_UnderworldLoad
org $028364
{
  #_028364: LDA.b #$00 ; Fixed color RGB: #808000
  #_028366: STA.b $9C

  #_028368: LDA.b #$00
  #_02836A: STA.b $9D

  #_02836C: LDA.b #$00
  #_02836E: STA.b $9E
  #_028370: LDA.b #$00
  #_028372: STA.l $7EC005
  #_028376: STA.l $7EC006

  #_02837A: JSL $079A2C ; Link_TuckIntoBed
}

