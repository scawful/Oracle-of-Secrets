; =========================================================
; Octoboss by Zarby89

pushpc

; Sprite_A2_Kholdstare
org $1E9518
JSL Sprite_Octoboss_Long
RTS

pullpc

BrotherSpr = $0EB0

Sprite_Octoboss_Long:
{
  PHB : PHK : PLB

  LDA.w SprMiscD, X : BNE + ; is the sprite already init
  LDA #$04 : STA.w $0E40, X
  ;LDA.w SprHitbox, X : AND.b #$E0 : ORA.b #$23 : STA.w SprHitbox, X 
  ;LDA.w $0CAA, X : AND #$7F : ORA.b #$81 : STA.w $0CAA, X
  ;LDA.b #$20 : STA.w SprHealth, X
  STZ.w $0BA0, X

  ; TODO: Add a safety check to prevent player from leaving without the item
  ; example if player left without the item, item will be on the ground still
  ; when he'll came back on that screen
  PHX

  LDX.b $8A
  LDA.l $7EF280, X : AND.b #$40 : BEQ .notKiledYet
  PLX ; get back SPR index
  ; Is is killed? do we have the quake medallion tho ?
  LDA.l $7EF349 : BNE .weHaveMedallion
  ; Spawn the medallion
  STZ.w $0DD0, X
  JSR SpawnMedallionAlt ; spawn standing medallion
  BRA .SpriteIsNotActive

  .weHaveMedallion
  ; Do nothing just kill this sprite

  STZ.w $0DD0, X
  BRA .SpriteIsNotActive

  .notKiledYet

  PLX


  ;LDA.w $0E60, X : AND.b #$BF : STA.w $0E60, X
  ;LDA.w $0F50, X : AND.b #$BF : STA.w $0F50, X

  LDA.b #15 : STA.w SprFrame, X
  LDA.b #$87 : STA.l $7EC664 : STA.l $7EC684
  LDA.b #$55 : STA.l $7EC665 : STA.l $7EC685
  INC.b $15
  INC.w SprMiscD, X ; increase it so sprite is initialized
  LDA.l $7EF343 : INC : STA.l $7EF343
  +

  LDA.w SprMiscF, X : BNE +
  JSR Sprite_Octoboss_Draw ; Call the draw code
  BRA ++
  +
  JSR Sprite_Octoboss_Draw2 ; Call the draw code
  ++

  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive


  LDA.w SprMiscF, X : BNE +

  JSR Sprite_Octoboss_Main ; Call the main sprite code
  BRA .SpriteIsNotActive
  +
  JSR Sprite_Octoboss_Secondary ; Call the Secondary sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}


Sprite_Octoboss_Main:
{
  LDA.w SprAction, X; Load the SprAction
  JSL UseImplicitRegIndexedLocalJumpTable; Goto the SprAction we are currently in
  dw WaitForPlayerToApproach ; 00
  dw Emerge ; 01
  dw EmergedShowMessage ; 02
  dw SpawnAndAwakeHisBrother ; 03
  dw WaitForBrotherEmerge ; 04
  dw SpawnPirateHats ; 05

  dw IdlePhase ; 06
  dw PickDirection ; 07
  dw Moving ; 08

  dw WaitMessageBeforeSurrender ; 09
  dw RemoveHat ; 0A
  dw Submerge ; 0B
  dw SubmergeWaitWall ; 0C
  dw EmergeWaitGiveItem ; 0D
  dw SubmergeForeverKill ; 0E




  Sprite_Octoboss_Secondary:
  LDA.w SprAction, X; Load the SprAction
  JSL UseImplicitRegIndexedLocalJumpTable; Goto the SprAction we are currently in
  dw WaitForPlayerToApproach ; 00
  dw Emerge ; 01
  dw WaitDialog ; 02
  dw IdlePhase ; 03
  dw PickDirection ; 04
  dw Moving2 ; 05

  dw IdleWait ; 06
  dw SubmergeForeverKill ; 07


  WaitForPlayerToApproach:
    REP #$20
    LDA.b $20 : CMP #$08C8 
    SEP #$20
    BCS .TooFar
    INC.w SprAction, X
    STZ.w SprFrame, X
    JSR SpawnSplash
    .TooFar
    RTS

    ; 08B8


  Emerge:
    INC.w $02E4 ; prevent link from moving
    LDA.w SprTimerB, X : BNE +
    LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #8 : BCC .noframereset
    INC.w SprAction, X
    .noframereset
    LDA.b #2 : STA.w SprTimerB, X
    +
    RTS


  EmergedShowMessage:
    LDA.b #$48
    LDY.b #$00
    JSL Sprite_ShowMessageUnconditional
    INC.w SprAction, X
    RTS

  WaitDialog:
    RTS


  SpawnAndAwakeHisBrother:
    LDA.b #$40 : STA.w SprTimerC, X ; Will need to adjust
    LDA.b #$3C
    JSL Sprite_SpawnDynamically
    TYA
    STA.w BrotherSpr, X ; keep the brother id
    LDA.b #$D0 : STA.w SprY, Y
    LDA.b #$08 : STA.w SprYH, Y

    LDA.b #$20 : STA.w SprX, Y
    LDA.b #$09 : STA.w SprXH, Y


    LDA.b #$01 : STA.w SprMiscF, Y
    LDA.b #$00 : STA.w SprFrame, Y
    ; Do the spawning code
    INC.w SprAction, X


    RTS


  WaitForBrotherEmerge:
    LDA.w SprTimerC, X : BNE +
        LDA.b #$49
        LDY.b #$00
        JSL Sprite_ShowMessageUnconditional
        LDA #$16 : STA.w SprTimerC, X
        INC.w SprAction, X
    +
    RTS

  SpawnPirateHats:
    LDA.w SprTimerC, X : CMP #$14 : BNE +
    PHX
    JSR SpawnBossPoof
    PLX

    PHX
    LDA.w BrotherSpr, X : TAX
    JSR SpawnBossPoof
    PLX
    +

    LDY.w BrotherSpr, X
    LDA.w SprTimerC, X : CMP #$0A : BNE +
    LDA.b #10 : STA.w SprFrame, X
    LDA.b #10 : STA.w SprFrame, Y
    +

    ; Spawn Walls too
    LDA.w SprTimerC, X : BNE +

    LDA.w SprAction, Y : INC : STA.w SprAction, Y
    LDA.b #$40 
    STA.w SprTimerC, Y
    STA.w SprTimerC, X

    STZ.w $02E4 ; allow link to move again

    INC.w SprAction, X


    ; All the tiles spawned by the sprite 
    ; you can use a sprite/item to get location from ZS
    ; and use the macro GetTilePos($x,$y)

    ;-------------------------------------------------------------
    PHX
    REP #$30
    %GetTilePos($0F, $07)
    LDA.w #$068F
    JSL $1BC97C ; Overworld_DrawMap16_Persist

    %GetTilePos($10, $07)
    LDA.w #$068F
    JSL $1BC97C ; Overworld_DrawMap16_Persist

    %GetTilePos($11, $07)
    LDA.w #$068F
    JSL $1BC97C ; Overworld_DrawMap16_Persist


    %GetTilePos($0F, $08)
    LDA.w #$06A4
    JSL $1BC97C ; Overworld_DrawMap16_Persist

    %GetTilePos($10, $08)
    LDA.w #$06A4
    JSL $1BC97C ; Overworld_DrawMap16_Persist

    %GetTilePos($11, $08)
    LDA.w #$06A4
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30
    PLX
    LDA.b #$01
    STA.b $14
    ;-------------------------------------------------------------
    +
    RTS



  IdlePhase:
    LDA.w SprTimerC, X : CMP.b #$08 : BNE +
    JSL Sprite_SpawnFireball
    +


    LDA.w SprTimerC, X : BNE +
    INC.w SprAction, X
    +
    LDA.w SprTimerB, X : BNE +
    LDA.b #$01 : STA.w SprHeight, X
    LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #12 : BCC .noframereset
    LDA.b #10 : STA.w SprFrame, X
    STZ.w SprHeight, X
    .noframereset
    LDA.b #18 : STA.w SprTimerB, X
    +

    LDA.w SprMiscF, X : BNE + ; is it the red octopus? (blue doesn't need to run that)
    JSR ReturnTotalHealth ; return the health total of both sprite
    CMP.b #$30 : BCS .tooMuchHealth
    LDA.b #$09 : STA.w SprAction, X ; go to wait message action
    .tooMuchHealth
    +

    JSL Sprite_CheckDamageFromPlayer
    RTS

  PickDirection:
    JSL GetRandomInt : AND.b #$1F : SEC : SBC #$10 : STA.w SprXSpeed, X
    JSL GetRandomInt : AND.b #$1F : SEC : SBC #$10 : STA.w SprYSpeed, X
    INC.w SprAction, X

    JSL GetRandomInt : AND.b #$4F : CLC : ADC.b #$1F : STA.w SprTimerC, X


    RTS


  Moving:
    LDA.w SprTimerC, X : BNE +
    DEC.w SprAction, X
    DEC.w SprAction, X
    JSL GetRandomInt : AND.b #$4F : CLC : ADC.b #$1F : STA.w SprTimerC, X
    +


    JSL Sprite_Move
    LDA.w SprTimerB, X : BNE +
    LDA.b #$01 : STA.w SprHeight, X
    LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #12 : BCC .noframereset
    LDA.b #10 : STA.w SprFrame, X
    STZ.w SprHeight, X
    .noframereset
    LDA.b #10 : STA.w SprTimerB, X
    +


    LDA.w SprX, X : CMP.b #$E2 : BCC .notTooFarRight
    LDA.w SprXSpeed, X : BMI .notTooFarRight
    EOR.b #$FF : STA.w SprXSpeed, X 
    .notTooFarRight


    LDA.w SprX, X : CMP.b #$80 : BCS .notTooFarLeft
    LDA.w SprXSpeed, X : BPL .notTooFarLeft
    EOR.b #$FF : STA.w SprXSpeed, X 
    .notTooFarLeft



    LDA.w SprY, X : CMP.b #$FB : BCC .notTooFarDown
    LDA.w SprYSpeed, X : BMI .notTooFarDown
    EOR.b #$FF : STA.w SprYSpeed, X 
    .notTooFarDown


    LDA.w SprY, X : CMP.b #$B8 : BCS .notTooFarUp
    LDA.w SprYSpeed, X : BPL .notTooFarUp
    EOR.b #$FF : STA.w SprYSpeed, X 
    .notTooFarUp

    JSR HandleMovingSplash

    JSL Sprite_CheckDamageFromPlayer

    JSR ReturnTotalHealth ; return the health total of both sprite
    CMP.b #$30 : BCS .tooMuchHealth
    LDA.b #$09 : STA.w SprAction, X ; go to wait message action
    .tooMuchHealth
    RTS


  Moving2:
    LDA.w SprTimerC, X : BNE +
    DEC.w SprAction, X
    DEC.w SprAction, X
    JSL GetRandomInt : AND.b #$4F : CLC : ADC.b #$1F : STA.w SprTimerC, X
    +


    JSL Sprite_Move
    LDA.w SprTimerB, X : BNE +
    LDA.b #$01 : STA.w SprHeight, X
    LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #12 : BCC .noframereset
    LDA.b #10 : STA.w SprFrame, X
    STZ.w SprHeight, X
    .noframereset
    LDA.b #10 : STA.w SprTimerB, X
    +


    LDA.w SprX, X : CMP.b #$78 : BCC .notTooFarRight
    LDA.w SprXSpeed, X : BMI .notTooFarRight
    EOR.b #$FF : STA.w SprXSpeed, X 
    .notTooFarRight


    LDA.w SprX, X : CMP.b #$10 : BCS .notTooFarLeft
    LDA.w SprXSpeed, X : BPL .notTooFarLeft
    EOR.b #$FF : STA.w SprXSpeed, X 
    .notTooFarLeft



    LDA.w SprY, X : CMP.b #$FB : BCC .notTooFarDown
    LDA.w SprYSpeed, X : BMI .notTooFarDown
    EOR.b #$FF : STA.w SprYSpeed, X 
    .notTooFarDown


    LDA.w SprY, X : CMP.b #$B8 : BCS .notTooFarUp
    LDA.w SprYSpeed, X : BPL .notTooFarUp
    EOR.b #$FF : STA.w SprYSpeed, X 
    .notTooFarUp

    JSR HandleMovingSplash

    JSL Sprite_CheckDamageFromPlayer

    RTS


  WaitMessageBeforeSurrender:
    ; display message 4A ; Wait! WAIT! please!
    LDY.w BrotherSpr, X
    LDA.b #$06 : STA.w SprAction, Y ; set brother to action 6
    LDA.b #$50 : STA.w SprTimerC, X ; set timer to remove hat, surrender
    LDA.b #$4A
    LDY.b #$00
    JSL Sprite_ShowMessageUnconditional
    INC.w SprAction, X ; go to remove hat routine

    RTS

    RemoveHat:
    INC.w $02E4
    STZ.b $5D ; kill link action
    ; Use timer to remove hat like when it's spawning
    LDA.w SprTimerC, X : CMP #$34 : BNE +
    PHX
    JSR SpawnBossPoof
    PLX

    PHX
    LDA.w BrotherSpr, X : TAX
    JSR SpawnBossPoof
    PLX
    +

    LDY.w BrotherSpr, X
    LDA.w SprTimerC, X : CMP #$3A : BNE +
    LDA.b #9 : STA.w SprFrame, X
    LDA.b #9 : STA.w SprFrame, Y
    +

    LDA.w SprTimerC, X : BNE +
    LDA.b #$4B
    LDY.b #$00
    JSL Sprite_ShowMessageUnconditional
    INC.w SprAction, X ; surrender message
    +
    RTS


  Submerge:
    ; display message 4B ; Surrender message
    LDA.w SprTimerB, X : BNE +
    LDA.w SprFrame, X : DEC : STA.w SprFrame, X : CMP.b #01 : BCS .noframereset
    JSR SpawnSplash
    INC.w SprAction, X ; surrender message
    LDA.b #15 : STA.w SprFrame, X
    LDA.b #$B0 : STA.w SprX, X
    LDA.b #$08 : STA.w SprXH, X : STA.w SprYH, X
    LDA.b #$D4 : STA.w SprY, X
    LDA.b #$90 : STA.w SprTimerC, X
    .noframereset
    LDA.b #2 : STA.w SprTimerB, X
    +

    RTS

  SubmergeWaitWall:
    ; go under water to get the item - move back to original position

    LDA.w SprTimerC, X : BNE +
    STZ.w SprFrame, X
    INC.w SprAction, X
    LDA.b #$40 : STA.w SprTimerC, X
    +

    LDA.w SprTimerC, X : CMP.b #$40 : BNE +
    ;-------------------------------------------------------------
    PHX
    REP #$30
    %GetTilePos($0F, $07)
    LDA.w #$0034
    JSL $1BC97C ; Overworld_DrawMap16_Persist

    %GetTilePos($10, $07)
    LDA.w #$0034
    JSL $1BC97C ; Overworld_DrawMap16_Persist

    %GetTilePos($11, $07)
    LDA.w #$0034
    JSL $1BC97C ; Overworld_DrawMap16_Persist


    %GetTilePos($0F, $08)
    LDA.w #$0034
    JSL $1BC97C ; Overworld_DrawMap16_Persist

    %GetTilePos($10, $08)
    LDA.w #$0034
    JSL $1BC97C ; Overworld_DrawMap16_Persist

    %GetTilePos($11, $08)
    LDA.w #$0034
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30
    PLX
    LDA.b #$01
    STA.b $14
    ;-------------------------------------------------------------
    +
    RTS

  EmergeWaitGiveItem:
    ; Emerge back wait few frames, throw item in the middle moat, despawn wall

    LDA.w SprTimerB, X : BNE +
    LDA.w SprFrame, X : INC : STA.w SprFrame, X : CMP.b #9 : BCC .noframereset
    LDA.b #$09 : STA.w SprFrame, X
    .noframereset
    LDA.b #2 : STA.w SprTimerB, X
    +



    LDA.w SprTimerC, X : BNE .noItemYet
    INC.w SprAction, X

    JSR SpawnMedallion

    LDY.w BrotherSpr, X
    LDA.b #$07 : STA.w SprAction, Y
    ; Throw item here

    PHX
    LDX.b $8A
    LDA.l $7EF280, X : ORA.b #$40 : STA.l $7EF280, X ; save in HP sram
    PLX

    .noItemYet

    RTS

  SubmergeForeverKill:
    ; Set overworld sram flag for object collected on that screen
    STZ.w $02E4 ; allow link to move

    LDA.w SprTimerB, X : BNE +
    LDA.w SprFrame, X : DEC : STA.w SprFrame, X : CMP.b #01 : BCS .noframereset
    JSR SpawnSplash
    STZ.w $0DD0, X
    .noframereset
    LDA.b #2 : STA.w SprTimerB, X
    +
    RTS



  IdleWait:
    RTS




  ReturnTotalHealth:
    LDY.w BrotherSpr, X
    LDA.w SprHealth, Y : STA.b $00

    LDA.w SprHealth, X : CLC : ADC.b $00
    RTS 
}




; =========================================================
; Sprite Draw code
; Draw the tiles on screen with the data provided by the sprite maker editor
; =========================================================
Sprite_Octoboss_Draw:
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
  LDA.b $05 : ORA.w .properties, X : STA ($90), Y

  PHY 
      
  TYA : LSR #2 : TAY
      
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
      
  PLY : INY
      
  PLX : DEX : BPL .nextTile

  PLX

  RTS


  ; =========================================================
  ; Sprite Draw Generated Data
  ; This is where the generated Data for the sprite go
  ; =========================================================
  .start_index
  db $00, $04, $0A, $10, $16, $1C, $20, $24, $28, $2C, $30, $34, $38, $3C, $40, $44
  .nbr_of_tiles
  db 3, 5, 5, 5, 5, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 0
  .x_offsets
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8, -8, 8
  dw -8, 8, -8, 8, -8, 8
  dw -8, 8, -8, 8, -8, 8
  dw -8, 8, -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8
  dw 0
  .y_offsets
  dw 6, 6, 16, 16
  dw 16, 16, 0, 0, 16, 16
  dw 12, 12, -4, -4, 16, 16
  dw 8, 8, -8, -8, 16, 16
  dw 4, 4, -12, -12, 16, 16
  dw 0, 0, -16, -16
  dw -2, -2, -18, -18
  dw 0, 0, -16, -16
  dw -16, -16, 0, 0
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0
  .chr
  db $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04
  db $2C, $2E, $02, $04
  db $2C, $2E, $02, $04
  db $02, $04, $24, $26
  db $20, $22, $02, $08
  db $20, $22, $00, $00
  db $28, $2A, $00, $00
  db $2C, $2E, $00, $00
  db $2C, $2E, $00, $00
  db $24, $26, $00, $00
  db $0E
  .properties
  db $37, $37, $37, $37
  db $37, $37, $37, $37, $37, $37
  db $37, $37, $37, $37, $37, $37
  db $37, $37, $37, $37, $37, $37
  db $37, $37, $37, $37, $37, $37
  db $37, $37, $37, $37
  db $37, $37, $37, $37
  db $37, $37, $37, $37
  db $37, $37, $37, $37
  db $37, $37, $37, $37
  db $37, $37, $37, $77
  db $37, $37, $37, $77
  db $37, $37, $37, $77
  db $37, $37, $37, $77
  db $37, $37, $37, $77
  db $37
  .sizes
  db $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02

}

; =========================================================
; Sprite Draw code
; Draw the tiles on screen with the data provided by the sprite maker editor
; =========================================================
Sprite_Octoboss_Draw2:
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
  LDA.b $05 : ORA.w .properties, X : STA ($90), Y

  PHY 
      
  TYA : LSR #2 : TAY
      
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
      
  PLY : INY
      
  PLX : DEX : BPL .nextTile

  PLX

  RTS



  ; =========================================================
  ; Sprite Draw Generated Data
  
  ; This is where the generated Data for the sprite go
  ; =========================================================
  .start_index
  db $00, $04, $0A, $10, $16, $1C, $20, $24, $28, $2C, $30, $34, $38, $3C, $40, $44
  .nbr_of_tiles
  db 3, 5, 5, 5, 5, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 0
  .x_offsets
  dw -8, 8, -8, 8
  dw -8, 8, -8, 8, -8, 8
  dw 8, -8, -8, 8, -8, 8
  dw 8, -8, -8, 8, -8, 8
  dw 8, -8, -8, 8, -8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw -8, 8, 8, -8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw 8, -8, -8, 8
  dw 0
  .y_offsets
  dw 6, 6, 16, 16
  dw 16, 16, 0, 0, 16, 16
  dw 12, 12, -4, -4, 16, 16
  dw 8, 8, -8, -8, 16, 16
  dw 4, 4, -12, -12, 16, 16
  dw 0, 0, -16, -16
  dw -2, -2, -18, -18
  dw 0, 0, -16, -16
  dw -16, -16, 0, 0
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw 0
  .chr
  db $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04, $0E, $0E
  db $2C, $2E, $02, $04
  db $2C, $2E, $02, $04
  db $2C, $2E, $02, $04
  db $02, $04, $24, $26
  db $20, $22, $02, $08
  db $20, $22, $00, $00
  db $28, $2A, $00, $00
  db $2C, $2E, $00, $00
  db $2C, $2E, $00, $00
  db $24, $26, $00, $00
  db $0E
  .properties
  db $39, $39, $39, $39
  db $39, $39, $39, $39, $39, $39
  db $79, $79, $39, $39, $39, $39
  db $79, $79, $39, $39, $39, $39
  db $79, $79, $39, $39, $39, $39
  db $79, $79, $39, $39
  db $79, $79, $39, $39
  db $79, $79, $39, $39
  db $39, $39, $79, $79
  db $79, $79, $39, $39
  db $79, $79, $39, $79
  db $79, $79, $39, $79
  db $79, $79, $39, $79
  db $79, $79, $39, $79
  db $79, $79, $39, $79
  db $39
  .sizes
  db $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02
}

SpawnSplash:
  LDA.b #$EC ; SPRITE EC
  JSL Sprite_SpawnDynamically
  BMI .exit

  JSL Sprite_SetSpawnedCoords

  LDA.b #$03
  STA.w $0DD0,Y

  LDA.b #$0F
  STA.w $0DF0,Y

  LDA.b #$00
  STA.w $0D80,Y

  LDA.b #$03
  STA.w $0E40,Y

  LDA.b #$28 ; SFX2.28
  JSL Sound_SetSfx2PanLong

  .exit

  RTS



SpawnBossPoof:
  LDA.b #$0C ; SFX2.0C
  STA.w $012E

  LDA.b #$CE ; SPRITE CE
  JSL Sprite_SpawnDynamically

  LDA.b $00
  CLC
  ADC.b #$10
  STA.w SprX,Y

  LDA.b $01
  ADC.b #$00
  STA.w SprXH,Y

  LDA.b $02
  CLC
  ADC.b #$08
  STA.w SprY,Y

  LDA.b $03
  ADC.b #$00
  STA.w SprYH,Y

  LDA.b #$0F
  STA.w $0DC0,Y

  LDA.b #$01
  STA.w $0D90,Y

  LDA.b #$2F
  STA.w $0DF0,Y

  LDA.b #$09
  STA.w $0E40,Y
  STA.w $0BA0,Y

  RTS




HandleMovingSplash:
  LDA.b $1A
  AND.b #$0F
  BNE .exit

  LDA.b #$28 ; SFX2.28
  JSL Sound_SetSfx2PanLong

  PHX

  TXY
  LDX.b #$1D

  LDA.w $0D40,Y
  BMI .next_slot

  LDX.b #$0E

  .next_slot
  LDA.l $7FF800,X
  BNE .slot_occupied

  LDA.b #$15 ; GARNISH 15
  STA.l $7FF800,X
  STA.w $0FB4

  LDA.w SprX,Y
  STA.l $7FF83C,X

  LDA.w SprXH,Y
  STA.l $7FF878,X

  LDA.w SprY,Y
  CLC
  ADC.b #$18
  STA.l $7FF81E,X

  LDA.w SprYH,Y
  STA.l $7FF85A,X

  LDA.b #$0F
  STA.l $7FF90E,X

  PLX

  RTS

  ; ---------------------------------------------------------

  .slot_occupied
  DEX
  BPL .next_slot

  PLX

  .exit
  RTS


SpawnMedallion:
  LDA.b #$C0 ; SPRITE C0
  JSL Sprite_SpawnDynamically
  BMI .exit

  JSL $09AE64 ; Sprite_SetSpawnedCoordinates

  PHX
  TYX

  LDA.b #$10
  STA.w $0D50, X

  LDA.b #$30
  STA.w $0F80, X

  LDA.b #$11 ; ITEMGET 11
  STA.w $0D90, X

  LDA.b #$20 ; SFX2.20
  JSL $0DBB7C ; SpriteSFX_QueueSFX2WithPan

  LDA.b #$83
  STA.w $0E40,X

  LDA.b #$58
  STA.w $0E60,X

  AND.b #$0F
  STA.w $0F50,X

  PLX

  PHX
  PHY

  LDA.b #$1C
  JSL $00D4ED ; WriteTo4BPPBuffer_item_gfx

  PLY
  PLX

  .exit
  RTS


SpawnMedallionAlt:
  LDA.b #$C0 ; SPRITE C0
  JSL Sprite_SpawnDynamically
  BMI .exit

  PHX
  TYX

  LDA.b #$11 ; ITEMGET 11
  STA.w $0D90, X

  LDA.b #$83
  STA.w $0E40,X

  LDA.b #$58
  STA.w $0E60,X

  AND.b #$0F
  STA.w $0F50,X

  LDA.b #$DC : STA.w SprY, X
  LDA.b #$F7 : STA.w SprX, X
  LDA.b #$08 : STA.w SprYH, X : STA.w SprXH, X
  PLX

  PHX
  PHY

  LDA.b #$1C
  JSL $00D4ED ; WriteTo4BPPBuffer_item_gfx

  PLY
  PLX

  .exit
  RTS
