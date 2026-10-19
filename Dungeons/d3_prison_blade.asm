; D3's confiscated blade, on room $54's existing plinth (object $129,
; tile 14,15). No item receipt or dialogue: A restores the captured sword.
; Diagnostic feature only. Normal sprite $62 and all ordinary sheets retain
; their behavior; the two per-slot markers identify only the staged actor.
if !ENABLE_D3_PRISON_SEQUENCE == 1 && !DISABLE_SPRITES == 0

!D3Prison_BladeMarker = $D3
!D3Prison_BladeMarker2 = $54
!D3Prison_BladeX = $0880
!D3Prison_BladeY = $0A80

; End-of-list room loader, M8/X8, DP0. Preserve caller registers, DB and P;
; in particular $02 is the native room-list allocator's next free slot.
D3Prison_BladeStage:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB
  JSR D3Prison_BladeStageEligible : BCS .stage
  JMP .done
  .stage

  ; Repeated staging is harmless. Do not consume a second slot.
  LDX.b #$0F
  .duplicate
    LDA.w SprState, X : BEQ .next
    LDA.w SprType, X : CMP.b #$62 : BNE .next
    LDA.w SprSubtype, X : CMP.b #!D3Prison_BladeMarker : BNE .next
    LDA.w SprMiscA, X : CMP.b #!D3Prison_BladeMarker2 : BEQ .done
    .next
    DEX : BPL .duplicate
  LDX.b #$0F
  .find_slot
    LDA.w SprState, X : BEQ .spawn
    DEX : BPL .find_slot
    BRA .done
  .spawn
  LDA.b #$62 : STA.w SprType, X
  JSL $0DB818 ; SpritePrep_LoadProperties: reset stale slot fields + native62
  ; Bypass native62 Prep's +6/+6 adjustment; these are exact draw coordinates.
  LDA.b #$09 : STA.w SprState, X
  LDA.b #!D3Prison_BladeMarker : STA.w SprSubtype, X
  LDA.b #!D3Prison_BladeMarker2 : STA.w SprMiscA, X
  LDA.b #!D3Prison_BladeX&$FF : STA.w SprX, X
  LDA.b #!D3Prison_BladeX>>8 : STA.w SprXH, X
  LDA.b #!D3Prison_BladeY&$FF : STA.w SprY, X
  LDA.b #!D3Prison_BladeY>>8 : STA.w SprYH, X
  STZ.w SprFloor, X
  LDA.b #$40 : STA.w SprHitbox, X ; does not count toward kill-all room tags
  LDA.b #$01 : STA.w SprBulletproof, X
  LDA.b #$FF : STA.w $0BC0, X ; never write a room sprite-death bit
  STZ.w SprDrop, X
  .done
  PLB
  REP #$30
  PLY : PLX : PLA
  PLP
  RTL
}

D3Prison_BladeStageEligible:
{
  LDA.b $1B : CMP.b #$01 : BNE .no
  LDA.w $048F : BNE .no
  LDA.w $048E : CMP.b #$54 : BNE .no
  LDA.w $040C : CMP.b #$10 : BNE .no
  JSL D3Prison_ShouldResumeCell : BCC .no
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_BladeReclaimed
  BNE .no
  SEC : RTS
  .no
  CLC : RTS
}

; MasterSword_Main originally starts LDA $10 / CMP #$1A. Native bank05
; dispatch has an RTS return; custom handling jumps to an existing bank05
; RTS after its long call. All unmarked swords replay the original pair.
D3Prison_BladeDispatch:
{
  LDA.w SprSubtype, X : CMP.b #!D3Prison_BladeMarker : BNE .native
  LDA.w SprMiscA, X : CMP.b #!D3Prison_BladeMarker2 : BNE .native
  JSL D3Prison_BladeMain
  JML $058D95 ; native RTS, returns to SpriteModule_Active_Bank05
  .native
  LDA.b $10
  CMP.b #$1A
  JML $0588DA
}

; X=slot, native sprite M8/X8. Draw uses native tabulated OAM allocation,
; including offscreen clipping and layer/player priority. No fixed OAM slot.
D3Prison_BladeMain:
{
  PHB : PHK : PLB
  JSR D3Prison_BladeRoomEligible : BCS .active
  STZ.w SprState, X
  PLB
  RTL
  .active
  JSR D3Prison_BladeDraw
  JSL Sprite_CheckActive : BCC .done
  LDA.b $F6 : AND.b #$80 : BEQ .done ; newly pressed A
  LDA.b $EE : BNE .done             ; the plinth is on layer0
  LDA.b $2F : BNE .done             ; face up from the reachable south edge
  LDA.b $5D : BNE .done             ; ordinary player control
  LDA.w $02B2 : BNE .done           ; untransformed Link can take the blade
  JSL $07F4D0 : BCS .done           ; native CheckIfLinkIsBusy

  ; The plinth's collision stops Link at Y=$0A90. Use his top/center, not
  ; his feet (which are another16px lower), and only admit the south front.
  ; Full16-bit positions avoid room-edge low-byte wrap.
  REP #$20
  LDA.b $22 : CLC : ADC.w #$0008
  SEC : SBC.w #!D3Prison_BladeX : CLC : ADC.w #$0010
  CMP.w #$0021 : BCS .far
  LDA.b $20 : SEC : SBC.w #!D3Prison_BladeY
  CMP.w #$0008 : BCC .far
  CMP.w #$0021 : BCS .far
  SEP #$20
  JSL D3Prison_Reclaim : BCC .done
  LDA.b $F6 : AND.b #$7F : STA.b $F6
  ; Use the same graphics/palette refresh as native sword receipts, without
  ; their ancilla, text, victory music or progression writes. X/Y are clobbered
  ; by decompression, so retain the actor slot before removing only this actor.
  PHX : PHY
  JSL $00D2C8 ; DecompressSwordGraphics
  JSL $1BED03 ; Palettes_Load_Sword
  PLY : PLX
  .despawn
  STZ.w SprState, X
  .done
  PLB
  RTL
  .far
  SEP #$20
  BRA .done
}

D3Prison_BladeRoomEligible:
{
  LDA.b $1B : CMP.b #$01 : BNE .no
  LDA.b $A1 : BNE .no
  LDA.b $A0 : CMP.b #$54 : BNE .no
  LDA.w $040C : CMP.b #$10 : BNE .no
  JSL D3Prison_ShouldResumeCell : BCC .no
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_BladeReclaimed
  BNE .no
  SEC : RTS
  .no
  CLC : RTS
}

D3Prison_BladeDraw:
{
  LDA.b #$06 : STA.b $06
  STZ.b $07
  LDA.b #.tiles : STA.b $08
  LDA.b #.tiles>>8 : STA.b $09
  JSL $05DF75 ; SpriteDraw_Tabulated_player_deferred, table in caller DB
  RTS
  ; Exact native Master Sword six-cell layout ($058D96-$058DA7).
  .tiles
  dw -8, -8 : db $C3, $00, $00, $00
  dw  0, -8 : db $C4, $00, $00, $00
  dw -8,  0 : db $D3, $00, $00, $00
  dw  0,  0 : db $D4, $00, $00, $00
  dw -8,  8 : db $E0, $00, $00, $00
  dw  0,  8 : db $F0, $00, $00, $00
}

; Room header sprite group21 becomes runtime61 at native $01B64B (+40).
; Group61=[46,49,1C,52]. Rats/ropes/keese use slot2 $80-$BB exclusively;
; slot3 is unused in room54. Select existing sword sheet36 before the native
; cache write so BOTH cold and transition paths convert it with the LOW
; palette half. Replacing only the decompressor's pointer would incorrectly
; retain sheet52's high-palette conversion. No source sheet bytes are changed.
; Adjacent rooms55/64 explicitly request52, restoring their normal slot3.
; ABI: M8, X/Y16, DB00, A=requested slot3 sheet. Preserve P/X/Y/DB, return
; selected A and perform the displaced STA.l $7EC2FF.
D3Prison_BladeSheet:
{
  PHP : PHA
  CMP.b #$52 : BNE .native
  LDA.b $1B : CMP.b #$01 : BNE .native
  LDA.b $A1 : BNE .native
  LDA.b $A0 : CMP.b #$54 : BNE .native
  LDA.w $040C : CMP.b #$10 : BNE .native
  LDA.w $0AA3 : CMP.b #$61 : BNE .native
  PLA
  LDA.b #$36
  BRA .store
  .native
  PLA
  .store
  STA.l $7EC2FF
  PLP
  RTL
}

pushpc
org $0588D6 ; @hook module=Dungeons name=D3Prison_BladeDispatch kind=jml target=D3Prison_BladeDispatch expected_m=8 expected_x=8
  JML D3Prison_BladeDispatch
assert pc() == $0588DA
org $00E1ED ; @hook module=Dungeons name=D3Prison_BladeSheet_Initial kind=jsl target=D3Prison_BladeSheet expected_m=8 expected_x=16
  JSL D3Prison_BladeSheet
assert pc() == $00E1F1
org $00D775 ; @hook module=Dungeons name=D3Prison_BladeSheet_Transition kind=jsl target=D3Prison_BladeSheet expected_m=8 expected_x=16
  JSL D3Prison_BladeSheet
assert pc() == $00D779
pullpc
endif
