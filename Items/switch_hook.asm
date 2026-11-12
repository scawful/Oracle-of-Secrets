; =========================================================
; Switch Hook prototype: exchange with a stationary ice block or statue.
; Ordinary Hookshot/Goldstar retain their existing collision path.
;
; Target contract: live $D5 ice block or native $1C movable statue,
; grounded, stopped, same dungeon/layer, within 128px,
; and safe floor under both footprints. The Elegy of Stone echo ($1C with
; SprFrame=!Stone_Marker) is not pushable and is never a target.
; Ruling 2026-10-19: "Ice blocks + statues" (no pots, no enemies).
; This prototype intentionally has no outdoor or enemy exchange.
; Link's feet occupy sprite Y+8..15, so Link Y = block Y-8.
; Both actors recompute $0642 from their own position every active frame,
; after Ancilla_Main, so a moved statue presses or releases a plate itself.
;
; Swap beat (Oracle of Ages, oracles-disasm object/switchHook): the hook
; clings 17 frames, then Link and the target rise 16 frames, exchange in
; one frame, fall 16 frames. From the swap on, the camera steps (vanilla
; Underworld_HandleCamera, called from a Module07 hook because the hook
; state zeroes $30/$31) until Link is in the follow box or the room limit
; stops it; only then does the chain end and control return.
; Link never moves through space, so no $037E drag is involved.
;
; $0268       : beat counter (0 = no beat; read only while shot tag is active)
; $0269       : target sprite slot
; $026A/$026B : $E2/$E8 low bytes seen on the previous beat frame
; $07F8       : active-shot tag ($A5, zero otherwise)
; $07F9-$07FA : launch dungeon room
; $07FB       : launch layer
; $07FC       : launch module
; $07FD       : Bombchu wall-following state (owned by Items/bombchu.asm)
; $07FE       : Bombchu allocator latch (owned by Items/bombchu.asm)
; $07FF       : Garo lunge timer (owned by Masks/garo_mask.asm)
; The latch is shot-owned, never inferred from the current menu icon.
; =========================================================

; goldstar.asm leaves its expanded cursor on the pushpc stack.
pullpc

!SwitchHookActive = $07F8
!SwitchHookRoom   = $07F9
!SwitchHookLayer  = $07FB
!SwitchHookMode   = $07FC
!SwitchHookTag    = $A5
!SwitchHookStatue = $1C               ; usdasm Sprite_1C_Statue ($06C0E8)
!SwitchHookBeat   = $0268             ; vanilla free RAM $0224-$027F
!SwitchHookTarget = $0269
!SwitchHookCamX   = $026A
!SwitchHookCamY   = $026B
!SwitchHookCling  = 17                ; Ages: 1+4+4+4+4 cling frames
!SwitchHookRise   = 16                ; Ages: z -1/frame for 16 frames
!SwitchHookSwap   = !SwitchHookCling+!SwitchHookRise+1
!SwitchHookLand   = !SwitchHookSwap+16
!SwitchHookSfx    = $0F               ; SFX3: existing magical effect sound

assert !SwitchHookMode < $0800, "Switch Hook exceeds its WRAM reservation"

pushpc
; @hook SwitchHook_AncillaEntry kind=jml target=SwitchHook_AncillaEntry
; @source usdasm/bank_08.asm:Ancilla1F_Hookshot ($08BD74)
; @assumption M=8, X=8, DBR=$08, X=ancilla slot.
; Link state $13 skips Link_HandleYItem, so the flight owns its own cleanup.
; Replaces LDA $11 / BNE .just_draw.
assert read2($08BD74) == $11A5, "Vanilla hookshot entry moved"
org $08BD74
  JML SwitchHook_AncillaEntry
assert pc() == $08BD78, "Switch Hook entry gateway exceeds four bytes"

; @hook SwitchHook_SpriteContact kind=jml target=SwitchHook_SpriteContact
; @source usdasm/bank_08.asm:Hookshot_Extending.do_bother ($08BDD7)
; @assumption M=8, X=8, DBR=$08, X=ancilla slot; entered by JSR caller.
; Replaces JSR Ancilla_CheckSpriteCollision / BCC .ignore_collision.
assert read3($08BDD7) == $8D6820, "Vanilla hookshot sprite collision call moved"
org $08BDD7
  JML SwitchHook_SpriteContact
  NOP
assert pc() == $08BDDC, "Switch Hook collision gateway exceeds five bytes"

; @hook SwitchHook_TileAnchor kind=jml target=SwitchHook_TileAnchor
; @source usdasm/bank_08.asm:Hookshot_ExtraCollisionLogic ($08BECA)
; @assumption M=8, X=8, DBR=$08, X=ancilla slot.
; Replaces LDA $0C5E,X / CMP #$04. Switch Hook never pulls Link to walls.
assert read3($08BECA) == $0C5EBD, "Vanilla hookshot anchor check moved"
org $08BECA
  JML SwitchHook_TileAnchor
  NOP
assert pc() == $08BECF, "Switch Hook anchor gateway exceeds five bytes"

; @hook SwitchHook_DungeonCamera kind=jsl target=SwitchHook_DungeonCamera
; @source usdasm/bank_02.asm:Module07_Dungeon ($0287E5)
; @assumption Runs every Module07 frame after Link and Underworld_HandleCamera,
; before LDA $E2 : PHA saves the camera around Sprite_Main.
; Replaces REP #$21 : LDA $E2; the target ends with the same two instructions.
assert read2($0287E5) == $21C2, "Vanilla Module07 camera save moved"
assert read2($0287E7) == $E2A5, "Vanilla Module07 camera save moved"
assert read1($028053) == $6B, "Switch Hook camera RTL trampoline moved"
org $0287E5
  JSL SwitchHook_DungeonCamera
assert pc() == $0287E9, "Switch Hook camera gateway exceeds four bytes"
pullpc

; Called once from BeginGoldstarOrHookshot, before ancilla creation.
; Entry/exit: preserve full A/X/Y, P and DBR; no caller scratch used.
SwitchHook_Init:
{
  PHP : REP #$30 : PHA : PHX : PHY : PHB
  PHK : PLB : SEP #$30
  STZ.w !SwitchHookActive
  LDA.w $0202 : CMP.b #$1D : BNE .done
  LDA.w $0304 : CMP.b #$0E : BNE .done
  LDA.l SwitchHookOwned : CMP.b #$01 : BNE .done
  STZ.w !SwitchHookBeat
  STZ.w !SwitchHookTarget
  LDA.b $10 : STA.w !SwitchHookMode
  LDA.b $EE : STA.w !SwitchHookLayer
  %a16()
  LDA.b $A0 : STA.w !SwitchHookRoom
  %a8()
  LDA.b #!SwitchHookTag : STA.w !SwitchHookActive
  .done
  PLB : REP #$30 : PLY : PLX : PLA : PLP
  RTL
}

; The vanilla hookshot completion path calls this even after a missed shot.
; Entry/exit: A/X/Y/DBR/P preserved, works with either accumulator width.
SwitchHook_Clear:
{
  PHP : REP #$30 : PHA : PHX : PHY : SEP #$30
  LDA.w !SwitchHookActive : CMP.b #!SwitchHookTag : BNE .idle
  LDA.w !SwitchHookBeat : BEQ .idle
  ; Abort or finish: put both actors back on the ground.
  LDY.w !SwitchHookTarget
  LDA.b #$00 : STA.w SprHeight,Y
  STZ.b $24 : STZ.b $25
  STZ.b $30 : STZ.b $31
  STZ.w !SwitchHookBeat
  .idle
  STZ.w !SwitchHookActive
  STZ.w !SwitchHookRoom : STZ.w !SwitchHookRoom+1
  STZ.w !SwitchHookLayer : STZ.w !SwitchHookMode
  REP #$30 : PLY : PLX : PLA
  PLP
  RTL
}

; Root gameplay tick calls this before item/sprite processing.
; Cancels the owned chain on transition, equipment/mask action change or
; room/layer change. A missing chain only clears the latch; the vanilla
; completion path retains ownership of its normal recovery animation.
; Entry/exit: full A/X/Y, P, DBR preserved; no caller scratch used.
SwitchHook_Tick:
{
  PHP : REP #$30 : PHA : PHX : PHY : PHB
  PHK : PLB : SEP #$30
  LDA.w !SwitchHookActive : CMP.b #!SwitchHookTag : BEQ .active
  JMP .done
  .active
  LDA.b $10 : CMP.w !SwitchHookMode : BNE .cancel
  LDA.b $11 : BEQ .submodule_ok
  ; A swapped statue or Link can trip a plate room tag mid-beat. Those
  ; in-room submodules pause the beat (AncillaEntry) instead of cancelling;
  ; every transition submodule still cancels.
  LDA.w !SwitchHookBeat : BEQ .cancel
  LDA.b $11
  CMP.b #$05 : BEQ .submodule_ok          ; Module07_05_ControlShutters
  CMP.b #$16 : BEQ .submodule_ok          ; Module07_16_UpdatePegs
  CMP.b #$17 : BNE .cancel                ; Module07_17_PressurePlate
  .submodule_ok
  LDA.w $0202 : CMP.b #$1D : BNE .cancel
  LDA.w $0304 : CMP.b #$0E : BNE .cancel
  LDA.l SwitchHookOwned : CMP.b #$01 : BNE .cancel
  LDA.b $EE : CMP.w !SwitchHookLayer : BNE .cancel
  %a16()
  LDA.b $A0 : CMP.w !SwitchHookRoom
  %a8()
  BNE .cancel
  LDX.b #$04
  .chain
  LDA.w $0C4A,X : CMP.b #$1F : BEQ .done
  DEX : BPL .chain
  JSL SwitchHook_Clear
  BRA .done
  .cancel
  LDX.b #$04
  .delete
  LDA.w $0C4A,X : CMP.b #$1F : BNE .next
  STZ.w $0C4A,X
  .next
  DEX : BPL .delete
  STZ.w $037E : STZ.w $037B : STZ.w $0300 : STZ.w $0112
  LDA.w $037A : AND.b #$FB : STA.w $037A
  LDA.b $3A : AND.b #$BF : STA.b $3A
  LDA.b $50 : AND.b #$FE : STA.b $50
  LDA.b $5D : CMP.b #$13 : BNE .clear
  STZ.b $5D
  .clear
  JSL SwitchHook_Clear
  .done
  PLB : REP #$30 : PLY : PLX : PLA : PLP
  RTL
}

; Called by Goldstar_SetChainProperties after ordinary OAM flags are formed.
; M=8; preserves X/Y/DBR and all flags. Only the active shot uses palette 3.
SwitchHook_ChainProperties:
{
  PHP : PHA
  LDA.w !SwitchHookActive : CMP.b #!SwitchHookTag : BNE .ordinary
  PLA : AND.b #$F1 : ORA.b #$06
  PLP : RTL
  .ordinary
  PLA : PLP : RTL
}

SwitchHook_AncillaEntry:
{
  JSL SwitchHook_Tick
  LDA.w $0C4A,X : CMP.b #$1F : BNE .deleted
  LDA.w !SwitchHookActive : CMP.b #!SwitchHookTag : BNE .flight
  LDA.w !SwitchHookBeat : BEQ .flight
  LDA.b $11 : BEQ .beat       ; plate/shutter/peg submodule: hold the beat
  LDA.w !SwitchHookBeat : CMP.b #!SwitchHookCling+1 : BCS .deleted
  BRA .paused                 ; draw as the beat would: hook only while clinging
  .beat
  JSL SwitchHook_Beat
  BCC .deleted                ; hidden frame, or the beat ended
  .paused
  JML $08BD9C                 ; draw the clinging hook only
  .flight
  LDA.b $11 : BNE .paused
  JML $08BD78
  .deleted
  JML $08BDA2
}

SwitchHook_SpriteContact:
{
  LDA.w !SwitchHookActive : CMP.b #!SwitchHookTag : BEQ .switch
  JSL Ancilla_CheckSpriteCollision_long
  BCC .continue
  JML $08BDDC                 ; preserve original collision result branch
  .continue
  JML $08BDFD
  .switch
  JSL SwitchHook_TryExchange
  BCC .continue
  JML $08BD9C                 ; beat started: draw the clinging hook only
}

SwitchHook_TileAnchor:
{
  LDA.w !SwitchHookActive : CMP.b #!SwitchHookTag : BEQ .retract
  LDA.w $0C5E,X : CMP.b #$04  ; replay original five bytes
  JML $08BECF
  .retract
  JSR SwitchHook_Retract
  JML $08BEDC                 ; draw chain, never set $037E drag latch
}

; M/X=8, DBR can be $08 or our code bank; X=hookshot ancilla.
; Calling this twice must not reverse an already retracting chain.
SwitchHook_Retract:
{
  LDA.w $0C54,X : BNE .done
  LDA.b #$01 : STA.w $0C54,X
  LDA.w $0C22,X : EOR.b #$FF : INC : STA.w $0C22,X
  LDA.w $0C2C,X : EOR.b #$FF : INC : STA.w $0C2C,X
  .done
  RTS
}

; Entry: M/X=8, X=ancilla; exit same widths, X/Y/DBR preserved, carry=swap.
; Scratch $00-$0F belongs to the ancilla collision caller at this boundary.
; $0A/$0C hold target Y/X, $0E target slot, $0F ancilla slot.
SwitchHook_TryExchange:
{
  PHB : PHK : PLB : PHX : PHY
  STX.b $0F
  JSR SwitchHook_ContextValid : BCC .no_swap
  LDY.b #$0F
  .next
  JSR SwitchHook_TargetValid : BCS .exchange
  LDA.w $0C54,X : BNE .no_swap
  DEY : BPL .next
  .no_swap
  PLY : PLX : PLB : CLC : RTL
  .exchange
  ; Start the swap beat. Positions change only on the hidden swap frame.
  TYA : STA.w !SwitchHookTarget
  LDA.b #$01 : STA.w !SwitchHookBeat
  LDA.b $E2 : STA.w !SwitchHookCamX
  LDA.b $E8 : STA.w !SwitchHookCamY
  STZ.b $30 : STZ.b $31
  STZ.w $037E
  LDA.b #$01 : STA.w $037B    ; Link stays unhittable for the whole beat
  PLY : PLX : PLB : SEC : RTL
}

; One beat frame. Entry M/X=8, X=ancilla; exit M/X=8, X preserved.
; Carry set: draw the clinging hook. Carry clear: draw nothing (the chain
; may have been deleted). Scratch $00-$0F is free at the ancilla boundary.
SwitchHook_Beat:
{
  PHB : PHK : PLB : PHY
  LDA.b $5D : CMP.b #$13 : BNE .abort
  LDY.w !SwitchHookTarget
  LDA.w SprState,Y : CMP.b #$09 : BNE .abort
  LDA.w !SwitchHookBeat : CMP.b #$FF : BEQ .finish  ; settle safety cap
  INC : STA.w !SwitchHookBeat
  CMP.b #!SwitchHookCling : BCC .cling
  BEQ .sfx
  CMP.b #!SwitchHookSwap : BCC .rise
  BEQ .swap
  CMP.b #!SwitchHookLand+1 : BCC .fall
  ; Landed: wait until the camera stopped moving on the previous frame.
  LDA.b $E2 : CMP.w !SwitchHookCamX : BNE .camera
  LDA.b $E8 : CMP.w !SwitchHookCamY : BNE .camera
  .finish
  STZ.w $0C4A,X
  STZ.w $037B
  JSL SwitchHook_Clear
  PLY : PLB : CLC : RTL
  .abort
  STZ.w $0C4A,X
  STZ.w $037B                 ; Link left $13; its exit path will not clear it
  JSL SwitchHook_Clear
  PLY : PLB : CLC : RTL
  .sfx
  LDA.b #!SwitchHookSfx : STA.w $012F
  .cling
  PLY : PLB : SEC : RTL
  .rise
  SEC : SBC.b #!SwitchHookCling
  JSR SwitchHook_SetHeight
  PLY : PLB : CLC : RTL
  .swap
  JSR SwitchHook_Exchange
  BRA .camera
  .fall
  EOR.b #$FF : SEC : ADC.b #!SwitchHookLand   ; A = Land - counter
  JSR SwitchHook_SetHeight
  .camera
  ; SwitchHook_DungeonCamera steps the camera before Sprite_Main; record
  ; this frame's result so the next landed frame can see it stopped.
  LDA.b $E2 : STA.w !SwitchHookCamX
  LDA.b $E8 : STA.w !SwitchHookCamY
  PLY : PLB : CLC : RTL
}

; Module07 at $0287E5, after Link and the vanilla camera, before the
; $E2 save/restore around Sprite_Main (an ancilla-side $E2 write is lost).
; LinkState_Hookshotting zeroes $30/$31, so the vanilla camera never moves
; during the beat; from the swap frame on, feed it Link's box offset here.
; Underworld_HandleCamera is JSR-only and ends in RTS: the pushed vanilla
; RTL at $028053 returns to us. Bank $2B DB maps $06xx.
; Exit: replaced REP #$21 : LDA $E2 (M=16, carry clear, A=$E2).
SwitchHook_DungeonCamera:
{
  PHP
  REP #$30
  PHX : PHY
  PHB : PHK : PLB
  SEP #$30
  LDA.w !SwitchHookActive : CMP.b #!SwitchHookTag : BNE .done
  LDA.w !SwitchHookBeat : CMP.b #!SwitchHookSwap : BCC .done
  LDA.b $5D : CMP.b #$13 : BNE .done
  LDA.b $11 : BNE .done
  JSR SwitchHook_CameraStep
  LDA.b $30 : ORA.b $31 : BEQ .done
  PHK : PEA.w .return-1
  PEA.w $8052                 ; $02:8053 RTL - 1
  JML $02BA31                 ; Underworld_HandleCamera
  .return
  SEP #$30
  STZ.b $30 : STZ.b $31
  .done
  PLB
  REP #$30
  PLY : PLX
  PLP
  REP #$21 : LDA.b $E2
  RTL
}

; A = height above the floor; Y = target. Lifts both actors the same amount.
SwitchHook_SetHeight:
{
  STA.w SprHeight,Y
  STA.b $24 : STZ.b $25
  RTS
}

; Hidden swap frame. Y = target, X = ancilla; preserves X/Y.
; The source block footprint is Link X, Link Y+8. Swap both bytes.
SwitchHook_Exchange:
{
  LDA.b $21 : STA.b $40       ; old high bytes: quadrant delta for camera
  LDA.b $23 : STA.b $41
  LDA.w SprY,Y : STA.b $0A
  LDA.w SprYH,Y : STA.b $0B
  LDA.w SprX,Y : STA.b $0C
  LDA.w SprXH,Y : STA.b $0D
  LDA.b $22 : STA.w SprX,Y
  LDA.b $23 : STA.w SprXH,Y
  %a16()
  LDA.b $20 : CLC : ADC.w #$0008 : STA.b $00
  LDA.b $0C : STA.b $22 : STA.w $0FC2
  LDA.b $0A : SEC : SBC.w #$0008 : STA.b $20 : STA.w $0FC4
  %a8()
  LDA.b $00 : STA.w SprY,Y
  LDA.b $01 : STA.w SprYH,Y
  LDA.b #$00
  STA.w SprXSpeed,Y : STA.w SprYSpeed,Y
  STA.w SprXRound,Y : STA.w SprYRound,Y
  STA.w SprTimerA,Y : STA.w SprMiscA,Y : STA.w SprMiscC,Y
  ; Cached reset coordinates deliberately stay at the original puzzle origin.
  STZ.w $0642                 ; block recomputes its switch contact next tick
  LDA.b $2F : EOR.b #$02 : STA.b $2F   ; Ages: Link turns around on swap
  PHX : PHY
  JSL ApplyLinksMovementToCamera      ; quadrant + camera bounds ($A9/$AA)
  PLY : PLX
  LDA.b $21 : STA.b $40
  LDA.b $23 : STA.b $41
  RTS
}

; Mirrors Underworld_HandleCamera's thresholds: request an 8px step toward
; Link on each axis where he is outside the follow box. The vanilla loop runs
; later this frame, scrolls one pixel per step and stops at room limits.
SwitchHook_CameraStep:
{
  STZ.b $30 : STZ.b $31
  %a16()
  LDA.b $78 : AND.w #$00FF : BEQ .flat
  LDA.b $24 : CMP.w #$FFFF : BNE .height
  .flat
  LDA.w #$0000
  .height
  STA.b $00
  LDA.b $20 : SEC : SBC.b $00 : AND.w #$01FF : CLC : ADC.w #$000C
  STA.b $00
  CMP.w $061A : BCC .not_down
  %a8()
  LDA.b #$08 : STA.b $30
  %a16()
  BRA .horizontal
  .not_down
  LDA.w $0618 : CMP.b $00 : BCC .horizontal
  %a8()
  LDA.b #$F8 : STA.b $30
  %a16()
  .horizontal
  LDA.b $22 : AND.w #$01FF : CLC : ADC.w #$0008
  STA.b $00
  CMP.w $061E : BCC .not_right
  %a8()
  LDA.b #$08 : STA.b $31
  RTS
  .not_right
  LDA.w $061C : CMP.b $00
  %a8()
  BCC .done
  LDA.b #$F8 : STA.b $31
  .done
  RTS
}

SwitchHook_ContextValid:
{
  LDA.b $10 : CMP.b #$07 : BNE .no
  CMP.w !SwitchHookMode : BNE .no
  LDA.b $1B : CMP.b #$01 : BNE .no
  LDA.b $11 : ORA.w $037E : BNE .no
  LDA.b $5D : CMP.b #$13 : BNE .no
  LDA.w $0304 : CMP.b #$0E : BNE .no
  LDA.w $0202 : CMP.b #$1D : BNE .no
  LDA.l SwitchHookOwned : CMP.b #$01 : BNE .no
  LDA.b $EE : CMP.b #$02 : BCS .no
  CMP.w !SwitchHookLayer : BNE .no
  %a16()
  LDA.b $A0 : CMP.w !SwitchHookRoom
  %a8()
  BNE .no
  SEC : RTS
  .no
  CLC : RTS
}

; Swappable sprite types: type, hit height above the 16x16 base ($08).
SwitchHook_Targets:
  db Sprite_IceBlock, $00
  db !SwitchHookStatue, $08                ; statue head
  db Sprite_SwapDiamond, $00               ; Ages Swap Diamond
.end

; Y=sprite, X=ancilla. Read-only validation until TryExchange commits.
; $08 = hit height from SwitchHook_Targets.
; Statue SprFrame is its 0/1 grab flag; its own reset path clears it.
SwitchHook_TargetValid:
{
  LDA.w SprState,Y : CMP.b #$09 : BNE .no
  STZ.b $09
  PHX
  LDX.b #SwitchHook_Targets_end-SwitchHook_Targets-2
  LDA.w SprType,Y
  .scan
  CMP.l SwitchHook_Targets,X : BEQ .found
  DEX : DEX : BPL .scan
  PLX
  BRA .no
  .found
  LDA.l SwitchHook_Targets+1,X : STA.b $08
  PLX
  LDA.w SprType,Y : CMP.b #!SwitchHookStatue : BNE .kind
  LDA.w SprFrame,Y : CMP.b #!Stone_Marker : BEQ .no
  .kind
  LDA.w SprFloor,Y : CMP.b $EE : BNE .no
  LDA.w SprY,Y : STA.b $0A
  LDA.w SprYH,Y : STA.b $0B
  LDA.w SprX,Y : STA.b $0C
  LDA.w SprXH,Y : STA.b $0D
  JSR SwitchHook_HeadOverlaps : BCC .no
  BRA .contact
  .no
  CLC : RTS
  .contact
  LDA.w SprHeight,Y : ORA.w SprXSpeed,Y : ORA.w SprYSpeed,Y
  ORA.w SprTimerA,Y : ORA.w SprMiscC,Y : BNE .blocked
  JSR SwitchHook_LandingVisible : BCC .blocked
  PHY : PHX
  JSR SwitchHook_FootprintSafe
  PLX : PLY
  BCC .blocked
  ; Temporarily replace the probe origin with Link's old standing footprint.
  %a16()
  LDA.b $0A : PHA
  LDA.b $0C : PHA
  LDA.b $20 : CLC : ADC.w #$0008 : STA.b $0A
  LDA.b $22 : STA.b $0C
  %a8()
  PHY : PHX
  JSR SwitchHook_FootprintSafe
  PLX : PLY
  %a16()
  PLA : STA.b $0C
  PLA : STA.b $0A
  %a8()
  BCC .blocked
  SEC : RTS
  .blocked
  JSR SwitchHook_Retract
  CLC : RTS
}

; Head is an 8x8 box; target is 16 wide and 16+$08 tall (top = Y-$08).
; Unsigned wrapped differences reject all non-overlap, including false
; low-byte matches across pages. With $08=0 this is the ice-block test.
SwitchHook_HeadOverlaps:
{
  LDA.w $0C04,X : STA.b $06
  LDA.w $0C18,X : STA.b $07
  %a16()
  LDA.b $06 : SEC : SBC.b $0C : CLC : ADC.w #$0007
  CMP.w #$0017
  %a8()
  BCS .no
  LDA.w $0BFA,X : STA.b $06
  LDA.w $0C0E,X : STA.b $07
  %a16()
  LDA.b $06 : SEC : SBC.b $0A : CLC : ADC.b $08
  CLC : ADC.w #$0007 : STA.b $06
  LDA.w #$0017 : CLC : ADC.b $08
  CMP.b $06                   ; carry set: limit >= distance
  %a8()
  BEQ .no
  BCC .no
  SEC : RTS
  .no
  CLC : RTS
}

; Full-word 128px range only: the swap beat moves the camera to Link, so an
; off-screen landing is allowed (Ages also swaps with off-screen targets).
SwitchHook_LandingVisible:
{
  %a16()
  LDA.b $0C : SEC : SBC.b $22 : CLC : ADC.w #$0080
  CMP.w #$0101 : BCS .no
  LDA.b $0A : SEC : SBC.b $20 : CLC : ADC.w #$0078
  CMP.w #$0101 : BCS .no
  %a8()
  SEC : RTS
  .no
  %a8()
  CLC : RTS
}

; $0A/$0C = Y/X footprint origin. Sampling 0,7,15 covers all nine
; potential 8px cells of a misaligned 16x16 box, including the middle.
; Clobbers X and $00-$06; caller saves X/Y. Return M/X=8, carry=safe.
SwitchHook_FootprintSafe:
{
  LDX.b #$08
  .point
  LDA.l .x_offsets,X : STA.b $02 : STZ.b $03
  LDA.l .y_offsets,X : STA.b $00 : STZ.b $01
  %a16()
  LDA.b $02 : CLC : ADC.b $0C : STA.b $02
  LDA.b $00 : CLC : ADC.b $0A : STA.b $00
  %a8()
  LDA.b $EE
  JSL Sprite_GetTileAttr
  LDA.w $0FA5 : BEQ .safe
  CMP.b #$0E : BEQ .safe      ; ice
  CMP.b #$23 : BEQ .safe      ; floor switch variants
  CMP.b #$24 : BEQ .safe
  CMP.b #$25 : BEQ .safe
  CMP.b #$3B : BNE .no
  .safe
  DEX : BPL .point
  SEC : RTS
  .no
  CLC : RTS
  .x_offsets
  db 0,7,15,0,7,15,0,7,15
  .y_offsets
  db 0,0,0,7,7,7,15,15,15
}

; Match the other item modules: the next file starts with vanilla org hooks.
pushpc
