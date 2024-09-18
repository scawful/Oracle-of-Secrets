; =========================================================
; Dark Link Boss

!SPRID              = $C1 ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 4   ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 34  ; Number of Health the sprite have
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
!DeflectProjectiles = 01  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 01  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss
%Set_Sprite_Properties(Sprite_DarkLink_Prep, Sprite_DarkLink_Long);

; =========================================================

Sprite_DarkLink_Long:
{  
  PHB : PHK : PLB

  ; ADD GANON CODE if subtype == 05
  LDA.w SprSubtype, X : CMP #$05 : BNE .NotGanon
    ; JSR Sprite_Ganon_Draw 
    JSL Sprite_CheckActive   ; Check if game is not paused (Prevent timers from running if game is paused)
    BCC .SpriteIsNotActive2   ; Skip Main code is sprite is innactive
    JSR Sprite_Ganon_Main ; do ganon instead
    .SpriteIsNotActive2
    PLB ; Get back the databank we stored previously
    RTL ; Go back to original code

  .NotGanon
  LDA.w SprAction, X : CMP.b #$01 : BNE .normal_draw
    ; JSR Sprite_DarkLink_Draw ; Call the draw code
    .sword_draw
    JSR Sprite_DarkLink_Draw_Sprite_SwordAttack_Draw
    BRA .skipnormal_draw
  .normal_draw
  CMP.b #$09 : BEQ .sword_draw
  LDA.w SprSubtype, X : BNE .skipnormal_draw
    JSR Sprite_DarkLink_Draw 
  .skipnormal_draw

  LDA.w SprAction, X : CMP.b #11 : BCS .notdying
    LDA.w SprHealth, X : CMP.b #$20 : BCS .notdying
      LDA.w SprMiscC, X : BNE +
        ; check if action is 00 otherwise wait
        LDA.w SprAction, X : BNE .notdying 
          %GotoAction(15) ; enraging instead
          BRA .SpriteIsNotActive
      +

      LDA #$30 : STA.w SprTimerA, X
      LDA #$08 : STA.w SprTimerB, X
      STZ.w SprFrame, X
      STZ.w SprMiscF, X
      STZ.w SprMiscD, X
      %GotoAction(11)
      BRA .SpriteIsNotActive
  .notdying

  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_DarkLink_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

; =========================================================

Sprite_DarkLink_Prep:
{
  PHB : PHK : PLB

  ; REP #$20 ; P is still on stack, so we don't even need to fix this
  ; LDX #$10
  ; --
  ;   LDA.l DarkLink_Palette, X : STA $7EC600, X
  ; DEX : DEX : BNE --
  ; INC $15 ; Refresh Palettes
  ; SEP #$20

  PLB

  JSL GanonInit

  LDA #$CF : STA.w SprTimerA, X ; wait timer before falling
  LDA #$7F : STA.w SprHeight, X

  LDA #$78 : STA.w SprX, X
  LDA #$58 : STA.w SprY, X

  LDA #$00 : STA.w SprMiscE, X
  LDA #$00 : STA.w SprMiscC, X ; Enraging 
  LDA #$C0 : STA.w SprHealth, X
  %GotoAction(4)

  RTL
}

DarkLink_Palette:
  dw $7FFF, $14A5, $2108, $294A, $1CF5, $7E4E, $3DEF, $6FF4

; =========================================================

Sprite_DarkLink_Main:
{
  LDA.w SprAction, X : JSL UseImplicitRegIndexedLocalJumpTable

  dw Handler
  dw SwordSlash
  dw JumpBack
  dw JumpAttackUp
  dw JumpAttackDown
  dw JumpAttackPrep
  dw JumpAttackShake
  dw WalkAction
  dw Damaged
  dw RecoilSword
  dw SwordSubtype
  dw DyingSpin
  dw DeadDespawn
  dw OpenDoor
  dw Dead
  dw Enraging

  Handler:
  {  
    LDA.w SprSubtype, X : CMP #$01 : BNE +
      %SetTimerA(16)
      %GotoAction(10)
      RTS
    +

    LDA.w SprMiscF, X : BNE .no_damage
      JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
        LDA.w SprTimerA, X : BNE .already_taking_damage
          LDA.w $0224 : CMP #$03 : BNE .not_more_damage
            LDA.w SprHealth, X : SEC : SBC #$04 : STA.w SprHealth, X
        .not_more_damage
        .already_taking_damage

        LDA #$20
        JSL Sprite_ApplySpeedTowardsPlayer
        LDA.w SprXSpeed, X : EOR #$FF : STA.w SprXSpeed, X
        LDA.w SprYSpeed, X : EOR #$FF : STA.w SprYSpeed, X
        LDA.b #$10 : STA.w $0F80,X
        LDA.b #$20 : STA.w SprTimerA, X
        LDA #$26 : STA.w $012E
        %GotoAction(8)
        RTS
    .no_damage
    JSL Sprite_CheckDamageToPlayer


    LDA #$10
    JSL Sprite_ApplySpeedTowardsPlayer

    REP #$20

    LDA $0FD8 ; Sprite X
    SEC : SBC $22 ; - Player X
    BPL +
    EOR #$FFFF
    +
    STA $00 ; Distance X (ABS)

    LDA $0FDA ; Sprite Y
    SEC : SBC $20 ; - Player Y
    BPL +
    EOR #$FFFF
    +
    ; Add it back to X Distance
    CLC : ADC $00 : STA $02 ; distance total X, Y (ABS)

    CMP #$0020 : BCS .toofarsword
    .dosword
    SEP #$20
    LDA.w SprTimerC, X : BNE ++
      ; attempt a slash if we can

      LDA.w SprMiscD, X : BNE +
      STZ.w SprFrame, X
      BRA .skipdirections
      +
      LDA.w SprMiscD, X : CMP #$01 : BNE +
      LDA.b #06 : STA.w SprFrame, X
      BRA .skipdirections
      +
      LDA.w SprMiscD, X : CMP #$02 : BNE +
      LDA.b #12 : STA.w SprFrame, X
      BRA .skipdirections
      +
      LDA.b #18 : STA.w SprFrame, X
      +

      .skipdirections

      JSR SpawnSwordDamage
      %GotoAction(1)
    ++
    REP #$20
    .toofarsword
    LDA $02 : CMP #$002B : BCS .toofardodge
    SEP #$20

    LDA.w SprMiscF : BNE .toofardodge


    LDA.w $0354 : CMP #$27 : BEQ .attemptToDodge
    CMP #$02 : BEQ .attemptToDodge
    CMP #$06 : BEQ .attemptToDodge
    CMP #$0F : BNE .toofardodge

    ; only once per slash !

    .attemptToDodge

    ;check if we are using spin attack
    LDA.b $3C : CMP #$90 : BNE .nospin

    ; determine if player is going to dodge it or not
    LDA $1A : AND #$01 : BEQ .dodge

    .nospin
    LDA.w SprMiscB, X : CMP.w $0354 : BEQ .toofardodge


    LDA.w SprMiscC, X : BNE .enrageddodge
    LDA $1A : AND #$03 : BEQ .toofardodge ; 50/50 chances of dodging
    BRA .dodge
    .enrageddodge
    LDA $1A : AND #$07 : BEQ .toofardodge ; 50/50 chances of dodging

    .dodge
    LDA #$16
    JSL Sprite_ApplySpeedTowardsPlayer
    LDA.w SprXSpeed, X : EOR #$FF : STA.w SprXSpeed, X
    LDA.w SprYSpeed, X : EOR #$FF : STA.w SprYSpeed, X
    LDA.b #$1A : STA.w $0F80,X

    %GotoAction(2)

    RTS

    .toofardodge

    SEP #$20


    .linknotattacking
    LDA.w $0354 : STA.w SprMiscB, X

    STZ $02 ; x direction if non zero = negative
    STZ $03 ; y direction

    LDA.w SprXSpeed, X : BPL .positiveX
    STA $02
    EOR #$FF
    .positiveX
    STA $00 ; X speed (abs)

    LDA.w SprYSpeed, X : BPL .positiveY
    STA $03
    EOR #$FF
    .positiveY
    STA $01 ; Y speed (abs)


    LDA.w SprXSpeed, X : CMP.b #$08 : BCC .zeroXSpeed
    BPL .positiveXspeed
    LDA #$F0 : STA.w SprXSpeed, X
    BRA .doYspeed
    .positiveXspeed
    LDA #$10 : STA.w SprXSpeed, X
    BRA .doYspeed
    .zeroXSpeed
    STZ.w SprXSpeed, X
    .doYspeed
    LDA.w SprYSpeed, X : CMP.b #$08 : BCC .zeroYSpeed

    BPL .positiveYspeed
    LDA #$F0 : STA.w SprYSpeed, X
    BRA .ignorezerospeed
    .positiveYspeed
    LDA #$10 : STA.w SprYSpeed, X
    BRA .ignorezerospeed
    .zeroYSpeed
    STZ.w SprYSpeed, X
    .ignorezerospeed

    LDA.w SprXSpeed, X : BEQ .nodiagonal 
    LDA.w SprYSpeed, X : BEQ .nodiagonal 
    BPL .diagoyspeedpositive
    LDA #$F5 : STA.w SprYSpeed, X
    BRA .dodiagox
    .diagoyspeedpositive
    LDA #$0B : STA.w SprYSpeed, X


    .dodiagox
    LDA.w SprXSpeed, X
    BPL .diagoxspeedpositive
    LDA #$F5 : STA.w SprXSpeed, X
    BRA .nodiagonal
    .diagoxspeedpositive
    LDA #$0B : STA.w SprXSpeed, X

    .nodiagonal


    LDA.w SprTimerD, X : BNE +
    TXY ; save X in Y
    JSL GetRandomInt : CMP #$3F : BCC .donothing
    LDA.w SprMiscF, X : BEQ .notusingcape
    JSR Cape
    BRA .donothing
    .notusingcape
    JSL GetRandomInt : AND #$03 : ASL ; use that as jump table
    TAX ; set X to do the jump table
    JSR (ActionJumpTable, X)

    .donothing
    LDA.w SprMiscC, X : BEQ .notenraged
    JSL GetRandomInt : AND #$3F : CLC : ADC #$20
    BRA .settimer
    .notenraged
    JSL GetRandomInt : AND #$3F : CLC : ADC #$50
    .settimer
    STA.w SprTimerD, X
    ;RTS
    +




    .DoWalk
    JSL Sprite_MoveLong

    LDA.b $01 : CMP.b $00 : BCC .xwassmaller
    ; if X is smaller than y were moving on y axis
    LDA $03 : BNE .up
    ; down
    STZ.w SprMiscD, X
    LDA.w SprTimerB, X : BNE +
        LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #12 : BCC .noframereset1
        .resetframe1
        LDA.b #4 : STA.w SprFrame, X
        .noframereset1
        CMP #4 : BCC .resetframe1
        LDA.b #4 : STA.w SprTimerB, X
        LDA.w SprTimerA, X : BNE +
    +
    BRA .end
    .up
    LDA #$01 : STA.w SprMiscD, X
    LDA.w SprTimerB, X : BNE +
        LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #20 : BCC .noframereset2
        .resetframe2
        LDA.b #12 : STA.w SprFrame, X
        .noframereset2
        CMP #12 : BCC .resetframe2
        LDA.b #4 : STA.w SprTimerB, X
    +
    BRA .end
    .xwassmaller
    ; were moving on x axis
    LDA $02 : BNE .left
    ; right
    LDA #$02 : STA.w SprMiscD, X
    LDA.w SprTimerB, X : BNE +
        LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #24 : BCC .noframereset3
        .resetframe3
        LDA.b #20 : STA.w SprFrame, X
        .noframereset3
        CMP #20 : BCC .resetframe3
        LDA.b #4 : STA.w SprTimerB, X
    +
    BRA .end
    .left
    LDA #$03 : STA.w SprMiscD, X
    LDA.w SprTimerB, X : BNE +
        LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #28 : BCC .noframereset4
        .resetframe4
        LDA.b #24 : STA.w SprFrame, X
        .noframereset4
        CMP #24 : BCC .resetframe4
        LDA.b #4 : STA.w SprTimerB, X
    +
    BRA .end

    .end
    RTS


    ActionJumpTable:
    dw JumpAttack ;00
    dw Cape ;02
    dw Bomb ;04
    dw BombThrow ;04
    ;dw Walk ;06



    Bomb:
    {
      TYX ; get back sprite index

      ;second guess itself because it can spawn too many bombs
      LDA $1A : AND #$01 : BNE .spawn_failed ; 50/50 chances

      LDA.b #$4A
      LDY.b #$0B
      JSL $1DF65F : BMI .spawn_failed

      JSL $09AE64

      ; ... but once spawned, transmute it to an enemy bomb.
      JSL $06AD50
      JSL GetRandomInt : AND #$7F : CLC : ADC #$20
      STA $0E00, Y
      .spawn_failed
      RTS
    }

    BombThrow:
    {
      TYX ; get back sprite index

      ;second guess itself because it can spawn too many bombs
      LDA $1A : AND #$01 : BNE .spawn_failed ; 50/50 chances

      LDA.b #$4A
      LDY.b #$0B
      JSL $1DF65F : BMI .spawn_failed
      JSL $09AE64
      ; ... but once spawned, transmute it to an enemy bomb.
      JSL $06AD50

      PHX
      TYX
      LDA.b #$28 : JSL Sprite_ApplySpeedTowardsPlayer
      LDA.b #$01 : STA $0DB0, X
      LDA.b #$16 : STA $0F80, X
      JSL GetRandomInt : AND #$7F : CLC : ADC #$20
      STA $0E00, X
      PLX

      .spawn_failed
      RTS
    }


    Cape:
    {
      TYX ; get back sprite index
      LDA.w SprMiscF, X : BNE +
      LDA $1A : AND #$01 : BNE .nocape ; 50/50 chances
      +
      JSL $05AB9C
      LDA.w SprMiscF, X : EOR #$01 : STA.w SprMiscF, X
      .nocape
      RTS

      Walk:
      TYX ; get back sprite index
      %GotoAction(7)
      JSL GetRandomInt : AND #$1F : CLC : ADC #$18
      STA.w SprTimerA, X
      JSL GetRandomInt
      AND #$03
      TAY
      LDA speedTableX, Y : STA.w SprXSpeed, X
      LDA speedTableY, Y : STA.w SprYSpeed, X

      RTS
    }


    JumpAttack:
    {
      TYX ; get back sprite index
      LDA #$20
      JSL Sprite_ApplySpeedTowardsPlayer
      LDA.b #$28 : STA.w $0F80,X
      LDA.b #$10 : STA.w SprTimerA, X
      %GotoAction(5)
      JSL GetRandomInt : AND #$3F : CLC : ADC #$50
      STA.w SprTimerD, X
      ; that one is popping the RTS to end sprite entirely
      ;PLA : PLA
      RTS
    }


    SpawnSwordDamage:
    {
      LDA #24 : STA.w SprTimerC, X
      LDA.w SprMiscC, X : BEQ +
      LDA #15 : STA.w SprTimerC, X ;faster if enraged
      +
      LDA #$06 : STA.w SprTimerB, X
      LDA #$03 : STA.w $012E


      LDA #$C1 ; SPRID
      JSL Sprite_SpawnDynamically
      JSL Sprite_SetSpawnedCoords
      PHX
      LDA #$01 : STA.w SprSubtype, Y
      LDA.w SprMiscD, X
      TYX
      TAY
      LDA.w SprX, X : CLC : ADC.w DirOffsetX, Y : STA.w SprX, X
      LDA.w SprY, X : CLC : ADC.w DirOffsetY, Y : STA.w SprY, X

      PLX
      RTS
    }

    DirOffsetX:
    db $00, $00, $0E, $F2
    DirOffsetY:
    db $0E, $F2, $00, $00
  }

  SwordSlash:
  {
    JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
    LDA.w SprTimerA, X : BNE .already_taking_damage
    LDA.w $0224 : CMP #$03 : BNE .not_more_damage
    LDA.w SprHealth, X : SEC : SBC #$04 : STA.w SprHealth, X
    .not_more_damage
    .already_taking_damage

      LDA #$05 : STA.w $012E ; clinking sound
      LDA #$20
      JSL Sprite_ApplySpeedTowardsPlayer
      ;restore life removed by the checkdamage
      STZ.w $0CE2, X

            
        LDA #$20 : STA $29 : STA $C7
        
        STZ $24
        STZ $25
        
        LDA.w SprYSpeed, X  : STA $27 : EOR #$FF : STA.w SprYSpeed, X
        LDA.w SprXSpeed, X  : STA $28 : EOR #$FF : STA.w SprXSpeed, X
        LDA.b #$08 : STA.w $0F80, X
        LDA.b #$10 : STA $47 : STA $46
        %SetTimerC(16)
      %GotoAction(09)
        
      RTS

    .no_damage

    ;LDA.w SprTimerD, X : BEQ +

    ;RTS
    ;+

    LDA.w SprMiscD, X : BNE .notdown
    LDA.w SprTimerB, X : BNE .notdown
        LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #6 : BCC .noframereset1
        .resetframe1
        LDA.b #0 : STA.w SprFrame, X
        .noframereset1
        LDA.b #4 : STA.w SprTimerB, X
    BRA .end

    .notdown
    LDA.w SprMiscD, X : CMP #$01 : BNE .notup
    LDA.w SprTimerB, X : BNE .notup
        LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #12 : BCC .noframereset2
        .resetframe2
        LDA.b #6 : STA.w SprFrame, X
        .noframereset2
        CMP #6 : BCC .resetframe2
        LDA.b #4 : STA.w SprTimerB, X
    BRA .end
    .notup
    LDA.w SprMiscD, X : CMP #$02 : BNE .notright

    LDA.w SprTimerB, X : BNE .notright
        LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #18 : BCC .noframereset3
        .resetframe3
        LDA.b #12 : STA.w SprFrame, X
        .noframereset3
        CMP #12 : BCC .resetframe3
        LDA.b #4 : STA.w SprTimerB, X
    BRA .end

    .notright
    LDA.w SprMiscD, X : CMP #$03 : BNE .notleft
    LDA.w SprTimerB, X : BNE .end
        LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #24 : BCC .noframereset4
        .resetframe4
        LDA.b #18 : STA.w SprFrame, X
        .noframereset4
        CMP #18 : BCC .resetframe4
        LDA.b #4 : STA.w SprTimerB, X
    .notleft
    .end

    LDA.w SprTimerC, X : BNE +
      %SetTimerC(20)
      %GotoAction(00)
    +

    RTS
  }

  JumpBack:
  {
    JSL Sprite_MoveXyz

    DEC.w $0F80,X : DEC.w $0F80,X

    LDA.w $0F70,X : BPL .aloft

    STZ.w $0F70,X
    %GotoAction(0)

    .aloft

    JSL Sprite_CheckTileCollision


    RTS
  }

  JumpAttackUp:
  {
    JSL Sprite_MoveXyz
    LDA.w $0F80,X : BEQ +
    DEC.w $0F80,X
    +
    LDA #36 : STA.w SprFrame, X

    REP #$20

    LDA $20 : STA $06
    LDA $22 : STA $04

    SEP #$20
    LDA.w SprMiscC, X : BEQ +
    LDA #$28 : BRA .movespeed
    +
    LDA #$20
    .movespeed
    JSL Sprite_ProjectSpeedTowardsEntityLong
    LDA.b $01 : STA.w SprXSpeed, X 
    LDA.b $00 : STA.w SprYSpeed, X 


    REP #$20

    LDA $0FD8 ; Sprite X
    SEC : SBC $22 ; - Player X
    BPL +
    EOR #$FFFF
    +
    STA $00 ; Distance X (ABS)

    LDA $0FDA ; Sprite Y
    SEC : SBC $20 ; - Player Y
    BPL +
    EOR #$FFFF
    +
    ; Add it back to X Distance
    CLC : ADC $00 : STA $02 ; distance total X, Y (ABS)

    CMP #$0008 : BCS .toofar
    SEP #$20
    STZ.w SprXSpeed, X 
    STZ.w SprYSpeed, X 
    %GotoAction(4)
    .toofar
    SEP #$20

    RTS
  }

  JumpAttackDown:
  {
    LDA.w SprTimerA, X : BNE .wait

    JSL Sprite_MoveXyz
    JSL Sprite_CheckDamageToPlayer

    LDA #37 : STA.w SprFrame, X

    DEC.w $0F80,X : DEC.w $0F80,X : DEC.w $0F80,X : DEC.w $0F80,X

    LDA.w $0F70,X : BPL .aloft


    STZ.w $0F70,X

    LDA.b #$90 : STA.w SprTimerC, X
    LDA.b #$10 : STA.w SprTimerA, X

    LDA.b #$0C : STA $012E
    %GotoAction(06)

    .aloft

    .wait

    RTS
  }

  JumpAttackPrep:
  {
    LDA #35 : STA.w SprFrame, X

    LDA.w SprTimerA, X : BNE +
    %GotoAction(3)
    +

    RTS
  }

  JumpAttackShake:
  {
    PHX
    JSL Sprite_CheckDamageToPlayer

    REP #$20

    ; Load the frame counter.
    LDA $1A : AND.w #$0001 : ASL A : TAX

    ; Shake the earth! This is the earthquake type effect.
    LDA.l $01C961, X : STA $011A
    LDA.l $01C965, X : STA $011C

    SEP #$20
    PLX
    LDA.w SprTimerA, X : BNE +

    LDA.w SprMiscA, X : BNE .nomessage
    LDA #$01 : STA.w SprMiscA, X
    %ShowUnconditionalMessage($016F)

    LDA.b #$15 : STA $012C
    .nomessage

    ; IF health is a certain level spawn crumbling tiles
    ;2, 3, 4, 5
    LDA.w SprMiscC, X : BEQ .tilesAreFallingAlready
    LDA.w $0B00 : BNE .tilesAreFallingAlready
    LDY.w SprMiscE, X
    LDA.w CrumbleSpr, Y
    STA.w $0B00 ; overlord index 00
    LDA.b $23 : STA.w $0B10 ; x high byte
    LDA.b $21 : STA.w $0B20 ; y high byte
    LDA.w CrumbleSprX, Y : STA.w $0B08
    LDA.w CrumbleSprY, Y : STA.w $0B18
    STZ.w $0B30
    STZ.w $0B38
    STZ.w $0B28
    INC.w SprMiscE, X
    .tilesAreFallingAlready

    %GotoAction(0)

    +

    RTS
  }

  CrumbleSpr:
  db $0C, $0D, $0E, $0F

  CrumbleSprX:
  db $18, $D8, $D8, $18

  CrumbleSprY:
  db $28, $28, $D8, $D8

  WalkAction:
  {
    JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
    LDA.w SprTimerA, X : BNE .already_taking_damage
    LDA.w $0224 : CMP #$03 : BNE .not_more_damage
    LDA.w SprHealth, X : SEC : SBC #$04 : STA.w SprHealth, X
    .not_more_damage
    .already_taking_damage

    LDA #$20
    JSL Sprite_ApplySpeedTowardsPlayer
    LDA.w SprXSpeed, X : EOR #$FF : STA.w SprXSpeed, X
    LDA.w SprYSpeed, X : EOR #$FF : STA.w SprYSpeed, X
    LDA.b #$10 : STA.w $0F80,X
    LDA.b #$20 : STA.w SprTimerA, X

    %GotoAction(8)
    RTS
    .no_damage
    JSL Sprite_CheckDamageToPlayer

    LDA.w SprTimerA, X : BNE +

      JSL GetRandomInt : AND #$3F : CLC : ADC #$50
      STA.w SprTimerA, X
      %GotoAction(00)

    +

    STZ $02 ; x direction if non zero = negative
    STZ $03 ; y direction

    LDA.w SprXSpeed, X : BPL .positiveX
    STA $02
    EOR #$FF
    .positiveX
    STA $00 ; X speed (abs)

    LDA.w SprYSpeed, X : BPL .positiveY
    STA $03
    EOR #$FF
    .positiveY
    STA $01 ; Y speed (abs)

    JMP Handler_DoWalk

    RTS
  }

  ; right

  speedTableX:
  db 16, -16, 00, 00
  speedTableY:
  db 00, 00, 16, -16

  Damaged:
  {
    JSL Sprite_MoveXyz

    LDA.w SprYSpeed, X : BPL +
    INC.w SprYSpeed, X
    BRA .next
    +
    DEC.w SprYSpeed, X

    .next

    LDA.w SprXSpeed, X : BPL +
    INC.w SprXSpeed, X
    BRA .done
    +
    DEC.w SprXSpeed, X
    .done

    DEC.w $0F80,X : DEC.w $0F80,X

    LDA.w $0F70,X : BPL .aloft

    STZ.w SprYSpeed, X
    STZ.w SprXSpeed, X

    STZ.w $0F70,X

    .aloft

    LDA.w SprTimerA, X : BNE +

    %GotoAction(0)
    STZ.w SprTimerD, X
    STZ.w SprMiscF, X
    RTS
    +
    AND #$01 : STA.w SprMiscF, X ; flashing code


    RTS
  }

  RecoilSword:
  {
    JSL Sprite_MoveLong
    LDA.w SprTimerC, X : BNE +
      %SetTimerC(20)
      %GotoAction(00)
    +

    JSL Sprite_CheckTileCollision

    RTS
  }

  SwordSubtype:
  {
    LDA.w SprTimerA, X : BNE +
    STZ.w SprState, X ; kill the sprite
    +
    CMP #$10 : BCS + ; only check for damage if sword has reached halfway
    JSL Sprite_CheckDamageToPlayer
    +
    RTS
  }

  DyingSpin:
  {
    STZ.w SprHeight, X
    LDA.w SprTimerB, X : BNE ++

    LDA.b #$08 : STA.w SprTimerB, X
    LDA.w SprMiscD, X : INC : STA.w SprMiscD, X : CMP #$04 : BNE + 
    STZ.w SprMiscD, X
    LDA #$00
    +
    TAY
    LDA.w dyingframes, Y : STA.w SprFrame, X

    ++

    LDA.w SprTimerA, X : BNE +
    LDA.b #$60 : STA.w SprTimerA, X 
    LDA.b #$12 : STA.w SprTimerB, X
    LDA.b #44 : STA.w SprFrame, X
    %GotoAction(12)
    +
    RTS
  }

  dyingframes:
  db $00, $02, $01, $03

  DeadDespawn:
  {
    LDA.w SprTimerB, X : BNE +
      LDA.b #45 : STA.w SprFrame, X

    +


    LDA.w SprTimerA, X : CMP #$28 : BCS +
    AND #$04
    STA.w SprMiscF, X
    +


    LDA.w SprTimerA, X : BNE +
    %GotoAction(13)
    +
      
    RTS
  }

  ; TODO: Trigger cutscene for ending Fortress of Secrets
  OpenDoor:
  {
    INC.w SprMiscF, X
    ;LDA #$1A : STA.b $11 ; ganon open door routine
    ; handled by the room tag?
    LDA #$04 : STZ.w $0DD0, X
    LDA.b #$80 : STA $0403
    %GotoAction(14)

    RTS
  }

  Dead:
  {
    
    RTS
  }

  Enraging:
  {
    PHX
    REP #$20 ; P is still on stack, so we don't even need to fix this
        LDX #$20
        --
        LDA dlinkPalRed, X : STA $7EC600, X
        DEX : DEX : BNE --
        INC $15 ;Refresh Palettes
        
    SEP #$20
    PLX

    INC.w SprMiscC, X ; Enraging

    LDA #$80 : STA.w SprHealth, X

    %ShowUnconditionalMessage($170)

    %GotoAction(00)

    RTS
  }

  dlinkPalRed:
  dw #$7FFF, #$14A5, #$2108, #$294A, #$1CF5, #$7E4E, #$001D, #$6FF4
}

; =========================================================

Sprite_DarkLink_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprMiscF, X : BNE .justshadow


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
      
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
      
  PLY : INY
      
  PLX : DEX : BPL .nextTile

  PLX

  .justshadow
  LDA.w SprHeight, X : CMP #$5F : BCS +
  LDA.w SprAction, X : CMP #11 : BCS +
  JSL Sprite_DrawShadow
  +
  RTS





  .Sprite_SwordAttack_Draw
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprMiscF, X : BNE .justshadow

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index2, Y : STA $06


  PHX
  LDX .nbr_of_tiles2, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile2

  PHX ; Save current Tile Index?
      
  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX 

  REP #$20

  LDA $00 : CLC : ADC .x_offsets2, X : STA ($90), Y
  AND.w #$0100 : STA $0E 
  INY
  LDA $02 : CLC : ADC .y_offsets2, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y2

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y2

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr2, X : STA ($90), Y
  INY
  LDA .properties2, X : STA ($90), Y

  PHY 
      
  TYA : LSR #2 : TAY
      
  LDA .sizes2, X : ORA $0F : STA ($92), Y ; store size in oam buffer
      
  PLY : INY
      
  PLX : DEX : BPL .nextTile2

  PLX

  RTS


  .start_index2
  db $00, $03, $06, $09, $0C, $0F, $11, $14, $17, $1A, $1D, $20, $22, $25, $28, $2B, $2E, $31, $33, $36, $39, $3C, $3F, $42
  .nbr_of_tiles2
  db 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 1
  .x_offsets2
  dw 0, 0, -12
  dw 0, -6, 0
  dw 0, 2, 0
  dw 0, 0, 5
  dw 0, 15, 0
  dw 0, 0
  dw 0, 0, 15
  dw 10, 0, 0
  dw 4, 0, 0
  dw -5, -1, 0
  dw -8, -1, 0
  dw 0, 0
  dw 0, 0, -2
  dw 11, 0, -1
  dw 0, 0, 14
  dw 0, 0, 14
  dw 0, -1, 2
  dw 0, -2
  dw -4, 0, 2
  dw -11, 0, 0
  dw -12, 0, 0
  dw 0, -1, -14
  dw 0, 1, -2
  dw 0, 1
  .y_offsets2
  dw 0, -16, 0
  dw 0, 8, -7
  dw 0, 11, -6
  dw 1, -4, 13
  dw 0, 2, -6
  dw 0, -7
  dw -1, -17, 0
  dw -10, 0, -8
  dw -14, 0, -8
  dw -17, 0, -9
  dw -13, 0, -8
  dw 0, -8
  dw -12, 0, -8
  dw -10, 0, -8
  dw 0, -8, -4
  dw 0, -8, 0
  dw 0, -8, 10
  dw 0, -8
  dw -12, 0, -7
  dw -8, 0, -7
  dw -3, 0, -7
  dw 0, -7, 0
  dw 0, -8, 9
  dw 0, -8
  .chr2
  db $2C, $0C, $88
  db $0A, $84, $06
  db $0E, $82, $06
  db $0E, $06, $80
  db $2E, $86, $06
  db $2E, $06
  db $6E, $4E, $88
  db $84, $60, $08
  db $82, $60, $08
  db $80, $62, $08
  db $82, $62, $08
  db $64, $08
  db $80, $46, $00
  db $84, $48, $02
  db $4A, $04, $86
  db $4A, $04, $88
  db $4C, $00, $82
  db $4C, $00
  db $80, $46, $00
  db $84, $48, $02
  db $86, $4A, $04
  db $4A, $04, $88
  db $4C, $00, $82
  db $4C, $00
  .properties2
  db $31, $31, $71
  db $31, $F1, $31
  db $31, $F1, $31
  db $31, $31, $F1
  db $31, $B1, $31
  db $31, $31
  db $31, $31, $31
  db $31, $31, $31
  db $31, $31, $31
  db $31, $31, $31
  db $71, $31, $31
  db $31, $31
  db $31, $31, $31
  db $31, $31, $31
  db $31, $31, $31
  db $31, $31, $31
  db $31, $31, $B1
  db $31, $31
  db $71, $71, $71
  db $71, $71, $71
  db $71, $71, $71
  db $71, $71, $71
  db $71, $71, $F1
  db $71, $71
  .sizes2
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02

  ; =========================================================

  .start_index
  db $00, $02, $04, $06, $08, $0A, $0C, $0E, $10, $12, $14, $16, $18, $1A, $1C, $1E, $20, $22, $24, $26, $28, $2A, $2C, $2E, $30, $32, $34, $36, $38, $3A, $3C, $3E, $40, $42, $44, $45, $48, $4B, $4E, $50, $52, $54, $56, $58, $5A, $5C
  .nbr_of_tiles
  db 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, -2
  dw 0, 2
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, -2
  dw 0, 0
  dw 0, 0
  dw 0, -1
  dw 0, 2
  dw 0, 1
  dw 0, 1
  dw 0, 1
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw -1, 0
  dw 0
  dw 0, 0, 8
  dw 0, 0, 5
  dw 0, 0, -2
  dw 0, -2
  dw 0, -1
  dw 0, -1
  dw 0, 1
  dw 0, 0
  dw 0, 1
  dw 0, 1
  dw -4, 12
  .y_offsets
  dw 0, -6
  dw 0, -6
  dw 0, -8
  dw 0, -8
  dw 0, -6
  dw 0, -6
  dw 0, -7
  dw 0, -6
  dw 0, -6
  dw 0, -6
  dw 0, -7
  dw 0, -6
  dw 0, -6
  dw 0, -6
  dw 0, -7
  dw 0, -6
  dw 0, -6
  dw 0, -6
  dw 0, -7
  dw 0, -6
  dw 0, -8
  dw 0, -8
  dw 0, -9
  dw 0, -8
  dw 0, -8
  dw 0, -8
  dw 0, -9
  dw 0, -8
  dw 0, -16
  dw 0, -8
  dw 0, -7
  dw 0, -16
  dw 0, -8
  dw 0, -9
  dw 0
  dw 0, -7, -12
  dw 0, -7, -13
  dw 0, -4, 10
  dw 0, -8
  dw 0, -8
  dw 0, -8
  dw 0, -9
  dw 0, -8
  dw 0, -8
  dw 0, -8
  dw 0, 0
  .chr
  db $42, $06
  db $44, $08
  db $40, $00
  db $40, $00
  db $42, $06
  db $24, $06
  db $26, $06
  db $24, $06
  db $42, $06
  db $24, $06
  db $26, $06
  db $24, $06
  db $44, $08
  db $28, $08
  db $2A, $08
  db $28, $08
  db $44, $08
  db $28, $08
  db $2A, $08
  db $28, $08
  db $40, $00
  db $20, $02
  db $22, $04
  db $20, $02
  db $40, $00
  db $20, $02
  db $22, $04
  db $20, $02
  db $2C, $0C
  db $0A, $06
  db $0E, $06
  db $6E, $4E
  db $60, $08
  db $62, $08
  db $06
  db $66, $06, $82
  db $66, $06, $80
  db $68, $06, $80
  db $46, $00
  db $48, $02
  db $4A, $04
  db $46, $00
  db $48, $02
  db $4A, $04
  db $A0, $00
  db $A2, $A4
  .properties
  db $31, $31
  db $31, $31
  db $31, $31
  db $71, $71
  db $31, $31
  db $31, $31
  db $31, $31
  db $31, $31
  db $31, $31
  db $71, $31
  db $71, $31
  db $71, $31
  db $31, $31
  db $31, $31
  db $31, $31
  db $31, $31
  db $31, $31
  db $71, $31
  db $71, $31
  db $71, $31
  db $31, $31
  db $31, $31
  db $31, $31
  db $31, $31
  db $71, $71
  db $71, $71
  db $71, $71
  db $71, $71
  db $31, $31
  db $31, $31
  db $31, $31
  db $31, $31
  db $31, $31
  db $31, $31
  db $31
  db $31, $31, $31
  db $31, $31, $31
  db $31, $31, $B1
  db $31, $31
  db $31, $31
  db $31, $31
  db $71, $71
  db $71, $71
  db $71, $71
  db $31, $31
  db $31, $31
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
}

; =========================================================

GanonInit:
{
  LDA #$C1
  JSL Sprite_SpawnDynamically
  LDA #$05 : STA.w SprSubtype, Y
  LDA $00 : STA.w SprX, Y
  LDA $01 : STA.w SprXH, Y
  
  LDA $02 : STA.w SprY, Y
  LDA $03 : STA.w SprYH, Y

  LDA.b #$30 : STA.w SprTimerA, Y  
  LDA #$1C : STA.w $012C
  RTL
}

; =========================================================

Sprite_Ganon_Main:
{
  LDA.w SprAction, X : JSL UseImplicitRegIndexedLocalJumpTable

  dw Wait
  dw ShowMessage
  dw Fall
  dw FellWait
  dw FadingAwait

  Wait:
  {
    LDA.w SprTimerA, X : BNE .wait
      JSR ApplyDarkLinkGraphics
      LDA.b #$30 : STA.w SprTimerA, X
      %ShowUnconditionalMessage($13E)
      %GotoAction(1)
    .wait
    RTS
  }

  ShowMessage:
  {
    LDA.w SprTimerA, X : BNE .wait
      LDA.b #$90 : STA.w SprTimerA, X
      %GotoAction(2)
    .wait
    RTS
  }

  Fall:
  {
    LDA.w SprTimerA, X : BNE .wait
      LDA.b #$50 : STA.w SprTimerA, X
      LDA #$01 : STA.w SprFrame, X
      INC.w SprMiscA, X
      %GotoAction(3)
    .wait
    RTS
  }

  FellWait:
  {
    LDA.w SprTimerA, X : BNE .wait
      LDA.b #$30 : STA.w SprTimerA, X
      %GotoAction(4)
    .wait
    RTS
  }

  FadingAwait:
  {
    LDA.w SprTimerA, X : BNE .wait
      STZ.w SprState, X
    .wait
    RTS
  }
}

; =========================================================

Sprite_Ganon_Draw:
{
  LDA.w SprAction, X : CMP #$04 : BNE +
  LDA.w SprTimerA, X : AND #$04 : BEQ +
  RTS

  +
  JSL Sprite_PrepOamCoord
  LDA #$18
  JSL OAM_AllocateFromRegionB


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
      
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
      
  PLY : INY
      
  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00, $0C
  .nbr_of_tiles
  db 11, 11
  .x_offsets
  dw 0, 16, 28, 28, 0, 0, 16, 16, 0, 16, -12, -12
  dw 22, 22, -5, -5, -3, 18, 0, 16, 0, 16, 0, 16
  .y_offsets
  dw 7, 7, -9, 7, -16, 0, 0, -16, -19, -19, -9, 7
  dw 10, 26, 11, 27, -21, -21, -11, -11, 5, 5, 10, 10
  .chr
  db $E0, $E0, $C4, $E4, $C2, $E2, $E2, $C2, $C0, $C0, $C4, $E4
  db $C4, $E4, $C4, $E4, $E6, $E6, $C8, $C8, $E8, $E8, $C6, $C6
  .properties
  db $3D, $7D, $7D, $7D, $3B, $3B, $7B, $7B, $3D, $7D, $3D, $3D
  db $7D, $7D, $3D, $3D, $3D, $7D, $3B, $7B, $3B, $7B, $3D, $7D
  .sizes
  db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
}

; =========================================================

ApplyDarkLinkGraphics:
{
    PHX 
    REP #$20               ; A = 16, XY = 8
    LDX #$80 : STX $2100   ; turn the screen off (required)
    LDX #$80 : STX $2115   ; Set the video port register every time we write it increase by 1
    LDA #$5000 : STA $2116 ; Destination of the DMA $5800 in vram <- this need to be divided by 2
    LDA #$1801 : STA $4300 ; DMA Transfer Mode and destination register 
                           ; "001 => 2 registers write once (2 bytes: p, p+1)"
    LDA.w #DarkLinkGraphics : STA $4302     ; Source address where you want gfx from ROM
    LDX.b #DarkLinkGraphics>>16 : STX $4304
    LDA   #$2000 : STA $4305                ; Size of the transfer 4 sheets of $800 each
    LDX   #$01 : STX $420B                  ; Do the DMA 
    LDX #$0F : STX $2100                    ; Turn the screen back on
    SEP #$30
    PLX
    RTS

  DarkLinkGraphics:
    incbin dark_link.bin
}
