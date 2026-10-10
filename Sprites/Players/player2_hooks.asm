; =========================================================
; Native 2-player PoC hooks (Sprites/Players/player2.asm).
; Included only when !ENABLE_NATIVE_2P_POC == 1.
;
; Util/item_cheat.asm (disabled) also patches $068365; do not enable both.
; =========================================================

pushpc

; Sprite_Main: JSL Follower_Main -> P2_Tick (tail-jumps to Follower_Main)
org $068365 ; @hook module=Sprites name=P2_Tick kind=jsl target=P2_Tick
  JSL P2_Tick

; NMI_DoUpdates.no_update_swagduck: LDX $0ADC : STX $4302 -> P2_NmiUpload
; (replays both). Goldstar's MaybeUploadBirdGraphicsToOam also lands here.
org $008B50 ; @hook module=Sprites name=P2_NmiUpload kind=jsl target=P2_NmiUpload
  JSL P2_NmiUpload : NOP #2

; Sprite_CheckDamageFromLink: LDA $44 : CMP #$80 -> JSL P2_ActionGate. The
; following BEQ .no_collision ($06F2C6) is untouched. P2's punch reaches every
; enemy through the check it already makes for Link's sword.
org $06F2C2 ; @hook module=Sprites name=P2_ActionGate kind=jsl target=P2_ActionGate
  JSL P2_ActionGate

; Sprite_CheckDamageToLink.collision_checked: LDA $0E40,X : BMI : BCC ->
; JSL P2_ContactGate : BCC .no_damage2 : NOP. Enemies that touch P2 (and not
; Link) cost the shared hearts.
P2_ContactNoDamage = $06F1D7                   ; Sprite_CheckDamageToLink .no_damage2
org $06F16F ; @hook module=Sprites name=P2_ContactGate kind=jsl target=P2_ContactGate
  JSL P2_ContactGate
  BCC P2_ContactNoDamage
  NOP

pullpc
