# State Quality & Emulator Management Roadmap

> NOTE (2026-02-07): This roadmap predates the current save-data/profile tooling.
> References to `scripts/mesen2_client_lib/state_library.py`, `state_library.py`, and `mesen_cli.sh` are historical.
> Current entry points:
> - `RUNBOOK.md`
> - `python3 scripts/mesen2_client.py library` (savestate library)
> - `python3 scripts/mesen2_client.py save-data ...` (profiles, snapshots, `.srm` hot reload)

## Problem Statement

1. **State Quality**: 11 "baseline" states are identical copies - no validation on capture
2. **Stale Sockets**: Mesen2 sockets persist after crashes/force-quit (no signal handlers)
3. **Window Management**: Emulator windows need predictable positioning without auto-tiling

---

## Phase 1: Socket Lifecycle & Cleanup

### 1.1 Signal Handler in Mesen2 (C++)

**File:** `Core/Shared/SocketServer.cpp`

Add signal handlers for graceful cleanup:
```cpp
#include <signal.h>

static SocketServer* g_socketServerInstance = nullptr;

static void SignalHandler(int signum) {
    if (g_socketServerInstance) {
        g_socketServerInstance->Stop();
    }
    signal(signum, SIG_DFL);
    raise(signum);
}

void SocketServer::Start() {
    // ... existing code ...
    g_socketServerInstance = this;
    signal(SIGINT, SignalHandler);
    signal(SIGTERM, SignalHandler);
}

void SocketServer::Stop() {
    // ... existing code ...
    g_socketServerInstance = nullptr;
    signal(SIGINT, SIG_DFL);
    signal(SIGTERM, SIG_DFL);
}
```

### 1.2 Wrapper Script with Cleanup

**File:** `~/src/tools/mesen-run`

Update to track PID and cleanup on exit:
```bash
cleanup_stale_sockets() {
    for sock in /tmp/mesen2-*.sock; do
        [ -e "$sock" ] || continue
        pid=$(basename "$sock" | sed 's/mesen2-\([0-9]*\).sock/\1/')
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$sock" "/tmp/mesen2-${pid}.status"
        fi
    done
}
```

### 1.3 Pre-launch Cleanup in mesen2_client.py

**File:** `scripts/mesen2_client_lib/bridge.py`

Add stale socket detection before connecting.

---

## Phase 2: State Quality System

### 2.1 Schema Update

**File:** `Docs/Tooling/Testing/save_state_library.json`

Add new fields to manifest entries:
```json
{
  "id": "...",
  "status": "draft|canon|deprecated",
  "captured_by": "human|agent",
  "verified_by": null,
  "verified_at": null,
  "md5": "...",
  "gameState": {
    "mode": "0x09",
    "area": "0x29",
    "position": [512, 512]
  }
}
```

### 2.2 Validation on Save

**File:** `scripts/mesen2_client_lib/state_library.py`

Add to `save_labeled_state()`:
1. Compute MD5 hash of new state file
2. Compare against all existing states
3. Warn if duplicate detected
4. Validate position matches claimed location

### 2.3 Verification Command

**File:** `scripts/mesen2_client.py`

Add `lib-verify <state_id>` command:
1. Load state in emulator
2. Show current game state (area, position, mode)
3. Prompt user to confirm it matches expected
4. On confirm: set `status: canon`, `verified_by: scawful`, `verified_at: <timestamp>`

### 2.4 Battery Test Filter

**File:** `scripts/campaign/transition_tester.py`

Update `run_state_battery()`:
- Only test states with `status: canon`
- Skip `draft` and `deprecated` states
- Log skipped states with reason

---

## Phase 3: Yabai Window Management

### 3.1 Current State (Already Done)

**File:** `~/.config/yabai/yabairc` (line 52)
```bash
yabai -m rule --add app="^(Mesen|Mesen2.*)$" manage=off
```

This already prevents auto-tiling.

### 3.2 Position Persistence (Optional)

Add to mesen2_client.py `launch` command:
```bash
# After launch, position window at consistent location
yabai -m window --focus "$(yabai -m query --windows | jq '.[] | select(.app=="Mesen") | .id')"
yabai -m window --move abs:100:100
yabai -m window --resize abs:800:600
```

### 3.3 Focus Command

**File:** `scripts/mesen2_client.py`

Add `focus` command to bring emulator window to front:
```python
def cmd_focus():
    """Bring Mesen2 window to foreground."""
    subprocess.run([
        "osascript", "-e",
        'tell application "System Events" to set frontmost of process "Mesen" to true'
    ])
```

---

## Phase 4: Cleanup Baseline States

### 4.1 Delete Broken Baselines

Remove the 11 identical baseline state files and manifest entries.

### 4.2 Capture New Canon States

Using verified workflow:
1. Launch emulator
2. Navigate to location manually
3. `lib-save "Description"` (creates draft)
4. Verify in-game
5. `lib-verify <id>` (promotes to canon)

### 4.3 Required Canon States

| Location | Area | Purpose |
|----------|------|---------|
| Link's House | 0x1B | Stable reference |
| Lost Woods Center | 0x29 | Transition hotspot |
| Village West | 0x23 | Near boundary |
| Dark World Pyramid | 0x40 | Cross-world testing |
| Castle Entrance | 0x00 | Game start |

---

## Execution Order

1. **Phase 2.1-2.2** - Schema + validation (code changes)
2. **Phase 1.2** - Wrapper script cleanup
3. **Phase 2.3** - Verification command
4. **Phase 2.4** - Battery test filter
5. **Phase 4.1-4.3** - Clean up and recapture states
6. **Phase 1.1** - Signal handlers (optional, requires Mesen2 rebuild)
7. **Phase 3.2-3.3** - Window management (optional)

---

## Success Criteria

- [x] `lib-save` rejects duplicates (hash match warning) - **DONE**
- [ ] `lib-save` validates position against claimed location - *Partial: captures metadata, no explicit rejection yet*
- [x] `lib-verify` promotes draft → canon with user confirmation - **DONE**
- [x] Battery tests skip non-canon states (default: canon only) - **DONE**
- [x] Stale sockets cleaned (`socket-cleanup` command) - **DONE**
- [ ] 5 verified canon states in library - *Pending: manual capture needed*

---

## Implementation Status (2026-01-25)

### Completed

1. **Schema Update** (`state_library.py`)
   - Added: `status` (draft/canon/deprecated), `captured_by`, `verified_by`, `verified_at`, `md5`
   - New methods: `verify_state()`, `deprecate_state()`, `backfill_hashes()`, `find_states_by_hash()`

2. **Hash Validation** (`state_library.py`)
   - `save_labeled_state()` now computes MD5 and warns on duplicates
   - Returns `(state_id, warnings)` tuple

3. **CLI Commands** (`cli.py`)
   - `lib-verify <state_id>` - Promote draft → canon
   - `lib-deprecate <state_id>` - Mark as deprecated
   - `lib-backfill` - Add hashes to old entries
   - `socket-cleanup` - Remove stale sockets
   - `lib-save --captured-by human|agent`
   - `library` output now shows status badges

4. **Battery Test Filter** (`transition_tester.py`)
   - Default: `canon_only=True` (only tests canon states)
   - `--include-draft` flag to also test draft states
   - Skipped states logged in summary

5. **Socket Cleanup** (`bridge.py`)
   - `cleanup_stale_sockets()` function removes orphaned `/tmp/mesen2-*.sock` files

### Pending

1. **Capture Canon States** - Manual workflow:
   ```bash
   python3 scripts/mesen2_client.py lib-save "Location Name" --captured-by human -t tag1 -t tag2
   # Navigate to location, verify correct
   python3 scripts/mesen2_client.py lib-verify <state_id>
   ```

2. **Mesen2 Signal Handlers** (optional) - C++ changes to SocketServer.cpp for graceful exit
