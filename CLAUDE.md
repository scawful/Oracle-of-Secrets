# CLAUDE.md

Purpose: Claude-specific routing for Oracle of Secrets.

## Read First
- Follow `AGENTS.md` for project facts, ROM naming, and rules.
- Check `.context/scratchpad/agent_handoff.md` for current session state.

## Reference Knowledge

When working on this project, consult the global knowledge base at `~/.context/knowledge/` for background context:

| Task | Read |
|------|------|
| Writing ASM hooks/patches | `hobby/oracle-hook-patterns.md` |
| Sprite development | `hobby/oracle-sprite-ram.md` + `alttp/sprite_catalog.md` |
| Progression/flag work | `hobby/oracle-progression.md` |
| Overworld editing | `hobby/zscustom-overworld.md` |
| Dialogue/message editing | `hobby/oracle-message-format.md` |
| Understanding game architecture | `alttp/architecture.md` |
| Looking up vanilla routines | `alttp/routine_index.md` |
| Finding ROM data tables | `alttp/data_tables.md` |
| SNES hardware questions | `snes/cpu_memory.md`, `snes/ppu_registers.md`, `snes/dma_registers.md` |
| Debugging workflows | `hobby/workflows.md` |
| Cross-referencing addresses | `hobby/usdasm.md` (bank map) + `alttp/ram_map.md` |
| Full project overview | `hobby/oracle-of-secrets.md` |

All paths relative to `~/.context/knowledge/`.

## Rules
1. Keep edits minimal, reversible, and task-scoped.
2. Prefer `Scripts/` tools over ad-hoc shell commands.
3. Validate with `./Scripts/Build/build_rom.sh 168` + `check_zscream_overlap.py` when changing ASM.
4. Never claim verification that was not actually run.
5. Escalate ambiguity quickly.

## Response Contract
- What changed
- How it was validated
- Remaining risks or unknowns
