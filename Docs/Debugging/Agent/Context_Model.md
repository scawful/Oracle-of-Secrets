# Oracle Agent Context Model

**Status:** Active  
**Last Reviewed:** 2026-02-22  
**Scope:** Oracle-of-Secrets agent workflows (Claude, Codex, Gemini, others)

## Purpose

Define shared context ownership and conflict resolution so agents do not drift when updating Oracle status, blockers, and plans.

## Context Roots

| Layer | Path | Audience |
|------|------|----------|
| Repo source-of-truth | `~/src/hobby/oracle-of-secrets/` | All agents |
| Shared AFS context | `~/.context/projects/oracle-of-secrets/` | All agents |
| Claude-local memory | `~/.claude/projects/-Users-scawful-src-hobby-oracle-of-secrets/memory/MEMORY.md` | Primarily Claude (optional for others) |

## Ownership and Priority

When two sources disagree, resolve in this order:

1. **Code + runtime evidence** in repo (`Core/`, `Sprites/`, `Dungeons/`, tests, regression artifacts)
2. **Repo docs/plans** in `Docs/`
3. **Shared AFS context** in `~/.context/projects/oracle-of-secrets/`
4. **Agent-local memory** in `~/.claude/.../MEMORY.md`

## Canonical Files (Shared)

- Current priorities and blocker ordering: `scratchpad/agent_handoff.md`
- Live bug investigations: `scratchpad/active_investigations.md`
- Persistent debt/risk list: `memory/technical_debt.md`
- Concept router: `CONTEXT_INDEX.md`

## Agent-Local Memory Policy

- `~/.claude/.../MEMORY.md` is allowed to store useful tactical notes.
- It is **not** canonical for shared project status.
- Facts discovered there must be promoted into shared `.context` files (and repo docs when relevant) before treating them as cross-agent truth.

## Update Protocol

1. Verify fact from repo files or runtime evidence.
2. Update shared `.context` files first (handoff/investigations/debt).
3. Update repo docs/plans when behavior or scope changed.
4. Optionally mirror summaries in agent-local memory.
5. Add explicit date and evidence path for major state changes.

## Dialogue Bundle Contract (Oracle + yaze)

- `id` means **index within bank**, not absolute Oracle message ID.
- `bank` must be correct: `vanilla` or `expanded`.
- For expanded absolute IDs (example: `0x1D5`), convert before import:  
  `expanded_index = absolute_id - 0x18D`
- Validate first:  
  `z3ed message-import-bundle --file <bundle.json> --strict`

Persistence rules:
- `expanded` messages must be committed in `Core/message.asm` for durable rebuild behavior.
- `vanilla` messages can use `z3ed ... --apply` as part of the base-ROM workflow.

`z3ed ... --apply` against patched output ROMs is non-durable across `build_rom.sh` runs unless source ASM is updated.
