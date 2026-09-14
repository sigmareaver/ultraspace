# ULTRASPACE Documentation Index

Start here: [vision.md](vision.md) — premise, pillars, non-goals.
Terminology: [glossary.md](glossary.md) — canonical vocabulary for docs, code, and content.

## Design (`docs/design/`)

| Doc | Contents |
|---|---|
| [game-overview.md](design/game-overview.md) | Player role, nested core loops, difficulty model, session shape |
| [simulation-depth.md](design/simulation-depth.md) | Containment hierarchy, networks, fidelity tiers, conservation laws, the canonical U4 story |
| [ship-systems.md](design/ship-systems.md) | ATA-style chapter catalog, per-system spec template, cross-system laws |
| [tech-levels.md](design/tech-levels.md) | TL0–TL4 definitions, gameplay matrix, integration friction rules |
| [failure-and-repair.md](design/failure-and-repair.md) | Fault taxonomy, stress model, diagnosis tools, repair verbs, consequence bookkeeping |
| [manuals-as-gameplay.md](design/manuals-as-gameplay.md) | The document corpus, knowledge progression, the "requires a manual" bar |
| [human-element.md](design/human-element.md) | ATC-style radio world, phraseology, crew, closed-loop orders |
| [command-language.md](design/command-language.md) | SCL grammar, safety semantics, scripts/checklists, journal |
| [ui-presentation.md](design/ui-presentation.md) | TUI stations, rendering language, teletype mode, accessibility |
| [scenarios-and-campaign.md](design/scenarios-and-campaign.md) | Scenario classes, campaign shape, fairness law |

### Per-system specs (`docs/design/systems/`)

Template in ship-systems.md; one per ATA chapter, written before the code it governs.

| Doc | Contents |
|---|---|
| [ata-24-eps.md](design/systems/ata-24-eps.md) | Electrical power: composition, solver tiers, instruments, annunciators, EPS failure modes (M1) |
| [ata-31-indicating.md](design/systems/ata-31-indicating.md) | Indicating & recording: annunciation severity, master warning/caution, new-vs-acknowledged, QRH v1 (M2) |
| [ata-42-data.md](design/systems/ata-42-data.md) | Data network: bus model, harness topology, located faults, DMM isolation, procedure set (M2) |

## Engineering (`docs/engineering/`)

| Doc | Contents |
|---|---|
| [architecture.md](engineering/architecture.md) | Layering, loops, No-God-View boundary, Iron Laws |
| [simulation-kernel.md](engineering/simulation-kernel.md) | Tick/time, scheduling phases, RNG streams, FDR, snapshot/replay, perf budgets |
| [data-model.md](engineering/data-model.md) | Content tree, schemas (part/ship/procedure/scenario), identity rules, generators |
| [tech-stack.md](engineering/tech-stack.md) | Toolchain, dependency policy, performance escape hatch |
| [testing.md](engineering/testing.md) | Test taxonomy incl. invariants, determinism, casualty, manual-conformance |
| [coding-standards.md](engineering/coding-standards.md) | Units policy, determinism hygiene, state discipline, naming |

## Process (`docs/process/`)

| Doc | Contents |
|---|---|
| [workflow.md](process/workflow.md) | The feature cycle (Manual-Driven Development), DoD, playtest protocol, agent collaboration |
| [roadmap.md](process/roadmap.md) | Milestones M0–M6 with acceptance vignettes and standing risks |
| [playtests/](process/playtests/TEMPLATE.md) | Weekly playtest notes (template; dated notes alongside it) |

## Decisions (`docs/adr/`)

[ADR index and template](adr/README.md) — 0001 language/UI, 0002 determinism,
0003 content format, 0004 units, 0005 manual-driven development, 0006 diegetic
displays.

## Doc conventions

- Every doc carries a status line (`Draft vX.Y · Last updated · Owner`) and a Related
  header. Statuses: Draft → Stable → (Superseded/Retired). Living documents (glossary,
  roadmap, this index) never freeze.
- Specs change via PR alongside the code/content they govern (workflow.md step 7).
- Decisions with alternatives → ADR, never buried in a spec revision.
- In-game manual content is **not** in `docs/` — it is game content, in `data/manuals/`.
