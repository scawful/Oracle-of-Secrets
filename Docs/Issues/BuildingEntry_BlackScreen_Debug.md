# Building Entry Black Screen - Grounded Debug Protocol

**Created:** 2026-01-24
**Status:** UNVERIFIED - No observational data yet
**Priority:** HIGH

## Critical Rule

**DO NOT APPLY FIXES until failure state is captured and documented here.**

All previous "fixes" (mode mismatch, DB addressing, etc.) were based on theory, not observation. We need ground truth.

---

## Step 1: Capture the Failure State

### Required Data

| Variable | Address | Expected Normal | Failure Value |
|----------|---------|-----------------|---------------|
| GameMode | `$7E0010` | 0x07 (Underworld) | ??? |
| Submodule | `$7E0011` | Should cycle, end at 0x00 | ??? |
| INIDISP | `$7E001A` | 0x0F (visible) | ??? |
| INIDISP Queue | `$7E0013` | 0x0F | ??? |
| Room ID | `$7E00A0` | Target room | ??? |
| Entrance ID | `$7E010E` | Valid entrance | ??? |

### Capture Method

1. Build ROM: `./scripts/build_rom.sh 168`
2. Launch Mesen2 with transition debug script:
   ```bash
   ~/src/tools/emu-launch -m Roms/oos168x.sfc scripts/mesen_transition_debug.lua
   ```
3. **Primary repro (2026-01-30):** load Save State 2, highlight the file, press A to load into the dungeon (freeze on load screen).
4. Alternate repro: navigate to a building/dungeon entrance that triggers the bug in normal play.
5. **Immediately pause when screen goes black**
6. Record ALL values in the HUD overlay
7. Check Mesen2's log output (Script Window)
8. Screenshot the failure state

### Capture Checklist

- [ ] Location where bug was triggered: _______________
- [ ] Entrance type (door/stairs/cave): _______________
- [ ] Frame count when black screen started: _______________
- [ ] GameMode at failure: _______________
- [ ] Submodule at failure: _______________
- [ ] INIDISP at failure: _______________
- [ ] Last Mode transition logged: _______________
- [ ] Last Submodule logged: _______________
- [ ] PC address (if available): _______________
- [ ] Screenshot saved: _______________

---

## Step 2: Diagnose from Observations

### Failure Categories

| Observation | Diagnosis | Next Step |
|-------------|-----------|-----------|
| Mode stuck at 0x06 (UW_Load) | Room load hung | Trace room loading |
| Mode at 0x07, INIDISP=0x80 | Fade-in never happened | Trace INIDISP writes |
| Mode at 0x07, Sub stuck non-0 | Submodule state machine hung | Trace submodule handler |
| Mode jumps to invalid value | Memory corruption | Find corrupting write |

### Key Routines to Trace

| Address | Label | Purpose |
|---------|-------|---------|
| `$02809F` | Module07_Underworld dispatch | Main underworld handler |
| `$028364` | Module06_UnderworldLoad | Room loading |
| `$02895D` | Module07_02_01 | Inter-room transition |
| `$0288B8` | Intraroom transition setup | Layer change preparation |

---

## Step 3: Create Targeted Breakpoint Script

Once failure state is captured, create a breakpoint script to catch the moment it happens:

```lua
-- breakpoint_blackscreen.lua
-- Set breakpoint on INIDISP write, break when it stays blanked

local blankFrames = 0
local INIDISP = 0x7E001A

function Main()
    local indi = emu.read(INIDISP, emu.memType.snesMemory)
    if indi == 0x80 or indi == 0x00 then
        blankFrames = blankFrames + 1
        if blankFrames > 120 then  -- 2 seconds of black screen
            emu.breakExecution()
            emu.log("BLACK SCREEN DETECTED - paused for inspection")
        end
    else
        blankFrames = 0
    end
end

emu.addEventCallback(Main, emu.eventType.endFrame)
```

---

## Observed Failure Data

### Session: 2026-01-24 - Pending Capture

**Build Status:** ROM rebuilt with latest fixes at 02:37

**Fixed build errors (unrelated to bug):**
- `Oracle_SpriteDraw_RaceGameLady` label redefinition (ranch_girl.asm)
- Relative branch out of bounds in ocarina.asm and menu.asm

**Ready to test:**
- ROM: `Roms/oos168x.sfc`
- Capture script: `scripts/capture_blackscreen.lua`
- Auto-test script: `scripts/auto_entrance_test.lua`

### Capture #1: 2026-01-30 (Save State 2 file-load dungeon freeze)

```
Repro: Load slot 2 → highlight file → press A → run 600 frames → freeze

GameMode ($7E0010): 0x07 (Underworld)
Submodule ($7E0011): 0x0F
INIDISP ($7E001A): 0x08
INIDISP Queue ($7E0013): 0x0F
Indoors ($7E001B): 0x01
Room ID ($7E00A0): 0x0104 (Link's House)
Entrance ID ($7E010E): 0x0000

CPU snapshot:
  PC=0x00B7B8  K=0x00  DBR=0x50  D=0x1009  P=0x34  SP=0x0D06  A=0xCB01
Stack retaddr:
  SP=0x0D06 -> [0]=0x04000C (WRAM mirror), [1]=0x1D8001 (ROM)
```

**Analysis:** This freeze shows **stack corruption** (SP=0x0D06, DBR=0x50) similar to the
overworld softlock chain. Treat as stack/return corruption until proven otherwise.

---

## Previous Theoretical Fixes (UNVERIFIED)

These fixes were applied based on theory, not observation. They may or may not be correct.

1. **16-bit/8-bit mode mismatch** - Added SEP/REP wrapper to `CheckForFollowerIntraroomTransition`
2. **Data Bank addressing** - Changed `STA.w $7EF3CC` to `STA.l $7EF3CC`

**Status:** Neither fix has been verified to address the actual bug. The bug may have a completely different root cause.

---

## Notes

- Don't trust any fix until it's verified against the actual failure state
- The failure could be in code unrelated to what we've been looking at
- Multiple bugs could exist - fixing one may reveal another
