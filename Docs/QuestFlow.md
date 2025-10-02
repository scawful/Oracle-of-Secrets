# Quest & Event Flow

This document outlines the progression of the main story and major side-quests. It details the flags and conditions that control the game's narrative flow, making it easier to understand how events are triggered.

## 1. Main Quest Progression

*This section provides a step-by-step guide to the main story, detailing the sequence of events, required items, and the flags that are set at each milestone.*

### Chapter 0: A Hero is Born

1.  **Trigger:** The game begins.
2.  **Events:**
    *   The Farore intro sequence plays, explaining the backstory of the Triforce and the sealing of the Sacred Realm.
    *   Link is shipwrecked and awakens in the Eon Abyss.
    *   The Kydrog intro sequence plays, showing the game's antagonist.
    *   Link is transported to the Temporal Pyramid.
3.  **Player Actions:**
    *   Navigate the Temporal Pyramid to find the **Moon Pearl**.
    *   Exit the pyramid to arrive in the Forest of Dreams.
    *   Obtain the **Lv1 Sword and Shield**.
4.  **Progression Flags:**

| Flag       | Address  | Value/Bit      | Notes                               |
|------------|----------|----------------|-------------------------------------|
| `GameState`| `$7EF3C5`| `0x02`         | Set after the Farore intro.         |
| `OosProg2` | `$7EF3C6`| `bit $04` set  | Set after the Kydrog intro.         |

### Chapter 1: The Maku Tree Awakens

1.  **Trigger:** Player talks to the Maku Tree for the first time (`Sprites/NPCs/maku_tree.asm`).
2.  **Events:** The Maku Tree speaks to Link, explaining the plight of the land.
3.  **Reward:** A Heart Container is given to the player (`Link_ReceiveItem` with Y=`$3E`).
4.  **Progression Flags & Consequences:**

| Flag            | Address  | Value/Bit     | Consequence                                                              |
|-----------------|----------|---------------|--------------------------------------------------------------------------|
| `MakuTreeQuest` | `$7EF3D4`| `0x01`        | The Maku Tree will now use a different dialogue branch on subsequent talks. |
| `MapIcon`       | `$7EF3C7`| `0x01`        | A red 'X' appears on the map over the Mushroom Grotto.                   |
| `OOSPROG`       | `$7EF3D6`| `bit $02` set | A major story flag indicating the quest has officially begun.            |

### Chapter 2: The Mushroom Grotto (D1)

1.  **Trigger:** Player enters the Mushroom Grotto, west of Wayward Village.
2.  **Events:** Player navigates the dungeon, facing the Vampire Bat miniboss and the Mothra boss.
3.  **Reward:** **Bow**.

### Chapter 3: The Tail Palace (D2)

1.  **Trigger:** Player enters Tail Palace.
2.  **Events:** Player defeats the boss, a vanilla-style Big Moldorm.
3.  **Reward:** **Roc's Feather**.
4.  **World State Changes:** After completion, Deku NPCs will appear in the overworld area near Tail Palace.

### Chapter 4: The Path to the Castle

1.  **Trigger:** This is a multi-part quest chain required to access Kalyxo Castle.
2.  **Player Actions:**
    *   **Ocarina:** Complete the "Lost Ranch Girl" side-quest to obtain the Ocarina.
    *   **Song of Healing:** Learn the Song of Healing from the Happy Mask Salesman.
    *   **Running Boots:** Play the Song of Healing for the sick child in Wayward Village to receive the Running Boots.
    *   **Book of Secrets:** Use the Running Boots to get the Book of Secrets from the village library.
3.  **Consequence:** The Book of Secrets is required to open the gates to Kalyxo Castle.

### Chapter 5: Kalyxo Castle (D3)

1.  **Trigger:** Player enters Kalyxo Castle.
2.  **Required Items:** Book of Secrets.
3.  **Events:** Player defeats the Armos Knights boss.
4.  **Reward:** **Meadow Blade (Lv2 Sword)**.

### Chapter 6: The Shrine of Wisdom (S1)

1.  **Trigger:** Player enters the Shrine of Wisdom.
2.  **Events:** Player must navigate a swampy overworld area.
3.  **Reward:** **Zora Flippers**.

### Chapter 7: Zora Temple (D4)

1.  **Trigger:** Player enters the Zora Temple.
2.  **Required Items:** Zora Flippers.
3.  **Events:** Player defeats an advanced variant of the Arrghus boss.
4.  **Reward:** **Hookshot**, **Zora Mask** (via side-quest within the dungeon).

### Chapter 8: Glacia Estate (D5)

1.  **Trigger:** Player enters Glacia Estate.
2.  **Required Items:** **Goldstar** (from the "Old Man Mountain Quest").
3.  **Events:** Player navigates ice puzzles and defeats the Twinrova boss.
4.  **Reward:** **Fire Rod**.

### Chapter 9: The Shrine of Power (S2)

1.  **Trigger:** Player enters the Shrine of Power.
2.  **Reward:** **Power Glove**.

### Chapter 10: Goron Mines (D6)

1.  **Trigger:** Player enters the Goron Mines.
2.  **Required Items:** **Power Glove**, Completion of the "Goron Mines Quest".
3.  **Events:** Player defeats the Lanmolas and the King Dodongo (Helmasaur variant) boss.
4.  **Reward:** **Hammer**.

### Chapter 11: Dragon Ship (D7)

1.  **Trigger:** Player enters the Dragon Ship.
2.  **Reward:** **Somaria Rod**.

### Chapter 12: The Shrine of Courage (S3)

1.  **Trigger:** Player enters the Shrine of Courage.
2.  **Events:** Player defeats the boss Vaati (Vitreous variant).
3.  **Reward:** **Mirror Shield**.

### Chapter 13: Fortress of Secrets (D8)

1.  **Trigger:** Player enters the Fortress of Secrets.
2.  **Events:** Player defeats Dark Link.
3.  **Reward:** **Portal Rod**.

### Chapter 14: The Eon Core (Endgame)

1.  **Trigger:** Player enters the final dungeon.
2.  **Events:** Player faces the final bosses: Kydreeok and Ganon.
3.  **Reward:** **The Triforce**.

---

## 2. Major Side-Quests

### The Lost Ranch Girl (Ocarina Quest)

1.  **Mushroom:** Get a Mushroom from the old woman's house in the Mushroom Grotto area.
2.  **Magic Powder:** Trade the Mushroom to the Potion Shop owner. Leave the area and return later to receive the Magic Powder.
3.  **Ocarina:** Use the Magic Powder on the sleeping Cucco in the Ranch House. This wakes it up and it gives you the Ocarina.

### The Mask Salesman

1.  **Trigger:** Player must have the Ocarina.
2.  **Action:** Talk to the Happy Mask Salesman.
3.  **Reward:** He teaches Link the **Song of Healing**.

### The Zora Mask

1.  **Trigger:** Player talks to the Zora Princess in the Zora Temple. She gives message `$0C5`.
2.  **Action:** Player must play the Song of Healing.
3.  **Reward:** The princess gives the player the **Zora Mask**.
4.  **Flag:** `ZoraMask` (`$7EF347`) is set in SRAM.

### The Wolf Mask

1.  **Trigger:** A Wolfos sprite appears outside Kalyxo Castle at night.
2.  **Action:** Player must defeat the Wolfos and then play the Song of Healing.
3.  **Reward:** **Wolf Mask**.

### Old Man Mountain Quest

1.  **Trigger:** Player takes the warp portal at the northwest point of Mount Snowpeak.
2.  **Action:** Enter the Lava Lands cave to find an Old Man sprite. Escort him to a rock formation and use the Magic Mirror.
3.  **Reward:** **Goldstar** (upgrade for the Hookshot).

### Goron Mines Quest

1.  **Trigger:** Player needs to open the Goron Mines.
2.  **Required Item:** Power Glove.
3.  **Action:**
    *   Collect five pieces of Goron Rock Meat from Lupo Mountain.
    *   Give the five pieces to the Kalyxian Goron NPC in the desert.
4.  **Consequence:** The Goron NPC opens the entrance to the Goron Mines.

### The Magic Bean

1.  **Purchase:** Player buys the Magic Bean from the Bean Vendor for 100 rupees. Requires an empty bottle.
2.  **Planting:** Player takes the bean to the fertile soil patch on the ranch. `MagicBeanProg` (`$7EF39B`) has bit `$01` set.
3.  **Watering:** Player plays the Song of Storms. `MagicBeanProg` has bit `$04` set.
4.  **Pollination:** Player must release a Good Bee from a bottle near the bean sprout. `MagicBeanProg` has bit `$02` set.
5.  **Growth:** After 3 in-game day/night cycles, the beanstalk grows into a large flower.
6.  **Reward:** The player can ride the flower to a Heart Container. `MagicBeanProg` has bit `$40` set upon completion.