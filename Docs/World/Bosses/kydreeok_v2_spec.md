# Kydreeok Boss Refactor - Technical Specification (v2)

**Target Files:**
- `Sprites/Bosses/kydreeok_v2.asm` (New Body Logic)
- `Sprites/Bosses/kydreeok_head_v2.asm` (New Head Logic)

## 1. Core Architecture Changes
The original Kydreeok implementation suffered from rigid "hard-coded" physics. The new **v2** implementation uses a **Dynamic Chain Physics** model with a **Parent-Child** architecture optimized for sprite slot usage.

### 1.1. The Chain Hierarchy
We will use a **Virtual Segment** approach (inspired by `SpiderBoss` drawing routines) rather than spawning separate sprites for every neck segment. This keeps the sprite count low (3 total: Body + 2 Heads).

1.  **Anchor (Body):** The `kydreeok_v2` body sprite defines the **Anchor Point** (`NeckAnchorX/Y`).
2.  **Virtual Segments:** The `Head` sprite calculates and stores the coordinates of 3 neck segments in RAM. These are *not* active sprites.
3.  **Head (Leader):** The `kydreeok_head_v2` sprite moves freely. The virtual segments strictly follow the head using Drag Physics.

### 1.2. Memory Map (RAM Strategy)
We need shared RAM for the body to communicate anchor positions to the heads, and for the heads to store their segment positions for drawing.

| Variable | Purpose | Owner |
|---|---|---|
| `$19EA-$19EF` | **Left Neck Chain** (Seg1 X/Y, Seg2 X/Y, Seg3 X/Y) | `LeftHead` |
| `$19F0-$19F5` | **Right Neck Chain** (Seg1 X/Y, Seg2 X/Y, Seg3 X/Y) | `RightHead` |
| `SprMiscA/B` (Body) | **Anchor Point** (Where necks attach to body) | `Body` |
| `SprMiscC` (Head) | **Parent Slot Index** (Index 0-15 of the Body sprite) | `Head` |
| `SprMiscD` (Head) | **Lunge State** (0=Idle, 1=Prep, 2=Dash, 3=Retract) | `Head` |

### 1.3. Parent Tracking Pattern (From GuardianBoss/Poltergeist)
-   **Spawning:** The Body (Parent) spawns the Heads (Children).
-   **Linking:** During spawn, the Body stores its own Sprite Index (`X`) into the Child's `SprMiscC` variable.
-   **Access:** The Head can now read the Body's position directly using `LDY SprMiscC, X` -> `LDA SprX, Y`. This is more robust than hardcoding slots or searching every frame.

## 2. Head Logic (`kydreeok_head_v2.asm`)
The head is the "Driver" of the chain.

### 2.1. State Machine
*   **State 00 (Orbit):**
    *   Behavior: Rotates around the Body's center.
    *   Transition: Random timer triggers `State 01 (Lunge Prep)`.
*   **State 01 (Lunge Prep):**
    *   Behavior: Stops. Faces Link. Roar animation.
    *   Transition: Timer $\to$ 0 triggers `State 02 (Lunge Dash)`.
*   **State 02 (Lunge Dash):**
    *   Behavior: High velocity towards Link.
    *   Transition: Timer $\to$ 0 OR Wall Collision triggers `State 03 (Lunge Retract)`.
*   **State 03 (Lunge Retract):**
    *   Behavior: Moves towards the **Orbit Target** (calculated relative to Body).
    *   Transition: Reaching target triggers `State 00 (Orbit)`.

### 2.2. Chain Physics Routine (`UpdateNeckSegments`)
Runs every frame in the Head's main loop.
1.  **Read Anchor:** Fetch Body Anchor X/Y using `SprMiscC` (Parent Index).
2.  **Drag Segments:**
    -   `Seg1` is dragged by `Head`.
    -   `Seg2` is dragged by `Seg1`.
    -   `Seg3` is dragged by `Seg2`.
3.  **Anchor Constraint:**
    -   Check distance between `Seg3` and `BodyAnchor`.
    -   If > Limit, pull `Seg3` towards `BodyAnchor`, then propagate pull back up the chain (IK Solver) OR just clamp it (simpler).
    -   *Simplified approach:* Just drag from Head down. If the chain breaks (disconnects from body), we just draw a line/segment to fill the gap or limit the Head's range.

### 2.3. Drawing Routine
The Head sprite's Draw routine handles drawing:
1.  The Head itself (standard).
2.  The 3 Neck Segments (using coordinates from `$19EA/$19F0`).
3.  This mimics the `SpiderBoss` technique where a single sprite controller draws multiple components.

## 3. Body Logic (`kydreeok_v2.asm`)
The coordinator.

### 3.1. Responsibilities
1.  **Spawning:** Spawns 2 Heads. Sets `SprMiscC` in children to its own index.
2.  **Anchor Update:** continually updates `SprMiscA/B` (Anchor X/Y) based on its current animation frame (e.g., shell moving up/down).
3.  **Damage Relay:** (Optional) If we want shared health, damage to Heads could transfer to Body.
4.  **Death:** Explodes only when both Heads are dead.

## 4. Implementation Plan
1.  **Step 1 (Body):** Create `kydreeok_v2.asm`. Implement movement and Child Spawning (with Index passing).
2.  **Step 2 (Head Basic):** Create `kydreeok_head_v2.asm`. Implement Orbit movement reading Parent position.
3.  **Step 3 (Physics):** Implement `UpdateNeckSegments` logic and RAM storage.
4.  **Step 4 (Drawing):** Implement the multi-segment draw routine in Head.
5.  **Step 5 (States):** Implement the Lunge State Machine.

## 5. Reference Code (Chain Physics)
Standard Drag Algorithm:
```asm
; Input: Source(X,Y), Target(X,Y), Length
; Output: New Source(X,Y)
CalculateAngle(Source, Target) -> Theta
Move Source towards Target until Dist == Length
```

