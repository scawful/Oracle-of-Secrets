# Overworld and Dungeon Softlock — Root Cause Investigation

**Date:** 2026-01-30  
**Purpose:** Synthesize potential root causes from existing evidence and codebase inspection. No dynamic capture was run; this report ranks hypotheses and points to next steps.

---

## 1. Confirmed Mechanism (from handoff)

- **SP** leaves the valid page (0x01xx) and lands in **0x0Dxx** (observed: SP=0x0D08 at crash).
- **NMI** then does PHK/PLB; **PLB** pulls from the (already wrong) stack → **DBR=0x50**.
- Main dispatch reads with DBR=0x50 → garbage pointer → **JML into RAM** → BRK/STP → black screen.
- **JumpTableLocal with X=8-bit is expected**; the real bug is whatever corrupts **SP** (or the NMI SP save location **$7E1F0A**) before NMI.

SP can only change via: **TCS**, **TXS**, **push/pull** instructions, or interrupt entry/exit. So either:

1. **TCS with bad A** — Some code path does TCS with A in 0x0Dxx (or A such that SP ends up there). The only TCS in ROM are in the NMI handler, and they do `LDA $1F0A : TCS`, so the bad value would have to come from **$7E1F0A**.
2. **Stack depth corruption** — Too many pushes (or too few pulls) somewhere, so SP moves out of 0x01xx; by the time NMI runs, SP is wrong and NMI’s PHK/PLB pull from the wrong place.

---

## 2. Ruled out (from prior work)

- **Direct writes to $7E1F0A** — MEM_WATCH on $7E1F0A saw **no writes** during repro. So POLYSTACKL is not being overwritten by observed code paths in that run.
- **JumpTableLocal X=8-bit** — Intentional; not the cause.
- **HUD hook at $06:8361** — Patching to vanilla did not fix.
- **ColorBgFix PHP/PLP** — Partial mitigation only.
- **Session 3 static fixes** — SEP #$20 in sprite dispatch, PHP/REP in time_system, JMP .continue in menu; all applied, crash persists.

---

## 3. Potential root causes (ranked)

### H1: Stack overflow (excessive pushes) before NMI — HIGH

**Idea:** A routine (or chain) pushes more than it pulls, or pulls less than a caller pushed, so SP drifts downward. Over many frames or one heavy path, SP leaves 0x01xx (e.g. wraps or reaches 0x0Dxx).

**Why plausible:** Static analysis reported **413 width-dependent stack imbalances** (PHA/PLA, PHX/PLX, PHY/PLY with different M/X at push vs pull). Several are in **sprite/ancilla** code (bank 06) and in **Overworld_Entrance** → **Oracle_ApplyRumbleToSprites**. A single wrong-width PLA (e.g. 8-bit pull where 16-bit was pushed) leaves SP off by one; repeated or in a hot path could eventually produce a wrong SP or wrong value pulled into A and then TCS.

**Where to look:**

- **Bank 06 sprite routines** (static analysis): Oracle_Sprite_TransmuteToBomb, Oracle_Sprite_CheckIfLifted, Oracle_Sprite_CheckDamageToPlayer_same_layer, Oracle_Sprite_BumpDamageGroups, Oracle_ApplyRumbleToSprites, Oracle_SpriteDraw_Locksmith, Oracle_ForcePrizeDrop_long.
- **Overworld_Entrance** ($1BC1C3) → **Oracle_ApplyRumbleToSprites** ($068142/$068189): PHA 16-bit at entrance, PLA 8-bit in rumble — **3+ routines** (RootCause doc).
- **Oracle_Ancilla_CheckDamageToSprite** ($06ECC8) → **Oracle_Sprite_CheckIfLifted** ($06ACF1): M=16 push vs M=8 pull — **8 sprite routines** (followers, bean_vendor, korok, minecart, village_dog, puffstool, helmet_chuchu, eon_scrub, business_scrub).

**USDASM cross-check update (2026-01-30):**
- **Confirmed in vanilla USDASM:** `Overworld_Entrance` PHA at `$1BC1C3` and PLAs at `$068142/$068189` (sprite terrain spawn paths), plus `SpriteDraw_Tabulated` PHX at `$05DF7A` and PLX at `$05DFE3`.
- **Balanced in vanilla:** `Ancilla_CheckDamageToSprite` has a local PHA/PLA pair (`$06ECC8`/`$06ECCF`); the reported pull at `$06ACF1` is **not** a PLA in USDASM.
- **Patched-ROM delta:** In `oos168x.sfc`, `$06ACF1` is a PLA (byte `0x68`), so this mismatch is **real in the patched build** even though vanilla USDASM shows `STA.l $7FF9FE,X` there.
- **Action:** Treat `$043519/$0401C8` as **unverified** until confirmed in a ROM disassembly (z3disasm) or live trace; treat `$06ACF1` as **patched-ROM** only.

**Next step:** Dynamic capture: **conditional breakpoint `sp >= 0x0200`** (or **`sp < 0x0100`**), repro, then **TRACE** + **STACK_RETADDR** at hit to see the exact instruction and call chain. Alternatively **frame-by-frame SP polling** until SP leaves 0x01xx.

---

### H2: $7E1F0A written on a path not yet observed — MEDIUM

**Idea:** Something writes the NMI SP save location **$7E1F0A** with a bad value (e.g. 0x0D08). The write happens only on a specific path (e.g. certain room, sprite set, or transition), so the earlier MEM_WATCH repro didn’t hit it.

**Why plausible:** NMI’s TCS loads SP from $7E1F0A. If that word is corrupted, next NMI restores SP to the wrong value. POLYSTACKL is documented in Core/ram.asm as “Stack pointer for polyhedral threads”; polyhedral or other code could write it.

**Where to look:**

- Grep for **1F0A**, **$1F0A**, **POLYSTACKL** in Oracle ASM and in vanilla disassembly (bank 00/01 for NMI).
- **MEM_WATCH** on $7E1F0A with **wider repro** (multiple states, dungeon + overworld, more frames).

**Next step:** Broader repro (State 1 and State 2, more frames); MEM_WATCH $7E1F0A again; if still no write, treat H1 as more likely.

---

### H3: Path-dependent P in ZSOW → wrong stack width elsewhere — MEDIUM

**Idea:** ZSOW routines return with **unspecified or 8-bit index** (P). A caller (or a routine later in the same frame) assumes 16-bit and does a 16-bit push; then another path does an 8-bit pull (or vice versa), unbalancing the stack.

**Evidence from codebase:**

- **BlockGFXCheck** (ZSCustomOverworld.asm 3054–3134): Enters REP #$30, then toggles SEP #$30, SEP #$20, SEP #$10, REP #$20 in the loop. **Exits with RTS** after STY.w TransGFXModuleFrame; last P state in loop can be **SEP #$30** or **SEP #$10** → **returns with 8-bit X/Y**. Called via **JSR** from two places (~2964, 2998); if the caller chain returns to vanilla and vanilla assumes 16-bit index, that could feed into a later width mismatch.
- **NewLoadTransAuxGFX** (4149–4258): **.indoors** path does PLB then JML LoadTransAuxGFX_return with **no REP #$30** → P on exit = entry P (often 8-bit). Long path toggles REP #$30, SEP #$10, REP #$10; ends with REP #$10 (16-bit X/Y) but **not** necessarily full REP #$30 → **path-dependent P on exit**.

**Next step:** Add **REP #$30** (or documented P contract) before **every** exit in BlockGFXCheck and NewLoadTransAuxGFX; retest. If crash disappears, narrow to that hook and then to the specific caller that was affected.

---

### H4: CheckIfNight / LoadPeacetimeSprites return P unspecified — LOWER

**Idea:** **CheckIfNight** (time_system.asm 252–265) has **no PHP/PLP**; return P is whatever LoadPeacetimeSprites or the LDA path left. Any caller that doesn’t set REP/SEP after JSL could leak 8-bit mode into a later routine that does 16-bit push/pull.

**Evidence:** LoadOverworldSprites_Interupt does **REP #$30** immediately after JSL Oracle_CheckIfNight, so **that** caller is safe. Other callers of CheckIfNight (if any) must be audited; RootCause doc notes “Callers: LoadOverworldSprites_Interupt … does REP #$30 after JSL.”

**Next step:** Grep for **CheckIfNight** / **Oracle_CheckIfNight**; ensure every call site restores P (or add PHP/PLP inside CheckIfNight). Low priority unless another caller is found.

---

### H5: Menu / HUD PHB-PLB or PHP-PLP imbalance — LOWER

**Idea:** ActivateSubScreen or HUD_Update (or related) has PHB/PLB or PHP/PLP imbalance, leading to wrong stack depth and eventually wrong SP or wrong byte pulled by PLB in NMI.

**Evidence:** Static analysis reported **ActivateSubScreen** exit: PHB/PLB imbalance (3 pushes vs 6 pulls). **HUD_Update** / **HUD_UpdateItemBox** exit: many unbalanced PHP/PLP and PHD/PLD. Session 3 already added PHP/PLP in HUD_ClockDisplay and fixed menu .max_N PLA; crash persists, so the main crash path may not go through these, or the imbalance is elsewhere in the same subsystem.

**Next step:** Run **oracle_analyzer.py** (or equivalent) and list every hook with PHB/PLB or PHP/PLP imbalance; fix or document each. If crash persists, deprioritize vs H1/H2/H3.

---

## 4. Two bugs (keep separate)

- **State 1 — Overworld softlock:** Repro: load slot 1 (overworld), press A, run; black screen within seconds. Use same state + same actions for dynamic capture.
- **State 2 — File-load dungeon freeze:** Repro: load slot 2 (file-load dungeon), press A; freeze. Track and capture separately; may be same root cause (SP/$7E1F0A) or a different code path.

---

## 5. Recommended next steps (in order)

1. **Validate suspect addresses (USDASM vs ROM)**  
   Before patching, confirm that each flagged push/pull site is **code** in USDASM or in a **ROM disassembly** of the patched build. If an address only exists as data in USDASM, treat it as a mapping artifact until proven otherwise.
2. **Dynamic capture (SP)**  
   Run repro with **conditional breakpoint `sp >= 0x0200`** (or `sp < 0x0100`). When it hits: **TRACE** (e.g. 500 instructions), **STACK_RETADDR**, **P_LOG**. Resolve PC to source (SYMBOLS_RESOLVE, z3ed, Hyrule Historian). This directly targets H1 (and narrows H2/H3 to a specific instruction).
3. **Repro script**  
   `python3 scripts/repro_stack_corruption.py --strategy auto` (or `--strategy polling --frames 600`) for State 1; `--slot 2 --press-a` for State 2. Inspect captured report for faulting PC and call chain.
4. **ZSOW P contract**  
   In **BlockGFXCheck** and **NewLoadTransAuxGFX**, set **REP #$30** (or a single documented P state) before every RTS/JML exit; retest. If crash stops, bisect to the exact exit/caller (H3).
5. **Wider MEM_WATCH on $7E1F0A**  
   Repro with both states and longer runs; MEM_WATCH $7E1F0A again. If a write appears, attribute it (MEM_BLAME) and map to source (H2).
6. **Module isolation**  
   `./scripts/run_module_isolation.sh --auto` (or disable sprites, then overworld, then menu); see which disable removes the crash. Correlate with H1/H3 (sprites/overworld) or H5 (menu).

---

## 6. References

- [RootCause_Investigation_Handoff.md](RootCause_Investigation_Handoff.md) — Mechanism, evidence, capture commands.
- [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md) — Static analysis, prioritized routines, Session 3 fixes.
- [OverworldSoftlock_CodebaseAnalysis.md](OverworldSoftlock_CodebaseAnalysis.md) — ZSOW/time_system/sprite contracts and risks.
- [Root_Cause_Debugging_Workflow.md](../Tooling/Root_Cause_Debugging_Workflow.md) — Phases 3–5 (instrument, isolate, map to source).
- [OverworldDungeon_Softlock_Approach.md](OverworldDungeon_Softlock_Approach.md) — Reproducibility, isolation, dynamic capture strategy.
