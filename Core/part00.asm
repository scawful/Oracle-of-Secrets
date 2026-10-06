; =========================================================
; Part00 polish (M1): house villager lines and the Part00 checkpoint
;
; Part00 = the opening from the fall into Kalyxo through the village and the
; hole (beats 2-6, Docs/Planning/story_canon_beat_sheet.md). Canon:
; Docs/Planning/Status/decisions.org, "Arrival lines A/B/C approved, with a
; repeat line for B", "Impa is the rescue voice on black", "Part00 checkpoint
; after the village hole". Line A lives in the arrival (opening.asm).
;
; Included from Oracle_main.asm when either flag is 1. Everything here runs
; only while GameState ($7EF3C5) = 0, i.e. before Kydrog's ambush.
; State: Part00Flags ($7EF30F, Core/sram.asm).
;
; !ENABLE_PART00_ARRIVAL_LINES
;   1. A villager (sprite $07 subtype 2, Sprite_BeanVendor_Long dispatch) is
;      staged into room $104 (the house Link wakes in) with the room's
;      sprites, while GameState = 0 and Impa is not following. Art: the
;      ALTTP sweeping woman, two 16x16 parts (spriteset $4D slot 1
;      substitutes local sheet $4A only in room $104; OAM palette 3).
;   2. On the first wake (IntroState = 2) she says B ($202) once. After a
;      death respawn in the house she says B2 ($203) once. Talking to her
;      gives B on the first visit and B2 on any later visit.
;   3. Impa on the beach opens with $25 (line C) instead of the old $1C
;      ("Oh, [L]! What a surprise. It's me, Impa."), which contradicts C
;      ("You're awake. Good. I am Impa.").
;
; !ENABLE_PART00_CHECKPOINT
;   Vanilla GameOver_FadeAndRevive reloads the save from SRAM when
;   GameState = 0 (.no_progress, $09F5EB). In Oracle that is the new-file save,
;   so every Part00 death replayed the experiment scene and the arrival.
;   With the flag, a Part00 death (after the wake-up) continues without the
;   reload and without saving (as vanilla never saves at GameState 0):
;   - after Link went down the village hole (room $FE entered through
;     entrance $80): entrance $80, the hole landing in room $FE;
;   - before that: spawn point 0 (the house, room $104); Impa stops
;     following and waits on the beach again, and the villager says B2.
; =========================================================

!Part00_HouseRoom          = $0104
!Part00_RouteRoomA         = $FE      ; hole landing, then the stairs up
!Part00_RouteRoomB         = $FD      ; second route room, exit to the forest
!Part00_CheckpointEntrance = $80      ; Wayward Village hole -> room $FE (7552,8056)

!HouseVillager_Sprite  = $07          ; Sprite_BeanVendor (bean vendor / village elder)
!HouseVillager_Subtype = $02
!HouseVillager_X       = $09A8        ; world px: room $104, left of the stove
!HouseVillager_Y       = $217C
!HouseVillager_Msg_B   = $0202
!HouseVillager_Msg_B2  = $0203

Part00_ShowMessage   = $05E219        ; Sprite_ShowMessageUnconditional (A = lo, Y = hi)

pushpc

; ---------------------------------------------------------
; Underworld_LoadSprites: end-of-list test (CMP #$FF : BEQ .done)
; A = first byte of the next record, M = 8, X = 8, DB = $09.
org $09C2C3 ; @hook module=Dungeons name=Part00_RoomSprites kind=jsl target=Part00_RoomSprites expected_m=8 expected_x=8
  JSL Part00_RoomSprites
assert pc() == $09C2C7

if !ENABLE_PART00_CHECKPOINT == 1
; GameOver_FadeAndRevive .use_this_spawn: LDA.l $7EF3C5 (then BEQ .no_progress)
org $09F5D4 ; @hook module=Dungeons name=Part00_ReviveGate kind=jsl target=Part00_ReviveGate expected_m=8
  JSL Part00_ReviveGate
assert pc() == $09F5D8
endif

if !ENABLE_PART00_ARRIVAL_LINES == 1
; Initial load and transition reload, slot 1 cache assignment. M=8; preserve
; X/Y widths and registers. Keep the shared spriteset table unchanged.
org $00E1CF ; @hook module=Sprites name=HouseVillager_InitialSheet kind=jsl target=HouseVillager_LoadSheet expected_m=8
  JSL HouseVillager_LoadSheet
assert pc() == $00E1D3
org $00D739 ; @hook module=Sprites name=HouseVillager_TransitionSheet kind=jsl target=HouseVillager_LoadSheet expected_m=8
  JSL HouseVillager_LoadSheet
assert pc() == $00D73D

; Zelda_ApproachHero (Impa on the beach): LDA #$1C : LDY #$00 : JSL Sprite_ShowMessageUnconditional
org $05ED02 ; @hook module=Sprites name=Part00_ImpaGreeting kind=jsl target=Part00_ImpaGreeting expected_m=8 expected_x=8
  JSL Part00_ImpaGreeting
  NOP #4
assert pc() == $05ED0A
endif

org $3AB800
; Bank $3A: free run $3A8AFD-$3ABDFF (mask routines end $3A8AFC, intro Stalfos
; patrol at $3ABE00). This block: $3AB800-$3ABBFF.

; ---------------------------------------------------------
; Room sprite loader, end of the room's list: runs once per room load.
Part00_RoomSprites:
{
  CMP.b #$FF : BEQ .end_of_list
  RTL                                     ; next record, $09C2C7

  .end_of_list
  LDA.l GameState : BNE .done             ; Part00 only
  if !ENABLE_PART00_CHECKPOINT == 1
    JSR Part00_CheckpointTrigger
  endif
  if !ENABLE_PART00_ARRIVAL_LINES == 1
    JSR HouseVillager_Stage
  endif
  .done
  PLA : PLA : PLA                         ; drop the JSL return
  JML $09C2D4                             ; Underworld_LoadSprites .done: RTS
}

if !ENABLE_PART00_CHECKPOINT == 1
; Room $FE or $FD loaded after entering through the village hole ($80):
; the route checkpoint is reached. The cave door $1C also leads into room
; $FE, but only into its closed south-west pocket, so it does not count.
Part00_CheckpointTrigger:
{
  LDA.l IntroState : CMP.b #$02 : BCC .no ; awake (not the arrival)
  LDA.w $048F : BNE .no                   ; room being loaded (high byte)
  LDA.w $048E : CMP.b #!Part00_RouteRoomA : BEQ .route
                CMP.b #!Part00_RouteRoomB : BNE .no
  .route
  LDA.w $010E : CMP.b #!Part00_CheckpointEntrance : BNE .no
    LDA.l Part00Flags : ORA.b #!Part00_Checkpoint : STA.l Part00Flags
  .no
  RTS
}

; Replaces LDA.l $7EF3C5 at .use_this_spawn ($09F5D4). The caller follows with
; BEQ .no_progress (reload the save). Returns Z clear to skip that reload.
; M = 8. $010A was already incremented by the caller ($09F5A2).
Part00_ReviveGate:
{
  LDA.l GameState : BNE .vanilla          ; not Part00: vanilla (Z clear)
  LDA.l IntroState : CMP.b #$02 : BCC .reload ; before the wake-up: vanilla reload

  LDA.l Part00Flags : AND.b #!Part00_Checkpoint : BEQ .house
    ; Village-hole landing: continue at entrance $80 (room $FE).
    LDA.b #!Part00_CheckpointEntrance : STA.w $010E
    STZ.w $010F
    LDA.b #$01 : STA.w $010A : STA.b $1B
    STZ.w $04AA : STZ.w $04AB             ; entrance $010E, not the spawn point
    BRA .continue

  .house
    ; Before the hole: spawn point 0, the house (room $104). Impa goes back
    ; to the beach (her $76 sprite there spawns again once she is not the
    ; follower), so the villager's B2 "The beach, remember. She's waiting."
    ; is true.
    LDA.b #$00 : STA.l SpawnPoint
    LDA.l FollowerId : CMP.b #$01 : BNE +
      LDA.b #$00 : STA.l FollowerId
    +
    LDA.l Part00Flags : ORA.b #!Part00_DeathPending : STA.l Part00Flags

  .continue
  LDA.b #$02 : STA.b $B0                  ; "Continue": GameState 0 never saves
  LDA.b #$01                              ; Z clear: no save reload
  RTL

  .reload
  LDA.b #$00                              ; Z set: vanilla .no_progress
  .vanilla
  RTL
}
endif

if !ENABLE_PART00_ARRIVAL_LINES == 1
; Stage the villager in room $104 after the room's own sprites.
; X/Y free (the loader returns right after), M = 8, X = 8.
HouseVillager_Stage:
{
  LDA.w $048F : CMP.b #!Part00_HouseRoom>>8 : BNE .no
  LDA.w $048E : CMP.b #!Part00_HouseRoom&$FF : BNE .no
  LDA.l FollowerId : CMP.b #$01 : BEQ .no ; Impa follows: the villager is out
  LDX.b $02 : CPX.b #$10 : BCS .no        ; next free slot of this load

  LDA.b #$08 : STA.w SprState, X          ; init: prep runs next frame
  LDA.b #!HouseVillager_Sprite : STA.w SprType, X
  LDA.b #!HouseVillager_Subtype : STA.w SprSubtype, X
  STZ.w SprFloor, X
  LDA.b #!HouseVillager_X&$FF : STA.w SprX, X
  LDA.b #!HouseVillager_X>>8 : STA.w SprXH, X
  LDA.b #!HouseVillager_Y&$FF : STA.w SprY, X
  LDA.b #!HouseVillager_Y>>8 : STA.w SprYH, X
  LDA.b #$FF : STA.w $0BC0, X             ; no room death bit
  STZ.w $0CBA, X                          ; no key drop

  ; B was already said on an earlier visit: talking now gives B2.
  LDA.l Part00Flags : AND.b #!Part00_VillagerB : BEQ .no
    LDA.l Part00Flags : ORA.b #!Part00_Revisit : STA.l Part00Flags
  .no
  RTS
}

; Sprite_BeanVendor_Long, subtype 2. X = slot. Must RTL.
HouseVillager_Main:
{
  PHB : PHK : PLB
  JSR HouseVillager_Draw
  JSL Sprite_CheckActive : BCC .inactive
    JSL Sprite_PlayerCantPassThrough
    JSR HouseVillager_Talk
  .inactive
  PLB
  RTL
}

; Override only the house slot, preserving the shared spriteset table.
HouseVillager_LoadSheet:
{
  CMP.b #$4D : BNE .store
  PHA
  LDA.w $0AA3 : CMP.b #$4D : BNE .unchanged
  LDA.b $1B : BEQ .unchanged
  LDA.b $A0 : CMP.b #$04 : BNE .unchanged
  LDA.b $A1 : CMP.b #$01 : BNE .unchanged
  PLA
  LDA.b #$4A
  .store
  STA.l $7EC2FD
  RTL
  .unchanged
  PLA
  BRA .store
}

HouseVillager_Draw:
{
  ; Reuse the vanilla sweeping woman's two poses, remapped from slot 2
  ; to slot 1. The original art has no side-facing pose.
  LDA.b #$07 : STA.w $0F50, X ; N=1, sprite palette 3, no flip
  LDA.b #$02 : STA.b $06
  STZ.b $07
  LDA.b $1A : LSR #4 : AND.b #$01
  ASL #4
  CLC : ADC.b #.oam_groups : STA.b $08
  LDA.b #.oam_groups>>8 : ADC.b #$00 : STA.b $09
  JSL $05DF75 ; SpriteDraw_Tabulated_player_deferred (table in caller DB)
  JSL Sprite_DrawShadow
  RTS

  .oam_groups
  dw 0, -7 : db $4E, $00, $00, $02
  dw 0,  5 : db $4A, $00, $00, $02
  dw 0, -8 : db $4E, $00, $00, $02
  dw 0,  4 : db $4C, $00, $00, $02
}

HouseVillager_Talk:
{
  LDA.l IntroState : CMP.b #$02 : BCC .done ; Link still asleep

  LDA.l Part00Flags : AND.b #!Part00_VillagerB : BNE .said_b
    LDA.b #!HouseVillager_Msg_B&$FF : LDY.b #!HouseVillager_Msg_B>>8
    JSR HouseVillager_Say
    LDA.l Part00Flags : ORA.b #!Part00_VillagerB : STA.l Part00Flags
    RTS

  .said_b
  LDA.l Part00Flags : AND.b #!Part00_DeathPending : BEQ .talk
    LDA.b #!HouseVillager_Msg_B2&$FF : LDY.b #!HouseVillager_Msg_B2>>8
    JSR HouseVillager_Say
    LDA.l Part00Flags : AND.b #$FF^!Part00_DeathPending
    ORA.b #!Part00_Revisit : STA.l Part00Flags
    RTS

  .talk
  LDA.l Part00Flags : AND.b #!Part00_Revisit : BNE .b2
    %ShowSolicitedMessage(!HouseVillager_Msg_B)
    RTS
  .b2
    %ShowSolicitedMessage(!HouseVillager_Msg_B2)
  .done
  RTS
}

; Sprite_ShowMessageUnconditional calls Sprite_CancelHookshot, which puts
; Link back at $0FC2/$0FC4. Link_Main refreshes those every frame, but on
; the first frame after a death respawn they still hold the spot where Link
; died, so B2 moved him there (Mesen2 write trace on $22, 2026-09-27).
; HouseTag_TelepathicPlea sets $0FC2-$0FC5 before its message for the same
; reason. A = message low, Y = high.
HouseVillager_Say:
{
  PHA
  REP #$20
  LDA.b $22 : STA.w $0FC2
  LDA.b $20 : STA.w $0FC4
  SEP #$20
  PLA
  JSL Part00_ShowMessage
  RTS
}

; Replaces the $1C greeting in Zelda_ApproachHero. M = 8, X = 8, X = slot.
; Part00 (Impa on the beach): no greeting; next frame Zelda_DebaseAgahnim
; shows $25, whose first box is line C.
Part00_ImpaGreeting:
{
  LDA.l GameState : BEQ .skip
    LDA.b #$1C : LDY.b #$00
    JSL Part00_ShowMessage
  .skip
  RTL
}
endif

print "End of Part00 polish              ", pc
assert pc() <= $3ABC00, "Part00 polish crossed $3ABC00 (patrol pirate draw)"
pullpc
