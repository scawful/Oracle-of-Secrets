# Mesen2 Testing Guide for AI Agents

**Last Updated:** 2026-01-22
**For:** Claude, Codex, Gemini, and other AI agents

---

## Overview

This guide enables AI agents to interact with the Oracle of Secrets ROM running in Mesen2 emulator for automated testing and debugging.

## Architecture

### Dual-Backend System
`mesen_cli.sh` uses the HTTP API on port 8080 when a hub/headless server is running, and falls back to the file bridge when it is not.

```
┌─────────────┐      HTTP       ┌────────────────────────┐
│   Agent     │ ──────────────▶ │ mesen_socket_server.py │ (Hub)
│  (Claude)   │ ◀────────────── │        (Port 8080)     │
└─────────────┘                 └───────────┬────────────┘
                                            │
                       ┌────────────────────┴────────────────────┐
                       ▼                                         ▼
              [Interactive Mode]                          [Headless Mode]
       ┌──────────────────────────────┐           ┌──────────────────────────────┐
       │           Mesen2             │           │         mesen2-mcp           │
       │   (Socket Bridge Script)     │           │      (Headless Server)       │
       └──────────────────────────────┘           └──────────────────────────────┘
```

## Quick Start

### Mode A: Interactive Debugging (GUI)
Best for visual confirmation and "shoulder-surfing".

```bash
# 1. Start the Hub (Terminal A)
python3 scripts/mesen_socket_server.py

# 2. Launch Mesen2 with Socket Bridge
./scripts/mesen_launch.sh --bridge socket

# 3. Interact (Terminal B)
./scripts/mesen_cli.sh state
./scripts/mesen_cli.sh press A
```

### Mode B: Headless Automation (CI)
Best for fast regression testing and background agents.

```bash
# 1. Start the Headless Server
cd ~/src/tools/mesen2-mcp
python3 -m mesen2_mcp.server

# 2. Interact
./scripts/mesen_cli.sh state
./scripts/mesen_cli.sh status
```

## Key Memory Addresses

### Game State
| Address | Name | Description | Values |
|---------|------|-------------|--------|
| `$7E0010` | MODE | Game mode | 0x07=Dungeon, 0x09=Overworld, 0x0E=Menu |
| `$7E0011` | SUBMODE | Sub-module | Varies by mode |
| `$7E001B` | INDOORS | Indoor flag | 0x00=Outside, 0x01=Inside |
| `$7E00A0` | ROOMID | Current room | Room number |

### Link State
| Address | Name | Description | Values |
|---------|------|-------------|--------|
| `$7E0020` | POSY | Y position (16-bit) | World coordinates |
| `$7E0022` | POSX | X position (16-bit) | World coordinates |
| `$7E002F` | DIR | Direction | 0=Up, 2=Down, 4=Left, 6=Right |
| `$7E005D` | STATE | Link's action state | 0x00=Default, 0x04=Swim, 0x13=Hookshot |

### Equipment (L/R Swap Testing)
| Address | Name | Description | Values |
|---------|------|-------------|--------|
| `$7E0202` | EQUIPPED | Menu cursor/equipped slot | 0x03=Hookshot slot |
| `$7E0739` | GSACTIVE | Active item | 0x00=Unset, 0x01=Hookshot, 0x02=Goldstar |
| `$7EF342` | HOOKSRAM | Hookshot SRAM flag | 0x01=Hookshot, 0x02=Both items |

### Input
| Address | Name | Description | Bits |
|---------|------|-------------|------|
| `$7E00F4` | INPUT | D-pad + Select/Start | udlr.... |
| `$7E00F6` | NEWINPUT | New AXLR this frame | AXLR.... (L=0x20, R=0x10) |
| `$7E00F2` | HELD | Held AXLR buttons | AXLR.... |

## GoldstarOrHookshot Variable

**Address:** `$7E0739` (in free RAM region starting at `$7E0730`)

**Values:**
- `0x00` - Uninitialized (defaults to hookshot behavior)
- `0x01` - Hookshot explicitly selected
- `0x02` - Goldstar selected

**Toggle Logic (L/R press):**
```
If GoldstarOrHookshot == 0x02 (goldstar):
    Set to 0x01 (hookshot)
Else (0x00 or 0x01):
    Set to 0x02 (goldstar)
```

**Prerequisite:** `$7EF342 == 0x02` (player has both hookshot AND goldstar)

## Testing Workflows

### L/R Swap Test
```bash
# 1. Ensure both items are present
./scripts/mesen_cli.sh read 0x7EF342   # Expect 0x02

# 2. Verify toggle by polling the active item
# First L/R press: 0x00 → 0x02 (goldstar)
# Second press:    0x02 → 0x01 (hookshot)
# Third press:     0x01 → 0x02 (goldstar)
./scripts/mesen_cli.sh read 0x7E0739
./scripts/mesen_cli.sh press L 5
./scripts/mesen_cli.sh read 0x7E0739
./scripts/mesen_cli.sh press R 5
./scripts/mesen_cli.sh read 0x7E0739
```

### Menu Navigation Test
```bash
# Check menu cursor / state
./scripts/mesen_cli.sh read 0x7E0202
./scripts/mesen_cli.sh read 0x7E0200
```

### Save State Workflow
```bash
# Load a known state via the bridge
./scripts/mesen_cli.sh loadstate ~/Documents/Mesen2/SaveStates/oos168x_1.mss
./scripts/mesen_cli.sh wait-load 10

# Verify state loaded
./scripts/mesen_cli.sh state
```

### Runtime Reinit (Stale Cache Fixes)
```bash
# Queue reinit targets (comma-separated)
./scripts/mesen_cli.sh reinit dialog,sprites,overlays

# Check reinit status bits
./scripts/mesen_cli.sh reinit-status
```

### Multi-Instance Bridges

```bash
# Launch a named instance with its own bridge directory
./scripts/mesen_launch.sh --instance crashlab

# Use the matching bridge from the CLI
MESEN_INSTANCE=crashlab ./scripts/mesen_cli.sh status
```

### Window Management (yabai)

```bash
# Float Mesen windows + tool panes
./scripts/yabai_mesen_rules.sh apply float

# Send Mesen behind or bring to front
./scripts/yabai_mesen_window.sh toggle

# Minimize/restore all Mesen windows
./scripts/yabai_mesen_window.sh minimize
./scripts/yabai_mesen_window.sh restore
```

### Save-State Sets (10-slot packs)
```bash
# Swap a full 10-slot pack into Mesen2
python3 scripts/state_library.py set-apply --set ow_baseline --rom Roms/oos168x.sfc --force
```

### Automated CLI Tests (mesen_cli + bridge)

Run the smoke test to verify the bridge and basic read/write commands:

```bash
./scripts/test_runner.py tests/bridge_smoke_test.json
```

Run the L/R swap test (requires `hookshot_both` state in the library):

```bash
./scripts/test_runner.py tests/lr_swap_test.json
```

If a local save state is missing, you can skip those tests:

```bash
./scripts/test_runner.py tests/*.json --skip-missing-state
```

## Bridge Commands

| Command | Description | Example |
|---------|-------------|---------|
| `state` | Full JSON state dump | `./mesen_cli.sh state` |
| `status` | Human-readable status | `./mesen_cli.sh status` |
| `state-json [PATH]` | Write state JSON to file | `./mesen_cli.sh state-json /tmp/oos_state.json` |
| `read ADDR` | Read 8-bit value | `./mesen_cli.sh read 0x7E0739` |
| `read16 ADDR` | Read 16-bit value | `./mesen_cli.sh read16 0x7E0022` |
| `write ADDR VAL` | Write 8-bit value | `./mesen_cli.sh write 0x7EF342 0x02` |
| `write16 ADDR VAL` | Write 16-bit value | `./mesen_cli.sh write16 0x7E0022 0x100` |
| `press BTN [F]` | Inject button press (F frames) | `./mesen_cli.sh press A 5` |
| `loadstate PATH` | Queue savestate load | `./mesen_cli.sh loadstate ~/Documents/Mesen2/SaveStates/oos168x_1.mss` |
| `savestate PATH` | Save state to file | `./mesen_cli.sh savestate /tmp/oos168x.mss` |
| `loadslot N` | Load slot 1-10 | `./mesen_cli.sh loadslot 1` |
| `saveslot N` | Save slot 1-10 | `./mesen_cli.sh saveslot 1` |
| `wait-load [SECS]` | Wait for load to finish | `./mesen_cli.sh wait-load 10` |
| `wait-save [SECS]` | Wait for save to finish | `./mesen_cli.sh wait-save 10` |
| `screenshot [PATH]` | Save screenshot | `./mesen_cli.sh screenshot ~/Desktop/oos.png` |
| `snapshot [DIR]` | Save state JSON + screenshot | `./mesen_cli.sh snapshot /tmp/oos_snap` |
| `reinit` | Queue runtime reinit | `./mesen_cli.sh reinit dialog,sprites` |
| `reinit-status` | Read reinit flags/status/error | `./mesen_cli.sh reinit-status` |
| `pause` | Pause emulator | `./mesen_cli.sh pause` |
| `resume` | Resume emulator | `./mesen_cli.sh resume` |
| `reset` | Reset emulator | `./mesen_cli.sh reset` |
| `wait-addr` | Wait for memory match | `./mesen_cli.sh wait-addr 0x7E0010 0x09 10` |
| `preserve` | SRAM preservation helper | `./mesen_cli.sh preserve status` |
| `ping` | Test bridge connection | `./mesen_cli.sh ping` |

### Planned CLI Additions (not yet implemented)
- `wait-state`, `wait-room`, `wait-indoors`
- `readblock`, `writeblock`, `cpu`, `stack`, `stack-report`, `step/stepover/stepout`
- `watch`, `watchlist`, `trace`, `log`, `trace-report`
- `emu-state-keys`, `emu-get`, `emu-call`, `where`, `loadrom`

## Input Injection

The bridge supports automated button presses via the `press` command:

```bash
# Single button press (default 5 frames ≈ 83ms)
./scripts/mesen_cli.sh press A

# Button press with custom frame count
./scripts/mesen_cli.sh press START 1      # Quick tap
./scripts/mesen_cli.sh press A 30         # Half second hold

# Combined buttons
./scripts/mesen_cli.sh press UP+A 10      # Press Up and A together
./scripts/mesen_cli.sh press L+R+START 5  # Soft reset combo
```

**Available Buttons:**
- D-pad: `UP`, `DOWN`, `LEFT`, `RIGHT`
- Face: `A`, `B`, `X`, `Y`
- Shoulder: `L`, `R`
- Control: `START`, `SELECT`

**Timing Notes:**
- SNES runs at ~60fps, so 1 frame ≈ 16.7ms
- Default 5 frames is usually enough for single input detection
- Menu navigation may need 10+ frames between inputs

## Yabai Integration

For automated testing, Mesen2 can be placed in BSP tiling mode:

```bash
# Add to yabai config or run manually:
yabai -m rule --add app="Mesen" manage=on

# Or for agent testing, use floating mode:
yabai -m rule --add app="Mesen" manage=off grid=6:6:4:0:2:3
```

### Background/Foreground Toggle (yabai)

Use `scripts/yabai_mesen_window.sh` to push Mesen behind other windows or bring it forward.

```bash
# Toggle Mesen between background (layer below) and normal
./scripts/yabai_mesen_window.sh toggle

# Force background
./scripts/yabai_mesen_window.sh hide

# Bring to front
./scripts/yabai_mesen_window.sh show
```

### Scratch Space Stash (yabai)

Send Mesen to a dedicated space for background runs, and bring it back later.

```bash
# Stash to space 8 (set SCRATCH_SPACE to avoid typing)
SCRATCH_SPACE=8 ./scripts/yabai_mesen_window.sh stash

# Toggle between scratch space and the previous space
SCRATCH_SPACE=8 ./scripts/yabai_mesen_window.sh toggle-space
```

### Auto background on launch, foreground on test start

```bash
# Launch Mesen in background layer
./scripts/mesen_launch.sh --yabai background

# Launch and stash to a specific space
./scripts/mesen_launch.sh --yabai space --yabai-space 8

# Disable auto-focus at test start
MESEN_AUTO_FOCUS=0 ./scripts/test_runner.py tests/*.json
```

Optional skhd bindings:

```bash
# Toggle Mesen window layer
alt - m : /Users/scawful/src/hobby/oracle-of-secrets/scripts/yabai_mesen_window.sh toggle

# Toggle Mesen between current space and scratch space 8
alt - shift - m : SCRATCH_SPACE=8 /Users/scawful/src/hobby/oracle-of-secrets/scripts/yabai_mesen_window.sh toggle-space
```

### Yabai Rules Cleanup (stop tiling)

If Mesen is still tiling, clean up conflicting rules and re-apply a single managed rule:

```bash
./scripts/yabai_mesen_rules.sh apply background
./scripts/yabai_mesen_rules.sh status
```

### Mesen Tool Windows (Script/Debugger/etc.)

The rules helper also floats common tool windows so they don’t tile:

```bash
./scripts/yabai_mesen_rules.sh apply float
```

### Auto stash/restore during test runs

```bash
# Restore Mesen to previous space before tests (default on)
MESEN_AUTO_UNSTASH=1 ./scripts/test_runner.py tests/*.json

# Stash Mesen after tests (requires SCRATCH_SPACE for space-based stash)
SCRATCH_SPACE=8 MESEN_AUTO_STASH=1 ./scripts/test_runner.py tests/*.json

# Stash only when failures occur
SCRATCH_SPACE=8 MESEN_STASH_ON_FAIL=1 ./scripts/test_runner.py tests/*.json
```

## Bridge Requirements

### Socket Bridge (Recommended)
- **Hub:** `scripts/mesen_socket_server.py` running on port 8080.
- **Client:** `scripts/mesen_socket_bridge.lua` loaded in Mesen2.
- **Settings:** `AllowIoOsAccess` enabled in Mesen2 (for socket library).

### Legacy File Bridge (Fallback)
If the Socket Hub is offline, `mesen_cli.sh` falls back to file polling.

| File | Purpose |
|------|---------|
| `~/Documents/Mesen2/bridge/state.json` | Current game state (updated ~6/sec) |
| `~/Documents/Mesen2/bridge/command.txt` | Send commands to Lua |
| `~/Documents/Mesen2/bridge/response.txt` | Command responses |
| `~/Documents/Mesen2/Scripts/mesen_live_bridge.lua` | Main bridge script |

## Mesen2 Settings Requirements

The bridge script requires I/O access to write state files. This must be enabled in Mesen2:

**Setting:** `Script > Settings > Script Window > Restrictions > Allow access to I/O and OS functions`

Or programmatically in `~/Documents/Mesen2/settings.json`:
```json
"AllowIoOsAccess": true
```

Also ensure auto-start is enabled:
```json
"AutoStartScriptOnLoad": true
```

## Troubleshooting

### Bridge not responding
1. Check if Mesen2 is running: `pgrep -l Mesen`
2. Check if I/O access is enabled in Mesen2 settings
3. Check if bridge script is loaded (look for message in Mesen2 console)
4. Check state file age: `ls -la ~/Documents/Mesen2/bridge/state.json`

### Script loads but no state file
- **Most common cause:** I/O access is disabled
- Check Mesen2 console for error: "I/O and OS libraries are disabled"
- Enable via: Script > Settings > Allow I/O access

### State file stale
- Bridge script may have crashed - reload it in Mesen2
- Mesen2 may be paused - resume emulation

### Commands timeout
- Bridge only processes commands during active emulation
- Ensure game is not paused or in a loading state

### API errors (ppu.frameCount nil)
- Ensure using updated bridge script that doesn't rely on `emu.getState().ppu`
