# Agent Entrypoint (Short)

**Read this page first. If you need more detail, open `Docs/Agent/Quickstart.md`.**

For all AI agents working on **Oracle of Secrets** (`~/src/hobby/oracle-of-secrets`):

1) **Quickstart:** Follow `Docs/Agent/Quickstart.md` (5-step loop: build → launch Mesen2 → preflight → repro → debug).
2) **Architecture rules:** `Docs/General/DevelopmentGuidelines.md`.
3) **Stability guardrails:** `Docs/STABILITY.md` (color math clears, SPC timeouts, input hygiene).
4) **Tooling reference (when stuck):** `Docs/Tooling/AgentWorkflow.md`.

### Minimal Preflight
- `python3 scripts/mesen2_client.py run-state`
- `python3 scripts/mesen2_client.py diagnostics --json`
- `python3 scripts/mesen2_client.py smart-save 5 --label "<bug>"` + `lib-save "<bug>"`
- Input safety: CLI inputs resume if paused; only pass `--allow-paused` intentionally.
