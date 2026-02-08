# Lore + Infra Planning Handoff

Date: 2026-01-24
Scope: Story canon updates, map guidance infrastructure, and item-flow planning. This is a planning handoff (no ROM edits).

## Locked Decisions
- Mirror of Time: canonical source is **Impa in the Hall of Secrets** (grant logic TBD).
- Tail Pond map marker: set after **post‑D1 NPC hint** about the Mask Salesman (Village Elder for now).
- Song of Storms: **optional**, used for Blue Mail waterfall post‑D4; Windmill NPC requires **Ocarina only**.
- Titan's Mitt: **immediate post‑D6** reward.
- Pyramid icon should **not** appear until after D3.

## Draft/Untested Implementations
- Added MapIcon value: `!MapIcon_TailPond = $09` in `Core/sram.asm`.
- Added `DrawTailPondMarker` to `Overworld/world_map.asm` (approximate coords).
  - **TODO:** tune coordinates manually after a visual map pass.
- Village Elder now gives a post‑D1 hint and sets Tail Pond marker (untested):
  - Checks: D1 complete + D2 not complete + ElderGuideStage stage < 1.
  - Message: `0x177` (Mask Shop Hint).
  - Effects: `MapIcon = Tail Pond`, `ElderGuideStage` low nibble = 1.
  - File: `Sprites/NPCs/village_elder.asm` (marked UNTESTED).

## Planning Docs Added/Updated
- `Docs/Planning/map_icon_guidance_notes.md` (verbatim guidance from Codex history).
- `Docs/Planning/item_flow_balance_check.md` (captures optional Storms + Tail Pond marker plan).
- `Docs/Planning/Story_Event_Graph.md` (adds EV-016 Mirror grant plan + EV-017 Tail Pond marker).
- `Docs/World/Guides/QuestFlow.md` (notes Impa grants Mirror; Elder hint added to D1.5 flow).
- `Docs/Planning/item_audit.md` (Mirror note updated).
- `oracle.org` (TODOs for Impa grant, Tail Pond marker wiring, manual coordinate tuning).

## Open Decisions / Next Questions
- **Impa grant logic:** where to wire the Mirror give in `Sprites/NPCs/impa.asm` and what gating condition should trigger it.
- **MapIcon staging:** when to set D3, midgame group (D4‑D6), D7, and Fortress.
- **ImpaGuideStage usage:** confirm when to display the Hall of Secrets icon for check‑ins.
- **Tail Pond marker coordinates:** manual tuning needed (LLM shouldn't adjust visuals).

## Important Constraints
- **Do not move ROM items** with tooling yet (Mirror relocation is design‑only).
- **Do not adjust song scrolling logic** (leave the Ocarina menu flow intact).
- Visual marker tuning should be done manually.

## Files to Review Next Session
- `Sprites/NPCs/impa.asm` (Mirror grant hook point).
- `Overworld/world_map.asm` (Tail Pond marker coords).
- `Core/sram.asm` (MapIcon constants).
- `Docs/Planning/map_icon_guidance_notes.md`
- `Docs/Planning/item_flow_balance_check.md`
- `oracle.org`

