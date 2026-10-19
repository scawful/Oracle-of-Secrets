; =========================================================
; BossDirector: shared boss pacing
;
; One director sprite per fight owns the attack token. Only the token
; holder attacks. Every attack ends with a rest (no new turn) and starts
; its own cooldown, so the fight has turns the player can read and punish.
; Method: ~/.context/knowledge/hobby/oracle-boss-pacing.md.
;
; BossKit (boss_kit.asm) asks "can this frame afford new work?";
; the director asks "can the player handle new work now?". A turn needs
; both: BossDirector_Ready checks BossKit_CanSpend last.
;
; Use:
;   1. Prep: JSL BossDirector_Reset.
;   2. Every frame, from the director sprite: JSL BossDirector_Tick.
;   3. To start a turn: JSL BossDirector_Ready, carry set means go.
;      Then A = the holder's slot: JSL BossDirector_Take.
;   4. When the turn's recovery ends: A = cooldown id, $00 = cooldown
;      frames, $01 = rest frames: JSL BossDirector_Release.
;   5. If the holder dies or loses its turn: $01 = rest: JSL BossDirector_Free.
;
; Calling convention: JSL, 8-bit A/X/Y, X = the calling sprite (kept).
; Code in bank $3A: no DBR use, tables are read with long addressing.
; =========================================================

; WRAM $7FF388-$7FF39D: vanilla-free UNUSED_7FF180 block, after BossKit
; ($7FF380-$7FF384) and before the 2P PoC ($7FF400). Core/symbols.asm.
BossDir_Token  = $7FF388 ; slot holding the attack token, $FF = free
BossDir_Rest   = $7FF389 ; frames before a new turn may start
BossDir_Grace  = $7FF38A ; frames of hit grace after the player is hurt
BossDir_LinkHP = $7FF38B ; player health at the last tick
BossDir_Cool   = $7FF38C ; 8 bytes: cooldown frames per cooldown id
BossDir_Stage  = $7FF394 ; boss-defined stage, 0 = not started
BossDir_Turn   = $7FF395 ; boss-defined turn counter
BossDir_Var    = $7FF396 ; 8 bytes for the boss ($7FF396-$7FF39D)

!BossDir_CoolCount = 8
!BossDir_HitGrace  = 60

pushpc
; Bank $3A free run $3A8DC8-$3AB7FF. Manhandla (manhandla.asm) uses
; $3AA000-$3AA7FF; this block and the Kydreeok turn code use $3AA800-$3AAFFF.
org $3AA800

BossDirector_Reset:
{
  PHX
  LDA.b #$FF : STA.l BossDir_Token
  LDA.b #$00
  STA.l BossDir_Rest
  STA.l BossDir_Grace
  LDX.b #$11
  .clear
    STA.l BossDir_Cool, X ; Cool, Stage, Turn and Var: 18 bytes
  DEX : BPL .clear
  LDA.l $7EF36D : STA.l BossDir_LinkHP
  PLX
  RTL
}

BossDirector_Tick:
{
  PHX
  LDA.l BossDir_Rest : BEQ .rested
    DEC A : STA.l BossDir_Rest
  .rested
  LDA.l BossDir_Grace : BEQ .no_grace
    DEC A : STA.l BossDir_Grace
  .no_grace
  LDX.b #!BossDir_CoolCount-1
  .cool
    LDA.l BossDir_Cool, X : BEQ .next
      DEC A : STA.l BossDir_Cool, X
    .next
  DEX : BPL .cool
  ; Hit grace: no new turn for a second after the player loses health.
  LDA.l $7EF36D : CMP.l BossDir_LinkHP : STA.l BossDir_LinkHP : BCS .not_hurt
    LDA.b #!BossDir_HitGrace : STA.l BossDir_Grace
  .not_hurt
  PLX
  RTL
}

; Carry set: the token is free, no rest or grace runs, and the frame has
; budget for new work.
BossDirector_Ready:
{
  LDA.l BossDir_Token : CMP.b #$FF : BNE .no
  LDA.l BossDir_Rest : ORA.l BossDir_Grace : BNE .no
  JSL BossKit_CanSpend
  RTL
  .no
  CLC
  RTL
}

; A = the slot that holds the token now.
BossDirector_Take:
{
  STA.l BossDir_Token
  RTL
}

; A = cooldown id. Out: A = frames left, Z set when the attack is ready.
BossDirector_CoolLeft:
{
  PHX
  TAX
  LDA.l BossDir_Cool, X
  PLX
  CMP.b #$00
  RTL
}

; A = cooldown id, $00 = cooldown frames, $01 = rest frames.
; Starts the cooldown, raises the rest to at least $01, frees the token.
BossDirector_Release:
{
  PHX
  TAX
  LDA.b $00 : STA.l BossDir_Cool, X
  PLX
}
; $01 = rest frames. Frees the token; a longer rest already running stays.
BossDirector_Free:
{
  LDA.b #$FF : STA.l BossDir_Token
  LDA.l BossDir_Rest : CMP.b $01 : BCS .keep
    LDA.b $01 : STA.l BossDir_Rest
  .keep
  RTL
}

assert pc() <= $3AAA00, "BossDirector block crossed $3AAA00"
pullpc
