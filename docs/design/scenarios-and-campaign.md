# Scenarios & Campaign

Status: Draft v0.1 · Last updated: 2026-07-14 · Owner: design
Related: [game-overview.md](game-overview.md), [tech-levels.md](tech-levels.md),
[../engineering/data-model.md](../engineering/data-model.md)

Two play modes over one sim: **Scenarios** (authored situations, the training and
benchmark layer) and **Campaign** (persistent ship/career, the long game). Scenarios ship
first (M1); campaign assembles from proven pieces (M5+).

## Scenarios

A scenario spec (data file) defines: ship + configuration + wear state, environment,
initial faults (or fault schedule), crew roster/state, comms world state, goals, and
debrief criteria. Because the sim is deterministic under seed, a scenario is exactly
reproducible — the same artifact serves as: tutorial, challenge content, regression test,
bug report, and community-shared war story (share the file + seed).

### Scenario classes

| Class | Example | Purpose |
|---|---|---|
| **Type rating** | "EPS familiarization: cold & dark to flight ready" | Teach a chapter; the interactive manual |
| **Casualty drill** | "Intermittent DB-A during approach" | The core loop, concentrated |
| **Checkride** | "Shakedown cruise" (M4 flagship) | Integration test for player *and* codebase |
| **Incident recreation** | Load any FDR segment as a scenario | Post-mortem learning; community content |
| **Sandbox** | Free config, fault injection console (godmode namespace) | Player experimentation, content dev |

Debrief screen after every scenario: objective outcomes, FDR timeline of key events,
procedure adherence notes (which steps skipped/reordered), damage/nonconformance delta.
Tone: flight instructor, not report card — always cites manual sections to study.

## Campaign (v1 shape, M5+)

The fantasy: **a working ship earning its keep at the edge of the charted volume, run by
a professional crew and one increasingly annotated binder.**

- **Structure:** contract-driven free play in one star system (v1): cargo legs, surveys,
  salvage claims, tech recovery jobs. Contracts are generated against the traffic/economy
  sim's actual state (a station short on water ice posts hauling contracts) — light
  simulation, heavy legibility; this is not a 4X.
- **Progression = capability + knowledge:** money buys parts/manuals/crew-hours; salvage
  yields TL2–TL4 hardware (with the docs problem); your notebook, crew skills, and
  nonconformance history *are* the character sheet. No player XP anywhere.
- **The TL ratchet:** contracts deeper in the volume pay better and need better
  hardware; better hardware is less knowable; less knowable hardware makes casualties
  scarier. The campaign's difficulty curve is self-inflicted, one salvaged artifact at
  a time.
- **Ship loss:** not save-death. Survivors (and the notebook — it's on your person) roll
  into an insurance/inquiry sequence (your FDR gets reviewed; your nonconformance log
  gets *read aloud*), then a lesser ship. Losing the Kestrel should feel like a divorce,
  not a game over screen.

## Content authoring model

Scenarios and campaign events are data (`data/scenarios/`), validated in CI, hot-loadable
in dev mode. Community scenario sharing is an explicit 1.0 feature; the format is
documented and versioned from day one (schema discipline, see data-model).

## Failure tempo & fairness (campaign tuning)

- Ambient failure tempo per failure-and-repair tuning targets; scenario-injected faults
  are additive, flagged in the FDR as `scheduled` (dev/debrief visibility only — the
  player just experiences weather).
- Fairness law: campaign fault scheduling may weight *where* (stressed, worn, jury-rigged
  equipment) but never *when it hurts most* dramatically. No director that waits for
  docking to break your radio; drama emerges from honest coincidence. (This is a real
  differentiator vs. scripted survival games and must survive tuning pressure.)

## Open questions

- OQ-SC-1: Multiple start ships (TL0 trainer vs TL0/1 Kestrel) at 1.0? (Lean: Kestrel
  only, trainer as scenario ship.)
- OQ-SC-2: Economy depth — fixed price boards vs. simulated flows? (Lean: simulated
  scarcities with fixed price bands; decide at M5.)
- OQ-SC-3: Time scale — campaign legs measured in days or weeks of sim time? Affects
  maintenance interval design heavily. (Decide with M4 shakedown data.)
