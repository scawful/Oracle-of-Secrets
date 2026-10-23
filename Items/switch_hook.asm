; =========================================================
; Switch Hook prototype: exchange with a stationary ice block.
; Ordinary Hookshot/Goldstar retain their existing collision path.
;
; Target contract: live $D5, grounded, stopped, same dungeon/layer,
; within 128px, visible landing, and safe floor under both footprints.
; This prototype intentionally has no outdoor or enemy exchange.
; Link's feet occupy sprite Y+8..15, so Link Y = block Y-8.
;
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
  PHP : %a8()
  STZ.w !SwitchHookActive
  STZ.w !SwitchHookRoom : STZ.w !SwitchHookRoom+1
  STZ.w !SwitchHookLayer : STZ.w !SwitchHookMode
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
  LDA.b $11 : BNE .cancel
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
  LDA.b $11 : BNE .paused
  JML $08BD78
  .paused
  JML $08BD9C
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
  JML $08BDA2                 ; chain was deleted: return to ancilla caller
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
  STY.b $0E
  ; The source block footprint is Link X, Link Y+8. Swap both bytes.
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
  STZ.b $30 : STZ.b $31
  STZ.w $037E
  LDX.b $0F : STZ.w $0C4A,X
  LDA.b #$0F : STA.w $012F    ; SFX3.0F: existing magical effect sound
  JSL SwitchHook_Clear
  PLY : PLX : PLB : SEC : RTL
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

; Y=sprite, X=ancilla. Read-only validation until TryExchange commits.
SwitchHook_TargetValid:
{
  LDA.w SprState,Y : CMP.b #$09 : BNE .no
  LDA.w SprType,Y : CMP.b #Sprite_IceBlock : BNE .no
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

; Head is an 8x8 box; target is 16x16. Unsigned wrapped differences
; reject all non-overlap, including false low-byte matches across pages.
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
  LDA.b $06 : SEC : SBC.b $0A : CLC : ADC.w #$0007
  CMP.w #$0017
  %a8()
  BCS .no
  SEC : RTS
  .no
  CLC : RTS
}

; Full-word range and screen bounds prevent arbitrary room-camera jumps.
SwitchHook_LandingVisible:
{
  %a16()
  LDA.b $0C : SEC : SBC.b $22 : CLC : ADC.w #$0080
  CMP.w #$0101 : BCS .no
  LDA.b $0A : SEC : SBC.b $20 : CLC : ADC.w #$0078
  CMP.w #$0101 : BCS .no
  LDA.b $0C : SEC : SBC.b $E2
  CMP.w #$0008 : BCC .no
  CMP.w #$00E9 : BCS .no
  LDA.b $0A : SEC : SBC.w #$0008 : SEC : SBC.b $E8
  CMP.w #$0018 : BCC .no
  CMP.w #$00C9 : BCS .no
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
