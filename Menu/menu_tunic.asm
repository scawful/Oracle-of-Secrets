; Worn tunic colour, picked on the Equipment page (GEAR slot 26).
; scawful 2026-11-16: "1 Wear what you own" (green always, blue with Blue
; Mail, red with Red Mail); names GREEN/BLUE/RED TUNIC, label "ARMOR n".
; Armor ($7EF35B) keeps meaning defense; damage code still reads it.
; SwordSlotFlags bits 3-5 hold the choice: 0 follow Armor (new files and
; old saves), 1-3 = green/blue/red. A choice above Armor, or bit7 clear
; (save not yet synced), follows Armor. Receiving a mail clears the choice,
; so the item-get still changes Link. Assembled in Items bank $2B.

; A = worn colour (0 green, 1 blue, 2 red). <flags>/<armor> are long
; addresses (WRAM or a file-select SRAM slot). M=8. Clobbers flags.
macro Tunic_Resolve(flags, armor)
  LDA.l <flags> : BPL +
  AND.b #!SwordSlot_TunicMask : BEQ +
  LSR #3 : DEC : CMP.l <armor> : BCC ++ : BEQ ++
+
  LDA.l <armor>
++
endmacro

; Long. Returns A = worn colour, high byte 0, in the caller's A width.
; Keeps X/Y and P (N/Z are the caller's: do not branch on them).
Tunic_GetWorn:
{
  PHP : SEP #$20
  %Tunic_Resolve(SwordSlotFlags, Armor)
  REP #$20 : AND.w #$00FF
  PLP
  RTL
}

; File select reads each SRAM slot's mail byte at a fixed address.
; Slot N = $700000 + (N-1)*$500 + the $7EF000 offset. A is 16-bit there.
Tunic_FileSelectSlot1:
  PHP : SEP #$20
  %Tunic_Resolve($7003BD, $70035B)
  BRA Tunic_FileSelectReturn
Tunic_FileSelectSlot2:
  PHP : SEP #$20
  %Tunic_Resolve($7008BD, $70085B)
  BRA Tunic_FileSelectReturn
Tunic_FileSelectSlot3:
  PHP : SEP #$20
  %Tunic_Resolve($700DBD, $700D5B)
Tunic_FileSelectReturn:
  REP #$20 : AND.w #$00FF
  PLP
  RTL

; Tunic icon variant: worn+1 (1 green, 2 blue, 3 red), 0 when Armor is not
; 0-2. M=8; keeps X/Y.
Tunic_WornVariant:
{
  LDA.l Armor : CMP.b #$03 : BCS .none
  JSL Tunic_GetWorn : INC
  RTL
.none
  LDA.b #$00
  RTL
}

; Equipment slot 26: a cursor stop only with two or more colours owned
; (Armor 1 or 2). Returns the icon variant or 0. M/X=8; keeps X/Y.
Tunic_StopVariant:
{
  LDA.l Armor : DEC : CMP.b #$02 : BCS .none
  JMP Tunic_WornVariant
.none
  LDA.b #$00
  RTL
}

; A on slot 26: the next owned colour, wrapping to green. Recolours Link
; now in the forms that show the tunic (base, Minish, GBC, horse); the
; other forms load their own palettes. Player 2 recolours at its next
; graphics reload. M/X=8.
Tunic_Cycle:
{
  JSL Tunic_GetWorn : INC
  CMP.l Armor : BCC + : BEQ +
  LDA.b #$00
+
  INC : ASL #3 : PHA                  ; field = colour+1
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_TunicMask^$FF
  ORA.b $01,S : STA.l SwordSlotFlags
  PLA
  LDA.w !CurrentMask : BEQ .reload
  CMP.b #$05 : BEQ .reload            ; Minish
  CMP.b #$06 : BEQ .reload            ; GBC
  CMP.b #$09 : BNE .done              ; horse
.reload
  JSL $1BEDF9                         ; Palette_ArmorAndGloves (mask-aware)
  SEP #$30
  INC.b $15
.done
  RTL
}

; Vanilla mail receipt ($08C4DC, Blue/Red Mail) reloads Link's palette:
; drop the worn choice first so the new mail shows. Tail-calls the loader.
Tunic_OnMailReceipt:
{
  PHP : SEP #$20
  LDA.l SwordSlotFlags : AND.b #!SwordSlot_TunicMask^$FF : STA.l SwordSlotFlags
  PLP
  JML $1BEDF9
}

; "ARMOR n" right-aligned on the GEAR label row: defense, not the colour.
; Called from SwordSlots_MarkerSlot. Returns M/X=8; clobbers A/X.
!TUNIC_ARMOR_LABEL_POS = menu_offset(9,20)
Tunic_DrawArmorLabel:
{
  REP #$30
  LDX.w #$000A
.loop
  LDA.l .text,X : STA.l $7E1000+!TUNIC_ARMOR_LABEL_POS,X
  DEX #2 : BPL .loop
  LDA.l Armor : AND.w #$00FF : CLC : ADC.w #$2570 ; menu font '0'
  STA.l $7E1000+!TUNIC_ARMOR_LABEL_POS+12
  SEP #$30
  RTL
.text
  pushtable
  'A' = $2550
  'M' = $255C
  'O' = $255E
  'R' = $2561
  '_' = $20F5
  dw "ARMOR_"
  pulltable
}

pushpc
; Link's mail palette in vanilla refreshes (6 callers). A is 16-bit; the
; following AND.w #$00FF stays.
org $0ED6C8 ; @hook module=Menu name=Tunic_GetWorn kind=jsl target=Tunic_GetWorn expected_m=16 protected_size=4
  JSL Tunic_GetWorn
; File select Link colour per slot. A is 16-bit; JSR to the armor loader follows.
org $1BEFA6 ; @hook module=Menu name=Tunic_FileSelectSlot1 kind=jsl target=Tunic_FileSelectSlot1 expected_m=16 expected_x=16 protected_size=4
  JSL Tunic_FileSelectSlot1
org $1BEFCA ; @hook module=Menu name=Tunic_FileSelectSlot2 kind=jsl target=Tunic_FileSelectSlot2 expected_m=16 expected_x=16 protected_size=4
  JSL Tunic_FileSelectSlot2
org $1BEFEE ; @hook module=Menu name=Tunic_FileSelectSlot3 kind=jsl target=Tunic_FileSelectSlot3 expected_m=16 expected_x=16 protected_size=4
  JSL Tunic_FileSelectSlot3
; Blue/Red Mail receipt: JSL Palettes_Load_LinkArmorAndGloves.
org $08C4DC ; @hook module=Menu name=Tunic_OnMailReceipt kind=jsl target=Tunic_OnMailReceipt protected_size=4
  JSL Tunic_OnMailReceipt
pullpc
