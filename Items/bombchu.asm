; =========================================================
; Bombchu: one travelling crawler with its own collectible ammunition.
; Native bomb damage, destructible checks and explosion remain shared.
; @source usdasm/bank_07.asm:LinkItem_Bombs
; @source usdasm/bank_08.asm:Ancilla07_Bomb
; @source usdasm/bank_09.asm:AncillaAdd_Bomb
; Dedicated page-0 OBJ cell $2E/$2F/$3E/$3F; native bomb $6E is untouched.
; =========================================================

BombchuSlot       = $7E07F1 ; slot + 1, zero means no travelling Bombchu
BombchuDirection  = $7E07F2 ; 0 up, 1 down, 2 left, 3 right
BombchuIndoors    = $7E07F3
BombchuAreaLow    = $7E07F4 ; room indoors, overworld area outdoors
BombchuAreaHigh   = $7E07F5
BombchuSignature  = $7E07F6
BombchuFloor      = $7E07F7
BombchuFollowing  = $7E07FD ; zero until the first wall; then keep it on the right
BombchuAllocating = $7E07FE ; nonzero only inside the native bomb allocator
!BOMBCHU_SIGNATURE = $BC

pushpc
org $07A153
; @hook Bombchu_BombSpawn kind=jsl target=Bombchu_AddBomb
; @assumption M=8, X=8; fresh Y press already checked by vanilla.
; Replaces JSL AncillaAdd_Bomb. Ordinary bombs use the original routine.
  JSL Bombchu_AddBomb
assert pc() <= $07A157

; Keep the native allocator and setup, selecting only its ammunition source.
; The synchronous latch distinguishes our caller from every ordinary bomb.
org $098127
assert read4($098127) == $7EF343AF, "Native bomb ammo load moved"
; @hook Bombchu_AmmoLoad kind=jsl target=Bombchu_AmmoLoad
; @assumption M=8, X=8; replaces LDA.l $7EF343, including its N/Z flags.
  JSL Bombchu_AmmoLoad
org $098133
assert read4($098133) == $7EF3438F, "Native bomb ammo store moved"
; @hook Bombchu_AmmoStore kind=jsl target=Bombchu_AmmoStore
; @assumption M=8, X=8; A is decremented stock, N/Z feed the next BNE.
  JSL Bombchu_AmmoStore

org $08955A
; @hook Bombchu_BombDispatch kind=jml target=Bombchu_BombEntry
; @assumption M=8, X=8, DBR=$08, X is the current ancilla slot.
; Replaces LDA $11 / BEQ $08958E; both vanilla branches are preserved.
  JML Bombchu_BombEntry
assert pc() <= $08955E

org $008B56
assert read3($008B56) == $0134AE, "Bombchu NMI VRAM load moved"
assert read3($008B59) == $21168E, "Bombchu NMI VRAM store moved"
; @hook Bombchu_WorldUpload kind=jsl target=Bombchu_NmiUpload
; @assumption M=8, X=16, DBR=$00; DMA0 mode=$1801, VMAIN=$80.
; Follows P2_NmiUpload rather than replacing its hook at $008B50.
  JSL Bombchu_NmiUpload : NOP #2
assert pc() == $008B5C

org $08A7D7
assert read3($08A7D7) == $9D10BD, "Bombchu draw tile load moved"
assert read3($08A7DD) == $9D11BD, "Bombchu draw property load moved"
; @hook Bombchu_WorldDraw kind=jsl target=Bombchu_DrawTile
; @assumption M=8, X=8, DBR=$08; X=draw-table offset, $0FA0=ancilla slot.
; Replay the native tile/property writes for every other bomb/explosion.
  JSL Bombchu_DrawTile : NOP #13
assert pc() == $08A7E8
pullpc

Bombchu_AddBomb:
{
  LDA.w $0202 : CMP.b #$1C : BEQ .bombchu
    LDY.b #$01 : LDA.b #$07
    JML $09811F ; original AncillaAdd_Bomb, returns to our caller

  .bombchu
  LDA.l BombchuOwned : CMP.b #$01 : BEQ .owned
    BRL .exit
  .owned
  JSL Bombchu_Tick
  LDA.l BombchuSlot : BNE .exit ; one travelling Bombchu at a time
  LDA.l BombchuAmmo : BEQ .exit

  ; The allocator's two ammunition hooks debit BombchuAmmo only while this
  ; latch is set. A changed count proves allocation; failure may leave X=$FF.
  PHA
  LDA.b #$01 : STA.l BombchuAllocating
  LDY.b #$01 : LDA.b #$07
  JSL $09811F
  LDA.b #$00 : STA.l BombchuAllocating
  PLA : CMP.l BombchuAmmo : BEQ .exit

  TXA : INC A : STA.l BombchuSlot
  LDA.b $2F : LSR A : AND.b #$03 : STA.l BombchuDirection
  STA.w $0C72,X
  LDA.b $1B : STA.l BombchuIndoors
  BEQ .overworld
    LDA.b $A0 : STA.l BombchuAreaLow
    LDA.b $A1 : STA.l BombchuAreaHigh
    BRA .context_ready
  .overworld
    LDA.w $008A : STA.l BombchuAreaLow
    LDA.w $008B : STA.l BombchuAreaHigh
  .context_ready
  LDA.b $EE : STA.l BombchuFloor
  LDA.b #!BOMBCHU_SIGNATURE
  STA.l BombchuSignature
  STA.w $03EA,X ; native non-liftable field, also protects against slot reuse
  LDA.b #$00 : STA.l BombchuFollowing
  LDA.b #$C0 : STA.w $039F,X ; 192 one-pixel active frames, same maximum range
  STZ.w $0C22,X : STZ.w $0C2C,X
  STZ.w $029E,X ; never airborne
  .exit
  RTL
}

; AmmoLoad reproduces LDA flags. AmmoStore preserves incoming A/P because
; native BNE uses the decrement's zero result, not the allocation latch.
Bombchu_AmmoLoad:
{
  LDA.l BombchuAllocating : BEQ .ordinary
  LDA.l BombchuAmmo : RTL
  .ordinary
  LDA.l $7EF343 : RTL
}

Bombchu_AmmoStore:
{
  PHP : PHA
  LDA.l BombchuAllocating : BEQ .ordinary
  PLA : STA.l BombchuAmmo : PLP : RTL
  .ordinary
  PLA : STA.l $7EF343 : PLP : RTL
}

; Called by the common prototype tick and immediately before use/dispatch.
; Preserves A/X/Y/P/DBR. The startup hook clears $07EE-$07FF.
Bombchu_Tick:
{
  PHP : PHB
  %m16()
  PHA : PHX : PHY
  %m8()
  PHK : PLB

  LDA.l BombchuSignature : CMP.b #!BOMBCHU_SIGNATURE : BEQ .has_signature
    BRL .clear
  .has_signature
  LDA.l BombchuSlot : BNE .has_slot
    BRL .clear
  .has_slot
  CMP.b #$03 : BCC .slot_in_range ; native bombs use slots 0 and 1 only
    BRL .clear
  .slot_in_range
  DEC A : TAX
  LDA.w $0C4A,X : CMP.b #$07 : BNE .clear
  LDA.w $03EA,X : CMP.b #!BOMBCHU_SIGNATURE : BNE .clear
  LDA.w $0C5E,X : BNE .clear ; native explosion now owns the object

  LDA.b $10 : CMP.b #$07 : BEQ .check_context
  CMP.b #$09 : BEQ .check_context
  CMP.b #$0E : BEQ .done ; inventory/message submodule preserves travel
  BRA .delete
  .check_context
  ; Class 2 temporarily changes $0C7C when probing both room layers.
  ; Link's floor is the stable launch context; the ancilla field is not.
  LDA.b $EE : CMP.l BombchuFloor : BNE .delete
  LDA.b $1B : CMP.l BombchuIndoors : BNE .delete
  LDA.b $1B : BEQ .check_overworld
    LDA.b $A0 : CMP.l BombchuAreaLow : BNE .delete
    LDA.b $A1 : CMP.l BombchuAreaHigh : BNE .delete
    BRA .done
  .check_overworld
    LDA.w $008A : CMP.l BombchuAreaLow : BNE .delete
    LDA.w $008B : CMP.l BombchuAreaHigh : BNE .delete
    BRA .done

  .delete
  ; The signature in the ancilla itself proves this is still our object.
  ; A freshly allocated ordinary bomb resets $03EA and is never deleted.
  STZ.w $0C4A,X
  .clear
  LDA.b #$00
  STA.l BombchuSlot : STA.l BombchuSignature : STA.l BombchuFollowing
  .done
  %m16()
  PLY : PLX : PLA
  PLB : PLP
  RTL
}

Bombchu_BombEntry:
{
  JSL Bombchu_Tick
  LDA.w $0C4A,X : CMP.b #$07 : BNE .deleted
  LDA.l BombchuSlot : BEQ .vanilla
  DEC A : STA.b $00
  TXA : CMP.b $00 : BNE .vanilla
  LDA.b $11 : BNE .paused
  LDA.w $0FC1 : BNE .paused ; sprite/cutscene freeze also freezes the fuse

  PHB : PHK : PLB
  JSR Bombchu_Crawl
  LDA.l BombchuDirection : STA.w $0C72,X
  PLB
  ; Skip lifting, then retain native terrain, pits, water and bomb state.
  JML $089591

  .paused
  JML $08958B ; draw only, no movement/fuse while a submodule is active
  .vanilla
  LDA.b $11 : BEQ .vanilla_main
  JML $08955E
  .vanilla_main
  JML $08958E
  .deleted
  JML $0897B5 ; native RTS: Tick removed our object during a transition
}

; Initially move forward. The first obstruction turns left, placing the wall
; on the right. Subsequent frames prefer right, forward, left, then reverse.
; Each failed candidate rotates left; four failures prove the Bombchu trapped.
; X=ancilla slot, M/X=8, DBR=our bank; X preserved, Y/$00-$0F scratch.
Bombchu_Crawl:
{
  LDA.l BombchuDirection : AND.b #$03 : STA.b $0E
  LDA.l BombchuFollowing : BEQ .first_candidate
    LDY.b $0E
    LDA.w .right,Y : STA.b $0E
  .first_candidate
  LDA.b #$04 : STA.b $0F
  .try_direction
  LDA.b $0E
  JSR Bombchu_ProbeStep : BCC .move
  LDA.b #$01 : STA.l BombchuFollowing
  DEC.b $0F : BEQ .trapped
  LDY.b $0E
  LDA.w .left,Y : STA.b $0E
  BRA .try_direction
  .move
  LDA.b $0E : STA.l BombchuDirection
  JSR Bombchu_Move
  RTS
  .trapped
  LDA.b #$01 : STA.w $039F,X ; native bomb state starts its explosion
  RTS
  .right
  db $03, $02, $00, $01
  .left
  db $02, $03, $01, $00
}

; A=prospective direction. Probe its leading edge before changing position.
; A one-pixel step with a 15x15 body has its new leading edge at old center
; +/-8. Samples at perpendicular -7,0,+7 cover all touched 8px collision cells.
; Sprite_GetTileAttr clobbers $00-$07, so each point is rebuilt from $0A/$0C.
; The live tile map includes opened doors and broken bushes/pots. Whole slope
; tiles are conservatively blocked; actor collision is still native bomb logic.
; X=ancilla slot preserved; returns M/X=8, C=1 blocked. $08-$0D/Y scratch.
Bombchu_ProbeStep:
{
  STA.b $08
  STZ.b $09
  LDA.w $0BFA,X : STA.b $0A
  LDA.w $0C0E,X : STA.b $0B
  LDA.w $0C04,X : STA.b $0C
  LDA.w $0C18,X : STA.b $0D
  .point
  LDA.b $08 : ASL A : CLC : ADC.b $08 : ASL A
  CLC : ADC.b $09 : TAY ; direction*6 + point*2
  %a16()
  LDA.b $0A : CLC : ADC.w .probe_y,Y : STA.b $00
  SEC : SBC.b $E8 : CMP.w #$00E0 : BCS .outside
  LDA.b $0C : CLC : ADC.w .probe_x,Y : STA.b $02
  SEC : SBC.b $E2 : CMP.w #$0100 : BCS .outside
  %a8()
  LDA.l BombchuFloor
  JSL Sprite_GetTileAttr ; raw type in A; X preserved, M/X=8
  CMP.b #$08 : BEQ .blocked ; deep water is zero in the sprite ground table
  CMP.b #$09 : BEQ .pass    ; shallow water
  CMP.b #$22 : BEQ .pass    ; outdoor stairs
  PHX : TAX
  LDA.l $1DF6CF,X
  PLX
  CMP.b #$00 : BNE .blocked ; PLX changes N/Z, not the tile classification
  .pass
  INC.b $09 : INC.b $09
  LDA.b $09 : CMP.b #$06 : BNE .point
  CLC
  RTS
  .outside
  %a8()
  .blocked
  SEC
  RTS
  .probe_y
  dw -8,-8,-8, 8,8,8, -7,0,7, -7,0,7
  .probe_x
  dw -7,0,7, -7,0,7, -8,-8,-8, 8,8,8
}

; A=direction, X=ancilla slot, DBR=our bank. Moves one pixel with full
; 16-bit coordinates, including across $xxFF/$xx00 boundaries.
Bombchu_Move:
{
  ASL A : TAY
  LDA.w $0BFA,X : STA.b $00
  LDA.w $0C0E,X : STA.b $01
  LDA.w $0C04,X : STA.b $02
  LDA.w $0C18,X : STA.b $03
  %a16()
  LDA.b $00 : CLC : ADC.w .delta_y,Y : STA.b $00
  LDA.b $02 : CLC : ADC.w .delta_x,Y : STA.b $02
  %a8()
  LDA.b $00 : STA.w $0BFA,X
  LDA.b $01 : STA.w $0C0E,X
  LDA.b $02 : STA.w $0C04,X
  LDA.b $03 : STA.w $0C18,X
  RTS

  .delta_y
  dw -1, 1, 0, 0
  .delta_x
  dw 0, 0, -1, 1
}

; Called inside the existing VBlank upload, after Link/P2/water graphics.
; The dedicated cell avoids arrows ($2A-$2D/$3A-$3D), P2 ($0E/$20/$24),
; and all ordinary bomb/explosion tiles. No shared WRAM art is replaced.
Bombchu_NmiUpload:
{
  PHP : PHA : PHX : PHY
  SEP #$10
  LDA.b $10 : CMP.b #$07 : BEQ .gameplay
  CMP.b #$09 : BEQ .gameplay
  CMP.b #$0E : BNE .skip
  .gameplay
  LDA.l BombchuSignature : CMP.b #!BOMBCHU_SIGNATURE : BNE .pickups
  LDA.l BombchuSlot : BEQ .pickups
  CMP.b #$03 : BCS .pickups
  DEC A : TAX
  LDA.w $0C4A,X : CMP.b #$07 : BNE .pickups
  LDA.w $03EA,X : CMP.b #!BOMBCHU_SIGNATURE : BNE .pickups
  LDA.w $0C5E,X : BNE .pickups
  ; Active crawl frame takes priority when a refill is visible too.
  LDA.l BombchuDirection : AND.b #$02 : PHA
  LDA.w $039F,X : AND.b #$08 : LSR #3
  ORA $01,S : STA $01,S
  PLA
  BRA .frame_ready
  .pickups
  LDA.l BombchuOwned : CMP.b #$01 : BNE .skip
  LDX.b #$0F
  .find_pack
  LDA.w $0DD0,X : CMP.b #$09 : BNE .next_pack
  LDA.w $0E20,X : CMP.b #$DD : BEQ .idle_frame
  .next_pack
  DEX : BPL .find_pack
  .skip
  BRL .done
  .idle_frame
  LDA.b #$00
  .frame_ready
  ; Up A/B and right A/B are 128-byte frames. With no travelling Bombchu,
  ; a live collectible uses frame zero from this same dedicated OBJ cell.
  REP #$30
  AND.w #$00FF : ASL #7
  CLC : ADC.w #BombchuWorldGfx : TAY
  SEP #$20
  LDA.b #BombchuWorldGfx>>16 : STA.w $4304
  REP #$20
  TYA : STA.w $4302
  LDA.w #$42E0 : STA.w $2116
  JSR .row
  TYA : CLC : ADC.w #$0040 : STA.w $4302
  LDA.w #$43E0 : STA.w $2116
  JSR .row
  SEP #$20
  LDA.b #$7E : STA.w $4304
  REP #$20
  LDA.w $0ADC : STA.w $4302 ; next DMA is the animated background
  SEP #$20
  .done
  REP #$10
  PLY : PLX : PLA : PLP
  LDX.w $0134 : STX.w $2116 ; displaced instructions
  RTL

  .row
  LDA.w #$0040 : STA.w $4305
  SEP #$20
  LDA.b #$01 : STA.w $420B
  REP #$20
  RTS
}

Bombchu_DrawTile:
{
  PHX
  CPX.b #$00 : BNE .vanilla ; unexpanded bomb body only
  LDA.l BombchuSignature : CMP.b #!BOMBCHU_SIGNATURE : BNE .vanilla
  LDA.l BombchuSlot : BEQ .vanilla
  CMP.b #$03 : BCS .vanilla
  DEC A : CMP.w $0FA0 : BNE .vanilla
  TAX
  LDA.w $0C4A,X : CMP.b #$07 : BNE .vanilla
  LDA.w $03EA,X : CMP.b #!BOMBCHU_SIGNATURE : BNE .vanilla
  LDA.w $0C5E,X : BNE .vanilla
  LDA.b #$2E : STA.b ($90),Y : INY
  LDA.l BombchuDirection : AND.b #$03 : TAX
  LDA.l .flips,X
  ORA.b $65 : ORA.b $0B : STA.b ($90),Y
  PLX : RTL
  .vanilla
  PLX
  LDA.w $9D10,X : STA.b ($90),Y : INY
  LDA.w $9D11,X : AND.b #$C1
  ORA.b $65 : ORA.b $0B : STA.b ($90),Y
  RTL
  .flips
  db $00, $80, $40, $00
}

BombchuWorldGfx:
  incbin "Data/graphics/items/bombchu_world.4bpp"
BombchuWorldGfxEnd:
assert BombchuWorldGfxEnd-BombchuWorldGfx == $0200, "Bombchu needs four 16x16 frames"
assert (BombchuWorldGfx>>16) == ((BombchuWorldGfxEnd-1)>>16), "Bombchu DMA source crosses bank"
