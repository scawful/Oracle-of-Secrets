# Overworld Softlock — Codebase Analysis and Bug Patterns

**Date:** 2026-01-30  
**Scope:** ZSCustomOverworld, time_system, overworld-related modules; practices and patterns that can cause stack/P corruption or softlocks.

---

## 1. Executive summary

- **ZSCustomOverworld (ZSOW)** is a large (~5.8k lines), third-party-style module that runs partly **outside** the Oracle namespace and hooks NMI, transition GFX, and overworld sprite loading. It uses **direct-page NMI variables** and path-dependent P state in several routines.
- **Time system** (`time_system.asm`) is in the documented crash chain (HUD_ClockDisplay → RunClock → …). It documents a PHP/PLP stack contract and uses PHP/PLP in HUD_ClockDisplay and TimeSystem_CheckCanRun; **CheckIfNight** and **LoadPeacetimeSprites** do **not** guarantee P state on return.
- **Sprite dispatch** (`Core/sprite_new_table.asm`) intentionally sets X=8-bit before `JMP [$0006]` for JumpTableLocal; callers of the hook may then see 8-bit X unless they restore it.
- Recurring risks: **path-dependent P on return**, **JSR vs JSL / RTS vs RTL** pairing at hook boundaries, **no PHP/PLP at hook entry/exit** in some ZSOW and time_system callees, and **main-loop vs NMI shared state** (DP vars) in ZSOW.

---

## 2. ZSCustomOverworld.asm — structure and risks

### 2.1 NMI and direct-page variables

ZSOW defines NMI-related variables in **direct page** (lines 69–76):

```asm
NewNMISource1   = $04D5   ; [0x02]
NewNMITarget1   = $04D3   ; [0x02]
NewNMICount1    = $04D7   ; [0x02]
NewNMITarget2   = $04D9   ; [0x02]
NewNMISource2   = $04DB   ; [0x02]
NewNMICount2    = $04DD   ; [0x02]
```

- **Written** from main-loop/transition code: `BlockGFXCheck` and callers (e.g. ~3063–3115) in transition GFX path; they run in main loop context.
- **Read** from **NMI**: `NMI_UpdateChr_Bg2HalfAndAnimatedLONG` (~4273–4302) runs in NMI and reads these to drive DMA.

**Risks:**

- If main-loop code ever writes to DP in a way that overlaps stack usage (e.g. wrong DP or stack underflow), NMI could see bad data or the main loop could corrupt SP. RootCause doc ruled out direct writes to `$7E1F0A`; the remaining risk is **stack underflow/overflow** leading to wrong return address and then TCS with bad A.
- Race: main loop updates NewNMICount1/2 and NMI reads them in the same frame. Typically one producer and one consumer; still worth documenting that NMI must not assume atomicity of multiple DP words.

### 2.2 LoadOverworldSprites_Interupt ($09C4C7) and Oracle_CheckIfNight

```asm
; ZSCustomOverworld.asm ~5259–5283
LoadOverworldSprites_Interupt:
    LDX.w $040A
    ...
    JSL Oracle_CheckIfNight : ASL : TAY
    REP #$30
    ...
```

- **Oracle_CheckIfNight** (time_system.asm 249–264) does **not** use PHP/PLP. It does `JSR LoadPeacetimeSprites : BCS + : RTL` or later `LDA.l GameState` / `LDA.b #$03` and RTL. So it returns with **unspecified P state** (whatever LoadPeacetimeSprites or the LDA path left).
- LoadOverworldSprites_Interupt immediately does **REP #$30** after the JSL, so **this** caller is safe. Any **other** caller of CheckIfNight that does not restore P after the JSL could leak 8-bit mode.

**Recommendation:** Document “CheckIfNight does not preserve P; callers must set REP/SEP as needed after JSL.” Consider PHP/PLP in CheckIfNight so it returns with caller’s P (or a documented state).

### 2.3 BlockGFXCheck — returns with 8-bit index

**BlockGFXCheck** (ZSOW ~3054–3134):

- Enters with `REP #$30`, then toggles `SEP #$30`, `REP #$30`, `SEP #$20`, `SEP #$10` in the loop.
- Exits with **RTS** and last explicit state **SEP #$30** (see ~3130–3134: `STY.w TransGFXModuleFrame`, `RTS` after a path that uses `SEP #$20` / `SEP #$10`).

So **BlockGFXCheck returns with 8-bit X/Y**. It is called via **JSR** from two places inside ZSOW (~2964, 2998), both in a routine that eventually does `PLB : RTL`. So the chain returns to vanilla with RTL; if the vanilla caller of that chain assumed 16-bit index registers, the 8-bit state could leak.

**Recommendation:** Before RTS in BlockGFXCheck, set a known state (e.g. `REP #$30`) so return contract is “16-bit A/X/Y”, or document “returns with 8-bit index; caller must restore if needed.”

### 2.4 NewLoadTransAuxGFX — path-dependent P on exit

**NewLoadTransAuxGFX** (ZSOW 4149–4258):

- Entry: `PHB : PHK : PLB`.
- Early exits: `.indoors` / normal load path does `PLB` then `JML LoadTransAuxGFX_return` — P is whatever it was on entry (often 8-bit from main loop).
- Long path: toggles `REP #$30`, `SEP #$20`, `SEP #$10`, `REP #$10` many times; ends with `REP #$10` (16-bit X/Y), then `STZ.w TransGFXModuleFrame`, `PLB`, `JML LoadTransAuxGFX_sprite_continue`.

So **returned P state depends on which path was taken**. Vanilla code at `LoadTransAuxGFX_sprite_continue` and the code that invoked the hook may assume a specific P; path-dependent P can cause subtle bugs (e.g. next routine assumes 16-bit X and indexes a table with 8-bit X).

**Recommendation:** Before every exit (JML), set a documented P state (e.g. `REP #$30` or match vanilla’s expectation) so the hook has a single return contract.

### 2.5 NMI_UpdateChr_Bg2HalfAndAnimated — RTS vs RTL

**NMI_UpdateChr_Bg2HalfAndAnimated** (4118–4122):

```asm
NMI_UpdateChr_Bg2HalfAndAnimated:
    JSL.l NMI_UpdateChr_Bg2HalfAndAnimatedLONG
    RTS
```

- The NMI table at `$008C8A` holds a **pointer** to this routine. Vanilla NMI code typically **JSR**s to the table entry (same-bank). So: caller pushes 2-byte return, we JSL (push 3), LONG RTL (pop 3), we RTS (pop 2) → balanced.
- If vanilla ever **JSL**s to this table entry, we would have 3-byte return on stack but we RTS (pop 2) → **stack imbalance** (1 byte left on stack).

**Recommendation:** Confirm in disassembly that the NMI dispatcher uses JSR (not JSL) to the table at $008C8A. If it is JSL, change the wrapper to RTL.

---

## 3. Time system (time_system.asm) — contracts and gaps

### 3.1 HUD_ClockDisplay — good

- **HUD_ClockDisplay** (19–31): PHP, JSR RunClock, JSR DrawClockToHud, REP #$30, JSL $09B06E, PLP, RTL. Matches documented “PHP/PLP only; RunClock and DrawClockToHud must not unbalance stack.”
- **TimeSystem_CheckCanRun** (113–142): PHP, REP #$30, JSL $00FC62, PLP. Balanced and preserves P across the vanilla JSL.

### 3.2 CheckIfNight and LoadPeacetimeSprites — no P contract

- **CheckIfNight** (249–264): No PHP/PLP. Returns with P as left by LoadPeacetimeSprites or by the LDA/CMP path. So **return P is unspecified**.
- **LoadPeacetimeSprites** (534–556): Only LDA/CMP/JMP/RTS. Does not touch stack depth; does not set P explicitly. So **return P = entry P**.

So the only “contract” is that CheckIfNight returns with **undefined P**. Callers that do not restore P (e.g. LoadOverworldSprites_Interupt does REP #$30) are safe; any new caller that assumes 16-bit after CheckIfNight could be wrong.

### 3.3 ColorBgFix and FixShockPalette — PHA/PLA

- **ColorBgFix** (511–533): PHP, PHA, SEP #$30, … branches, then REP #$30, PLA, … PLP, RTL. Balanced.
- **FixShockPalette** (565–579): PHA, … PLA or PHX … PLX, PLA, RTL. Balanced.

No issues found in these for stack depth; they are consistent with StyleGuide’s “preserve state at hook boundaries.”

---

## 4. Sprite dispatch (Core/sprite_new_table.asm)

- **NewMainSprFunction** / **NewSprTable**: Replaces vanilla sprite main loop. Does `SEP #$30` before `JMP [$0006]` so that **JumpTableLocal** (vanilla) sees X=8-bit, which is required for its stack math. So 8-bit X on entry to each sprite routine is **intentional**.
- Sprite routines then RTL back; the **vanilla** code that called the hook (at $06FFF8) gets control back after an RTS. So the **caller** of the hook sees 8-bit X after the hook returns. If that caller or anything up the call chain assumes 16-bit X, that could propagate and contribute to wrong behavior (e.g. later JSL to a routine that assumes 16-bit index).

The Handoff/FixPlan mention PHP/PLP on SpriteActiveExp_MainLong / Sprite_PrepExp_Long; the current snippet in sprite_new_table.asm does not show PHP/PLP there. If those wrappers were reverted or live elsewhere, restoring PHP/PLP at the hook boundary would limit P leakage to vanilla.

---

## 5. Overworld overlays and entrances

- **overlays.asm**: Many routines use explicit REP #$30 / SEP #$30 (or SEP #$20) around blocks; P is toggled locally. No obvious unbalanced push/pull in the sampled regions.
- **entrances.asm**: Overworld_UseEntranceEntry uses PHB/PLB and JSL Overworld_UseEntrance; Overworld_UseEntrance starts with REP #$31 and does not clear it, so it returns with 16-bit and carry clear. Consistent.

---

## 6. Recurring patterns that can cause bugs

| Pattern | Where seen | Risk |
|--------|------------|------|
| **No P contract on return** | CheckIfNight, LoadPeacetimeSprites | Callers that assume 16-bit after JSL can get 8-bit and mis-index or mis-pull stack. |
| **Path-dependent P on exit** | NewLoadTransAuxGFX, BlockGFXCheck | Different exit paths leave different P; upstream code can assume one state and get another. |
| **RTS after JSL to LONG** | NMI_UpdateChr_Bg2HalfAndAnimated | Correct only if caller used JSR. If caller used JSL, RTS pops 2 instead of 3 → stack imbalance. |
| **Returning with 8-bit index** | BlockGFXCheck | Caller continues with 8-bit X/Y; if caller is part of a chain that eventually RTLs to vanilla expecting 16-bit, state leaks. |
| **DP used for NMI/main coordination** | ZSOW NewNMICount1/2 etc. | Theoretically sensitive to DP or stack misuse; write watch on $7E1F0A already ruled out for this bug. |
| **Large hook surface, no namespace** | ZSCustomOverworld.asm | Global scope and many JSL/JSR (150+); any missed P or stack contract is a potential regression. |

---

## 7. Recommendations

1. **Document P and stack contracts** for every hook and every routine called from multiple contexts (e.g. “CheckIfNight: does not preserve P; callers must set REP/SEP after JSL” in a header or Docs).
2. **CheckIfNight**: Add PHP/PLP around the body (or at least restore a documented P before RTL) so return state is defined; alternatively, document and audit all callers.
3. **BlockGFXCheck**: Before RTS, set REP #$30 (or document “returns 8-bit index; caller must restore”).
4. **NewLoadTransAuxGFX**: Before each JML exit, set a single documented P state (e.g. REP #$30).
5. **NMI table at $008C8A**: Verify in bank $00 disassembly that the NMI code uses JSR (not JSL) to the table; if JSL, change the wrapper to RTL.
6. **Sprite hook**: If PHP/PLP was removed from SpriteActiveExp_MainLong / Sprite_PrepExp_Long, restore it so the hook does not leak P to vanilla.
7. **Static analysis**: Keep using `oracle_analyzer.py --check-hooks --find-mx --find-width-imbalance` and extend it to flag “routine returns without REP #$30” or “multiple exit paths with different P” where possible.
8. **Module isolation / bisect**: Continue using the infrastructure in OverworldSoftlock_Plan.md (Path C, D) to narrow whether regressions are in ZSOW, time_system, sprites, or menu; this analysis gives concrete spots to inspect first in each module.

---

## 8. References

- [OverworldSoftlock_InvestigationPaths.md](OverworldSoftlock_InvestigationPaths.md) — Contract documentation, caller audit, usdasm/z3dk/ROM comparison, ZScream vs Oracle patching, ZScreamDungeon.
- [OverworldSoftlock_Plan.md](OverworldSoftlock_Plan.md) — Paths A–D and tooling.
- [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md) — Mechanism (JumpTableLocal, SP corruption, $7E1F0A).
- [OverworldSoftlock_FixPlan.md](OverworldSoftlock_FixPlan.md) — Phase 1B module order, Phase 2 ZSOW NMI audit.
- [Docs/Technical/Core/StyleGuide.md](../Core/StyleGuide.md) — Section 4 (processor state), Section 5 (hooks).
- [Docs/Debugging/Guides/Troubleshooting.md](../General/Troubleshooting.md) — Stack overflow/underflow and JSR/JSL pairing.
