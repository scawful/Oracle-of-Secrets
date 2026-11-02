; Garo in the Goron Mines approach: heal the existing sprite $57 in OW $36.
; Keep its current statue-derived drawing and placement. A fresh Song of
; Healing cast nearby grants the sixth mask, with a poof and milestone chime.
; No new dialogue or automatic R binding. GaroMaskOwned is the persistent
; completion flag; vanilla $57 behavior remains intact outside this area.
;
; Entry contract for both gateways: M=8, X=8, X=sprite slot. Preserve DBR/X.
; Main replaces a contact JSL, so A/Y and $00-$03 are caller scratch; C must
; be clear for Garo to skip the following vanilla statue collision response.

if !ENABLE_GOLDSTAR_CELL == 1 && !DISABLE_MASKS == 0

pushpc
; @hook Garo_Healing kind=jsl target=Garo_Healing
; @source usdasm/bank_05.asm:Sprite_57_DesertStatue ($059573)
; Drawing and Sprite_CheckIfActive_Bank05 have already run.
assert read4($059573) == $06F12922, "Garo contact hook moved"
org $059573
  JSL Garo_Healing
assert pc() == $059577, "Garo contact hook exceeds four bytes"

; @hook Garo_Prep kind=jsl target=Garo_Prep
; @source usdasm/bank_06.asm:SpritePrep_DesertStatue ($068F4D)
; Hide completed Garo before its first draw after loading the area.
assert read3($068F4D) == $0B6AAD, "Garo prep load moved"
assert read3($068F50) == $0D909D, "Garo prep store moved"
org $068F4D
  JSL Garo_Prep
  NOP #2
assert pc() == $068F53, "Garo prep hook exceeds six bytes"
pullpc

Garo_Prep:
{
  PHB : PHK : PLB
  JSR Garo_IsMinesNPC : BCC .original
  LDA.l GaroMaskOwned : CMP.b #$01 : BNE .original
    STZ.w SprState, X
  .original
  PLB
  ; Reproduce both overwritten instructions for all sprite $57 instances.
  LDA.w $0B6A : STA.w $0D90, X
  RTL
}

Garo_Healing:
{
  PHB : PHK : PLB
  JSR Garo_IsMinesNPC : BCS .garo
    PLB
    JML Sprite_CheckDamageToPlayerSameLayer

  .garo
  ; The original function continues after this JSL. Its negative-action
  ; guard must prevent the global $02F0 statue trigger from moving Garo.
  LDA.b #$80 : STA.w SprAction, X
  LDA.l GaroMaskOwned : CMP.b #$01 : BNE .unowned
    STZ.w SprState, X
    PLB
    CLC
    RTL

  .unowned
  JSL Sprite_PlayerCantPassThrough
  LDA.b $10 : CMP.b #$09 : BNE .done
  LDA.w SprFloor, X : CMP.b $EE : BNE .done
  ; Wolf shares the flute action but Y digs; it cannot perform Healing.
  LDA.w $02B2 : CMP.b #$03 : BEQ .done ; CurrentMask (Masks assemble later)
  LDA.w $0202 : CMP.b #$0D : BNE .done ; logical Ocarina
  LDA.w $0304 : CMP.b #$08 : BNE .done ; effective flute action
  LDA.w CurrentSong : CMP.b #$01 : BNE .done
  LDA.b SongFlag : CMP.b #$01 : BNE .done
  LDA.b $3A : AND.b #$40 : BEQ .done ; active flute animation
  ; Ocarina sets $03F0=$80 only when a new song starts. Module09 runs Link
  ; before sprites ($02A5A2 -> $02A4B1), so Garo sees $80 on the cast frame.
  ; A sticky SongFlag or walking closer later cannot win.
  LDA.w $03F0 : CMP.b #$80 : BNE .done

  ; Full 16-bit coordinates: a low-byte match across screens is not nearby.
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  LDA.w SprY, X : STA.b $02
  LDA.w SprYH, X : STA.b $03
  REP #$20
  LDA.b $22 : SEC : SBC.b $00 : CLC : ADC.w #$0030
  CMP.w #$0060 : BCS .far
  LDA.b $20 : SEC : SBC.b $02 : CLC : ADC.w #$0030
  CMP.w #$0060 : BCS .far
  SEP #$20

  LDA.b #$01 : STA.l GaroMaskOwned
  STZ.b SongFlag ; consume only this successful local Healing interaction
  JSL Sprite_SpawnPoofGarnish
  LDA.b #$2D : STA.w $012F ; milestone jingle
  STZ.w SprState, X
  .done
  PLB
  CLC
  RTL

  .far
  SEP #$20
  BRA .done
}

; C=1 only for the existing outdoor Garo placement's area. No new placement,
; dungeon/story flag write, or replacement of other vanilla desert statues.
Garo_IsMinesNPC:
{
  LDA.b $1B : BNE .no
  LDA.b $8B : BNE .no
  LDA.b $8A : CMP.b #$36 : BNE .no
  SEC
  RTS
  .no
  CLC
  RTS
}

endif
