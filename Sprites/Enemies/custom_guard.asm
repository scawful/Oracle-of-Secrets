; Experimental: D3 Prison Sequence (Guard Capture)
;
; This file is fully feature-gated. When disabled, it must assemble to a no-op
; (no code/data emitted, no vanilla patches applied).
;
; Enable via:
;   !ENABLE_D3_PRISON_SEQUENCE = 1
;
; Implementation notes:
; - We do NOT hook Guard_Main entry ($05C227). Guard sprites JMP into Guard_Main
;   (no return address on stack), so a JSL-based entry hook is unsafe.
; - Instead, we hook an existing JSL callsite inside Guard_Main:
;     $05C263: JSL Sprite_CheckDamageToLink_long
;   Replacing that call keeps stack/flow correct and minimizes patch surface.

if !ENABLE_D3_PRISON_SEQUENCE == 1

; Capture the player and warp them to a dungeon entrance.
;
; A = entrance id
Oracle_CaptureAndWarp:
{
  ; This is called from sprite code paths. Preserve M/X bitness so we don't
  ; accidentally widen stores into SRAM/WRAM, but force 8-bit A while writing.
  PHP
  SEP #$20

  ; Set the target entrance ID (16-bit variable: $010E/$010F).
  STA.w $010E
  STZ.w $010F

  ; Mark player as captured (one-shot flag)
  LDA.l CastleAmbushFlags : ORA.b #!CastleAmbush_HasBeenCaptured
  STA.l CastleAmbushFlags

  ; Set spawn point to Prison — die/continue will return here
  LDA.b #!Spawn_Prison
  STA.l SpawnPoint

  ; Transitions should clear color math state to avoid visual glitches.
  STZ.b $9A
  STZ.b $9C
  STZ.b $9D

  LDA.b #$05         ; Game Mode 05: hole/whirlpool transition
  STA.b $10

  STZ.b $2F          ; Clear Link's action state
  STZ.b $5D          ; Clear Link's state (e.g., walking)

  LDA.b #$02
  STA.b $71          ; Transition/camera flag

  PLP
  RTL
}

; Post-item-get trigger for the prison sequence.
;
; The common receipt exit runs after chest/sprite and text/object receipts.
; Ancilla22's submodule02 path only draws while a message is open, so this
; completion point preserves the Meadow Blade message before capture.
; Entry/exit M8/X8, D=0 and the receipt caller's DBR. Replay the displaced
; STZ/LDA last: A and N/Z must describe the receipt, other flags stay intact.
Oracle_PrisonSequence_PostMeadowBlade:
{
  PHP

  ; Only the Meadow Blade receipt ($01, sword level2) can trigger capture.
  LDA.w $0C5E, X
  CMP.b #$01
  BNE .done

  LDA.b $1B
  BEQ .done

  ; Entrance$28 and native map data identify D3's dungeon as$10.
  LDA.l $7E040C ; DUNGEON
  CMP.b #$10
  BNE .done

  LDA.l $7EF359
  CMP.b #$02
  BNE .done

  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_HasBeenCaptured
  BNE .done

  ; The normal receipt dispatcher reaches this after the message closes.
  ; Keep other receipt contexts on their original completion path.
  LDA.b $10
  CMP.b #$07
  BNE .done
  LDA.b $11
  BNE .done

  LDA.b #$32
  JSL Oracle_CaptureAndWarp

.done
  PLP
  ; Exact displaced instructions at$08C43B; continue the native cleanup.
  STZ.w $02E9
  LDA.w $0C5E, X
  RTL
}

; Wrapper for Guard_Main's damage/contact check.
;
; Replaces $05C263: JSL Sprite_CheckDamageToLink_long
;
; Behavior changes:
; - D3 prison guards (SprSubtype&7 >= $05) ignore Minish Link ($02B2 == $05).
; - D3 prison guards trigger capture+warp on first contact, then suppress the
;   vanilla guard alert path by clearing C and $0FDC.
;
; Returns:
; - Carry / $0FDC semantics match vanilla, except when we intentionally suppress.
Guard_CheckDamageToLink_CaptureWrapper:
{
  ; Guard_Main also runs outside D3. Preserve its incoming A/P before the
  ; scope check, then tail-call native contact logic outside dungeon $10.
  PHP
  PHA
  LDA.b $1B
  BEQ .outside_d3
  LDA.l $7E040C ; DUNGEON
  CMP.b #$10
  BEQ .in_d3

.outside_d3
  PLA
  PLP
  JML $06F121 ; Sprite_CheckDamageToLink_long; uses the original JSL return

.in_d3
  PLA
  PLP
  ; Only D3 prison guards participate in the special logic.
  LDA.w SprSubtype, X
  AND.b #$07
  CMP.b #$05
  BCC .do_vanilla_check

  ; Minish Link is invisible to prison guards.
  LDA.w $02B2
  CMP.b #$05
  BNE .do_vanilla_check

  STZ.w $0FDC
  CLC
  RTL

.do_vanilla_check
  ; Vanilla contact/damage logic.
  JSL $06F121 ; Sprite_CheckDamageToLink_long

  ; Guard_Main immediately consumes the carry from Sprite_CheckDamageToLink_long,
  ; so preserve P while we do additional checks that would otherwise clobber C.
  PHP

  ; Detect "triggered" the same way Guard_Main does: C set OR $0FDC != 0.
  BCS .maybe_capture
  LDA.w $0FDC
  BEQ .restore_and_return

.maybe_capture
  ; Only prison guards can capture.
  LDA.w SprSubtype, X
  AND.b #$07
  CMP.b #$05
  BCC .restore_and_return

  ; One-shot: don't re-capture if player already captured
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_HasBeenCaptured
  BNE .restore_and_return

  ; Capture and warp to Kalyxo Castle Prison (entrance $32)
  ; Keep the saved P on stack until the end so we can restore M/X cleanly.
  SEP #$20
  LDA.b #$32
  JSL Oracle_CaptureAndWarp

  ; Suppress vanilla alert/recoil response (we're transitioning away).
  PLP
  STZ.w $0FDC
  CLC
  RTL

.restore_and_return
  PLP
  RTL
}

; ---------------------------------------------------------
; Vanilla patch (guard callsite hook)
; ---------------------------------------------------------
	; With !ENABLE_INTRO_STALFOS_PATROL the patrol owns $05C263 and calls this
	; wrapper for every guard outside the intro village (stalfos_patrol.asm).
	if !ENABLE_INTRO_STALFOS_PATROL == 0
	pushpc
	org $05C263 ; Guard_Main damage/contact check ; @hook module=Sprites name=Guard_CheckDamageToLink_CaptureWrapper kind=jsl target=Guard_CheckDamageToLink_CaptureWrapper
	  JSL Guard_CheckDamageToLink_CaptureWrapper
	pullpc
	endif

; ---------------------------------------------------------
; Vanilla patch (common receipt completion hook)
; ---------------------------------------------------------
  pushpc
  org $08C43B ; @hook module=Core name=Oracle_PrisonSequence_PostMeadowBlade kind=jsl target=Oracle_PrisonSequence_PostMeadowBlade expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8 protected_size=6
    assert read4($08C43B) == $BD02E99C, "D3 receipt completion preimage changed"
    assert read2($08C43F) == $0C5E, "D3 receipt item operand preimage changed"
    JSL Oracle_PrisonSequence_PostMeadowBlade
    NOP #2
  assert pc() == $08C441
  pullpc

endif
