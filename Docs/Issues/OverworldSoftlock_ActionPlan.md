# Overworld / Dungeon Black Screen — Action & Testing Plan

**Superseded for next steps:** See **[OverworldSoftlock_Plan.md](OverworldSoftlock_Plan.md)** for the current plan (hands-on options, dynamic capture, module isolation, bisect).

---

## Summary (for reference)

- **State 1:** Overworld softlock (pyramid overworld). **State 2:** File-load dungeon freeze — track separately.
- **Mechanism:** JumpTableLocal PLY pops 1 byte when X=8-bit → stack misalignment → RTL to garbage → JSL into WRAM → black screen. Root cause (which instruction corrupts P/SP) not yet identified.
- **Status:** Static fixes (sprite dispatch, HUD PHP/PLP, time system, menu) did not resolve either bug. Next: pick a path from [OverworldSoftlock_Plan.md](OverworldSoftlock_Plan.md).

---

## Evidence and execution detail (historical)

- **Evidence ledger:** `~/.context/scratchpad/overworld_softlock_evidence_20260128.md`
- **Detailed handoff:** [OverworldSoftlock_Handoff.md](OverworldSoftlock_Handoff.md)
- **Fix phases and module list:** [OverworldSoftlock_FixPlan.md](OverworldSoftlock_FixPlan.md)
- **Root cause and mechanism:** [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md)

For capture targets, hypotheses, tooling improvements, and raw execution commands (breakpoints, MEM_WATCH, repro script), see the Handoff and FixPlan docs above.
