# AGENTS.md (Compact)

Purpose: high-signal operating rules only.

Core Rules
1. Clarify goals, constraints, and done criteria before major edits.
2. Prefer the smallest working change over architecture churn.
3. Read local `README.md` and nearby docs before coding.
4. Touch only task-related files.
5. Keep hygiene high: no dead code or commented-out leftovers.
6. Run the fastest relevant verification command before finishing.
7. If checks cannot run, report exactly why and residual risk.
8. Ask before destructive actions (`rm`, force-push, history rewrite).

Delivery Contract
- Report what changed.
- Report what was verified.
- Report known gaps or follow-ups.

Reference Material
- Detailed historical guidance: `.context/knowledge/agent-reference.md`.
- Project docs remain the source of truth for architecture and workflows.
