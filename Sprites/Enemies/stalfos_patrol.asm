; =========================================================
; Intro Stalfos patrol (!ENABLE_INTRO_STALFOS_PATROL)
;
; Beat 5 (story_canon_beat_sheet.md): Kydrog's Stalfos pirates patrol
; Wayward Village while Link sneaks to the village hole. The pirates are
; vanilla moving guards ($42), staged into the village's sprite loading grid
; with the phase-0 list (GameState 0 or 1; IntroPatrol_GuardCells below).
; Vanilla already gives them patrol, probe sight (180 degrees, blocked by
; solid tiles), notice, pursuit and look-around. This file changes four
; things, and only for guards loaded in the intro village (outdoors,
; SprRoom = $23, GameState < 2):
;
; 1. Look: OAM palette 6, the palette of the $3F pirate blockers, and the
;    $3F blockers' own frames (M1, 2026-09-27): the vanilla moving-guard
;    bodies are slot-0 soldier chars ($02-$22, sheet $48), which made the
;    patrol look like recolored Hyrule soldiers. Village guards now draw
;    with the TutorialGuard ($3F) frames instead: skeleton body, skull head
;    and purple shield (chars $46/$4E/$40/$42 + $00/$28/$29/$39/$2A/$3A, one
;    frame per facing, vanilla tables at $05D548-$05D63B), with a 1 px step
;    bob while moving. Other guards keep the vanilla draw.
; 2. Contact (scawful ruling 2026-09-23): half heart ($42 bump class 1),
;    normal knockback and invulnerability, then the guard stands still
;    (notice pose, facing Link) for !IntroPatrol_Recovery frames before it
;    resumes the chase. Only a hit that hurt Link starts the pause; touching
;    Link while he is still invulnerable does not extend it.
; 3. Pursuit speed !IntroPatrol_ChaseSpeed (vanilla 16 = 1 px/frame).
; 4. Sight: probes stop !IntroPatrol_SightRange px from their guard, so Link
;    can pass at a distance. A home box of +-!IntroPatrol_Leash cells
;    (16 px) keeps each guard near its spawn while it patrols.
;
; No capture, restart or scripted shove. Everything else is vanilla guard
; behavior; guards outside the village or after the intro are untouched.
;
; Hooks (vanilla bytes checked in Roms/oos168.sfc):
;   $09C512 Overworld_LoadSprites: CMP.b #$FF : BEQ .done_sprites (4 bytes)
;   $05C1BF Probe:            JSL Probe_CheckTileSolidity        (4 bytes)
;   $05C25F Guard_NotFalling: JSL Guard_ParrySwordAttacks        (4 bytes)
;   $05C263 Guard_NotFalling: JSL Sprite_CheckDamageToLink_long  (4 bytes)
;   $05C520 Guard_InPursuit:  LDA.w AppliedSpeed16,Y : JSL Sprite_ApplySpeedTowardsLink_long (7 bytes)
;   $05C683 Guard_HandleAllAnimation: JSR Guard_AnimateHead/Body/Weapon (9 bytes)
; $05C263 is also the D3 prison capture hook (custom_guard.asm); with both
; flags on, guards outside the village still go through the capture wrapper.
;
; Per-slot RAM (cleared by SpritePrep_ResetProperties on every load; the
; outdoor subtype-0 guard AI never uses them): SprMiscA $0DA0 = home X / 16,
; SprFrame $0D90 = home Y / 16 (world coordinates).
; =========================================================

!IntroPatrol_Area       = $23   ; Wayward Village (large area parent, SprRoom)
!IntroPatrol_Palette    = $06   ; OAM palette of the $3F pirate blockers
!IntroPatrol_ChaseSpeed = 14    ; vanilla AppliedSpeed16 = 16
!IntroPatrol_Recovery   = $30   ; frames of stand-still after a hit (Link: $3A)
!IntroPatrol_SightRange = 112   ; px, probe distance from its guard (0 = vanilla)
!IntroPatrol_Leash      = 3     ; home box half size in 16 px cells (0 = off)

IntroPatrol_CheckTileSolidity = $0DC26E ; Probe_CheckTileSolidity (RTL)
IntroPatrol_AppliedSpeed16    = $05C566 ; vanilla chase speed table
IntroPatrol_ApplySpeedToLink  = $06EA12 ; Sprite_ApplySpeedTowardsLink_long
IntroPatrol_CheckDamageToLink = $06F121 ; Sprite_CheckDamageToLink_long
IntroPatrol_ParrySwordAttacks = $06EB5E ; Guard_ParrySwordAttacks (RTL)

pushpc
org $05C1BF ; Probe .not_from_blind ; @hook module=Sprites name=IntroPatrol_ProbeSight kind=jsl target=IntroPatrol_ProbeSight expected_m=8 expected_x=8
  JSL IntroPatrol_ProbeSight
assert pc() == $05C1C3

org $05C25F ; Guard_NotFalling parry/contact check ; @hook module=Sprites name=IntroPatrol_GuardParry kind=jsl target=IntroPatrol_GuardParry expected_m=8 expected_x=8
  JSL IntroPatrol_GuardParry
assert pc() == $05C263

org $05C263 ; Guard_NotFalling contact check ; @hook module=Sprites name=IntroPatrol_GuardContact kind=jsl target=IntroPatrol_GuardContact expected_m=8 expected_x=8
  JSL IntroPatrol_GuardContact
assert pc() == $05C267

org $05C520 ; Guard_InPursuit chase speed ; @hook module=Sprites name=IntroPatrol_ChaseSpeed kind=jsl target=IntroPatrol_ChaseSpeed expected_m=8 expected_x=8
  JSL IntroPatrol_ChaseSpeed
  NOP #3
assert pc() == $05C527

; Guard_HandleAllAnimation after Sprite_PrepOAMCoord_Bank05: the three part
; draws. Guard_DrawShadow ($05C68C) still follows.
org $05C683 ; @hook module=Sprites name=IntroPatrol_DrawParts kind=jsl target=IntroPatrol_DrawParts expected_m=8 expected_x=8
  JSL IntroPatrol_DrawParts
  NOP #5
assert pc() == $05C68C

; Overworld_LoadSprites staging loop: LDA ($00),Y : CMP.b #$FF : BEQ .done_sprites
org $09C512 ; @hook module=Sprites name=IntroPatrol_StageGuards kind=jsl target=IntroPatrol_StageGuards expected_m=8 expected_x=16
  JSL IntroPatrol_StageGuards
assert pc() == $09C516

org $3ABE00
; Bank $3A: free run $3A8AFD-$3ABFFF (after the mask routines, before the
; opening at $3AC000).

; ---------------------------------------------------------
; Placement. The guards are staged by code, not stored in the ZScream sprite
; lists: the phase-0 list region (PC $04C881-$04D2B2) has no free bytes
; (z3ed overworld-add-sprite refuses to grow map $23's list). Staging writes
; ID+1 into the overworld loading grid ($7FDF80 + cell key) right after the
; vanilla list, so the guards load, unload and respawn like placed sprites.
; A cell already used by a placed sprite is left alone.
; Cell key (Overworld_LoadSprites $09C528): tile = local px / 16 (0-63 in a
; large area); block = (y>>4)*4 + (x>>4); key = block<<8 | (y&15)<<4 | (x&15).
macro IntroPatrol_Cell(tile_x, tile_y)
  dw ((((<tile_y>>>4)<<2)+(<tile_x>>>4))<<8)|((<tile_y>&$0F)<<4)|(<tile_x>&$0F)
endmacro

; Village map (local px, checked by walking in headless Mesen2):
; - Upper route: west stairs (x 352-416) -> south road (y 752-808) -> east
;   road. Holding down at (880,735) hops the ledge into the hole (entrance
;   $80, room $FE); the east exit beyond stays blocked by the $3F pirate at
;   (992,704). The road does not drop into the deck yard anywhere else.
; - Lower route: south field -> deck stairs (x ~815) -> cave door $1C
;   (816,768), the same room $FE.
; Home boxes (+-48 px) stay off door fronts (House $44 (592,672), Tavern
; $42 (720,640)), the ledge and the deck stairs.
IntroPatrol_GuardCells:
  %IntroPatrol_Cell(38, 49)   ; G1 south road below House $44's garden, local (608,784)
  %IntroPatrol_Cell(24, 40)   ; G2 plaza south arm by the gate arch, local (384,640)
  ; %IntroPatrol_Cell(40, 59) ; G3 (optional) south field, local (640,944): lower route
  dw $FFFF

; A = first byte of the next list record, M = 8, X/Y = 16, DB = $09.
IntroPatrol_StageGuards:
{
  CMP.b #$FF : BEQ .end_of_list
  RTL                                                   ; next record, $09C516

  .end_of_list
  LDA.w $040A : CMP.b #!IntroPatrol_Area : BNE .done
  LDA.l GameState : CMP.b #$02 : BCS .done              ; phase-0 list only
  LDY.w #$0000
  .next
  TYX
  LDA.l IntroPatrol_GuardCells+1, X : CMP.b #$FF : BEQ .done
  REP #$20
  LDA.l IntroPatrol_GuardCells, X : TAX
  SEP #$20
  LDA.l $7FDF80, X : BNE +
    LDA.b #$42+1 : STA.l $7FDF80, X
  +
  INY #2
  BRA .next

  .done
  PLA : PLA : PLA                                       ; drop the JSL return
  JML $09C55B                                           ; .done_sprites: SEP #$10 : RTS
}

; C set when slot X was loaded in the intro village. Keeps X and Y.
IntroPatrol_InContext:
{
  LDA.b $1B : BNE .no                                   ; overworld only
  LDA.w SprRoom, X : CMP.b #!IntroPatrol_Area : BNE .no
  LDA.l GameState : CMP.b #$02 : BCS .no                ; 0 start, 1 Loom Beach
  SEC
  RTS
  .no
  CLC
  RTS
}

; Vanilla guards hurt Link from two calls in Guard_NotFalling:
; Guard_ParrySwordAttacks ($05C25F; its no-parry exit runs
; Sprite_AttemptDamageToLinkWithCollisionCheck every other frame) and
; Sprite_CheckDamageToLink_long ($05C263, every fourth frame). A hit from
; either one starts the recovery pause.

; Replaces JSL Guard_ParrySwordAttacks. Also applies the look and home box
; (first call runs during SpritePrep, before the first visible frame).
IntroPatrol_GuardParry:
{
  JSR IntroPatrol_InContext : BCS .patrol
  JML IntroPatrol_ParrySwordAttacks

  .patrol
  LDA.w $0F50, X : AND.b #$F1 : ORA.b #!IntroPatrol_Palette<<1 : STA.w $0F50, X
  JSR IntroPatrol_Leash
  LDA.w $031F : ORA.w $037B : ORA.b $4D : PHA           ; 0 = Link can be hurt
  JSL IntroPatrol_ParrySwordAttacks
  PLA : BNE .done
  LDA.b $4D : BEQ .done                                 ; still not recoiling
  JSR IntroPatrol_StartRecovery
  .done
  RTL
}

; Replaces JSL Sprite_CheckDamageToLink_long. Returns C like the vanilla
; call: set = Guard_Main's alert path (action 3, $20 frames, if action < 3).
IntroPatrol_GuardContact:
{
  JSR IntroPatrol_InContext : BCS .patrol
  if !ENABLE_D3_PRISON_SEQUENCE == 1
    JML Guard_CheckDamageToLink_CaptureWrapper
  else
    JML IntroPatrol_CheckDamageToLink
  endif

  .patrol
  LDA.w $031F : ORA.w $037B : PHA                       ; 0 = Link can be hurt
  JSL IntroPatrol_CheckDamageToLink                     ; C = touching Link
  PLA                                                   ; (keeps C)
  BCC .done
  BNE .done                                             ; invulnerable: vanilla alert
  JSR IntroPatrol_StartRecovery                         ; returns C clear
  .done
  RTL
}

; The hit hurt Link: stand still in the notice pose (Guard_NoticeKouhai,
; facing Link) for !IntroPatrol_Recovery frames, then chase again. Link's
; invulnerability ($031F = $3A) outlasts the pause, so touching him during
; it cannot restart it.
IntroPatrol_StartRecovery:
{
  LDA.b #$03 : STA.w SprAction, X
  LDA.b #!IntroPatrol_Recovery : STA.w SprTimerA, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  CLC
  RTS
}

; Replaces LDA.w AppliedSpeed16,Y : JSL Sprite_ApplySpeedTowardsLink_long.
IntroPatrol_ChaseSpeed:
{
  JSR IntroPatrol_InContext
  LDA.b #!IntroPatrol_ChaseSpeed
  BCS +
    PHX : TYX
    LDA.l IntroPatrol_AppliedSpeed16, X                 ; vanilla (Y = slot & 3)
    PLX
  +
  JML IntroPatrol_ApplySpeedToLink                      ; RTLs to Guard_InPursuit
}

; Replaces JSL Probe_CheckTileSolidity. X = probe, SprMiscB = parent slot+1.
; The probe's contact test uses its cached position (SprCachedX/Y, $0FD8/
; $0FDA), so the range is measured from there to the guard. A probe beyond
; the sight range fails like a probe that hit a wall.
IntroPatrol_ProbeSight:
{
  if !IntroPatrol_SightRange != 0
    JSR IntroPatrol_InContext : BCC .vanilla
    LDA.w SprMiscB, X : DEC A : TAY
    LDA.w SprX, Y : STA.b $00
    LDA.w SprXH, Y : STA.b $01
    LDA.w SprY, Y : STA.b $02
    LDA.w SprYH, Y : STA.b $03
    REP #$20
    LDA.w SprCachedX : SEC : SBC.b $00 : BPL + : EOR.w #$FFFF : INC A : +
    CMP.w #!IntroPatrol_SightRange : BCS .too_far
    LDA.w SprCachedY : SEC : SBC.b $02 : BPL + : EOR.w #$FFFF : INC A : +
    CMP.w #!IntroPatrol_SightRange : BCS .too_far
    SEP #$20
  endif
  .vanilla
  JML IntroPatrol_CheckTileSolidity

  .too_far
  SEP #$20
  STZ.w $0FA5                                           ; not tile $09
  SEC                                                   ; -> .complete_failure
  RTL
}

; Home box. The first call (during SpritePrep, still on the spawn cell) saves
; the home cell; later, a patrolling guard outside the box turns toward home.
; Guard directions: 0 east, 1 west, 2 south, 3 north.
IntroPatrol_Leash:
{
  if !IntroPatrol_Leash != 0
    LDA.w SprMiscA, X : BNE .have_home
      JSR IntroPatrol_CellX : STA.w SprMiscA, X
      JSR IntroPatrol_CellY : STA.w SprFrame, X
      RTS
    .have_home
    LDA.w SprAction, X : CMP.b #$01 : BNE .exit        ; Guard_OnPatrol only
    JSR IntroPatrol_CellX : SEC : SBC.w SprMiscA, X
    BMI .west_of_home
      CMP.b #!IntroPatrol_Leash+1 : BCC .check_y
      LDY.b #$01 : BRA .turn
    .west_of_home
      CMP.b #$100-!IntroPatrol_Leash : BCS .check_y
      LDY.b #$00 : BRA .turn
    .check_y
    JSR IntroPatrol_CellY : SEC : SBC.w SprFrame, X
    BMI .north_of_home
      CMP.b #!IntroPatrol_Leash+1 : BCC .exit
      LDY.b #$03 : BRA .turn
    .north_of_home
      CMP.b #$100-!IntroPatrol_Leash : BCS .exit
      LDY.b #$02
    .turn
    TYA : STA.w SprMiscC, X
    .exit
  endif
  RTS
}

; World position / 16 (0-255 on the 4096 px overworld).
IntroPatrol_CellX:
{
  LDA.w SprX, X : LSR #4 : STA.b $00
  LDA.w SprXH, X : ASL #4 : ORA.b $00
  RTS
}

IntroPatrol_CellY:
{
  LDA.w SprY, X : LSR #4 : STA.b $00
  LDA.w SprYH, X : ASL #4 : ORA.b $00
  RTS
}

print "End of intro Stalfos patrol       ", pc
assert pc() <= $3AC000, "Intro Stalfos patrol crossed the opening at $3AC000"

org $3ABC00
; Pirate look (M1). Bank $3A: Part00 polish ends below $3ABC00; the patrol
; block above starts at $3ABE00.

; Call a bank-$05 RTS routine from here: its RTS lands on the RTL at $05C67F
; (Guard_HandleAllAnimation_long), which returns to ?ret. DB, X, Y and the
; scratch registers pass through unchanged.
macro IntroPatrol_Call05(addr)
  PHK
  PER ?ret-1
  PEA.w $C67E
  JML <addr>
?ret:
endmacro

IntroPatrol_AnimateHead   = $05C6DE ; Guard_AnimateHead (RTS)
IntroPatrol_AnimateBody   = $05CA09 ; Guard_AnimateBody (RTS)
IntroPatrol_AnimateWeapon = $05CB64 ; Guard_AnimateWeapon (RTS)
IntroPatrol_TGStep        = $05D548 ; Sprite_3F_TutorialGuard .anim_step (by SprMiscC)
IntroPatrol_TGOffsetX     = $05D5BF ; SpriteDraw_TutorialGuard tables, 5 objects/frame
IntroPatrol_TGOffsetY     = $05D5E7
IntroPatrol_TGChar        = $05D60F
IntroPatrol_TGFlip        = $05D623
IntroPatrol_TGSize        = $05D637

; Replaces JSR Guard_AnimateHead : JSR Guard_AnimateBody : JSR Guard_AnimateWeapon.
; $00-$0F and the OAM pointers come from Sprite_PrepOAMCoord_Bank05. DB = $05.
IntroPatrol_DrawParts:
{
  JSR IntroPatrol_InContext : BCS .pirate
  %IntroPatrol_Call05(IntroPatrol_AnimateHead)
  %IntroPatrol_Call05(IntroPatrol_AnimateBody)
  %IntroPatrol_Call05(IntroPatrol_AnimateWeapon)
  RTL
  .pirate
  JSR IntroPatrol_DrawPirate
  RTL
}

; SpriteDraw_TutorialGuard without its own Sprite_PrepOAMCoord: frame by
; facing (SprMiscC: 0 east, 1 west, 2 south, 3 north), five objects.
IntroPatrol_DrawPirate:
{
  PHX
  LDA.w SprMiscC, X : TAX
  LDA.l IntroPatrol_TGStep, X : STA.b $06
  PLX
  ASL A : ASL A : CLC : ADC.b $06 : STA.b $06   ; frame * 5

  ; Step bob: 1 px up every other 8 frames while moving.
  LDA.w SprXSpeed, X : ORA.w SprYSpeed, X : BEQ .still
  LDA.b $1A : AND.b #$08 : BEQ .still
    REP #$20 : DEC.b $02 : SEP #$20
  .still

  PHX
  LDX.b #$04
  LDY.b #$00
  .next_object
    PHX
    TXA : CLC : ADC.b $06 : PHA
    ASL A : TAX
    REP #$20
    LDA.l IntroPatrol_TGOffsetX, X : CLC : ADC.b $00 : STA.b ($90), Y
    AND.w #$0100 : STA.b $0E
    LDA.l IntroPatrol_TGOffsetY, X : CLC : ADC.b $02
    INY : STA.b ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100 : BCC .on_screen
      LDA.w #$00F0 : STA.b ($90), Y
    .on_screen
    SEP #$20
    PLX
    LDA.l IntroPatrol_TGChar, X : INY : STA.b ($90), Y
    CMP.b #$40                                   ; slot-0 chars use palette 4
    LDA.l IntroPatrol_TGFlip, X : ORA.b $05 : BCS .keep_palette
      AND.b #$F1 : ORA.b #$08
    .keep_palette
    INY : STA.b ($90), Y
    PHY
    TYA : LSR A : LSR A : TAY
    LDA.l IntroPatrol_TGSize, X : ORA.b $0F : STA.b ($92), Y
    PLY : INY
    PLX
  DEX : BPL .next_object
  PLX
  RTS
}

print "End of intro patrol pirate draw   ", pc
assert pc() <= $3ABE00, "Intro patrol pirate draw crossed the patrol block at $3ABE00"
pullpc
