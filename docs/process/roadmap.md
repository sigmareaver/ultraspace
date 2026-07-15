# Roadmap

Status: Living document · Last updated: 2026-07-14 · Owner: process
Related: [workflow.md](workflow.md), [../vision.md](../vision.md)

Milestones are defined by **acceptance vignettes** (playable proofs), not feature lists.
Each vignette is eventually encoded as a scenario + conformance suite, so "milestone
done" is a command you can run. Dates are deliberately absent; order is not.

## M0 — Foundations ✅ (this repo state)

Deterministic kernel (clock, scheduler, RNG hub, event log) with tests; full design/
engineering/process documentation; CI skeleton; project scaffolding.

**Acceptance:** `make check` green; `ultraspace selftest` runs N deterministic ticks
and prints a stable state digest; docs index complete.

## M1 — First Light (EPS vertical slice) — FEATURE-COMPLETE (one gate open)

The whole concept proven on one chapter: **cold & dark TB-1/Kestrel to powered, by
manual, in the TUI.**

Progress 2026-07-14: spec ✅ · content pipeline ✅ · electrical L0/L1 ✅ · instruments
chain ✅ · SCL v1 ✅ · procedure runner ✅ · SOM Ch 24 + conformance ✅ · teletype ✅ ·
WDM generators + style guide + no-drift gate ✅ · import/units lint tools ✅ ·
Textual TUI v1 (SYS/EPS + DOCS + LOG stations, annunciator row, command bar) ✅ ·
Kestrel blueprint (EPS subset: BUS B, split batteries, cross-tie) + SOM 24-30-03/04 +
conformance ✅ · manual binder HTML export (`make binder`) ✅ · vignette playtest
(maintainer solo, [playtests/2026-07-14-m1-vignette.md](playtests/2026-07-14-m1-vignette.md);
found + fixed the undocumented tie-reset recovery) ✅.
**Open before closing M1:** the true stranger-with-the-binder session (the vignette
demands a manual-naive human); TUI polish riding along — clickable station-key footer,
finish the semantic color contract (glyph-redundant state colors, mapping in the
style guide).

- Content pipeline (schemas, loader, validation, generators) with EPS parts + Kestrel
  blueprint (EPS subset).
- Electrical network L0/L1 (sources, buses, ties, breakers, PDUs, precharge physics);
  instruments-as-devices minimal chain (transducer → data stub → display).
- SCL v1 (parse, dispatch, journal, refusals with manual refs); procedure runner v1.
- TUI v1: SYS/EPS station + DOCS reader + annunciator row + command bar; teletype mode.
- Manual binder v1: SOM Ch 24 (theory + cold-start 24-30-01), WDM Ch 24 (generated
  tables + first ASCII schematic), IPC Ch 24 stub. Style guide for diagrams.
- First conformance tests (cold start), first invariants (electrical conservation),
  determinism suite operating on real content.

**Acceptance vignette:** a person who has never seen the code, given the TUI and the
SOM, brings BUS A online (hitting the precharge interlock at least once and being
taught by the refusal message); the conformance suite proves the same procedure
headlessly; pulling breaker 24-C7 mid-procedure produces honest downstream symptoms.

## M2 — Symptoms & Suspects (fault isolation update)

The casualty loop end-to-end on EPS + Data + minimal Thermal.

- Data network (DB-A/B, RT/BC, message schedules, bus analyzer tool); thermal loop v1
  (enough to make electronics care about heat); L2 forensic tier for PDU boards
  (netlists, test points, DMM probing); stress model + fault scheduling; intermittents.
- FIM Ch 24/42 with executable isolation tasks; QRH v1; MEL v1 (defer DB-A!).
- MAINT station (records, spares, swap verbs), LOG station (FDR review v1).
- Device power dependencies: annunciator panel as a powered device (a dark panel at
  cold & dark is the honest "alarm reset" — playtest finding, 2026-07-14 follow-up).
- The canonical U4 latch-up story (simulation-depth.md) fully playable.
- Perf budgets begin gating; replay bisect tool; casualty test suite per failure mode.

**Acceptance vignette:** the U4 story — from `DATA BUS A DEGRADED` annunciator to
board A2 swap and functional test, navigated via FIM alone; casualty tests cover every
shipped failure mode; a deliberately wrong FIM edit fails CI.

## M3 — Voices on the Loop (human element slice)

- Comms physical layer (radios, channels, link budget v1) + phraseology grammar +
  CPM (generated from the same grammar); Meridian Station traffic sim (controllers
  with workload/personality, NPC schedules); clearances, readbacks, violations.
- Crew v1: 2 NPC crew, closed-loop orders, procedure delegation, fatigue.
- Docking & mechanisms v1 (corridors, capture, umbilicals) — enough to give traffic
  control something real to control.
- COMM station; the human-element acceptance vignette from human-element.md.

**Acceptance:** that vignette, emergent (PAN-PAN preemption from NPC state, not
script); order "Ramos, run QRH E-3" executes correctly and shows up in the FDR with
Ramos's fingerprints; phraseology errors get corrected by controllers per CPM rules.

## M4 — Shakedown Cruise (whole-ship alpha)

- ECLSS, propulsion (fission-thermal + RCS), propellant, nav/burn execution, remaining
  thermal; time compression with event auto-drop at full scale; save/load complete.
- Full Kestrel manual binder rev A (all chapters shipped so far), print/HTML export.
- The **Shakedown Cruise** checkride scenario: depart Meridian, transit (compression,
  scheduled maintenance, one ambient casualty statistically due), burn, arrive, dock.

**Acceptance:** shakedown completable start-to-finish in TUI and teletype; a full-cruise
FDR replays bit-identical; binder exports and a human successfully uses the printed QRH
during a drill.

## M5 — Patchwork Ships (tech level expansion)

- TL2 module (sealed unit + recert procedures + acquisition-gated docs), first TL3
  artifact (boundary contract, research dossier, adapter chain, notebook-as-manual
  workflow), integration friction rules (certs, MEL interactions, station attitudes).
- Campaign skeleton: contracts, spares/manual acquisition economy v1, nonconformance
  audits, ship-loss inquiry sequence.

**Acceptance:** acquire a TL3 artifact with no manual, characterize it by experiment
(notebook entries with attached measurements), integrate via adapter onto BUS B,
survive the consequences; get audited and have your jury-rigs read back to you.

## M6 — The Long Watch (campaign & 1.0 shape)

Archeotech (rituals, refinement), 2–3 alien design grammars, campaign depth (crew
careers, reputation arcs, insurance), scenario sharing, difficulty presets validated,
performance/polish, accessibility audit against ui-presentation commitments.

**Acceptance:** a stranger plays a 10-hour campaign from the binder alone and produces
a war story we didn't script — and the FDR proves we didn't.

## Standing risks (watched every milestone)

| Risk | Mitigation |
|---|---|
| Depth without play (simulationism trap) | Weekly playtests; every milestone has a *fun* acceptance vignette, not a physics demo |
| Python perf ceiling | Budgets gate at M2; escape hatch pre-planned (tech-stack.md) |
| Manual authoring cost | Generators for all mechanical content; MDD makes manuals pay rent as tests; scope chapters ruthlessly |
| Scope (it's a whole ship) | TB-1 discipline: every mechanism proven minimal first; chapters land one at a time |
| Determinism erosion | Suite runs on every PR; violations are P0; hygiene lints |
