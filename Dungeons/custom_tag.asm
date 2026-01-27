; =========================================================
; Custom Tag
; Provide custom room behavior based on room ID

; StoryState is now defined in Core/sram.asm at $7EF39E (persistent SRAM)
RoomTag_Return = $01CC5A

; override routine 0x39 "Holes(7)"
org $01CC18 : JML CustomTag

; RoomTag_Holes5
org $01CC10 : JML RoomTag_MinishShutterDoor

pullpc
CustomTag:
{
  PHX
  LDA $7EF3C6 : BNE .game_has_begun
    JSR HouseTag_Main
  .game_has_begun
  PLX
  JML RoomTag_Return
}

; =========================================================
; Room tag to initialize the game without the Uncle sprite.

HouseTag_Main:
{
  LDA.l StoryState   ; Must use long addressing for SRAM ($7EF39E)
  CMP.b #$03 : BCC .valid_state
    ; If state is invalid (>= 3), force reset to 0 (Intro)
    LDA.b #$00 : STA.l StoryState
  .valid_state
  ASL A : TAX
  JSR (.jump_table, X)
  RTS

  .jump_table
  dw HouseTag_TelepathicPlea
  dw HouseTag_WakeUpPlayer
  dw HouseTag_End

  HouseTag_TelepathicPlea:
  {
    LDA.b #$08 : STA.l TimeState.Hours ; Set the time to 8:00am
    LDA.b #$03 : STA.w $012C ; Play the deku tree music

    ; Set Link's coordinates to this specific position.
    LDA.b #$40 : STA $0FC2
    LDA.b #$09 : STA $0FC3
    LDA.b #$5A : STA $0FC4
    LDA.b #$21 : STA $0FC5

    ; "Accept our quest, Link!"
    LDA.b #$1F : LDY.b #$00
    JSL Sprite_ShowMessageUnconditional
    LDA.l StoryState : INC A : STA.l StoryState  ; Long addressing for SRAM

    RTS
  }

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
    LDA.l StoryState : INC A : STA.l StoryState  ; Long addressing for SRAM

    ; Legacy vanilla house flag (no uncle NPC in OOS).
    LDA $7EF3C6 : ORA.b #!Story2_LegacyHouseFlag : STA $7EF3C6

    ; Set the game mode (legacy mapping; see Core/sram.asm for current values)
    LDA #$00 : STA GameState
    LDA #$00 : STA $7EF3CC   ; disable telepathic message
    JSL Sprite_LoadGfxProperties
    RTS
  }

  HouseTag_End:
  {
    LDA $B6 : BNE .hasMetFarore
      LDA #$00 : STA.l StoryState  ; Long addressing for SRAM
    .hasMetFarore
    RTS
  }
}

print  "End of house_tag.asm              ", pc

; ========================================================
; Room tag to open shutter door when player is minish

RoomTag_MinishShutterDoor:
{
  LDA.w $02B2 : CMP.b #$05 : BNE .no_minish
    REP #$30
    LDX.w #$0000 : CPX.w $0468 : BEQ .exit
      STZ.w $0468
      STZ.w $068E : STZ.w $0690
      SEP #$30
      LDA.b #$1B : STA.w $012F
      LDA.b #$05 : STA.b $11
    .exit
    SEP #$30
  .no_minish
  JML RoomTag_Return
}
pushpc

