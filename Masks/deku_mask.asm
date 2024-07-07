; =========================================================
; Deku Mask
; Press R to transform into Deku Link
; Press Y to perform a spin and jump, allowing you to hover
; for a short period of time, as well as drop bombs while
; hovering with the Y button, and cancelling the hover with
; the B button.
; =========================================================

UpdateDekuPalette:
{
  REP #$30   ; change 16bit mode
  LDX #$001E

  .loop
  LDA.l deku_palette, X : STA $7EC6E0, X
  DEX : DEX : BPL .loop

  SEP #$30 ; go back to 8 bit mode
  INC $15  ; update the palette
  RTL      ; or RTS depending on where you need it
}

deku_palette:
  dw #$6739, #$15C5, #$150E, #$26C9, #$17AA, #$21F4, #$17DF, #$42DB
  dw #$14A5, #$14BC, #$14B2, #$14A5, #$7FFF, #$7A18, #$178C

print "End of Masks/deku_mask.asm        ", pc

; =========================================================

org $07A64B           ; formerly Quake
LinkItem_DekuMask:
{
  ; Don't use magic unless deku form
  LDA.w $02B2 : CMP.b #$01 : BNE .continue
    ; Don't shoot while transform is active
    LDA.w $0C4E : BNE .continue 
      JSR Link_CheckNewY_ButtonPress : BCC .continue
        LDA $3A : AND.b #$BF : STA $3A
        LDX.b #$02
        JSR LinkItem_EvaluateMagicCost : BCC .return
          JSL DekuLink_ShootBubbleOrStartHover
          RTS

  .continue
  ; Don't transform while shooting
  LDA.w $0C52 : CMP.b #$0E : BEQ .return
    LDA.b #$01
    JSL Link_TransformMask
  .return
  RTS
}

warnpc $07A6BE

; =========================================================

Link_HandleChangeInZVelocity = $078926
Link_HandleChangeInZVelocity_preset =  $078932

PlaySFX_Set2 = $078028
PlaySFX_Set3 = $07802F

org $07A6BE
LinkState_UsingQuake:
{
  .anim_step
    db #$00, #$01, #$02, #$03
    db #$00, #$01, #$02, #$03
    db #$10, #$10, #$00, #$00 ; 16

  .anim_timer
    db   5,   5,   5,   5
    db   5,   5,   5,   5
    db   5,   5,   5,  19

  JSR $F514 ; CacheCameraPropertiesIfOutdoors

  STZ.b $27 : STZ.b $28 ; Reset recoil X and Y 

  ; SPIN STEP CHECK
  LDA.w LinkSpinStep : CMP.b #$0A : BNE .not_ascending
    LDA.w $0362 : STA.b $29
    LDA.w $0363 : STA.w $02C7
    LDA.w $0364 : STA.b $24

    LDA.b #$02 : STA.b $00 : STA.b $4D

    JSR Link_HandleChangeInZVelocity_preset
    JSL LinkHop_FindArbitraryLandingSpot

    ; Link recoil Z value, hop Z value 
    LDA.b LinkRecoilZ : STA.w $0362
    LDA.w $02C7 : STA.w $0363

    ; Z Position of Link
    LDA.b $24 : STA.w $0364 : BMI .still_ascending

      ; End of ASCEND -------------------------------------
      LDY.b #$00 : LDA.b LinkRecoilZ : BPL .done_ascending
        LDY.b #$00 ; Thrust Sword Down OAM Frame Set

      .done_ascending
        STY.w $031C : BRA .exit
      ; ---------------------------------------------------

  .not_ascending
    DEC.b $3D : BPL .special

    .still_ascending
    INC.w LinkSpinStep
    LDX.w LinkSpinStep 
    CPX.b #$04 : BNE .skip_swish_sfx
      PHX : LDA.b #$23 : JSR PlaySFX_Set3 : PLX
    .skip_swish_sfx
    CPX.b #$0C : BNE .dont_reset_step
      LDA.b #$0B : STA.w LinkSpinStep
      TAX
    .dont_reset_step
    LDA.w .anim_timer,X : STA.b $3D
    LDA.w .anim_step,X : STA.w $031C
    
    LDA.w $0324 : BNE .special ; Prevent repeat spellcast check
    CPX.b #$0B : BNE .special ; Animation step check

      ; -------------------------------------------------
      ; Prevent repeat spellcast set
      LDA.b #$01 : STA.w $0324
      LDA.b #$12 : STA LinkZ
      LDA.b #$FF : STA FallTimer
      LDA.b #$01 : STA DekuFloating
      ; -------------------------------------------------

  .exit
  RTS

  .special
  LDA.b DekuFloating : BEQ +
    DEC $5C 
    JSL DekuLink_HoverBasedOnInput
  +
  RTS
}

warnpc $07A779

; LinkHop_FindArbitraryLandingSpot
; Allow LinkState 0x0A to use velocity
; Previously would skip velocity for LinkState 0x0A
org $07E38B
  LDA.b $5D : CMP.b #$09