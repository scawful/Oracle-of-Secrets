; Weight Plate (underworld tile type $DD, room tag $35)
;
; Tag $35 opens the room's hold doors ($0468, vanilla hold-door path) while
; something heavy rests on a $DD cell:
;   - Link on foot (not Minish form $02B2 == $05, not airborne $5D == $02)
;   - a pushed block that settled on the plate (block state 5)
;   - statue ($1C), ice block ($D5) or minecart ($A3) sprite
;   - the follower
;   - a Somaria block (ancilla $2C)
; Rooms listed in WeightPlate_LatchRooms latch instead: once pressed, the
; room's bit in WeightPlate_Latch is set and the door stays open.
; Sprites are included after Dungeons, so raw IDs are used.
;
; Allocation:
;   $01B55C-$01B55F  tag stub (Bank01 free space; object_handler.asm asserts
;                    it stays below $01B55C)
;   $2EF000-$2EF7FF  main code (bank $2E tail; Menu/menu.asm asserts the HUD
;                    stream stays below $2EF000)
;   $7EF4F0-$7EF4F1  WeightPlate_Latch (Core/sram.asm)
; The vanilla tag $35 slot $01CC0C is the RTS of the crumble floor tag ($34),
; so the $35 vector is pointed at the stub instead.

if !ENABLE_WEIGHT_PLATE == 1

pushpc

; Room tag $35 vector (vanilla RoomTag_Holes4 at $01CC0C).
org $01C2E7 ; @hook module=Dungeons name=WeightPlate_TagVector kind=data
  dw WeightPlate_TagStub

org $01B55C ; @hook module=Dungeons name=WeightPlate_TagStub kind=jml target=WeightPlate_Main expected_m=8 expected_x=8
WeightPlate_TagStub:
  JML WeightPlate_Main
assert pc() <= $01B560, "WeightPlate tag stub crossed $01B560"

; PushBlock_CheckForPit: a block that lands on $DD settles in state 5 like
; one on a $23 switch, without the $0466 write the switch path makes.
org $01D94D ; @hook module=Dungeons name=WeightPlate_BlockLand kind=jml target=WeightPlate_BlockLand expected_m=16 expected_x=16
  JML WeightPlate_BlockLand
  NOP

; Push target class for $DD: $00 lets blocks slide onto the plate (was $01).
org $07DF26+$DD ; @hook module=Dungeons name=WeightPlate_PushTarget kind=data
  db $00

; Sprite tile class: $00 = sprites walk on the plate (was $01, wall).
org $1DF6CF+$DD ; @hook module=Dungeons name=WeightPlate_SpriteClass kind=data
  db $00

org $2EF000
; Entered with 16-bit A/X/Y and the landing tile type in A.
WeightPlate_BlockLand:
{
  CMP.w #$0023 : BNE +
    JML $01D952 ; vanilla switch landing
  +
  CMP.w #$00DD : BNE +
    LDA.w #$0004
    JML $01D963 ; .proceed: state 4, advanced to 5
  +
  JML $01D960   ; .go_negative
}

; Room tag $35. Entered from Underworld_HandleRoomTags with 8-bit A/X/Y;
; $0E holds the tag slot.
WeightPlate_Main:
{
  REP #$30
  STZ.b $08 ; latch mask, 0 = hold room
  LDX.w #$0000
  .find_room
    LDA.l WeightPlate_LatchRooms, X : CMP.w #$FFFF : BEQ .scan
    CMP.b $A0 : BEQ .latch_room
    INX #4
    BRA .find_room
  .latch_room
  LDA.l WeightPlate_LatchRooms+2, X : STA.b $08
  AND.l WeightPlate_Latch : BNE .pressed

  .scan
  SEP #$30
  JSR WeightPlate_IsPressed
  REP #$30
  BCC .released
  LDA.b $08 : BEQ .pressed
    ORA.l WeightPlate_Latch : STA.l WeightPlate_Latch

  .pressed
  LDX.w #$0000
  BRA .update
  .released
  LDX.w #$0001

  ; Same update as RoomTag_SwitchTrigger_HoldDoor ($01C579).
  .update
  CPX.w $0468 : BEQ .exit
  STX.w $0468
  STZ.w $068E
  STZ.w $0690
  SEP #$30
  CPX.b #$00 : BNE .no_sfx
    LDA.b #$25 : STA.w $012F
  .no_sfx
  LDA.b #$05 : STA.b $11

  .exit
  SEP #$30
  JML RoomTag_Return
}

; Returns carry set when an occupant stands on a $DD cell. 8-bit A/X/Y.
WeightPlate_IsPressed:
{
  ; Link on foot
  LDA.w $02E4 : ORA.b $4D : BNE .no_link
  LDA.w $02B2 : CMP.b #$05 : BEQ .no_link ; Minish form
  LDA.b $5D   : CMP.b #$02 : BEQ .no_link ; airborne
  REP #$20
  LDA.b $20 : CLC : ADC.w #$0014 : STA.b $00
  LDA.b $22 : CLC : ADC.w #$0008 : STA.b $02
  SEP #$20
  LDA.b $EE
  JSR WeightPlate_TileIsPlate : BCC .no_link
    RTS
  .no_link

  ; Pushed blocks: state 5 = settled on a plate or switch
  REP #$30
  LDX.w #$FFFE
  .next_block
    INX #2
    CPX.w $0478 : BEQ .blocks_done
    LDA.w $0500, X : CMP.w #$0005 : BNE .next_block
    SEP #$30
    SEC
    RTS
  .blocks_done
  SEP #$30

  ; Statue, ice block, minecart
  LDX.b #$0F
  .next_sprite
    LDA.w $0DD0, X : CMP.b #$09 : BNE .skip_sprite
    LDA.w $0E20, X
    CMP.b #$1C : BEQ .heavy_sprite ; statue
    CMP.b #$D5 : BEQ .heavy_sprite ; ice block
    CMP.b #$A3 : BNE .skip_sprite  ; minecart
    .heavy_sprite
    LDA.w $0D00, X : CLC : ADC.b #$08 : STA.b $00
    LDA.w $0D20, X : ADC.b #$00 : STA.b $01
    LDA.w $0D10, X : CLC : ADC.b #$08 : STA.b $02
    LDA.w $0D30, X : ADC.b #$00 : STA.b $03
    LDA.w $0F20, X
    JSR WeightPlate_TileIsPlate : BCC .skip_sprite
      RTS
  .skip_sprite
    DEX : BPL .next_sprite

  ; Follower: current step in the position ring buffer
  LDA.l $7EF3CC : BEQ .no_follower
    LDX.w $02CF
    LDA.w $1A00, X : CLC : ADC.b #$14 : STA.b $00
    LDA.w $1A14, X : ADC.b #$00 : STA.b $01
    LDA.w $1A28, X : CLC : ADC.b #$08 : STA.b $02
    LDA.w $1A3C, X : ADC.b #$00 : STA.b $03
    LDA.w $1A64, X
    JSR WeightPlate_TileIsPlate : BCC .no_follower
      RTS
  .no_follower

  ; Somaria block: ancilla position is its centre
  LDX.b #$09
  .next_ancilla
    LDA.w $0C4A, X : CMP.b #$2C : BNE .skip_ancilla
    LDA.w $0BFA, X : STA.b $00
    LDA.w $0C0E, X : STA.b $01
    LDA.w $0C04, X : STA.b $02
    LDA.w $0C18, X : STA.b $03
    LDA.w $0C7C, X
    JSR WeightPlate_TileIsPlate : BCC .skip_ancilla
      RTS
  .skip_ancilla
    DEX : BPL .next_ancilla

  CLC
  RTS
}

; In: $00-$01 = Y, $02-$03 = X, A = layer. Out: carry set on $DD.
; Sprite_GetTileAttr keeps X and clobbers $04-$06; exits 8-bit.
WeightPlate_TileIsPlate:
{
  JSL Sprite_GetTileAttr
  CMP.b #$DD : BEQ .plate
    CLC
    RTS
  .plate
  SEC
  RTS
}

; Latch rooms: dw room ID, dw WeightPlate_Latch bit. $FFFF ends the list.
; Any room not listed holds (door open only while pressed).
WeightPlate_LatchRooms:
  dw $FFFF

assert pc() <= $2EF800, "WeightPlate crossed $2EF800"

pullpc

endif
