# Architecture

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: engineering
Related: [simulation-kernel.md](simulation-kernel.md), [data-model.md](data-model.md),
[../design/simulation-depth.md](../design/simulation-depth.md)

## Layering (strict dependency direction, top depends on bottom)

```
┌───────────────────────────────────────────────────────────────┐
│ presentation/   TUI (Textual) · teletype client               │  no sim imports;
├───────────────────────────────────────────────────────────────┤  telemetry+SCL only
│ interaction/    SCL parser/dispatcher · procedure runner      │
├───────────────────────────────────────────────────────────────┤
│ world/          traffic & comms sim · stations · scenario     │
│                 director · crew agents                        │
├───────────────────────────────────────────────────────────────┤
│ ship/           blueprint assembly · devices · instrumentation│
│                 & annunciators · maintenance state            │
├───────────────────────────────────────────────────────────────┤
│ networks/       electrical · thermal · fluid · data ·         │
│                 structure solvers (graphs + tier managers)    │
├───────────────────────────────────────────────────────────────┤
│ kernel/         clock · scheduler · rng hub · event log/FDR   │
│                 snapshot/replay                               │
├───────────────────────────────────────────────────────────────┤
│ content/        schemas (pydantic) · loaders · validators ·   │
│                 generators (manual tables from data)          │
└───────────────────────────────────────────────────────────────┘
```

Import rules (CI-enforced by lint config, `tools/check_imports.py`):

1. `kernel` imports stdlib only.
2. `networks` → `kernel`, `content` only. `ship` → those + `networks`. Etc. upward.
3. **`presentation` may import only `interaction` (SCL) and telemetry types.** Game
   logic in a widget is a review-blocking defect.
4. `content` is import-leaf for schemas (anyone may read schemas; schemas import nothing
   of ours).

## The two loops

- **Sim loop** (headless, owns truth): fixed-tick kernel advancing all systems. Runs in
  its own thread (or sole thread in headless/CI mode). Interface to the outside: an
  inbound SCL command queue and outbound telemetry/event snapshots (immutable message
  passing only — no shared mutable state with UI, no locks in model code).
- **UI loop**: Textual's asyncio loop, renders latest telemetry, submits SCL. UI dropping
  frames must never stall the sim; sim overrun policy is defined in simulation-kernel.

Headless-first is contractual: `ultraspace run --headless --script x.scl` is a supported
product surface (CI, scenario debugging, teletype server), not a test hack.

## Telemetry & the No God View boundary

The sim exposes exactly two read surfaces:

1. **Telemetry** — instrument-mediated values with provenance/age (what displays render).
2. **FDR stream** — the event log (commands, annunciators, faults *as manifested*).

Raw model state is accessible only to `networks/ship` internals and to the test suite
via an explicit `ultraspace.testing` API (used by invariant tests; forbidden import in
`presentation`, `world`, `interaction` — the game cannot cheat even if a dev is lazy,
because the import gate fails CI).

## Determinism boundary

Everything below `presentation` is deterministic under (seed, content hash, SCL journal).
The UI is *not* required to be deterministic (render timing, completion popups). Replay =
kernel + journal; the UI just watches. See ADR-0002.

## Concurrency policy

- Model code: single-threaded by contract, no async, no wall-clock reads (`time.time()`
  banned in `kernel/networks/ship/world` — lint rule; the sim clock is injected).
- Parallelism, if ever needed, happens *inside* a solver step with deterministic
  reduction order — a performance measure, never an architecture (see tech-stack
  escalation path).

## Error philosophy

- **In-fiction failures are data**, never exceptions (a dead regulator is a state).
- Exceptions crossing a layer boundary are bugs; the sim tick has a top-level guard that
  snapshots FDR + state on crash ("black box even for us").
- Content errors (bad YAML, schema violation, dangling part number) fail at *load time*
  with file/line context — never at tick time. Validation is a build step, not a runtime
  surprise.

## Package layout (target state, grows by milestone)

```
src/ultraspace/
  kernel/        # M0 ✅  clock, scheduler, rng, events
  content/       # M1     schemas, loader, validation, generators
  networks/      # M1–M2  electrical, thermal, data, fluid, structure
  ship/          # M1     blueprint, devices, instruments, annunciators
  interaction/   # M1     scl, procedures
  world/         # M3     comms, traffic, stations, crew, scenarios
  presentation/  # M1     tui/, teletype/
  testing/       # M1     state-inspection API for tests, fault injection console
```

## Cross-cutting invariants (the Iron Laws, engineering form)

1. Fixed tick, integer time, seeded named RNG streams — no other randomness/time source.
2. Conservation checks on every network solve (test + optional runtime assert mode).
3. Tier consistency: L2↔L1↔L0 agreement within documented tolerance.
4. Instruments-only player data path; `ultraspace.testing` is the only bypass.
5. All content schema'd + versioned; generated manual sections never hand-edited.
6. Every UI affordance emits SCL; the FDR journal replays to identical state hash.

These laws also appear in AGENTS.md (agent-operational form) and testing.md
(enforcement form). Change requires an ADR.
