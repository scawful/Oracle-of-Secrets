; =========================================================
; Normal Overlays:
; Overworld_DrawQuadrantsAndOverlays
; -> ApplyOverworldOverlay

; Animated Entrances:
; Module09_00_PlayerControl
; -> Overworld_AnimateEntrance

; Overworld entrance cutscene to play
; OWENTSC         = $7E04C6

; Trigger Zora Temple from Tablet 

org $1EE061
  CMP.b #$1E ; Zora Temple Map 

; InitiateDesertCutscene
org $07866D
#_07866D: REP #$20

#_07866F: LDA.w #$0001
#_078672: STA.b $3C

#_078674: SEP #$20

#_078676: LDA.b #$1B ; LINKSTATE 1B
#_078678: STA.b $5D

#_07867A: RTL


; =========================================================

; ; before the intro keep value of $061E (not even sure if it's needed to move that)
; REP #$20
; LDA.w $061E : STA.w $0632 ; keep value of 061E
; SEP #$20


; ; move the camera to the right until position is 0980
; REP #$20
; INC.w $061C
; INC.w $061E
; INC.b $E2 ; that's the camera

; LDA.w $061E : CMP.w #$0980 : BNE +
; SEP #$20
; INC.b $B0
; +

; SEP #$20
; RTS


; ; move camera back until it's back to $0632 (position we were at)
; REP #$20
; DEC.w $061C
; DEC.w $061E
; DEC.b $E2

; LDA.w $061E : CMP.w $0632 : BNE +
; SEP #$20

; ================================================

;Desert Book activation trigger
org $07A484 ; LDA $02ED : BNE BRANCH_BETA
NOP #01
JML NewDesertCheck
returnPos:


org $348000

NewDesertCheck:
; LDA.b #$02 : STA.w $037A ; set link in praying mode
  ; LDA #$FF : STA $8C
  ; LDA #$00 : STA $7EE00E
  ; STZ $1D
  ; STZ $9A
  ; STZ.w $012D

LDA.b #$01 : STA.w $04C6 ; set entrance animation
STZ.b $B0
STZ.b $C8

+
JML $07A493 ; returnPos ; do not !

pushpc

;===============================================
; Entrance Animation
;===============================================
; don't forget to set $C8 to zero (STZ.b $C8)
; don't forget to set $B0 to zero (STZ.b $B0)

; Rename this into something unique
org $1BCADE
JSL EntranceAnimation
RTS 

pullpc
;===============================================
; Entrance Animation
;===============================================
; don't forget to set $C8 to zero (STZ.b $C8)
; don't forget to set $B0 to zero (STZ.b $B0)

; Rename this into something unique
EntranceAnimation:
{
  REP #$20
  LDA $0618 : CMP.w #$0630 : BCC +
    DEC.b $E8 ; Increment camera vertical
    DEC.w $0618 : DEC.w $0618 
    DEC.w $061A : DEC.w $061A
  +
  SEP #$20


  LDA.b $B0 ; Get animation state
  ASL A
  TAX ; x2

  JSR.w (.AnimationFrames, X)

  RTL
}

.AnimationFrames
dw Frame0
dw Frame1
dw Frame2
dw Frame3
dw Frame4
dw Frame5
dw Frame6
dw Frame7

;===================================================
; Shake screen
;===================================================
; if you already have that function delete this one
ShakeScreen:
REP #$20
LDA.b $1A
AND.w #$0001
ASL A
TAX

LDA.l $01C961, X
STA.w $011A

LDA.l $01C965, X
STA.w $011C

.exit
SEP #$20
RTS

Frame0:
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
Frame1:
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
Frame2:
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
Frame3:
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
Frame4:
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
Frame5:
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
Frame6:
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
Frame7:
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
.wait

RTS
