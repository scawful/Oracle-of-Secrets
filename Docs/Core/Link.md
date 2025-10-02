# Bank $07: Core Player (Link) Engine Analysis

**File**: `ALTTP/bank_07.asm`
**Address Range**: `$078000` - `$07FFFF`

This bank is dedicated entirely to the player character, Link. It contains his core state machine, which governs everything from movement and physics to item usage and interaction with the world. It is executed every frame that the player has control and is not in a cutscene.

---

### 1. Main Entry Point: `Link_Main`

*   **Routine**: `Link_Main` (`#_078000`)
*   **Purpose**: This is the top-level function for all player-related code, called once per frame from the main game loop when the game is in a playable state (e.g., Overworld or Underworld).
*   **Functionality**:
    1.  It first checks if the player is in a state that prevents control (e.g., a cutscene, indicated by `$02E4` being non-zero).
    2.  If the player has control, it calls `Link_ControlHandler`, which is the heart of the player engine.
    3.  After the main handler runs, it calls `HandleSomariaAndGraves` to process interactions with those specific objects, which need to be checked every frame.

---

### 2. The Player State Machine: `Link_ControlHandler`

*   **Routine**: `Link_ControlHandler` (`#_07807F`)
*   **Purpose**: This function acts as a state machine dispatcher. It reads Link's current state from a single, critical WRAM variable and jumps to the appropriate logic handler for that state.
*   **Critical WRAM Variable**: `$7E005D` (`LINKDO`) - This byte holds Link's current state ID. Modifying this value directly forces Link into a different state.

*   **Execution Flow**:
    1.  **Damage Check**: Before any other action, the handler checks if Link has taken damage (`$7E0373`, `HURTME`). If so, it processes the damage, checks for the Magic Cape (`$7E0055`), reduces health, and can trigger a state change to `LinkState_Recoil` or the death sequence.
    2.  **State Dispatch**: It reads the value of `LINKDO`, multiplies it by two (since each entry is a 2-byte address), and uses it as an index into the `.vectors` jump table (`#_078041`). It then performs a `JMP` to the corresponding state handler routine.

---

### 3. Link State Vector Table

This table at `#_078041` defines all 31 possible states for Link. Understanding this is key to modifying player behavior.

| State ID | Label (`#_07....`) | Description |
|:---:|---|---|
| `0x00` | `LinkState_Default` | The normal on-foot state for walking, standing, and most basic interactions. |
| `0x01` | `LinkState_Pits` | Handles the logic for falling into a pit. |
| `0x02` | `LinkState_Recoil` | Handles being knocked back by an enemy or obstacle. |
| `0x03` | `LinkState_SpinAttack` | Manages the spin attack animation and hitbox. |
| `0x04` | `LinkState_Swimming` | The state for swimming in water. |
| `0x05` | `LinkState_OnIce` | Handles movement physics for icy surfaces. |
| `0x06` | `LinkState_Recoil` | A duplicate pointer to the recoil state, likely for a different impact type. |
| `0x07` | `LinkState_Zapped` | A special recoil state for electrical damage. |
| `0x08` | `LinkState_UsingEther` | Handles the animation and logic for using the Ether medallion. |
| `0x09` | `LinkState_UsingBombos` | Handles the animation and logic for using the Bombos medallion. |
| `0x0A` | `LinkState_UsingQuake` | Handles the animation and logic for using the Quake medallion. |
| `0x0B` | `LinkState_HoppingSouthOW` | Manages the multi-frame action of hopping off a ledge to the south. |
| `0x0C` | `LinkState_HoppingHorizontallyOW` | Manages hopping off a ledge to the east or west. |
| `0x0D` | `LinkState_HoppingDiagonallyUpOW` | Manages hopping off a ledge diagonally up-left or up-right. |
| `0x0E` | `LinkState_HoppingDiagonallyDownOW`| Manages hopping off a ledge diagonally down-left or down-right. |
| `0x0F` | `LinkState_0F` | A generic ledge-hopping state. |
| `0x10` | `LinkState_0F` | (Duplicate) A generic ledge-hopping state. |
| `0x11` | `LinkState_Dashing` | The state for running with the Pegasus Boots. |
| `0x12` | `LinkState_ExitingDash` | The brief turn-around animation after a dash collides with a wall. |
| `0x13` | `LinkState_Hookshotting` | Manages Link's state while the hookshot is extended. |
| `0x14`| `LinkState_CrossingWorlds` | Handles the Magic Mirror animation and world transition. |
| `0x15` | `LinkState_ShowingOffItem` | The "item get" pose when Link holds an item above his head. |
| `0x16` | `LinkState_Sleeping` | For the beginning of the game when Link is in bed. |
| `0x17` | `LinkState_Bunny` | The state for when Link is transformed into a bunny in the Dark World. |
| `0x18` | `LinkState_HoldingBigRock` | The state for lifting a heavy, dark-colored rock (requires Titan's Mitt). |
| `0x19` | `LinkState_ReceivingEther` | The cutscene for receiving the Ether medallion from the tablet. |
| `0x1A` | `LinkState_ReceivingBombos` | The cutscene for receiving the Bombos medallion from the tablet. |
| `0x1B` | `LinkState_ReadingDesertTablet` | The cutscene for reading the Desert Palace tablet. |
| `0x1C` | `LinkState_TemporaryBunny` | The brief bunny transformation sequence when entering the Dark World. |
| `0x1D` | `LinkState_TreePull` | The state for pulling on the tree in the haunted grove for the race game. |
| `0x1E` | `LinkState_SpinAttack` | (Duplicate) A second entry for the spin attack state. |

---

### 4. Analysis of Core States

#### `LinkState_Default` (`#_078109`)

This is the most complex state and serves as the foundation for player control. It is a large routine that dispatches to numerous sub-handlers.

*   **Initial Checks**:
    *   `Link_HandleBunnyTransformation`: Checks if Link should transform into a bunny.
    *   Checks for recoil/damage (`$7E004D`) and branches to a simplified physics handler if necessary.
*   **Action Dispatching**: If not recoiling, it checks for player input and calls the appropriate action handler.
    *   `Link_HandleToss`: Checks if Link is throwing a carried object.
    *   `Link_HandleAPress`: Handles context-sensitive actions for the A button (talk, read, lift, open, dash).
    *   `Link_HandleYItem`: Manages using the currently selected item (bow, boomerang, rods, etc.).
    *   `Link_HandleSwordCooldown`: Manages sword swings and charging a spin attack.
*   **Physics and Collision**: If no other action is taken, it processes movement.
    *   `ResetAllAcceleration`: Clears speed values if Link is standing still.
    *   `Link_HandleDiagonalCollision` & `Link_HandleCardinalCollision`: Check for collisions with walls and objects.
    *   `JSL Link_HandleVelocity`: The main physics engine. Applies acceleration, deceleration, and the final movement vector to Link's coordinates.
*   **Animation & Camera**:
    *   `JSL Link_HandleMovingAnimation_FullLongEntry`: Updates Link's sprite graphics based on his direction and action.
    *   `HandleIndoorCameraAndDoors`: Manages camera scrolling and door transitions indoors.

#### `LinkState_Recoil` (`#_0786B5`)

This state demonstrates how control is temporarily taken from the player.

*   **Z-Axis Movement**: It uses `$7E0024` (Link's Z-position) and `$7E0029` (knockback Z-velocity) to handle Link being knocked into the air and falling back down.
*   **Timer-Based**: The duration of the recoil is controlled by a countdown timer in `$7E0046` (`INPAIN`). Once the timer reaches zero, Link's state is typically returned to `LinkState_Default`.
*   **Collision & Landing**: While in recoil, it still checks for collisions. It also has special checks for landing, such as `Link_SplashUponLanding` if he falls into water, which can change his state to `LinkState_Swimming`.

#### `LinkState_Bunny` (`#_0783A1`)

This state shows a persistent change in abilities.

*   **Simplified Controls**: The bunny state has a much simpler control handler. It still allows for movement but disables all item and sword usage.
*   **State Check**: It constantly checks for the condition that allows Link to transform back: the presence of the Moon Pearl (`$7EF357`). If the pearl is obtained or Link leaves the Dark World, it triggers the transformation back to the default state.

---

### 5. Key WRAM Variables for Link

This bank relies on a large number of WRAM addresses to function. Understanding these is critical to debugging or modifying player logic.

| Address | Label | Description |
|:---:|---|---|
| `$7E005D` | `LINKDO` | **Link's State**: The primary state ID, used as an index for the state machine. |
| `$7E0020/21`| `POSY` | Link's 16-bit Y-coordinate. |
| `$7E0022/23`| `POSX` | Link's 16-bit X-coordinate. |
| `$7E0024` | `POSZ` | Link's 8-bit Z-coordinate (height). |
| `$7E0026` | - | Link's facing direction. |
| `$7E0027/28`| - | Link's Y/X velocity. |
| `$7E002A/2B`| - | Link's Y/X sub-pixel position. |
| `$7E003A` | - | Action flags (bitfield for sword charging, etc.). |
| `$7E0046` | `INPAIN` | Recoil/invincibility timer after taking damage. |
| `$7E004D` | - | A flag indicating Link is in a recoil state. |
| `$7E0303` | - | The ID of the currently selected Y-button item. |
| `$7E0373` | `HURTME` | Damage value to be applied to Link on the next frame. |
| `$7E037B` | - | A flag that temporarily disables taking damage. |
| `$7E0372` | - | A flag indicating Link is currently dashing. |
