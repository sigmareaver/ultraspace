# Roadmap

Status: Living document · Last updated: 2026-09-12 · Owner: process
Related: [workflow.md](workflow.md), [../vision.md](../vision.md)

Milestones are defined by **acceptance vignettes** (playable proofs), not feature lists.
Each vignette is eventually encoded as a scenario + conformance suite, so "milestone
done" is a command you can run. Dates are deliberately absent; order is not.

## M0 — Foundations ✅ (this repo state)

Deterministic kernel (clock, scheduler, RNG hub, event log) with tests; full design/
engineering/process documentation; CI skeleton; project scaffolding.

**Acceptance:** `make check` green; `ultraspace selftest` runs N deterministic ticks
and prints a stable state digest; docs index complete.

## M1 — First Light (EPS vertical slice) ✅ (closed 2026-07-18)

The whole concept proven on one chapter: **cold & dark TB-1/Kestrel to powered, by
manual, in the TUI.**

Progress 2026-07-14: spec ✅ · content pipeline ✅ · electrical L0/L1 ✅ · instruments
chain ✅ · SCL v1 ✅ · procedure runner ✅ · SOM Ch 24 + conformance ✅ · teletype ✅ ·
WDM generators + style guide + no-drift gate ✅ · import/units lint tools ✅ ·
Textual TUI v1 (SYS/EPS + DOCS + LOG stations, annunciator row, command bar) ✅ ·
Kestrel blueprint (EPS subset: BUS B, split batteries, cross-tie) + SOM 24-30-03/04 +
conformance ✅ · manual binder HTML export (`make binder`) ✅ · vignette playtest
(maintainer solo, [playtests/2026-07-14-m1-vignette.md](playtests/2026-07-14-m1-vignette.md);
found + fixed the undocumented tie-reset recovery) ✅ · TUI polish (2026-07-17):
clickable station-key footer + semantic color contract (palette.py; mapping in the
style guide) ✅ · stranger-with-the-binder playtest (2026-07-18, manual-naive human,
zero issues, [playtests/2026-07-18-stranger-with-the-binder.md](playtests/2026-07-18-stranger-with-the-binder.md)) ✅.

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

Progress 2026-07-18: data network increment 1 ✅ — DB-A on TB-1 + Kestrel
(BC/RT, timeout/FAILED accounting, health telemetry, analyzer v1, `DATA BUS A
DEGRADED`; spec [../design/systems/ata-42-data.md](../design/systems/ata-42-data.md);
SOM 42-00-00/42-30-01 + conformance + casualty suites).
Progress 2026-07-19: fault model v1 ✅ — injected stuck-dominant RT (the U4
fault) jams the bus; latch-up clears on power removal; procedure-runner
branching (on_pass/on_fail_goto + verdict END); FIM 42-11 executable with
per-suspect verdict-path conformance (a wrong FIM edit fails CI); RT 5 added
(the one-dark vs all-dark diagnostic split).
Progress 2026-07-20: harness depth ✅ — the bus grows a body per MIL-STD-1553
culture: trunk/couplers/stubs, 78 ohm termination, transformer-coupled
containment (a stub short cannot kill the bus; a trunk short kills it; a
break partitions contiguously). DMM ohms probe points (de-energize
interlock), repair verbs, five-mode fault matrix, WDM 42 harness sheets,
FIM 42-12 executable with per-fault verdict-path conformance.

Review + playtest 2026-09-12: the increment-3 harness shipped with coupler
faults unwalked — the tree convicted innocent parts and died on a refusal for
three of them — plus a lint-red HEAD, an assembly-order crash on validated
content, and a No-God-View leak in the `repair` refusal. All fixed
(66eb23d..51a92bd); conformance now derives its fault set from the blueprint so
the coverage gap cannot recur. Note:
[playtests/2026-09-12-m2-harness-tree.md](playtests/2026-09-12-m2-harness-tree.md).
Progress 2026-09-12: sensor transport ✅ — remote transducers ride their RT
(`carried_by`), so a dark terminal freezes the readings it carries while the
measured load keeps drawing: the U4 step-3 symptom at last, displays wrong
with the cabin fine. Telemetry gains one staleness horizon shared by the
panel, the printed line (`? STALE`) and the monitors — a stale source takes
its caution quiet, which makes SOM 42-00-00 §6's promise true in the sim.
FIM 42-14 (executable) routes a frozen indication: panel-wired instruments
first, so a dead bus is never mistaken for a data fault. Note:
[playtests/2026-09-12-m2-sensor-transport.md](playtests/2026-09-12-m2-sensor-transport.md).
Progress 2026-09-13: stress model v1 ✅ — faults stop being authored. Parts
declare hazards (`rate_per_h`, `radiation`, `needs_rail`), the ship carries a
particle environment, and each (device, mode) pair draws its own stream once
per tick *unconditionally*, so a crew action can never shift another device's
future. Scenarios become content (`scenario/1`: a flux timeline and any
scripted faults) played by a new `world` layer, and `testing.inject_fault`
now delegates to the same ship-layer door — an emergent casualty and an
authored one are indistinguishable except in the FDR. The SEU monitor
(`data.seu read`) and `SEU HAZARD` give the crew minutes of warning; SOM
42-30-02 (executable) trades a shed terminal for exposure, and the essential
terminal that cannot be shed latches up anyway on a severe event — under an
already-lit lamp. Note:
[playtests/2026-09-13-m2-particle-event.md](playtests/2026-09-13-m2-particle-event.md).
Progress 2026-09-13: annunciator discipline + QRH v1 ✅ — the panel learns to
rank. Annunciations carry a severity (`warning`/`caution`/`advisory`, spelled
in words on every text surface because the teletype has no color), the ship
grows two master lights instead of one, and every lamp carries a second bit:
**acknowledged**. `sys.annunciator ack` says *I have seen this* and never
clears anything, so the masters can flash again for the next thing; recall
ranks severity, then new-before-seen, then blueprint order — never recency,
because the newest problem is usually a consequence of the worst one. Graded
annunciation closes the increment-5 finding: `DATA BUS A FAILED` (warning)
sits above `DATA BUS A DEGRADED` (caution) on the same measurement, so a
casualty under a lamp the crew lit themselves announces itself. One
`DataBus.state_word()` now feeds the analyzer and the grading, because a panel
and a display that disagree teach the crew to trust neither. New spec
[../design/systems/ata-31-indicating.md](../design/systems/ata-31-indicating.md);
QRH is the third executable manual (00-00 using-this-book, 42-01 DATA BUS A
FAILED); lamp test is step 1 of both cold & dark checklists. Note:
[playtests/2026-09-13-m2-annunciator-discipline.md](playtests/2026-09-13-m2-annunciator-discipline.md).
Progress 2026-09-13: MAINT v1 ✅ — a verdict finally has somewhere to go. Every
fitted box is a serialized unit (`<P/N>/<NNNN>`, derived from the blueprint so
stocking a part costs one content line), carrying position, powered hours and a
fitted/removed/installed history readable with `records` at any device address.
`swap lru` lands as two verbs, `remove` and `install`, because the interesting
state is the position with nothing in it: a removed board draws no current,
answers no poll, and cannot jam — so pulling a babbling terminal really does
cure its bus, at the cost of the function. The bus table is *not* told; a
controller cannot see an empty rack and still reads NO RESPONSE, and the only
record of the hole is the ship's own stores sheet (`maint read`). Stores are
finite and refusals cite the generated IPC sheet, which is built from the same
blueprint the registry serializes. MAINT is the fourth executable manual (00-00
using-this-book, 42-110-001 terminal replacement, closing with the SOM 42-30-01
functional test); FIM 42-12's board verdicts now *end* the tree and hand off,
because wiring is repaired where you stand and a box is an LRU. The U4
acceptance vignette runs end to end as a casualty test — flux, emergent
latch-up, QRH, FIM, swap, functional test — with nothing read that an
instrument did not say. Note:
[playtests/2026-09-13-m2-maint-swap.md](playtests/2026-09-13-m2-maint-swap.md).

Progress 2026-09-14: increment 8, the friction increment ✅ — five playtest
findings from three sessions, paid off together because DB-B would have made
two of them materially worse. A timed wait is now a *watch*: one primitive
(`interaction/watch.py`) behind both the console's `wait` and the runner's wait
step, ending the moment a warning goes new and reporting what is left; cautions
do not interrupt, nor does a lamp already lit, and a step may opt out
(`hold_through_warning`) where stopping is the wrong act. The analyzer gained
`zero --confirm`, FDR-recorded with the totals it discards, so SOM 42-30-01's
"errors 0" close-out is reachable after a casualty and now means *clean since
somebody looked*, with the time printed beside it. `data read` gained
per-terminal lines annotating a silent terminal `SHED (cb.a2 open)` or
`NOT FITTED (position open since MET …)` from the ship's own observable
knowledge — the BC's table stays pure, and a *bare* NO RESPONSE became the line
that carries information. Procedures gained `targets`: MAINT 42-110-001 is one
card, printed for RT 12, executed by conformance at both terminals. And
`tools/check_manual_steps.py` joins `make check` — it found real drift the day
it was written (FIM 42-11 printed a three-command feed cycle as one numbered
line). Note:
[playtests/2026-09-14-m2-friction.md](playtests/2026-09-14-m2-friction.md).

- Data network (DB-A/B, RT/BC, message schedules, bus analyzer tool); thermal loop v1
  (enough to make electronics care about heat); L2 forensic tier for PDU boards
  (netlists, test points, DMM probing); intermittents and condition-triggered
  hazards (the stress model's v2 factors: thermal, duty, wear).
- FIM Ch 24/42 with executable isolation tasks; QRH 24-01 and 31-01 (the executable
  priority page); generated QRH index; MEL v1 (defer DB-A!).
- `sys annunciator recall` is not a verb, though ATA 31 and QRH 42-01 both teach the
  word — the panel answers to `read` (playtest finding, 2026-09-14).
- An interrupted wait must be resumable as one act (`wait --resume`), not by retyping
  the remainder the client just printed (playtest finding, 2026-09-14).
- The watch covers `wait_s` steps only: SOM 42-30-02 holds with an expectation poll,
  so a warning during its monitor step does not interrupt it (playtest finding,
  2026-09-14).
- `records` reaches only addressed positions, but the IPC issues a serial to every
  fitted unit — the battery's nameplate is in the catalog and unreadable on the ship.
- MAINT station UI (the verbs and the stores sheet shipped 2026-09-13), LOG station
  (FDR review v1) — and with LOG, a notebook write verb, which closes both the
  "note the flux" and the "why was this board pulled" findings.
- Device power dependencies: annunciator panel as a powered device (a dark panel at
  cold & dark is the honest "alarm reset" — playtest finding, 2026-07-14 follow-up).
- The canonical U4 latch-up story (simulation-depth.md) fully playable.
- Perf budgets begin gating; replay bisect tool; casualty test suite per failure mode.

**Acceptance vignette:** the U4 story — from `DATA BUS A DEGRADED` annunciator to
board A2 swap and functional test, navigated via FIM alone; casualty tests cover every
shipped failure mode; a deliberately wrong FIM edit fails CI.
Status 2026-09-13: the vignette walks end to end on TB-1 and is held there by
`tests/casualties/test_u4_vignette.py`. What acceptance still wants is breadth —
DB-B failover and the MEL deferral that make the story a *choice* rather than a
single path, and the thermal loop that gives the stress model its second factor.

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
