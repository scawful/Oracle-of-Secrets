; =========================================================
; Normal Overlays:
; Overworld_DrawQuadrantsAndOverlays
; -> ApplyOverworldOverlay

; Animated Entrances:
; Module09_00_PlayerControl
; -> Overworld_AnimateEntrance
; =========================================================

; Trigger Zora Temple from Tablet
org $1EE061
  CMP.b #$1E ; Zora Temple Map

; InitiateDesertCutscene
org $07866D
  REP #$20
  LDA.w #$0001 : STA.b $3C
  SEP #$20
  LDA.b #$1B : STA.b $5D
  RTL

; =========================================================
; Overlays $04C6
; 01 - Zora Temple (OW 1E)
; 02 - Castle Bridge (OW 1B)
; 03 - Tail Palace (OW 2F)
; 04 - Goron Mines Entrance (OW 36)
; 05 - TODO: Fortress of Secrets (OW 5E)

CameraCache = $0632

; LinkItem_Book
; Desert Book activation trigger
org $07A484 ; LDA $02ED : BNE BRANCH_BETA
NOP #01
JML NewDesertCheck
returnPos:

pullpc
NewDesertCheck:
{
  ; set link in praying mode
  ; LDA.b #$02 : STA.w $037A
  ; LDA #$FF : STA $8C
  ; LDA #$00 : STA $7EE00E
  ; STZ $1D : STZ $9A
  ; STZ.w $012D

  ; Are we on the castle map?
  LDA $8A : CMP.b #$1B : BNE +
    ; Is there an overlay playing?
    LDA $04C6 : BNE +
      ; If not, start the castle entrance animation
      LDA.b #$02 : STA.w $04C6 ; Set the overlay
      STZ.b $B0 : STZ.b $C8
      ; Cache the camera
      REP #$20
      LDA.w $0618 : STA.w CameraCache
      SEP #$20
  +
  JML $07A493 ; return do not !
}

pushpc

org $1BCADE
JSL ZoraTemple_EntranceAnimation
RTS

org $1BCBA6
JSL Castle_EntranceAnimation
RTS

org $1BCCD4
JSL TailPalace_EntranceAnimation
RTS

org $1BCE28
JSL Goron_EntranceAnimation
RTS

org $1BCFD9
JSL Fortress_EntranceAnimation
RTS

pullpc

; Zarby Notes
; don't forget to set $C8 to zero (STZ.b $C8)
; don't forget to set $B0 to zero (STZ.b $B0)

ShakeScreen:
{
  REP #$20
  LDA.b $1A : AND.w #$0001 : ASL A : TAX
  LDA.l $01C961, X : STA.w $011A
  LDA.l $01C965, X : STA.w $011C
  SEP #$20
  RTS
}

; =========================================================
; Zora Temple Hidden Waterfall

ZoraTemple_EntranceAnimation:
{
  ; If $B0 is 8, then we move the camera back to the origin
  LDA.b $B0 : CMP.b #$08 : BCS .lastframe
  REP #$20
  LDA $0618 : CMP.w #$0630 : BCC +
    DEC.b $E8 ; Increment camera vertical
    DEC.w $0618 : DEC.w $0618
    DEC.w $061A : DEC.w $061A
  +
  SEP #$20
  JMP .do_anim
  .lastframe
  REP #$20
  LDA #$06F3 : STA.w $0618
  LDA #$06F1 : STA.w $061A
  LDA.w #$0692 : STA.b $E8
  SEP #$20

  .do_anim
  ; Get animation state
  LDA.b $B0 : ASL A : TAX ; x2
  JSR.w (.AnimationFrames, X)

  RTL

  .AnimationFrames
  dw Frame0
  dw Frame1
  dw Frame2
  dw Frame3
  dw Frame4
  dw Frame5
  dw Frame6
  dw Frame7
  dw Frame8

  Frame0:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$0965
    LDX.w #$0490
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0175
    LDX.w #$0492
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0965
    LDX.w #$049C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0175
    LDX.w #$049E
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02D5
    LDX.w #$0510
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0730
    LDX.w #$0512
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02D5
    LDX.w #$051C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0730
    LDX.w #$051E
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00CE
    LDX.w #$0410
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00D5
    LDX.w #$0412
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00CE
    LDX.w #$041C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00D5
    LDX.w #$041E
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    .wait
    RTS
  }

  Frame1:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$0965
    LDX.w #$0510
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0183
    LDX.w #$0512
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02D5
    LDX.w #$0590
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0730
    LDX.w #$0592
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0965
    LDX.w #$051C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0183
    LDX.w #$051E
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02D5
    LDX.w #$059C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0730
    LDX.w #$059E
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00CE
    LDX.w #$0490
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00D5
    LDX.w #$0492
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00CE
    LDX.w #$049C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00D5
    LDX.w #$049E
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    JSR ShakeScreen ; make the screen shake
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    .wait
    RTS
  }

  Frame2:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$00CE
    LDX.w #$0510
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00D5
    LDX.w #$0512
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00CE
    LDX.w #$051C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00D5
    LDX.w #$051E
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0965
    LDX.w #$0590
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0183
    LDX.w #$0592
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02D5
    LDX.w #$0610
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0730
    LDX.w #$0612
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0965
    LDX.w #$059C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0183
    LDX.w #$059E
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02D5
    LDX.w #$061C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0730
    LDX.w #$061E
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    .wait
    RTS
  }

  Frame3:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$0530
    LDX.w #$0616
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02E4
    LDX.w #$0618
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$05A1
    LDX.w #$0594
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$05A1
    LDX.w #$059A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0530
    LDX.w #$0596
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02E4
    LDX.w #$0598
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0599
    LDX.w #$0614
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0599
    LDX.w #$061A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0094
    LDX.w #$0494
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0094
    LDX.w #$049A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$05A1
    LDX.w #$0514
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$05A1
    LDX.w #$051A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0530
    LDX.w #$0516
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02E4
    LDX.w #$0518
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    .wait
    RTS
  }

  Frame4:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$056D
    LDX.w #$0396
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$056D
    LDX.w #$0398
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$056D
    LDX.w #$0416
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$056D
    LDX.w #$0418
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$056D
    LDX.w #$0496
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$056D
    LDX.w #$0498
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$056D
    LDX.w #$0414
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$056D
    LDX.w #$041A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$06AF
    LDX.w #$0394
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$06AF
    LDX.w #$039A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    JSR ShakeScreen ; make the screen shake
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    .wait
    RTS
  }

  Frame5:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$02C0
    LDX.w #$0292
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02BD
    LDX.w #$029C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00D5
    LDX.w #$031C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00CE
    LDX.w #$0392
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00D5
    LDX.w #$039C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00CE
    LDX.w #$0412
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00D5
    LDX.w #$041C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0965
    LDX.w #$0492
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0175
    LDX.w #$049C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00C7
    LDX.w #$0512
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00C8
    LDX.w #$051C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$057D
    LDX.w #$0592
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$057D
    LDX.w #$059C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0156
    LDX.w #$0612
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0156
    LDX.w #$061C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00CE
    LDX.w #$0312
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    LDA.b #$07 :  STA.w $012D
    .notfirstframe
    JSR ShakeScreen ; make the screen shake
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    .wait
    RTS
  }

  Frame6:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$02BF
    LDX.w #$0192
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0312
    LDX.w #$019C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02B9
    LDX.w #$0212
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02B6
    LDX.w #$021C
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$06B0
    LDX.w #$0214
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$06B1
    LDX.w #$0216
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$06B2
    LDX.w #$0218
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$06B3
    LDX.w #$021A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$06B5
    LDX.w #$0294
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00DF
    LDX.w #$0296
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00E0
    LDX.w #$0298
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$06B6
    LDX.w #$029A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$02D5
    LDX.w #$0314
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0223
    LDX.w #$0316
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0205
    LDX.w #$0318
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0730
    LDX.w #$031A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    JSR ShakeScreen ; make the screen shake
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    .wait
    RTS
  }

  Frame7:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$00C7
    LDX.w #$0014
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0158
    LDX.w #$0016
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0158
    LDX.w #$0018
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00C8
    LDX.w #$001A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00C7
    LDX.w #$0094
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0158
    LDX.w #$0096
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0158
    LDX.w #$0098
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00C8
    LDX.w #$009A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00C7
    LDX.w #$0114
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0158
    LDX.w #$0116
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0158
    LDX.w #$0118
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00C8
    LDX.w #$011A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00C7
    LDX.w #$0194
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0158
    LDX.w #$0196
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0158
    LDX.w #$0198
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$00C8
    LDX.w #$019A
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    LDA.b #$0D :  STA.w $012D
    .notfirstframe
    JSR ShakeScreen ; make the screen shake
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    .wait
    RTS
  }

  Frame8:
  {
    JSR ShakeScreen ; make the screen shake
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    STZ.w $04C6
    STZ.b $B0
    STZ.w $0710
    STZ.w $02E4
    STZ.w SprFreeze
    STZ.w $011A
    STZ.w $011B
    STZ.w $011C
    STZ.w $011D
    ; set the overlay
    LDX.b $8A
    LDA.l $7EF280,X
    ORA.b #$20
    STA.l $7EF280,X
    .wait
    RTS
  }

}

; =========================================================
; Castle Drawbridge

Castle_EntranceAnimation:
{
  LDA.b $B0 : CMP.b #$04 : BEQ .last_frame
    REP #$20
    LDA $0618 : CMP.w #$0630 : BCC +
      DEC.b $E8 ; Increment camera vertical
      DEC.w $0618 : DEC.w $0618
      DEC.w $061A : DEC.w $061A
    +
    SEP #$20
  .last_frame
  ; Get animation state
  LDA.b $B0 : ASL A : TAX ; x2
  JSR.w (.AnimationFrames, X)
  RTL

  .AnimationFrames
  dw Castle_Frame0
  dw Castle_Frame3
  dw Castle_Frame1
  dw Castle_Frame2
  dw Castle_RestoreCamera
}

Castle_EndAnimation:
{
  INC.b $B0 ; increase frame
  STZ.b $C8 ; reset timer for next frame
  STZ.w $04C6
  STZ.b $B0
  STZ.w $0710
  STZ.w $02E4
  STZ.w SprFreeze
  STZ.w $011A
  STZ.w $011B
  STZ.w $011C
  STZ.w $011D
  LDA.b #$1B ; SFX3.1B
  STA.w $012F
  ; set the overlay
  LDX.b $8A
  LDA.l $7EF280,X
  ORA.b #$20
  STA.l $7EF280,X
  RTS
}

Castle_RestoreCamera:
{
  REP #$20

  INC.w $061A : INC.w $061A
  INC.w $0618 : INC.w $0618
  INC.b $E8

  LDA.w $0618 : CMP.w CameraCache : BNE +
    SEP #$20
    JSR Castle_EndAnimation
    RTS
  +
  SEP #$20
  RTS
}

Castle_Frame0:
{
  #_1BD017: LDA.b #$02 ; SFX3.07
  #_1BD019: STA.w $012F
  LDA.b $C8 : BEQ .doInit ; Load the timer
  JMP .notfirstframe
  .doInit
  ; Init code for the frame here
  REP #$30 ; 16 bit mode
  LDA.w #$0611
  LDX.w #$031C
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0613
  LDX.w #$031E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0613
  LDX.w #$0320
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0612
  LDX.w #$0322
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0614
  LDX.w #$039C
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0613
  LDX.w #$039E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0613
  LDX.w #$03A0
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0615
  LDX.w #$03A2
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0480
  LDX.w #$029C
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0479
  LDX.w #$029E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0479
  LDX.w #$02A0
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0481
  LDX.w #$02A2
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  SEP #$30 ; 8 bit mode
  INC.b $14 ; Do tiles transfer
  .notfirstframe
  JSR ShakeScreen ; make the screen shake
  INC.b $C8 : LDA.b $C8 : CMP.b #$2E ; Load and compare timer
  BNE .wait
  INC.b $B0 ; increase frame
  STZ.b $C8 ; reset timer for next frame
  .wait
  RTS
}

Castle_Frame1:
{
  LDA.b #$16 ; SFX3.16
  STA.w $012F
  LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
  .doInit
  ; Init code for the frame here
  REP #$30 ; 16 bit mode
  LDA.w #$049E
  LDX.w #$039C
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$049C
  LDX.w #$039E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0604
  LDX.w #$03A0
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0608
  LDX.w #$03A2
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$060A
  LDX.w #$041C
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0495
  LDX.w #$041E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0496
  LDX.w #$0420
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0499
  LDX.w #$0422
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0602
  LDX.w #$049C
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0606
  LDX.w #$049E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0606
  LDX.w #$04A0
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$060E
  LDX.w #$04A2
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0610
  LDX.w #$051C
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0606
  LDX.w #$051E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0606
  LDX.w #$0520
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$046C
  LDX.w #$0522
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$046F
  LDX.w #$059C
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0469
  LDX.w #$059E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$046A
  LDX.w #$05A0
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$046E
  LDX.w #$05A2
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  SEP #$30 ; 8 bit mode
  INC.b $14 ; Do tiles transfer
  .notfirstframe
  JSR ShakeScreen ; make the screen shake
  INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
  BNE .wait
  INC.b $B0 ; increase frame
  STZ.b $C8 ; reset timer for next frame
  .wait
  RTS
}

Castle_Frame2:
{
  LDA.b $C8 : BEQ .doInit ; Load the timer
  JMP .notfirstframe
  .doInit
  ; Init code for the frame here
  REP #$30 ; 16 bit mode
  LDA.w #$0108
  LDX.w #$061C
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$010A
  LDX.w #$0622
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$04E2
  LDX.w #$0620
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$04E2
  LDX.w #$061E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  SEP #$30 ; 8 bit mode
  INC.b $14 ; Do tiles transfer
  .notfirstframe
  JSR ShakeScreen ; make the screen shake
  INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
  BNE .wait
  INC.b $B0 ; increase frame
  STZ.b $C8 ; reset timer for next frame
  .wait
  RTS
}

Castle_Frame3:
{
  LDA.b $C8 : BEQ .doInit ; Load the timer
  JMP .notfirstframe
  .doInit
  ; Init code for the frame here
  REP #$30 ; 16 bit mode
  LDA.w #$0611
  LDX.w #$039C
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0612
  LDX.w #$03A2
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0613
  LDX.w #$039E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0613
  LDX.w #$03A0
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$048F
  LDX.w #$031C
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0474
  LDX.w #$031E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$061C
  LDX.w #$0320
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$061A
  LDX.w #$0322
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  SEP #$30 ; 8 bit mode
  INC.b $14 ; Do tiles transfer
  .notfirstframe
  JSR ShakeScreen ; make the screen shake
  INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
  BNE .wait
  INC.b $B0 ; increase frame
  STZ.b $C8 ; reset timer for next frame
  .wait
  RTS
}

; =========================================================

TailPalace_EntranceAnimation:
{
  LDA.b $B0 : ASL A : TAX ; x2
  JSR.w (.AnimationFrames, X)
  RTL

  .AnimationFrames
    dw TailPalace_Frame0
    dw TailPalace_Frame1
    dw TailPalace_Frame2

  TailPalace_Frame0:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$0A8C
    LDX.w #$02A2
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    .wait
    RTS
  }

  TailPalace_Frame1:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$0AF3
    LDX.w #$0328
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    .wait
    RTS
  }

  TailPalace_Frame2:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$0AF1
    LDX.w #$0328
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0AF3
    LDX.w #$03A8
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    JSR ShakeScreen ; make the screen shake
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    STZ.w $04C6
    STZ.b $B0
    STZ.w $0710
    STZ.w $02E4
    STZ.w SprFreeze
    STZ.w $011A
    STZ.w $011B
    STZ.w $011C
    STZ.w $011D
    ; set the overlay
    LDX.b $8A
    LDA.l $7EF280,X
    ORA.b #$20
    STA.l $7EF280,X
    .wait
    RTS
  }
}

Goron_EntranceAnimation:
{
  LDA.b $B0 : ASL A : TAX ; x2
  JSR.w (.AnimationFrames, X)
  RTL

  .AnimationFrames
  dw Goron_Frame0
  dw Goron_Frame1
  dw Goron_Frame2
  dw Goron_Frame3
  dw Goron_Frame4

  Goron_Frame0:
  LDA.b $C8 : BEQ .doInit ; Load the timer
  JMP .notfirstframe
  .doInit
  ; Init code for the frame here
  REP #$30 ; 16 bit mode
  LDA.w #$0789
  LDX.w #$10A2
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  SEP #$30 ; 8 bit mode
  INC.b $14 ; Do tiles transfer
  LDA.b #$16 :  STA.w $012F
  .notfirstframe
  JSR ShakeScreen ; make the screen shake
  INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
  BNE .wait
  INC.b $B0 ; increase frame
  STZ.b $C8 ; reset timer for next frame
  .wait
  RTS
  Goron_Frame1:
  LDA.b $C8 : BEQ .doInit ; Load the timer
  JMP .notfirstframe
  .doInit
  ; Init code for the frame here
  REP #$30 ; 16 bit mode
  LDA.w #$09C1
  LDX.w #$109C
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  SEP #$30 ; 8 bit mode
  INC.b $14 ; Do tiles transfer
  .notfirstframe
  JSR ShakeScreen ; make the screen shake
  INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
  BNE .wait
  INC.b $B0 ; increase frame
  STZ.b $C8 ; reset timer for next frame
  .wait
  RTS
  Goron_Frame2:
  LDA.b $C8 : BEQ .doInit ; Load the timer
  JMP .notfirstframe
  .doInit
  ; Init code for the frame here
  REP #$30 ; 16 bit mode
  LDA.w #$09C1
  LDX.w #$1024
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$078A
  LDX.w #$101E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  SEP #$30 ; 8 bit mode
  INC.b $14 ; Do tiles transfer
  LDA.b #$16 :  STA.w $012F
  .notfirstframe
  JSR ShakeScreen ; make the screen shake
  INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
  BNE .wait
  INC.b $B0 ; increase frame
  STZ.b $C8 ; reset timer for next frame
  .wait
  RTS
  Goron_Frame3:
  LDA.b $C8 : BEQ .doInit ; Load the timer
  JMP .notfirstframe
  .doInit
  ; Init code for the frame here
  REP #$30 ; 16 bit mode
  LDA.w #$0791
  LDX.w #$0FA2
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  LDA.w #$0797
  LDX.w #$0F9E
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  SEP #$30 ; 8 bit mode
  INC.b $14 ; Do tiles transfer
  .notfirstframe
  INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
  BNE .wait
  INC.b $B0 ; increase frame
  STZ.b $C8 ; reset timer for next frame
  .wait
  RTS
  Goron_Frame4:
  LDA.b $C8 : BEQ .doInit ; Load the timer
  JMP .notfirstframe
  .doInit
  ; Init code for the frame here
  REP #$30 ; 16 bit mode
  LDA.w #$0787
  LDX.w #$0FA0
  JSL $1BC97C ; Overworld_DrawMap16_Persist
  SEP #$30 ; 8 bit mode
  INC.b $14 ; Do tiles transfer
  LDA.b #$1B :  STA.w $012F
  .notfirstframe
  JSR ShakeScreen ; make the screen shake
  INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
  BNE .wait
  INC.b $B0 ; increase frame
  STZ.b $C8 ; reset timer for next frame
  STZ.w $04C6
  STZ.b $B0
  STZ.w $0710
  STZ.w $02E4
  STZ.w SprFreeze
  STZ.w $011A
  STZ.w $011B
  STZ.w $011C
  STZ.w $011D
  LDX.b $8A
  LDA.l $7EF280,X
  ORA.b #$20
  STA.l $7EF280,X
  .wait
  RTS
}



Fortress_EntranceAnimation:
{
  LDA.b $B0 : ASL A : TAX ; x2
  JSR.w (.AnimationFrames, X)
  RTL

  .AnimationFrames
  dw Fortress_Frame0
  dw Fortress_Frame1
  dw Fortress_Frame2
  dw Fortress_Frame3
  dw Fortress_Frame4

  Fortress_Frame0:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$0196
    LDX.w #$0754
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$0756
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$06D4
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$06D6
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A2
    LDX.w #$0752
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A2
    LDX.w #$06D2
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A3
    LDX.w #$0758
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A3
    LDX.w #$06D8
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    JSR ShakeScreen ; make the screen shake
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    LDA.b #$05 ; SFX1.05
    STA.w $012D

    LDA.b #$0C ; SFX2.0C
    STA.w $012E

    LDA.b #$07 ; SFX3.07
    STA.w $012F
    .wait
    RTS
  }
  Fortress_Frame1:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$09A3
    LDX.w #$0658
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A3
    LDX.w #$05D8
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A2
    LDX.w #$0652
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A2
    LDX.w #$05D2
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$0654
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$0656
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$05D6
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$05D4
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    JSR ShakeScreen ; make the screen shake
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    LDA.b #$05 ; SFX1.05
    STA.w $012D

    LDA.b #$0C ; SFX2.0C
    STA.w $012E

    LDA.b #$07 ; SFX3.07
    STA.w $012F
    .wait
    RTS
  }
  Fortress_Frame2:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$09A3
    LDX.w #$04D8
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A3
    LDX.w #$0558
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A2
    LDX.w #$04D2
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A2
    LDX.w #$0552
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$04D6
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$0556
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$04D4
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$0554
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    JSR ShakeScreen ; make the screen shake
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    LDA.b #$05 ; SFX1.05
    STA.w $012D

    LDA.b #$0C ; SFX2.0C
    STA.w $012E

    LDA.b #$07 ; SFX3.07
    STA.w $012F
    .wait
    RTS
  }
  Fortress_Frame3:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$0196
    LDX.w #$0454
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$0456
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$03D6
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$0196
    LDX.w #$03D4
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A2
    LDX.w #$03D2
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A2
    LDX.w #$0452
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A3
    LDX.w #$03D8
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$09A3
    LDX.w #$0458
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    LDA.b #$05 ; SFX1.05
    STA.w $012D

    LDA.b #$0C ; SFX2.0C
    STA.w $012E

    LDA.b #$07 ; SFX3.07
    STA.w $012F
    .wait
    RTS
  }
  Fortress_Frame4:
  {
    LDA.b $C8 : BEQ .doInit ; Load the timer
    JMP .notfirstframe
    .doInit
    ; Init code for the frame here
    REP #$30 ; 16 bit mode
    LDA.w #$099C
    LDX.w #$0354
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    LDA.w #$099C
    LDX.w #$0356
    JSL $1BC97C ; Overworld_DrawMap16_Persist
    SEP #$30 ; 8 bit mode
    INC.b $14 ; Do tiles transfer
    .notfirstframe
    INC.b $C8 : LDA.b $C8 : CMP.b #$1E ; Load and compare timer
    BNE .wait
    INC.b $B0 ; increase frame
    STZ.b $C8 ; reset timer for next frame
    STZ.w $04C6
    STZ.b $B0
    STZ.w $0710
    STZ.w $02E4
    STZ.w $0FC1
    STZ.w $011A
    STZ.w $011B
    STZ.w $011C
    STZ.w $011D
    ; set the overlay
    LDX.b $8A
    LDA.l $7EF280,X
    ORA.b #$20
    STA.l $7EF280,X
    ; OverworldEntrance_PlayJingle
    #_1BCF40: LDA.b #$1B ; SFX3.1B

    #_1BCF42: STA.w $012F

    #_1BCF45: STZ.w $04C6
    #_1BCF48: STZ.b $B0
    #_1BCF4A: STZ.w $0710

    #_1BCF4D: STZ.w $02E4

    #_1BCF50: STZ.w $0FC1

    #_1BCF53: STZ.w $011A
    #_1BCF56: STZ.w $011B
    #_1BCF59: STZ.w $011C
    #_1BCF5C: STZ.w $011D

    #_1BD1CD: LDA.b #$09
    #_1BD1CF: STA.w $012C

    #_1BD1D2: LDA.b #$09 ; SFX1.09
    #_1BD1D4: STA.w $012D
    .wait
    RTS
  }
}
