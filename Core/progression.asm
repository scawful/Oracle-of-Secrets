; =========================================================
; Oracle of Secrets — Progression Infrastructure
;
; Shared helpers for crystal counting, MapIcon management,
; and NPC reaction-based message dispatch. Centralizes the
; scattered ad-hoc progression checks found across the
; codebase (maku_tree.asm, zora.asm, village_elder.asm, etc.)
;
; STATUS: UNTESTED — needs Mesen2 runtime verification.
;   First consumer: maku_tree.asm (MakuTreeReactionTable).
;
; Created: 2026-02-06
; File: Core/progression.asm
; Depends on: Core/sram.asm (Crystals, MapIcon symbols)
;             Core/sprite_macros.asm (message display conventions)
;
; USAGE NOTES:
;   All routines are JSL targets — callable from any bank.
;   No hooks or org patches — these are passive helpers.
;   First consumer: Maku Tree (maku_tree.asm). Next: Zora NPC.
;
; DESIGN DECISIONS:
;   - GetCrystalCount uses shift-and-count (popcount) since
;     the crystal bitfield has only 7 bits. A lookup table
;     would be faster but unnecessary for NPC dialogue triggers
;     that run once per interaction (~40 cycles is negligible).
;
;   - UpdateMapIcon uses the formula MapIcon = count + 1.
;     This works because MapIcon is a REVEAL THRESHOLD that
;     controls how many dungeon markers are visible on the
;     world map (world_map.asm MapIconDraw), not a "go here
;     next" pointer. Higher values show more markers.
;
;   - SelectReactionMessage takes a 24-bit table pointer in
;     $00-$02 for cross-bank compatibility (NPC reaction
;     tables live in their sprite's bank, not Core's bank).
;     Returns A/Y pre-loaded for Sprite_Show* JSL calls.
;
; =========================================================

; =========================================================
; GetCrystalCount
;
; Returns the number of completed dungeons (popcount of the
; crystal bitfield at $7EF37A). Counts set bits among bits
; 0-6, which map to D1-D7 in non-linear order:
;
;   Bit 0 ($01) = D1 Mushroom Grotto
;   Bit 1 ($02) = D6 Goron Mines
;   Bit 2 ($04) = D5 Glacia Estate
;   Bit 3 ($08) = D7 Dragon Ship
;   Bit 4 ($10) = D2 Tail Palace
;   Bit 5 ($20) = D4 Zora Temple
;   Bit 6 ($40) = D3 Kalyxo Castle
;
; Entry: Any M/X state
; Exit:
;   A = crystal count (0–7)
;   M flag is SET on exit (8-bit A)
;   If caller had 16-bit A, high byte is guaranteed $00
;   X, Y preserved
;
; Clobbers: P (M flag forced, restored by PLP at end)
; Stack: 3 bytes (PHP + PHX with 8-bit X)
; Cycles: ~40 worst case (7 iterations)
; =========================================================
GetCrystalCount:
{
  PHP                ; Save caller's M/X flags
  SEP #$30           ; Force 8-bit A, 8-bit X
  PHX                ; Save X (1 byte — width now known)

  LDA.l Crystals     ; Load $7EF37A (24-bit, DBR-safe)
  AND #$7F           ; Mask to 7 valid crystal bits
  LDX #$00           ; Bit counter

  .loop
    LSR              ; Shift lowest bit into carry
    BCC .no_bit
      INX            ; Count this set bit
    .no_bit
    CMP #$00         ; Any bits remaining?
    BNE .loop

  TXA                ; A = count (low byte from 8-bit X)
  PLX                ; Restore X (1 byte, matches 8-bit PHX)

  ; Zero-extend to 16-bit so callers with REP #$20 get
  ; clean values. After PLP, if caller had 8-bit A they
  ; see only the low byte (count). If 16-bit A, they see
  ; $00CC where CC = count.
  REP #$20           ; 16-bit A
  AND #$00FF         ; Clear high byte (B accumulator)

  PLP                ; Restore caller's M/X flags
  RTL
}

; =========================================================
; UpdateMapIcon
;
; Sets MapIcon ($7EF3C7) based on current crystal count.
; Formula: MapIcon = GetCrystalCount() + 1
;
; MapIcon values control world map dungeon marker visibility:
;   $00 = Maku Tree (no dungeon markers)
;   $01 = D1 marker visible
;   $02 = D2+ markers visible (all shown)
;   ...
;   $07 = D7 marker visible
;   $08 = Fortress marker visible (endgame)
;   $09 = Tail Pond (special — set by Village Elder only)
;
; This routine handles the common case. Special MapIcon
; values (Tail Pond, Maku Tree reset) should be set directly
; by the NPC that owns that guidance, not through this helper.
;
; Entry: Any M/X state
; Exit:
;   A = new MapIcon value (8-bit, 1–8)
;   MapIcon ($7EF3C7) written
;   X, Y preserved
;
; Clobbers: MapIcon SRAM
; =========================================================
UpdateMapIcon:
{
  PHP
  SEP #$20           ; 8-bit A

  JSL GetCrystalCount ; A = count (0-7, 8-bit after JSL)
  INC                 ; A = count + 1 (1-8)
  STA.l MapIcon       ; Write $7EF3C7

  PLP
  RTL
}

; =========================================================
; SelectReactionMessage
;
; Walks a reaction table and returns the message ID for the
; first entry whose crystal threshold is met by the player's
; current progress. The returned A/Y values are pre-loaded
; for direct use with Sprite_ShowSolicitedMessageIfPlayerFacing
; or Sprite_ShowMessageUnconditional.
;
; Entry:
;   $00-$02 = 24-bit pointer to reaction table
;             (set all 3 bytes: $00=low, $01=high, $02=bank)
;
; Exit:
;   A = message ID low byte  (8-bit)
;   Y = message ID high byte (8-bit)
;   Ready for: JSL Sprite_ShowSolicitedMessageIfPlayerFacing
;         or:  JSL Sprite_ShowMessageUnconditional
;
; Table format (3 bytes per entry, DESCENDING threshold order):
;   db threshold    ; min crystal count (>= comparison)
;   dw msg_id       ; 16-bit message ID (little-endian)
;   ...
;   db $00          ; sentinel: threshold 0 always matches
;   dw default_id   ; default message
;
; The first entry where crystal_count >= threshold wins.
; Table MUST end with a $00 sentinel to prevent runaway.
;
; EXAMPLE table definition (for an NPC with 3 tiers):
;
;   NPCReaction_Zora:
;     db $04 : dw $01A6   ; 4+ crystals → post-D4
;     db $02 : dw $01A5   ; 2+ crystals → mid-game
;     db $00 : dw $01A4   ; default     → initial
;
; EXAMPLE usage in NPC code:
;
;   REP #$20
;   LDA.w #NPCReaction_Zora : STA $00
;   SEP #$20
;   LDA.b #NPCReaction_Zora>>16 : STA $02
;   JSL SelectReactionMessage
;   JSL Sprite_ShowSolicitedMessageIfPlayerFacing
;
; Clobbers: $04 (temp crystal count)
; Stack: 3 bytes (PHP + PHX with 8-bit X)
; =========================================================
SelectReactionMessage:
{
  PHP
  SEP #$30           ; Force 8-bit A, 8-bit X/Y (stack-safe PHX/PLX)
  PHX                ; Save X (1 byte — width now known)

  ; Get crystal count and stash in temp
  JSL GetCrystalCount ; A = count (0-7, 8-bit)
  STA.b $04           ; $04 = crystal count

  ; Walk the reaction table at [$00] (indirect long)
  LDY #$00            ; Table offset
  .walk
    LDA [$00], Y      ; Read threshold byte
    BEQ .match         ; Threshold $00 = sentinel, always matches
    CMP.b $04          ; Compare: threshold vs crystal count
    BEQ .match         ; count == threshold → match
    BCC .match         ; threshold < count  → match (unsigned)
    ; threshold > count → skip to next entry (+3 bytes)
    INY : INY : INY
    BRA .walk

  .match
    ; Read the 16-bit message ID following the threshold byte
    INY                ; Advance past threshold
    LDA [$00], Y       ; msg_id low byte
    PHA                ; Stash on stack
    INY
    LDA [$00], Y       ; msg_id high byte
    TAY                ; Y = message high byte (return value)
    PLA                ; A = message low byte (return value)

    PLX                ; Restore X (1 byte, matches 8-bit PHX)
    PLP                ; Restore caller's M/X flags
    ; A = msg low, Y = msg high — ready for Sprite_Show* JSLs
    RTL
}

; =========================================================
; TEST PLAN — Runtime verification needed before use
;
; These routines are PASSIVE (no hooks, no org patches).
; They don't affect the game until an NPC JSLs to them.
; Testing requires a temporary test harness or manual
; Mesen2 register injection.
;
; Test 1: GetCrystalCount accuracy
;   Method: Use Mesen2 to write crystal values, call routine
;   python3 scripts/mesen2_client.py write 0x7EF37A 0x00
;   → expect A = 0
;   python3 scripts/mesen2_client.py write 0x7EF37A 0x01
;   → expect A = 1
;   python3 scripts/mesen2_client.py write 0x7EF37A 0x7F
;   → expect A = 7
;   python3 scripts/mesen2_client.py write 0x7EF37A 0x15
;   → expect A = 3 (bits 0, 2, 4 = D1, D5, D2)
;   Verify: high byte of A is $00 for 16-bit callers
;
; Test 2: UpdateMapIcon correctness
;   Method: Set Crystals, call UpdateMapIcon, read $7EF3C7
;   Crystals=$00 → MapIcon should be $01 (D1)
;   Crystals=$01 → MapIcon should be $02 (D2)
;   Crystals=$7F → MapIcon should be $08 (Fortress)
;
; Test 3: SelectReactionMessage table walk
;   Method: Set up a test reaction table, set Crystals,
;           call routine, verify A/Y contain expected msg ID
;   With Crystals=0:  expect default entry (threshold $00)
;   With Crystals=4+: expect first high-threshold entry
;   Verify: table must be sorted descending by threshold
;   Verify: $00 sentinel catches the fallthrough case
;
; Test 4: Register preservation
;   Method: Set X, Y to known values, JSL GetCrystalCount,
;           verify X, Y unchanged on return
;   Verify: works with both 8-bit and 16-bit caller widths
;
; Test 5: NPC integration (deferred — do one NPC at a time)
;   Candidate: Zora NPC (simplest — one threshold check)
;   Before: LDA.l Crystals : AND.b #$20 : BEQ +++
;   After:  Set $00-$02 → JSL SelectReactionMessage → JSL Show*
;   Verify: no dialogue regression, same behavior as before
;
; =========================================================

print "Progression helpers assembled at     ", pc
