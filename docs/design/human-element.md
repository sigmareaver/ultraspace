# The Human Element

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: design
Related: [game-overview.md](game-overview.md), [command-language.md](command-language.md),
[manuals-as-gameplay.md](manuals-as-gameplay.md)

Pillar: **Space is crewed.** Two subsystems: the **radio world** (traffic control, other
vessels, stations) and the **crew** (the people inside your hull). Both run on the same
cultural physics: procedure, phraseology, closed-loop communication, and trust.

## Part 1 — The radio world (ATC in space)

### Structure

- **Controlled volumes** around stations/gates (approach, dock control, ground/bay ops)
  with published frequencies and procedures (in the CPM, per-station pages like real
  airport charts).
- **Uncontrolled space**: advisory frequencies, traffic self-announcing (CTAF analog).
- **Long range**: light-lag turns dialogue into directed message traffic (telegram
  gameplay: compose well, because round trips are minutes). Local ops are effectively
  real-time; the transition is physical (distance), not a mode switch.

### Dialogue model

Strict phraseology with a defined grammar. The player composes calls either by typing
free text (parsed against the expected-intent grammar with tolerance) or via the comms
station's prompt-assembly UI (which emits the same text — same rule as SCL/panels).

```
YOU:  "Meridian Approach, UEV Kestrel, with information BRAVO, request docking, bay four."
APP:  "Kestrel, Meridian Approach, cleared corridor three to holding fix MIKE,
       maintain closure under five meters per second, report MIKE."
YOU:  "Cleared corridor three to MIKE, closure under five, will report MIKE, Kestrel."
```

- **Readback enforcement:** safety-relevant items must be read back correctly.
  Controllers correct errors ("negative, corridor THREE") with patience that varies by
  workload and personality. Persistent sloppiness → delays, violations on record.
- **Information broadcasts** (lettered ALPHA, BRAVO...) carry station config: active
  corridors, bay closures, local hazards, traffic load — reading them matters.
- **Emergencies:** MAYDAY/PAN-PAN get priority handling, corridor clearing, and
  paperwork afterward (an incident report the player actually writes, feeding
  reputation). Declaring early is rewarded, mirroring real culture.

### Controllers and traffic as simulation

- Controllers have workload (traffic count), shift fatigue, and personality parameters
  (strictness, patience). Overloaded controllers batch you, miss calls, snap.
- NPC vessels fly persistent schedules with their own (coarse) system states; their
  emergencies preempt your clearances — the world audibly does not revolve around you.
  Party-line realism: you hear everyone on frequency; monitoring it is gameplay.
- Determinism: NPC decisions draw from named RNG streams; radio world replays under seed.

### Violations & reputation

Recorded breaches (blown readback on safety item, corridor deviation, unauthorized bay
entry) accumulate per jurisdiction: consequences from a talking-to, to mandatory
inspection (they *will* find your nonconformance log), to denied clearances. Reputation
is jurisdiction-scoped, not global.

## Part 2 — The crew

### Crew members

Persistent characters with: role qualifications (pilot/engineer/ops/medic), per-chapter
skill levels (Ch 24 EPS ≠ Ch 42 avionics), fatigue/circadian state, and **trust** (in
you, from history: your orders' quality, your jury-rigs, outcomes).

### Closed-loop orders (the core crew mechanic)

Orders use procedure culture — the same grammar as everything else:

```
YOU:    "Ramos, execute QRH E-3, aft coolant loop, report completion."
RAMOS:  "QRH E-3 on the aft loop, Ramos."          ← readback
...
RAMOS:  "Bridge, Ramos. E-3 complete, loop B stable, flow 82%, one caution: pump P-202
         current 10% over placard. Logged."         ← report
```

- Crew execute **whole procedures** (SOM/QRH/FIM tasks) autonomously; execution quality
  (speed, error rate, initiative on ambiguity) derives from skill, fatigue, trust, and
  whether they physically hold the manual (a crew member without the doc works from
  memory: skill-gated).
- **Skill vs. player knowledge:** the game must stay winnable by a knowledgeable player
  with a green crew (you do it yourself, slowly) and by a knowledgeable crew with a
  green player (order the right procedure by name — the manual's table of contents is
  the player's minimum literacy).
- Errors are honest simulation: a tired engineer skips a step (the FDR shows it); a
  low-trust crew member quietly double-checks your riskier orders (slower, safer).

### Fatigue, watchkeeping, and morale

Watch schedules are a real planning surface (who's awake for the burn?). Morale is
driven by legible causes (workload, casualties survived, port calls, your competence),
not a hidden mood bar: the crew *tells* you, in words, in character.

### What crew are not (v1 scope fences)

No relationship drama subsystem, no dialogue trees about feelings, no crew combat. The
emotional register is *The Martian*/*Apollo 13*: professionals under pressure. Depth of
characterization comes from voice in dialogue templates and RD/notebook writing.

## Implementation notes

- All dialogue is template+grammar driven, deterministic, and testable. Structured
  intents underneath; rendered text on top. An LLM layer is explicitly **out of core
  scope** (revisit post-1.0 as optional garnish; determinism and testability rule core).
- Phraseology grammar and station pages live in data (`data/comms/`, `data/manuals/cpm/`);
  the CPM is generated from the same grammar the parser uses — the manual literally
  documents the parser. One source of truth, same as WDM/netlists.
- Radio traffic runs at L0 fidelity when unobserved (schedule outcomes), L1 when on your
  frequency (utterance-level). Same fidelity philosophy as everything else.

## Acceptance vignette (M3 target)

Player departs Meridian with a MEL-deferred DB-A (single data bus): Dock Control asks for
souls and status per policy; mid-corridor, an NPC ore hauler declares PAN-PAN and
approach re-sequences everyone (player must hold at a fix, actually flying the hold via
autopilot modes); player misses a readback item under load and gets corrected; on
frequency handoff, the next controller already has their strip ("Kestrel, radar contact,
cleared to depart the zone, single-bus ops acknowledged, safe voyage"). Nothing in the
vignette is scripted; all emerges from traffic sim + phraseology grammar + player state.
