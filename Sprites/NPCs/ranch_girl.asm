; =========================================================
; Ranch Girl (Chicken Lady / Ocarina Quest)
;
; NARRATIVE ROLE: Toto Ranch girl, cursed into a Cucco by Twinrova.
;   Magic Powder reveals her briefly; she gives the Ocarina and names the
;   Mask Salesman (beat 10). The curse lifts when Twinrova falls (D5).
;   Canon: decisions.org ("Beat sheet crux 7").
;
; TERMINOLOGY: "Ranch Girl" = RanchGirl / ChickenLady
;   - Appears when Magic Powder hits the cursed Cucco
;   - Gives Ocarina (item 0x14)
;   - $7EF34C = 1 after receiving Ocarina (no songs yet)
;
; TECHNICAL NOTE: This sprite hooks into the existing ChickenLady
;   sprite at ROM address $1AFECF, extending vanilla ALTTP behavior.
;
; BEHAVIOR:
;   1. SprTimerA = 1 triggers message display
;   2. First visit: Show message 0x1BE, set SprMiscD = 1
;   3. SprMiscD = 1: Give Ocarina
;   4. Subsequent visits: Show message 0x10E
;
; MESSAGES:
;   0x1BE - First meeting (powder reveal, gives Ocarina, names the Mask
;           Salesman); replaces vanilla 0x17D, whose longer text does not
;           fit vanilla text region 2
;   0x10E - Already has Ocarina (curse reminder)
;   0x187/0x188/0x189/0x18B, 0x033 - Toto Ranch milk sale on later visits
;           (!ENABLE_RANCH_MILK; BottleMan's texts, replaces 0x10E)
;
; FLAGS WRITTEN:
;   SideQuestProg2 |= 0x01 - Ranch Girl revealed (Ocarina given)
;   $7EF34C = 1 - Ocarina obtained (Lv1)
;   SideQuestProg2 |= !SideQuest2_EponaSong - Epona's Song (!ENABLE_EPONA_SONG;
;     with the Ocarina, or on a later talk for saves that predate it)
;   MapIcon = !MapIcon_TailPond - Tail Pond objective (beat 10; moved here
;     from the Village Elder, dialogue audit D3)
;
; FLAGS READ:
;   $7EF34C - Check if already has Ocarina
;
; ITEMS GIVEN:
;   0x14 - Ocarina
;
; RELATED:
;   - mask_salesman.asm (requires Ocarina to proceed)
;   - vanilla ChickenLady ($1AFECF), Magic Powder trigger
;
; ROM HOOKS:
;   $1AFECF - ChickenLady main hook
;   $1AFEFF - End of hook space
; =========================================================

Sprite_ShowMessageMinimal = $05FA8E
; SpriteDraw_RaceGameLady already defined in windmill_guy.asm
Sprite_CheckIfActive_Bank1A = $1AF954

RanchGirl_Message:
{
  LDA $7EF34C : CMP.b #$01 : BCS .has_ocarina
    ; Set journal flag: Ranch Girl revealed (curse lifts at D5)
    LDA.l SideQuestProg2 : ORA.b #$01 : STA.l SideQuestProg2
    %ShowUnconditionalMessage($01BE)
    LDA #$01 : STA.w SprMiscD, X
    RTL
  .has_ocarina
if !ENABLE_EPONA_SONG == 1
  ; Saves that got the Ocarina before Epona's Song existed learn it here.
  LDA.l SideQuestProg2 : AND.b #!SideQuest2_EponaSong : BNE .knows_epona
    LDA.l SideQuestProg2 : ORA.b #!SideQuest2_EponaSong : STA.l SideQuestProg2
    LDA.b #$13 : STA.w $0CF8
    JSL $0DBB67 ; Link_CalculateSFXPan
    ORA.w $0CF8
    STA.w $012E ; song learned sound
  .knows_epona
endif
if !ENABLE_RANCH_MILK == 1
  ; Later visits: Toto Ranch milk for 30 Rupees (BottleMan offer $187,
  ; Buy/Reject). RanchGirl_TeachSong finishes the sale once the box closes.
  %ShowUnconditionalMessage($0187)
  LDA.b #$02 : STA.w SprMiscD, X
  RTL
else
  %ShowUnconditionalMessage($010E)
  RTL
endif
}

RanchGirl_TeachSong:
{
if !ENABLE_RANCH_MILK == 1
  LDA.w SprMiscD, X : CMP.b #$02 : BNE .no_sale
  LDA $10 : CMP.b #$0E : BEQ .running_dialog   ; offer still on screen
    STZ.w SprMiscD, X
    JSL RanchGirl_SellMilk_Long     ; Sprites/NPCs/ranch_milk.asm (bank $30)
    BRA .running_dialog
  .no_sale
endif
  LDA.w SprMiscD, X : CMP.b #$01 : BNE .not_started
  LDA $10 : CMP.b #$0E : BEQ .running_dialog
  LDA $7EF34C : CMP.b #$01 : BCS .has_song

  ; Give Link the Ocarina
  LDY #$14
  ; Clear the item receipt ID
  STZ $02E9
  PHX
  JSL Link_ReceiveItem
  PLX

  LDA #$01 : STA $7EF34C ; Ocarina only (no songs yet)
if !ENABLE_EPONA_SONG == 1
  ; Epona's Song comes with the Ocarina (song 6; the item fanfare plays).
  ; UpdateFluteSong_Long then selects it as the only learned song.
  LDA.l SideQuestProg2 : ORA.b #!SideQuest2_EponaSong : STA.l SideQuestProg2
endif
  ; Beat 10: the Tail Pond objective starts at the Ocarina receipt.
  LDA.b #!MapIcon_TailPond : STA.l MapIcon
  STZ $030F              ; Clear active song selection

  .not_started
  .running_dialog
  .has_song
  LDA.b $1A : LSR #4 : AND.b #$01 : STA.w $0DC0,X

  RTL
}

pushpc

org $1AFECF ; @hook module=Sprites
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
