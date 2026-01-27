# Oracle of Secrets Agent Brain

This directory contains the "Intelligence" layer for the Mesen2 Agent. It sits on top of the `mesen2_client_lib` and provides higher-level cognitive functions.

## Capabilities

### 1. Intelligent Navigation (`Navigator`)
- **Collision Awareness**: Reads the live collision map (ColMap A - $7F2000) from the emulator via the `GET_COLLISION` bridge command.
- **Pathfinding**: Implements A* algorithm to find optimal paths around obstacles.
- **Usage**:
  ```python
  agent.goto(target_x, target_y)
  ```

### 2. State Awareness (`GameState`)
- **Structured Data**: Converts raw RAM values into a clean Python object (`agent.state`).
- **Properties**:
  - `state.link_pos`: (x, y) coordinates
  - `state.health`: Current HP
  - `state.mode`: Game mode (Overworld, Dungeon, etc.)
  - `state.is_gameplay`: Boolean flag for valid gameplay states

### 3. Smart Save Management (`SaveManager`)
- **Safety Checks**: Prevents saving bad states (soft-locks, death loops).
- **Criteria**:
  - HP > 0
  - Link is not inside a solid tile (collision check)
  - Game Mode is valid (0x07 Dungeon or 0x09 Overworld)
  - Link Action State is safe (e.g., standing, swimming; not falling)

### 4. Input Mapping Auto-Detection (B008)
- **Auto Mode (default)**: Detects if D-pad input is rotated (90° CW) and applies correction only when needed.
- **Manual Override**: Force `on` or `off` via `agent.set_b008_mode("on"|"off")`.
- **Note**: Auto-detect probes a short movement in gameplay to infer rotation.

## Usage

### CLI Command
You can use the smart save feature directly from the command line:

```bash
# Save to slot 1 ONLY if the state is considered safe
./scripts/mesen2_client.py smart-save 1
```

### Python API
Import the agent brain in your own scripts:

```python
from agent.brain import AgentBrain

agent = AgentBrain()  # B008 input correction auto-detects by default

# Run one tick of the agent loop
agent.tick()

# Print current state
print(f"Health: {agent.state.health}")

# Move to a specific tile coordinate
agent.goto(32, 32)

# Save safely
agent.validate_and_save(1)

# Force input correction behavior if needed
agent.set_b008_mode("on")   # always apply rotation correction
agent.set_b008_mode("off")  # never apply rotation correction

# One-shot auto calibration (returns "on", "off", or "unknown")
agent.calibrate_b008()
```

## Methodology

1.  **Bridge Extension**: We extended `mesen_live_bridge.lua` to dump the 4KB collision map to a binary file.
2.  **Socket Transport**: The `OracleDebugClient` triggers this dump and reads the file.
3.  **Local Processing**: The Python `Navigator` parses this binary map to build a navigation grid.
4.  **Feedback Loop**: The agent ticks every frame/interval, updates its internal state model, and decides on actions (Input Injection) based on the plan.
