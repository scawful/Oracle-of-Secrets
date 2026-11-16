; D3's confiscated blade. Armory mode uses the selected room54 worktable;
; the preserved prototype uses object129. A restores the captured sword
; and plays its native silent pose.
; Diagnostic feature only. Normal sprite $62 and all ordinary sheets retain
; their behavior; the two per-slot markers identify only the staged actor.
if !ENABLE_D3_PRISON_CELL65 == 1 && !DISABLE_SPRITES == 0

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
  STZ.w SprAction, X
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
  ; Expanded bank52 does not mirror low WRAM. Behavior uses DB00.
  PHB : LDA.b #$00 : PHA : PLB
  LDA.w SprAction, X : BEQ .idle
  JSR D3Prison_BladePoseTick
  PLB : RTL
  .idle
  JSR D3Prison_BladeRoomEligible : BCS .active
  STZ.w SprState, X
  PLB
  RTL
  .active
  JSR D3Prison_BladeDraw
  JSL Sprite_CheckActive : BCC .reject
  LDA.b $F6 : AND.b #$80 : BEQ .reject ; newly pressed A
  LDA.b $EE : BNE .reject             ; the plinth is on layer0
  LDA.b $2F : BNE .reject             ; face up from the reachable south edge
  ; Player control runs before sprites. A with Boots starts state11 on this
  ; same frame; allow only that initial dash, not an already running dash.
  LDA.b $5D : BEQ .player_ready
  CMP.b #$11 : BNE .reject
  LDA.w $0374 : CMP.b #$1D : BNE .reject
  LDA.w $0372 : CMP.b #$01 : BNE .reject
  .player_ready
  LDA.w $02B2 : BNE .reject           ; untransformed Link can take the blade
  JSL $07F4D0 : BCS .reject           ; native CheckIfLinkIsBusy

  BRA .contact
  .reject
  PLB : RTL
  .contact
  ; The plinth's collision stops Link at Y=$0A90. Use his top/center, not
  ; his feet (which are another16px lower), and only admit the south front.
  ; Full16-bit positions avoid room-edge low-byte wrap.
  ; Contact follows this actor, so moving the accepted plinth later does not
  ; leave a hidden pickup at its previous position.
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20 : STA.b $00 : SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20 : STA.b $02
  LDA.b $22 : CLC : ADC.w #$0008
  SEC : SBC.b $00 : CLC : ADC.w #$0010
  CMP.w #$0021 : BCS .far
  LDA.b $20 : SEC : SBC.b $02
  CMP.w #$0008 : BCC .far
  CMP.w #$0021 : BCS .far
  SEP #$20
  ; Native allocator searches 4..0 and may replace effects when full. Refuse
  ; first instead: no eviction and no reclaim without room for its display.
  JSR D3Prison_BladeReceiptSlot : BCC .done
  JSL D3Prison_Reclaim : BCC .done
  LDA.b $F6 : AND.b #$7F : STA.b $F6
  LDA.b #$01 : STA.w SprAction, X
  PHX : PHY
  LDA.l Sword : DEC A : TAY ; existing item00..03 matches restored sword1..4
  LDA.b #$02 : STA.w $02E9 ; native sprite receipt: no text/victory scene
  JSL $0799AD
  ; Native receipt $0987AE deliberately skips these for item00 (uncle's
  ; fighter gear). Our reclaim bypasses that gear grant, so refresh the
  ; restored fighter sword here. Higher swords already refresh natively.
  LDA.l Sword : CMP.b #$01 : BNE .refreshed
  JSL $00D2C8
  JSL $1BED03
  .refreshed
  PLY : PLX
  ; Same native normal-pose state, with type2's silent finite receipt timer.
  STZ.w $0308
  ; The accepted pickup owns the fresh A press; cancel its unused dash startup.
  ; Refusal paths above preserve all dash state.
  STZ.w $0372 : STZ.w $0374 : STZ.w $02F1
  STZ.b $3A : STZ.b $3B : STZ.b $3C : STZ.b $5E : STZ.b $50
  STZ.w $0301 : STZ.w $037A : STZ.w $0300
  LDA.b #$15 : STA.b $5D
  LDA.b #$01 : STA.w $02DA : STA.w $037B
  .done
  PLB
  RTL
  .far
  SEP #$20
  BRA .done
}

D3Prison_BladeReceiptSlot:
{
  PHY
  LDY.b #$04
  .receipt
    LDA.w $0C4A, Y : CMP.b #$22 : BEQ .no
    DEY : BPL .receipt
  LDY.b #$04
  .empty
    LDA.w $0C4A, Y : BEQ .yes
    DEY : BPL .empty
  .no
  PLY : CLC : RTS
  .yes
  TYA : STA.w SprMiscB, X
  PLY : SEC : RTS
}

D3Prison_BladePoseTick:
{
  ; Native type2 receipt clears $02E9 through the $08C43B hook before retiring its slot
  ; at $08C4E1, but deliberately leaves the player pose for this owner.
  ; Require our slot empty, our pose, and no replacement receipt elsewhere.
  LDY.w SprMiscB, X
  CPY.b #$05 : BCS .despawn
  LDA.w $0C4A, Y : CMP.b #$22 : BEQ .wait
  CMP.b #$00 : BNE .despawn
  LDA.b $5D : CMP.b #$15 : BNE .despawn
  LDA.w $02E9 : BEQ .check_receipts
  CMP.b #$02 : BNE .despawn
  .check_receipts
  LDY.b #$04
  .find_receipt
    LDA.w $0C4A, Y : CMP.b #$22 : BEQ .despawn
    DEY : BPL .find_receipt
  STZ.b $5D
  STZ.w $02DA : STZ.w $037B : STZ.w $02D8
  STZ.w $02E4 : STZ.w $02E9 : STZ.w $0FC1
  .despawn
  STZ.w SprState, X
  .wait
  RTS
}

; Native receipt has already allocated its slot and pushed X at $09860F.
; Only our active marked sprite takes the graphics-only prefix bypass. This
; avoids re-granting fighter gear/shield, sword downgrade or Master Sword
; ambience/progression. Native graphics, position, timer and draw remain intact.
D3Prison_BladeReceiptGraphics:
{
  PHP : PHX : PHY
  TXY
  LDA.w $02E9 : CMP.b #$02 : BNE .native
  LDA.b $10 : CMP.b #$07 : BNE .native
  LDA.w $040C : CMP.b #$10 : BNE .native
  LDA.b $1B : CMP.b #$01 : BNE .native
  LDA.b $A1 : BNE .native
  LDA.b $A0 : CMP.b #$54 : BNE .native
  LDA.w $02D8 : CMP.b #$04 : BCS .native
  LDX.b #$0F
  .find
    LDA.w SprState, X : BEQ .next
    LDA.w SprType, X : CMP.b #$62 : BNE .next
    LDA.w SprSubtype, X : CMP.b #!D3Prison_BladeMarker : BNE .next
    LDA.w SprMiscA, X : CMP.b #!D3Prison_BladeMarker2 : BNE .next
    LDA.w SprAction, X : CMP.b #$01 : BNE .next
    TYA : CMP.w SprMiscB, X : BEQ .graphics
    .next
    DEX : BPL .find
  .native
  PLY : PLX : PLP
  LDY.w $02D8
  BEQ .uncle
  JML $09862A
  .uncle
  JML $098615
  .graphics
  PLY : PLX : PLP
  JML $09877A
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
if !ENABLE_D3_PRISON_ARMORY == 1
  LDA.b #$01 : STA.b $06
else
  LDA.b #$06 : STA.b $06
endif
  STZ.b $07
  LDA.b #.tiles : STA.b $08
  LDA.b #.tiles>>8 : STA.b $09
  ; Native tabulated OAM reads both this ROM table and low WRAM through DBR.
  PHB : LDA.b #$38 : PHA : PLB
  JSL $05DF75 ; SpriteDraw_Tabulated_player_deferred, table in caller DB
  PLB
  RTS
  ; Exact native Master Sword six-cell layout ($058D96-$058DA7), expanded
  ; into native tabulated form. A low-ROM bank keeps native WRAM mirrors.
  pushpc
  !prison_draw_guard = $38F100
  while !prison_draw_guard < $38F130
    assert read2(!prison_draw_guard) == 0, "Prison blade draw table reservation occupied"
    !prison_draw_guard #= !prison_draw_guard+2
  endwhile
  org $38F100 ; @hook module=Dungeons kind=data name=PrisonBladeDrawTable protected_size=48
  .tiles
if !ENABLE_D3_PRISON_ARMORY == 1
  ; One16x16 OAM entry: source chars06/07/16/17, palette4 -> CGRAM row12.
  ; Actor remains at128,128; art starts120,116 to lie on the worktable.
  ; Floor0 native props $29 EOR $10 -> OBJ priority3 ($39).
  ; Keep the displayed blade above the high-priority armory tabletop only.
  dw -8, -12 : db $C6, $10, $00, $02
  fillbyte $00 : fill 40
else
  dw -8, -8 : db $C3, $00, $00, $00
  dw  0, -8 : db $C4, $00, $00, $00
  dw -8,  0 : db $D3, $00, $00, $00
  dw  0,  0 : db $D4, $00, $00, $00
  dw -8,  8 : db $E0, $00, $00, $00
  dw  0,  8 : db $F0, $00, $00, $00
endif
  assert pc() == $38F130
  pullpc
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

if !ENABLE_D3_PRISON_ARMORY == 1
; Context-only sheet pointer. The global table, logical request/cache IDs,
; and caller-selected HIGH BG / LOW sprite conversion stay unchanged.
; Entry M8/X16, X=requested sheet. Preserve P/X/Y/DBR/D, affect only pointer DP.
D3Prison_ArmorySpritePtr00:
{
  PHP
  CPX.w #$0036 : BNE .done
  JSR D3Prison_ArmoryContext : BCC .done
  LDA.b #WallSel_Private_prison_armory_slot3 : STA.b $00
  LDA.b #WallSel_Private_prison_armory_slot3>>8 : STA.b $01
  LDA.b #WallSel_Private_prison_armory_slot3>>16 : STA.b $02
.done
  PLP : RTL
}
D3Prison_ArmorySpritePtrCA:
{
  PHP
  CPX.w #$0036 : BNE .done
  JSR D3Prison_ArmoryContext : BCC .done
  BRA D3Prison_ArmoryWriteCA
.done
  PLP : RTL
}
D3Prison_ArmoryBgPtrCA:
{
  PHP
  CPX.w #$0008 : BNE .done
  JSR D3Prison_ArmoryContext : BCS D3Prison_ArmoryWriteCA
.done
  PLP : RTL
}
D3Prison_ArmoryWriteCA:
  LDA.b #WallSel_Private_prison_armory_slot3 : STA.b $C8
  LDA.b #WallSel_Private_prison_armory_slot3>>8 : STA.b $C9
  LDA.b #WallSel_Private_prison_armory_slot3>>16 : STA.b $CA
  PLP : RTL
D3Prison_ArmoryContext:
{
  LDA.l $7E001B : CMP.b #$01 : BNE .no
  LDA.l $7E00A1 : BNE .no
  LDA.l $7E00A0 : CMP.b #$54 : BNE .no
  LDA.l $7E040C : CMP.b #$10 : BNE .no
  LDA.l $7E0AA2 : CMP.b #$19 : BNE .no
  SEC : RTS
.no
  CLC : RTS
}
endif

if !ENABLE_D3_PRISON_ARMORY == 1
  ; Object-dispatch ABI: M/X=16, DP=0, Y=tilemap byte offset. Preserve all
  ; registers, flags and DBR; no new scratch, collision or palette ownership.
  ; Only room $0054, subtype $0D, native primary pointer $7E2000 qualifies.
  ; Copy six-by-four floor words at low priority BEFORE the table overwrites
  ; them. The worktable data uses high priority, so BGACT3 shows the copied
  ; floor only through raw-zero table pixels; collision ignores priority.
D3Prison_ArmoryFloorUnderlay:
{
    PHP : PHA : PHX : PHY
    CMP.w #$000D : BNE .underlay_done
    LDA.l $7E00A0 : CMP.w #$0054 : BNE .underlay_done
    LDA.b $BF : CMP.w #$2000 : BNE .underlay_done
    LDA.b $C0 : CMP.w #$7E20 : BNE .underlay_done
    TYA : TAX
    LDY.w #$0004
    .underlay_row
      LDA.l $7E2000,X : AND.w #$DFFF : STA.l $7E4000,X
      LDA.l $7E2002,X : AND.w #$DFFF : STA.l $7E4002,X
      LDA.l $7E2004,X : AND.w #$DFFF : STA.l $7E4004,X
      LDA.l $7E2006,X : AND.w #$DFFF : STA.l $7E4006,X
      LDA.l $7E2008,X : AND.w #$DFFF : STA.l $7E4008,X
      LDA.l $7E200A,X : AND.w #$DFFF : STA.l $7E400A,X
      TXA : CLC : ADC.w #$0080 : TAX
      DEY : BNE .underlay_row
    .underlay_done
    PLY : PLX : PLA : PLP
    RTL
}
endif

pushpc
assert read4($098610) == $D002D8AC && read1($098614) == $15, "Prison receipt prefix changed"
org $098610 ; @hook module=Dungeons kind=jml name=D3Prison_BladeReceiptGraphics target=D3Prison_BladeReceiptGraphics expected_m=8 expected_x=8
  JML D3Prison_BladeReceiptGraphics : NOP
assert pc() == $098615
assert read4($0588D6) == $1AC910A5, "Prison blade dispatch preimage changed"
org $0588D6 ; @hook module=Dungeons name=D3Prison_BladeDispatch kind=jml target=D3Prison_BladeDispatch expected_m=8 expected_x=8
  JML D3Prison_BladeDispatch
assert pc() == $0588DA
assert read4($00E1ED) == $7EC2FF8F, "Prison blade initial sheet preimage changed"
org $00E1ED ; @hook module=Dungeons name=D3Prison_BladeSheet_Initial kind=jsl target=D3Prison_BladeSheet expected_m=8 expected_x=16
  JSL D3Prison_BladeSheet
assert pc() == $00E1F1
assert read4($00D775) == $7EC2FF8F, "Prison blade transition sheet preimage changed"
org $00D775 ; @hook module=Dungeons name=D3Prison_BladeSheet_Transition kind=jsl target=D3Prison_BladeSheet expected_m=8 expected_x=16
  JSL D3Prison_BladeSheet
assert pc() == $00D779
pullpc
endif
