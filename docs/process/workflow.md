# Development Workflow

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: process
Related: [roadmap.md](roadmap.md), [../adr/README.md](../adr/README.md),
[../engineering/testing.md](../engineering/testing.md)

The workflow is designed around this project's unusual property: **the in-game manual is
a specification we can execute.** Everything else is disciplined normalcy.

## The feature cycle (any gameplay-visible work)

```
1. SPEC      Design doc delta (docs/design/...) or new system doc from the template
             in ship-systems.md. For decisions with alternatives: ADR.
2. MANUAL    Write/update the in-game manual content FIRST: SOM section, procedure
             spec, FIM entries, WDM data as applicable. If you cannot write the manual
             page, the design isn't done — go back to 1. ("Two-manual rule": explain
             it to the player or it doesn't exist.)
3. TESTS     Encode the spec: conformance test from the procedure (usually free —
             the procedure IS the test), casualty tests for new failure modes,
             invariants for new physics.
4. BUILD     Implement models/content until conformance + casualty + invariant
             tests pass. Keep `make check` green continuously.
5. VERIFY    `make test-all` (includes determinism suite). Perf budgets if touched.
6. PLAY      Actually play the slice (TUI and teletype). File friction notes as
             issues; playability observations go in the PR description.
7. SYNC      Doc deltas land in the same PR: spec status bumps, glossary additions,
             roadmap checkbox, CHANGELOG entry. Docs lagging code is a review blocker.
```

Steps 2–3 before 4 is **Manual-Driven Development** (ADR-0005). For pure-engineering
work (kernel, tooling), step 2 is replaced by the engineering spec delta.

## Iteration structure

- **Trunk-based**: short-lived branches (`feat/ata24-precharge`, `fix/replay-divergence`)
  off `main`; `main` is always green and always playable (`make run-tb1` boots TB-1).
- **Milestones over sprints** (solo/small-team + agent-friendly): the roadmap defines
  acceptance criteria; work between milestones is pulled from the milestone's issue
  list in priority order. No ceremony, but the **weekly playtest** is sacred: every
  Friday, play the current build for 30+ min, write a playtest note in
  `docs/process/playtests/YYYY-MM-DD.md` (template there). Design truth comes from
  playing, not from specs admiring themselves.
- **Conventional commits** (`feat(ata24): bus precharge interlock`, `docs(fim): ...`,
  `content(kestrel): ...`). Scope = ATA chapter or package name. Enables changelog
  generation and per-chapter history (`git log --grep 'ata24'`).

### Commit discipline (project rule)

**Every feature, fix, and change/tweak is committed as its own commit** — including
docs-only and content-only changes. Rationale: the history is our regression bisection
tool and our creative-direction ledger; when a sim behavior regresses or a design
direction is reversed, `git log`/`git bisect` must be able to isolate exactly what
changed and why.

1. One logical change per commit; unrelated changes never share a commit.
2. Commit at green: `make check` passes before committing (determinism suite too when
   models/content changed). Broken-state checkpoints go on branches, never `main`.
3. The commit body says *why*, not just what — especially for design reversals
   (reference the spec/ADR delta: "per ADR-0006", "reverses part of tech-levels.md §…").
4. Spec deltas travel in the same commit as the code/content they govern (workflow
   step 7); a commit that changes behavior but not its spec is incomplete.
5. Golden/determinism value updates (state hashes, pinned digests) are always called
   out explicitly in the commit body with their justification.

## Definition of Done (PR gate — the checklist reviewers actually walk)

1. CI green (lint, types, tests, content validation, conformance, determinism).
2. Spec/docs delta in the same PR; statuses bumped; ADR if a decision was made.
3. New failure modes → casualty tests; new physics → invariants; new procedures →
   conformance entries; new content → validates + generated tables regenerated.
4. Playability note (what does this feel like at the terminal? one paragraph minimum
   for player-visible changes).
5. FDR/replay compatibility statement (breaks replays? → save-major bump + migration
   note; the determinism suite will have flagged this anyway).
6. No new runtime deps without justification; no glossary violations.

## Bug workflow

Sub-presentation bugs require a repro triple (scenario/save + seed + journal) — the
FDR-first culture (testing.md) makes "can't reproduce" structurally impossible. Label
by chapter (`ata24`) + class (`physics`, `determinism`, `content`, `ui`, `manual-wrong`).
`manual-wrong` is a special class: **if the sim and the manual disagree, the one that's
wrong is decided by design intent, and whichever is wrong is a P1** — the binder's
credibility is the product.

## Playtest protocol (the design feedback loop)

- Weekly note (above) + milestone-end structured playtest against the milestone's
  acceptance vignette (e.g., M1's cold-and-dark test with a manual-only participant).
- The "manual bar" measurements (manuals-as-gameplay.md) are collected here: fresh
  player + manual ≥ 80% / no manual ≤ 20% success targets, measured with real humans
  when available, honestly noted when not.
- Every playtest produces: friction list (issues), surprise list (things the sim did
  that delighted/confused — the emergent-behavior ledger), and a keep/kill call on any
  experimental feature flags.

## Agent collaboration model

This project is developed with heavy AI-agent involvement. Ground rules:

- **AGENTS.md is the operational contract** (commands, laws, layout); this doc is the
  human-level process. Agents follow the same feature cycle — a PR from an agent that
  skips MANUAL/TESTS phases fails review like anyone else's.
- Specs and ADRs are written to be executable-by-agent: acceptance criteria phrased as
  observable checks, file paths explicit, "done" always verifiable by command.
- Long agent sessions should update TODO/issue state as they go; session summaries land
  in PR descriptions, not in lost scrollback.
- Design authority: pillars and Iron Laws change only via ADR reviewed by the human
  maintainer. Agents propose, humans ratify.

## Cadence summary

| Rhythm | Ritual |
|---|---|
| Continuous | `make check` green; docs move with code |
| Per PR | Definition of Done walk |
| Weekly | Friday playtest + note |
| Per milestone | Acceptance vignette playtest; roadmap retro (what did the sim teach us?); spec status sweep |
