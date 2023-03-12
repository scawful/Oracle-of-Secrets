; =============================================================================
; Wolf Mask 

; =============================================================================

org $098F5B
  AddShovelDirt:

org $098C73
  AddRecoveredFlute:

org $098024
  AddHitStars:

org $1DFD5C
  DiggingGameGuy_AttemptPrizeSpawn:


; =============================================================================

org $07D077
  Link_ShovelTileDetect:

org $07F8D1
Link_ShovelTileDetect_Long:
{
  PHB : PHK : PLB
  JSR Link_ShovelTileDetect
  PLB
  RTL
}

org $07802F
  Player_DoSfx3:

org $07A772
Player_DoSfx3_Long:
{
  PHB : PHK : PLB
  JSR Player_DoSfx3
  PLB
  RTL
}

print "Next address for jump in bank07: ", pc 

; =============================================================================

org $07A3DB
LinkItem_Flute:

; =============================================================================

org $07A313
LinkItem_ShovelAndFlute:
{
  ; Play flute or use the Wolf Mask
  LDA $0202 : CMP.b #$0D : BNE LinkItem_WolfMask
  BRL LinkItem_Flute
}

; =============================================================================

; TODO: Make sure there's no inaccessible code issues past here 
; LinkItem_Shovel 
org $07A32C
LinkItem_WolfMask:
{
  JSL LinkItem_UsingWolfMask
  JSR Link_CheckNewY_ButtonPress : BCC .return
  LDA $3A : AND.b #$BF : STA $3A        ; clear the Y button state 

  LDA $6C : BNE .return                 ; in a doorway
  LDA $0FFC : BNE .return               ; can't open menu

  LDY.b #$04 : LDA.b #$23
  JSL AddTransformationCloud
  LDA.b #$14 : JSR Player_DoSfx2

  LDA $02B2 : CMP #$03 : BEQ .unequip ; is the wolf mask already on?
  JSL UpdateWolfPalette
  LDA #$38 : STA $BC                   ; change link's sprite 
  LDA #$03 : STA $02B2
  BRA .return

.unequip
  JSL Palette_ArmorAndGloves
  LDA #$10 : STA $BC : STZ $02B2        ; take the mask off

.return
  CLC
  RTS
}

; =============================================================================

org $388000
incbin gfx/wolf_link.4bpp

; =============================================================================

UpdateWolfPalette:
{
  REP #$30 ; change 16bit mode
  LDX #$001E

  .loop
  LDA.l WolfPalette, X : STA $7EC6E0, X
  DEX : DEX : BPL .loop

  SEP #$30 ; go back to 8 bit mode
  INC $15 ; update the palette
  RTL ; or RTS depending on where you need it
}

; =============================================================================

WolfPalette:
  dw #$7BDE, #$7FFF, #$2F7D, #$19B5, #$3A9C, #$14A5, #$1A3D, #$14B6
  dw #$4650, #$362A, #$3F4E, #$162B, #$318A, #$39CC, #$1CE7, #$76D1
  dw #$6565, #$7271, #$14B5, #$459B, #$3D95, #$22D0, #$567C, #$1890
  dw #$7616, #$0000
  
; =============================================================================

LinkItem_Return:
{
  RTL
}

print pc
LinkItem_UsingWolfMask:
{
  ; Shovel item code
  
  BIT $3A : BVS .in_use
  LDA $6C : BNE LinkItem_Return ; .BRANCH_$3A312 ; (RTS, BASICALLY)
  
  LDA $F2     ; load unfiltered joypad 1 register (AXLR|????)
  CMP #$10    ; R button pressed?
  BEQ $03     ; if yes, branch behind the jump that leads to the end and load items instead
  JMP LinkItem_Return
  ; JSR Link_CheckNewY_ButtonPress : BCC LinkItem_Return ;.BRANCH_$3A312
  
  LDA $A320 : STA $3D
  
  STZ $030D
  STZ $0300
  
  LDA.b #$01 : STA $037A
  LDA.b #$01 : TSB $50
  STZ $2E

.in_use

  JSR HaltLinkWhenUsingItems ; $AE65 ; $3AE65 IN ROM
  
  LDA $67 : AND.b #$F0 : STA $67
  
  DEC $3D : BMI .continue
  
  RTL

.continue

  LDX $030D : INX : STX $030D
  
  LDA $A320, X : STA $3D
  
  LDA $A326, X : STA $0300 : CMP.b #$01 : BNE .BRANCH_GAMMA
  
  LDY.b #$02
  
  PHX
  
  ; JSR $D077   ; $3D077 IN ROM
  JSL Link_ShovelTileDetect_Long
  
  PLX
  
  LDA $04B2 : BEQ .not_flute_spot
  
  LDA.b #$1B : JSL Player_DoSfx3_Long
  
  PHX
  
  ; Add recovered flute (from digging). Interesting...
  LDY.b #$00
  LDA.b #$36
  
  JSL AddRecoveredFlute
  
  PLX

.not_flute_spot

  LDA $0357 : ORA $035B : AND.b #$01 : BNE .dont_clink
  
  PHX
  
  LDY.b #$00
  LDA.b #$16
  
  JSL AddHitStars
  
  PLX
  
  LDA.b #$05 : JSL Player_DoSfx2
  
  BRA .finish_up

.dont_clink

  PHX
  
  ; Add shovel dirt? what? I thought these were aftermath tiles
  LDY.b #$00
  LDA.b #$17
  
  JSL AddShovelDirt
  
  LDA $03FC : BEQ .digging_game_inactive
  
  JSL DiggingGameGuy_AttemptPrizeSpawn

.digging_game_inactive

  PLX
  
  LDA.b #$12 : JSL Player_DoSfx2

.finish_up

  CPX.b #$03 : BNE .return
  
  STZ $030D
  STZ $0300
  
  LDA $3A : AND.b #$80 : STA $3A
  
  STZ $037A
  
  LDA $50 : AND.b #$FE : STA $50

.return

  RTL
}

; ==============================================================================

; *$3AE65-$3AE87 LOCAL
HaltLinkWhenUsingItems:
{
  LDA $AD : CMP.b #$02 : BNE .BRANCH_ALPHA
  
  LDA $0322 : AND.b #$03 : CMP.b #$03 : BNE .BRANCH_ALPHA
  
  STZ $30
  STZ $31
  STZ $67
  STZ $2A
  STZ $2B
  STZ $6B

.BRANCH_ALPHA:

  ; Cane of Somaria transit lines?
  LDA $02F5 : BEQ .BRANCH_BETA
  
  STZ $67

.BRANCH_BETA:

  RTS
}