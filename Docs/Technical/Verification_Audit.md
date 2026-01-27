# Verification Audit Checklist

**Purpose:** Keep core docs, flags, and story mapping accurate and date-stamped.
**Last Verified:** 2026-01-23 (created)
**Primary Sources:** Internal audit process
**Confidence:** Medium

## When to Run

- After any change to SRAM/WRAM flags, story progression, or system architecture.
- After debugging sessions that discover new runtime behavior.
- Before sharing status reports or handing off AI context.

## Checklist (per document)

1) Identify source tier used (ROM/disassembly, runtime, sheets, notes).
2) Update **Last Verified** date and **Confidence**.
3) Fill or update the **Verification** table with evidence + method.
4) If a claim is unverified, add `UNKNOWN` and a `;@assumption` tag in code or doc.
5) Link to evidence artifacts (screenshots, watch logs, save states).

## Doc Audit Table (seed)

| Document | Last Verified | Source Tier | Status | Owner | Notes |
| --- | --- | --- | --- | --- | --- |
| Docs/Core/Ram.md | UNKNOWN | ROM + runtime | Needs audit | TBD | Fill table with evidence |
| Docs/Core/MemoryMap.md | UNKNOWN | ROM + runtime | Needs audit | TBD | Check SRAM usage notes |
| Docs/Core/SystemArchitecture.md | UNKNOWN | ROM + docs | Needs audit | TBD | Confirm TimeState and transitions |
| Docs/Technical/Flag_Ledger.md | 2026-01-23 | ROM (sram.asm) | Partial | TBD | Runtime verification pending |
| Docs/Planning/Story_Event_Graph.md | 2026-01-23 | ROM + lore | Partial | TBD | Map routines + rooms |

## Evidence Locations

- Scratchpad: `~/.context/projects/oracle-of-secrets/scratchpad/`
- Screenshots: `tests/screenshots/` (if captured)
- Save states: `Roms/SaveStates/`

## Suggested Audit Order

1) `Docs/Technical/Flag_Ledger.md`
2) `Docs/Planning/Story_Event_Graph.md`
3) `Docs/Core/Ram.md`
4) `Docs/Core/MemoryMap.md`
5) `Docs/Core/SystemArchitecture.md`
