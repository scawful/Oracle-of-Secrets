; Native $DD four-bomb drops become five-Bombchu packs after ownership.
; $DC/$DE and unowned $DD retain their original regular-bomb refill path.
; The native transient sprite still owns contact, bounce, expiry, ancilla
; dragging, pickup sound and Player 2 absorption. No receipt ID is added.

pushpc
org $06D1D8
assert read3($06D1D8) == $0E20BC, "Absorb_Bomb type load moved"
assert read3($06D1DB) == $D0F9B9, "Absorb_Bomb amount table moved"
; @hook module=Items name=BombchuPickup kind=jml target=Bombchu_Pickup expected_m=8 expected_x=8
; DBR=$06, X=sprite slot. Native absorption already removed the sprite.
  JML Bombchu_Pickup : NOP #2
assert pc() == $06D1DE

org $06D257
assert read3($06D257) == $0E20BC, "Absorbable draw type load moved"
assert read3($06D25A) == $D144B9, "Absorbable numeral table moved"
; @hook module=Items name=BombchuPickupDraw kind=jml target=Bombchu_PickupDraw expected_m=8 expected_x=8
; DBR=$06, X=sprite slot. Blink and OAM-region allocation already ran.
  JML Bombchu_PickupDraw : NOP #2
assert pc() == $06D25D
pullpc

Bombchu_Pickup:
{
  LDA.w $0E20,X : CMP.b #$DD : BNE .ordinary
  LDA.l BombchuOwned : CMP.b #$01 : BNE .ordinary
  LDA.l BombchuAmmo : CMP.b #$15 : BCC .valid
    LDA.b #$00 ; match the count sanitizer; do not keep stale free-RAM data
  .valid
  CLC : ADC.b #$05 : CMP.b #$15 : BCC .store
    LDA.b #$14
  .store
  STA.l BombchuAmmo
  JML $06D1E7 ; native RTS; leave pending regular bombs $7EF375 untouched

  .ordinary
  LDY.w $0E20,X
  LDA.w $D0F9,Y ; replay .megatonnage-$DC in the caller's DBR=$06
  JML $06D1DE
}

Bombchu_PickupDraw:
{
  LDA.w $0E20,X : CMP.b #$DD : BNE .ordinary
  LDA.l BombchuOwned : CMP.b #$01 : BNE .ordinary
  JSL Sprite_PrepOamCoord
  BCS .offscreen

  LDA.b $00 : STA.b ($90),Y
  LDA.b $01 : CMP.b #$01 : LDA.b #$01 : ROL A : STA.b ($92)
  REP #$20
  LDA.b $02 : INY : CLC : ADC.w #$0010 : CMP.w #$0100
  SEP #$20
  BCS .offscreen
  SBC.b #$0F : STA.b ($90),Y ; native partial-screen Y clipping
  INY
  LDA.b #$2E : STA.b ($90),Y

  ; NMI supplies idle/up frame 0 when no Bombchu travels. During travel the
  ; pack shares that Bombchu's animated OBJ cell and orientation intentionally.
  STZ.b $04
  LDA.l BombchuSignature : CMP.b #!BOMBCHU_SIGNATURE : BNE .properties
  LDA.l BombchuSlot : BEQ .properties
  CMP.b #$03 : BCS .properties
  LDA.l BombchuDirection : CMP.b #$01 : BNE .not_down
    LDA.b #$80 : STA.b $04 : BRA .properties
  .not_down
  CMP.b #$02 : BNE .properties
    LDA.b #$40 : STA.b $04
  .properties
  LDA.b $05 : AND.b #$30 : ORA.b #$04 : ORA.b $04
  INY : STA.b ($90),Y
  JML $06DC64 ; native shadow, then the original draw caller's RTS

  .offscreen
  JML $06D289
  .ordinary
  LDY.w $0E20,X
  LDA.w $D144,Y ; replay .numeral-$D8 in DBR=$06
  JML $06D25D
}
