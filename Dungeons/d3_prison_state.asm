; D3 capture transactions. Diagnostic-only until the cell, actors and continue
; contract are authored. No helper chooses an entrance or rewrites room data.
; Dungeon code is included before Core/sprite_macros.asm, so use SEP #$20.
; Caller: native mode, DP=0. All helpers preserve X/Y, DB and M/X; A is scratch.
; Capture/Reclaim/CompleteEscape return C=1 only when a transaction committed.
; The receipt hook only arms the later hall ambush and retains Farore's callout.

if !ENABLE_D3_PRISON_SEQUENCE == 1

; Ancilla22_ItemReceipt .check_if_hp, native M8/X8, X=item ancilla slot.
; Chest receipts bypass .not_in_water; this common completion runs after text.
; @source usdasm/bank_08.asm:$08C43B-$08C440
Oracle_PrisonSequence_PostMeadowBlade:
{
  PHP
  SEP #$20
  JSR D3Prison_InDungeon : BCC .done
  LDA.l $7E00A0 : CMP.b #$56 : BNE .done
  LDA.l $7E0C5E, X : CMP.b #$01 : BNE .done ; exact sword receipt
  LDA.l Sword : CMP.b #$02 : BNE .done
  LDA.l CastleAmbushFlags
  AND.b #!CastleAmbush_HasBeenCaptured|!CastleAmbush_HasEscaped|!CastleAmbush_BladeReclaimed
  BNE .done
  LDA.l CastleAmbushFlags : ORA.b #!CastleAmbush_AmbushPending
  STA.l CastleAmbushFlags
  .done
  PLP
  STZ.w $02E9
  LDA.w $0C5E, X ; replay native A/N/Z after restoring the caller status
  RTL
}

; The hall scene calls this only after its arrest staging is ready. This leaf
; commits ownership atomically; the scene must then use its validated cell load.
; Repeated contact cannot overwrite the stored blade with Sword=0.
D3Prison_Capture:
{
  PHP
  SEP #$20
  JSR D3Prison_InPlayerControl : BCC .no
  LDA.l $7E00A0 : CMP.b #$56 : BNE .no
  LDA.l CastleAmbushFlags : AND.b #$0F
  CMP.b #!CastleAmbush_AmbushPending : BNE .no
  LDA.l Sword : CMP.b #$02 : BNE .no
  LDA.l CastleAmbushFlags : AND.b #$80 : PHA ; unrelated bit retained
  LDA.l Sword : ASL #4
  ORA.b #!CastleAmbush_HasBeenCaptured
  ORA $01, S
  STA.l CastleAmbushFlags
  PLA
  LDA.b #$00 : STA.l Sword
  PLP
  SEC
  RTL
  .no
  PLP
  CLC
  RTL
}

; Called by the room-$54 blade-table actor after interaction is accepted.
; No ordinary item receipt: that would repeat Farore's first-chest telepathy.
; The actor owns the silent pose/HUD refresh. Never downgrade a later sword.
D3Prison_Reclaim:
{
  PHP
  SEP #$20
  JSR D3Prison_InPlayerControl : BCC .no
  LDA.l $7E00A0 : CMP.b #$54 : BNE .no
  LDA.l CastleAmbushFlags : AND.b #$0F
  CMP.b #!CastleAmbush_HasBeenCaptured : BNE .no
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_SwordMask
  LSR #4
  BEQ .no
  CMP.b #$05 : BCS .no
  PHA
  LDA.l Sword : CMP.b #$05 : BCS .bad_sword ; includes smith-held $FF
  CMP $01, S : BCS .keep_better_sword
  PLA : STA.l Sword
  BRA .commit
  .keep_better_sword
  PLA
  .commit
  LDA.l CastleAmbushFlags : ORA.b #!CastleAmbush_BladeReclaimed
  STA.l CastleAmbushFlags
  PLP
  SEC
  RTL
  .bad_sword
  PLA
  .no
  PLP
  CLC
  RTL
}

; Only the outward room-$55 exit calls this after selecting Module08, while
; the old room/dungeon context still exists. Merely entering room55, changing
; rooms or running a Minish tag cannot complete the escape. The exit caller
; and its native timing remain to be qualified before the feature is enabled.
D3Prison_CompleteEscape:
{
  PHP
  SEP #$20
  JSR D3Prison_InDungeon : BCC .no
  LDA.l $7E0010 : CMP.b #$08 : BNE .no
  LDA.l $7E00A0 : CMP.b #$55 : BNE .no
  LDA.l CastleAmbushFlags : AND.b #$0F
  CMP.b #!CastleAmbush_HasBeenCaptured|!CastleAmbush_BladeReclaimed
  BNE .no
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_SwordMask
  LSR #4
  BEQ .no
  CMP.b #$05 : BCS .no
  PHA
  LDA.l Sword : CMP.b #$05 : BCS .bad_sword
  CMP $01, S : BCC .bad_sword
  PLA
  LDA.l CastleAmbushFlags : ORA.b #!CastleAmbush_HasEscaped
  STA.l CastleAmbushFlags
  PLP
  SEC
  RTL
  .bad_sword
  PLA
  .no
  PLP
  CLC
  RTL
}

D3Prison_InPlayerControl:
{
  LDA.l $7E0010 : CMP.b #$07 : BNE .no
  LDA.l $7E0011 : BNE .no
  JSR D3Prison_InDungeon
  RTS
  .no
  CLC
  RTS
}

D3Prison_InDungeon:
{
  LDA.l $7E001B : CMP.b #$01 : BNE .no
  LDA.l $7E040C : CMP.b #$10 : BNE .no ; actual Kalyxo Castle slot
  LDA.l $7E00A1 : BNE .no              ; full room ID, not low-byte alias
  SEC
  RTS
  .no
  CLC
  RTS
}

pushpc
org $08C43B ; @hook module=Dungeons name=Oracle_PrisonSequence_PostMeadowBlade kind=jsl target=Oracle_PrisonSequence_PostMeadowBlade expected_m=8 expected_x=8
  JSL Oracle_PrisonSequence_PostMeadowBlade
  NOP #2
assert pc() == $08C441
pullpc

endif
