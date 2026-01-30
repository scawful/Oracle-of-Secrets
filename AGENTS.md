# Oracle of Secrets: Antigravity Rules & Standards

These rules are optimized for the Oracle of Secrets Zelda ROM hacking workflow.
See also: [Global Rules](file:///Users/scawful/src/config/zelda-dev/rules.md)

## 1. Build and Verification
- **Command**: Recommended: `mesen-agent build`. Legacy: `./scripts/build_rom.sh 168`.
- **Verification**: Run `python3 scripts/check_zscream_overlap.py` after every build that adds new code or data.
- **Static Analysis**: z3dk's `oracle_analyzer.py --check-hooks --find-mx` validates M/X register state at hook entry points (e.g., JumpTableLocal at $008781 requires 8-bit Y; 16-bit Y causes stack underflow). Run via build script or manually from `~/src/hobby/z3dk/scripts/`.
- **Symbols**: Ensure `Roms/oos168x.mlb` is updated after builds for proper symbol debugging in Mesen2.

## 1.1 Critical Guardrails (softlock/color investigations)
- **No silent doc/comment pruning**: Do not delete analysis blocks, inline notes, or commentary without an explicit commit note. Treat docs/comments as evidence; if you must prune, set `ALLOW_DOC_PRUNE=1` and explain why.
- **Critical file watchlist**: Changes to `Overworld/time_system.asm`, `Overworld/ZSCustomOverworld.asm`, `Dungeons/dungeons.asm`, `Sprites/NPCs/followers.asm`, and `Core/patches.asm` require (a) a captured failing state, and (b) an entry in `Docs/Issues/OverworldSoftlock_Handoff.md` before merge.
- **Color math hygiene**: Area transitions must clear `$9A/$9C/$9D` and restore caller P. Calls into `BackgroundFix/Oracle_BackgroundFix` must ensure A=16‑bit, X=8‑bit, and wrap PHP/PLP (or document the calling convention at the site).
- **State-first fixes**: Do not apply fixes to Module06/07 load paths without a captured black‑screen frame (addresses: $7E0010/$7E0011/$7E001A/$7E0013/$7E00A0/$7E010E/$9A/$9C/$9D/$1D + PC) attached to the issue doc.

## 2. Debugging Workflow
- **Launcher**: Recommended: `mesen-agent launch oos`. Legacy: `./scripts/start_debug_session.sh`.
- **Client**: Use `python3 scripts/mesen2_client.py` for state inspection, health checks, and watch profile management.
- **Skills**: Use `mesen2-oos-debugging` for socket CLI workflows and `alttp-disasm-labels` for disassembly label lookup.
- **Socket discovery**: `MESEN2_SOCKET_PATH` → `/tmp/mesen2-*.status` (read `socketPath`) → `/tmp/mesen2-*.sock` by mtime. Do not assume socket name contains a PID. See `~/src/hobby/mesen2-oos/docs/Agent_Integration_Guide.md`.
- **Symbols**: Load via `SYMBOLS_LOAD` with `file` or `path` (JSON or `.mlb`). Resolve address→symbol with `SYMBOLS_RESOLVE addr=`. See `~/src/hobby/mesen2-oos/docs/Socket_API_Reference.md`.
- **Watch Presets**: Prefer established watch profiles like `overworld`, `time`, or `debug` before creating manual watches.
- **Preflight**: Always run `python3 scripts/mesen2_client.py diagnostics` when troubleshooting crashes.

## 2.1 State & Progression
- **Reference**: Consult `Docs/Agent/SRAM_and_Progression.md` for the authoritative SRAM map and progression flags.
- **Validation**: Validate `GameState` ($7EF3C5) and `StoryProgress` ($7EF3D6) against the guide before assuming a specific game state.
- **Tools**: Use `mesen2_client.py` to inspect these values directly (e.g., `client.read(0x7EF3C5)`).

## 3. ASM Coding Standards
- **Handbook**: Consult `Docs/Agent/Developer_Handbook.md` for memory maps, standard library routines, and bank structure.
- **Register Hygiene**: Always use `PHX/PHY/PHA` and `PLA/PLY/PLX` to preserve registers in subroutines.
- **Bitness Safety**: Explicitly use `REP #$20` or `SEP #$20` after `JSL` calls to external routines.
- **Coordinate Math**: Use `JSL Sprite_Get_16_bit_Coords` ($06E60E) for 16-bit sprite physics math.
- **Color Math**: Area transitions MUST clear `$9A`, `$9C`, and `$9D` to prevent visual glitches.
- **Input Handling**: Use `$F0` (JOY1A) for D-pad and `$F2` (JOY1B_ALL) for continuous actions. Avoid `$F6` (JOY1B_NEW) for timers.

## 4. Repository Cleanup & Safety
- **Legacy Stack**: The `mesen_cli.sh` stack is obsolete. Always use the `mesen2_client.py` Socket API client. The `mesen2-mcp` server has been removed.
- **Sandbox**: If encountering `Operation not permitted`, ensure the targeted file is not in `.gitignore` or use `SANDBOX_MODE=permissive`.
- **Git Hygiene**: Avoid committing redundant iteration commits. Squash history if it becomes bloated with campaign iterations.
