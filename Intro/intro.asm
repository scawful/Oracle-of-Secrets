;===========================================================
; Intro
; game will Switch to part 1 after your uncle left the house
;===========================================================

namespace Intro 
{
  Main: 
  {
    lorom

    ORG $05DF12
    JSL $04ECA0
    NOP
    NOP

    org $04ECA0
    STZ $0DD0,x
    STZ $02E4     ; repeat native code overwritten by hook
    LDA #$02
    STA $7ef3C5   ; store "part 2"
    LDA #$00
    STA $7ef3CC   ; disable telepathic message
    JSL $00FC41   ; fix monsters
    RTL
  }  ; label Main

  Items: 
  {
    ; SRM Start Modyfier
    ; This ASM was written by Euclid, modified by Conn; thanks to MoN for his banks research
    ; This is a ASM FrontEnd Code for Zelda ALTTP (US, no header) to modify the sram on startup
    ; the values are included to better distinguish where is what. You need to set your own values. Description at the end.

    lorom

    org $0cdc5a
    jsr $ffb1

    org $0cffb1

    LDA #$0000     
    STA $7003C5,x

    LDA #$0000   
    STA $7003C7,x

    LDA #$0101      ; 01=sword,  02 = shield to start with        
    STA $700359,x   ; sword/shield save

    LDY #$0000              
    RTS


    ;---------------------------------------------------------
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
            
    ;$359: Sword you start with
    ;    00 - No sword
    ;    01 - Fighter Sword
    ;    02 - Master Sword
    ;    03 - Tempered Sword
    ;    04 - Golden Sword

    ;$35A: Shield you start with           .      
    ;     00 - No shield
    ;     01 - Blue Shield
    ;     02 - Hero's Shield
    ;     03 - Mirror Shield  
  }
}  ; namespace Intro
