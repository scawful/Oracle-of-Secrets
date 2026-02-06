; This file contains all direct patches to the original ROM.
; It is included from Oracle_main.asm.

; UnderworldTransition_ScrollRoom
org $02BE5E : JSL Graphics_Transfer ; @hook module=Core name=Graphics_Transfer kind=jsl target=Graphics_Transfer

; Whirlpool
org $1EEEE4 : JSL DontTeleportWithoutFlippers ; @hook module=Core name=DontTeleportWithoutFlippers kind=jsl target=DontTeleportWithoutFlippers

; SpriteDraw_Roller
org $058EE6 : JSL PutRollerBeneathLink ; @hook module=Core name=PutRollerBeneathLink kind=jsl target=PutRollerBeneathLink

; =========================================================

; Sprite Recoil and Death
; TODO: Sprite_AttemptKillingOfKin
; Kydreeok Head die like Sidenexx
org $06F003 : CMP.b #$CF

; Remove sidenexx death from booki
org $06EFFF : NOP #4

; Make Dark Link die like sidenexx
org $06F003 : CMP.b #$C1

; Make Helmet ChuChu recoil link
org $06F37D : CMP.b #$05

; Make Kydreeok head recoil Link
org $06F381 : CMP.b #$CF

; =========================================================

InCutScene = $7EF303

; Player2JoypadReturn
org $0083F8 ; @hook module=Core name=Player2JoypadReturn_InputClamp kind=patch
  LDA InCutScene : BEQ .notInCutscene
    STZ $F0
    STZ $F2
    STZ $F4
    STZ $F6
    STZ $F8
    STZ $FA ; kill all input
  .notInCutscene
  RTS

assert pc() <= $00841E

; =========================================================

org $1EF27D ; @hook module=Core
ShopItem_Banana:
{
  JSR $F4CE   ; SpriteDraw_ShopItem
  JSR $FE78   ; Sprite_CheckIfActive_Bank1E
  JSL $1EF4F3 ; Sprite_BehaveAsBarrier
  JSR $F391   ; ShopItem_CheckForAPress
  BCC .exit

    LDA.l Bananas : CMP.b #$0A : BCS .error
    LDA.b #$1E : LDY.b #$00
    JSR $F39E ; ShopItem_HandleCost
    BCC .error

    STZ.w SprState,X
    INC.b Bananas

    LDY.b #$42 : JSR $F366 ; ShopItem_HandleReceipt

  .exit
  RTS
  .error
  JSR $F1A1 ; ShopItem_GiveFailureMessage
}
assert pc() <= $1EF2AB

; =========================================================

; Shop item heart OAM
; SpriteDraw_ShopItem
org $1EF42E
  dw  -4,  16 : db $03, $02, $00, $00 ; 3
  dw  -4,  16 : db $03, $02, $00, $00 ; 3
  dw   4,  16 : db $30, $02, $00, $00 ; 0
  dw   0,   0 : db $E5, $03, $00, $02 ; item
  dw   4,  11 : db $38, $03, $00, $00 ; shadow

; =========================================================

; Octoballoon_FormBabby
; Reduce by half the number of babies spawned
org $06D814 : LDA.b #$02

; SpritePrep_HauntedGroveOstritch
org $068BB2 : NOP #11

; HauntedGroveRabbit_Idle
org $1E9A8F : NOP #5

; MedallionTablet (Goron)
org $05F274 : LDA.l $7EF378 ; Unused SRAM

org $08C2E3 : dw $006F ; BUTTER SWORD DIALOGUE

; Fix the capital 'B' debug item cheat.
org $0CDC26 : db $80 ; replace a $F0 (BEQ) with a $80 (BRA).

; Update Catfish Item Get to Bottle
org $1DE184 : LDA.b #$16 : STA.w $0D90, X

; Follower_Disable
; Don't disable Kiki so we can switch maps with him.
org $09ACF3 : LDA.l $7EF3CC : CMP.b #$0E

; Kiki, don't care if we're not in dark world
org $099FEB : LDA.b $8A : AND.b #$FF

org $1EE48E : NOP #6

; Kiki activate cutscene 3 (tail palace)
org $1EE630 : LDA.b #$03 : STA.w $04C6

; Kid at ranch checks for flute
org $05FF7D : LDA.l $7EF34C : CMP.b #$01

; Raven Damage (LW/DW)
org $068963 : db $81, $84

; Running Man draw palette
org $05E9CD
SpriteDraw_RunningBoy:
  #_05E9CD: dw   0,  -8 : db $2C, $00, $00, $02
  #_05E9D5: dw   0,   0 : db $EE, $0E, $00, $02

  #_05E9DD: dw   0,  -7 : db $2C, $00, $00, $02
  #_05E9E5: dw   0,   1 : db $EE, $4E, $00, $02

  #_05E9ED: dw   0,  -8 : db $2A, $00, $00, $02
  #_05E9F5: dw   0,   0 : db $CA, $0E, $00, $02

  #_05E9FD: dw   0,  -7 : db $2A, $00, $00, $02
  #_05EA05: dw   0,   1 : db $CA, $4E, $00, $02

  #_05EA0D: dw   0,  -8 : db $2E, $00, $00, $02
  #_05EA15: dw   0,   0 : db $CC, $0E, $00, $02

  #_05EA1D: dw   0,  -7 : db $2E, $00, $00, $02
  #_05EA25: dw   0,   1 : db $CE, $0E, $00, $02

  #_05EA2D: dw   0,  -8 : db $2E, $40, $00, $02
  #_05EA35: dw   0,   0 : db $CC, $4E, $00, $02

  #_05EA3D: dw   0,  -7 : db $2E, $40, $00, $02
  #_05EA45: dw   0,   1 : db $CE, $4E, $00, $02

; Sword Barrier Sprite Prep
; Skip overworld flag check, sprite is indoors now
org $06891B : NOP #12

; (SPC upload timeout hook removed – revert to vanilla handshake)
