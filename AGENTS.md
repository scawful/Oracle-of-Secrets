# Oracle of Secrets: Antigravity Rules & Standards

These rules are optimized for the Oracle of Secrets Zelda ROM hacking workflow.
See also: [Global Rules](file:///Users/scawful/src/config/zelda-dev/rules.md)

## 1. Build and Verification
- **Command**: Recommended: `mesen-agent build`. Legacy: `./scripts/build_rom.sh 168`.
- **Verification**: Run `python3 scripts/check_zscream_overlap.py` after every build that adds new code or data.
- **Static Analysis**: z3dk's `oracle_analyzer.py --check-hooks --find-mx --check-sprite-tables` validates M/X register state at hook entry points and checks sprite property tables for ID overflow past `$F2`. Run via build script or manually from `~/src/hobby/z3dk/scripts/`.
- **Symbols**: Ensure `Roms/oos168x.mlb` is updated after builds for proper symbol debugging in Mesen2.

## 2. Debugging Workflow
- **Runbook**: Start with `RUNBOOK.md` (repo root) for the current golden-path commands.
- **Launcher**: Recommended: `mesen-agent launch oos`. Legacy: `./scripts/start_debug_session.sh`.
- **Client**: Use `python3 scripts/mesen2_client.py` for state inspection, health checks, and watch profile management.
- **Skills**: Use `mesen2-oos-debugging` for socket CLI workflows and `alttp-disasm-labels` for disassembly label lookup.
- **Socket discovery**: `MESEN2_SOCKET_PATH` → `/tmp/mesen2-*.status` (read `socketPath`) → `/tmp/mesen2-*.sock` by mtime. Do not assume socket name contains a PID. See `~/src/hobby/mesen2-oos/docs/Agent_Integration_Guide.md`.
- **Symbols**: Load via `SYMBOLS_LOAD` with `file` or `path` (JSON or `.mlb`). Resolve address→symbol with `SYMBOLS_RESOLVE addr=`. See `~/src/hobby/mesen2-oos/docs/Socket_API_Reference.md`.
- **Watch Presets**: Prefer established watch profiles like `overworld`, `time`, or `debug` before creating manual watches.
- **Preflight**: Always run `python3 scripts/mesen2_client.py diagnostics` when troubleshooting crashes.

## 2.1 State & Progression
- **Reference**: Consult `Core/sram.asm` (source of truth) and `Docs/Technical/sram_flag_analysis.md` (notes) for the SRAM map and progression flags.
- **Validation**: Validate `GameState` ($7EF3C5) and `StoryProgress` ($7EF3D6) against the guide before assuming a specific game state.
- **Tools**: Use `mesen2_client.py` to inspect these values directly (e.g., `client.read(0x7EF3C5)`).

## 3. ASM Coding Standards
- **References**: Use `Docs/Technical/MemoryMap.md` + `Docs/Technical/Ram.md` for WRAM/SRAM labels, `Docs/Technical/Disassembly_Guide.md` for bank/addressing conventions, and `Docs/Debugging/Oracle_ABI_Standard.md` for hook/ABI expectations.
- **Register Hygiene**: Always use `PHX/PHY/PHA` and `PLA/PLY/PLX` to preserve registers in subroutines.
- **Bitness Safety**: Explicitly use `REP #$20` or `SEP #$20` after `JSL` calls to external routines.
- **Coordinate Math**: Use `JSL Sprite_Get_16_bit_Coords` ($06E60E) for 16-bit sprite physics math.
- **Color Math**: Area transitions MUST clear `$9A`, `$9C`, and `$9D` to prevent visual glitches.
- **Input Handling**: Use `$F0` (JOY1A) for D-pad and `$F2` (JOY1B_ALL) for continuous actions. Avoid `$F6` (JOY1B_NEW) for timers.

## 4. Repository Cleanup & Safety
- **Legacy Stack**: Legacy Lua/file-bridge stacks are obsolete. Always use the `mesen2_client.py` Socket API client. The `mesen2-mcp` server has been removed.
- **Sandbox**: If encountering `Operation not permitted`, ensure the targeted file is not in `.gitignore` or use `SANDBOX_MODE=permissive`.
- **Git Hygiene**: Avoid committing redundant iteration commits. Squash history if it becomes bloated with campaign iterations.
