; Crumble Floor Room Tag

pushpc
org $01CC08 ; Holes3 / tag $34 ; @hook module=Dungeons name=CrumbleFloor
if !ENABLE_THIN_ICE == 1
JSL CrumbleFloorTag_ThinIceEntry
else
JSL CrumbleFloorTag_Main
endif
RTS
pullpc

; check under link feet what tile he is standing on
; save in ram last tile we were on so it doesn't turn back off
; kill room tag
CrumbleFloorTag_Main:
{
  LDA.w $02B2 : CMP.b #$05 : BNE +
    RTL
  +
  LDA.b $20 : CLC : ADC #$10 : AND.b #$F0 : STA.w $0224 ; y
  LDA.b $22 : CLC : ADC #$08 : AND.b #$F0 : STA.w $0225 ; x

  LDA.w $0224 : CMP.w $0226 : BNE .differentTile
    LDA.w $0225 : CMP.w $0227 : BNE .differentTile
      JMP .sameTile
  .differentTile

  ; do code here for tile code
  REP #$30

  LDA.w $022A : AND.w #$01F0 : LSR #$02 : STA.b $00
  LDA.w $0228 : AND.w #$01F0 : ASL #$04
                        CLC : ADC.b $00 : STA.b $06
  TAX

  LDA.l $7E2000, X : CMP.w #$0CCC : BNE +
    JSR update_pit_tile
    SEP #$30
    JSR SpawnFallingTile
    BRA .doneupdate
  +
  LDA.l $7E2000, X : CMP.w #$0C62 : BNE +
  -
    JSR update_crack_tile
  +
  LDA.l $7E2000, X : CMP.w #$0C63 : BEQ -
  .doneupdate
  SEP #$30

  .sameTile

  LDA.w $0224 : STA.w $0226 : STA.w $0228 ; Last Y
  LDA.w $0225 : STA.w $0227 : STA.w $022A ; Last X
  ; Last Y with link high byte
  LDA.b $21 : STA.w $0229
  LDA.b $23 : STA.w $022B
  RTL
}


SpawnFallingTile:
{
  LDX.b #$1D

  .next
  LDA.l $7FF800, X : BNE .skip
    ; GARNISH 03
    LDA.b #$03 : STA.l $7FF800, X
    LDA.w $022A : STA.l $7FF83C, X
    LDA.w $022B : STA.l $7FF878, X
    LDA.w $0228 : CLC : ADC.b #$10 : STA.l $7FF81E, X
    LDA.w $0229 : ADC.b #$00 : STA.l $7FF85A, X
    LDA.b #$1F : STA.l $7FF90E, X
    STA.w $0FB4
    BRA .exit
  .skip
  DEX
  BPL .next

  .exit
  RTS
}

update_crack_tile:
{
  STZ.b $0E
  REP #$30
  JSR replace_crack_pit
  SEP #$30
  LDA.b #$01 : STA.b $14
  REP #$30
  RTS
}

update_pit_tile:
{
  STZ.b $0E
  REP #$30
  JSR replace_tile_pit
  SEP #$30
  LDA.b #$01 : STA.b $14
  REP #$30
  RTS
}

replace_crack_pit:
{
  LDX.w $1000
  LDA.w #$0CCC : STA.w $1006, X
  LDA.w #$0CDC : STA.w $100C, X
  LDA.w #$0CCD : STA.w $1012, X
  LDA.w #$0CDD : STA.w $1018, X

  LDX.b $06
  LDA.w #$0CCC : STA.l $7E2000, X
  LDA.w #$0CDC : STA.l $7E2080, X
  LDA.w #$0CCD : STA.l $7E2002, X
  LDA.w #$0CDD : STA.l $7E2082, X

  LDA.w #$01E9 : AND.w #$03FF : TAX
  LDA.l $7EFE00, X : AND.w #$00FF
  STA.b $08 : STA.b $09

  JMP replace_tile_continue
}

replace_tile_pit:
{
  LDX.w $1000

  LDA.w #$01E9
  STA.w $1006, X
  STA.w $100C, X
  STA.w $1012, X
  STA.w $1018, X

  LDX.b $06

  LDA.w #$01E9
  STA.l $7E2000, X
  STA.l $7E2080, X
  STA.l $7E2002, X
  STA.l $7E2082, X

  TXA
  LSR
  TAX
  LDA.w #$2020
  STA.l $7F2000, X
  STA.l $7F2040, X

  LDA.w #$01E9 : AND.w #$03FF : TAX
  LDA.l $7EFE00, X : AND.w #$00FF : STA.b $08 : STA.b $09

  JMP replace_tile_continue
}

; =========================================================
; Thin ice: the same tag also tracks ice floor (tile type $0E/$0F by the
; char at the cell's top-left). The ice cell Link steps off cracks; after
; !ThinIce_FuseFrames it turns into a pit. Standing still never breaks it.
; A cracked cell Link steps back onto and off again falls at once through
; the crumble rule above ($0CCC -> pit).
;
; Allocation: fixed slot $2CF800-$2CF9FF (Sprites/all_sprites.asm asserts
; the bank $2C stream stays below it). RAM $7FB000-$7FB035 (zeroed at boot).
if !ENABLE_THIN_ICE == 1

!ThinIce_LastFrame  = $7FB000 ; byte, $1A of the last run
!ThinIce_LastY      = $7FB002 ; word, $FFFF = no stored cell
!ThinIce_LastX      = $7FB004 ; word
!ThinIce_Fuses      = $7FB006 ; 8 entries x {Y word, X word, timer word}
!ThinIce_FuseCount  = 8
!ThinIce_FuseFrames = 40

pushpc
org $2CF800
; Entered from the tag slot with 8-bit A and X/Y.
CrumbleFloorTag_ThinIceEntry:
{
  JSL CrumbleFloorTag_Main
  SEP #$30
  LDA.b $1A : CMP.l !ThinIce_LastFrame : BNE +
    RTL ; already ran this frame
  +
  DEC : CMP.l !ThinIce_LastFrame : BEQ .continuous
    ; Frame gap (room change, dialog, pause): drop fuses and stored cell.
    REP #$30
    LDA.w #$FFFF : STA.l !ThinIce_LastY
    LDX.w #(!ThinIce_FuseCount-1)*6
    -
      LDA.w #$0000 : STA.l !ThinIce_Fuses+4, X
      TXA : SEC : SBC.w #$0006 : TAX
    BPL -
    SEP #$30
  .continuous
  LDA.b $1A : STA.l !ThinIce_LastFrame

  JSR ThinIce_Track
  JSR ThinIce_TickFuses
  SEP #$30
  RTL
}

; Crack the ice cell Link just stepped off and start its fuse.
ThinIce_Track:
{
  LDA.w $02B2 : CMP.b #$05 : BEQ .skip  ; Minish
  LDA.b $5D   : CMP.b #$0A : BEQ .skip  ; Deku hover
                CMP.b #$13 : BEQ .skip  ; hookshot pull
  LDA.b $24   : BEQ +                   ; airborne
    CMP.b #$FF : BNE .skip
  +
  LDA.w $02F5 : BNE .skip               ; Somaria platform
  BRA .track
  .skip
  RTS

  .track
  REP #$30
  LDA.b $20 : CLC : ADC.w #$0010 : AND.w #$FFF0 : STA.b $00 ; foot cell Y
  LDA.b $22 : CLC : ADC.w #$0008 : AND.w #$FFF0 : STA.b $02 ; foot cell X

  LDA.l !ThinIce_LastY : CMP.w #$FFFF : BEQ .store
  CMP.b $00 : BNE .moved
  LDA.l !ThinIce_LastX : CMP.b $02 : BEQ .done
  .moved
  LDA.l !ThinIce_LastX : AND.w #$01F0 : LSR #2 : STA.b $06
  LDA.l !ThinIce_LastY : AND.w #$01F0 : ASL #4
                         CLC : ADC.b $06 : STA.b $06
  TAX
  LDA.l $7E2000, X : AND.w #$03FF : TAX
  LDA.l $7EFE00, X : AND.w #$00FF
  CMP.w #$000E : BEQ .ice
  CMP.w #$000F : BNE .store
  .ice
  LDX.w #(!ThinIce_FuseCount-1)*6
  -
    LDA.l !ThinIce_Fuses+4, X : BEQ .slot
    TXA : SEC : SBC.w #$0006 : TAX
  BPL -
  BRA .store ; all fuses busy: leave this cell uncracked
  .slot
  LDA.l !ThinIce_LastY : STA.l !ThinIce_Fuses+0, X
  LDA.l !ThinIce_LastX : STA.l !ThinIce_Fuses+2, X
  LDA.w #!ThinIce_FuseFrames : STA.l !ThinIce_Fuses+4, X
  LDA.b $00 : STA.l !ThinIce_LastY
  LDA.b $02 : STA.l !ThinIce_LastX
  JSR update_crack_tile ; uses $06, returns 16-bit
  BRA .done

  .store
  LDA.b $00 : STA.l !ThinIce_LastY
  LDA.b $02 : STA.l !ThinIce_LastX
  .done
  SEP #$30
  RTS
}

; Count down fuses. At most one cell breaks per frame.
ThinIce_TickFuses:
{
  REP #$30
  LDX.w #(!ThinIce_FuseCount-1)*6
  .next
  LDA.l !ThinIce_Fuses+4, X : BEQ .skip
    DEC : STA.l !ThinIce_Fuses+4, X : BNE .skip
      JSR ThinIce_Break
      BRA .exit
  .skip
  TXA : SEC : SBC.w #$0006 : TAX
  BPL .next
  .exit
  SEP #$30
  RTS
}

; X = fuse entry offset (16-bit). Breaks the cell only if it is still cracked.
ThinIce_Break:
{
  LDA.l !ThinIce_Fuses+2, X : AND.w #$01F0 : LSR #2 : STA.b $06
  LDA.l !ThinIce_Fuses+0, X : AND.w #$01F0 : ASL #4
                              CLC : ADC.b $06 : STA.b $06
  PHX
  TAX
  LDA.l $7E2000, X : CMP.w #$0CCC : BNE .not_cracked
  JSR update_pit_tile ; uses $06, returns 16-bit
  PLX
  ; SpawnFallingTile reads the cell from $0228-$022B; borrow them.
  LDA.w $0228 : PHA
  LDA.w $022A : PHA
  LDA.l !ThinIce_Fuses+0, X : STA.w $0228
  LDA.l !ThinIce_Fuses+2, X : STA.w $022A
  SEP #$30
  JSR SpawnFallingTile
  REP #$30
  PLA : STA.w $022A
  PLA : STA.w $0228
  RTS

  .not_cracked
  PLX
  RTS
}
assert pc() <= $2CFA00, "Thin ice overflows its bank $2C slot"
pullpc

endif
