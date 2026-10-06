# Custom Code Interaction Audit — 2026-09-26

Read-only audit. No `.asm`/ROM/save edits, no builds, no emulators. Build under
audit: `Roms/TestBuilds/rc-playtest-2026-09-25/` (`oos168x.sfc`, `.sym`,
`hooks.json`, `feature_flags_used.asm`, `NOTES.md`). Ground truth for hook
wiring was taken by hex-reading `oos168x.sfc` directly (LoROM, no copier
header — confirmed via the `$00:FFFC` reset vector) and cross-checking
against `oos168x.sym`, not from `hooks.json` alone (see P1-1, which is about
`hooks.json` itself being wrong). `oracle_analyzer.py --check-abi --check-hooks
--find-mx` was run against this exact ROM/sym/hooks triple (673 hooks
checked; 2 errors, 279 warnings — most warnings are pre-existing ROM-wide
noise, not from today's flags).

## P0 — Bugs live in this exact build

**P0-1. Magic ring inventory aliases unrelated collectible counters.**
CONFIRMED (read in code). `ring_sram_relocate` is off in this build. With the
flag off, `Items/magic_rings.asm:35-41` defines `RingSlot2 = $7EF38D` — which
`Core/sram.asm:432` documents as `Pineapples` — and `RingSlotsNum = $7EF38F`
= `RockMeatCount` (`Core/sram.asm:433`). `Pineapples` is incremented every
pineapple pickup (`Sprites/Objects/collectible.asm:93`) and `RockMeatCount`
every Goron trade item (`collectible.asm:127`). Every frame,
`MagicRing_CheckForArmor`/`CheckForPower`/`CheckForLight`/`CheckForBlast`/
`CheckForSteadfast`/`MagicRings_CheckForHeart` call `MagicRing_IsEquipped`,
which does `CMP.l RingSlot1/2/3` against ring IDs 2-7 — no "equipped via menu"
bit, just a raw byte compare. **Collecting 2-7 pineapples silently equips the
matching ring's passive effect** (2=Power/+dmg, 3=Armor/half contact damage,
4=Heart/regen, 5=Light, 6=Blast, 7=Steadfast) with no player action and no UI
indicator, and nothing appraised via Vasu. `Core/sram.asm:478-481` already
documents this exact bug and reserves `RingSaveBlock` ($7EF3A1-3A6) as the
fix target; the fix (flip the flag) is scaffolded but not shipped. Also:
`FOUNDRINGS`/`MAGICRINGS` alias `SideQuestProgress`/`2` ($7EF3D7/D8) the same
way. Owner: rings/menu track (marked "finished by other agents" in the brief
— this specific bug is explicitly still open per the source's own 2026-09-25
comment). **Fix now or before any playtest that touches pineapples/Goron
trade/side quests: flip `ENABLE_RING_SRAM_RELOCATE`, or gate
`MagicRing_IsEquipped` on an explicit "appraised" bit so raw counts can't
alias ring IDs.**

**P0-2. `NewOverworld_SetCameraBounds` has no M-width guard; analyzer found a live 8-bit-A caller.**
CONFIRMED contract gap in code; call-site reachability not independently
traced live. `Overworld/ZSCustomOverworld.asm:5001-5072`:
`Overworld_SetCameraBounds_Interupt` (`$02:C0C3`, hook-annotated
`expected_m=16 expected_x=8`) does only `JSL NewOverworld_SetCameraBounds :
RTS` — no `REP #$20`. `NewOverworld_SetCameraBounds` only does `REP/SEP
#$10` (X only) and assumes M=16 for its whole body, including
`AND.w #$00FF` right after an `LDA.l ...,X` with no preceding width fix — if
M is actually 8-bit here, `AND.w #$00FF` (assembled as a 2-byte immediate)
desyncs the instruction stream. `oracle_analyzer --find-mx` flagged exactly
this: `$02C09C: M flag: expected 16-bit, got 8-bit` at a real `JSR $C0C3`
instruction (confirmed by hex-reading `$02:C09C` = `20 C3 C0`), reached from
a different overworld-transition helper than the one JSL path already
appears twice in this file. Not created by today's flags, but it lives in
the same file/subsystem as `part0_storm`'s hooks and the `$02AFAD` overlay
work (P1-2). **Fix: add `REP #$20`/`SEP #$20` inside
`NewOverworld_SetCameraBounds` itself instead of trusting every caller.**

## P1 — Risk

**P1-1. `hooks.json` in this test-build folder does not match the ROM it ships with.**
CONFIRMED. `hooks.json` reports `$06:8365` as `Util/item_cheat.asm:30`'s
`JSL $3CA62A` (`skip_abi: true`). The actual ROM at `$06:8365` (PC
`0x030365`) is `22 00 F0 3A` = `JSL $3AF000` = `Oracle_P2_Tick` per
`oos168x.sym` — i.e. `Sprites/Players/player2_hooks.asm:11`'s hook, exactly
as documented ("Sprite_Main: JSL Follower_Main -> P2_Tick"). `item_cheat.asm`
is not even assembled (`Oracle_main.asm:129`:
`; incsrc "Util/item_cheat.asm"  ; DISABLED FOR TESTING`). Root cause, read
in `Scripts/Generate/generate_hooks_json.py`: `filter_active_asm_sources`
(line 411) only excludes a file if its *top-level directory* is in
`MODULE_DISABLE_FLAGS`; it has no way to know a specific `incsrc` line was
commented out, so it still scans `item_cheat.asm`. `scan_hooks`'s
address-collision tie-break (line 689, `if not existing or _score_entry(entry)
> _score_entry(existing)`) uses a strict `>`, so on a tie between two `jsl`
hooks at the same address the *first one seen in filesystem walk order*
(`root.rglob('*.asm')`, unsorted) wins — non-deterministic, and here it
picked the dead file. Net effect: `P2_Tick`'s hook silently gets no ABI/width
checking (the wrong, `skip_abi:true` entry stands in for it), and a future
real collision at this address would be similarly hidden. Both
`player2_hooks.asm` and `item_cheat.asm` already contain a comment warning
"do not enable both" — the manifest generator doesn't enforce or even see
that intent. Owner: tooling (P2/dual-swords session touches this file most).
**Fix: regenerate `hooks.json` now; teach the generator to walk
`Oracle_main.asm`'s actual active `incsrc` graph instead of a flat
directory-flag filter, and make same-address collisions a hard error unless
one side is provably dead code.**

**P1-2. Zero-slack code block has no build-time size guard.**
CONFIRMED. `Overworld/ZSCustomOverworld.asm:2258-2280`
(`Overworld_ReloadSubscreenOverlay_Interupt.noSubscreenOverlay`, the
`part0_storm`/pyramid-fix code) carries its own comment: "this block ends
exactly at $02B0D2 with !ENABLE_PART0_STORM = 0" — i.e. zero spare bytes.
Every one of the ~18 other `org`-patched blocks in this same file (e.g.
lines 418, 504, 543, 1397, 1717, 1925, 2045, 2160...) has an `assert pc() <=
...` right after it; this one does not. A future one-byte addition here
(with the flag off) silently overwrites whatever starts at `$02B0D2`. Owner:
storm/overworld. **Fix: add `assert pc() <= $02B0D2` after the `RTS` at
line 2280.**

**P1-3. Two independent "in a cutscene" signals for pad-2, not unified.**
CONFIRMED. `Core/patches.asm:102` (`InCutScene = $7EF303`) and
`Sprites/Players/player2.asm:136` (`P2_ReadPad`) both gate on `InCutScene`,
but the only writer of that flag is `Sprites/NPCs/farore.asm:137/192/212`.
Neither `Core/Cutscene/opening.asm` (Arrival, module `$0C`) nor
`experiment.asm` (module `$0D`) ever sets it. Today this is harmless only
because P2's *separate* module gates (`P2_CanAct` restricts to `$07/$09`;
`P2_Draw` to `$07/$09/$0E`) happen to exclude `$0C`/`$0D` too — two
unrelated mechanisms coincidentally agreeing. If a future cutscene module
reuses `$10 = $07/$09/$0E` without also setting `InCutScene`, pad-2 input
would leak through un-clamped. Owner: opening/experiment (main session) +
P2 (dual-swords session). **Fix: have `Arrival_Init`/`Exp_Init` set
`InCutScene = 1` and `Arrival_Handoff`/`Exp_Reload` clear it, matching
`farore.asm`'s pattern, for defense in depth.**

**P1-4. Analyzer ownership-check false positive on Cutscene hooks.**
CONFIRMED. The lone `--check-hooks` **ERROR** at `$02932D` ("target
'Arrival_SpotlightGate' resolves outside module 'Cutscene' (owners: Core)")
is a false alarm: `check_hook_target_ownership` in `oracle_analyzer.py:363`
compares the hook's declared `module=Cutscene` annotation against the
target's *top-level filesystem directory* — but `opening.asm` (which both
declares the hook and defines `Arrival_SpotlightGate`, lines 70/82) lives at
`Core/Cutscene/opening.asm`, whose top-level directory is `Core`, not
`Cutscene`. Same-file, self-contained hook; no real cross-module hazard.
This will keep firing for every Cutscene-labeled hook in this file and train
reviewers to ignore real ownership errors. Owner: tooling. **Fix: add
`Arrival_SpotlightGate` (and siblings) to `HOOK_TARGET_OWNER_ALLOWLIST`, or
compare against the second path segment when the first is a generic
container (`Core`, `Sprites`, ...).**

## P2 — Confirmed fine / cleanup

- **P2-1 (FINE).** `$06:8361` (`HUD_ClockDisplay`) → `$06:8365`
  (`P2_Tick`) → `JML Follower_Main` → `Follower_HandleTrigger` (`$09:A59E`,
  Impa JML) is a correctly ABI-preserving chain: every stage brackets its own
  `REP/SEP` work in `PHP...PLP` before handing control onward, so stacking
  independent hooks at adjacent addresses in `Sprite_Main` is safe here. The
  explicit stack-contract comment at `time_system.asm:16-18` is upheld by
  `RunClock`/`DrawClockToHud`/`TimeSystem_*` (no unbalanced `PHA/PLX/PLY`
  found).
- **P2-2 (FINE).** `ImpaHint_Check` (`impa_hints.asm:74`) no-ops immediately
  for any follower other than Impa (`$7EF3CC != $01`); no double-fire or
  starvation of Zora Baby/Kiki/minecart-follower triggers found nearby
  (`$09A19C`-`$09AA5E`, no address overlap).
- **P2-3 (FINE).** `SongTintTick` (`Items/ocarina.asm:402`) writes `$9A`
  unconditionally every `Sprite_Main` tick, but `ocarina_song_tint` is off in
  this build (short-circuits to a no-op) and `Sprite_Main` never runs during
  Experiment module `$0D` anyway (it's dispatched by
  `Module_MainRouting`, not by Module07/09's per-frame body) — so it cannot
  fight the experiment script's own `$9A` writes. Re-check if
  `ocarina_song_tint` and `experiment_scene` are ever both enabled.
- **P2-4 (FINE).** OBJ palette row 6: only `player2.asm` (`!P2_PAL = 6`)
  claims it; no other sprite/follower file references "row 6" or the
  `PAL*$20` pattern. Risk is already self-mitigated by `P2_SlotsBusy`/
  `P2_RowIsP2` and documented as a known limitation in the test build's
  `NOTES.md`.
- **P2-5 (FINE).** SRAM layout: `RingSaveBlock` ($7EF3A1-3A6) and
  `FreeBlock_Large` ($7EF3A7+) are correctly adjacent, no overlap.
  `FreeBlock_Dreams` ($7EF412, bank `$7E`, SRAM) and `P2_LastRoom`
  ($7FF412, bank `$7F`, WRAM) share low digits but are different banks —
  not a collision, just a naming trap for a future skim-reader; a one-line
  disambiguating comment in each file would help.

## Not independently confirmed

The SNES Classic/RetroArch-only BG3 tilemap/CHR corruption "in the Abyss"
noted in the brief was not reproduced or root-caused here (no emulator used,
per scope). Static reading of `experiment.asm`'s Abyss shot found no direct
VRAM/hardware-register writes outside the existing forced-blank window; the
`$9A-$9E` writes are WRAM staging bytes applied by NMI as usual. Recommend a
targeted real-hardware-timing trace (Mesen with strict timing, or the
SNES Classic bridge) of the Abyss shot's frame boundary rather than further
static review.
