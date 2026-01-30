# Overworld Softlock — Plan

**Updated:** 2026-01-30  
**Status:** Investigating. Static fixes did not resolve. Pick one path below and run with it.

**Two bugs:** Save State 1 = overworld softlock. Save State 2 = file-load dungeon freeze (track separately).

**Mechanism (confirmed):** JumpTableLocal at `$008781` uses PLY; when X is 8-bit, PLY pops 1 byte instead of 2 → stack misaligned → RTL to garbage → JSL into WRAM → black screen. We have not yet found the **instruction** that leaves X 8-bit or corrupts SP; static analysis and several targeted fixes did not fix it.

---

## Path A — Hands-on (no debugger required)

Pick one. See [OverworldSoftlock_LessCerebralOptions.md](OverworldSoftlock_LessCerebralOptions.md) for full text.

| # | Option | What you do |
|---|--------|-------------|
| 1 | **Play and log** | Play; when it softlocks, write “Did X, then Y, then black screen.” Keep a “last good” savestate. |
| 2 | **One fix, then test** | Apply one low-risk change (e.g. fix JumpTableLocal once for width, or NMI SP clamp). Build, play same route, see if softlocks drop. |
| 3 | **Golden path** | Define one path that must never softlock (e.g. start → overworld → first dungeon door). Make that the only regression test until it’s solid. |
| 4 | **On-screen debug** | Show SP (or 1–2 key values) on screen during play. On softlock, note the last value. See [OverworldSoftlock_LessCerebralOptions.md](OverworldSoftlock_LessCerebralOptions.md) §4 for how to add. |
| 5 | **Savestate checklist** | Keep “known good” savestates (boot, load, key events). On softlock, reload last good and shorten repro. |
| 6 | **Ask the community** | Post minimal repro + savestate/ROM on romhacking.net or Discord. |
| 7 | **Compare builds** | If you have an older build that doesn’t softlock on same route, diff or compare what changed. |
| 8 | **Feature freeze** | Pause new overworld/sprite features; only fix regressions on that path. |

**Golden path regression test (option 3):** Run `./scripts/run_regression_tests.sh regression --tag golden_path` or `python3 scripts/test_runner.py tests/regression/golden_path_overworld.json`.

---

## Path B — Find the corrupting instruction (debugger)

**Goal:** Catch the exact PC that corrupts SP or leaves P (X) 8-bit. Then fix that one place.

1. **Run repro script** (recommended):
   ```bash
   cd ~/src/hobby/oracle-of-secrets
   python3 scripts/repro_stack_corruption.py --strategy polling --frames 600 --output /tmp/blame_report.json
   ```
   Or `--strategy sp_range` / `--strategy breakpoint` if supported.

2. **Or watch NMI SP save location:** Use `repro_stack_corruption.py --strategy polling` for SP attribution, or manually:
   ```bash
   python3 scripts/mesen2_client.py mem-watch add 0x7E1F0A --size 2 --depth 500
   python3 scripts/mesen2_client.py load 1
   # Play until crash, then:
   python3 scripts/mesen2_client.py mem-blame --addr 0x7E1F0A
   ```

3. **Resolve blame PC to symbol:**  
   `z3ed rom-resolve-address --address=<PC> --rom=Roms/oos168x.sfc`

4. **Fix that routine** (e.g. restore P or balance stack), build, retest.

Details: [OverworldSoftlock_Handoff.md](OverworldSoftlock_Handoff.md) (dynamic capture), [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md) (mechanism).

---

## Path C — Find the guilty module (no debugger)

**Goal:** Identify which Oracle module introduced the regression by turning features off.

1. **Isolation:** In `Util/macros.asm` set `!DISABLE_<MODULE> = 1` (or use `python3 scripts/set_module_flags.py --disable <module>`). Build: `./scripts/build_rom.sh 168`. Test state 1 (and 2 if desired).
2. **Order (safest first):** Masks → Music → Menu → Items → Patches → Sprites → Dungeon → Overworld. See [OverworldSoftlock_FixPlan.md](OverworldSoftlock_FixPlan.md) Phase 1B table.
3. **Optional:** Run `./scripts/run_module_isolation.sh` to cycle through modules in order (or `--next N` for step N, `--next 9` to reset).
4. **When crash disappears:** Re-enable that module, then bisect inside it (comment out `incsrc` lines in its `all_*.asm`) to find the file/routine.
5. **Fix the identified routine**, then re-enable and verify.

Details: [OverworldSoftlock_FixPlan.md](OverworldSoftlock_FixPlan.md) (Phase 1B), [Module_Isolation_Plan.md](Module_Isolation_Plan.md).

---

## Path D — Find the introducing commit

**Goal:** Bisect to the commit that introduced the instability (Nov 22–Jan 26 window).

**Automated bisect:** Requires Mesen2 running with ROM loaded and socket available. After each step the script builds the ROM; reload the ROM in Mesen2 before the next run (or use a launcher that auto-reloads).

```bash
cd ~/src/hobby/oracle-of-secrets
git bisect start HEAD <last-known-good-commit>
git bisect run python3 scripts/bisect_softlock.py
```

Manual: for each step run `./scripts/build_rom.sh 168`, test in emulator, then `git bisect good` or `git bisect bad`.

**Suspects:** `8b23049` (menu rewrite), `93bd42b` (time system), `d41dcda` (ZSOW v3). See [OverworldSoftlock_FixPlan.md](OverworldSoftlock_FixPlan.md) Phase 3.

---

## Coordination and tooling

- **ROM:** Build from `Roms/oos168_test2.sfc`; load `Roms/oos168x.sfc` in Mesen2. Confirm CRC before captures.
- **Mesen2:** Use isolated instance + socket; don’t attach to another agent’s live socket.
- **Save states:** Slot 1 = overworld softlock repro, Slot 2 = dungeon freeze.

### Savestate checklist (Path A.5)

| Slot / ID | Purpose | How to capture |
|-----------|---------|-----------------|
| **Slot 1** | Overworld softlock repro (State 1) | Reproduce softlock in overworld, then save to slot 1 in Mesen2 (or `python3 scripts/mesen2_client.py save 1`). |
| **Slot 2** | File-load dungeon freeze (State 2) | Load file, enter dungeon, freeze; save to slot 2. Track separately from State 1. |
| **Known-good (optional)** | Boot completed | After title/boot, save to a spare slot (e.g. 5) or use state library: `python3 scripts/mesen2_client.py smart-save 5 --label "boot_done"`. |
| **Known-good (optional)** | After load, before overworld | Save just before overworld play; use to shorten repro. |
| **Known-good (optional)** | Key event X | Capture after specific transitions for bisect or sharing. |

State library: see [Docs/Testing/SaveStateLibrary.md](../Testing/SaveStateLibrary.md) and `scripts/mesen2_client.py lib-save` / `lib-load`.

**Key refs:**

| Doc | Role |
|-----|------|
| [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md) | Mechanism, static findings, “root cause first” |
| [OverworldSoftlock_Handoff.md](OverworldSoftlock_Handoff.md) | What was tried, dynamic capture commands |
| [OverworldSoftlock_FixPlan.md](OverworldSoftlock_FixPlan.md) | Phase 1–5 detail, module list, bisect commands |
| [OverworldSoftlock_Investigation_Alternatives.md](OverworldSoftlock_Investigation_Alternatives.md) | TCS breakpoint, JumpTableLocal patch, NMI validation |
| [OverworldSoftlock_LessCerebralOptions.md](OverworldSoftlock_LessCerebralOptions.md) | Full text for Path A options |
| [OverworldSoftlock_CodebaseAnalysis.md](OverworldSoftlock_CodebaseAnalysis.md) | ZSOW/time_system/sprite patterns and bug-risk analysis |
