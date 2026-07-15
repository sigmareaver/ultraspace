# ADR-0001: Python + Textual over a headless core

Status: Accepted
Date: 2026-07-14
Deciders: project maintainer + founding agent session

## Context

The game is a text-driven, systems-heavy simulation whose cost center is *design
iteration* (models, content, manuals), not rendering. The user-facing brief names
Textual and Asciimatics as candidate presentation layers and allows a flat format.
The sim must reach circuit-board depth via multi-fidelity modeling, which is an
algorithmic/architectural problem more than a raw-throughput one. Team is small with
heavy agent assistance; iteration speed and testability dominate.

## Decision

- **Python ≥ 3.12** for the entire application at 1.0 scope.
- **Textual** for the primary TUI client.
- A **strictly headless simulation core**: presentation layers (TUI and a stdlib-only
  teletype/flat client) consume only telemetry + SCL. No sim logic in any UI layer.

## Consequences

- Fast iteration on models/content; the agent-assisted workflow (read-modify-test
  loops) is dramatically cheaper in Python.
- Textual provides layout, focus, testing (pilot), and potential web deployment free.
- We accept a performance ceiling and pre-commit to an escape hatch: algorithmic
  tiering first, then targeted Rust/PyO3 ports of individual solvers behind golden
  tests (see tech-stack.md). The headless-core + layering decision is partly *for*
  this: solvers are surgically replaceable.
- Determinism requires discipline Python won't enforce (hygiene lints, review rules).

## Alternatives considered

- **Rust + ratatui**: best runtime perf and determinism-by-culture; rejected for
  iteration cost on a design-unstable project — we'd pay Rust's rigidity precisely
  during the phase (design discovery) where it hurts most.
- **Asciimatics**: lighter than Textual but lower-level (no widget/layout system);
  we'd rebuild half of Textual badly.
- **C#/.NET (Terminal.Gui)**: solid, but ecosystem fit for our tooling (pytest,
  hypothesis, agents' fluency) favors Python.
- **Godot/graphical**: out of scope per vision non-goals.

## Revisit triggers

- M2 perf budgets missed after algorithmic + CPython-upgrade remedies (→ execute the
  PyO3 escape hatch, not a rewrite).
- Textual project abandonment or a breaking-change cadence we can't absorb (teletype
  client + headless core cap the blast radius by design).
