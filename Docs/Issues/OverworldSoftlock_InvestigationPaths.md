# Overworld Softlock — Investigation Paths

**Date:** 2026-01-30  
**Purpose:** Document contract conventions, caller-audit methodology, usdasm/z3dk/ROM comparison workflows, ZScream vs Oracle patching, and ZScreamDungeon interaction as **paths to investigate further**. This doc does not perform the investigations; it records how to run them and what to compare.

**Related:** [OverworldSoftlock_Plan.md](OverworldSoftlock_Plan.md), [OverworldSoftlock_CodebaseAnalysis.md](OverworldSoftlock_CodebaseAnalysis.md), [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md).

---

## What to look into first

| Order | Action | Why |
|-------|--------|-----|
| **1** | **Module isolation (Path C)** — run `./scripts/run_module_isolation.sh` or disable modules in order (Masks → … → Overworld), build, test state 1/2 | Tells you *which* module is guilty; then bisect inside that module. Highest leverage to narrow the bug. |
| **2** | **BlockGFXCheck: add REP #$30 before RTS** (ZSCustomOverworld.asm ~3132) | One-line fix; removes 8-bit index leak on return. Low risk. |
| **3** | **Git bisect (Path D)** — if you have a known-good commit (e.g. before Nov 22), run `git bisect run python3 scripts/bisect_softlock.py` | Finds the introducing commit; then inspect that diff. |
| **4** | **NewLoadTransAuxGFX: normalize P before each JML exit** (e.g. REP #$30 before PLB/JML) | Removes path-dependent P; a few lines. |
| **5** | **Caller audit** — fill the table in §2.2 for CheckIfNight, BlockGFXCheck, NewLoadTransAuxGFX | Confirms no other callers assume wrong P; quick grep + hooks.json. |
| **6** | **z3dk oracle_analyzer** on vanilla ROM vs oos168x.sfc; diff `--find-width-imbalance` / `--find-mx` | Baseline “Oracle-only” mismatches; helps prioritize fixes. |

**Already checked:** NMI dispatcher uses JMP (.vectors,X); vector RTS is correct. ZSOW wrapper does not need RTL.

---

## 1. Documentation contracts (done and pending)

### 1.1 Done

- **CheckIfNight** (`Overworld/time_system.asm`): Header documents “Does NOT preserve P; callers must set REP/SEP after JSL.” Return: A = phase; P unspecified. Caller: LoadOverworldSprites_Interupt (ZSCustomOverworld.asm) does REP #$30 after JSL.
- **CheckIfNight16Bit**: Header documents “Does NOT preserve P; sets SEP #$30 on entry; returns REP #$30 on all paths.” No active callers (hook sites commented out for ZSOWv3).
- **LoadPeacetimeSprites**: Header documents “Does NOT modify P explicitly; return P = entry P. Stack: no push/pull; JSR-safe.” Return: C set/clear; A clobbered.

### 1.2 Pending (paths to complete)

- **BlockGFXCheck** (ZSCustomOverworld.asm ~3054): Document “Returns with 8-bit index (SEP #$30); caller must restore if 16-bit expected” or add REP #$30 before RTS.
- **NewLoadTransAuxGFX** (ZSCustomOverworld.asm 4149): Document “Return P is path-dependent; early exit = entry P, long path = REP #$10” and/or normalize P before every JML exit.
- **NMI_UpdateChr_Bg2HalfAndAnimated** (ZSCustomOverworld.asm 4118): Document “Caller must use JSR (2-byte return); we RTS. If NMI ever JSLs to table, change to RTL.”
- **HUD_ClockDisplay** (time_system.asm): Already has stack contract in comments; ensure every hook in the crash chain has a one-line contract in code or in [Docs/Core/StyleGuide.md](../Core/StyleGuide.md) “Hook contracts” section.

---

## 2. Caller audit

### 2.1 Goals

- List every caller of routines that have no (or weak) P/stack contracts so we can verify each restores P or accepts the documented state.
- Cross-check against vanilla (usdasm) so we know what *would* have called the same address and what we replaced.

### 2.2 Methodology

1. **Grep for JSL/JSR to the routine name** (e.g. `Oracle_CheckIfNight`, `CheckIfNight`).  
   Paths: `oracle-of-secrets/**/*.asm`, `oracle-of-secrets/**/*.md` (docs sometimes reference call sites).

2. **hooks.json**: For hooks that *replace* vanilla code, the hook target is the “caller” of our replacement; the *real* callers are whatever vanilla code JSL/JSR’d to the original address. Use hooks.json to get original address, then search usdasm for that address to list vanilla callers.

3. **z3dk oracle_analyzer**:  
   `python3 ~/src/hobby/z3dk/scripts/oracle_analyzer.py --rom Roms/oos168x.sfc --hooks hooks.json --check-hooks --find-mx --find-width-imbalance`  
   Use to find JSL/JSR to hook addresses and M/X mismatches at call sites.

4. **Caller audit table** (to fill when running the audit):

   | Routine              | Callers (Oracle ASM)                    | Vanilla callers (usdasm)     | P restored after call? |
   |----------------------|-----------------------------------------|------------------------------|--------------------------|
   | Oracle_CheckIfNight  | LoadOverworldSprites_Interupt (ZSOW)    | (replaced $09C4E3 LDA $7EF3C5 path) | Yes (REP #$30)          |
   | LoadPeacetimeSprites | CheckIfNight, CheckIfNight16Bit         | N/A (Oracle-only)            | N/A (JSR, same bank)     |
   | BlockGFXCheck        | 2× JSR in ZSOW transition code          | N/A (ZSOW-only)              | No (caller then PLB RTL) |
   | …                    | …                                       | …                            | …                        |

### 2.3 Paths to investigate further

- Run the above for **CheckIfNight**, **BlockGFXCheck**, **NewLoadTransAuxGFX**, **NMI_UpdateChr_Bg2HalfAndAnimated**, and any hook in the crash chain (HUD_ClockDisplay, Sprite_ExecuteSingle, JumpTableLocal).
- Add a “Hook contracts” subsection to StyleGuide or a dedicated `Docs/Issues/Hook_Contracts.md` that lists every hook’s P/stack contract and callers.

---

## 3. usdasm comparison

### 3.1 Vanilla references (usdasm paths)

- **usdasm location:** `~/src/hobby/usdasm/` (or `../usdasm` from oracle-of-secrets).  
  Banks: `bank_00.asm` … `bank_0F.asm`, `bank_1A.asm`, etc.

- **Key addresses for overworld softlock:**

  | Address   | File       | Vanilla label / behavior |
   |-----------|------------|---------------------------|
   | $09C4C7   | bank_09.asm | Start of LoadOverworldSprites: LDA.w $040A, TAY, LDX OverworldScreenSizeForLoading,Y, … REP #$30, LDA.w $040A ASL TAY, SEP #$20, **LDA.l $7EF3C5** (game state), CMP #$03/#$02, then LDA Overworld_SpritePointers_state_*+0,Y etc. |
   | $09C4E3   | bank_09.asm | LDA.l $7EF3C5 (vanilla reads SRAM for phase) — *replaced by ZSOW with JSL Oracle_CheckIfNight* (currently ZSOW replaces from $09C4C7 so whole block is our code). |
   | $008C8A   | bank_00.asm | `dw NMI_TilemapNothing` (index 0x06). Vanilla NMI table entry 6 = no-op (RTS). ZSOW replaces with `dw NMI_UpdateChr_Bg2HalfAndAnimated`. |
   | $008E4B   | bank_00.asm | NMI_TilemapNothing: RTS. |
   | NMI dispatch | bank_00.asm | **Verified:** Dispatcher does `LDA.b $17 : ASL A : TAX : STZ.b $17 : JMP.w (.vectors,X)` ($008C75–$008C7B). So the vector is entered via **JMP**, not JSR/JSL. The stack still holds the 2-byte return address from the earlier JSR that led to this code; the vector routine’s **RTS** is correct. ZSOW’s wrapper (JSL to LONG, RTL, then RTS) is balanced. No change needed. |

### 3.2 Comparison workflow

1. **Disassemble vanilla ROM** (if needed): Use usdasm as the reference; it is the US disassembly. For a specific ROM (e.g. oos168.sfc), ensure it matches usdasm’s bank layout or note differences (header, checksum).
2. **Diff hook replacement vs vanilla:** For each hook (e.g. $09C4C7, $008C8A), compare:
   - Bytes/lines in usdasm at that address (vanilla behavior).
   - Our replacement (Oracle/ZSOW) in the repo.
   - Ensure our replacement preserves stack depth and return convention (JSR→RTS, JSL→RTL) where we do not replace the entire call chain.
3. **NMI table dispatch:** In bank_00.asm, search for references to the table at $008C7E (e.g. LDX $17; JSR (.vectors,X) or similar). Document “NMI uses JSR to table” or “JSL to table” so ZSOW’s NMI_UpdateChr_Bg2HalfAndAnimated wrapper (RTS vs RTL) is correct.

### 3.3 Paths to investigate further

- Confirm NMI dispatcher instruction (JSR vs JSL) to the table at $008C8A.
- For every overworld/time-system hook, write a one-line “Vanilla: … ; We: …” in code or in Hook_Contracts.md.
- Optionally: script that extracts bytes from vanilla ROM at hook addresses and compares to patched ROM (same addresses) to catch accidental overwrites.

---

## 4. z3dk and vanilla vs Oracle ROMs

### 4.1 z3dk oracle_analyzer

- **Path:** `~/src/hobby/z3dk/scripts/oracle_analyzer.py`  
- **Typical usage:**  
  `python3 ~/src/hobby/z3dk/scripts/oracle_analyzer.py --rom Roms/oos168x.sfc [--hooks hooks.json] --check-hooks --find-mx --find-width-imbalance [--check-abi]`  
- Use to:
  - List hook sites and callers (from ROM + hooks.json).
  - Find M/X flag mismatches and width-dependent stack imbalances.
  - Compare output across ROM versions (see below).

### 4.2 Vanilla vs Oracle ROM versions

- **ROM naming (oracle-of-secrets):**
  - Base: `Roms/oos168.sfc` or `Roms/oos168_test2.sfc` (prefer test2 when present; see build_rom.sh).
  - Patched: `Roms/oos168x.sfc` (output of Asar on Oracle_main.asm).
- **Comparing versions:**
  1. **Vanilla (unpatched) ROM:** e.g. `oos168.sfc` or a known-good vanilla copy. Run oracle_analyzer on it *without* Oracle hooks (or with a minimal hooks list) to get a baseline (e.g. no Oracle hooks, so no Oracle-induced M/X issues).
  2. **Historical Oracle builds:** If you have older oos168x.sfc builds (e.g. from git history or backups), run oracle_analyzer on each and diff the reports (e.g. `--find-width-imbalance` output, hook list). Bisect to the build that first introduced a given mismatch or failure.
  3. **Bisect (Plan Path D):** Use `scripts/bisect_softlock.py` with different base ROMs if needed (e.g. OOS_BASE_ROM=… to test “same Oracle code, different base ROM” vs “same base, different Oracle commit”).

### 4.3 Paths to investigate further

- Run oracle_analyzer on vanilla ROM (no Oracle) and on current oos168x.sfc; document “only in Oracle” findings.
- Keep a small set of ROMs: vanilla, oos168_test2 (base), oos168x (current), and one or two older oos168x from before Nov 22 – Jan 26 window; re-run analyzer and bisect when chasing regressions.
- Add to FixPlan or this doc: “ROM version matrix” (rows = ROM file, columns = analyzer flags) for future runs.

---

## 5. ZScream and ZSCustomOverworld — patch order and custom edits

### 5.1 Build pipeline (oracle-of-secrets)

1. **Base ROM:** `Roms/oos168_test2.sfc` (preferred) or `Roms/oos168.sfc`.  
   - RootCause doc: “Build script prefers oos168_test2.sfc (ZScream v3 edited, Nov 16) over oos168.sfc.” So the *base* is already a ZScream-edited ROM (expanded banks, ZS tile data, etc.), not raw vanilla.
2. **Single Asar patch:** `Oracle_main.asm` is applied to the base ROM → `Roms/oos168x.sfc`.  
   - Oracle_main.asm incsrc’s (among others) `Overworld/overworld.asm` (time_system, overlays, entrances, etc.) and then **Overworld/ZSCustomOverworld.asm** (outside namespace). So **ZSCustomOverworld is patched in one shot with all Oracle code**; there is no “first ZScream patch, then Oracle patch” in the script — the base ROM is already ZScream output, and we only run Asar once.

### 5.2 ZScream vs Oracle source of ZSCustomOverworld

- **In-repo file:** `oracle-of-secrets/Overworld/ZSCustomOverworld.asm` is the one included by Oracle_main.asm. It is the **Oracle-maintained** version (with our edits: e.g. LoadOverworldSprites_Interupt calling JSL Oracle_CheckIfNight, NMI table entry 6 replaced, etc.).
- **Util/ZScreamNew/ZSCustomOverworld.asm** is in .gitignore; it is typically the **ZScream editor output** or a copy used by the ZScream tool. We do *not* assemble from that file; we assemble from Overworld/ZSCustomOverworld.asm. So any divergence between Util/ZScreamNew/ZSCustomOverworld.asm and Overworld/ZSCustomOverworld.asm is a potential source of confusion (e.g. if someone re-exports from ZScream and overwrites Overworld/ without merging our Oracle_CheckIfNight and other edits).

### 5.3 Interaction risks

- **Base ROM (oos168_test2) content:** If ZScream writes certain tables or code into the base ROM (e.g. pool data, tile data in banks $3E/$3F), and our Asar patch *also* writes to those addresses (via org in ZSCustomOverworld or elsewhere), we could double-patch or conflict. RootCause noted banks $3E–$3F have ~970 tile diffs (expected from ZScream). So far no evidence of byte-level conflict; still, document that “base ROM is ZScream output; Oracle only appends/replaces at org’d addresses.”
- **Include order:** Oracle_main.asm loads Overworld (time_system, etc.) inside namespace, then loads ZSCustomOverworld *outside* namespace. So ZSOW can call into Oracle (e.g. Oracle_CheckIfNight) but must use the Oracle_ prefix for names in the namespace. Any future reorder (e.g. ZSOW before time_system) could break label resolution.

### 5.4 Paths to investigate further

- Document in a single place: “Base ROM = ZScream output (oos168_test2). Oracle applies one Asar patch (Oracle_main.asm). ZSCustomOverworld.asm in Overworld/ is the canonical one; Util/ZScreamNew/ is editor output, not assembled.”
- If you have a ZScream project or export that produces oos168_test2.sfc, note the exact ZScream version and options so that regenerating the base ROM is reproducible.
- Optionally: list all `org` in ZSCustomOverworld.asm and confirm none fall inside regions that ZScream might also write (e.g. banks $28–$2A “ZS Reserved” per Oracle_main.asm comments).

---

## 6. ZScreamDungeon and patch interaction

### 6.1 What ZScreamDungeon is

- **Location:** `~/src/hobby/ZScreamDungeon/` — C# project (ZeldaFullEditor, PatchesSystem with AsmPatch/AsmPlugin). It is a **dungeon/ROM editor** (graphics, sprites, patches), not the same as the “ZScream” that produces the overworld base ROM. Naming: “ZScream” often refers to the overworld editor/tool that produces expanded OW; “ZScreamDungeon” is the dungeon-focused editor.

### 6.2 How it could interact with Oracle

- If ZScreamDungeon **applies ASM patches** to a ROM (e.g. via PatchesSystem/AsmPlugin), then the **order** of operations could be:
  - Option A: Vanilla → ZScreamDungeon patches → that ROM used as base for Oracle → Oracle_main.asm. Then Oracle and ZScreamDungeon both patch the same ROM; any overlapping `org` would conflict.
  - Option B: Oracle base (oos168_test2) is produced by the *overworld* ZScream tool; ZScreamDungeon is never run on that base. Then no interaction.
- Current build_rom.sh uses only one base ROM and one Asar invocation (Oracle_main.asm). So **unless** the base ROM (oos168_test2) was ever produced by running ZScreamDungeon, there is no direct interaction in the current pipeline. It remains important to document “what produced the base ROM” so that future use of ZScreamDungeon (e.g. adding dungeon patches) is done in a way that doesn’t overwrite Oracle hooks or vice versa.

### 6.3 Paths to investigate further

- Confirm whether oos168_test2.sfc is produced by (1) overworld ZScream only, (2) ZScreamDungeon only, or (3) both in sequence. Document in this doc or in [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md) “Base ROM provenance.”
- If you introduce ZScreamDungeon into the pipeline: define a clear order (e.g. vanilla → ZScream OW → ZScreamDungeon → Oracle_main.asm) and a list of reserved address ranges for each step so patches don’t overlap.
- List ZScreamDungeon patch files (e.g. under PatchesSystem or ZeldaFullEditor) that modify bank $00, $09, or overworld-related banks; cross-check against Oracle’s org’d addresses in ZSCustomOverworld and time_system.

---

## 7. Summary: investigation paths checklist

Use this as a living checklist; tick when a path has been run and where results are recorded.

| # | Path | Where to record results |
|---|------|--------------------------|
| 1 | Add contract headers for BlockGFXCheck, NewLoadTransAuxGFX, NMI_UpdateChr wrapper (and optionally Hook_Contracts.md) | ZSCustomOverworld.asm, Docs |
| 2 | Caller audit: CheckIfNight, BlockGFXCheck, NewLoadTransAuxGFX, NMI wrapper, HUD_ClockDisplay | This doc §2, or Hook_Contracts.md |
| 3 | usdasm: Confirm NMI dispatcher uses JSR (not JSL) to table at $008C8A | **Done:** Dispatcher uses JMP (.vectors,X); vector RTS is correct. This doc §3. |
| 4 | usdasm: Per-hook “Vanilla: … ; We: …” for $09C4C7, $09C4E3, $008C8A | This doc §3, or code comments |
| 5 | z3dk: Run oracle_analyzer on vanilla ROM vs oos168x.sfc; diff reports | This doc §4, or FixPlan |
| 6 | ROM version matrix: vanilla, oos168_test2, oos168x (current + 1–2 old) with analyzer flags | This doc §4 or OverworldSoftlock_RootCause.md |
| 7 | Document base ROM provenance (ZScream OW vs ZScreamDungeon vs neither) and patch order | This doc §5–6, RootCause |
| 8 | List org’d addresses in ZSCustomOverworld that might overlap ZScream base ROM writes | This doc §5 |
| 9 | If ZScreamDungeon is ever used: define patch order and reserved ranges | This doc §6 |
| 10 | Bisect with different base ROMs (OOS_BASE_ROM) to separate “base ROM change” from “Oracle code change” | Plan Path D, this doc §4 |

---

## 8. References

- [OverworldSoftlock_Plan.md](OverworldSoftlock_Plan.md) — Paths A–D, tooling.
- [OverworldSoftlock_CodebaseAnalysis.md](OverworldSoftlock_CodebaseAnalysis.md) — ZSOW/time_system patterns, risks, recommendations.
- [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md) — Mechanism, suspect commits, base ROM note.
- [OverworldSoftlock_FixPlan.md](OverworldSoftlock_FixPlan.md) — Phases 1–5, oracle_analyzer usage.
- usdasm: `~/src/hobby/usdasm/` (bank_00.asm, bank_09.asm).
- z3dk: `~/src/hobby/z3dk/scripts/oracle_analyzer.py`.
- Build: `scripts/build_rom.sh`, `Oracle_main.asm`.
- ZScreamDungeon: `~/src/hobby/ZScreamDungeon/` (PatchesSystem, ZeldaFullEditor).
