# Agent Workflow: Oracle of Secrets Debugging + Editing

This workflow ties together Oracle-of-Secrets ASM, YAZE/z3ed, and Mesen2 so agents can debug and edit safely and repeatably.

## Tool Map

| Tool | Where | Purpose |
| --- | --- | --- |
| YAZE (GUI) | `~/src/hobby/yaze` | Visual editing (overworld/dungeon/graphics/palette) |
| z3ed (CLI) | `~/src/hobby/yaze` | Scripted ROM ops, agent plans, snapshots, diffs |
| Mesen2 (App) | `~/src/third_party/mesen2` | Runtime debugging, breakpoints, memory inspection |
| mesen2-mcp | `~/src/tools/mesen2-mcp` | MCP control for Mesen2 debugger + screenshots |
| yaze-mcp | `~/src/tools/yaze-mcp` | Unified emulator API (yaze + mesen2), patch tests |
| hyrule-historian | `~/src/tools/hyrule-historian` | Disassembly + RAM/ROM reference lookups |
| book-of-mudora | `~/src/tools/book-of-mudora` | Patch collision analysis / ROM map checks |
| expert-chain | `~/src/tools/expert-chain` | Multi-step expert model chaining (LM Studio) |
| AFS context | `~/.context/projects/oracle-of-secrets` | Scratchpad + shared agent notes |

## Baseline Flow (Edit -> Build -> Debug)

1. **Build ROM**
   - Use `scripts/build_rom.sh` (mac/linux) or `build.bat` (Windows).
2. **Export symbols for Mesen2**
   - `yaze --headless --rom_file <rom> --export_symbols <rom>.mlb --symbol_format mesen`
   - Place `<rom>.mlb` next to the ROM for label sync in Mesen2.
3. **Run Mesen2**
   - Launch Mesen2 and open the ROM (labels should load from `.mlb`).
4. **Debug / verify**
   - Use `scripts/mesen_water_debug.lua` or `scripts/verify_boot.lua` as needed.
   - Use mesen2-mcp or yaze-mcp to read/write memory, set breakpoints, and grab screenshots.

## Automation Flow (Headless)

### Quick Start (Launcher Script)

```
./scripts/agent_workflow_start.sh --rom Roms/oos168.sfc --api-port 8081 --wait-grpc 120 --generate-states
./scripts/agent_workflow_start.sh --rom Roms/oos168.sfc --export-fast --symbols-src /Users/scawful/src/hobby/oracle-of-secrets
./scripts/agent_workflow_stop.sh
```

1. **Start yaze in server mode**
   - `yaze --server --rom_file <rom>` (enables gRPC + HTTP and disables GUI).
2. **Start yaze-mcp**
   - `python -m server` (from `~/src/tools/yaze-mcp`).
3. **Run tests / checks**
   - Use yaze-mcp tools like `emu_read_memory`, `emu_test_run`, and `emu_screenshot`.
4. **Optional: Mesen2 MCP**
   - Run `python3 -m mesen2_mcp.server` (from `~/src/tools/mesen2-mcp`).

## Multi-Expert Analysis (LM Studio)

Use `expert-chain` when you want a structured, multi-step review (debug → analyze → scope → fix).

```
~/src/tools/expert-chain --list-workflows
~/src/tools/expert-chain water-collision --dry-run
~/src/tools/expert-chain water-collision --context "Room 0x27 shows $08 at expected offsets"
```

Notes:
- Requires LM Studio running at `localhost:1234` with a model loaded.
- Results saved to `~/.context/projects/oracle-of-secrets/scratchpad/`.

## CLI + Agent Flow (z3ed)

1. **Snapshot before changes**
   - `z3ed rom snapshot --rom=<rom> --name <label>`
2. **Propose edits in sandbox**
   - `z3ed agent plan --rom=<rom> --sandbox`
3. **Review and apply**
   - `z3ed agent diff --rom=<rom>`
   - `z3ed agent accept --rom=<rom> --proposal-id <id>`
4. **Diff and validate**
   - `z3ed rom diff <base> <target>`
   - `z3ed rom validate --rom=<rom>`

## Recommended Paths

- ROMs: `Roms/`
- Save states: `Roms/SaveStates/`
- Mesen2 scripts: `scripts/mesen_water_debug.lua`, `scripts/verify_boot.lua`
- Save-state library: `scripts/state_library.py` + `Docs/Testing/save_state_library.json`
- Agent notes: AFS scratchpad (`~/.context/projects/oracle-of-secrets/scratchpad/`)

## References

- `Docs/Tooling/Mesen2_MCP_Design.md`
- `~/src/tools/mesen2-mcp/README.md`
- `~/src/tools/yaze-mcp/README.md`
- `~/src/tools/AGENT_EMULATOR_INTEGRATION.md`
- `~/src/hobby/yaze/docs/internal/agents/automation-workflows.md`
- `~/src/hobby/yaze/docs/public/usage/z3ed-cli.md`
