# NPCs Analysis

This document provides an analysis of the Non-Player Character (NPC) sprites found in the `Sprites/NPCs/` directory.

## File Overview

| Filename | Sprite ID(s) | Description |
|---|---|---|
| `bean_vendor.asm` | `Sprite_BeanVendor` | Handles the logic for the bean vendor who sells Magic Beans to the player. |
| `bottle_vendor.asm` | (Vanilla Hook) | Modifies the vanilla bottle vendor to handle selling milk. |
| `bug_net_kid.asm` | (Vanilla Hook) | Modifies the Sick Kid to grant the Pegasus Boots after playing the Song of Healing. |
| `deku_scrub.asm` | `Sprite_DekuScrubNPCs` | Manages various Deku Scrub NPCs, including one who gives the Deku Mask. |
| `eon_owl.asm` | `Sprite_EonOwl` | The owl that guides Link. Includes logic for both the Eon Owl and Kaepora Gaebora. |
| `eon_zora.asm` | (Part of `zora.asm`) | A friendly Zora NPC found in the Eon Abyss. |
| `eon_zora_elder.asm`| (Part of `zora.asm`) | The elder Zora in the Eon Abyss. |
| `farore.asm` | `Sprite_Farore` | The Oracle Farore, who appears in cutscenes and guides the player. |
| `followers.asm` | (Vanilla Hooks) | Contains logic for various follower characters like the Zora Baby and the Old Man. |
| `fortune_teller.asm`| (Vanilla Hook) | Modifies the fortune teller's dialogue to provide hints relevant to the hack's progression. |
| `goron.asm` | `Sprite_Goron` | Handles both the Kalyxo Goron who opens the mines and the Eon Gorons. |
| `hyrule_dream.asm` | (Part of `farore.asm`) | Logic for NPCs appearing in Link's dream sequences (Zelda, King, Soldier). |
| `impa.asm` | (Vanilla Hook) | Modifies Impa's behavior, particularly in setting spawn points. |
| `korok.asm` | `Sprite_Korok` | A friendly Korok NPC. |
| `maku_tree.asm` | `Sprite_MakuTree` | The Maku Tree, a key story NPC who provides a Heart Container. |
| `maple.asm` | (Part of `mermaid.asm`)| Maple the witch, who can send Link to dream worlds. |
| `mask_salesman.asm` | `Sprite_MaskSalesman` | The Happy Mask Salesman, who sells the Bunny Hood and Stone Mask. |
| `mermaid.asm` | `Sprite_Mermaid` | A friendly mermaid NPC. Also contains logic for Maple and the Librarian. |
| `piratian.asm` | `$0E` | A friendly pirate-like NPC that becomes aggressive if attacked. |
| `ranch_girl.asm` | (Vanilla Hook) | Modifies the chicken lady at the ranch to give the Ocarina. |
| `tingle.asm` | `$22` | Tingle, who sells dungeon maps to the player. |
| `vasu.asm` | `Sprite_Vasu` | Vasu, the jeweler who appraises magic rings. Also includes logic for Error. |
| `village_dog.asm` | `Sprite_VillageDog` | A friendly dog that interacts with the player. Includes logic for the Eon Dog. |
| `village_elder.asm` | (Part of `bean_vendor.asm`)| The village elder NPC. |
| `zora_princess.asm` | `Sprite_ZoraPrincess` | The Zora Princess, who grants the Zora Mask. |
| `zora.asm` | `Sprite_Zora` | A friendly Zora NPC. Also contains logic for the Zora Princess and Eon Zoras. |

## Detailed NPC Analysis

### `bean_vendor.asm` / `village_elder.asm`
- **Sprite ID:** `Sprite_BeanVendor`
- **Summary:** This file contains the logic for two NPCs. The primary is the Bean Vendor, who sells Magic Beans for 100 rupees. The second is the Village Elder.
- **Key Logic:**
    - **BeanVendor:** Initiates a dialogue on contact. If the player agrees to buy, it checks for sufficient rupees, deducts the cost, and spawns a collectible Magic Bean sprite.
    - **VillageElder:** Engages in dialogue and sets a progress flag (`OOSPROG`) after the first interaction.

### `bug_net_kid.asm`
- **Sprite ID:** (Hooks `SpritePrep_SickKid`)
- **Summary:** This modifies the vanilla "Sick Kid" NPC. Instead of giving the Bug Net, he gives the player the Pegasus Boots.
- **Key Logic:** The `SickKid_CheckForSongOfHealing` routine checks if the `SongFlag` is set. If it is, the `BugNetKid_GrantBugNet` routine is called, which uses `Link_ReceiveItem` to give the boots (`ITEMGET` ID `$4B`).

### `deku_scrub.asm`
- **Sprite ID:** `Sprite_DekuScrubNPCs`
- **Summary:** Manages several Deku Scrub NPCs, including the Deku Butler and Deku Princess. A key interaction involves a withered Deku Scrub who, after being healed with the Song of Healing, gives the player the Deku Mask.
- **Key Logic:**
    - The main state machine checks for the `SongFlag`.
    - If the song is played, it transitions through a dialogue sequence (`QuiereCuracion`, `DarMascara`).
    - Finally, in the `Regalo` state, it calls `Link_ReceiveItem` with item ID `$11` (Deku Mask) and sets a progress flag (`$7EF301`).

### `eon_owl.asm`
- **Sprite ID:** `Sprite_EonOwl`
- **Summary:** This is the guide owl, appearing in both the overworld (as Eon Owl) and the Hall of Secrets (as Kaepora Gaebora).
- **Key Logic:**
    - **Eon Owl:** In the overworld, it triggers introductory dialogue when the player gets close and then flies away.
    - **Kaepora Gaebora:** In the Hall of Secrets, it appears only after all 7 crystals are collected and before the player has the Song of Soaring. It offers to teach the player the song.

### `farore.asm` / `hyrule_dream.asm`
- **Sprite ID:** `Sprite_Farore`
- **Summary:** Handles the Oracle Farore and NPCs that appear in dream sequences.
- **Key Logic:**
    - **Farore:** Manages the introductory cutscene where she follows Link, sets the main story state (`$B6`), and changes the game state to post-pendants (`$7EF3C5 = 2`).
    - **Dream NPCs:** Contains simple display logic for Zelda, the King, and a soldier during the `MakuTree_HasMetLink` dream sequence.

### `followers.asm`
- **Sprite ID:** (Hooks vanilla follower system)
- **Summary:** Contains significant custom logic for follower characters, most notably the Zora Baby (Locksmith) and the Old Man.
- **Key Logic:**
    - **Zora Baby:**
        - Replaces the Locksmith sprite (`$39`).
        - Can be picked up and carried by Link.
        - When placed on a water gate switch, it triggers the switch.
        - Transitions from a follower to a standard sprite when on a star tile in a dungeon.
    - **Old Man:** Logic is modified to grant the Goldstar (Hookshot Lv2 upgrade) instead of the Magic Mirror.

### `vasu.asm`
- **Sprite ID:** `Sprite_Vasu`
- **Summary:** This is the ring jeweler, Vasu. He can appraise rings the player has found. The file also contains logic for the "I am Error" NPC.
- **Key Logic:**
    - Vasu's main loop presents a choice: "Appraise" or "Explain".
    - If "Appraise" is chosen, it checks if the player has any unappraised rings (`FOUNDRINGS`).
    - It charges 20 rupees (the first one is free) and transfers the bits from `FOUNDRINGS` to `MAGICRINGS`, making them usable.
    - The Error NPC appears as a subtype and gives the player a random ring when spoken to.
