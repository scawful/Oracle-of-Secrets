; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_VillageDog
!NbrTiles           = 05  ; Number of tiles used in a frame (4 body max + 1 shadow)
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this VillageDog (can be 0 to 7)
!Hitbox             = 09  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 01  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 01  ; 01 = will check both layer for collision
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

%Set_Sprite_Properties(Sprite_VillageDog_Prep, Sprite_VillageDog_Long)

Sprite_VillageDog_Long:
{
  PHB : PHK : PLB
  LDA.w WORLDFLAG : BEQ .village
    JSR Sprite_EonDog_Draw
    JMP .shadow
  .village
  JSR Sprite_VillageDog_Draw
  BCS .after_draw
  .shadow
  JSL Sprite_DrawShadow
  .after_draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_VillageDog_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_VillageDog_Prep:
{
  PHB : PHK : PLB
  LDA.w WORLDFLAG : BEQ .village
    LDA.b #$07 : STA.w SprAction, X
    LDA.b #$40 : STA.w SprTimerA, X
    BRA .done
  .village
  TXA : AND.b #$03 : STA.w SprMiscD, X ; Stagger initial idle phase per slot
  TXA : ASL #4 : ORA.b #$28 : STA.w SprTimerD, X
  LDA.b $1B : BNE .done ; Coat variation is Overworld outdoors only
  LDA.w $0AAE : CMP.b #$0A : BNE .done ; Only use SP6 cream-taupe when Village Aux2 ($0A) is loaded
    JSL GetRandomInt : AND.b #$01 : BEQ .done
      LDA.b #$0A : STA.w SprMiscG, X ; Palette 6 ($3D/$7D) cream-taupe coat (never SP7 Link palette)
  .done
  PLB
  RTL
}

HandleTossedDog:
{
  LDA.w SprHeight, X : BEQ .on_ground
    DEC.w SprHeight, X
  .on_ground
  RTS
}

LiftOrTalk:
{
  LDA.w $02B2
  CMP.b #$03 : BEQ .talk
  CMP.b #$05 : BEQ .talk
    ; Grounded states only check lift here; Dog_Tossed owns ThrownSprite Z-physics
    ; so cosmetic perk-up / Ocarina hops in SprHeight never bounce SprTimerF.
    JSL Sprite_CheckIfLifted
    RTS
  .talk
  JSL VillageDog_FormInteractLong
  RTS
}

; In: A = 8-bit axis radius ($01-$7F). Out: C set if |Link - SprCached| < r on both axes.
Dog_NearPlayer:
{
  STZ.b $07 : STA.b $06
  ASL A : STZ.b $09 : STA.b $08
  REP #$20
  LDA.b $22 : SEC : SBC.w SprCachedX : CLC : ADC.b $06 : CMP.b $08 : BCS .far
  LDA.b $20 : SEC : SBC.w SprCachedY : CLC : ADC.b $06 : CMP.b $08 : BCS .far
  SEP #$21
  RTS
  .far
  SEP #$20
  CLC
  RTS
}

; In: Y = animation slot (0..7). Immediately clamps stale frames on direction flip.
Dog_PlayAnim:
{
  LDA.w .start, Y : CMP.w SprFrame, X : BEQ .in_range : BCC .check_hi
  .reset
    LDA.w .start, Y : STA.w SprFrame, X
    LDA.w .wait, Y : STA.w SprTimerB, X
    RTS
  .check_hi
  LDA.w .end, Y : CMP.w SprFrame, X : BCC .reset
  .in_range
  LDA.w SprTimerB, X : BNE .done
    LDA.w SprFrame, X : INC A
    CMP.w .end, Y : BCC .store : BEQ .store
      LDA.w .start, Y
    .store
    STA.w SprFrame, X
    LDA.w .wait, Y : STA.w SprTimerB, X
  .done
  RTS
  .start : db 0, 11, 2, 5, 0, 2,  0, 11
  .end   : db 1, 12, 4, 7, 1, 3,  1, 12
  .wait  : db 8,  8, 6, 6, 8, 8,  4,  4
}

Sprite_VillageDog_Main:
{
  JSL RichardDog_Main : BCC .richard_vanilla ; Overworld/richard_quest.asm
    RTS
  .richard_vanilla
  ; Bug fix (2026-09-26 playtest): vanilla CarriedSprite_CheckForThrow
  ; (usdasm bank_06 $06DF6D) restores SprState to 9, sets SprTimerF ($0F80,X,
  ; Z velocity) to +4 and SprXSpeed/SprYSpeed to a pot-throw speed, and
  ; SpriteModule_Carried then runs this Main on the same frame. SprHeight is
  ; still the carry height (16), not 0. The old dog resumed whatever action it
  ; was lifted in; the wag/look actions never call Sprite_Move, so the dog
  ; dropped straight down with no travel (Mesen2 trace, 2026-09-26).
  ; SprTimerF is 0 on every grounded frame (ThrownSprite_TileAndSpriteInteraction
  ; zeroes it on landing), so nonzero outside Dog_Tossed means a fresh throw.
  LDA.w SprTimerF, X : BEQ .not_fresh_toss
    LDA.w SprAction, X : CMP.b #$09 : BEQ .not_fresh_toss
      ; Halve the vanilla pot-throw speed (signed, sign-preserving shift) --
      ; a dog toss should travel a dog-sized hop, not a rock-shatter distance.
      LDA.w SprXSpeed, X : CMP.b #$80 : ROR A : STA.w SprXSpeed, X
      LDA.w SprYSpeed, X : CMP.b #$80 : ROR A : STA.w SprYSpeed, X
      ; Upward hop from the carry height (replaces the vanilla +4).
      LDA.b #$20 : STA.w SprTimerF, X
      LDA.b #$09 : STA.w SprAction, X ; -> Dog_Tossed
  .not_fresh_toss

  ; Ocarina happy-dance trigger (fresh cast frame $03F0=$80, not Wolf dig, OW module $09)
  LDA.w SprAction, X
  CMP.b #$07 : BCC .ocarina_eligible
  CMP.b #$0B : BCC .no_ocarina ; wake Action $0B (Sleep) and $0C (SniffPlay), skip Eon ($07-$08) & Tossed ($09) & HappyDance ($0A)
  .ocarina_eligible
  LDA.b $10 : CMP.b #$09 : BNE .no_ocarina
  LDA.w $02B2 : CMP.b #$03 : BEQ .no_ocarina
  LDA.b $3A : AND.b #$40 : BEQ .no_ocarina
  LDA.w $03F0 : CMP.b #$80 : BEQ .try_ocarina
  BRA .no_ocarina
  .try_ocarina
  LDA.b #$60 : JSR Dog_NearPlayer : BCC .no_ocarina
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    STZ.w SprMiscF, X
    LDA.b #$50 : STA.w SprTimerD, X
    %GotoAction($0A)
  .no_ocarina

  LDA.w SprAction, X
  JSL   JumpTableLocal

  dw Dog_Handler              ; 00
  dw Dog_LookLeftAtLink       ; 01
  dw Dog_LookRightAtLink      ; 02
  dw Dog_MoveLeftTowardsLink  ; 03
  dw Dog_MoveRightTowardsLink ; 04
  dw Dog_WagTailLeft          ; 05
  dw Dog_WagTailRight         ; 06

  dw EonDog_Handler           ; 07
  dw EonDog_Right             ; 08
  dw Dog_Tossed                ; 09
  dw Dog_HappyDance            ; 0A
  dw Dog_Sleep                 ; 0B
  dw Dog_SniffPlay             ; 0C

  ; 00 - Calm idle (sit, head-tilt, short stroll, daytime sniff, night sleep) unless Link approaches within 88px.
  ; Wolf Link ($02B2 == #$03) within 40px immediately triggers a friendly pack tail-wag.
  Dog_Handler:
  {
    JSR HandleTossedDog
    LDA.w $02B2 : CMP.b #$03 : BNE .check_perk
      LDA.b #$28 : JSR Dog_NearPlayer : BCC .check_perk
        STZ.w SprXSpeed, X
        STZ.w SprYSpeed, X
        LDA.b #$50 : STA.w SprTimerD, X
        JSL Sprite_IsToRightOfPlayer : TYA : BEQ .wolf_wag_r
          %GotoAction(5)
          JMP LiftOrTalk
        .wolf_wag_r
        %GotoAction(6)
        JMP LiftOrTalk
    .check_perk
    LDA.w SprTimerC, X : BNE .calm
    ; Throttle outer 88px proximity check to once per 4 frames per slot while calm.
    TXA : EOR.b $1A : AND.b #$03 : BNE .calm
    LDA.b #$58 : JSR Dog_NearPlayer : BCC .calm
      STZ.w SprXSpeed, X
      STZ.w SprYSpeed, X
      LDA.b #$04 : STA.w SprHeight, X
      LDA.b #$18 : STA.w SprTimerD, X
      JSL Sprite_IsToRightOfPlayer : TYA : BEQ .perk_right
        %GotoAction(1)
        JMP LiftOrTalk
      .perk_right
      %GotoAction(2)
      JMP LiftOrTalk
    .calm
    JSR Dog_CalmIdle
    JMP LiftOrTalk
  }

  ; 01
  Dog_LookLeftAtLink:
  {
    %SetFrame(9)
    LDA.b #$03 : BRA Dog_LookCommon
  }

  ; 02
  Dog_LookRightAtLink:
  {
    %SetFrame(10)
    LDA.b #$04
  }
  Dog_LookCommon:
  {
    PHA
    JSR HandleTossedDog
    JSR LiftOrTalk
    PLA
    LDY.w SprTimerD, X : BNE +
      STA.w SprAction, X
      LDA.b #$58 : STA.w SprTimerD, X
    +
    RTS
  }

  ; 03
  Dog_MoveLeftTowardsLink:
  {
    LDY.b #$02 : BRA Dog_MoveCommon
  }

  ; 04
  Dog_MoveRightTowardsLink:
  {
    LDY.b #$03
  }
  Dog_MoveCommon:
  {
    JSR Dog_PlayAnim
    JSR HandleTossedDog
    LDA.b #$16
    LDY.w $02B2 : CPY.b #$05 : BNE +
      LDA.b #$18 ; Minish Link: stop slightly wider so dog doesn't bowl over tiny Link
    +
    JSR Dog_NearPlayer : BCC .keep_moving
      STZ.w SprXSpeed, X
      STZ.w SprYSpeed, X
      LDA.b #$50 : STA.w SprTimerD, X
      JSL Sprite_IsToRightOfPlayer : TYA : BEQ .wag_r
        %GotoAction(5) : RTS
      .wag_r
      %GotoAction(6) : RTS

    .keep_moving
    JSL Sprite_CheckTileCollision
    LDA.w $0E70, X : BNE .settle
    LDA.w SprTimerD, X : BEQ .settle
      LDA.b #$0C
      LDY.w $02B2 : CPY.b #$05 : BNE +
        LDA.b #$08 ; Gentle curious trot toward Minish Link
      +
      JSL Sprite_ApplySpeedTowardsPlayer
      STZ.b $06 : STZ.b $07
      JSL Sprite_MoveLong
      JSR LiftOrTalk
      ; Sync facing to horizontal velocity so circling Link never moonwalks.
      LDA.w SprXSpeed, X : BEQ .stay
        BPL .face_r
          %GotoAction(3) : RTS
        .face_r
          %GotoAction(4)
      .stay
      RTS

    .settle
      STZ.w SprXSpeed, X
      STZ.w SprYSpeed, X
      STZ.w SprMiscD, X
      LDA.b #$80 : STA.w SprTimerC, X
      LDA.b #$40 : STA.w SprTimerD, X
      %GotoAction(0)
      RTS
  }

  ; 05
  Dog_WagTailLeft:
  {
    LDY.b #$00 : BRA Dog_WagCommon
  }

  ; 06
  Dog_WagTailRight:
  {
    LDY.b #$01
  }
  Dog_WagCommon:
  {
    JSR Dog_PlayAnim
    JSR LiftOrTalk
    JSR HandleTossedDog
    JSL Sprite_IsToRightOfPlayer : TYA : BEQ .face_r
      %GotoAction(5) : BRA .chk_done
    .face_r
      %GotoAction(6)
    .chk_done
    LDA.w SprTimerD, X : BNE +
      STZ.w SprMiscD, X
      LDA.b #$90 : STA.w SprTimerC, X
      LDA.b #$48 : STA.w SprTimerD, X
      %GotoAction(0)
    +
    RTS
  }

  EonDog_Handler:
  {
    LDY.b #$04 : JSR Dog_PlayAnim
    JMP EonDog_Walk
  }

  EonDog_Right:
  {
    LDY.b #$05 : JSR Dog_PlayAnim
    JMP EonDog_Walk
  }

  ; 09 - airborne after a real toss (see the fresh-toss detection above).
  ; Same order as vanilla ThrowableScenery_InteractWithSpritesAndTiles
  ; ($06E164): move XY, tile collision, then ThrownSprite_TileAndSpriteInteraction,
  ; which owns Z (SprHeight += SprTimerF, gravity -2/frame, bounce, XY friction,
  ; wall ricochet, pit/water) and can re-lift. Do not integrate Z here too: the
  ; vanilla routine clamps SprHeight to 0 on landing, so a second integrator
  ; never sees a negative height and the dog bounced forever. Settled means
  ; SprHeight == 0 and no bounce velocity left; then an "excited" tail wag
  ; (report D: reactive behavior, "excited after being put down").
  Dog_Tossed:
  {
    %SetFrame(8) ; reuse the sitting frame while airborne
    JSL Sprite_Move
    JSL Sprite_CheckTileCollision
    JSL ThrownSprite_TileAndSpriteInteraction_long
    LDA.w SprHeight, X : ORA.w SprTimerF, X : BNE .aloft
      STZ.w SprXSpeed, X
      STZ.w SprYSpeed, X
      LDA.b #$40 : STA.w SprTimerD, X ; happy wag duration on landing
      JSL Sprite_IsToRightOfPlayer : TYA : BEQ .land_right
        %GotoAction(5)
        RTS
      .land_right
      %GotoAction(6)
    .aloft
    RTS
  }

  ; 0A - joyful hopping wag dance triggered by nearby Ocarina cast ($03F0=$80).
  Dog_HappyDance:
  {
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    JSL Sprite_IsToRightOfPlayer : TYA : BEQ .dance_r
      LDY.b #$06 : BRA .dance_anim
    .dance_r
      LDY.b #$07
    .dance_anim
    JSR Dog_PlayAnim
    LDA.w SprMiscF, X : INC A : STA.w SprMiscF, X
    AND.b #$0F
    CMP.b #$08 : BCC .hop_up
      EOR.b #$0F
    .hop_up
    STA.w SprHeight, X
    JSR LiftOrTalk
    LDA.w SprTimerD, X : BNE .done
      STZ.w SprHeight, X
      STZ.w SprMiscD, X
      LDA.b #$70 : STA.w SprTimerC, X
      LDA.b #$40 : STA.w SprTimerD, X
      %GotoAction(0)
    .done
    RTS
  }

  ; 0B - Night sleep / doze for outdoor strays (18:00-05:59).
  ; Uses sitting Frame 8 (single 16x16 body OAM + shadow = 2 OAM slots total).
  Dog_Sleep:
  {
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    JSR HandleTossedDog
    %SetFrame(8)
    ; Wake at dawn (06:00-17:59) or if Richard quest takes ownership.
    LDA.w SprSubtype, X : BNE .wake_calm
    LDA.l TimeState.Hours
    CMP.b #$12 : BCS .still_night
    CMP.b #$06 : BCS .wake_calm
    .still_night
    ; Throttle proximity wake checks to every 4 frames per slot.
    TXA : EOR.b $1A : AND.b #$03 : BNE .sleep_talk
      LDA.w $02B2 : CMP.b #$03 : BNE .chk_move_wake
        LDA.b #$20 : JSR Dog_NearPlayer : BCS .wake_startle
      .chk_move_wake
      LDA.b $30 : ORA.b $31 : BEQ .sleep_talk
        LDA.b #$1C : JSR Dog_NearPlayer : BCS .wake_startle
    .sleep_talk
    JMP LiftOrTalk

    .wake_startle
    LDA.b #$06 : STA.w SprHeight, X
    .wake_calm
    STZ.w SprMiscD, X
    LDA.b #$C0 : STA.w SprTimerC, X
    LDA.b #$40 : STA.w SprTimerD, X
    %GotoAction(0)
    JMP LiftOrTalk
  }

  ; 0C - Curious ground-sniff / play-bow during daytime idle.
  Dog_SniffPlay:
  {
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    JSR HandleTossedDog
    LDA.b $1A : AND.b #$08 : BNE .sniff_down
      %SetFrame(4)
      BRA .bob
    .sniff_down
      %SetFrame(3)
    .bob
    LDA.b $1A : AND.b #$04 : LSR #2 : STA.w SprHeight, X
    JSR LiftOrTalk
    LDA.w SprTimerD, X : BNE .stay
      STZ.w SprHeight, X
      STZ.w SprMiscD, X
      LDA.b #$48 : STA.w SprTimerD, X
      %GotoAction(0)
    .stay
    RTS
  }
}

; Inline Bank $31 calm idle behavior (returned from Bank $2C once Bank $31 headroom opened).
Dog_CalmIdle:
{
  ; Outdoor strays (SprSubtype == 0) curl up to sleep at night (18:00-05:59) after cooldown.
  LDA.b $1B : BNE .no_sleep
  LDA.w SprSubtype, X : BNE .no_sleep
  LDA.w SprTimerC, X : BNE .no_sleep
  LDA.l TimeState.Hours
  CMP.b #$12 : BCS .go_sleep
  CMP.b #$06 : BCS .no_sleep
  .go_sleep
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    STZ.w SprMiscD, X
    %GotoAction($0B)
    RTS
  .no_sleep
  LDA.w SprMiscD, X
  CMP.b #$01 : BEQ .idle_left
  CMP.b #$02 : BEQ .idle_right
  CMP.b #$03 : BEQ .idle_stroll
    %SetFrame(8)
    BRA .idle_tick
  .idle_left
    %SetFrame(9)
    BRA .idle_tick
  .idle_right
    %SetFrame(10)
    BRA .idle_tick
  .idle_stroll
    LDA.w SprTimerC, X : BNE .stop_stroll
    LDA.w SprXSpeed, X : BMI .stroll_anim_l
      LDY.b #$03 : BRA .stroll_anim
    .stroll_anim_l
      LDY.b #$02
    .stroll_anim
    JSR Dog_PlayAnim
    STZ.b $06 : STZ.b $07
    JSL Sprite_MoveLong
    JSL Sprite_CheckTileCollision
    LDA.w $0E70, X : BEQ .idle_tick
    .stop_stroll
      STZ.w SprXSpeed, X
      STZ.w SprYSpeed, X
      STZ.w SprMiscD, X
      LDA.b #$50 : STA.w SprTimerD, X
      RTS

  .idle_tick
  LDA.w SprTimerD, X : BNE .done
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    JSL GetRandomInt : AND.b #$07
    CMP.b #$04 : BEQ .start_sniff
    AND.b #$03 : STA.w SprMiscD, X
    LDA.b #$50 : STA.w SprTimerD, X
    LDA.w SprMiscD, X : CMP.b #$03 : BNE .done
    LDA.w SprTimerC, X : BEQ .start_stroll
      STZ.w SprMiscD, X
      RTS
    .start_sniff
      LDA.b #$38 : STA.w SprTimerD, X
      %GotoAction($0C)
      RTS
    .start_stroll
      JSL GetRandomInt : TAY
      AND.b #$01 : BEQ .stroll_r
        LDA.b #$FA : BRA .set_sx
      .stroll_r
        LDA.b #$06
      .set_sx
      STA.w SprXSpeed, X
      TYA : LSR A : AND.b #$03 : TAY
      LDA.w .stroll_vy, Y : STA.w SprYSpeed, X
      LDA.b #$28 : STA.w SprTimerD, X

  .done
  RTS
  .stroll_vy : db 0, -2, 2, 0
}

EonDog_Walk:
{
  JSL Sprite_MoveLong
  JSL Sprite_BounceFromTileCollision
  LDA.w SprTimerA, X : BNE +
    JSL GetRandomInt : AND.b #$03 : TAY
    LDA.w .speed_x, Y : STA.w SprXSpeed, X
    LDA.w .speed_y, Y : STA.w SprYSpeed, X
    LDA.b #$3F : STA.w SprTimerA, X
    JSL GetRandomInt : AND.b #$01 : CLC : ADC.b #$07 : STA.w SprAction, X
  +
  RTS
  .speed_x
  db 0, -2, 2, 0
  .speed_y
  db 2, 0, 0, -2
}

Sprite_VillageDog_Draw:
{
  JSL   Sprite_PrepOamCoord : BCS .offscreen
  ; Tight viewport cull for 24x24 dog bounds so offscreen persistent strays never allocate OAM or loop.
  REP   #$20
  LDA.b $00 : CLC : ADC.w #$0010 : CMP.w #$0118 : BCS .offscreen_16
  LDA.b $02 : CLC : ADC.w #$0014 : CMP.w #$00FC : BCC .onscreen
  .offscreen_16
    SEP #$20
  .offscreen
    SEC
    RTS

  .onscreen
  SEP   #$20
  JSL   Sprite_OAM_AllocateDeferToPlayer
  LDA.w SprSubtype, X : BEQ .stray_mask
    STZ.b $0C
    JSL   RichardDog_PaletteMask ; $0C = Richard palette XOR ($04)
    BRA   .have_mask
  .stray_mask
    LDA.w SprMiscG, X : STA.b $0C
  .have_mask

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY ; Animation Frame
  LDA   .start_index,     Y : STA $06

  PHX
  LDX   .nbr_of_tiles,    Y              ; amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX                                    ; Save current Tile Index?

  TXA   : CLC : ADC $06                  ; Add Animation Index Offset

  PHA                                    ; Keep the value with animation index offset?

  ASL   A : TAX

  REP   #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC   : ADC #$0010 : CMP.w #$0100
  SEP   #$20
  BCC   .on_screen_y

  LDA.b #$F0 : STA ($90), Y              ;Put the sprite out of the way
  STA   $0E
  .on_screen_y

  PLX                                    ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : EOR.b $0C : STA ($90), Y

  PHY

  TYA   : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY   : INY

  PLX   : DEX : BPL .nextTile

  PLX

  CLC
  RTS


  .start_index
    db $00, $04, $08, $0C, $10, $13, $17, $1B, $1F, $20, $21, $22, $26
  .nbr_of_tiles
    db 3, 3, 3, 3, 2, 3, 3, 3, 0, 0, 0, 3, 3
  .x_offsets
    dw -4, -4, 12, 12
    dw -4, -4, 12, 12
    dw -4, -4, 4, 12
    dw -4, -4, 4, 4
    dw -4, 4, 12
    dw 4, -4, 4, -4
    dw 4, -4, 4, -4
    dw 4, -4, -4, -4
    dw 0
    dw 0
    dw 0
    dw 8, 8, 0, 0
    dw 8, 8, 0, 0
  .y_offsets
    dw -4, 4, 4, 12
    dw -4, 4, 4, 12
    dw -8, 0, 0, -8
    dw 0, -8, -8, 0
    dw 0, 0, -8
    dw 0, 0, -8, -8
    dw 0, 0, -16, -8
    dw 0, 0, 8, -8
    dw 0
    dw 0
    dw 0
    dw -4, 4, 4, 12
    dw -4, 4, 4, 12
  .chr
    db $10, $20, $22, $32
    db $10, $20, $02, $12
    db $13, $23, $24, $15
    db $26, $16, $17, $27
    db $29, $2A, $1B
    db $23, $24, $13, $14
    db $26, $27, $06, $18
    db $29, $2B, $3B, $1B
    db $2C
    db $2E
    db $2E
    db $10, $20, $22, $32
    db $10, $20, $02, $12
  ; Bug fix (2026-09-26 playtest): "dog needs to render above Link". Priority
  ; was 2 ($27/$67) while Link's own OAM priority is layer-dependent
  ; (LinkOAM_ObjectPriority, usdasm bank_0D $0DA126: $20/$10/$30/$30 -> 2/1/3/3
  ; by BG layer), so on layers where Link is priority 3 he always won over the
  ; dog regardless of the Region B/C OAM ordering from
  ; Sprite_OAM_AllocateDeferToPlayer above. Bumped to priority 3 ($37/$77),
  ; matching Sprite_EonDog_Draw's .properties below (already $3B/$7B, priority
  ; 3) and nearly every other Oracle NPC (bean_vendor, deku_scrub, eon_owl,
  ; farore, goron, korok, mermaid, zora, etc. all default to priority 3) --
  ; the village dog was the inconsistent one. Same table size, so this is a
  ; free (zero added ROM bytes) fix. It was written when Bank $31 had 10 bytes
  ; free; the build log now prints "Bank31 Free Space" (see all_sprites.asm).
  .properties
    db $37, $37, $37, $37
    db $37, $37, $37, $37
    db $37, $37, $37, $37
    db $37, $37, $37, $37
    db $37, $37, $37
    db $77, $77, $77, $77
    db $77, $77, $77, $77
    db $77, $77, $77, $77
    db $37
    db $77
    db $37
    db $77, $77, $77, $77
    db $77, $77, $77, $77
  .sizes
    db $02, $02, $00, $00
    db $02, $02, $00, $00
    db $02, $02, $02, $00
    db $02, $02, $02, $02
    db $02, $02, $00
    db $02, $02, $02, $02
    db $02, $02, $02, $00
    db $02, $00, $00, $00
    db $02
    db $02
    db $02
    db $02, $02, $00, $00
    db $02, $02, $00, $00
}

Sprite_EonDog_Draw:
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

  CLC
  RTS

  .start_index
  db $00, $01, $02, $03
  .nbr_of_tiles
  db 0, 0, 0, 0
  .x_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  .y_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  .chr
  db $C0
  db $C2
  db $C0
  db $C2
  .properties
  db $3B
  db $3B
  db $7B
  db $7B
  .sizes
  db $02
  db $02
  db $02
  db $02
}
