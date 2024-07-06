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

; =========================================================

; Indicates somaria platform status.
;   0x00 - Not on platform
;   0x01 - On platform
;   0x02 - On platform and moving
SOMPLAT         = $7E02F5

org    $07A64B           ; formerly Quake
LinkItem_DekuMask:
{
  JSR Link_CheckNewY_ButtonPress : BCC .continue
    LDX.b #$01 
    JSR LinkItem_EvaluateMagicCost : BCC .return
      JSL PrepareQuakeSpell
      RTS

  .continue
  LDA.b #$01
  JSL Link_TransformMask : BCC .return
    LDA.b #$01 : STA.w SOMPLAT
    RTS
  .return
  STZ.w SOMPLAT
  RTS
}

warnpc $07A6BE

; =========================================================

org $07811A
  JSR Link_HandleDekuTransformation

pullpc ; Free space in bank07 - all_sprites.asm
Link_HandleDekuTransformation: 
{
  ; Check if using Quake Medallion
  LDA $5D : CMP.b #$0A : BEQ .continue

  .continue
  JSR $82DA ; Link_HandleBunnyTransformation

  RTS
}

print "End of Masks/deku_mask.asm        ", pc
pushpc


org $078926
  Link_HandleChangeInZVelocity:

org $078932
  Link_HandleChangeInZVelocity_preset:

org $078028
  PlaySFX_Set2:

org $07802F
  PlaySFX_Set3:

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
  LDA.w $031D : CMP.b #$0A : BNE .not_ascending
    LDA.w $0362 : STA.b $29
    LDA.w $0363 : STA.w $02C7
    LDA.w $0364 : STA.b $24

    LDA.b #$02 : STA.b $00 : STA.b $4D

    JSR Link_HandleChangeInZVelocity_preset
    JSL LinkHop_FindArbitraryLandingSpot

    ; Link recoil Z value, hop Z value 
    LDA.b $29 : STA.w $0362
    LDA.w $02C7 : STA.w $0363

    ; Z Position of Link
    LDA.b $24 : STA.w $0364 : BMI .still_ascending

    ; End of ASCEND -----------------------------------------
      ; Link recoil Z 
      LDY.b #$00 : LDA.b $29 : BPL .done_ascending

      LDY.b #$00 ; Thrust Sword Down OAM Frame Set

    .done_ascending
      STY.w $031C : BRA .exit
    ; -------------------------------------------------------

  .not_ascending
    DEC.b $3D : BPL .special

    .still_ascending
      INC.w $031D

      ; $031D - Spin Step
      LDX.w $031D : CPX.b #$04 : BNE .skip_swish_sfx
        PHX : LDA.b #$23 : JSR PlaySFX_Set3 : PLX
      .skip_swish_sfx
        CPX.b #$0C : BNE .dont_reset_step
        LDA.b #$0B : STA.w $031D

        TAX

        .dont_reset_step
          LDA.w .anim_timer,X : STA.b $3D
          LDA.w .anim_step,X : STA.w $031C
          
          LDA.w $0324 : BNE .special ; Prevent repeat spellcast check
          CPX.b #$0B : BNE .special ; Animation step check

            ; -----------------------------------------------------
            ; Prevent repeat spellcast set
            LDA.b #$01 : STA.w $0324
            LDA.b #$12 : STA $24
            LDA.b #$FF : STA $5C
            LDA.b #$01 : STA $70
            ; -----------------------------------------------------

.exit
  RTS

.special
  DEC $5C 
  JSL DekuLink_HoverBasedOnInput
  RTS
}

warnpc $07A779