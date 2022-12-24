
org $07983A
  Player_ResetSwimState:

org $079873
  Player_ResetSwimCollision:

org $07E8F0
  HandleIndoorCameraAndDoors:

org $0ED6C0
  LoadActualGearPalettes:

org $07B64F 
  Link_HandleDiagonalCollision:

org $07E245 
  Link_HandleVelocity:

org $07B7C7
  Link_HandleCardinalCollision:

org $07E6A6
  Link_HandleMovingAnimation_FullLongEntry:

; *$3CEC9-$3CF09 LOCAL
Collision_Detection:
{
  REP #$20
  
  JSR TileDetect_ResetState
  
  STZ $59
  
  LDA $22 : ADD $CDA3, Y : AND $EC : LSR #3 : STA $02
  
  LDA $20 : ADD $CDAB, Y : AND $EC : STA $00
  
  LDA $20 : ADD $CDB3, Y : AND $EC : STA $04
  
  REP #$10
  
  LDA.w #$0001 : STA $0A
  
  JSR TileDetect_Execute
  
  LDA $04 : STA $00
  
  LDA.w #$0002 : STA $0A
  
  JSR TileDetect_Execute
  
  SEP #$30
  
  RTS
}

; *$3B9B3-$3B9F6 LOCAL
Collision_Uncategorized:
{
  LDA $046C : CMP.b #$01 : BEQ .BRANCH_ALPHA
  
  REP #$20
  
  LDA $20 : SUB $0318 : STA $00
  LDA $22 : SUB $031A : STA $02
  
  LDA $E8 : SUB $E6 : ADD $20 : STA $20
  LDA $E2 : SUB $E0 : ADD $22 : STA $22
  
  SEP #$20
  
  LDA $67 : BEQ .BRANCH_ALPHA
  
  LDA $30 : ADD $00 : STA $30
  LDA $31 : ADD $02 : STA $31

  .BRANCH_ALPHA:

  STZ $EE
  
  RTS
}


Collision_Settings:
{
  ; Collision settings
  LDA $046C  : BEQ .oneBg
  CMP.b #$04 : BEQ .oneBg       ; moving water collision setting
  CMP.b #$02 : BCC .twoBgs
  CMP.b #$03 : BNE .uselessBranch
  
  ; No code here, just us mice!

.uselessBranch

  REP #$20
  
  LDA $E6 : SUB $E8 : ADD $20 : STA $20 : STA $0318
  LDA $E0 : SUB $E2 : ADD $22 : STA $22 : STA $031A
  
  SEP #$20

.twoBgs

  LDA.b #$01 : STA $EE
  
  SEC
  
  RTS

.oneBg

  CLC
  
  RTS
}

Link_HandleDiagonalCollision:
{
  ; $3B97C IN ROM
  JSR Collision_Settings : BCC .onlyOneBg

  JSR .alt_entry ; $3B660 IN ROM
  JSR Collision_Uncategorized ; $3B9B3 IN ROM

.onlyOneBg

  LDA $67 : AND.b #$0F : STA $67

; *$3B660 ALTERNATE ENTRY POINT
.alt_entry

  LDA.b #$0F : STA $42 : STA $43

  STZ $6A

  ; Checking to see if either up or down was pressed.
  ; Yeah, one of them was.
  LDA $67 : AND.b #$0C : BNE .verticalWalking

  ; Neither up nor down was pressed.
  BRL .BRANCH_ULTIMA

.verticalWalking

  INC $6A

  LDY.b #$00

  ; Walking in the up direction?
  AND.b #$08 : BNE .walkingUp

  ; Walking in the down direction
  LDY.b #$02

.walkingUp

  ; $66 = #$0 or #$1. #$1 if the down button, #$0 if the up button was pushed.
  TYA : LSR A : STA $66

  JSR Collision_Uncategorized ; $3CE85 IN ROM

  LDA $0E : AND.b #$30 : BEQ .BRANCH_DELTA

  LDA $62 : AND.b #$02 : BNE .BRANCH_DELTA

  LDA $0E : AND.b #$30 : LSR #4 : AND $67 : BNE .BRANCH_DELTA

  LDY.b #$02

  LDA $67

  AND.b #$03 : BEQ .BRANCH_DELTA
  AND.b #$02 : BNE .BRANCH_EPSILON

  LDY.b #$03

  BRA .BRANCH_EPSILON

.BRANCH_DELTA:

  LDA $046C : BEQ .BRANCH_ZETA

  LDA $0E : AND.b #$03 : BNE .BRANCH_THETA

  BRA .BRANCH_IOTA

.BRANCH_ZETA:

  ; If Link is in the ground state, then branch.
  LDA $4D : BEQ .BRANCH_THETA

  LDA $0C : AND.b #$03 : BEQ .BRANCH_THETA

  BRA .BRANCH_MU

.BRANCH_THETA:

  LDA $0E : AND.b #$03 : BEQ .BRANCH_IOTA

  STZ $6B

  LDA $034A : BEQ .BRANCH_MU

  LDA $02E8 : AND.b #$03 : BNE .BRANCH_MU

  LDA $67 : AND.b #$03 : BEQ .BRANCH_MU

  STZ $033C
  STZ $033D
  STZ $032F
  STZ $0330
  STZ $032B
  STZ $032C
  STZ $0334
  STZ $0335

.BRANCH_MU:

  LDA.b #$01 : STA $0302

  LDY $66

.BRANCH_EPSILON:

  LDA $B64B, Y : STA $42

.BRANCH_IOTA:

  LDA $67 : AND.b #$03 : BNE .BRANCH_LAMBDA

  BRL .BRANCH_ULTIMA

.BRANCH_LAMBDA:

  INC $6A
  LDY.b #$04
  AND.b #$02 : BNE .BRANCH_NU
  LDY.b #$06

.BRANCH_NU:

  TYA : LSR A : STA $66
  JSR Collision_Detection ; $3CEC9 IN ROM

  LDA $0E : AND.b #$30 : BEQ .BRANCH_XI
  LDA $62 : AND.b #$02 : BEQ .BRANCH_XI
  LDA $0E : AND.b #$30 : LSR #2 : AND $67 : BNE .BRANCH_XI

  LDY.b #$00

  LDA $67

  AND.b #$0C : BEQ .BRANCH_XI
  AND.b #$08 : BNE .BRANCH_OMICRON

  LDY.b #$01

  BRA .BRANCH_OMICRON

.BRANCH_XI:

  ; One BG collision
  LDA $046C : BEQ .BRANCH_PI

  LDA $0E : AND.b #$03 : BNE .BRANCH_RHO

  BRA .BRANCH_SIGMA

.BRANCH_PI:

  LDA $4D : BEQ .BRANCH_RHO
  LDA $0C : AND.b #$03 : BEQ .BRANCH_RHO

  BRA .BRANCH_UPSILON

.BRANCH_RHO:

  LDA $0E : AND.b #$03 : BEQ .BRANCH_SIGMA
  STZ $6B

  LDA $034A : BEQ .BRANCH_UPSILON
  LDA $02E8 : AND.b #$03 : BNE .BRANCH_UPSILON

  ; Check if Link is walking in an vertical direction
  LDA $67 : AND.b #$0C : BEQ .BRANCH_UPSILON

  STZ $033E
  STZ $033F
  STZ $0331
  STZ $0332
  STZ $032D
  STZ $032E
  STZ $0336
  STZ $0337

.BRANCH_UPSILON:

  LDA.b #$01 : STA $0302

  LDY $66

.BRANCH_OMICRON:

  LDA $B64B, Y : STA $43

.BRANCH_SIGMA:

  LDA $67 : AND $42 : AND $43 : STA $67

.BRANCH_ULTIMA:

  LDA $67 : AND.b #$0F : BEQ .BRANCH_PHI

  LDA $6B : AND.b #$0F : BEQ .BRANCH_PHI

  STA $67

.BRANCH_PHI:

  ; Is this checking if Link is moving diagonally?
  LDA $6A : STZ $6A : CMP.b #$02 : BNE .BRANCH_OMEGA

  LDY.b #$01

  LDA $2F : AND.b #$04 : BEQ .BRANCH_ALIF

  LDY.b #$02

.BRANCH_ALIF:

  STY $6A

.BRANCH_OMEGA:

  RTS
}
