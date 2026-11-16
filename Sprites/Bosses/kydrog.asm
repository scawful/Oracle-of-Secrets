; =========================================================
; Kydrog NPC (Intro Cutscene)
;
; NARRATIVE ROLE: The Pirate King who kidnaps Farore and banishes Link
;   to the Eon Abyss. This is the NPC/cutscene version - not the boss.
;   Kydrog was a Hylian garrison knight, Farore's chosen guardian of the
;   Abyss prison; the prison corrupted him decades ago. He spares Impa as a
;   messenger to Zelda in $21. Canon: Docs/Planning/Status/decisions.org
;   ("Villain chain").
;
; TERMINOLOGY: "Kydrog" = KydrogNPC (NPC form)
;   - "Pirate King" - his self-styled title
;   - "Fallen Knight" - his true origin (revealed in Dream 1, after the
;     Shrine of Wisdom)
;   - See kydrog_boss.asm for D7 boss fight
;   - See kydreeok.asm for his Abyss form (the prison's corruption of him,
;     fought in D8); Ganon is the final fight after it
;
; TRIGGER: Spawns at Maku Tree area (LW 0x2A) during intro
;   - Despawns permanently after encounter ($7EF300 = 1)
;
; STATES:
;   0: StartCutscene - Auto-walk Link north, play music
;   1: AttractPlayer - Timer countdown, show message 0x21
;   2: SpawnOffspring - Update Farore's story flag ($B6)
;   3: WarpPlayerAway - Banish to Eon Abyss (DW 0x20)
;
; MESSAGES:
;   0x21 - Intro confrontation ("Well, well, what a surprise!")
;
; FLAGS WRITTEN:
;   $7EF300 = 1 - KydrogFaroreRemoved (prevents respawn)
;   $7EF303 = 0 - InCutScene cleared
;   $7EF3C6 |= 0x04 - OOSPROG2 bit 2 (Kydrog encounter done)
;   $7EF3CA ^= 0x40 - Toggle Dark World flag
;   $7EF3CC = 0 - Remove Impa follower
;
; FLAGS READ:
;   $7EF300 - If set, sprite is killed in Prep
;
; RELATED:
;   - farore.asm (captured by Kydrog, uses $B6 story state)
;   - impa.asm (follower removed during warp)
;   - maku_tree.asm (same area, appears after Kydrog gone)
;   - Docs/Planning/Status/decisions.org (story rulings)
;
; LORE HOOK: Message 0x21 contains "cast away to the Eon Abyss,
;   just as I was" - hints at his fallen hero origin.
;
; TODO: Implement "Fallen Knight" transition logic where his palette 
;       changes as his armor breaks (visual storytelling).
; =========================================================
; Cutscene Kydrog Sprite Properties
; =========================================================

!SPRID              = Sprite_KydrogNPC
!NbrTiles           = 6   ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 0   ; Number of Health the sprite have
!Damage             = 0   ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 0   ; Unused in this template (can be 0 to 7)
!Hitbox             = 0   ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 0   ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_Kydrog_Prep, Sprite_Kydrog_Long)

Sprite_Kydrog_Long:
{
  PHB : PHK : PLB
  if !ENABLE_GLADE_AMBUSH == 1
    LDA.w SprSubtype, X : BEQ .kydrog
      JSR KydrogStal_Draw
      JSL Sprite_CheckActive : BCC .SpriteIsNotActive
        LDA.w SprSubtype, X : CMP.b #$02 : BEQ .patrol
        JSR KydrogStal_Main
        BRA .SpriteIsNotActive
      .patrol
        JSR KydrogPatrol_Main
        BRA .SpriteIsNotActive
    .kydrog
  endif
  JSR Sprite_Kydrog_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Kydrog_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Kydrog_Prep:
{
  PHB : PHK : PLB
  LDA.l $7EF300 : BEQ .PlayIntro
    STZ.w SprState, X ; Kill the sprite
  .PlayIntro
  if !ENABLE_GLADE_AMBUSH == 1
    STZ.w SprMiscE, X ; arrival pan not shown yet
  endif
  PLB
  RTL
}

Sprite_Kydrog_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Kydrog_StartCutscene
  dw Kydrog_AttractPlayer
  dw Kydrog_SpawnOffspring
  dw Kydrog_WarpPlayerAway
  if !ENABLE_GLADE_AMBUSH == 1
    dw Kydrog_AmbushBlackout
    dw Kydrog_AmbushLight
    dw Kydrog_AmbushRise
    dw Kydrog_AmbushMosaic
    dw Kydrog_ArrivalHold
    dw Kydrog_ArrivalDim
    dw Kydrog_ArrivalCut
    dw Kydrog_ArrivalReveal
    dw Kydrog_ArrivalLook
    dw Kydrog_ArrivalPan
  endif

  Kydrog_StartCutscene:
  {
    if !ENABLE_GLADE_AMBUSH == 1
      LDA.w SprMiscE, X : BNE .arrived
        INC.w SprMiscE, X
        LDA.b #$01 : STA.w $02E4 ; Link holds still for the arrival pan
        STZ.b $49
        LDA.b #$28 : STA.w SprTimerA, X
        %GotoAction(8)
        RTS
      .arrived
    endif
    LDA #$03 : STA $012C ; Play music
    LDA.b #WALKSPEED : NOP : STA.b $57 ; Preserve the original instruction span
    LDA.b #$08 : STA.b $49 ; Auto-movement north

    LDA.b $20 ; Link's Y Position
    CMP.b #72 ; Y = 6C
    BCC .linkistoofar
      LDA.b #$80 : STA.w SprTimerA, X
      %GotoAction(1)
    .linkistoofar

    RTS
  }

  Kydrog_AttractPlayer:
  {
    LDA.w SprTimerA, X : BNE +
      LDA.b #$0C : STA $012D
      LDA #$00 : STA $7EF303
      %ShowUnconditionalMessage($21)
      %GotoAction(2)
    +
    RTS
  }

  Kydrog_SpawnOffspring:
  {
    LDA.b #$02 : STA.b $B6 ; Update story flag for Farore
    STZ.b $49 ; Stop Link from moving
    if !ENABLE_GLADE_AMBUSH == 1
      LDA.b #$01 : STA.w $02E4 ; Link holds still for the ambush
      LDA.b #$10 : STA.w SprTimerA, X
      %GotoAction(4)
      RTS
    endif
    %GotoAction(3)
    RTS
  }

  if !ENABLE_GLADE_AMBUSH == 1
  ; Lightning crack and a short blackout. Under forced blank the stalfos art
  ; replaces the two glade slots that are not Kydrog or Farore: slot 0 ($51,
  ; nothing on screen) gets pirate equipment $48, slot 3 (birds/squirrels,
  ; $42) gets pirate Stalfos $0D. The animals leave in the dark.
  Kydrog_AmbushBlackout:
  {
    LDA.w SprTimerA, X : BNE .wait
      LDA.b #$26 : STA.w $012F ; lightning
      JSR KydrogAmbush_LoadStalfosArt
      JSR KydrogAmbush_BoneStalfos
      JSR KydrogAmbush_ClearAnimals
      LDA.b #$08 : STA.w SprTimerA, X
      %GotoAction(5)
    .wait
    RTS
  }

  Kydrog_AmbushLight:
  {
    LDA.w SprTimerA, X : BNE .wait
      LDA.b #$0F : STA.b $13
      STZ.w SprMiscA, X ; Stalfos spawned so far
      LDA.b #$06 : STA.w SprTimerA, X
      %GotoAction(6)
    .wait
    RTS
  }

  ; One Stalfos every 12 frames: two flank Link, two close the path south.
  Kydrog_AmbushRise:
  {
    LDA.w SprTimerA, X : BNE .wait
      JSR KydrogAmbush_SpawnStalfos
      INC.w SprMiscA, X
      LDA.b #$0C : STA.w SprTimerA, X
      LDA.w SprMiscA, X : CMP.b #$04 : BCC .wait
        LDA.b #$30 : STA.w SprTimerA, X ; hold the ring
        STZ.w SprMiscB, X ; mosaic size
        %GotoAction(7)
    .wait
    RTS
  }

  ; Mosaic grows on BG1/BG2 every 2 frames, then the module $15 banish.
  Kydrog_AmbushMosaic:
  {
    LDA.w SprTimerA, X : BNE .wait
      LDA.b $1A : AND.b #$01 : BNE .wait
      LDA.w SprMiscB, X : CMP.b #$0F : BCS .warp
        INC A : STA.w SprMiscB, X
        ASL #4 : ORA.b #$03 : STA.b $95
        RTS
      .warp
      STZ.b $95
      %GotoAction(3)
    .wait
    RTS
  }

  ; Arrival pan. Link and Farore stand at the glade mouth, the screen dims,
  ; and the camera cuts north to Kydrog with two Stalfos patrolling the
  ; clearing. The camera then pans back south to Link and the vanilla walk-in
  ; (action 0) starts. SprMiscD = camera rows still to pan back.
  Kydrog_ArrivalHold:
  {
    LDA.w SprTimerA, X : BNE .wait
      %GotoAction(9)
    .wait
    RTS
  }

  Kydrog_ArrivalDim:
  {
    LDA.b $1A : AND.b #$01 : BNE .wait
    LDA.b $13 : BEQ .dark
      DEC.b $13
      RTS
    .dark
    %GotoAction(10)
    .wait
    RTS
  }

  ; Everything changes while the screen is black: Stalfos art, bone palette,
  ; no animals, two patrols, Link hidden, camera on Kydrog.
  Kydrog_ArrivalCut:
  {
    JSR KydrogAmbush_LoadStalfosArt
    STZ.b $13 ; LoadStalfosArt left forced blank on
    JSR KydrogAmbush_BoneStalfos
    JSR KydrogAmbush_ClearAnimals
    LDA.b #$00 : JSR KydrogPatrol_Spawn
    LDA.b #$01 : JSR KydrogPatrol_Spawn
    ; D = $E8 - .camera_y, never negative; the shown camera is $E8 - D
    REP #$20
    ; $E8 = $B8 keeps Farore (y about $1E0) inside the sprite off-screen
    ; window ($E8-$40 to $E8+$12F) and puts Kydrog (y $100) 72 px down.
    LDA.b $E8 : SEC : SBC.w #$00B8 : BCS +
      LDA.w #$0000
    +
    SEP #$20
    STA.w SprMiscD, X
    REP #$20
    AND.w #$00FF : EOR.w #$FFFF : INC A
    JSR KydrogArrival_ShiftCamera
    SEP #$20
    LDA.b #$0C : STA.b $4B ; Link invisible while the camera is away
    LDA.b #$03 : STA.w $012C ; Kydrog's theme with the reveal
    %GotoAction(11)
    RTS
  }

  Kydrog_ArrivalReveal:
  {
    LDA.b $13 : CMP.b #$0F : BCS .lit
      INC.b $13
      RTS
    .lit
    LDA.b #$40 : STA.w SprTimerA, X
    %GotoAction(12)
    RTS
  }

  Kydrog_ArrivalLook:
  {
    LDA.w SprTimerA, X : BNE .wait
      %GotoAction(13)
    .wait
    RTS
  }

  ; 1 px per frame back to Link. Link reappears once his sprite is on screen
  ; (screen y = $C8 + D, so below D = $30).
  Kydrog_ArrivalPan:
  {
    LDA.w SprMiscD, X : BEQ .done
      DEC A : STA.w SprMiscD, X
      CMP.b #$30 : BCS +
        STZ.b $4B
      +
      REP #$20
      LDA.w #$0001
      JSR KydrogArrival_ShiftCamera
      SEP #$20
      RTS
    .done
    STZ.b $4B
    STZ.w $02E4
    STZ.w $011C : STZ.w $011D
    %GotoAction(0)
    RTS
  }
  endif

  Kydrog_WarpPlayerAway:
  {
    ; TODO: Trigger "Abyss" background effect here (BG3 mosaic or HDMA scanlines)
    ;       to emphasize the banishment sequence.
    
    ; Put us in the Dark World.
    LDA $7EF3CA : EOR.b #$40 : STA $7EF3CA

    JSL Sprite_LoadGfxProperties

    STZ $037B : STZ $3C : STZ $3A : STZ $03EF

    ; Link can't move
    LDA.b #$01 : STA $02E4

    ; The module to return to is #$08 (preoverworld)
    LDA.b #$08 : STA $010C

    ; Set the map I want
    LDA.b #$20 : STA $A0 : STZ $A1

    ; Set us to the warp state
    LDA.b #$15 : STA $10

    ; Clear submodules
    STZ $11 : STZ $B0

    ; Remove Impa follower
    LDA.b #$00 : STA $7EF3CC

    ; Set the flag to remove Farore and Kydrog from Maku area
    LDA #$01 : STA.l $7EF300

    ; Set the progress flag for Impa (Zelda) in the sanctuary
    LDA $7EF3C6 : ORA.b #$04 : STA $7EF3C6

    RTS
  }
}

Sprite_Kydrog_Draw:
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
  LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
    db $00
  .nbr_of_tiles
    db 5
  .x_offsets
    dw -8, 8, 8, -8, -8, 8
  .y_offsets
    dw -12, -12, 4, 4, 20, 20
  .chr
    db $CC, $CE, $EE, $EC, $E8, $EA
  .properties
    db $39, $39, $39, $39, $39, $39
}

if !ENABLE_GLADE_AMBUSH == 1
; =========================================================
; Forest Glade ambush (!ENABLE_GLADE_AMBUSH)
; Pirate Stalfos art and poses come from the mirror experiment scene
; (Core/Cutscene/experiment.asm Exp_Poses, Exp_LoadSheets, Exp_BoneStalfos).
; There the Stalfos sheet sits in slot 1; here it sits in slot 3, so every
; Stalfos body char moves up by $80. Equipment chars ($00-$3F) stay in slot 0.
; =========================================================

KydrogAmbush_LoadSprGfx = $00E583 ; RTS; Y = sheet, X = buffer page, $02 = buffer bank
KydrogAmbush_Bank00_RTL = $00E33A ; RTL in bank $00

; Forced blank now and in any lag NMI, then decompress and upload two sheets
; with the vanilla InitializeTilesets loader. The caller restores $13.
KydrogAmbush_LoadStalfosArt:
{
  PHX
  LDA.b #$80 : STA.b $13 : STA.w $2100
  PHB
  LDA.b #$00 : PHA : PLB ; sheet pointer tables are DB-relative
  LDA.b #$80 : STA.w $2115
  LDX.b #$00
  .next
    PHX
    STZ.w $2116
    LDA.l .vram_hi, X : STA.w $2117
    LDA.l .sheets, X : TAY
    LDA.b #$7E : STA.b $02
    LDX.b #$78 ; buffer $7E7800
    PHK : PEA.w .return-1
    PEA.w KydrogAmbush_Bank00_RTL-1
    JML KydrogAmbush_LoadSprGfx
    .return
    SEP #$30
    PLX
    INX : CPX.b #$02 : BCC .next
  PLB
  PLX
  RTS

  .sheets
  db $48, $0D ; pirate equipment, pirate Stalfos
  .vram_hi
  db $50, $5C ; slot 0 ($5000), slot 3 ($5C00)
}

; Sprite palette 6 (CGRAM row 14): gold to bone greys, same rule as
; Exp_BoneStalfos. Squirrels also use row 14; they are gone by now.
KydrogAmbush_BoneStalfos:
{
  PHX
  REP #$30
  LDX.w #$001E
  .loop
    LDA.l $7EC6C0, X : AND.w #$001F : STA.b $00         ; R
    LDA.l $7EC6C0, X : LSR #5 : AND.w #$001F : STA.b $02 ; G
    LDA.l $7EC6C0, X : XBA : LSR #2 : AND.w #$001F       ; B
    CLC : ADC.w #$0004 : STA.b $04
    LDA.b $00 : CMP.b $04 : BCC .next
    LDA.b $02 : CMP.b $04 : BCC .next
    LDA.b $00 : CLC : ADC.b $02 : LSR A : INC A
    CMP.w #$0020 : BCC .lum
      LDA.w #$001F
    .lum
    STA.b $06
    DEC A : DEC A : XBA : ASL #2 : STA.b $04            ; (L-2) << 10
    LDA.b $06 : ASL #5 : ORA.b $06 : ORA.b $04
    STA.l $7EC6C0, X
    .next
    DEX : DEX : BPL .loop
  SEP #$30
  INC.b $15 ; upload CGRAM
  PLX
  RTS
}

; Birds ($59) and squirrels ($5A) used slot 3; remove them with the art.
KydrogAmbush_ClearAnimals:
{
  PHX
  LDX.b #$0F
  .loop
    LDA.w SprState, X : BEQ .next
    LDA.w SprType, X : CMP.b #$59 : BEQ .clear
    CMP.b #$5A : BNE .next
    .clear
    STZ.w SprState, X
    .next
    DEX : BPL .loop
  PLX
  RTS
}

; Spawn Stalfos number SprMiscA at an offset from Link.
KydrogAmbush_SpawnStalfos:
{
  LDA.b #Sprite_KydrogNPC
  JSL Sprite_SpawnDynamically : BMI .no_slot
    LDA.b #$01 : STA.w SprSubtype, Y
    LDA.b #$00 : STA.w SprAction, Y : STA.w SprFrame, Y ; low pose
    LDA.b #$05 : STA.w SprTimerA, Y
    LDA.b $EE : STA.w SprFloor, Y
    PHX
    LDA.w SprMiscA, X : TAX
    LDA.l .pose, X : STA.w SprMiscC, Y
    LDA.l .dx, X : STA.b $04 : STZ.b $05 : BPL +
      DEC.b $05
    +
    LDA.l .dy, X : STA.b $06 : STZ.b $07 : BPL +
      DEC.b $07
    +
    REP #$20
    LDA.b $22 : CLC : ADC.b $04 : STA.b $04
    LDA.b $20 : CLC : ADC.b $06 : STA.b $06
    SEP #$20
    LDA.b $04 : STA.w SprX, Y
    LDA.b $05 : STA.w SprXH, Y
    LDA.b $06 : STA.w SprY, Y
    LDA.b $07 : STA.w SprYH, Y
    PLX
    LDA.b #$22 : STA.w $012E ; rattle
  .no_slot
  RTS

  ; west flank, east flank, south-west, south-east
  .dx   db -40,  40, -20,  20
  .dy   db   0,   0,  36,  36
  .pose db   4,   3,   5,   5 ; KydrogStal_Draw pose ids
}

; A (16-bit, signed) is added to every vertical camera register, the same
; set D4Zora_ClampRoomCamera moves. Link and sprites keep their positions.
; Overworld module 09/0B pushes $E8/$E6 before Sprite_Main and pops them
; after ($02A48B/$02A4BE), so sprite writes to $E8 are lost. The shown BG
; scroll and the sprite camera are $E8 + $011C (the quake offset), so the
; cut and pan move $011C. Link's own scroll and triggers stay untouched.
KydrogArrival_ShiftCamera:
{
  CLC : ADC.w $011C : STA.w $011C
  RTS
}

; Spawn patrol A (0-1). X = Kydrog. Patrols are subtype 2 and keep Kydrog's
; slot in SprMiscB.
KydrogPatrol_Spawn:
{
  PHA
  LDA.b #Sprite_KydrogNPC
  JSL Sprite_SpawnDynamically
  PLA : STA.b $0F
  TYA : BMI .no_slot
    LDA.b #$02 : STA.w SprSubtype, Y
    TXA : STA.w SprMiscB, Y
    LDA.b $EE : STA.w SprFloor, Y
    PHX
    LDX.b $0F
    LDA.l .x, X : STA.w SprX, Y
    LDA.l .y, X : STA.w SprY, Y
    LDA.b #$01 : STA.w SprYH, Y
    LDA.b #$00 : STA.w SprXH, Y : STA.w SprAction, Y
    LDA.l .dir, X : STA.w SprMiscD, Y
    LDA.l .pose, X : STA.w SprFrame, Y
    PLX
  .no_slot
  RTS

  ; y is $100 + value: $154 = 340, $180 = 384
  .x    db 72, 184
  .y    db $54, $80
  .dir  db 0, 1 ; 0 east, 1 west
  .pose db 4, 3
}

; Patrol: walk the clearing x 72-184 while Kydrog holds the camera (actions
; 10-12), otherwise stand at the tree line (x 64 or 192) facing the path.
KydrogPatrol_Main:
{
  LDY.w SprMiscB, X
  LDA.w SprAction, Y : CMP.b #10 : BCC .retreat
  CMP.b #13 : BCS .retreat
  LDA.b $1A : LSR #3 : AND.b #$01 : STA.w SprHeight, X ; step bob
  LDA.b $1A : AND.b #$01 : BNE .done
  LDA.w SprMiscD, X : BNE .west
    INC.w SprX, X
    LDA.w SprX, X : CMP.b #184 : BCC .face
      INC.w SprMiscD, X
    BRA .face
  .west
    DEC.w SprX, X
    LDA.w SprX, X : CMP.b #73 : BCS .face
      STZ.w SprMiscD, X
  .face
  LDY.w SprMiscD, X
  LDA.w .walk_pose, Y : STA.w SprFrame, X
  .done
  RTS

  .retreat
  STZ.w SprHeight, X
  LDA.w SprX, X : CMP.b #128 : BCS .east_side
    CMP.b #64 : BEQ .west_post
    BCC .step_east
    DEC.w SprX, X
    LDA.b #$03 : STA.w SprFrame, X ; walking west
    RTS
  .step_east
    INC.w SprX, X
    RTS
  .west_post
    LDA.b #$04 : STA.w SprFrame, X ; face east, toward the path
    RTS
  .east_side
    CMP.b #192 : BEQ .east_post
    BCS .step_west
    INC.w SprX, X
    LDA.b #$04 : STA.w SprFrame, X ; walking east
    RTS
  .step_west
    DEC.w SprX, X
    RTS
  .east_post
    LDA.b #$03 : STA.w SprFrame, X ; face west, toward the path
    RTS

  .walk_pose db 4, 3
}

; Stalfos child: low (5 frames), mid (5 frames), then its facing pose.
KydrogStal_Main:
{
  LDA.w SprTimerA, X : BNE .wait
  LDA.w SprAction, X : BNE .stand
    INC.w SprAction, X
    LDA.b #$01 : STA.w SprFrame, X ; mid
    LDA.b #$05 : STA.w SprTimerA, X
    RTS
  .stand
  LDA.w SprMiscC, X : STA.w SprFrame, X
  .wait
  RTS
}

; Pose ids: 0 low, 1 mid, 2 front, 3 west, 4 east, 5 north.
; Piece: dx, dy, char, prop, size (Exp_Poses order, chars $40+ moved +$80).
KydrogStal_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer
  PHX
  LDA.w SprFrame, X : TAX
  LDA.l .start, X : TAX
  LDA.l .data, X : STA.b $06
  INX
  LDY.b #$00
  .next
    LDA.l .data, X : STA.b $08 : STZ.b $09 : BPL +
      DEC.b $09
    +
    LDA.l .data+1, X : STA.b $0A : STZ.b $0B : BPL +
      DEC.b $0B
    +
    REP #$20
    LDA.b $00 : CLC : ADC.b $08 : STA ($90), Y
    AND.w #$0100 : STA.b $0E
    INY
    LDA.b $02 : CLC : ADC.b $0A : STA ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .on_screen_y
      LDA.b #$F0 : STA ($90), Y
    .on_screen_y
    INY
    LDA.l .data+2, X : STA ($90), Y
    INY
    LDA.l .data+3, X : STA ($90), Y
    PHY
    TYA : LSR #2 : TAY
    LDA.l .data+4, X : ORA.b $0F : STA ($92), Y
    PLY : INY
    TXA : CLC : ADC.b #$05 : TAX
    DEC.b $06 : BNE .next
  PLX
  RTS

  .start
  db .low-.data, .mid-.data, .front-.data, .west-.data, .east-.data, .north-.data

  .data
  .low
  db 1 : db 0,2,$C0,$3D,$02
  .mid
  db 3 : db -6,2,$00,$39,$02, 0,-4,$C0,$3D,$02, 4,6,$C6,$7D,$02
  .front
  db 5 : db 2,12,$29,$39,$00, -6,12,$28,$39,$00, -6,-4,$00,$39,$02, 0,-10,$C0,$3D,$02, 4,0,$C6,$7D,$02
  .west
  db 5 : db -7,5,$3A,$39,$00, -7,-3,$2A,$39,$00, -7,-11,$39,$39,$00, 0,-9,$C2,$3D,$02, 0,0,$CE,$3D,$02
  .east
  db 5 : db 15,5,$3A,$79,$00, 15,-3,$2A,$79,$00, 15,-11,$39,$79,$00, 0,-9,$C2,$7D,$02, 0,0,$CE,$7D,$02
  .north
  db 5 : db 0,-9,$C4,$3D,$02, 4,0,$E4,$7D,$02, -4,0,$E4,$3D,$02, 14,5,$38,$79,$00, 6,-11,$26,$39,$02
}
endif
