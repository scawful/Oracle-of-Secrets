; =========================================================
; Dive gate (tag 0x39 CustomTag, room-ID dispatch)
;
; Room 0x44 (Zora Temple): an upper deck sits over an underwater passage.
; The deck walker and the Zora diver both use collision map a ($7F2000,
; $EE=0). While !ZoraDiving is set, this tag swaps a short list of map-a
; cells (rails and caps at x41-48 y49-52) and restores them when the dive ends.
; It also hides the diver while the surface map b ($7F3000) cell under
; him is 02 (under the deck), using LinkVisible ($4B=$0C).
;
; Why $4B and not $65: LinkOAM recomputes $64/$65 from $EE every frame
; (bank $0D LinkOAM_ObjectPriority), so a tag write to $65 cannot hold.
;
; !ZoraDiving is $0AAB (Masks/all_masks.asm, included after Dungeons).
;
; Static room collision lives here, not in the custom-collision table: the
; deck strip is on map b (offsets $1000+), which the frozen custom-collision
; reader and yaze reject or drop. DiveGate_ApplyRoomCollision writes it once
; per room load; a room reload rebuilds map b and clears the sentinel.

DiveGate_IsRoom:
{
  PHA
  LDA.b $1B : BEQ .no
  LDA.b $A1 : BNE .no
  LDA.b $A0 : CMP.b #$44 : BNE .no
  LDA.b $AE : CMP.b #$39 : BNE .no  ; inert until room 0x44 has tag1 0x39
  PLA : SEC : RTL
  .no
  PLA : CLC : RTL
}

; Per-frame tag body. Entry from CustomTag: M=8/X=8, D=0, WRAM-mirrored DBR.
; Preserves P, X, Y and DBR.
DiveGate_Main:
{
  PHB : PHP : PHX : PHY
  REP #$10
  LDX.w #$0000
  LDA.w $0AAB : BEQ +           ; !ZoraDiving
    LDX.w #DiveGate_Room44_Dive-DiveGate_Room44_Normal
  +
  PEA.w $7F7F : PLB : PLB       ; DBR = $7F for the collision maps
  JSR DiveGate_ApplyRoomCollision

  ; Write the selected column every frame (16 cells, idempotent).
  .cell
    REP #$20
    LDA.l DiveGate_Room44_Normal,X : BMI .cells_done   ; $FFFF ends a list
    TAY
    SEP #$20
    LDA.l DiveGate_Room44_Normal+2,X : STA.w $2000,Y   ; map a
    INX #3
    BRA .cell
  .cells_done
  SEP #$20

  ; Hide the diver while the surface cell above him is deck (02).
  LDA.l $7E0AAB : BEQ .show
  JSR DiveGate_ProbeIndex
  LDA.w $3000,Y : CMP.b #$02 : BNE .show
    LDA.b #$0C : STA.b $4B
    BRA .exit
  .show
  ; No vanilla $4B=$0C user runs in this room (bird/whirlpool are overworld).
  LDA.b $4B : CMP.b #$0C : BNE .exit
    STZ.b $4B
  .exit
  SEP #$30
  PLY : PLX : PLP : PLB
  RTS
}

; Once per room load: map-b deck strip x42-47 y44-57 = 02. The deck's south wall
; is already map-a row 56 (02) on layout rO, so no south cap. Needs DBR=$7F, M=8,
; X/Y=16. Preserves X; clobbers A, Y. Sentinel: the first strip cell (authored 1C).
DiveGate_ApplyRoomCollision:
{
  LDA.w $3B2A : CMP.b #$02 : BEQ .done
  PHX
  LDX.w #$3B2A                  ; map b x42 y44
  .row
    LDA.b #$02
    LDY.w #$0006
    .column
      STA.w $0000,X : INX
      DEY : BNE .column
    REP #$21
    TXA : ADC.w #$003A : TAX    ; next row, x42
    SEP #$20
    CPX.w #$3EAA : BNE .row     ; past y57
  PLX
  .done
  RTS
}

; Zora resurface guard, JSL from Masks/zora_mask.asm .dungeon_resurface.
; Carry set: Y may surface here. In room 0x44 only when the map-b cell
; under Link is deep water (08). Preserves X, Y, DBR; A is clobbered.
DiveGate_CanSurface:
{
  PHB : PHX : PHY : PHP
  JSL DiveGate_IsRoom : BCC .allow
  REP #$10
  PEA.w $7F7F : PLB : PLB
  JSR DiveGate_ProbeIndex
  LDA.w $3000,Y : CMP.b #$08 : BEQ .allow
    PLP : CLC
    BRA .exit
  .allow
  PLP : SEC
  .exit
  PLY : PLX : PLB
  RTL
}

; Out: Y = collision cell index (0-$0FFF) under Link's probe point
; x = ($22 + 8) & $1FF, y = ($20 + 12) & $1FF. Needs X/Y 16-bit; keeps A width.
DiveGate_ProbeIndex:
{
  PHP
  REP #$20
  LDA.b $22 : CLC : ADC.w #$0008 : AND.w #$01FF : LSR #3 : PHA
  LDA.b $20 : CLC : ADC.w #$000C : AND.w #$01F8 : ASL #3
  CLC : ADC.b $01,S : TAY
  PLA
  PLP
  RTS
}

; Map-a cells, offset = y*64 + x. Format: dw offset : db value.
; Layout rO, values read from z3ed dungeon-tile-types map a. Rails are two cells
; thick (2A + 02) on each side of the 4-wide deck x43-46.
; Normal: rails block x41-42/x47-48 at y50-51, the north/south caps are open.
; Dive: the rails open and the caps close (16 cells, written every frame).
DiveGate_Room44_Normal:
  dw $0CA9 : db $2A   ; rail x41 y50
  dw $0CAA : db $02   ; rail x42 y50
  dw $0CE9 : db $2A   ; rail x41 y51
  dw $0CEA : db $02   ; rail x42 y51
  dw $0CAF : db $02   ; rail x47 y50
  dw $0CB0 : db $2A   ; rail x48 y50
  dw $0CEF : db $02   ; rail x47 y51
  dw $0CF0 : db $2A   ; rail x48 y51
  dw $0C6B : db $00   ; cap x43 y49
  dw $0C6C : db $00   ; cap x44 y49
  dw $0C6D : db $00   ; cap x45 y49
  dw $0C6E : db $00   ; cap x46 y49
  dw $0D2B : db $00   ; cap x43 y52
  dw $0D2C : db $00   ; cap x44 y52
  dw $0D2D : db $00   ; cap x45 y52
  dw $0D2E : db $00   ; cap x46 y52
  dw $FFFF
DiveGate_Room44_Dive:
  dw $0CA9 : db $00
  dw $0CAA : db $00
  dw $0CE9 : db $00
  dw $0CEA : db $00
  dw $0CAF : db $00
  dw $0CB0 : db $00
  dw $0CEF : db $00
  dw $0CF0 : db $00
  dw $0C6B : db $02
  dw $0C6C : db $02
  dw $0C6D : db $02
  dw $0C6E : db $02
  dw $0D2B : db $02
  dw $0D2C : db $02
  dw $0D2D : db $02
  dw $0D2E : db $02
  dw $FFFF
