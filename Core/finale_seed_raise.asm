; =========================================================
; Finale: Link raises the Maku Seed in the Triforce room.
;
; Canon (decisions.org "DECIDED Maku Seed ending"): after Ganon, Link holds the
; Maku Seed up (item-raise pose) before the credits.
;
; Module19_0C_HoldTriforce counts $C8 down while Link holds the Triforce with
; both hands ($02DA = 2). When that count is about to end, this switches Link to
; the one-hand item-raise pose ($02DA = 1), loads the seed tiles into the
; held-item VRAM slot (chars $24/$25/$34/$35, uploaded by NMI from $7EBD40 and
; $7EBD80 every frame) and restarts $C8. The seed is drawn above Link until the
; vanilla white fade (Module19_0D) ends.
;
; Seed art: Items/gfx/magic_bean.bin tiles 0,1 (top) and 8,9 (bottom).
; Included from Sprites/Bosses/ganondorf.asm (bank $2A).

!FinaleSeed_RaiseFrames = $A0
!FinaleSeed_Oam         = $09F0        ; OAM slot 124
!FinaleSeed_OamHigh     = $0A20+124
!FinaleSeed_Char        = $24
!FinaleSeed_Props       = $3C          ; priority 3, palette 6, name table 0
!FinaleSeed_PalRow      = $01C0        ; sprite palette 6 offset in the CGRAM buffers
!FinaleSeed_LiftUntil   = !FinaleSeed_RaiseFrames-$30 ; $C8 where the Triforce lift reaches 24 px

; Replaces `JSL AdvancePolyhedral` in Module19_0C_HoldTriforce. M=8, X=8.
FinaleSeed_HoldStep:
{
  JSL $0CCAB1 ; AdvancePolyhedral
  LDA.w $02DA : CMP.b #$01 : BEQ .draw
    ; Vanilla runs DEC $C8 : BNE after this; $C8 = 1 is its last hold frame.
    LDA.b $C8 : CMP.b #$01 : BNE .exit
      LDA.b #$01 : STA.w $02DA
      LDA.b #!FinaleSeed_RaiseFrames+1 : STA.b $C8
      JSR FinaleSeed_LoadTiles
  .draw
  JSR FinaleSeed_LiftTriforce
  JSR FinaleSeed_Draw
  .exit
  RTL
}

; The Triforce here is three scene sprites (type 4-6) drawn right above Link.
; Once stopped, vanilla resets each one's Y to a fixed table every frame (after
; drawing it). Rewrite that Y as table - lift, so the next draw is higher. The
; lift eases from 0 to 24 px over the first $30 seed frames, then holds.
FinaleSeed_LiftTriforce:
{
  LDA.w $1E00 : CMP.b #$03 : BCC .exit          ; triangles not stopped yet
  LDA.b $C8 : CMP.b #!FinaleSeed_LiftUntil+1 : BCC .full
    LDA.b #!FinaleSeed_RaiseFrames+1 : SEC : SBC.b $C8 : LSR A
    BRA .have
  .full
  LDA.b #$18
  .have
  STA.b $00
  LDX.b #$02
  .next
    LDA.w $1E18, X : CMP.b #$04 : BCC .skip
    CMP.b #$07 : BCS .skip
      LDA.l $0CCC8C, X : SEC : SBC.b $00 : STA.w $1E48, X  ; Stopped .position_y
    .skip
    DEX : BPL .next
  .exit
  RTS
}

; Replaces `JSL AdvancePolyhedral` in Module19_0D_FadeToWhite. M=8, X=8.
FinaleSeed_FadeStep:
{
  JSL $0CCAB1 ; AdvancePolyhedral
  LDA.w $02DA : CMP.b #$01 : BNE .exit
    JSR FinaleSeed_LiftTriforce
    JSR FinaleSeed_Draw
  .exit
  RTL
}

FinaleSeed_LoadTiles:
{
  REP #$30
  LDX.w #$003E
  .copy
    LDA.l MagicBeanGfx+$000, X : STA.l $7EBD40, X
    LDA.l MagicBeanGfx+$100, X : STA.l $7EBD80, X
    DEX : DEX : BPL .copy
  ; Seed colors (brown seed) into sprite palette 6 (unused in this room). Both buffers, so the
  ; vanilla white fade (it moves $7EC500 toward $7EC300) keeps them.
  LDX.w #$000E
  .pal
    LDA.l FinaleSeed_Palette, X
    STA.l $7EC300+!FinaleSeed_PalRow, X
    STA.l $7EC500+!FinaleSeed_PalRow, X
    DEX : DEX : BPL .pal
  SEP #$30
  INC.b $15
  RTS
}

; Colors 0-7 of the seed palette (BGR555). 5 outline, 6 rim, 7 body, 1-4 shine.
FinaleSeed_Palette:
  dw $0000, $7FFF, $4F3D, $3A99, $639E, $0887, $194F, $25F5 ; f8f8f8 e8c898 c8a070 f0e0c0 382010 785030 a87848

; Seed sits where an item-receipt ancilla does: Link X, Link Y - 14.
FinaleSeed_Draw:
{
  REP #$20
  LDA.b $22 : SEC : SBC.b $E2 : STA.b $00
  LDA.b $20 : SEC : SBC.b $E8 : SEC : SBC.w #$000E : STA.b $02
  SEP #$20
  LDA.b $00 : STA.w !FinaleSeed_Oam+0
  LDA.b $02 : STA.w !FinaleSeed_Oam+1
  LDA.b #!FinaleSeed_Char : STA.w !FinaleSeed_Oam+2
  LDA.b #!FinaleSeed_Props : STA.w !FinaleSeed_Oam+3
  LDA.b #$02 : STA.w !FinaleSeed_OamHigh
  RTS
}

pushpc
org $02A164 ; @hook module=Sprites name=FinaleSeed_HoldStep kind=jsl target=FinaleSeed_HoldStep expected_m=8 expected_x=8
  JSL FinaleSeed_HoldStep
  assert pc() == $02A168
org $02A173 ; @hook module=Sprites name=FinaleSeed_FadeStep kind=jsl target=FinaleSeed_FadeStep expected_m=8 expected_x=8
  JSL FinaleSeed_FadeStep
  assert pc() == $02A177
pullpc
