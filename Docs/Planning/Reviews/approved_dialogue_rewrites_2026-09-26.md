# Approved dialogue rewrites (2026-09-26)

Approved by scawful in the Claude story/design discussion session, 2026-09-26
("approve"). Style rule: `Docs/Planning/Status/decisions.org`, "Dialogue style:
people of Kalyxo first, race second".

These are vanilla-bank messages: they need a base-ROM write (`Roms/oos168.sfc`)
in the dialogue-audit write pass. Nothing has been written yet. Validate byte
length against the bank with z3ed before writing; both drafts are shorter than
the current text.

## 0x135 (309) - D4 Zora Temple maiden

Current ROM text (read with `z3ed message-read --rom Roms/oos168.sfc --id 0x135`):

```
[S:02][P:01][W:02][L], your actions here have[2]cast a hopeful light upon our[3]troubled waters. Thank you.[K][V]The Zora, throughout the ages,[V]have harnessed the mysteries[V]of time through hidden [K][V]technologies. The Ocarina you[V]wield, and even the Hookshot,[V]a tool of our invention,[K][V]signify our mastery over both[V]time and space. With these, [V]we navigated our vast domain[K][V]effortlessly. The Zora Mask,[V]and your aid too our princess, [V]speaks of a bond between[K][V]you and our kind[...][V]Yet, there's more to discover.[V]Hidden within the cascading[K][V]waters of our waterfalls is[V]another part of this temple, [V]untouched by Kydrog's evil[K][V]Another invention of the Zora[V]which should protect you on[V]your dangerous quest.[K][V]Once you leave this place, head[V]directly west and dive from[V]our highest cliff to find it.[K][V] [...] [...] [...] [...] [...][SFX:2D]
```

Approved text:

```
[S:02][P:01][W:02][L], your actions here have[2]cast a hopeful light upon our[3]troubled waters. Thank you.[K][V]For ages, the scholars of[V]this temple studied the[V]mysteries of time and space.[K][V]The Ocarina you wield, and[V]the Hookshot, our own[V]invention, are proof of it.[K][V]The Zora Mask, and your aid[V]to our princess, speak of a[V]bond between you and us[...][K][V]Yet, there's more to discover.[V]Hidden behind the waterfalls[V]lies another part of this[K][V]temple, untouched by Kydrog.[V]Another of our inventions[V]waits there to protect you.[K][V]When you leave, head west[V]and dive from our highest[V]cliff to find it.[K][V] [...] [...] [...] [...] [...][SFX:2D]
```

Lore note (scawful, 2026-09-26): the Ocarina was made by the temple's Zora
makers; the Ranch Girl owning one is fine ("ocarina made by the zora but some
girl has one nbd").

## 0x137 (311) - D6 Goron Mines maiden

Current ROM text:

```
[S:02][P:01][W:02][L], because of you, I am[2]finally freed from Kydrog's [3]evil forces. Thank you![K][V]These mines were once thriving[V]with Goron, but the instability[V]brought on by the Pirate King[K][V]crippled any hope of continued[V]business in these caves.[V][L], you must journey to[K][V]Dragon Ship, off the coast of[V]Kalyxo where Kydrog is hiding[...]
```

Approved text:

```
[S:02][P:01][W:02][L], because of you, I am[2]finally freed from Kydrog's [3]evil forces. Thank you![K][V]These mines once rang with[V]miners from across Kalyxo,[V]but the Pirate King's[K][V]tremors ended any hope of[V]work in these caves.[V][L], you must journey to[K][V]the Dragon Ship, off the[V]coast of Kalyxo, where[V]Kydrog is hiding[...]
```

Supersedes the id 311 entry in `Data/dialogue/maiden_upgrades_dialogue.json`
(agent-written "trade liaison between Goron and Zora ... before the mistrust";
conflicts with the style rule and with D6's place in the dungeon order). Do not
import that entry.

## Attract narration $1C0-$1C3 (expanded bank)

Approved by scawful 2026-09-26 ("approve text for now"; may be tweaked later).
Middle ground between scawful's original 0x112-0x115 and the 2026-09-24 agent
draft. These are expanded messages: edit `Data/dialogue/expanded_messages.json`
(entries 51-54, id = message - 0x18D), then `z3ed message-source-sync`
(dry-run, then `--write`), then build. Check line widths with
`z3ed message-doctor`. Card 5 is longer than the old dungeon-card budget
(about 3 lines + 1 scroll line in ~9 s): extend its `$64` timer in
`Dungeons/attract_scenes.asm` and verify in an emulator.

Scene context (decisions.org "Attract scene direction"): 1-2 storybook,
3 great hall full with Farore beside the Hylian commander, 4 soldiers arrest a
villager, 5 same hall empty with one knight, then the map zoom onto Tail Pond.

$1C0 (storybook, cards 1-2):

```
[SPD:00][C:07][S:03][W:02][IMG]Not long ago, the kingdom of[2]Hyrule was aided by a mythical[3]hero to protect the Triforce[...][WT:09][V]Far away, the island of[V]Kalyxo, home of Farore,[V]lived by its own ways.[WT:09][IMG][IMG][V]Its miners and river scholars[V]built a mirror to another[V]realm, the Eon Abyss.[WT:09][V]Its strange beauty drew[V]explorers in. Many never[V]came back[...][WT:09]
```

$1C1 (card 3, great hall):

```
[W:02][C:07][S:03][1]Word reached Hyrule of a[2]Golden Power beyond the[3]mirror. Its king sent[WT:05][V]soldiers to guard it.[WT:05]
```

$1C2 (card 4, escort):

```
[W:02][C:07][S:03][1]Roads and forts came with[2]them, and new laws. They[3]claimed it was to protect[WT:05][V]the island. Many called[V]it an invasion.[WT:05]
```

$1C3 (card 5, empty hall):

```
[W:02][C:07][S:03][1]But as years passed, the zeal[2]to protect waned into neglect.[3]The guardians grew complacent[...][WT:05][V]One knight kept watch alone.[WT:05][V]Now dark forces stir in the[V]Abyss, and the destiny of the[V]Oracle of Secrets draws near.[WT:05]
```

## Abyss guidance: $36, new early Owl line, $E6

Approved by scawful 2026-09-26 ("yes approve sounds good"). Plan context:
decisions.org "Abyss segment: fix direction before cutting content".
Directions come from map data (Origins entrance $76 on parent $40; sword area
$58 is one row south of Owl map $50); confirm "west" and "just south" in game.

### $36 (vanilla bank, base-ROM write)

Current:

```
[W:02][S:03]I sense your despair[...][2]Kydrog has cast you into the[3]Eon Abyss, a place where time[K][V]stands still. You must find the [V]Moon Pearl. It will protect you[V]against the dark magic here.[K][V]Without it, you will be unable[V]to defend yourself. Once you[V]have returned to Kalyxo, seek[K][V]out the Great Maku Tree.[V]He will know what to do next.[V]Good luck, [L][...]
```

Approved:

```
[W:02][S:03]I sense your despair[...][2]Kydrog has cast you into the[3]Eon Abyss, a place where time[K][V]stands still. You must find the [V]Moon Pearl. It will protect you[V]against the dark magic here.[K][V]It rests in the Shrine of[V]Origins, west of the great[V]pyramid. Once you have[K][V]returned to Kalyxo, seek out[V]the Great Maku Tree.[V]Good luck, [L][...]
```

### New: Owl first appearance (expanded bank; allocate an ID via message_registry.json)

Shown by the Eon Owl on the Abyss arrival area before the Pearl (placement to
be chosen by the RC leader; $E6 stays the post-Pearl line).

```
Hoo hoo! A stranger in[2]the Abyss? Your shape is[3]not your own here.[K][V]The Shrine of Origins[V]lies west of the pyramid.[V]Hoo hoo! Off you go![K]
```

### $E6 (vanilla bank, base-ROM write)

Changes: second-meeting opener; the "Forest of Dreams" fragment becomes a
sentence with a direction. Rest unchanged.

```
Hoo hoo! We meet again,[2][L].[K][V]This realm is a mirror,[V]a reflection of forgotten[V]dreams and shadowed paths.[K][V]Though you hold the Moon[V]Pearl, beware, for not all[V]is as it seems in the Abyss.[K][V]Deep in the Forest of Dreams,[V]just south of here, a sword[V]awaits you, a blade to cut[K][V]through the veil of deception.[V]But remember, young one,[V]even the sharpest blade[K][V]cannot sever all bonds.[V]Hoo hoo![K]
```
