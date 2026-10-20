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

; Only the first four bytes of the twelve-byte RoomTag_Holes2 body change.
assert read2($01C2C5) == $CC89, "Tag $24 vector no longer names RoomTag_Holes2"
assert read4($01CC89) == $CC2030C2, "RoomTag_Holes2 body moved"
assert read4($01CC8D) == $A0F690CD, "RoomTag_Holes2 body moved"
assert read4($01CC91) == $D9800005, "RoomTag_Holes2 body moved"
; RoomTag_Holes2 (tag $24) — Somaria socket door
org $01CC89 : JML RoomTag_SomariaSocketDoor ; @hook module=Dungeons name=RoomTag_SomariaSocketDoor kind=jml target=RoomTag_SomariaSocketDoor expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
assert pc() == $01CC8D

; Vanilla draw culling must not delete a grounded cube holding a tag $24 plate.
; Keep the six-byte deletion pair together; $08E724 is another branch target.
assert read3($08E731) == $06469C, "Somaria culled pressure clear moved"
assert read3($08E734) == $0C4A9E, "Somaria culled actor clear moved"
assert read1($08E737) == $8A, "Somaria culled cleanup continuation moved"
assert read1($08E74B) == $60, "Somaria draw return moved"
org $08E731 ; @hook module=Dungeons name=SomariaSocket_CulledBlock kind=jml target=SomariaSocket_CulledBlock expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=6
  JML SomariaSocket_CulledBlock
  NOP #2
assert pc() == $08E737

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

if !ENABLE_PART0_STORM == 1
    ; Part 0 storm starts with the new game (Overworld/storm.asm). Runs in
    ; both the arrival and the flags-off intro; cleared when Link is back on
    ; Kalyxo after the Abyss.
    LDA.l StoryProgress2 : ORA.b #!Story2_Part0Storm : STA.l StoryProgress2
endif

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
if !ENABLE_ORIGINS_MINISH_PUZZLE == 1
    ; Shrine of Origins (room $05): open the west shutter only once Minish
    ; Link reaches the NE chamber (QUADH $A9 = right, QUADV $AA = top), so
    ; the player sees it open. Other rooms keep the old behavior.
    LDA.b $A1 : BNE .quadrant_ok
    LDA.b $A0 : CMP.b #$05 : BNE .quadrant_ok
if !ENABLE_ORIGINS_PEARL_RETURN_FIX == 1
      ; The shutter closes again in the NW chest chamber. Once the Pearl
      ; is earned, Minish Link must also be able to reopen it from there.
      LDA.l MoonPearl : BNE .quadrant_ok
endif
      LDA.b $A9 : BEQ .no_minish
      LDA.b $AA : BNE .no_minish
    .quadrant_ok
endif
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
; Minish Switch — Tiny Pressure Plate (Tag 0x23 / Holes1)
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

; =========================================================
; Somaria Socket Door — hold door held only by a Somaria block
;
; Dispatcher-connected as room tag $24 through the RoomTag_Holes2 gateway
; ($01CC89). No audited base room header assigns tag $24.
;
; Reversible like RoomTag_SwitchTrigger_HoldDoor ($01C541): open while a
; live Somaria block rests on a pressure switch, closed otherwise. Its other
; inputs are not read: $0642 (sprites, ice block, followers), the push-block
; switch latch ($0500 state 5 / $0466) and Link's floor test.
;
; Entry contract: JML from the $01CC89 gateway, reached by
; Underworld_HandleRoomTags ($01C2FD) through JSR (.vectors, X):
;   M=8 X=8 (re-asserted here), D=$0000, DBR with WRAM $0000-$1FFF mirrored
;   (bank $00-$3F/$80-$BF), $11=$00, $0E = tag slot (0=$AE, 1=$AF).
;   Stack top is the JSR return into bank $01; this routine pushes nothing.
; Exit: JML RoomTag_Return ($01CC5A, a bare RTS) with M=8 X=8, stack as on
; entry. A, X and P are clobbered; Y, $0E, $AE and $AF are untouched.
; Writes happen only when the door state changes: $0468 (16-bit, 0=open
; 1=closed), $068E and $0690 (16-bit zero), $012F=$25 when opening only,
; $11=$05.
;
; A block qualifies only when the Ancilla2C_SomariaBlock .run_trigger gates
; ($08E3A3) held and SomariaBlock_CheckForSwitch ($08E75C) found all four
; probe points on switch tiles at its last update:
;   $1B!=0, $0646!=0, $0308 bit7 clear, $03F4==0, and for a slot X in 0-4:
;   $0C4A,X==$2C, $0394,X==0 (spawn delay over), $03C5,X==0, $0380,X==0,
;   $03DB,X==4, $029E,X in {$00,$FF}.
; $0646 alone is not trusted: pit deletion ($08E5D8) frees the slot without
; clearing it, and .bouncing only clears it for the $02EC slot. Ancillae run
; in Sprite_Main after room tags, so the state is one frame old, as in vanilla.
; Rooms with Somaria transit lines ($03F4) never open, and the door closes
; while Link carries anything ($0308 bit7) because no switch check runs then.
;
; Room contract: the block's switch probe reads its own floor ($0C7C,X at
; $088A56), and the tag acts room-wide like the vanilla hold door. Before a
; header assigns tag $24, the room needs exactly one accepted pressure plate
; across all layers, one owner of the shutter state, and no transit lines.
; The caller must keep the vanilla once-per-frame, $11==$00 room-tag cadence.
;
; Allocation: fixed bank $2C tail $2CFD00-$2CFDFF, so the bank $2C
; continuation used by the code before and after this file is unchanged.
; Neighbors: main bank $2C stream below (ended at $2CE113 in the control
; build), CustomRoomCollision at $2CFE00-$2CFEFF, JumpTableLocal_Guard at
; $2CFF00. This org places code only; the $01CC89 gateway is its only entry.

pushpc
org $2CFD00
RoomTag_SomariaSocketDoor:
{
  SEP #$30
  LDA.b $1B : BEQ .closed
  LDA.w $0646 : BEQ .closed
  BIT.w $0308 : BMI .closed
  LDA.w $03F4 : BNE .closed

  LDX.b #$04
  .next_slot
    LDA.w $0C4A, X : CMP.b #$2C : BNE .skip_slot
    LDA.w $0394, X : BNE .skip_slot
    LDA.w $03C5, X : BNE .skip_slot
    LDA.w $0380, X : BNE .skip_slot
    LDA.w $03DB, X : CMP.b #$04 : BNE .skip_slot
    LDA.w $029E, X : BEQ .held
    CMP.b #$FF : BEQ .held
  .skip_slot
    DEX : BPL .next_slot

  .closed
  REP #$30
  LDX.w #$0001
  BRA .update

  .held
  REP #$30
  LDX.w #$0000

  .update
  CPX.w $0468 : BEQ .exit
    STX.w $0468
    STZ.w $068E : STZ.w $0690
    SEP #$30
    CPX.b #$00 : BNE .no_sfx
      LDA.b #$25 : STA.w $012F
    .no_sfx
    LDA.b #$05 : STA.b $11
  .exit
  SEP #$30
  JML RoomTag_Return
}

; JML entry from $08E731: M/X=8, DBR=$08, X=original ancilla slot.
; The draw routine has already restored X; its inherited JSR return stays put.
; Preserve A/P, X/Y, DBR and D. All absolute data accesses use the WRAM mirror.
; Only the original cull/delete path changes: lift, split, pit and room unload
; still remove the block normally. Fizz shares the draw routine, so require $2C.
SomariaSocket_CulledBlock:
{
  PHP : PHA
  CPX.b #$05 : BCS .vanilla
  LDA.w $001B : BEQ .vanilla
  LDA.w $00AE : CMP.b #$24 : BEQ .tag24
  LDA.w $00AF : CMP.b #$24 : BNE .vanilla
  .tag24
  LDA.w $0C4A,X : CMP.b #$2C : BNE .vanilla
  LDA.w $0646 : BEQ .vanilla
  BIT.w $0308 : BMI .vanilla
  LDA.w $03F4 : BNE .vanilla
  LDA.w $0394,X : ORA.w $03C5,X : ORA.w $0380,X : BNE .vanilla
  LDA.w $03DB,X : CMP.b #$04 : BNE .vanilla
  LDA.w $029E,X : BEQ .keep
  CMP.b #$FF : BNE .vanilla
  .keep
  PLA : PLP
  JML $08E74B
  .vanilla
  PLA : PLP
  STZ.w $0646
  STZ.w $0C4A,X
  JML $08E737
}
assert pc() <= $2CFE00 ; do not overlap CustomRoomCollision
pullpc

pushpc
