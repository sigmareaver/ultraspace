# Tech Stack

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: engineering
Related: [../adr/0001-language-and-ui.md](../adr/0001-language-and-ui.md),
[../adr/0004-units-policy.md](../adr/0004-units-policy.md)

## Decisions (rationale in ADRs)

| Concern | Choice | Notes |
|---|---|---|
| Language | Python ≥ 3.12 (dev on 3.14) | Iteration speed for a design-heavy sim; escape hatch documented below |
| Package/env | uv | Lockfile committed; `uv run` is the only blessed entry point |
| TUI | Textual | Primary client; `presentation/tui` only |
| Flat client | stdlib only | Teletype mode must run anywhere Python runs |
| Schemas/validation | pydantic v2 | Content boundary + snapshots only — **not** in hot sim loops (plain dataclasses/slots inside models) |
| Content format | YAML (PyYAML, safe loader) | Human-authored; JSON Lines for FDR streams |
| Tests | pytest + hypothesis | Property tests carry the conservation laws |
| Perf tests | pytest-benchmark | Informational M1, gating M2+ |
| Lint/format | ruff (lint+format) | One tool; config in pyproject |
| Types | mypy --strict | Whole `src/`, no per-module opt-outs without ADR |
| Docs build | mkdocs-material (M1) | Also builds the exportable in-game manual binder (HTML/PDF) |
| CI | GitHub Actions | lint → types → tests → validate content → determinism → (perf) |

## Dependency policy (deliberately austere)

Runtime dependencies require justification in PR description; the bar is "implements a
solved hard problem" (Textual, pydantic, PyYAML clear it). Current runtime set at M0:
**none** (kernel is stdlib-only). Adoption schedule:

| Dependency | Arrives | Trigger |
|---|---|---|
| pydantic, PyYAML | M1 | content pipeline |
| Textual | M1 | first TUI station |
| numpy | when a solver needs it | not before profiling shows it (bus nodal solves are small; pure-Python PLU may suffice for years) |
| networkx | probably never | our graphs are small and bespoke; write the 60 lines |

## The performance escape hatch (pre-committed, so it's not a panic)

Python will eventually strain against the depth ceiling (many L2 solves, big thermal
graphs, 1000× compression). The pre-agreed path, in order:

1. **Algorithmic**: better tiering/demotion, equilibrium caching, event-armed wake-ups
   (these are design tools, always first).
2. **CPython upgrades**: 3.14+ JIT improvements are free real estate; measure each bump.
3. **Targeted native**: port *individual solvers* (electrical nodal solve, thermal step)
   to Rust via PyO3 behind the existing Python interface + golden tests. The layering
   (networks/ isolated, deterministic, fully golden-tested) exists partly to make this
   surgical. Trigger: sustained failure of M2 perf budgets after (1) and (2).
4. Full-core rewrite: explicitly *not* a plan; if (3) covers >50% of tick time in Rust
   and we still miss budgets, write an ADR and think.

Determinism note: any native port must reproduce results bit-exactly (fixed-order
reductions, no fast-math) — golden state-hash tests are the acceptance gate.

## Supported platforms

Linux first-class (dev target), macOS and Windows Terminal supported at M2+ (Textual
carries most portability; CI matrix expands then). Terminal floor: 80×24, 256-color,
UTF-8; box-drawing degradation table maintained in ui-presentation spec.

## Repo conventions

- Src layout: `src/ultraspace/` (import-safe), tests in `tests/` mirroring package tree.
- Entry points: `ultraspace` CLI (`run`, `validate`, `replay`, `docs`, `selftest`).
- `tools/` for repo maintenance scripts (not shipped); `data/` for content (shipped).
- Line length 100; full config in `pyproject.toml` (single config file policy — no
  scattered dotfiles beyond `.gitignore`, CI, and pre-commit).
