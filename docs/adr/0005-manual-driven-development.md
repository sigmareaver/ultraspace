# ADR-0005: Manual-Driven Development

Status: Accepted
Date: 2026-07-14
Deciders: project maintainer + founding agent session

## Context

The game's premise is that operating the ship *actively requires* the manual, and its
success criteria include manuals good enough to print and bind. Two failure modes
threaten this: (a) manuals drifting from simulation behavior (instant credibility
death — the player's trust in the binder is the product), and (b) manuals written last,
as documentation, instead of first, as design (producing systems that can't be
explained, violating the knowledge-is-progression pillar).

Meanwhile, the sim needs specification-grade tests, and specs need to be executable to
stay honest. These are the same problem.

## Decision

**The in-game manual is the specification, written before implementation and executed
as the test suite.**

1. **Manual first**: gameplay-visible features begin with their manual content — SOM
   theory + procedures, FIM tasks, QRH checklists (workflow.md step 2). If the manual
   page can't be written, the design is rejected as incoherent ("two-manual rule").
2. **Procedures are structured data** (procedure/1 schema) rendered into manual pages
   AND executed by one procedure-runner engine with three clients: player-interactive,
   crew-AI, and CI-headless.
3. **Conformance gate**: every executable procedure must pass headlessly against its
   referenced ship state on every PR. SOM startups must reach documented end states;
   FIM tasks must isolate the faults they claim; QRH checklists must stabilize their
   casualties; MEL deferrals must be operable. A failing manual is a failing build.
4. **Mechanical truth is generated** (ADR-0003): pinouts, breaker tables, limits —
   the manual cannot even *state* mechanical facts that disagree with the sim.
5. **Symmetric blame**: when sim and manual disagree, design intent decides which is
   wrong; either way it's a P1 (`manual-wrong` label class in workflow.md).

## Consequences

- The binder ships true, permanently, by construction — the core product promise
  becomes a CI property instead of an editorial aspiration.
- Design incoherence surfaces at the cheapest possible moment (writing, not coding).
- Tests come nearly free with content: authoring a procedure *is* writing its test.
- The crew-delegation feature and CI share one engine — crew AI correctness is
  continuously exercised by the build.
- Costs: procedure schema must stay expressive enough for real documents (revisit
  trigger in ADR-0003); manual authoring becomes a critical path (mitigated by
  generators and by it being, literally, the game's content); prose sections (theory
  of operation) remain human-verified — MDD covers procedures and mechanical facts,
  playtests cover pedagogy (the ≥80%/≤20% manual-bar measurements).

## Alternatives considered

- **Docs-last** (industry default): guarantees drift; rejected as existentially
  incompatible with the premise.
- **Tests-first, docs separate**: duplicates the same knowledge in two artifacts that
  then diverge from each other; rejected — merge the artifacts instead.
- **Wiki-style living docs without CI teeth**: how every game wiki rots; rejected.

## Revisit triggers

- Procedure schema expressiveness ceiling (see ADR-0003 trigger) — the DSL evolution
  must preserve the render+execute duality.
- Conformance suite runtime > 10 CI minutes (→ shard by chapter, cache ship states).
- Evidence from playtests that manual-first is producing pedagogically worse prose
  than retrospective writing would (no current reason to believe this; watch for it).
