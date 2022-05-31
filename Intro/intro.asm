;===========================================================
; Intro
; 
; asm for no Header ALTTP US Rom
; game will Switch to part 1 after your uncle left the house
;===========================================================

namespace Intro 
{
  Main: {
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
}  ; namespace Intro
