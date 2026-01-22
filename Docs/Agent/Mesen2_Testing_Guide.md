# Mesen2 Testing Guide for AI Agents

**Last Updated:** 2026-01-21
**For:** Claude, Codex, Gemini, and other AI agents

---

## Overview

This guide enables AI agents to interact with the Oracle of Secrets ROM running in Mesen2 emulator for automated testing and debugging.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Agent     │────▶│  mesen_cli.sh    │────▶│  Bridge     │
│  (Claude)   │◀────│  (Shell script)  │◀────│  Files      │
└─────────────┘     └──────────────────┘     └──────┬──────┘
                                                    │
                                             ┌──────▼──────┐
                                             │   Mesen2    │
                                             │  (Lua API)  │
                                             └─────────────┘
```

## Quick Start

```bash
# 1. Launch Mesen2 with ROM and auto-load bridge
./scripts/mesen_launch.sh

# 2. Poll game state from agent
./scripts/mesen_cli.sh state

# 3. Get human-readable status
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
# 1. Check if ready for test
./scripts/mesen_cli.sh lrswap
# Expected: ready=true, hookshotSRAM=2

# 2. Watch for value changes while user presses L or R
./scripts/mesen_cli.sh watch 0x7E0739

# 3. Verify toggle
# First L/R press: 0x00 → 0x02 (goldstar)
# Second press:    0x02 → 0x01 (hookshot)
# Third press:     0x01 → 0x02 (goldstar)
```

### Menu Navigation Test
```bash
# Watch menu cursor
./scripts/mesen_cli.sh watch 0x7E0202

# Check menu state
./scripts/mesen_cli.sh read 0x7E0200
```

### Save State Workflow
```bash
# Load a known state
# (User must do this in Mesen2 UI - F1-F10 for slots)

# Verify state loaded
./scripts/mesen_cli.sh state
```

## Bridge Commands

| Command | Description | Example |
|---------|-------------|---------|
| `state` | Full JSON state dump | `./mesen_cli.sh state` |
| `status` | Human-readable status | `./mesen_cli.sh status` |
| `poll N` | Continuous polling (N seconds) | `./mesen_cli.sh poll 0.5` |
| `read ADDR` | Read 8-bit value | `./mesen_cli.sh read 0x7E0739` |
| `read16 ADDR` | Read 16-bit value | `./mesen_cli.sh read16 0x7E0022` |
| `readblock ADDR LEN` | Read block of bytes (hex) | `./mesen_cli.sh readblock 0x7E0000 16` |
| `write ADDR VAL` | Write 8-bit value | `./mesen_cli.sh write 0x7EF342 0x02` |
| `write16 ADDR VAL` | Write 16-bit value | `./mesen_cli.sh write16 0x7E0022 0x100` |
| `watch ADDR` | Watch for changes | `./mesen_cli.sh watch 0x7E0739` |
| `wait-ready` | Wait for L/R swap ready | `./mesen_cli.sh wait-ready` |
| `lrswap` | L/R swap test status | `./mesen_cli.sh lrswap` |
| `ping` | Test bridge connection | `./mesen_cli.sh ping` |

## Yabai Integration

For automated testing, Mesen2 can be placed in BSP tiling mode:

```bash
# Add to yabai config or run manually:
yabai -m rule --add app="Mesen" manage=on

# Or for agent testing, use floating mode:
yabai -m rule --add app="Mesen" manage=off grid=6:6:4:0:2:3
```

## File Locations

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
