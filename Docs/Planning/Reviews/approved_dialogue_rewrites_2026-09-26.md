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
