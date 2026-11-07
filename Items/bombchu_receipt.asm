; Dedicated Bombchu receipt. $00-$4B remain the original ROM-backed rows;
; $4C is an additional row, never a reassignment of an existing reward.
;@source: usdasm banks00/06/07/08/09 item-receipt readers listed below.
; No chest placement, SRAM allocation or palette edit is made here.
; Message $1BD owns the exact approved Bombchu receipt text in the registry.
BombchuReceipt_Id = $4C
BombchuReceipt_GfxId = $39
BombchuReceipt_Message = $01BD
BombchuReceipt_CodeStart = pc()

; Extend one table read without moving/changing any native row. Callers use
; X/Y=receipt ID (twice ID for pointer/message rows). Preserve full A's hidden
; byte for M8, X/Y/DBR/D and all flags except the original LDA's N/Z. The
; native absolute readers have DBR equal to their documented table bank.
; reg=0 is X, reg=1 is Y. New word values serve M16 callers too.
macro BombchuReceiptReader(name, old, index, value, reg)
<name>:
  PHP : REP #$30 : PHA : PHX
if <reg> == 1
  TYX
endif
  LDA $05,S : BIT.w #$0020 : BNE ?byte
  CPX.w #<index> : BNE ?native_word
  LDA.w #<value> : BRA ?word_ready
?native_word:
  LDA.l <old>,X
?word_ready:
  STA $03,S : BRA ?restore
?byte:
  SEP #$20
  CPX.w #<index> : BNE ?native_byte
  LDA.b #<value>&$FF : BRA ?byte_ready
?native_byte:
  LDA.l <old>,X
?byte_ready:
  STA $03,S
  REP #$20
?restore:
  PLX : PLA : PLP
  PHA : PLA : RTL
<name>_End:
endmacro

%BombchuReceiptReader(BombchuReceipt_OffsetY, $09836C, $4C, $00FC, 1)
%BombchuReceiptReader(BombchuReceipt_OffsetX, $0983B8, $4C, $0000, 1)
%BombchuReceiptReader(BombchuReceipt_Gfx, $098404, $4C, BombchuReceipt_GfxId, 1)
%BombchuReceiptReader(BombchuReceipt_WidthY, $098450, $4C, $0002, 1)
%BombchuReceiptReader(BombchuReceipt_WidthX, $098450, $4C, $0002, 0)
%BombchuReceiptReader(BombchuReceipt_Prop, $09849C, $4C, $0002, 0)
%BombchuReceiptReader(BombchuReceipt_SramLow, $0984E8, $98, BombchuOwned&$FFFF, 0)
%BombchuReceiptReader(BombchuReceipt_SramHigh, $0984E9, $98, BombchuOwned>>8, 0)
%BombchuReceiptReader(BombchuReceipt_Value, $098580, $4C, $0001, 1)
%BombchuReceiptReader(BombchuReceipt_Overflow, $07B528, $4C, $00FF, 1)
%BombchuReceiptReader(BombchuReceipt_MessageRead, $08C2DD, $98, BombchuReceipt_Message, 1)

; Each short native LDA is widened through its complete displaced span.
BombchuReceipt_LoadLow:
  JSL BombchuReceipt_SramLow : STA.b $00 : RTL
BombchuReceipt_LoadHigh:
  JSL BombchuReceipt_SramHigh : STA.b $01 : RTL
BombchuReceipt_UncleValue:
  JSL BombchuReceipt_Value : STA.b [$00] : RTL
BombchuReceipt_LoadValue:
  LDA.b #$7E : STA.b $02
  JSL BombchuReceipt_Value : RTL
BombchuReceipt_LoadGfx:
  JSL BombchuReceipt_Gfx : STA.b $72 : RTL
BombchuReceipt_LoadOverflow:
  JSL BombchuReceipt_Overflow : STA.b $03 : RTL
BombchuReceipt_LoadOffsetY:
  JSL BombchuReceipt_OffsetY : AND.w #$00FF : RTL
BombchuReceipt_LoadOffsetX:
  JSL BombchuReceipt_OffsetX : AND.w #$00FF : RTL
BombchuReceipt_LoadMessage:
  JSL BombchuReceipt_MessageRead : CMP.w #$FFFF : RTL

; This displaced span includes a conditional branch; preserve both original
; continuations without introducing an RTS/JSL stack mismatch.
BombchuReceipt_WidthBranch:
  JSL BombchuReceipt_WidthY
  BEQ .zero
  JML $0988D0
.zero
  JML $0988DC

; Gfx selector $39 is new. Every original selector takes the untouched native
; decompression/conversion path. Replaying PHK must select BANK00, not ours.
; Native entry requires M8/X8. New art is the same four tile order as the
; existing 128-byte item-get buffer: top pair then bottom pair.
BombchuReceipt_LoadArt:
  PHP
  CMP.b #BombchuReceipt_GfxId : BEQ .bombchu
  PLP
  PHB : PEA.w $0000 : PLB : PLB : PHA
  JML $00D4F1
.bombchu
  REP #$30 : PHA : PHX : PHY
  LDX.w #$007E
.copy
  LDA.l BombchuWorldGfx,X : STA.l $7EBD40,X
  DEX : DEX : BPL .copy
  PLY : PLX : PLA : PLP
  RTL
BombchuReceipt_CodeEnd = pc()
assert pc() <= $2BF000, "Bombchu receipt overlaps dream-entry owner"

; All 24 table loads: chest overflow, main receipt, fairy display, tossed
; pond item, falling prizes and the fixed rupee display path. Original table
; bytes remain untouched, including receipt $31 (room41) and $49 (sword).
macro BombchuReceiptHook(site, preimage, tail, count, target, jump)
  assert pc() == <site>, "Bombchu receipt caller org changed"
  assert read4(<site>) == <preimage>, "Bombchu receipt reader preimage changed"
if <count> == 5
  assert read1(<site>+4) == <tail>, "Bombchu receipt reader tail changed"
elseif <count> == 6
  assert read2(<site>+4) == <tail>, "Bombchu receipt reader tail changed"
elseif <count> == 7
  assert read3(<site>+4) == <tail>, "Bombchu receipt reader tail changed"
endif
if <jump> == 1
  JML <target>
else
  JSL <target>
endif
  NOP #<count>-4
  assert pc() == <site>+<count>
endmacro

; Literal caller orgs expose every bank to the manifest scanner. The shared
; macro emits only the checked hook span; preserve the item-code cursor once.
pushpc
org $07B594 ; @hook kind=jsl target=BombchuReceipt_LoadOverflow protected_size=5
%BombchuReceiptHook($07B594, $85B528B9, $03, 5, BombchuReceipt_LoadOverflow, 0)
org $07B5A0 ; @hook kind=jsl target=BombchuReceipt_SramLow protected_size=4
%BombchuReceiptHook($07B5A0, $0984E8BF, $00, 4, BombchuReceipt_SramLow, 0)
org $07B5A6 ; @hook kind=jsl target=BombchuReceipt_SramHigh protected_size=4
%BombchuReceiptHook($07B5A6, $0984E9BF, $00, 4, BombchuReceipt_SramHigh, 0)
org $098617 ; @hook kind=jsl target=BombchuReceipt_LoadLow protected_size=5
%BombchuReceiptHook($098617, $8584E8BD, $00, 5, BombchuReceipt_LoadLow, 0)
org $09861C ; @hook kind=jsl target=BombchuReceipt_LoadHigh protected_size=5
%BombchuReceiptHook($09861C, $8584E9BD, $01, 5, BombchuReceipt_LoadHigh, 0)
org $098625 ; @hook kind=jsl target=BombchuReceipt_UncleValue protected_size=5
%BombchuReceiptHook($098625, $878580B9, $00, 5, BombchuReceipt_UncleValue, 0)
org $09862D ; @hook kind=jsl target=BombchuReceipt_LoadLow protected_size=5
%BombchuReceiptHook($09862D, $8584E8BD, $00, 5, BombchuReceipt_LoadLow, 0)
org $098632 ; @hook kind=jsl target=BombchuReceipt_LoadHigh protected_size=5
%BombchuReceiptHook($098632, $8584E9BD, $01, 5, BombchuReceipt_LoadHigh, 0)
; Preserve the existing Goldstar-owned JSL at $09863E exactly.
org $098637 ; @hook kind=jsl target=BombchuReceipt_LoadValue protected_size=7
%BombchuReceiptHook($098637, $02857EA9, $8580B9, 7, BombchuReceipt_LoadValue, 0)
org $09877D ; @hook kind=jsl target=BombchuReceipt_LoadGfx protected_size=5
%BombchuReceiptHook($09877D, $858404B9, $72, 5, BombchuReceipt_LoadGfx, 0)
org $098861 ; @hook kind=jsl target=BombchuReceipt_LoadOffsetY protected_size=6
%BombchuReceiptHook($098861, $29836CB9, $00FF, 6, BombchuReceipt_LoadOffsetY, 0)
org $09886F ; @hook kind=jsl target=BombchuReceipt_LoadOffsetX protected_size=6
%BombchuReceiptHook($09886F, $2983B8B9, $00FF, 6, BombchuReceipt_LoadOffsetX, 0)
org $0988CB ; @hook kind=jml target=BombchuReceipt_WidthBranch protected_size=5
%BombchuReceiptHook($0988CB, $F08450B9, $0C, 5, BombchuReceipt_WidthBranch, 1)
org $098903 ; @hook kind=jsl target=BombchuReceipt_LoadOffsetY protected_size=6
%BombchuReceiptHook($098903, $29836CB9, $00FF, 6, BombchuReceipt_LoadOffsetY, 0)
org $09891C ; @hook kind=jsl target=BombchuReceipt_LoadOffsetX protected_size=6
%BombchuReceiptHook($09891C, $2983B8B9, $00FF, 6, BombchuReceipt_LoadOffsetX, 0)
org $098A4A ; @hook kind=jsl target=BombchuReceipt_LoadGfx protected_size=5
%BombchuReceiptHook($098A4A, $858404B9, $72, 5, BombchuReceipt_LoadGfx, 0)
org $098AFD ; @hook kind=jsl target=BombchuReceipt_LoadGfx protected_size=5
%BombchuReceiptHook($098AFD, $858404B9, $72, 5, BombchuReceipt_LoadGfx, 0)
org $098BE1 ; @hook kind=jsl target=BombchuReceipt_LoadGfx protected_size=5
%BombchuReceiptHook($098BE1, $858404B9, $72, 5, BombchuReceipt_LoadGfx, 0)
org $08C5C1 ; @hook kind=jsl target=BombchuReceipt_LoadMessage protected_size=6
%BombchuReceiptHook($08C5C1, $C9C2DDB9, $FFFF, 6, BombchuReceipt_LoadMessage, 0)
org $08C6A4 ; @hook kind=jsl target=BombchuReceipt_Prop protected_size=4
%BombchuReceiptHook($08C6A4, $09849CBF, $00, 4, BombchuReceipt_Prop, 0)
org $08C6BA ; @hook kind=jsl target=BombchuReceipt_WidthX protected_size=4
%BombchuReceiptHook($08C6BA, $098450BF, $00, 4, BombchuReceipt_WidthX, 0)
org $08C6D5 ; @hook kind=jsl target=BombchuReceipt_Prop protected_size=4
%BombchuReceiptHook($08C6D5, $09849CBF, $00, 4, BombchuReceipt_Prop, 0)
org $06C4D6 ; @hook kind=jsl target=BombchuReceipt_Prop protected_size=4
%BombchuReceiptHook($06C4D6, $09849CBF, $00, 4, BombchuReceipt_Prop, 0)
org $06C4E6 ; @hook kind=jsl target=BombchuReceipt_WidthX protected_size=4
%BombchuReceiptHook($06C4E6, $098450BF, $00, 4, BombchuReceipt_WidthX, 0)
org $00D4ED ; @hook kind=jml target=BombchuReceipt_LoadArt protected_size=4
%BombchuReceiptHook($00D4ED, $48AB4B8B, $00, 4, BombchuReceipt_LoadArt, 1)
pullpc
