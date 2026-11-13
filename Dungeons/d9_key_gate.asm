; Private D9 Small Key nook. Native room flag $1000 belongs to Chu success.
; Door index3 is normal00, whose native path skips the persistent flag write.
; Guard the index3/type00 composition and unearned east entry in native tests.
; The new shutter is index2/$2000; legacy first-three-door bits never earn it.
; No new SRAM layout, room-entry hook, sprite ID or shared state is introduced.
;
; Called by CustomTag with M=8/X=8, D=$0000, WRAM-mirrored DBR. Preserve
; P/X/Y and the stack; clobber A and $00-$03. RoomTag cadence requires $11=0.
D9KeyGate_Main:
{
  PHP : PHX : PHY
  JSR D9KeyGate_Refill
  REP #$20
  LDA.w $0400 : BIT.w #$1000 : BEQ .not_earned
  BRL .open
  .not_earned
  ; A previously collected first chest must also retain an exit.
  LDA.w $0402 : BIT.w #$0100 : BEQ + : BRL .earned
+
  SEP #$20
  LDA.l BombchuSignature : CMP.b #$BC : BEQ + : BRL .closed
+
  LDA.l BombchuIndoors : BNE + : BRL .closed
+
  LDA.l BombchuAreaLow : CMP.b #$D9 : BEQ + : BRL .closed
+
  LDA.l BombchuAreaHigh : BEQ + : BRL .closed
+
  LDA.l BombchuFloor : BEQ + : BRL .closed
+
  LDA.l BombchuSlot : BNE + : BRL .closed
+
  CMP.b #$03 : BCC + : BRL .closed
+
  DEC A : TAX
  LDA.w $0C4A,X : CMP.b #$07 : BEQ + : BRL .closed
+
  LDA.w $03EA,X : CMP.b #$BC : BEQ + : BRL .closed
+
  LDA.w $0C5E,X : BEQ + : BRL .closed
+
  ; Native travelling center, 15x15 footprint, target [192,320,16,16].
  LDA.w $0C04,X : STA.b $00
  LDA.w $0C18,X : STA.b $01
  LDA.w $0BFA,X : STA.b $02
  LDA.w $0C0E,X : STA.b $03
  REP #$20
  LDA.b $00 : SEC : SBC.w #$12C0 : CLC : ADC.w #$0007
  CMP.w #$001E : BCC + : BRL .closed
+
  LDA.b $02 : SEC : SBC.w #$1B40 : CLC : ADC.w #$0007
  CMP.w #$001E : BCC + : BRL .closed
+
  SEP #$20
  LDA.b #$01 : STA.w $039F,X ; consume the successful travelling Chu

  .earned
  REP #$20
  LDA.w $0400 : ORA.w #$1000 : STA.w $0400
  LDA.l $7EF1B2 : ORA.w #$1000 : STA.l $7EF1B2
  .open
  LDA.w $068C : AND.w #$2020 : CMP.w #$2020 : BEQ .exit
  STZ.w $0468
  BRA .animate

  .closed
  REP #$20
  ; Native door data may contain an old index2 opening from the prior room.
  ; Clear its saved bit, then let the native shutter animator change live
  ; $068C and collision. Never pre-clear $068C and skip the visible closure.
  LDA.w $0400 : AND.w #$DFFF : STA.w $0400
  LDA.w $068C : BIT.w #$2020 : BEQ .exit
  LDA.w #$0001 : STA.w $0468
  .animate
  STZ.w $068E : STZ.w $0690
  SEP #$20
  LDA.b #$05 : STA.b $11
  .exit
  SEP #$30
  PLY : PLX : PLP
  RTS
}

; Pot secret05 deterministically spawns native one-bomb spriteDC. At the
; relocated refill pot only, promote that pickup to native four-bombDD,
; whose existing Oracle pickup handler grants five Chus after ownership.
; Preserve unrelated bomb drops and the global secret/pickup tables.
D9KeyGate_Refill:
{
  LDA.l BombchuOwned : CMP.b #$01 : BNE .done
  LDX.b #$0F
  .slot
  LDA.w $0DD0,X : CMP.b #$09 : BNE .next
  LDA.w $0E20,X : CMP.b #$DC : BNE .next
  LDA.w $0D30,X : CMP.b #$12 : BNE .next
  LDA.w $0D10,X : CMP.b #$70 : BNE .next
  LDA.w $0D20,X : CMP.b #$1B : BNE .next
  LDA.w $0D00,X : CMP.b #$90 : BNE .next
  LDA.b #$DD : STA.w $0E20,X
  .next
  DEX : BPL .slot
  .done
  RTS
}

; Room-specific actor mode; other lever/Goron behavior remains native.
; M=8/X=8, preserve A, return C=1 only for indoor room $00D9.
D9KeyGate_IsRoom:
{
  PHA
  LDA.b $1B : BEQ .no
  LDA.b $A1 : BNE .no
  LDA.b $A0 : CMP.b #$D9 : BNE .no
  PLA : SEC : RTL
  .no
  PLA : CLC : RTL
}

; Sprite prep runs during a transition, before $A0 necessarily changes.
D9KeyGate_IsLoadedRoom:
{
  PHA
  LDA.b $1B : BEQ .no
  LDA.w $048F : BNE .no
  LDA.w $048E : CMP.b #$D9 : BNE .no
  PLA : SEC : RTL
  .no
  PLA : CLC : RTL
}

; Existing AF dispatchers branch here to keep their nearly full bank unchanged.
; All entries are M=8/X=8, D=0, mirrored-WRAM DBR; preserve X/Y and the
; native long-call stack. Ordinary actors tail into their original wrappers.
D9Actor_PrepDispatch:
{
if !ENABLE_D6_CHU_GATE_97 == 1
  JSL D6ChuActor_IsLoadedRoom : BCS .stationary
  JSL D6ChuGate97_IsLoadedTarget : BCC .ordinary
  .stationary
else
  JSL D6ChuActor_IsLoadedRoom : BCC .ordinary
endif
  LDA.w $0E60,X : ORA.b #$40 : STA.w $0E60,X
  LDA.b #$80 : STA.w SprDefl,X
  STZ.w SprTileDie,X : STZ.w SprBulletproof,X
  STZ.w SprAction,X : STZ.w SprFrame,X
  RTL
  .ordinary
  JML Sprite_LeverSwitch_Prep_Ordinary
}
D9Actor_MainHandled:
{
if !ENABLE_D6_CHU_GATE_97 == 1
  JSL D6ChuActor_IsRoom : BCS .stationary
  JSL D6ChuGate97_IsRoom : BCC .ordinary
  JSL D6ChuGate97_IsTarget : BCC .ordinary
  .stationary
else
  JSL D6ChuActor_IsRoom : BCC .ordinary
endif
  LDA.w $0401 : AND.b #$10
  LSR A : LSR A : LSR A : LSR A
  STA.w SprFrame,X : STA.w SprAction,X
  SEC : RTL
  .ordinary
  CLC : RTL
}
