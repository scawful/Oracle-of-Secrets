; =========================================================
; Custom Tag
; Provide custom room behavior based on room ID

; StoryState is now defined in Core/sram.asm at $7EF39E (persistent SRAM)
RoomTag_Return = $01CC5A

; override routine 0x39 "Holes(7)"
org $01CC18 : JML CustomTag ; @hook module=Dungeons name=CustomTag kind=jml target=CustomTag

; RoomTag_Holes5
org $01CC10 : JML RoomTag_MinishShutterDoor ; @hook module=Dungeons name=RoomTag_MinishShutterDoor kind=jml target=RoomTag_MinishShutterDoor

; RoomTag_Holes1 — Minish Switch (crystal toggle for Minish form only)
if !ENABLE_D3_PRISON_SEQUENCE == 1
org $01CC04 : JML RoomTag_MinishSwitch ; @hook module=Dungeons name=RoomTag_MinishSwitch kind=jml target=RoomTag_MinishSwitch
endif

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

; =========================================================
; Prison Escape Tag — D3 Kalyxo Castle
;
; Called when Link enters the escape exit room after the
; prison capture. Sets the HasEscaped flag and restores
; SpawnPoint so death/continue no longer returns to prison.
;
; Activation conditions (all must be true):
;   1. HasBeenCaptured is set (player was captured)
;   2. HasEscaped is NOT set (haven't already escaped)
;
; This is designed to be called from a room tag handler.
; The calling room tag determines WHICH room triggers escape.
; Currently wired into RoomTag_MinishShutterDoor below
; (both the Minish shutter and the escape flag can coexist
; on the same room tag since the escape room needs Minish
; doors anyway).

if !ENABLE_D3_PRISON_SEQUENCE == 1
PrisonEscape_CheckAndComplete:
{
  ; Skip if player was never captured
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_HasBeenCaptured
  BEQ .done

  ; Skip if already escaped (don't re-trigger)
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_HasEscaped
  BNE .done

  ; Check room ID — only trigger in the designated escape room
  ; TODO: Replace $00FF with actual escape room ID from yaze
  ; LDA.b RoomIndex : CMP.b #$FF : BNE .done

  ; --- Escape complete ---
  ; Set HasEscaped flag (this prevents re-triggering on subsequent frames)
  LDA.l CastleAmbushFlags : ORA.b #!CastleAmbush_HasEscaped
  STA.l CastleAmbushFlags

  ; Restore spawn point to Sanctuary (normal D3 respawn)
  LDA.b #!Spawn_Sanctuary
  STA.l SpawnPoint

  .done
  RTS
}
endif

; ========================================================
; Room tag to open shutter door when player is minish

RoomTag_MinishShutterDoor:
{
if !ENABLE_D3_PRISON_SEQUENCE == 1
  ; Check for prison escape on rooms with Minish shutter tag
  JSR PrisonEscape_CheckAndComplete
endif

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

; =========================================================
; Minish Switch — Tiny Pressure Plate (Tag 0x34 / Holes1)
;
; Toggles crystal switches ($0468) only when Link is in
; Minish form. Normal Link walks over it with no effect.
;
; Puzzle mechanic: players must transform to Minish near the
; switch tile, then the crystal state flips, opening/closing
; orange/blue barriers in the room. Reverting to normal Link
; does NOT undo the toggle — it's a permanent room state change
; (until toggled again by another Minish switch visit).
;
; Uses the same shutter display update pattern as MinishShutterDoor
; but operates on the crystal toggle ($0468 XOR) instead of
; clearing shutters.
;
; Room tag: runs every frame. The one-shot guard uses $0468
; comparison — once toggled, the new state persists and the
; tag stops retriggering until the state changes again.

if !ENABLE_D3_PRISON_SEQUENCE == 1
RoomTag_MinishSwitch:
{
  ; Only respond to Minish form
  LDA.w $02B2 : CMP.b #$05 : BNE .not_minish

    ; Check if Link is standing on the switch tile position
    ; Uses quantized tile coordinates like floor_puzzle.asm
    LDA.b $20 : CLC : ADC #$10 : AND.b #$F0 : STA.w $0224 ; Link Y → tile
    LDA.b $22 : CLC : ADC #$08 : AND.b #$F0 : STA.w $0225 ; Link X → tile

    ; Compare against the designated switch tile coordinates
    ; TODO: Set these to actual switch tile coords from yaze room design
    ; For now, use placeholder coordinates that won't accidentally match
    LDA.w $0224 : CMP.b #$FF : BNE .off_switch
    LDA.w $0225 : CMP.b #$FF : BNE .off_switch

    ; Debounce: only toggle once per step-on.
    ; $0226 reused as "on switch" flag (rooms use different tags,
    ; so no conflict with floor_puzzle which also uses $0226).
    LDA.w $0226 : BNE .not_on_switch  ; Already triggered this step
    LDA.b #$01 : STA.w $0226          ; Mark as triggered
    BRA .do_toggle

    .off_switch
    ; Link is NOT on the switch tile — clear debounce flag
    STZ.w $0226
    BRA .not_on_switch

    .do_toggle

    ; Toggle crystal state (XOR $0468 between $0000 and $0001)
    REP #$30
    LDA.w $0468 : EOR.w #$0001 : STA.w $0468
    STZ.w $068E : STZ.w $0690
    SEP #$30

    ; Trigger room display update + SFX
    LDA.b #$1B : STA.w $012F   ; Crystal toggle SFX
    LDA.b #$05 : STA.b $11     ; Request tilemap refresh
    BRA .not_minish

  .not_on_switch
  .not_minish
  JML RoomTag_Return
}
endif

pushpc
