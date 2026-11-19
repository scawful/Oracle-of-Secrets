; =========================================================
; Twinrova Boss Sprite
;
; Overrides Blind and the Blind Maiden to create a new
; boss sequence.
;
; =========================================================

!SPRID              = Sprite_Twinrova
!NbrTiles           = 06  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 01  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this Twinrova (can be 0 to 7)
!Hitbox             = 03  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
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
!Boss               = 01  ; 00 = normal sprite, 01 = sprite is a boss
%Set_Sprite_Properties(Sprite_Twinrova_Prep, Sprite_Twinrova_Long)

; =========================================================

Sprite_Twinrova_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Twinrova_Draw
  JSL Sprite_DrawShadow
  ; Native boss explosions still draw through this entry, but state $04
  ; skips the active action table. Restore before that gate, retaining the
  ; native Draw/Shadow scratch, frame, timers and explosion/prize dispatch.
  JSR Twinrova_RestoreRodDamageOnDeath

  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Twinrova_CheckIfDead
    JSR Sprite_Twinrova_Main
  .SpriteIsNotActive
  PLB
  RTL
}

; =========================================================

Sprite_Twinrova_CheckIfDead:
{
  LDA.w SprAction, X : CMP.b #$0A : BEQ .not_dead
    ; If health is negative, set back to zero
    LDA.w SprHealth, X : CMP.b #$C3 : BCC .health_not_negative
      LDA.b #$00 : STA.w SprHealth, X
    .health_not_negative
    LDA.w SprHealth, X : BNE .not_dead
      PHX
      LDA.b #$04 : STA.w SprState, X     ; Kill sprite boss style
      LDA.b #$0A : STA.w SprAction, X ; Go to Twinrova_Dead stage
      LDA.b #$10 : STA.w $0D90, X
      PLX
  .not_dead
  RTS
}

; =========================================================

Sprite_Twinrova_Prep:
{
  %BossPrep_ExitIfDefeated()
  PHB : PHK : PLB
  ; Kill the sprite if the Maiden is present
  LDA.l $7EF3CC : CMP.b #$06 : BNE .prep_twinrova
    STZ.w SprState, X
  .prep_twinrova

  JSR Twinrova_Initialize
  PLB
  RTL
}

; Shared startup after native property loading; caller supplies our data bank.
Twinrova_Initialize:
{
  LDA.b #$5A : STA.w SprHealth, X ; Health
  LDA.b #$80 : STA.w SprDefl, X
  LDA.b #$04 : STA.w SprBump, X ; Bump damage type (4 hearts, green tunic)
  LDA.w SprGfxProps, X : AND.b #$BF : STA.w SprGfxProps, X ; Not invincible

  %SetSpriteSpeedX(15)
  %SetSpriteSpeedX(15)

  ; Blind Boss startup configuration
  LDA.b #$10 : STA $08
  LDA.b #$10 : STA $09

  LDA.b #$60 : STA.w SprTimerC, X
  LDA.b #$01 : STA.w SprMiscB, X
  LDA.b #$02 : STA.w SprMiscC, X
  LDA.b #$04 : STA.w SprMiscE, X
  LDA.b #$07 : STA.w SprGfx, X
  STZ.w $0B69
  JSR Twinrova_RodDamageDefault

  RTS
}

; Only Twinrova's two rod subclasses change. The selected source base loads
; both as zero; swords and every other sprite's damage profile stay intact.
!Twinrova_FireRodDamage = $7F6CEB
!Twinrova_IceRodDamage  = $7F6CEC
!Twinrova_FireRodLoaded = $00
!Twinrova_IceRodLoaded  = $00

; @abi m8x8 -- X is this Twinrova's slot. A/flags only; preserve X/Y/DB/D and
; scratch $00-$04, which native explosion rendering consumes after this call.
Twinrova_RestoreRodDamageOnDeath:
{
  LDA.w SprState, X : CMP.b #$04 : BNE .done
    JSR Twinrova_RodDamageDefault
  .done
  RTS
}

Twinrova_RodDamageDefault:
{
  LDA.b #!Twinrova_FireRodLoaded : STA.l !Twinrova_FireRodDamage
  LDA.b #!Twinrova_IceRodLoaded  : STA.l !Twinrova_IceRodDamage
  RTS
}

Twinrova_RodDamageKoume:
{
  LDA.b #$00 : STA.l !Twinrova_FireRodDamage
  LDA.b #$01 : STA.l !Twinrova_IceRodDamage
  RTS
}

Twinrova_RodDamageKotake:
{
  LDA.b #$01 : STA.l !Twinrova_FireRodDamage
  LDA.b #$00 : STA.l !Twinrova_IceRodDamage
  RTS
}

; The maiden spawn bypasses state08 and its native property loader.
; Keep its fixed-size hook and follower position cache ($00-$03) intact.
Twinrova_FirstFightPrep: ; @abi m8x8
{
  PHB : PHK : PLB
  PHX
  LDX.b #$00
  LDA.b #Sprite_Twinrova : STA.w SprType, X
  JSL SpritePrep_LoadProperties
  JSR Twinrova_Initialize
  PLX
  PLB
  JML ApplyTwinrovaGraphics
}

; =========================================================

!AnimSpeed = 8

macro Twinrova_Front()
  %PlayAnimation(0,1,!AnimSpeed)
endmacro

macro Twinrova_Back()
  %PlayAnimation(2,3,!AnimSpeed)
endmacro

macro Twinrova_Ready()
  %PlayAnimation(4,6,!AnimSpeed)
endmacro

macro Twinrova_Attack()
  %PlayAnimation(7,7,!AnimSpeed)
endmacro

macro Show_Koume()
  %PlayAnimation(8,8,!AnimSpeed)
endmacro

macro Show_Kotake()
  %PlayAnimation(9,9,!AnimSpeed)
endmacro

macro Twinrova_Hurt()
  %PlayAnimation(10,11,!AnimSpeed)
endmacro

; =========================================================

; =========================================================
; Cinematic 3-Act Twinrova Fight (SprMiscD = Act 0/1/2):
;
; Act 1 (HP $5A -> $35, SprMiscD == 0):
;   Maiden reveals Koume (Fire, Frame 8) & Kotake (Ice, Frame 9)
;   in a deterministic tag-team with telegraphed elemental attacks,
;   orbiting sweeps, and opposite-element rod vulnerability.
;
; Act 2 (HP <= $34, SprMiscD == 1, ZERO RNG):
;   78-frame invincible Twinrova_FusionCinematic (Action $0B):
;   converge/spiral toward center arena with accelerating Fire/Ice
;   flash strobe, rising SFX & quake, snapping cleanly into Twinrova.
;
; Act 3 (HP $34 -> $00, SprMiscD == 2):
;   Combined Twinrova alternates deterministic Fire Wave & Ice Barrage
;   with Twinrova_Ready (4..6) wind-up -> Twinrova_Attack (7) cast,
;   opposite-rod counterplay, and enraged speed-up below $1A HP.
; =========================================================

!Twinrova_FusionHP = $34
!Twinrova_EnrageHP = $1A
!Twinrova_FusionFrames = $4E

Sprite_Twinrova_Main:
{
  JSL Sprite_DamageFlash_Long

  ; Invincible & harmless during the Act 2 fusion cinematic ($0B)
  LDA.w SprAction, X : CMP.b #$0B : BEQ .skip_contact
    PHX
    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()
    PLX
  .skip_contact

  LDA.w SprAction, X
  JSL   JumpTableLocal

  dw Twinrova_Init            ; 0x00
  dw Twinrova_MoveState       ; 0x01
  dw Twinrova_MoveForwards    ; 0x02
  dw Twinrova_MoveBackwards   ; 0x03
  dw Twinrova_PrepareAttack   ; 0x04
  dw Twinrova_FireAttack      ; 0x05
  dw Twinrova_IceAttack       ; 0x06
  dw Twinrova_Hurt            ; 0x07
  dw Twinrova_KoumeMode       ; 0x08
  dw Twinrova_KotakeMode      ; 0x09
  dw Twinrova_Dead            ; 0x0A
  dw Twinrova_FusionCinematic ; 0x0B

  ; 0x00 - Reveal dialogue, then open Act 1 with Koume (Fire Witch)
  Twinrova_Init:
  {
    STZ.w $0DC0, X ; Ensure clean base frame offset on re-entry as well as first fight
    %ShowUnconditionalMessage($123)
    LDA.w SprTimerD, X : BNE +
      STZ.w SprMiscD, X               ; Act 1: Koume & Kotake Tag-Team
      STZ.w SprMiscF, X
      STZ.w SprMiscA, X
      LDA.b #$88 : STA.w SprTimerD, X ; Opening Koume turn (136 frames)
      LDA.b #$28 : JSL Sound_SetSfx3PanLong ; Dramatic reveal warp SFX
      %GotoAction(8)                  ; Start Act 1 as Koume!
    +
    RTS
  }

  ; 0x01 - Act 3 Combined Twinrova neutral float & deterministic cast scheduler
  Twinrova_MoveState:
  {
    STZ.w $0360
    STZ.w $0DC0, X

    ; Guard: if somehow entered during Act 1, return to Koume tag-team
    LDA.w SprMiscD, X : BNE .act3
      LDA.b #$88 : STA.w SprTimerD, X
      %GotoAction(8)
      RTS
    .act3

    JSR Twinrova_RodDamageDefault

    ; Brief hurt recoil on hit (rate-limited by SprTimerE to prevent stunlock)
    LDA.w SprFlash, X : BEQ .not_flashing
    LDA.w SprTimerE, X : BNE .not_flashing
      LDA.b #$14 : STA.w SprTimerA, X ; 20-frame recoil
      LDA.b #$30 : STA.w SprTimerE, X ; Hurt cooldown
      %GotoAction(7) ; Twinrova_Hurt
      RTS
    .not_flashing

    ; Deterministic alternating Fire Wave / Ice Barrage trigger (ZERO RNG)
    LDA.w SprTimerD, X : BNE .keep_moving
      LDA.w SprMiscF, X : AND.b #$01 : BNE .queue_ice
        STZ.b $AC                     ; Fire Wave
        JSR Twinrova_RodDamageKoume   ; Ice Rod punishes Fire channel
        LDA.b #$0E : JSL Sound_SetSfx2PanLong ; Fire charge telegraph cue
        BRA .enter_prepare
      .queue_ice
        LDA.b #$01 : STA.b $AC        ; Ice Barrage
        JSR Twinrova_RodDamageKotake  ; Fire Rod punishes Ice channel
        LDA.b #$0F : JSL Sound_SetSfx2PanLong ; Ice charge telegraph cue
      .enter_prepare
      INC.w SprMiscF, X
      LDA.b #$28
      LDY.w SprHealth, X : CPY.b #!Twinrova_EnrageHP+1 : BCS +
        LDA.b #$1C ; Enraged shorter telegraph below $1A HP
      +
      STA.w SprTimerD, X
      LDA.b #$04 : STA.w SprFrame, X  ; Start cleanly on Twinrova_Ready frame 4
      %GotoAction(4) ; Twinrova_PrepareAttack
      RTS

    .keep_moving
    JSL Sprite_IsBelowPlayer : TYA : BNE .move_back
      %GotoAction(2) ; MoveForwards
      RTS
    .move_back
    %GotoAction(3) ; MoveBackwards
    RTS
  }

  ; 0x02 - Twinrova_MoveForwards (Act 3 float toward player)
  Twinrova_MoveForwards:
  {
    %Twinrova_Front()
    LDA.b #$14
    LDY.w SprHealth, X : CPY.b #!Twinrova_EnrageHP+1 : BCS +
      LDA.b #$1C ; Enraged float speed
    +
    LDY.b #$10 ; height
    JSL Sprite_FloatTowardPlayer
    JSL Sprite_CheckTileCollision
    %GotoAction(1)
    RTS
  }

  ; 0x03 - Twinrova_MoveBackwards (Act 3 float back)
  Twinrova_MoveBackwards:
  {
    %Twinrova_Back()
    LDA.b #$18
    LDY.w SprHealth, X : CPY.b #!Twinrova_EnrageHP+1 : BCS +
      LDA.b #$20
    +
    LDY.b #$10
    JSL Sprite_FloatTowardPlayer
    JSL Sprite_CheckTileCollision
    %GotoAction(1)
    RTS
  }

  ; 0x04 - Act 3 telegraphed cast wind-up (Twinrova_Ready frames 4..6 + glow!)
  Twinrova_PrepareAttack:
  {
    %StartOnFrame(4)
    %Twinrova_Ready()
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X

    LDA.b #$01 : STA.w $0360
    LDA.w SprTimerD, X : BNE +
      LDA.b #$36 : JSL Sound_SetSfx3PanLong ; Magic cast release SFX
      LDA.b #$44
      LDY.w SprHealth, X : CPY.b #!Twinrova_EnrageHP+1 : BCS ++
        LDA.b #$4E ; Enraged extended barrage
      ++
      STA.w SprTimerD, X
      LDA.b #$07 : STA.w SprFrame, X ; Snap to wide-arm cast Frame 7
      LDA.b $AC : BEQ .fire
        %GotoAction(6) ; Ice Barrage
        RTS
      .fire
      %GotoAction(5) ; Fire Wave
    +
    RTS
  }

  ; 0x05 - Act 3 Combined Fire Wave (Frame 7 wide cast + aimed fire volleys)
  Twinrova_FireAttack:
  {
    LDA.b #$07 : STA.w SprFrame, X
    %Twinrova_Attack()
    JSR Twinrova_RodDamageKoume ; Ice Rod punishes active Fire Wave

    JSR Twinrova_RestoreFloorTile
    LDA.b #$08 : JSL BossKit_FireTrail ; at most 8 live flames

    ; Deterministic aimed fireball beats (extra beat when enraged)
    LDA.w SprTimerD, X
    CMP.b #$38 : BEQ .fire_orb
    CMP.b #$20 : BEQ .fire_orb
    CMP.b #$0C : BNE .no_orb
      LDY.w SprHealth, X : CPY.b #!Twinrova_EnrageHP+1 : BCS .no_orb
    .fire_orb
      JSR Twinrova_FireAimedOrb
      LDA.b #$0E : JSL Sound_SetSfx2PanLong
    .no_orb

    LDA.w SprTimerD, X : BNE +
      JSR Twinrova_FinishAct3Cast
    +
    RTS
  }

  ; 0x06 - Act 3 Combined Ice Barrage (Frame 7 wide cast + ice trail & frost orbs)
  Twinrova_IceAttack:
  {
    LDA.b #$07 : STA.w SprFrame, X
    %Twinrova_Attack()
    JSR Twinrova_RodDamageKotake ; Fire Rod punishes active Ice Barrage

    LDA.b #$08 : JSL BossKit_IceTrail ; at most 8 live ice clouds

    ; Deterministic frost orb volleys (extra beat when enraged)
    LDA.w SprTimerD, X
    CMP.b #$38 : BEQ .ice_orb
    CMP.b #$1C : BEQ .ice_orb
    CMP.b #$0C : BNE .check_keese
      LDY.w SprHealth, X : CPY.b #!Twinrova_EnrageHP+1 : BCS .check_keese
    .ice_orb
      JSR Twinrova_FireAimedOrb
      LDA.b #$0F : JSL Sound_SetSfx2PanLong
      BRA .check_done

    .check_keese
    CMP.b #$2C : BNE .check_done
      ; Summon at most 1 Ice Keese if fewer than 2 active
      LDA.b #$11 : STA.b $00
      JSL Sprite_CountActiveById
      LDA.b $02 : CMP.b #$02 : BCS .check_done
        JSL Sprite_SpawnIceKeese
        LDA.b #$01 : STA.w SprMiscB, Y

    .check_done
    LDA.w SprTimerD, X : BNE +
      JSR Twinrova_FinishAct3Cast
    +
    RTS
  }

  ; 0x07 - Act 3 crisp hurt recoil (uses SprTimerA, resumes MoveState cleanly)
  Twinrova_Hurt:
  {
    %StartOnFrame(10)
    %Twinrova_Hurt()
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X

    LDA.w SprTimerA, X : BNE .hurt_anim
      STZ.w SprFrame, X
      %GotoAction(1)
    .hurt_anim
    RTS
  }

  ; 0x08 - Act 1 Koume (Fire Witch): Ice Rod / Sword counterplay, deterministic tag-out & fusion
  Twinrova_KoumeMode:
  {
    ; Fixed form: StartOnFrame only raises a frame, so Kotake's $09 could
    ; otherwise persist while the rod profile has already switched to Koume.
    ; Keep this exact prefix before JSL GetRandomInt for twinrova_rod_lifecycle.py.
    LDA.b #$08 : STA.w SprFrame, X
    %Show_Koume()
    JSR Twinrova_RodDamageKoume

    JSL GetRandomInt ; Preserved ABI boundary (Act 1/2 transitions are 100% deterministic)
    STZ.w $0DC0, X

    ; Deterministic fusion trigger at exact HP threshold (<= $34, ZERO RNG!)
    LDA.w SprHealth, X : CMP.b #!Twinrova_FusionHP+1 : BCS .act1_koume
      JMP Twinrova_StartFusion
    .act1_koume

    ; Choreographed turn across SprTimerD ($88 -> $00):
    ;   $88..$64: sweeping orbit | $63..$48: fire telegraph | $48/$34: aimed orbs | $33..$01: punish dip
    LDA.w SprTimerD, X
    CMP.b #$64 : BCS .orbit
    CMP.b #$48 : BCS .charge_fire
      ; Attack release beats + punish dip
      CMP.b #$34 : BNE .dip
        JSR Twinrova_FireAimedOrb
        LDA.b #$0E : JSL Sound_SetSfx2PanLong
      .dip
      JSR KoumeKotake_DipTowardLink
      BRA .check_tagout

    .charge_fire
    CMP.b #$63 : BNE +
      LDA.b #$0E : JSL Sound_SetSfx2PanLong ; Fire charge telegraph cue
    +
    CMP.b #$48 : BNE .hover_charge
      JSR Twinrova_FireAimedOrb
      LDA.b #$0E : JSL Sound_SetSfx2PanLong
    .hover_charge
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    LDA.b #$10 : STA.w SprHeight, X
    BRA .check_tagout

    .orbit
    JSR KoumeKotake_OrbitMove

    .check_tagout
    LDA.w SprTimerD, X : BNE +
      ; Deterministic tag-out flash to Kotake!
      LDA.b #$28 : JSL Sound_SetSfx3PanLong
      LDA.b #$88 : STA.w SprTimerD, X
      LDA.w SprMiscA, X : CLC : ADC.b #$10 : STA.w SprMiscA, X
      %GotoAction(9) ; Tag in Kotake
    +
    RTS
  }

  ; 0x09 - Act 1 Kotake (Ice Witch): Fire Rod / Sword counterplay, deterministic tag-out & fusion
  Twinrova_KotakeMode:
  {
    ; Keep this exact prefix before JSL Sprite_IsBelowPlayer for twinrova_rod_lifecycle.py.
    LDA.b #$09 : STA.w SprFrame, X
    %Show_Kotake()
    JSR Twinrova_RodDamageKotake

    JSL Sprite_IsBelowPlayer ; Preserved ABI boundary
    STZ.w $0DC0, X

    ; Deterministic fusion trigger at exact HP threshold (<= $34, ZERO RNG!)
    LDA.w SprHealth, X : CMP.b #!Twinrova_FusionHP+1 : BCS .act1_kotake
      JMP Twinrova_StartFusion
    .act1_kotake

    ; Choreographed turn across SprTimerD ($88 -> $00):
    ;   $88..$64: sweeping orbit | $63..$48: frost telegraph | $48..$30: ice burst | $2F..$01: punish dip
    LDA.w SprTimerD, X
    CMP.b #$64 : BCS .orbit
    CMP.b #$48 : BCS .charge_ice
    CMP.b #$30 : BCS .cast_ice
      JSR KoumeKotake_DipTowardLink
      BRA .check_tagout

    .cast_ice
    CMP.b #$44 : BNE +
      JSR Twinrova_FireAimedOrb
      LDA.b #$0F : JSL Sound_SetSfx2PanLong
    +
    LDA.b #$06 : JSL BossKit_IceTrail
    BRA .check_tagout

    .charge_ice
    CMP.b #$63 : BNE +
      LDA.b #$0F : JSL Sound_SetSfx2PanLong ; Frost charge telegraph cue
    +
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    LDA.b #$10 : STA.w SprHeight, X
    BRA .check_tagout

    .orbit
    JSR KoumeKotake_OrbitMove

    .check_tagout
    LDA.w SprTimerD, X : BNE +
      ; Deterministic tag-out flash back to Koume!
      LDA.b #$28 : JSL Sound_SetSfx3PanLong
      LDA.b #$88 : STA.w SprTimerD, X
      LDA.w SprMiscA, X : CLC : ADC.b #$10 : STA.w SprMiscA, X
      %GotoAction(8) ; Tag in Koume
    +
    RTS
  }

  ; 0x0A
  Twinrova_Dead:
  {
    %StartOnFrame(11)
    JSR Twinrova_RodDamageDefault
    JSL Sprite_KillFriends
    %Twinrova_Hurt()
    RTS
  }

  ; 0x0B - Act 2 Deterministic Telegraphed Fusion Cinematic (78 frames, invincible)
  Twinrova_FusionCinematic:
  {
    STZ.w $0DC0, X
    LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X ; Invincible
    STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    LDA.b #$10 : STA.w SprHeight, X

    LDA.w SprTimerD, X
    CMP.b #$26 : BCS .converge_spiral
    CMP.b #$14 : BCS .climax_strobe
      ; Phase C ($13..$00): Combined Twinrova wide-arm grand reveal!
      REP #$20
      STZ.w $011A : STZ.w $011C
      SEP #$20
      LDA.b #$07 : STA.w SprFrame, X
      JMP .check_finish

    .converge_spiral
    ; Phase A ($4E..$26): Drift & spiral toward center arena with accelerating Koume/Kotake flash
    JSR Twinrova_EaseToCenter
    ; Rising elemental SFX cues
    LDA.w SprTimerD, X
    CMP.b #$40 : BNE + : LDA.b #$0E : JSL Sound_SetSfx2PanLong : +
    LDA.w SprTimerD, X
    CMP.b #$32 : BNE + : LDA.b #$0F : JSL Sound_SetSfx2PanLong : +
    LDA.w SprTimerD, X
    CMP.b #$26 : BNE + : LDA.b #$2A : JSL Sound_SetSfx3PanLong : +

    ; Subtle convergence shake (+-1 px)
    REP #$20
    LDA.b $1A : AND.w #$0002 : DEC A : STA.w $011A
    STZ.w $011C
    SEP #$20

    ; Accelerating Koume (8) <-> Kotake (9) visual merge
    LDA.w SprTimerD, X : CMP.b #$38 : BCS .swap_slow
      LDA.b $1A : LSR A : AND.b #$01 : CLC : ADC.b #$08 : STA.w SprFrame, X
      BRA .check_finish
    .swap_slow
      LDA.b $1A : LSR A : LSR A : AND.b #$01 : CLC : ADC.b #$08 : STA.w SprFrame, X
      BRA .check_finish

    .climax_strobe
    ; Phase B ($25..$14): Locked at center, rapid 1-frame strobe -> Thunder burst reveal!
    REP #$20
    LDA.b $1A : AND.w #$0002 : ASL A : SEC : SBC.w #$0002 : STA.w $011A
    LDA.b $1A : AND.w #$0001 : ASL A : DEC A : STA.w $011C
    SEP #$20
    LDA.b $1A : AND.b #$01 : CLC : ADC.b #$08 : STA.w SprFrame, X
    LDA.w SprTimerD, X : CMP.b #$14 : BNE .check_finish
      LDA.b #$26 : JSL Sound_SetSfx3PanLong ; Fusion thunder burst!
      LDA.b #$0C : JSL Sound_SetSfx2PanLong ; Shockwave boom!
      LDA.b #$07 : STA.w SprFrame, X        ; Snap into Combined Twinrova!

    .check_finish
    LDA.w SprTimerD, X : BNE .still_fusing
      ; Enter Act 3: Combined Twinrova Climax!
      REP #$20
      STZ.w $011A : STZ.w $011C
      SEP #$20
      LDA.w SprGfxProps, X : AND.b #$BF : STA.w SprGfxProps, X ; Vulnerable again
      LDA.b #$02 : STA.w SprMiscD, X ; Act 3 active!
      STZ.w SprMiscF, X              ; Deterministic cast cycle: Fire -> Ice -> ...
      STZ.w SprFrame, X              ; Clean front float frame 0
      LDA.b #$38 : STA.w SprTimerD, X
      %GotoAction(1) ; Twinrova_MoveState
    .still_fusing
    RTS
  }
}

; Shared Act 1 -> Act 2 deterministic transition helper.
Twinrova_StartFusion:
{
  LDA.b #$01 : STA.w SprMiscD, X ; Act 2: Fusion Cinematic
  LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X ; Invincible during fusion
  JSR Twinrova_RodDamageDefault
  STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
  STZ.w $0DC0, X
  LDA.b #!Twinrova_FusionFrames : STA.w SprTimerD, X
  LDA.b #$35 : JSL Sound_SetSfx2PanLong ; Rising rumble cue
  %GotoAction($0B)
  RTS
}

; Shared Act 3 cast completion: sets punish/reposition rest and returns to MoveState.
Twinrova_FinishAct3Cast:
{
  JSR Twinrova_RodDamageDefault
  LDA.b #$44
  LDY.w SprHealth, X : CPY.b #!Twinrova_EnrageHP+1 : BCS +
    LDA.b #$2E ; Enraged tighter punish window
  +
  STA.w SprTimerD, X
  STZ.w SprFrame, X
  %GotoAction(1)
  RTS
}

; Smoothly eases low-byte (SprX, SprY) toward arena center ($80, $68) with spiral flourish.
Twinrova_EaseToCenter:
{
  ; Target X low = $80 + spiral offset
  LDA.w SprTimerD, X : LSR A : AND.b #$07 : TAY
  LDA.w .spiral_x, Y : CLC : ADC.b #$80 : STA.b $00
  LDA.w SprX, X : CMP.b $00 : BEQ .do_y : BCC .inc_x
    SEC : SBC.b #$02 : CMP.b $00 : BCS .store_x
      LDA.b $00 : BRA .store_x
  .inc_x
    CLC : ADC.b #$02 : CMP.b $00 : BCC .store_x
      LDA.b $00
  .store_x
  STA.w SprX, X

  .do_y
  LDA.w .spiral_y, Y : CLC : ADC.b #$68 : STA.b $01
  LDA.w SprY, X : CMP.b $01 : BEQ .done : BCC .inc_y
    SEC : SBC.b #$02 : CMP.b $01 : BCS .store_y
      LDA.b $01 : BRA .store_y
  .inc_y
    CLC : ADC.b #$02 : CMP.b $01 : BCC .store_y
      LDA.b $01
  .store_y
  STA.w SprY, X
  .done
  RTS

  .spiral_x
  db  4,  3,  0, -3, -4, -3,  0,  3
  .spiral_y
  db  0,  3,  4,  3,  0, -3, -4, -3
}

; Act 1 witch swoop orbit: figure-8 sweeping flight across upper/mid arena.
KoumeKotake_OrbitMove:
{
  INC.w SprMiscA, X
  LDA.w SprMiscA, X : LSR A : LSR A : AND.b #$0F : TAY
  LDA.w .vel_x, Y : STA.w SprXSpeed, X
  LDA.w .vel_y, Y : STA.w SprYSpeed, X
  LDA.b #$10 : STA.w SprHeight, X
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  RTS

  .vel_x
  db  18,  16,  10,   0, -10, -16, -18, -16
  db -18, -16, -10,   0,  10,  16,  18,  16
  .vel_y
  db   6,  10,  10,   6,  -6, -10, -10,  -6
  db   6,  10,  10,   6,  -6, -10, -10,  -6
}

; Act 1 punish dip: gently drifts toward Link's band so Sword & opposite Rod can punish.
KoumeKotake_DipTowardLink:
{
  LDA.b #$0E
  LDY.b #$0C
  JSL Sprite_FloatTowardPlayer
  JSL Sprite_CheckTileCollision
  RTS
}

; Spawns a crisp aimed elemental fireball straight toward Link (speed $26).
Twinrova_FireAimedOrb:
{
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  LDA.w SprY, X : STA.b $02
  LDA.w SprYH, X : STA.b $03
  LDA.w SprHeight, X : STA.b $04
  JSL Sprite_SpawnFireball : BMI .exit
    JSR Fireball_Configure
    PHX
    TYX
    LDA.b #$26 : JSL Sprite_ProjectSpeedTowardsPlayer
    LDA.b $01 : STA.w SprXSpeed, X
    LDA.b $00 : STA.w SprYSpeed, X
    PLX
  .exit
  RTS
}

; Out: A = palette flash bits (damage flash OR Act 1/2/3 telegraph & fusion glow).
Twinrova_FlashBits:
{
  LDA.w SprAction, X
  CMP.b #$0B : BEQ .glow ; Act 2 Fusion Cinematic strobe
  CMP.b #$04 : BEQ .glow ; Act 3 PrepareAttack wind-up
  CMP.b #$08 : BEQ .act1_charge
  CMP.b #$09 : BNE .damage
  .act1_charge
    LDA.w SprTimerD, X
    CMP.b #$48 : BCC .damage
    CMP.b #$64 : BCS .damage
  .glow
    LDA.b $1A : AND.b #$06 : ORA.w SprFlash, X
    RTS
  .damage
  LDA.w SprFlash, X
  RTS
}


; =========================================================
; Handles dynamic floaty movement for Twinrova

RageModeMove:
{
  ; If timer is zero, determine a new movement mode
  LDA.w SprTimerA, X : BEQ .DetermineMovementMode
    ; Execute current movement mode
    LDA.w SprMiscA, X
    CMP #$01 : BEQ .MoveTowardsPlayer
    CMP #$02 : BEQ .RandomStrafe
    CMP #$03 : BEQ .RandomDodge
    CMP #$04 : BEQ .StayInPlace
    JMP .UpdatePosition
  .DetermineMovementMode

  ; Determine random movement mode with weighted probabilities
  JSL GetRandomInt : AND.b #$0F
  CMP.b #$05 : BCC .SetMoveTowardsPlayer  ; 0-5 -> Predictive movement towards player
    CMP.b #$0A : BCC .SetRandomStrafe       ; 6-10 -> Random strafe
    CMP.b #$0E : BCC .SetRandomDodge        ; 11-14 -> Random dodge
    ; 15 -> Stay in place
    LDA.b #$04 : STA.w SprMiscA, X
    LDA.b #$30 : STA.w SprTimerA, X  ; Set timer for 48 frames
    RTS
    BRA .StayInPlace

  .SetMoveTowardsPlayer
  LDA.b #$01 : STA.w SprMiscA, X
  LDA.b #$30 : STA.w SprTimerA, X  ; Set timer for 48 frames
  BRA .MoveTowardsPlayer

  .SetRandomStrafe
  LDA.b #$02 : STA.w SprMiscA, X
  LDA.b #$30 : STA.w SprTimerA, X  ; Set timer for 48 frames
  BRA .RandomStrafe

  .SetRandomDodge
  LDA.b #$03 : STA.w SprMiscA, X
  LDA.b #$30 : STA.w SprTimerA, X  ; Set timer for 48 frames
  BRA .RandomDodge

  .MoveTowardsPlayer
  ; Predictive movement towards player with altitude increase
  JSL Sprite_DirectionToFacePlayer
  JSL Sprite_ApplySpeedTowardsPlayer
  LDA.b #$10 : STA.w SprHeight, X ; Set height
  BRA .UpdatePosition

  .RandomStrafe
  JSR DoRandomStrafe
  BRA .UpdatePosition

  .RandomDodge
  ; Random dodge with controlled movement
  JSL GetRandomInt : AND.b #$03 : TAY
  LDA VelocityOffsets+4, Y : STA.w SprXSpeed, X
  INY
  LDA VelocityOffsets, Y : STA.w SprYSpeed, X
  LDA.b #$10 : STA.w SprHeight, X ; Set height
  BRA .UpdatePosition

  .StayInPlace
  ; Stay in place to prepare for attack or other action
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  LDA.b #$10 : STA.w SprHeight, X ; Set height
  BRA .UpdatePosition

  .Evasive
  ; Evasive action if too close to player
  JSL GetRandomInt : AND.b #$03 : TAY
  LDA VelocityOffsets, Y : EOR #$FF : INC : STA.w SprXSpeed, X
  INY
  LDA VelocityOffsets+4, Y : EOR #$FF : INC : STA.w SprYSpeed, X
  LDA.b #$10 : STA.w SprHeight, X ; Set height
  BRA .UpdatePosition

  .UpdatePosition
  ; Handle floaty movement with controlled altitude
  LDA.w SprHeight, X : CMP #$10 : BNE .CheckGrounded
    DEC.w SprHeight, X
    DEC.w SprHeightS, X

  .CheckGrounded
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  RTS
}

DoRandomStrafe:
{
  JSL GetRandomInt : AND.b #$03
  TAY
  LDA VelocityOffsets, Y : STA.w SprXSpeed, X
  INY
  LDA VelocityOffsets+4, Y : STA.w SprYSpeed, X
  LDA.b #$10 : STA.w SprHeight, X ; Set height
  RTS
}

; Velocity offsets table
VelocityOffsets:
  db $08, $F8, $08, $F8  ; X speeds (right, left, down, up)
  db $04, $FC, $04, $FC  ; Y speeds (down, up, right, left)

; Target positions table (relative to the player)
TargetPositions:
  dw $0040, $FFC0  ; Right, Left
  dw $0040, $FFC0  ; Down, Up

; =========================================================

Twinrova_RestoreFloorTile:
{
  LDA.w SprY, X : STA.b $00 : LDA.w SprYH, X : STA.b $01
  LDA.w SprX, X : STA.b $02 : LDA.w SprXH, X : STA.b $03

  LDA.b #$00
  JSL Sprite_GetTileAttr
  LDA.w $0FA5 : CMP.b #$0E : BNE +
    LDA.w SprX, Y : STA.l $7FF83C, X
    LDA.w SprXH, Y : STA.l $7FF878, X
    LDA.w SprY, Y : CLC : ADC.b #$10 : STA.l $7FF81E, X
    LDA.w SprYH, Y : ADC.b #$00 : STA.l $7FF85A, X
    JSR RestoreFloorTile
  +
  RTS
}

RestoreFloorTile:
{
  PHA
  LDA.l $7FF83C, X : STA.b $00
  LDA.l $7FF878, X : STA.b $01
  LDA.l $7FF81E, X : SEC : SBC.b #$10 : STA.b $02
  LDA.l $7FF85A, X : SBC.b #$00 : STA.b $03

  LDY.b #$00
  JSL $01E7A9 ; Underworld_UpdateTilemapWithCommonTile
  PLA
  RTS
}

AddPitHazard:
{
  PHA
  LDA.l $7FF83C, X : STA.b $00
  LDA.l $7FF878, X : STA.b $01
  LDA.l $7FF81E, X : SEC : SBC.b #$10 : STA.b $02
  LDA.l $7FF85A, X : SBC.b #$00 : STA.b $03

  LDY.b #$04
  JSL $01E7A9 ; Underworld_UpdateTilemapWithCommonTile
  PLA
  RTS
}

Ganon_SpawnFallingTilesOverlord:
{
  LDY.b #$07
  .next_slot
  LDA.w $0B00, Y : BEQ .free_slot
    DEY : BPL .next_slot
      RTS
  .free_slot

  LDA.w SprMiscF, X : CMP.b #$04 : BCS .dont_spawn
    INC.w SprMiscF, X
    PHX
    TAX
    LDA.w .overlord_type, X : STA.w $0B00, Y
    LDA.w .position_x, X : STA.w $0B08, Y
    LDA.b $23 : STA.w $0B10, Y
    LDA.w .position_y, X : STA.w $0B18, Y
    LDA.b $21 : STA.w $0B20, Y
    LDA.b #$00 : STA.w $0B28, Y : STA.w $0B30, Y
    PLX
  .dont_spawn
  RTS

  .overlord_type
  db $0C ; OVERLORD 0C
  db $0D ; OVERLORD 0D
  db $0E ; OVERLORD 0E
  db $0F ; OVERLORD 0F

  .position_x
  db $18
  db $D8
  db $D8
  db $18

  .position_y
  db $20
  db $20
  db $D0
  db $D0
}

; =========================================================

Sprite_Twinrova_Draw:
{
    JSL Sprite_PrepOamCoord
    JSL Sprite_OAM_AllocateDeferToPlayer

    LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
    LDA .start_index, Y : STA $06

    JSR Twinrova_FlashBits : STA $08

    PHX
    LDX   .nbr_of_tiles, Y ;amount of tiles -1
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
    CLC   : ADC #$0010 : CMP.w #$0100
    SEP   #$20
    BCC   .on_screen_y

    LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
    STA   $0E
  .on_screen_y

    PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
    INY
    LDA .chr, X : STA ($90), Y
    INY

    ; Set palette flash modifier
    LDA .properties, X : ORA $08 : STA ($90), Y

    PHY

    TYA : LSR #2 : TAY

    SEP #$20 ;set A back to 8bit but not X and Y
    LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

    PLY : INY

    PLX : DEX : BPL .nextTile

    SEP #$30

    PLX

    RTS

  .start_index
    db $00, $04, $08, $0C, $10, $14, $18, $1C, $22, $26, $2A, $2E
  .nbr_of_tiles
    db 3, 3, 3, 3, 3, 3, 3, 5, 3, 3, 3, 3
  .x_offsets
    dw -8, 8, 8, -8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -16, 0, 16, -16, 0, 16
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
  .y_offsets
    dw -8, -8, 8, 8
    dw -7, -7, 9, 9
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -7, -7, 9, 9
    dw -6, -6, 10, 10
    dw -8, -8, -8, 8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -7, -7, 9, 9
  .chr
    db $00, $02, $22, $24
    db $04, $06, $24, $26
    db $08, $0A, $28, $2A
    db $0C, $0E, $28, $2A
    db $44, $46, $64, $66
    db $48, $4A, $68, $6A
    db $4C, $4E, $6C, $6E
    db $88, $8A, $8C, $A8, $AA, $AC
    db $80, $82, $A0, $A2
    db $84, $86, $A4, $A6
    db $40, $42, $60, $62
    db $40, $42, $60, $62
  .properties
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
  .sizes
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02, $02, $00
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
}

; =========================================================

ApplyTwinrovaGraphics:
{
    PHX
    REP #$20               ; A = 16, XY = 8
    LDX #$80 : STX $2100   ; turn the screen off (required)
    LDX #$80 : STX $2115   ; Set the video port register every time we write it increase by 1
    LDA #$5000 : STA $2116 ; Destination of the DMA $5800 in vram <- this need to be divided by 2
    LDA #$1801 : STA $4300 ; DMA Transfer Mode and destination register
                           ; "001 => 2 registers write once (2 bytes: p, p+1)"
    LDA.w #TwinrovaGraphics : STA $4302     ; Source address where you want gfx from ROM
    LDX.b #TwinrovaGraphics>>16 : STX $4304
    LDA   #$2000 : STA $4305                ; Size of the transfer 4 sheets of $800 each
    LDX   #$01 : STX $420B                  ; Do the DMA
    LDX #$0F : STX $2100                    ; Turn the screen back on
    SEP #$30
    PLX
    RTL
}

; Relocated from Bank $32 sprite code stream to dedicated Bank $54 asset slot
; (DMA-only via ApplyTwinrovaGraphics; saves 8,192 B in Bank $32).
pushpc
org $54E000
TwinrovaGraphics_DataStart:
TwinrovaGraphics:
  incbin twinrova.bin
TwinrovaGraphics_DataEnd:
assert pc() <= $550000, "TwinrovaGraphics overflowed $54E000-$54FFFF"
pullpc

; $1DC845
#Fireball_Configure:
{
  LDA.w SprDefl, Y : ORA.b #$08 : STA.w SprDefl, Y
  LDA.b #$04 : STA.w SprBump, Y
  .exit
  RTS
}

; $1DC879
ReleaseFireballs:
{
  JSL Sprite_SpawnFireball : BMI .exit_a
    JSR Fireball_Configure

    PHX
    TYX
    JSL Sprite_DirectionToFacePlayer

    LDA.w .speed_x, Y : STA.w SprXSpeed, X
    LDA.w .speed_y, Y : STA.w SprYSpeed, X
    LDA.w SprX, X : CLC : ADC.w .offset_x_low, Y : STA.w SprX, X
    LDA.w SprXH, X : ADC.w .offset_x_high, Y : STA.w SprXH, X
    LDA.w SprY, X : CLC : ADC.w .offset_y_low, Y : STA.w SprY, X
    LDA.w SprYH, X : ADC.w .offset_y_high, Y : STA.w SprYH, X

    PLX
  .exit_a
  RTS

  .offset_x_low
  db  12, -12,   0,   0

  .offset_x_high
  db   0,  -1,   0,   0

  .offset_y_low
  db   0,   0,  12, -12

  .offset_y_high
  db   0,   0,   0,  -1

  .speed_y ; bleeds into next
  db   0,   0

  .speed_x
  db  40, -40,   0,   0
}

pushpc

; =========================================================
; Blind Maiden spawn code

SpritePrep_LoadProperties = $0DB818

; Follower_BasicMover.dont_scare_kiki
org $09A1E4
Follower_BasicMover:
{
  ; Check if the follower is the blind maiden
  LDA.l $7EF3CC : CMP.b #$06 : BNE .no_blind_transform
    ; Check if we are in room 0xAC
    REP #$20
    LDA.b $A0 : CMP.w #$00AC : BNE .no_blind_transform
      ; Check room flag 0x65
      ; LDA.l $7EF0CA : AND.w #$0100 : BEQ .no_blind_transform
      SEP #$20
      JSL Follower_CheckBlindTrigger : BCC .no_blind_transform
  .blind_transform
  ; Load follower animation step index from $02CF
  LDX.w $02CF
  LDA.w $1A28, X : STA.b $00 ; Follower XL
  LDA.w $1A3C, X : STA.b $01 ; Follower XH
  LDA.w $1A00, X : SEC : SBC.b #$10 : STA.b $02 ; Follower YL
  LDA.w $1A14, X : STA.b $03 ; Follower YH

  ; Dismiss the follower and spawn Twinrova
  LDA.b #$00 : STA.l $7EF3CC
  JSL Blind_SpawnFromMaiden

  ; Close the shutter door
  INC.w $0468

  ; Clear door tilemap position for some reason
  STZ.w $068E : STZ.w $0690

  ; Submodule $05 = "Opened Chest / Got Item" — triggers post-boss sequence
  LDA.b #$05 : STA.b $11

  ; SONG 15
  LDA.b #$15 : STA.w $012C

  RTS
  assert pc() <= $09A23A

  org $09A23A
  .no_blind_transform
}

; =========================================================

org $099E90
Follower_CheckBlindTrigger:
{
  PHB : PHK : PLB

  ; Cache the follower's position
  LDX.w $02CF
  LDA.w $1A00, X : STA.b $00
  LDA.w $1A14, X : STA.b $01
  LDA.w $1A28, X : STA.b $02
  LDA.w $1A3C, X : STA.b $03
  STZ.b $0B

  ; Check if the follower is within the trigger area
  LDA.w $1A50, X : STA.b $0A : BPL .positive_z
    LDA.b #$FF : STA.b $0B
  .positive_z
  REP #$20

  LDA.b $00 : CLC : ADC.b $0A : CLC : ADC.w #$000C : STA.b $00
  LDA.b $02 : CLC : ADC.w #$0008 : STA.b $02
  LDA.w #$1568 : SEC : SBC.b $00 : BPL .positive_x
    EOR.w #$FFFF : INC A
  .positive_x
  CMP.w #$0018 : BCS .fail
    LDA.w #$1980 : SEC : SBC.b $02 : BPL .positive_y
      EOR.w #$FFFF : INC A
  .positive_y
  CMP.w #$0018 : BCS .fail
    .success
    SEP #$20
    PLB : SEC
    RTL
  .fail
  SEP #$20
  PLB : CLC
  RTL
}

; =========================================================
; Called during Blind Maiden section of Follower_BasicMover
; to spawn Twinrova from the Blind Maiden.

org $1DA03C ; @hook module=Sprites
Blind_SpawnFromMaiden:
{
  JSL Twinrova_FirstFightPrep

  LDX.b #$00 ; Load the boss into sprite index 0

  ; Set the sprite to alive and active
  LDA.b #$09 : STA.w SprState, X

  ; SPRITE CE
  LDA.b #$CE : STA.w $0E20, X

  ; Load the position cache from the maiden follower
  LDA.b $00 : STA.w SprX, X
  LDA.b $01 : STA.w SprXH, X
  LDA.b $02 : SEC : SBC.b #$10 : STA.w SprY, X
  LDA.b $03 : STA.w SprYH, X

  ; Properties and shared startup were loaded before the graphics transfer.

  ; Set SprTimerC
  LDA.b #$C0 : STA.w SprTimerC, X

  ; Set SprGfx
  LDA.b #$00 : STA.w $0DC0, X

  ; Set SprMiscC and bulletproof properties
  LDA.b #$02 : STA.w SprMiscC, X : STA.w SprBulletproof, X

  ; Set the 2nd key / heart piece items taken room flag
  LDA.w $0403 : ORA.b #$20 : STA.w $0403

  ; Clear blinds head spin flag
  STZ.w $0B69

  RTL
}

assert pc() <= $1DA081

; =========================================================
; We are using space from this function to insert the
; Twinrova graphics above, since the prep is now handled
; in the custom sprite code.

org $1DA081
SpritePrep_Blind_PrepareBattle:
{
  ; LDA.l $7EF3CC
  ; CMP.b #$06 ; FOLLOWER 06
  ; BEQ .despawn
  LDA.w $0403 : AND.b #$20 : BEQ .despawn
    LDA.b #$60 : STA.w SprTimerC, X
    LDA.b #$01 : STA.w SprMiscB, X
    LDA.b #$02 : STA.w SprMiscC, X
    LDA.b #$04 : STA.w SprMiscE, X
    LDA.b #$07 : STA.w $0DC0, X
    STZ.w $0B69
    RTL
  .despawn
  STZ.w SprState, X
  RTL
}

assert pc() <= $1DA0B1

org $01B3E1
  RoomDraw_BombableFloor:
    LDA.b $A0
    CMP.w #$00AD

; =========================================================
; Laser trail garnish inherited from Blind's laser attack.
; Currently active but AND #$00 disables the delay check,
; so garnish spawns every frame. Consider adding a delay
; mask (e.g. AND #$03) to reduce particle count post-beta.

org $1DA0B1
BlindLaser_SpawnTrailGarnish:
{
  LDA.w SprDelay, X : AND.b #$00 : BNE .exit

  PHX
  TXY

  LDX.b #$1D

  .next_slot
  LDA.l $7FF800, X : BEQ .free_slot

  DEX
  BPL .next_slot

  DEC.w $0FF8
  BPL .use_search_index

  LDA.b #$1D : STA.w $0FF8

  .use_search_index
  LDX.w $0FF8

  .free_slot
  LDA.b #$0F ; GARNISH 0F
  STA.l $7FF800, X
  STA.w $0FB4

  LDA.w $0DC0, Y : STA.l $7FF9FE, X
  TYA : STA.l $7FF92C, X

  LDA.w SprX, Y : STA.l $7FF83C, X
  LDA.w SprXH, Y : STA.l $7FF878, X
  LDA.w SprY, Y : CLC : ADC.b #$10 : STA.l $7FF81E, X
  LDA.w SprYH, Y : ADC.b #$00 : STA.l $7FF85A, X

  LDA.b #$0A : STA.l $7FF90E, X

  PLX

  .exit
  RTL
}

; =========================================================
; Mantle and Maiden

org $068841 ; @hook module=Sprites
  JSL NewMantlePrep
  RTS

org $1AFC52
  db $06 ; check for maiden instead of zelda

org $1AFCA7
  ; Tiles
  db $0C, $0E, $0C, $2C, $2E, $2C
  ; Mantle Properties :
  db $3D, $3D, $7D, $3D, $3D, $7D

pullpc

NewMantlePrep:
{
  LDA.w SprY, X : CLC : ADC.b #$07 : STA.w SprY, X
  LDA.w SprX, X : CLC : ADC.b #$08 : STA.w SprX, X
  LDA $7EF0DA : AND #$0F : BEQ +
    LDA.w SprX, X : CLC : ADC.b #$28 : STA.w SprX, X
  +
  RTL
}

pushpc

org $09A1EC : JSL CheckForMaidenInLibrary ; @hook module=Sprites name=CheckForMaidenInLibrary kind=jsl target=CheckForMaidenInLibrary

; Prevent mantle from setting spawn point
org $1AFC6D
NOP #6
; LDA.b #$04
; STA.l $7EF3C8

pullpc

CheckForMaidenInLibrary:
{
  LDA $A0 : CMP.b #$BD : BNE .notTheLibrary
    LDA $11 : BNE .notTheLibrary
      LDA $7FF9D2 : BNE .dialogue_played
        LDA #$1D : LDY #$00
        JSL Sprite_ShowMessageUnconditional
        LDA #$01 : STA $7FF9D2
      .dialogue_played
  .notTheLibrary
  ; Check for blind room vanilla
  REP #$20
  LDA.b $A0
  RTL
}
