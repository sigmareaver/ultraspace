# Simulation Kernel Specification

Status: Draft v0.2 (M0 partially implemented) · Last updated: 2026-07-14 · Owner: engineering
Related: [architecture.md](architecture.md), [../adr/0002-determinism.md](../adr/0002-determinism.md)

The kernel is the smallest layer: time, scheduling, randomness, and the event log. It
contains zero game content and imports stdlib only.

## Time

- **Base tick:** 100 ms of sim time (`TICK_US = 100_000`). All sim time is **integer
  microseconds** (`SimTime = int`). Floats never represent absolute time (drift-free by
  construction; float durations allowed at model level for local integration only).
- `SimClock`: monotonic tick counter + epoch (mission start UTC). Provides `now_us`,
  `tick_index`, formatted mission-elapsed/UTC strings for UI.
- **Wall-clock independence:** model code cannot read OS time (lint-banned). The runner
  maps wall time → tick cadence (1× = 10 ticks/s), and **time compression** multiplies
  ticks per wall second up to 1000×, with auto-drop to 1× on configured event classes
  (annunciator raised, radio addressed to player, threshold crossing). dt never changes;
  compression is *more ticks*, so physics and determinism are identical at any speed.

## Scheduling

- **Rate groups:** tasks register at divisors of the base rate: `EVERY_TICK` (10 Hz),
  `RG_1HZ`, `RG_0_1HZ`, plus `ON_DEMAND` (L2 forensic solves, event-armed).
- **Deterministic order:** within a rate group, execution order is registration order;
  registration order derives from ship blueprint traversal (stable, content-defined).
  Iterating unordered collections into task lists is forbidden (no set/dict-order
  nondeterminism — lint + review checklist).
- **Phases per tick** (fixed sequence): `commands → networks → devices → faults →
  instruments → annunciators → world → telemetry/FDR flush`. A device reads network
  state from phase N-consistent views; no mid-phase mutation visibility.
- **Overrun policy:** if a tick exceeds budget, compression auto-downshifts;
  at 1×, the sim *slows below real time* rather than skipping ticks (a study sim tells
  the truth slowly rather than lying quickly). Overruns are counted in perf telemetry.

## Randomness

- `RngHub(master_seed)` → `stream(name) -> random.Random`, seeded by
  `blake2b(master_seed || name)`. Stable across platforms/Python versions (unlike
  `hash()`; blake2b is stdlib).
- **Stream naming convention:** `domain/entity/purpose`, e.g.
  `fault/pdu2.a2.u4/latchup`, `world/traffic/meridian/departures`, `crew/ramos/error`.
- Laws: no stream sharing across entities (fault draws for one device never perturb
  another's sequence — adding a device must not reshuffle the world); no `random.*`
  module-level calls anywhere in `src/` (lint rule); streams created lazily but named
  deterministically from content IDs.

## Event log / FDR

- Append-only, per-tick-ordered records: `(tick, seq, source, kind, payload)` with
  monotonic `(tick, seq)`. Everything notable is an event: SCL accepted/refused,
  annunciator transitions, fault manifestations, network trips, radio utterances,
  procedure steps, snapshot markers.
- **The FDR is simultaneously:** the debug log, the replay input (paired with command
  journal), the save-game delta stream, the in-game FDR review feature, and the bug
  report format. One artifact, five customers — this is why it lives in the kernel.
- Serialization: JSON Lines (compressed) v1; schema versioned; readers must tolerate
  unknown event kinds (forward compat for content packs).

## Snapshot & replay

- **Snapshot:** full serialization of model state at a tick boundary (pydantic-dumped
  state structs, versioned). Saves = snapshot + FDR tail. Autosnapshot cadence
  configurable (default 5 min sim time).
- **Replay:** `snapshot + SCL journal → identical state hash at every subsequent tick`.
  The **state hash** (blake2b over canonical state serialization, excluding
  perf/debug fields) is the determinism oracle used by CI (see testing.md).
- Replay divergence is a P0 bug with a dedicated triage tool
  (`tools/replay_bisect.py`, M2): bisects the journal to the first divergent tick and
  diffs state trees.

## Performance budgets (M2 gate, mid-range laptop, single core)

| Phase | Budget @10 Hz, 5k devices |
|---|---|
| networks (all L0/L1) | ≤ 40 ms/s (40%) |
| devices + faults | ≤ 20 ms/s |
| instruments/annunciators/telemetry | ≤ 15 ms/s |
| world | ≤ 10 ms/s |
| headroom | ≥ 15 ms/s |

Benchmarks in CI (`tests/perf/`, pytest-benchmark, informational until M2, gating after).
1000× compression target: ≥ 300× actual on TB-1-class ships (batched L0 stepping with
event-armed wake-ups — design in networks docs at M1).

## Implemented at M0 (see `src/ultraspace/kernel/`)

`SimClock` (integer time, tick arithmetic), `RngHub` (named blake2b streams),
`Scheduler` (rate groups, phases, deterministic order), `EventLog` (ordered append,
seq discipline). Snapshot/replay lands with first stateful models (M1).
