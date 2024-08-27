; =========================================================
; Room tag to initialize the game without the Uncle sprite.
; 

StoryState = $7C

org $01CC18 ; override routine 0x39 "Holes(7)"
  JML HouseTag

org $01CC5A 
  HouseTag_Return:

pullpc
HouseTag:
{
  PHX 
  ; -------------------------------
  LDA $7EF3C6 : BNE .game_has_begun
  JSR HouseTag_Main
.game_has_begun
  ; -------------------------------
  PLX
  JML HouseTag_Return
}

; =========================================================

HouseTag_Main:
{
  LDA StoryState

  JSL $008781
  
  dw HouseTag_TelepathicPlea
  dw HouseTag_WakeUpPlayer
  dw HouseTag_End
}

; =========================================================

HouseTag_TelepathicPlea:
{
  LDA #$08 : STA $7EE000 ; Set the time to 8:00am

  ; -------------------------------
  ; Set Link's coordinates to this specific position.
  LDA.b #$40 : STA $0FC2
  LDA.b #$09 : STA $0FC3
  
  LDA.b #$5A : STA $0FC4
  LDA.b #$21 : STA $0FC5
      
  ; "Accept our quest, Link!"
  LDA.b #$1F : LDY.b #$00
  JSL $05E219 ; Sprite_ShowMessageUnconditional
  INC.b StoryState

  RTS
}

; =========================================================

HouseTag_WakeUpPlayer:
{
  ; Lighten the screen gradually and then wake Link up partially
  LDA $1A : AND.b #$03 : BNE .delay
  LDA $9C : CMP.b #$00 : BEQ .colorTargetReached
  
  DEC $9C : DEC $9D

.delay
  RTS

.colorTargetReached

  INC $0D80, X
  
  INC $037D
  INC $037C
  
  LDA.b #$57 : STA $20
  LDA.b #$21 : STA $21
  
  ;LDA.b #$01 : STA $02E4

  STZ $02E4 ; awake from slumber
  INC.b StoryState 

  ; Make it so Link's uncle never respawns in the house again.
  LDA $7EF3C6 : ORA.b #$10 : STA $7EF3C6

  ; Set the game mode
  LDA #$00 : STA $7EF3C5   ; (0 - intro, 1 - pendants, 2 - crystals)
  LDA #$00 : STA $7EF3CC   ; disable telepathic message
  JSL Sprite_LoadGfxProperties
  
  RTS
}

; =========================================================

HouseTag_End:
{
  LDA $B6 : BNE .hasMetFarore
  LDA #$00 : STA StoryState
  
.hasMetFarore
  RTS
}

print  "End of house_tag.asm              ", pc

pushpc

; =========================================================
; Fixed color fade-in effect
; TODO: Investigate if this is the best way to fix this.

org $028364
{
  #_028364: LDA.b #$00 ; Fixed color RGB: #808000
  #_028366: STA.b $9C

  #_028368: LDA.b #$00
  #_02836A: STA.b $9D

  #_02836C: LDA.b #$00
  #_02836E: STA.b $9E
  #_028370: LDA.b #$00
  #_028372: STA.l $7EC005
  #_028376: STA.l $7EC006

  #_02837A: JSL $079A2C ; Link_TuckIntoBed
}

; =========================================================
; Dying Uncle Code Hook
; Uncle won't remove tagalong when interacting 

org $05DF3A
LDA.b #$01 : STA $7EF3CC

; =========================================================
; SRM Start Modifier
; Credit: Conn, Euclid, MathOnNapkins

org $0cdc5a
JSR $ffb1

org $0cffb1
; =========================================================
;$3C5: $00: Unset, Will put Link in his bed state at the beginning of the game. (Also can't use sword or shield)
;      $01: Start in the castle on start up.
;      $02: Indicates you have completed the first Hyrule Castle dungeon.
;      $03: Indicates you have beaten Agahnim and are now searching for crystals.
;      $04 and above: meaningless. Though, you could write code using them to expand the event system perhaps.

;$3C6: Progress Flags (bitwise)
;    00 - Set after your Uncle gives you his gear in the secret passage. Prevents him from showing up there again.
;    01 - Indicates that you've touched the dying priest in Sanctuary.
;    02 - Set after you bring Zelda to sanctuary?
;    03 - Unused? (98% certainty)
;    04 - Set after Link's Uncle leaves your house. It's used to prevent him from respawning there.  
;    05 - Set after you obtain the Book of Mudora (this is a guess)
;    06 - Seems to be a persistent flag that toggles between two possible statements that a fortune teller can give you during your "reading".
;         In other words, don't expect this to stay in one state if you're using fortune tellers. Has no other known purpose.
;    07 - Unused? (98% certainty)
;    10 - Start value (in house, bed)
LDA #$0000     
STA $7003C5,x

; =========================================================
;$3C7: Map Icons Indicator 2 (value, not bitwise)
;    00 - start value (cross at Hyrule Castle)
;    01 - cross at Sahasrala's house
;    02 - cross at ruins
;    03 - The Three Pendants
;    04 - Master Sword in Lost Woods
;    05 - Agahnim (skull icon at Hyrule Castle)
;    06 - Just crystal 1 shown (Sahasrala's idea)
;    07 - All crystals shown
;    08 - Agahnim (skull icon at Ganon's Tower)
;    All values beyond 8 are invalid, it seems.

;$3C8: Starting Entrance to use. Abbreviations: LH = Link's House - SA = Sanctuary - MC = Mountain Cave - PP = Pyramid of Power in DW  
;    00 - Start the game in Link's house always.
;    01 - SA.
;    03 - Secret passage under HC garden (near dying uncle).
;    05 - LH or SA or MC.
LDA #$0000   
STA $7003C7,x

; =========================================================
;$359: Sword you start with
;    00 - No sword
;    01 - Fighter Sword
;    02 - Master Sword
;    03 - Tempered Sword
;    04 - Golden Sword

;$35A: Shield you start with
;     00 - No shield
;     01 - Blue Shield
;     02 - Hero's Shield
;     03 - Mirror Shield  
LDA #$0000      ; 01=sword,  02 = shield to start with
STA $700359,x   

LDY #$0000
RTS