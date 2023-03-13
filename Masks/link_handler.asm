; =============================================================================
;  Link Handler Expanded Bank Module
;  Handles the routines necessary for creating "Mask Forms"
; =============================================================================

; Makes use of Bank07 Expanded Space
; $3F89D-$3FFFF NULL 
; {
;   fillbyte $FF
  
;   fill $763
; }
; ==============================================================================

; *$3D798-$3D7D7 LOCAL
TileDetect_ResetState:
{
  STZ $0C
  STZ $0E
  STZ $38
  STZ $58
  
  STZ $02C0
  
  STZ $5F
  STZ $62
  
  STZ $0320
  STZ $0341
  STZ $0343
  STZ $0348
  STZ $034C
  STZ $0357
  STZ $0359
  STZ $035B
  STZ $0366
  STZ $036D
  STZ $036F
  STZ $03E5
  STZ $03E7
  STZ $02EE
  STZ $02F6
  STZ $03F1
  
  RTS
}

; ==============================================================================

; *$3D077-$3D2C5 LOCAL
UnnamedRoutine3:
{
  ; Takes Y as an input ranging from 0x00 to 0x08
  ; The different behaviors with each has not been figured out yet
  
  STZ $59
  
  REP #$20
  
  JSR TileDetect_ResetState
  
  STY $00 : CPY.b #$08 : BNE .alpha
  
  ; Checking to see if a spin attack is still executing.
  LDA $031C : AND.w #$00FF : DEC #2 : BMI .stillSpinAttacking
  
  CMP.w #$0008 : BCS .stillSpinAttacking
  
  PHY
  
  TAY
  
  LDA $D06F, Y : AND.w #$00FF : CLC : ADC.w #$0040 : TAY
  
  BRA .delta

.alpha

  PHY
  
  ; Use the direction link is facing and the action in question to form an index
  LDA $00 : AND.w #$00FF : ASL #3 : CLC : ADC $2F : TAY

.delta

  ; Find some coordinates relative to Link, but depending on
  LDA $22 : CLC : ADC $D01C, Y : AND $EC : LSR #3 : STA $02
  
  LDA $20 : CLC : ADC $CFCC, Y : AND $EC : STA $00
  
  LDA.w #$0001 : STA $0A
  
  PLY
  
  REP #$10
  
  ; 0 - nothing, just standing there, 1 - sword, others - ????
  TYA
  
  CMP.w #$0001 : BEQ .BRANCH_EPSILON
  CMP.w #$0002 : BEQ .BRANCH_EPSILON
  CMP.w #$0003 : BEQ .BRANCH_EPSILON
  CMP.w #$0006 : BEQ .BRANCH_EPSILON
  CMP.w #$0007 : BEQ .BRANCH_EPSILON
  CMP.w #$0008 : BEQ .BRANCH_EPSILON
  
  ; action types 0x00, 0x05, and 0x04 end up here
  PHY
  
  JSR TileDetect_Execute
  
  PLY
  
  BRA .BRANCH_MU

.BRANCH_EPSILON:

  SEP #$30
  
  JSR $DC4A ; $3DC4A IN ROM

.stillSpinAttacking

  SEP #$30

.BRANCH_XI:

  BRL .return

.BRANCH_MU:

  SEP #$30
  
  CPY.b #$05 : BEQ .BRANCH_XI
  
  LDA $0357 : AND.b #$10 : BEQ .BRANCH_OMICRON
  
  LDA $20 : CLC : ADC.b #$08 : AND.b #$0F
  
  CMP.b #$04 : BCC .BRANCH_PI
  CMP.b #$0B : BCC .BRANCH_RHO

.BRANCH_PI:

  LDA $22 : AND.b #$0F
  
  CMP.b #$04 : BCC .BRANCH_SIGMA
  CMP.b #$0C : BCC .BRANCH_RHO

.BRANCH_SIGMA:

  LDA $031F : BNE .BRANCH_RHO
  
  LDA $4D : BNE .BRANCH_RHO
  
  LDA $1B : BEQ .BRANCH_CHI
  
  JSL Dungeon_SaveRoomQuadrantData
  
  LDA.b #$33 : JSR Player_DoSfx2
  
  STZ $5E
  
  LDA.b #$15 : STA $11
  
  LDA $A0 : STA $A2
  
  LDA $7EC000 : STA $A0
  
  JSR $94F1 ; $394F1 IN ROM
  
  BRA .BRANCH_RHO

.BRANCH_CHI:

  LDA $02DB : BNE .BRANCH_RHO
  
  JSR $A95C ; $3A95C IN ROM

.BRANCH_RHO:

  BRL .BRANCH_GAMMA

.BRANCH_OMICRON:

  STZ $02DB
  
  LDA $0357 : AND.b #$01 : BEQ .BRANCH_ZETA
  
  LDA.b #$02 : STA $0351
  
  JSR $D2C6 ; $3D2C6 IN ROM
  
  BCS .BRANCH_THETA
  
  LDA $4D : BNE .BRANCH_THETA
  
  LDA.b #$1A : JSR Player_DoSfx2

.BRANCH_THETA:

  BRL .BRANCH_KAPPA

.BRANCH_ZETA:

  LDA $0359 : AND.b #$01 : BEQ .BRANCH_LAMBDA
  
  LDA.b #$01 : STA $0351
  
  LDA $1B : BNE .BRANCH_IOTA
  
  LDA $0345 : BEQ .BRANCH_IOTA
  
  LDA $02E0 : BNE .BRANCH_IOTA
  
  LDA $7EF356 : BEQ .BRANCH_THETA
  
  STZ $0345
  
  LDA $0340 : STA $26
  
  LDA.b #$00 : STA $5D
  
  BRL .BRANCH_KAPPA

.BRANCH_IOTA:

  ; $3D2C6 IN ROM
  JSR $D2C6 : BCS .BRANCH_TAU
  
  LDA $8A : CMP.b #$70 : BNE .notEvilSwamp

.BRANCH_LAMBDA:

  LDA.b #$1B : JSR Player_DoSfx2
  
  BRA .BRANCH_TAU

.notEvilSwamp

  LDA $4D : BNE .BRANCH_TAU
  
  LDA.b #$1C : JSR Player_DoSfx2

.BRANCH_TAU:

  BRL .BRANCH_KAPPA
  
  LDA $1B : BNE .BRANCH_ALEPH
  
  LDA $0345 : BNE .BRANCH_ALEPH
  
  LDA $0341 : AND.b #$01 : BEQ .BRANCH_ALEPH
  
  LDA.b #$01 : STA $0351
  
  ; $3D2C6 IN ROM
  JSR $D2C6 : BCS .BRANCH_BET
  
  ; Dat be sum swamp o' evil
  LDA $8A : CMP.b #$70 : BNE .BRANCH_DALET
  
  LDA.b #$1B : JSR Player_DoSfx2
  
  BRA .BRANCH_BET

.BRANCH_DALET:

  LDA $4D : BNE .BRANCH_BET
  
  LDA.b #$1C : JSR Player_DoSfx2

.BRANCH_BET:

  BRL .return

.BRANCH_ALEPH:

  STZ $0351
  
  LDA $02EE : AND.b #$01
  
  BEQ .chet
  
  ; Only current documentation on this relates to the Desert Palace opening
  LDA.b #$01 : STA $02ED
  
  ; Our work is done here I guess?
  BRL .return

.chet

  STZ $02ED
  
  LDA $02EE : AND.b #$10 : BEQ .noSpikeFloorDamage
  
  STZ $0373
  
  LDA $55 : BNE .noSpikeFloorDamage
  
  ; $3AFB5 IN ROM
  JSR $AFB5 : BCS .noSpikeFloorDamage
  
  ; Did Link just get damaged and is still flashing?
  LDA $031F : BNE .noSpikeFloorDamage
  
  STZ $03F7
  STZ $03F5
  STZ $03F6
  
  ; moon pearl
  LDA $7EF357 : BEQ .doesntHaveMoonPearl
  
  STZ $56
  STZ $02E0

.doesntHaveMoonPearl

  ; armor level
  LDA $7EF35B : TAY
  
  ; Determine how much damage the spike floor will do to Link.
  LDA $D06C, Y : STA $0373
  
  BRL LinkState_ExitingDash

.noSpikeFloorDamage

  LDA $0348 : AND.b #$11 : BEQ .notWalkingOnIce
  
  LDA $034A : BEQ .BRANCH_AYIN
  
  LDA $6A : BEQ .BRANCH_PEY
  
  LDA $0340 : STA $26
  
  BRL .BRANCH_PEY

.BRANCH_AYIN:

  LDA $67 : AND.b #$0C : BEQ .BRANCH_TSADIE
  
  LDA.b #$01 : STA $033D
  LDA.b #$80 : STA $033C

.BRANCH_TSADIE:

  LDA $67 : AND.b #$03 : BEQ .BRANCH_QOF
  
  LDA.b #$01 : STA $033D
  LDA.b #$80 : STA $033C

.BRANCH_QOF:

  LDY.b #$01
  
  LDA $0348 : AND.b #$01 : BNE .BRANCH_RESH
  
  LDY.b #$02

.BRANCH_RESH:

  STY $034A
  
  LDA $26 : STA $0340
  
  JSL Player_ResetSwimState
  
  BRL .BRANCH_PEY

.notWalkingOnIce

  LDA $5D : CMP.b #$04 : BEQ .BRANCH_SIN
  
  LDA $034A : BEQ .BRANCH_TAV
  
  LDA $0340 : STA $26

.BRANCH_TAV:

  JSL Player_ResetSwimState

.BRANCH_SIN:

  STZ $034A

.BRANCH_PEY:

  LDA $02E8 : AND.b #$10 : BEQ .BRANCH_KAPPA
  
  LDA $031F : BNE .BRANCH_KAPPA
  
  LDA.b #$3A : STA $031F

.BRANCH_KAPPA:
.return

  RTS
}

; *$39D84-$39E62 LOCAL
Link_ResetSwordAndItemUsage:
{

  .BRANCH_EPSILON:

  ; Bring Link to stop
  STZ $5E

  LDA $48 : AND.b #$F6 : STA $48

  ; Stop any animations Link is doing
  STZ $3D
  STZ $3C

  ; Nullify button input on the B button
  LDA $3A : AND.b #$7E : STA $3A

  ; Make it so Link can change direction if need be
  LDA $50 : AND.b #$FE : STA $50

  BRL .BRANCH_ALPHA

; *$39D9F ALTERNATE ENTRY POINT

  BIT $48 : BNE .BRANCH_BETA

  LDA $48 : AND.b #$09 : BNE .BRANCH_GAMMA

  .BRANCH_BETA:

  LDA $47    : BEQ .BRANCH_DELTA
  CMP.b #$01 : BEQ .BRANCH_EPSILON

  .BRANCH_GAMMA:

  LDA $3C : CMP.b #$09 : BNE .BRANCH_ZETA

  LDX.b #$0A : STX $3C

  LDA $9CBF, X : STA $3D

  .BRANCH_ZETA:

  DEC $3D : BPL .BRANCH_THETA

  LDA $3C : INC A : CMP.b #$0D : BNE .BRANCH_KAPPA

  LDA $7EF359 : INC A : AND.b #$FE : BEQ .BRANCH_LAMBDA

  LDA $48 : AND.b #$09 : BEQ .BRANCH_LAMBDA

  LDY.b #$01
  LDA.b #$1B

  JSL AddWallTapSpark ; $49395 IN ROM

  LDA $48 : AND.b #$08 : BNE .BRANCH_MUNU

  LDA $05 : JSR Player_DoSfx2

  BRA .BRANCH_XI

  .BRANCH_MUNU:

  LDA.b #$06 : JSR Player_DoSfx2

  .BRANCH_XI:

  ; Do sword interaction with tiles
  LDY.b #$01

  JSR UnnamedRoutine3 ; $3D077 IN ROM

.BRANCH_LAMBDA:

  LDA.b #$0A

.BRANCH_KAPPA:

  STA $3C : TAX

  LDA $9CBF, X : STA $3D

.BRANCH_THETA:

  BRA .BRANCH_RHO

.BRANCH_DELTA:

  LDA.b #$09 : STA $3C

  LDA.b #$01 : TSB $50

  STZ $3D

  LDA $5E

  CMP.b #$04 : BEQ .BRANCH_RHO
  CMP.b #$10 : BEQ .BRANCH_RHO

  LDA.b #$0C : STA $5E

  LDA $7EF359 : INC A : AND.b #$FE : BEQ .BRANCH_ALPHA

  LDX.b #$04

.BRANCH_PHI:

  LDA $0C4A, X

  CMP.b #$30 : BEQ .BRANCH_ALPHA
  CMP.b #$31 : BEQ .BRANCH_ALPHA

  DEX : BPL .BRANCH_PHI

  LDA $79 : CMP.b #$06 : BCC .BRANCH_CHI

  LDA $1A : AND.b #$03 : BNE .BRANCH_CHI

  JSL AncillaSpawn_SwordChargeSparkle

.BRANCH_CHI:

  LDA $79 : CMP.b #$40 : BCS .BRANCH_ALPHA

  INC $79 : LDA $79 : CMP.b #$30 : BNE .BRANCH_ALPHA

  LDA.b #$37 : JSR Player_DoSfx2

  JSL AddChargedSpinAttackSparkle

  BRA .BRANCH_ALPHA

.BRANCH_RHO:

  JSR $9E63 ; $39E63 IN ROM

  .BRANCH_ALPHA:

  RTS
}

; =============================================================================

; *$3C8E9-$3CB83 LONG BRANCH LOCATION
CancelStairDragWithHorizontals:
{
  LDA $6A : BNE .BRANCH_ALPHA

  STZ $57

  LDA $5E : CMP.b #$02 : BNE .BRANCH_ALPHA

  STZ $5E

.BRANCH_ALPHA:

  LDA $59 : AND.b #$05 : BEQ .BRANCH_BETA

  LDA $0E : AND.b #$02 : BNE .BRANCH_BETA

  LDA $5D

  CMP.b #$05 : BEQ .BRANCH_GAMMA
  CMP.b #$02 : BEQ .BRANCH_GAMMA

  LDA.b #$09 : STA $5C

  STZ $5A

  LDA.b #$01 : STA $5B

  LDA.b #$01 : STA $5D

.BRANCH_GAMMA:

  RTS

.BRANCH_BETA:

  LDA $0366 : AND.b #$02 : BEQ .BRANCH_DELTA

  LDA $036A : ASL A : STA $0369

  BRA .BRANCH_EPSILON

.BRANCH_DELTA:

  STZ $0369

.BRANCH_EPSILON:

  LDA $0341 : AND.b #$04 : BEQ .BRANCH_ZETA

  BRA .BRANCH_THETA

  LDA $0341 : AND.b #$07 : CMP.b #$07 : BNE .BRANCH_ZETA

.BRANCH_THETA:

  LDA $0345 : BNE .BRANCH_ZETA

  LDA $4D : BNE .BRANCH_ZETA

  JSR LinkState_ExitingDash
  JSR $9D84 ; $39D84 IN ROM

  LDA.b #$01 : STA $0345

  LDA $26 : STA $0340

  JSL Player_ResetSwimState

  STZ $0376
  STZ $5E

  LDA $0351 : CMP.b #$01 : BNE .BRANCH_IOTA

  JSR $AE54 ; $3AE54 IN ROM

  LDA $7EF356 : BEQ .BRANCH_IOTA

  LDA $02E0 : BNE .BRANCH_ZETA

  LDA.b #$04 : STA $5D

  BRA .BRANCH_ZETA

.BRANCH_IOTA:

  LDA $3E : STA $20
  LDA $40 : STA $21

  LDA $3F : STA $22
  LDA $41 : STA $23

  LDA.b #$01 : STA $037B

  JSR $CC3C ; $3CC3C IN ROM

  LDA.b #$20 : JSR Player_DoSfx2

.BRANCH_ZETA:

  LDA $0345 : BEQ .BRANCH_KAPPA

  LDA $036E : AND.b #$07 : CMP.b #$07 : BEQ .BRANCH_LAMBDA

  BRA .BRANCH_MU

  .BRANCH_KAPPA:

  LDA $036D : AND.b #$42 : BEQ .BRANCH_MU

.BRANCH_LAMBDA:

  LDA.b #$07 : STA $0E

  BRL .BRANCH_$3C7FC

.BRANCH_MU:

  LDA $0343 : AND.b #$07 : CMP.b #$07 : BNE .BRANCH_NU

  LDA $0345 : BEQ .BRANCH_NU

  JSR LinkState_ExitingDash

  LDA $4D : BNE .BRANCH_NU

  LDA $0340 : STA $26

  STZ $0345

  LDA.b #$15
  LDY.b #$00

  JSL AddTransitionSplash  ; $498FC IN ROM

  LDA.b #$01 : STA $037B

  BRL .BRANCH_$3CC3C

.BRANCH_NU:

  LDA $036E : AND.b #$07 : BEQ .BRANCH_XI

  ; $3C16D IN ROM
  JSR $C16D : BCC .BRANCH_XI

  LDA.b #$20 : JSR Player_DoSfx2

  LDX.b #$10

  LDA $66 : AND.b #$01 : BNE .BRANCH_OMICRON

  TXA : EOR.b #$FF : INC A : TAX

.BRANCH_OMICRON:

  STX $28

  JSR LinkState_ExitingDash

  LDA.b #$02 : STA $4D

  LDA.b #$14 : STA $0362 : STA $0363

  LDA.b #$FF : STA $0364

  LDA.b #$0C : STA $5D

  LDA.b #$01 : STA $037B : STA $78

  STZ $48
  STZ $5E

  LDA $1B

  BNE .BRANCH_PI

  LDA.b #$02 : STA $EE

.BRANCH_PI:

  LDA $66 : AND.b #$FD : ASL A : TAY

  LDA $22 : PHA
  LDA $23 : PHA

  JSR $8D2B   ; $38D2B IN ROM

  LDA.b #$01 : STA $66

  CPX.b #$FF

  BEQ .BRANCH_RHO

  JSR $8B9B ; $38B9B IN ROM

  BRL .BRANCH_SIGMA

.BRANCH_RHO:

  JSR $8AD1; $38AD1 IN ROM

.BRANCH_SIGMA:

  PLA : STA $23
  PLA : STA $22

  RTS

.BRANCH_XI:

  LDA $0370 : AND.b #$77

  BEQ .BRANCH_TAU

  JSR $C16D ; $3C16D IN ROM

  BCC .BRANCH_TAU

  LDA.b #$20 : JSR Player_DoSfx2

  LDX.b #$0F

  AND.b #$07

  BNE .BRANCH_UPSILON

  LDX.b #$10

.BRANCH_UPSILON:

  STX $5D

  LDX.b #$10

  LDA $66 : AND.b #$01

  BNE .BRANCH_PHI

  LDX.b #$F0

.BRANCH_PHI:

  STX $28

  JSR LinkState_ExitingDash

  LDA.b #$02 : STA $4D

  LDA.b #$14 : STA $0362 : STA $0363

  LDA.b #$FF : STA $0364

  STZ $46

  LDA.b #$01 : STA $037B : STA $78

  STZ $48
  STZ $5E

  RTS

.BRANCH_TAU:

  LDA $036E : AND.b #$70 : BEQ .BRANCH_CHI

  LDA $036E : AND.b #$07 : BNE .BRANCH_CHI

  LDA $0370 : AND.b #$77 : BNE .BRANCH_CHI

  LDA $5D : CMP.b #$0D : BEQ .BRANCH_CHI

  ; $3C16D IN ROM
  JSR $C16D : BCC .BRANCH_CHI

  LDA.b #$20 : JSR Player_DoSfx2

  JSR LinkState_ExitingDash

  LDA.b #$01 : STA $037B

  STZ $48
  STZ $5E

  BRL .BRANCH_$3C46D

.BRANCH_CHI:

  LDA $036F : AND.b #$07 : BEQ .BRANCH_PSI

  LDA $036E : AND.b #$07 : BNE .BRANCH_PSI

  LDA $0370 : AND.b #$77 : BNE .BRANCH_PSI

  ; $3C16D IN ROM
  JSR $C16D : BCC .BRANCH_PSI

  LDX.b #$10

  LDA $66 : AND.b #$01 : BNE .BRANCH_OMEGA

  TXA : EOR.b #$FF : INC A : TAX

.BRANCH_OMEGA:

  STX $28

  JSR LinkState_ExitingDash

  LDA.b #$02 : STA $4D

  LDA.b #$14 : STA $0362 : STA $0363

  LDA.b #$FF : STA $0364

  LDA.b #$0E : STA $5D

  STZ $46

  LDA.b #$01 : STA $037B : STA $78

  STZ $48
  STZ $5E

  RTS

.BRANCH_PSI:

  LDA $0E : AND.b #$02 : BNE .BRANCH_ALIF

  LDA $0C : AND.b #$05 : BEQ .BRANCH_ALIF

  LDA $0372 : BEQ .BRANCH_BET

  LDA $2F : AND.b #$04 : BEQ .BRANCH_ALIF

.BRANCH_BET:

  JSR $E112   ; $3E112 IN ROM

  LDA $6B : AND.b #$0F : BEQ .BRANCH_ALIF

  RTS

.BRANCH_ALIF:

  STZ $6B

  ; check for spike block interactions
  LDA $02E8 : AND.b #$07 : BEQ .noSpikeBlockInteraction

  ; link is flashing or otherwise invincible
  LDA $46 : ORA $031F : ORA $55 : BNE .ignoreSpikeBlocks

  LDA $22

  LDY $66 : CPY.b #$02 : BNE .didntMoveLeft

  ; this is a tad strange, seems like more of a tweak than anything else
  AND.b #$04 : BEQ .notOn4PixelGrid

  BRA .noSpikeBlockInteraction

.didntMoveLeft

  AND.b #$04 : BEQ .noSpikeBlockInteraction

.notOn4PixelGrid

  ; use armor value to determine damage to be doled out
  LDA $7EF35B : TAY

  LDA $BA07, Y : STA $0373

  JSR LinkState_ExitingDash

  BRL .BRANCH_$39222

.ignoreSpikeBlocks

  LDA $02E8 : AND.b #$07 : STA $0E

.noSpikeBlockInteraction

  BRL .BRANCH_$3C7FC
}

; =============================================================================

; *$3CDCB-$3CE29 LOCAL
TileDetect_Movement_Vertical:
{
  ; This probably the up/down movement handler analagous to $3CE2A below
  REP #$20
  
  JSR TileDetect_ResetState
  
  STZ $59
  
  LDA $20 : CLC : ADC $CB7B, Y : STA $51 : AND $EC : STA $00
  LDA $22 : CLC : ADC $CD89, Y : AND $EC : LSR #3  : STA $02
  LDA $22 : CLC : ADC $CD8B, Y : AND $EC : LSR #3  : STA $04
  LDA $22 : CLC : ADC $CD93, Y : AND $EC : LSR #3  : STA $74
  
  REP #$10
  
  LDA.w #$0001 : STA $0A
  
  JSR TileDetect_Execute
  
  LDA $04 : STA $02
  
  LDA.w #$0002 : STA $0A
  
  JSR TileDetect_Execute
  
  LDA $74 : STA $02
  
  LDA.w #$0004 : STA $0A
  
  JSR TileDetect_Execute
  
  SEP #$30
  
  RTS
}

; *$3CE2A-$3CE84 LOCAL
TileDetect_Movement_Horizontal:
{
  ; Note, this routine only execute when Link is moving horizontally
  ; (Yes, it will execute if he's moving in a diagonal direction since that includes horizontal)
  
  REP #$20
  
  JSR TileDetect_ResetState
  
  STZ $59
  
  LDA $22 : CLC : ADC $CD7B, Y : AND $EC : LSR #3 : STA $02
  
  LDA $20 : CLC : ADC $CD83, Y : AND $EC : STA $00
  
  LDA $20 : CLC : ADC $CD8B, Y : STA $51 : AND $EC : STA $04
  
  LDA $20 : CLC : ADC $CD93, Y : STA $53 : AND $EC : STA $08
  
  REP #$10
  
  LDA.w #$0001 : STA $0A
  
  JSR TileDetect_Execute
  
  LDA $04 : STA $00
  
  LDA.w #$0002 : STA $0A
  
  JSR TileDetect_Execute
  
  LDA $08 : STA $00
  
  LDA.w #$0004 : STA $0A
  
  JSR TileDetect_Execute
  
  SEP #$30
  
  RTS
}

; *$3C4D4-$3C8E8 LOCAL
{
  LDA $31 : BNE .BRANCH_ALPHA

  RTS

.BRANCH_ALPHA:

  LDA $6C : CMP.b #$02 : BNE .BRANCH_BETA

  LDY.b #$04

  LDA $22 : CMP.b #$80 : BCC .BRANCH_GAMMA

  BRA .BRANCH_DELTA

.BRANCH_BETA:

  LDY.b #$04

  LDA $31 : BMI .BRANCH_GAMMA

.BRANCH_DELTA:

  LDY.b #$06

.BRANCH_GAMMA:

  TYA : LSR A : STA $66

  JSR $CE2A ; $3CE2A IN ROM; Has to do with detecting areas around chests.

  LDA $1B : BNE .BRANCH_EPSILON

  BRL CancelStairDragWithHorizontals

.BRANCH_EPSILON:

  LDA $0308 : BMI .BRANCH_ZETA

  LDA $46 : BEQ .BRANCH_THETA

.BRANCH_ZETA:

  LDA $0E : LSR #4 : TSB $0E

  BRL .BRANCH_RHO

.BRANCH_THETA:

  LDA $6A : BNE .BRANCH_IOTA

  STZ $57

.BRANCH_IOTA:

  LDA $6C : CMP.b #$01 : BNE .BRANCH_KAPPA

  LDA $6A : BNE .BRANCH_KAPPA

  LDA $046C : CMP.b #$03 : BNE .BRANCH_LAMBDA

  LDA $EE : BEQ .BRANCH_LAMBDA

  BRL .BRANCH_TAU

.BRANCH_LAMBDA:

  JSR $CB84   ; $3CB84 IN ROM
  JSR $CBDD   ; $3CBDD IN ROM

  BRL .BRANCH_$3D667

.BRANCH_KAPPA:

  LDA $0E : AND.b #$70 : BEQ .BRANCH_RHO

  STZ $05

  LDA $0F : AND.b #$07 : BEQ .BRANCH_NU

  LDY.b #$02

  LDA $31 : BCC .BRANCH_XI

  LDY.b #$03

.BRANCH_XI:

  LDA $B7C3, Y : STA $49

.BRANCH_NU:

  LDA.b #$02 : STA $6C

  STZ $03F3

  LDA $0E : AND.b #$70 : CMP.b #$70 : BEQ .BRANCH_OMICRON

  LDA $0E : AND.b #$07 : BNE .BRANCH_PI

  LDA $0E : AND.b #$70 : BNE .BRANCH_OMICRON

  BRA .BRANCH_RHO

.BRANCH_PI:

  STZ $6B
  STZ $6C

  JSR $CB84   ; $3CB84 IN ROM
  JML $07CB9F ; $3CB9F IN ROM

.BRANCH_OMICRON:

  LDA $0315 : AND.b #$02 : BNE .BRANCH_SIGMA

  LDA $50 : AND.b #$FD : STA $50

.BRANCH_SIGMA:

  RTS

.BRANCH_RHO:

  LDA $0315 : AND.b #$02 : BNE .BRANCH_TAU

  LDA $50 : AND.b #$FD : STA $50

  STZ $6C
  STZ $EF
  STZ $49

.BRANCH_TAU:

  LDA $0E : AND.b #$02 : BNE .BRANCH_UPSILON

  LDA $0C : AND.b #$05 : BEQ .BRANCH_UPSILON

  STZ $03F3

  JSR $E112 ; $3E112 IN ROM

  LDA $6B : AND.b #$0F : BEQ .BRANCH_UPSILON

  RTS

.BRANCH_UPSILON:

  STZ $6B

  LDA $EE : BNE .BRANCH_PHI

  LDA $034C : AND.b #$07 : BEQ .BRANCH_CHI

  LDA.b #$01 : TSB $0322

  BRA .BRANCH_PSI

.BRANCH_CHI:

  LDA $02E8 : AND.b #$07 : BNE .BRANCH_PSI

  LDA $0E : AND.b #$02 : BNE .BRANCH_PSI

  LDA $0322 : AND.b #$FE : STA $0322

  BRA .BRANCH_PSI

.BRANCH_PHI:

  LDA $0320 : AND.b #$07 : BEQ .BRANCH_OMEGA

  LDA.b #$02 : TSB $0322

  BRA .BRANCH_PSI

.BRANCH_OMEGA:

  ; Apparently they knew how to use TSB but now how to use TRB >___>
  ; LDA.b #$02 : TRB $0322 would have sooooo worked here
  LDA $0322 : AND.b #$FD : STA $0322

  .BRANCH_PSI:

  LDA $02F7 : AND.b #$22 : BEQ .no_blue_rupee_touch

  LDX.b #$00

  AND.b #$20 : BEQ .touched_upper_rupee_half

  LDX.b #$08

  .touched_upper_rupee_half

  STX $00
  STZ $01

  LDA $66 : ASL A : TAY

  REP #$20

  LDA $7EF360 : CLC : ADC.w #$0005 : STA $7EF360

  ; Configure the CLC : ADCress where the clearing of the rupee tile will occur.
  LDA $20 : CLC : ADC $B9F7, Y : SEC : SBC $00 : STA $00
  LDA $22 : CLC : ADC $B9FF, Y           : STA $02

  SEP #$20

  JSL Dungeon_ClearRupeeTile

  LDA.b #$0A : JSR Player_DoSfx3

  .no_blue_rupee_touch

  LDY.b #$01

  LDA $03F1

  AND.b #$22 : BEQ .BRANCH_DEL
  AND.b #$20 : BEQ .BRANCH_THEL

  LDY.b #$02

.BRANCH_THEL:

  STY $03F3

; *$3C64D LONG BRANCH LOCATION

  BRA .BRANCH_SIN

.BRANCH_DEL:

  LDY.b #$03

  LDA $03F2

  AND.b #$22 : BEQ .BRANCH_SHIN
  AND.b #$20 : BEQ .BRANCH_SOD

  LDY.b #$04

  .BRANCH_SOD:

  STY $03F3

  BRA .BRANCH_SIN

  .BRANCH_SHIN:

  LDA $02E8 : AND.b #$07 : BNE .BRANCH_SIN

  LDA $0E : AND.b #$02 : BNE .BRANCH_SIN

  STZ $03F3

  .BRANCH_SIN:

  LDA $036E : AND.b #$07 : CMP.b #$07 : BNE .BRANCH_DOD

  ; $3C16D IN ROM
  JSR $C16D : BCC .BRANCH_DOD

  JSR LinkState_ExitingDash

  INC $047A

  LDA.b #$02 : STA $4D

  BRA .BRANCH_TOD

  .BRANCH_DOD:

  LDA $0341 : AND.b #$07 : CMP.b #$07 : BNE .BRANCH_ZOD

  LDA $0345 : BNE .BRANCH_ZOD

  LDA $5D : CMP.b #$06 : BEQ .BRANCH_ZOD

  LDA $3E : STA $20
  LDA $40 : STA $21
  LDA $3F : STA $22
  LDA $41 : STA $23

  JSR LinkState_ExitingDash

  LDA $1D : BNE .BRANCH_HEH

  JSL Player_LedgeJumpInducedLayerChange

  BRA .BRANCH_TOD

  .BRANCH_HEH:

  LDA.b #$01 : STA $0345

  LDA $26 : STA $0340

  STZ $0308
  STZ $0309
  STZ $0376
  STZ $5E

  JSL Player_ResetSwimState

  .BRANCH_TOD:

  LDA.b #$01 : STA $037B

  JSR $CC3C ; $3CC3C IN ROM

  LDA.b #$20 : JSR Player_DoSfx2

  BRA .BRANCH_JIIM

  .BRANCH_ZOD:

  LDA $0343 : AND.b #$07 : CMP.b #$07 : BNE .BRANCH_JIIM

  LDA $0345 : BEQ .BRANCH_JIIM

  LDA $4D : BEQ .BRANCH_EIN

  LDA.b #$07 : STA $0E

  BRA .BRANCH_JIIM

  .BRANCH_EIN:

  JSR LinkState_ExitingDash

  LDA $4D : BNE .BRANCH_JIIM

  LDA $0340 : STA $26

  STZ $0345

  LDA.b #$15
  LDY.b #$00

  JSL SubTransitionSplash ; $498FC IN ROM

  LDA.b #$01 : STA $037B

  JSR $CC3C ; $3CC3C IN ROM

  .BRANCH_JIIM:

  LDA $59 : AND.b #$05 : BEQ .BRANCH_GHEIN

  LDA $0E : AND.b #$02 : BNE .BRANCH_GHEIN

  LDA $5D

  CMP.b #$05 : BEQ .BRANCH_FATHA
  CMP.b #$02 : BEQ .BRANCH_FATHA

  LDA.b #$09 : STA $5C

  STZ $5A

  LDA.b #$01 : STA $5B
  LDA.b #$01 : STA $5D

  .BRANCH_FATHA:

  RTS

  .BRANCH_GHEIN:

  STZ $5B

  LDA $02E8 : AND.b #$07 : BEQ .BRANCH_KESRA

  LDA $46 : ORA $031F : ORA $55 : BNE .BRANCH_DUMMA

  LDA $22

  LDY $66 : CPY.b #$02 : BNE .BRANCH_YEH

  AND.b #$04 : BEQ .BRANCH_WAW

  BRA .BRANCH_KESRA

  .BRANCH_YEH:

  AND.b #$04 : BEQ .BRANCH_KESRA

  .BRANCH_WAW:

  LDA $031F : BNE .BRANCH_KESRA

  LDA $7EF35B : TAY

  LDA $BA07, Y : STA $0373

  JSR LinkState_ExitingDash
  JSR $AE54 ; $3AE54 IN ROM

  BRL .BRANCH_$39222

  .BRANCH_DUMMA:

  LDA $02E8 : AND.b #$07 : STA $0E

  .BRANCH_KESRA:

  LDA $046C  : BEQ .BRANCH_ALPHA2
  CMP.b #$04 : BEQ .BRANCH_ALPHA2

  LDA $EE : BNE .BRANCH_BETA2

  .BRANCH_ALPHA2:

  LDA $5F : ORA $60 : BEQ .BRANCH_GAMMA2

  LDA $6A : BNE .BRANCH_GAMMA2

  LDA $5F : STA $02C2

  DEC $61 : BPL .BRANCH_BETA2

  REP #$20

  LDY.b #$0F

  LDA $5F

  .BRANCH_THETA2:

  ASL A : BCC .BRANCH_DELTA2

  PHA : PHY

  SEP #$20

  ; $3ED2C IN ROM
  JSR $ED2C : BCS .BRANCH_EPSILON2

  STX $0E

  TYA : ASL A : TAX

  ; $3ED3F IN ROM
  JSR $ED3F : BCS .BRANCH_EPSILON2

  LDA $0E : ASL A : TAY

  JSR $F0D9 ; $3F0D9 IN ROM

  TYX

  LDY $66

  TYA : ASL A : STA $05F8, X : STA $0474

  LDA $05E4, X : CPY.b #$02 : BEQ .BRANCH_ZETA2

  DEC A

  .BRANCH_ZETA2:

  AND.b #$0F : STA $05E8, X

  .BRANCH_EPSILON2:

  REP #$20

  PLY : PLA

  .BRANCH_DELTA2:

  DEY : BPL .BRANCH_THETA2

  SEP #$20

  .BRANCH_GAMMA2:

  LDA.b #$15 : STA $61

  .BRANCH_BETA2:

  LDA $6A : BNE .BRANCH_IOTA2

  STZ $57

  LDA $5E : CMP.b #$02 : BNE .BRANCH_IOTA2

  STZ $5E

; *$3C7FC LONG BRANCH LOCATION
  .BRANCH_IOTA2:

  LDA $0E : AND.b #$07 : BNE .BRANCH_KAPPA2

  BRL .BRANCH_PI2

  .BRANCH_KAPPA2:

  LDA $5D : CMP.b #$04 : BNE .BRANCH_LAMBDA2

  LDA $0312 : BNE .BRANCH_LAMBDA2

  JSR Player_ResetSwimCollision

  .BRANCH_LAMBDA2:

  LDA $0E : AND.b #$02 : BEQ .BRANCH_MU2

  LDA $0E : PHA

  JSR $C1A1 ; $3C1A1 IN ROM
  JSR $91F1 ; $391F1 IN ROM

  PLA : STA $0E

  .BRANCH_MU2:

  LDA.b #$01 : STA $0302

  LDA $0E : AND.b #$07 : CMP.b #$07 : BNE .BRANCH_NU2

  JSR $CB84 ; $3CB84 IN ROM

  BRA .BRANCH_XI2

  .BRANCH_NU2:

  LDA $6A : CMP.b #$02 : BNE .BRANCH_OMICRON2

  .BRANCH_PI2:

  BRL .BRANCH_ALPHA3

  .BRANCH_OMICRON2:

  JSR $CB84 ; $3CB84 IN ROM

  LDA $6A : CMP.b #$01 : BEQ .BRANCH_PI2

  .BRANCH_XI2:

  LDA $0E : AND.b #$05 : CMP.b #$05 : BEQ .BRANCH_RHO2

  AND.b #$04 : BEQ .BRANCH_SIGMA2

  LDY.b #$01

  LDA $31 : BCC .BRANCH_TAU2

  EOR.b #$FF : INC A

  .BRANCH_TAU2:

  BPL .BRANCH_UPSILON2

  LDY.b #$FF

  .BRANCH_UPSILON2:

  STY $00 : STZ $01

  LDA $0E : AND.b #$02 : BNE .BRANCH_PHI2

  LDA $20 : AND.b #$07 : BNE .BRANCH_CHI2

  JSR $C1A1 ; $3C1A1 IN ROM
  JSR $91F1 ; $391F1 IN ROM

  BRA .BRANCH_PHI2

  .BRANCH_SIGMA2:

  LDY.b #$01

  LDA $31 : BPL .BRANCH_PSI2

  EOR.b #$FF : INC A

  .BRANCH_PSI2:

  BPL .BRANCH_OMEGA2

  LDY.b #$FF

  .BRANCH_OMEGA2:

  STY $00 : STZ $01

  LDA $0E : AND.b #$02 : BNE .BRANCH_PHI2

  LDA $20 : AND.b #$07 : BNE .BRANCH_CHI2

  .BRANCH_RHO2:

  JSR $C1A1 ; $3C1A1 IN ROM
  JSR $91F1 ; $391F1 IN ROM

  BRA .BRANCH_PHI2

  .BRANCH_CHI2:

  JSR $CBC9 ; $3CBC9 IN ROM
  JMP $D485 ; $3D485 IN ROM

  .BRANCH_PHI2:

  LDA $66 : ASL A : CMP $2F : BNE .BRANCH_ALPHA3

  LDA $0315 : AND.b #$01 : ASL A : TSB $48

  LDA $3C : BNE .BRANCH_BETA3

  DEC $0371 : BPL .BRANCH_GAMMA3

  .BRANCH_BETA3:

  LDY $0315

  LDA $02F6 : AND.b #$20 : BEQ .BRANCH_DELTA3

  LDA $0315 : ASL #3 : TAY

  .BRANCH_DELTA3:

  TYA : TSB $48

  BRA .BRANCH_ALPHA3

  LDA $EE : BNE .BRANCH_GAMMA3

  LDA $48 : AND.b #$F6 : STA $48

  .BRANCH_ALPHA3:

  LDA.b #$20 : STA $0371

  LDA $48 : AND.b #$FD : STA $48

  .BRANCH_GAMMA3:

  RTS
}

; ==============================================================================

; *$3CF12-$3CF7D LOCAL
Player_TileDetectNearby:
{
  STZ $59
  
  REP #$20
  
  JSR TileDetect_ResetState
  
  LDA $22 : CLC : ADC $CD83 : AND $EC : LSR #3 : STA $02
  
  LDA $22 : CLC : ADC $CD93 : AND $EC : LSR #3 : STA $04
  
  LDA $20 : CLC : ADC $CD87 : AND $EC : STA $00 : STA $74
  
  LDA $20 : CLC : ADC $CD97 : AND $EC : STA $08

; *$3CF49 ALTERNATE ENTRY POINT

  REP #$10
  
  LDA.w #$0008 : STA $0A
  
  JSR TileDetect_Execute
  
  LDA $08 : STA $00
  
  LDA.w #$0002 : STA $0A
  
  JSR TileDetect_Execute
  
  LDA $74 : STA $00
  
  LDA $04 : STA $02
  
  LDA.w #$0004 : STA $02
  
  JSR TileDetect_Execute
  
  LDA $08 : STA $00
  
  LDA.w #$0001 : STA $0A
  
  JSR TileDetect_Execute
  
  SEP #$30
  
  RTS
}

; ==============================================================================

; *$3D9D8-$3DA29 LOCAL
TileDetect_Execute:
{
  ; Tile attribute handler
  
  ; Has $0A as a hidden argument.
  
  SEP #$30
  
  ; Are we indoors?
  LDA $1B : BNE .indoors
  
  ; Jump to routine that handles outdoor tile behaviors
  BRL $07DC2A

.indoors

  ; Handle dungeon tile attributes
  ; some quick notes:
  ; $06[1] is the tile type (no, not the tile type multiplied by two)
  ; $0A[2] seems to be either 1, 2, 4, or 8. This is basically the tile's position relative to Link
  
  REP #$20
  
  ; It's Link's movement impetus (it makes him move in a given direction each frame)
  LDA $49 : AND.w #$00FF : STA $49
  
  LDA $00 : AND.w #$FFF8 : ASL #3 : STA $06
  
  LDA $02 : AND.w #$003F : CLC : ADC $06
  
  ; Which part of a two level room is Link on
  LDX $EE : BEQ .lowerFloor
  
  ; He's on the upper floor then.
  ; CLC : ADC this offset in b/c BG0's tile attributes start at $7F3000
  CLC : ADC.w #$1000

.lowerFloor

  REP #$10
  
  TAX
  
  ; Are we figuring out what sort of tile this is
  LDA $7F2000, X : PHA
  
  LDA $037F : AND.w #$00FF
  
  BEQ .playinByTheRules
  
  ; $037F being nonzero is a sort of a hidden cheat code
  PLA
  
  LDA.w #$0000
  
  BRA .walkThroughWallsCode

.playinByTheRules

  ; Okay back to what kind of tile it was...
  PLA

.walkThroughWallsCode

  ; Store the tile type at $06 and mirror it at $0114
  AND.w #$00FF : STA $06 : STA $0114
  
  ; Save the offset for the tile (i.e. its position in $7F2000)
  STX $BD
  
  ; Multiply this tile index by two and use it to run a service routine for that kind of tile.
  ASL A : TAX
  
  JMP ($D7D8, X) ; ($3D7D8, X) THAT IS
}

; *$3CEC9-$3CF09 LOCAL
Collision_Detection:
{
  REP #$20
  
  JSR TileDetect_ResetState
  
  STZ $59
  
  LDA $22 : CLC : ADC $CDA3, Y : AND $EC : LSR #3 : STA $02
  
  LDA $20 : CLC : ADC $CDAB, Y : AND $EC : STA $00
  
  LDA $20 : CLC : ADC $CDB3, Y : AND $EC : STA $04
  
  REP #$10
  
  LDA.w #$0001 : STA $0A
  
  JSR TileDetect_Execute
  
  LDA $04 : STA $00
  
  LDA.w #$0002 : STA $0A
  
  JSR TileDetect_Execute
  
  SEP #$30
  
  RTS
}

; =============================================================================

; *$3B9B3-$3B9F6 LOCAL
Collision_Uncategorized:
{
  LDA $046C : CMP.b #$01 : BEQ .BRANCH_ALPHA
  
  REP #$20
  
  LDA $20 : SEC : SBC $0318 : STA $00
  LDA $22 : SEC : SBC $031A : STA $02
  
  LDA $E8 : SEC : SBC $E6 : CLC : ADC $20 : STA $20
  LDA $E2 : SEC : SBC $E0 : CLC : ADC $22 : STA $22
  
  SEP #$20
  
  LDA $67 : BEQ .BRANCH_ALPHA
  
  LDA $30 : CLC : ADC $00 : STA $30
  LDA $31 : CLC : ADC $02 : STA $31

  .BRANCH_ALPHA:

  STZ $EE
  
  RTS
}

; =============================================================================

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
  
  LDA $E6 : SEC : SBC $E8 : CLC : ADC $20 : STA $20 : STA $0318
  LDA $E0 : SEC : SBC $E2 : CLC : ADC $22 : STA $22 : STA $031A
  
  SEP #$20

.twoBgs

  LDA.b #$01 : STA $EE
  
  SEC
  
  RTS

.oneBg

  CLC
  
  RTS
}

; =============================================================================

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

; *$3B956-$3B968 LOCAL
RunSlopeCollisionChecks_VerticalFirst:
{
  LDA $6B : AND.b #$20 : BNE .BRANCH_ALPHA
  
  JSR $BA0A ; $3BA0A IN ROM

.BRANCH_ALPHA:

  LDA $6B : AND.b #$10 : BNE .BRANCH_BETA
  
  JSR $C4D4 ; $3C4D4 IN ROM

.BRANCH_BETA:

  RTS
}

; *$3B969-$3B97B LOCAL
RunSlopeCollisionChecks_HorizontalFirst:
{
  LDA $6B : AND.b #$10 : BNE .BRANCH_ALPHA
  
  JSR $C4D4   ; $3C4D4 IN ROM

  .BRANCH_ALPHA:

  LDA $6B : AND.b #$20 : BNE .BRANCH_BETA
  
  JSR $BA0A   ; $3BA0A IN ROM

.BRANCH_BETA:

  RTS
}

; ==============================================================================

; *$3CCAB-$3CD7A LOCAL
LinkTileMovementRoutine:
{
  ; Denotes how much Link will move during the frame in a vertical direction (signed)
  LDA $30 : BEQ .BRANCH_ALPHA
  
  ; this is reached if there is vertical movement
  LDA $31 : BNE .BRANCH_BETA

  .BRANCH_ALPHA:

  ; This is executed if there is no horizontal movement (vertical doesn't matter)
  
  BRL .BRANCH_THETA

.BRANCH_BETA:

  ; Basically this code executes only if Link is moving diagonally
  
  ; $02DE[2] = mirror of Link's Y coordinate
  LDA $20 : STA $02DE
  LDA $21 : STA $02DF
  
  ; $02DC[2] = mirror of Link's X coordinate
  LDA $22 : STA $02DC
  LDA $23 : STA $02DD
  
  LDY.b #$04
  
  LDA $31 : BMI .BRANCH_GAMMA ; Is Link moving to the left? If so, branch
  
  ; This probably sets up a different hit detection box b/c he's looking in a different direction
  LDY.b #$06

.BRANCH_GAMMA:

  JSR $CE2A ; $3CE2A IN ROM
  
  LDA $0C : AND.b #$05 : BEQ .BRANCH_DELTA
  
  JSR $E112 ; $3E112 IN ROM
  
  LDA $6B : AND.b #$0F : BNE .BRANCH_EPSILON

  .BRANCH_DELTA:

  BRL .BRANCH_THETA

.BRANCH_EPSILON:

  REP #$20
  
  LDA $22 : SEC : SBC $02DC : STA $00
  
  LDA $02DC : STA $22
  
  SEP #$20
  
  LDA $00 : STA $31
  
  LDY.b #$00
  
  LDA $30 : BMI .BRANCH_ZETA
  
  LDY.b #$02

.BRANCH_ZETA:

  JSR TileDetect_Movement_Vertical ; $3CDCB IN ROM
  
  LDA $0C : AND.b #$05 : BEQ .BRANCH_THETA
  
  JSR $E076 ; $3E076 IN ROM
  
  LDA $6B : AND.b #$0F : BEQ .BRANCH_THETA
  
  ; Store the diagonal movement characteristics to $6D (but why?)
  LDA $6B : STA $6D
  
  REP #$20
  
  LDA $20 : SEC : SBC $02DE : STA $00
  
  SEP #$20
  
  LDA $00 : STA $30
  
  LDY $31 : BMI .BRANCH_IOTA
  
  LDA $CC83, Y
  
  BRA .BRANCH_KAPPA

.BRANCH_IOTA:

  TYA : EOR.b #$FF : INC A : TAY
  
  LDA $CC8D, Y ; $3CC8D, Y THAT IS

.BRANCH_KAPPA:

  REP #$20
  
  AND.w #$00FF : CMP.w #$0080 : BCC .BRANCH_LAMBDA
  
  ORA.w #$FF00

.BRANCH_LAMBDA:

  CLC : ADC $22 : STA $22
  
  SEP #$20
  
  LDY $30 : BMI .BRANCH_MU
  
  LDA $CC97, Y
  
  BRA .BRANCH_NU

.BRANCH_MU:

  TYA : EOR.b #$FF : INC A : TAY
  
  LDA $CCA1, Y

.BRANCH_NU:

  REP #$20
  
  AND.w #$00FF : CMP.w #$0080 : BCC .BRANCH_XI
  
  ORA.w #$FF00

.BRANCH_XI:

  CLC : ADC $20 : STA $20
  
  SEP #$20
  
  BRA .BRANCH_OMICRON

.BRANCH_THETA:

  STZ $6D

.BRANCH_OMICRON:

  STZ $6B
  
  RTS
}

; *$3B7C7-$3B955 LOCAL
Link_HandleCardinalCollision:
{
  ; Initialize the diagonal wall state
  STZ $6E
  
  ; ????
  STZ $38
  
  ; Detects forced diagonal movement, as when walking against a diagonal wall
  ; Branch if there is [forced] diagonal movement
  LDA $6B : AND.b #$30 : BNE .BRANCH_ALPHA
  
  ; $3CCAB IN ROM; Handles left/right tiles and maybe up/down too
  JSR LinkTileMovementRoutine
  
  LDA $6D : BEQ .BRANCH_ALPHA
  
  BRL .BRANCH_BETA

  .BRANCH_ALPHA:

  ; $3B97C IN ROM
  JSR Collision_Settings : BCC .BRANCH_BETA
  
  ; "Check collision" as named in Hyrule Magic
  ; Keep in mind that outdoors, collisions are always 0, i.e. "normal"
  ; Why load it twice, homes?
  LDA $046C : CMP.b #$02 : BCC .BRANCH_GAMMA
  LDA $046C : CMP.b #$03 : BEQ .BRANCH_GAMMA
  
  LDA.b #$02 : STA $0315
  
  REP #$20
  
  JSR Player_TileDetectNearby
  
  SEP #$20
  
  LDA $0E : STA $0316 : BEQ .BRANCH_GAMMA
  
  LDA $30 : STA $00
  
  CLC : ADC $0310 : STA $30
  
  LDA $31 : STA $01
  
  CLC : ADC $0312 : STA $31
  
  LDA $0E
  
  CMP.b #$0C : BEQ .BRANCH_GAMMA
  CMP.b #$03 : BEQ .BRANCH_GAMMA
  CMP.b #$0A : BEQ .BRANCH_DELTA
  CMP.b #$05 : BEQ .BRANCH_DELTA
  AND.b #$0C : BNE .BRANCH_EPSILON
  
  LDA $0E : AND.b #$03 : BNE .BRANCH_EPSILON
  
  BRA .BRANCH_GAMMA

.BRANCH_EPSILON:

  LDA $00 : BNE .BRANCH_DELTA
  
  LDA $01 : BEQ .BRANCH_GAMMA
  
  LDA $0301 : BPL .BRANCH_DELTA

.BRANCH_GAMMA:

  JSR UnnamedRoutine1 ; $3B956 IN ROM
  
  BRA .BRANCH_ZETA

  .BRANCH_DELTA:

  JSR UnnamedRoutine2   ; $3B969 IN ROM

.BRANCH_ZETA:

  JSR $B9B3 ; $3B9B3 IN ROM

.BRANCH_BETA:

  ; Check the "collision" value (as in Hyrule Magic)
  LDA $046C
  
  CMP.b #$02 : BEQ .BRANCH_THETA
  CMP.b #$03 : BEQ .BRANCH_IOTA
  CMP.b #$04 : BEQ .BRANCH_KAPPA
  
  ; Is there horizontal or vertical scrolling happening?
  LDA $30 : ORA $31 : BNE .BRANCH_KAPPA
  
  LDA $5D
  
  CMP.b #$13 : BEQ .BRANCH_LAMBDA
  CMP.b #$08 : BEQ .BRANCH_LAMBDA
  CMP.b #$09 : BEQ .BRANCH_LAMBDA
  CMP.b #$0A : BEQ .BRANCH_LAMBDA
  CMP.b #$03 : BEQ .BRANCH_LAMBDA
  
  JSR Player_TileDetectNearby
  
  LDA $59 : AND.b #$0F : BEQ .BRANCH_LAMBDA
  
  LDA.b #$01 : STA $5D
  
  LDA $0372 : BNE .BRANCH_LAMBDA
  
  LDA.b #$04 : STA $5E

.BRANCH_LAMBDA:

  BRL .BRANCH_XI

.BRANCH_THETA:

  JSR Player_TileDetectNearby
  
  LDA $0E : ORA $0316 : CMP.b #$0F : BNE .BRANCH_KAPPA
  
  LDA $031F : BNE .BRANCH_MU
  
  LDA.b #$3A : STA $031F

.BRANCH_MU:

  LDA $67 : BNE .BRANCH_KAPPA
  
  LDA $0310 : BEQ .BRANCH_NU
  
  LDA $30 : EOR.b #$FF : INC A : STA $30

.BRANCH_NU:

  LDA $0312 : BEQ .BRANCH_KAPPA
  
  LDA $31 : EOR.b #$FF : INC A : STA $31

.BRANCH_KAPPA:

  LDA.b #$01 : STA $0315
  
  JSR UnnamedRoutine1 ; $3B956 IN ROM
  
  BRA .BRANCH_XI

.BRANCH_IOTA:

  LDA.b #$01 : STA $0315
  
  JSR UnnamedRoutine2 ; $3B969 IN ROM

.BRANCH_XI:

  LDY.b #$00
  
  JSR UnnamedRoutine3 ; $3D077 IN ROM
  
  LDA $6A : BEQ .BRANCH_OMICRON
  
  STZ $6B

.BRANCH_OMICRON:

  LDA $5D : CMP.b #$0B : BEQ .BRANCH_PI
  
  LDY.b #$08
  
  LDA $20 : SEC : SBC $3E : STA $30 : BEQ .BRANCH_PI : BMI .BRANCH_RHO
  
  LDY.b #$04

.BRANCH_RHO:

  LDA $67 : AND.b #$03 : STA $67
  
  TYA : TSB $67

.BRANCH_PI:

  ; Two LDA's in a row?
  LDA.b #$02
  
  LDA $22 : SEC : SBC $3F : STA $31 : BEQ .BRANCH_SIGMA : BMI .BRANCH_TAU
  
  LDY.b #$01

.BRANCH_TAU:

  LDA $67 : AND.b #$0C : STA $67
  
  TYA : TSB $67

.BRANCH_SIGMA:

  LDA $1B : BEQ .BRANCH_UPSILON
  
  LDA $046C : CMP.b #$04 : BNE .BRANCH_UPSILON
  
  LDA $5D : CMP.b #$04 : BNE .BRANCH_UPSILON
  
  LDY.b #$F7
  
  LDA $0310 : BEQ .BRANCH_PHI : BMI .BRANCH_CHI
  
  LDY.b #$FB

.BRANCH_CHI:

  EOR.b #$FF : INC A : CLC : ADC $30 : BNE .BRANCH_PHI
  
  TYA : AND $67 : STA $67

.BRANCH_PHI:

  LDY.b #$FD
  
  LDA $0312 : BEQ .BRANCH_UPSILON : BMI .BRANCH_PSI
  
  LDY.b #$FE

.BRANCH_PSI:

  EOR.b #$FF : INC A : CLC : ADC $31 : BNE .BRANCH_UPSILON
  
  TYA : AND $67 : STA $67

.BRANCH_UPSILON:

  RTS
}

; ==============================================================================

; *$3E8F0-$3E900 LOCAL
HandleIndoorCameraAndDoors:
{
  ; If outdoors, ignore
  LDA $1B : BEQ .return
  
  ; I'll deal with this routine later >:(
  LDA $6C : BEQ .notInDoorway
  
  JML $07E901 ; $3E901 IN ROM

.notInDoorway

  JSL $07E9D3 ; $3E9D3 IN ROM

.return

  RTS
}