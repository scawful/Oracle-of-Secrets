# CLAUDE.md

Purpose: Claude-specific routing for Oracle of Secrets.

## Read First
- Follow `AGENTS.md` for project facts, ROM naming, and rules.
- Check `.context/scratchpad/agent_handoff.md` for current session state.

## Skills

Use `/skill-name` to invoke domain knowledge for specific workflows:

| Task | Skill |
|------|-------|
| Writing ASM hooks/patches | `/oos-hook-author` |
| Reading vanilla disassembly | `/oos-vanilla-xref` |
| Building the ROM | `/oos-build-pipeline` |
| Custom sprites (NPC, enemy, boss) | `/oos-sprite-forge` |
| Dungeon rooms, collision, tags | `/oos-dungeon-workshop` |
| Progression flags, SRAM, crystals | `/oos-progression-engine` |
| Dialogue and messages | `/oos-dialogue-author` |
| Music and SPC700 | `/oos-music-workshop` |
| Overworld, entrances, time system | `/oos-overworld-workshop` |
| Items, equipment, ancillae | `/oos-item-forge` |
| Transformation masks | `/oos-mask-system` |
| Menu, HUD, submenus | `/oos-menu-architect` |
| ASM code quality, anti-patterns, linting | `/oos-asm-quality` |
| Debugging, black screen, traces | `/oracle-debugger` |
| Mesen2 socket, breakpoints | `/mesen2-oos-debugging` |
| Navigation testing | `/hyrule-navigator` |
| Address/label lookup | `/alttp-disasm-labels` |

### Cross-Project Skills
| Task | Skill |
|------|-------|
| Yaze editor/z3ed development | `/yaze-editor-dev` |
| z3dk assembler/LSP/linter | `/z3dk-toolchain` |

## Reference Knowledge

When skills don't cover your task, consult `~/.context/knowledge/` for background:

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
