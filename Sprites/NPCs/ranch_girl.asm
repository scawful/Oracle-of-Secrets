; =========================================================
; Ranch Girl (Chicken Lady / Ocarina Quest)
;
; NARRATIVE ROLE: Side quest NPC who gives Link the Ocarina and teaches
;   the Song of Storms. The "Chicken Easter Egg" refers to the Cucco
;   attack sequence that triggers her appearance. This is the prerequisite
;   for the Mask Salesman's Song of Healing quest.
;
; TERMINOLOGY: "Ranch Girl" = RanchGirl / ChickenLady
;   - Appears after Cucco attack sequence
;   - Gives Ocarina (item 0x14)
;   - Teaches Song of Storms (SFX 0x2F)
;   - $7EF34C = 1 after receiving Ocarina
;
; TECHNICAL NOTE: This sprite hooks into the existing ChickenLady
;   sprite at ROM address $1AFECF, extending vanilla ALTTP behavior.
;
; BEHAVIOR:
;   1. SprTimerA = 1 triggers message display
;   2. First visit: Show message 0x17D, set SprMiscD = 1
;   3. SprMiscD = 1: Play Song of Storms, give Ocarina
;   4. Subsequent visits: Show message 0x10E
;
; MESSAGES:
;   0x17D - First meeting (curse broken, teaches song)
;   0x10E - Already has Ocarina
;
; FLAGS WRITTEN:
;   SideQuestProg2 |= 0x01 - Ranch Girl transformed back
;   $7EF34C = 1 - Ocarina obtained (Lv1)
;
; FLAGS READ:
;   $7EF34C - Check if already has Ocarina
;
; ITEMS GIVEN:
;   0x14 - Ocarina
;
; RELATED:
;   - mask_salesman.asm (requires Ocarina to proceed)
;   - cucco.asm (triggers her appearance)
;
; ROM HOOKS:
;   $1AFECF - ChickenLady main hook
;   $1AFEFF - End of hook space
; =========================================================

Sprite_ShowMessageMinimal = $05FA8E
SpriteDraw_RaceGameLady =  $1AF92C
Sprite_CheckIfActive_Bank1A = $1AF954

RanchGirl_Message:
{
  LDA $7EF34C : CMP.b #$01 : BCS .has_ocarina
    ; Set journal flag: Ranch Girl transformed back (curse broken)
    LDA.l SideQuestProg2 : ORA.b #$01 : STA.l SideQuestProg2
    %ShowUnconditionalMessage($017D)
    LDA #$01 : STA.w SprMiscD, X
    RTL
  .has_ocarina
  %ShowUnconditionalMessage($010E)
  RTL
}

RanchGirl_TeachSong:
{
  LDA.w SprMiscD, X : CMP.b #$01 : BNE .not_started
  LDA $10 : CMP.b #$0E : BEQ .running_dialog
  LDA $7EF34C : CMP.b #$01 : BCS .has_song

  ; Play the song of storms
  LDA.b #$2F
  STA.w $0CF8
  JSL $0DBB67 ;  Link_CalculateSFXPan
  ORA.w $0CF8
  STA $012E ; Play the song learned sound

  ; Give Link the Ocarina
  LDY #$14
  ; Clear the item receipt ID
  STZ $02E9
  PHX
  JSL Link_ReceiveItem
  PLX

  LDA #$01 : STA $7EF34C ; The item gives 02 by default, so decrement that for now

  .not_started
  .running_dialog
  .has_song
  LDA.b $1A : LSR #4 : AND.b #$01 : STA.w $0DC0,X

  RTL
}

pushpc

org $1AFECF
ChickenLady:
{
  JSR .main
  RTL

  .main
  LDA.b #$01 : STA.w SprMiscC, X

  JSL SpriteDraw_RaceGameLady
  JSR Sprite_CheckIfActive_Bank1A

  LDA.w SprTimerA, X : CMP.b #$01 : BNE .no_message
    JSL RanchGirl_Message
  .no_message
  JSL RanchGirl_TeachSong
  .return
  RTS
}

assert pc() <= $1AFEFF
pullpc
