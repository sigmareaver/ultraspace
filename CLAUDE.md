# CLAUDE.md

Canonical agent instructions live in **[AGENTS.md](AGENTS.md)** — one source of truth
for all agents and humans. Read it first, then [docs/README.md](docs/README.md).

Claude-specific notes:

- Plan with your todo tool for any multi-step task; keep exactly one item in_progress.
- Prefer editing existing specs over spawning new documents; the docs index
  ([docs/README.md](docs/README.md)) must list every doc that exists.
- When a task touches design *and* code, do the docs delta in the same change set —
  the Definition of Done in [docs/process/workflow.md](docs/process/workflow.md) is
  the review standard, including for agent-authored PRs.
- Never mark work complete without running `make check` (and `make test` when models,
  content, or determinism-adjacent code changed).
