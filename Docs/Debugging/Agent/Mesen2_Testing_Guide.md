# Mesen2 Testing Guide for AI Agents

**Last Updated:** 2026-01-29
**For:** Claude, Codex, Gemini, and other AI agents

---

## Overview

This guide enables AI agents to interact with the Oracle of Secrets ROM running in the **Mesen2-OoS** fork via the **Unix Domain Socket API**.

> **Note**: Legacy Lua/file-bridge stacks are deprecated. Use the Python `mesen2_client.py` or the `MesenBridge` in `scripts/mesen2_client_lib/bridge.py`.

## Architecture

Mesen2-OoS runs a custom C++ `SocketServer` on a separate thread, listening on `/tmp/mesen2-{PID}.sock`.

```
┌─────────────┐      JSON       ┌────────────────────────┐
│   Agent     │ ──────────────▶ │  Mesen2 (SocketServer) │
│  (Client)   │ ◀────────────── │  /tmp/mesen2-*.sock    │
└─────────────┘                 └────────────────────────┘
```

## Quick Start

### Interactive Debugging (GUI)

```bash
# 1. Launch Mesen2 with a source-tagged window title
./scripts/mesen2_launch_instance.sh --instance agent-demo --owner claude \
  --title "Claude" --source manual

# Title shows ACTIVE + source tag for clarity.

# 2. Interact via Python Client
python3 scripts/mesen2_client.py state --json
python3 scripts/mesen2_client.py press A
```

### Socket API Quick Commands (Preferred)

```bash
python3 scripts/mesen2_client.py --socket /tmp/mesen2-<pid>.sock state --json
python3 scripts/mesen2_client.py --socket /tmp/mesen2-<pid>.sock diagnostics --json
python3 scripts/mesen2_client.py --socket /tmp/mesen2-<pid>.sock press A --frames 5
python3 scripts/mesen2_client.py --socket /tmp/mesen2-<pid>.sock load 2
python3 scripts/mesen2_client.py --socket /tmp/mesen2-<pid>.sock save 2
python3 scripts/mesen2_client.py --socket /tmp/mesen2-<pid>.sock breakpoint --add 0x0080C9:exec
```

Direct memory reads/writes (raw bridge):

```bash
PYTHONPATH=./scripts python3 - <<'PY'
from mesen2_client_lib.bridge import MesenBridge
b=MesenBridge('/tmp/mesen2-<pid>.sock')
print(hex(b.read_memory(0x7E0739)))
PY
```

### Instance Lifecycle (Required)

- **Source tag is mandatory**: use `--source <label>` or set `MESEN2_AGENT_SOURCE`.
- **Active instances are highlighted**: window title is prefixed with `ACTIVE` and includes `[src:<label>]`.
- **Close cleanly** (no force-kill):  
  `./scripts/mesen2_client.py close --instance <name>`
  - If marked active: add `--confirm`
  - `--force` only increases the graceful wait; it never sends kill signals.

### Headless Automation (CI)

```bash
# 1. Start a headless Mesen2 OOS instance
./scripts/mesen2_launch_instance.sh --headless --instance agent-headless --source ci --owner agent

# 2. Interact via socket
python3 scripts/mesen2_client.py --instance agent-headless state --json
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
python3 scripts/mesen2_client.py mem-read 0x7EF342 --len 1 --json   # Expect 0x02 in bytes

# 2. Verify toggle by polling the active item
# First L/R press: 0x00 → 0x02 (goldstar)
# Second press:    0x02 → 0x01 (hookshot)
# Third press:     0x01 → 0x02 (goldstar)
python3 scripts/mesen2_client.py mem-read 0x7E0739 --len 1 --json
python3 scripts/mesen2_client.py press l --frames 5
python3 scripts/mesen2_client.py mem-read 0x7E0739 --len 1 --json
python3 scripts/mesen2_client.py press r --frames 5
python3 scripts/mesen2_client.py mem-read 0x7E0739 --len 1 --json
```

### Menu Navigation Test
```bash
# Check menu cursor / state
python3 scripts/mesen2_client.py mem-read 0x7E0202 --len 2 --json
```

### Save State Workflow (Preferred)
```bash
# Load a known state from the repo library (manifest-backed)
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-load baseline_1
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py state --json
```

### Agent Brain (B008 Input Correction)
```bash
# Calibrate input correction (prints on/off/unknown)
python3 scripts/mesen2_client.py brain-calibrate

# Smart save with correction override
python3 scripts/mesen2_client.py smart-save 3 --b008-mode auto
python3 scripts/mesen2_client.py smart-save 3 --b008-mode on
python3 scripts/mesen2_client.py smart-save 3 --b008-mode off
```

If calibration returns `unknown`, you are likely not in gameplay or no movement was detected.

### Runtime Reinit (Stale Cache Fixes)
```bash
# Queue reinit targets (comma-separated)
python3 scripts/mesen2_client.py lua "if DebugBridge and DebugBridge.reinit then DebugBridge.reinit('dialog,sprites,overlays') end"
```

### Agent-Friendly CLI (JSON Output)

```bash
./scripts/mesen2_client.py agent health
./scripts/mesen2_client.py agent state --pretty
./scripts/mesen2_client.py agent snapshot
```

### Multi-Instance Bridges

```bash
# Launch a named isolated instance (recommended)
./scripts/mesen2_launch_instance.sh --instance crashlab --owner you --source manual

# Attach by instance name
python3 scripts/mesen2_client.py --instance crashlab health
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

## Save States (Current)

Some older docs refer to “slot packs”. The current supported path is the socket client + manifest-backed state library:

```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py library
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-save "my repro seed" -t repro -t overworld
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-load <state_id>
```

Direct slot/file helpers (when you do not want to touch the library):

```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save 5
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py load 5
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py screenshot /tmp/oos.png
```

## Input Injection

The bridge supports automated button presses via the `press` command:

```bash
# Single button press (default 5 frames ≈ 83ms)
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py press A

# Button press with custom frame count
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py press START 1      # Quick tap
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py press A 30         # Half second hold

# Combined buttons
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py press UP+A 10      # Press Up and A together
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py press L+R+START 5  # Soft reset combo
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
./scripts/mesen2_launch_instance.sh --instance bg-run --owner you --source manual
./scripts/yabai_mesen_window.sh hide

# Launch and stash to a specific space
./scripts/mesen2_launch_instance.sh --instance scratch-run --owner you --source manual
SCRATCH_SPACE=8 ./scripts/yabai_mesen_window.sh stash

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

### Fork Socket API (Recommended)
- **Socket:** `/tmp/mesen2-<pid>.sock` (auto‑started by `/Applications/Mesen2 OOS.app`).
- **Client:** `python3 scripts/mesen2_client.py --socket /tmp/mesen2-<pid>.sock ...`
- **Automation:** `mesen2_client.py` or `MesenBridge` (`scripts/mesen2_client_lib/bridge.py`) for CPU/stack/breakpoint capture.

### Legacy Lua/File Bridges (Historical)

Older workflows used a Lua bridge + file polling. Those are no longer the supported path for Oracle of Secrets.

If the socket client cannot connect:

```bash
python3 scripts/mesen2_client.py socket-cleanup
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py health
```

If that still fails, restart the Mesen2 OOS fork instance and re-run `diagnostics`.

## Troubleshooting

### Bridge not responding
1. Check if Mesen2 is running: `pgrep -l Mesen`
2. If using the Lua bridge, check if I/O access is enabled in Mesen2 settings
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
