# Testing Strategy

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: engineering
Related: [../adr/0005-manual-driven-development.md](../adr/0005-manual-driven-development.md),
[simulation-kernel.md](simulation-kernel.md), [../process/workflow.md](../process/workflow.md)

A simulation whose *selling point is truthfulness* needs tests that check truthfulness,
not just code coverage. Five distinctive test classes carry that load (3–7 below).

## Test taxonomy

### 1. Unit tests (`tests/<pkg>/`)
Plain pytest for kernel primitives, solvers, parsers, schema validation. Standard stuff;
fast; the bulk by count.

### 2. UI tests (`tests/presentation/`)
Textual pilot smoke tests (stations mount, annunciators render, command bar round-trips)
plus teletype golden transcripts. Deliberately thin: UI contains no logic worth deep
testing (architecture rule), so we test that wiring exists, not physics.

### 3. Invariant / property tests (`tests/invariants/`)
Hypothesis-driven, the physics conscience:

- **Conservation**: for arbitrary valid network configurations and step sequences —
  electrical power balance per bus, thermal energy conservation, fluid mass conservation,
  data-message causality. Tolerances documented per solver; violations are P0.
- **Tier consistency**: for parts declaring multiple fidelity tiers, L2 steady-state ==
  L1 equilibrium == L0 (within declared tolerance), across generated operating points.
- **Schema round-trip**: content → model → serialize → identical.

### 4. Determinism tests (`tests/determinism/`)
The replay oracle (see kernel spec):

- Same (seed, content, journal) → identical per-tick state hashes, twice in-process and
  across a process restart.
- Cross-platform hash agreement (CI matrix at M2+).
- **Perturbation independence**: adding an unrelated device/stream does not change
  another entity's random draws (guards the stream-naming law).
- Compression equivalence: 1× vs 1000× over the same journal → identical state at equal
  sim times.

### 5. Fault-scenario tests (`tests/casualties/`)
Each cataloged failure mode gets at least one scenario: inject fault F on TB-1 →
**assert symptoms via telemetry only** (test code importing raw state for assertions is
lint-blocked in this directory — the test experiences the fault exactly as a player
would). Asserts: expected annunciators fire, expected instrument deviations appear,
*and the documented FIM path terminates at the injected fault*. That last clause keeps
the FIM honest forever.

### 6. Manual-conformance tests (`tests/conformance/`) — the flagship
The procedure runner executes every executable procedure in `data/procedures/` headless
against the referenced ship state:

- SOM normal procedures must reach their documented end state (cold & dark → flight
  ready), with every step's expected indication satisfied.
- QRH abnormals run against their triggering fault: stabilization criteria must hold.
- FIM tasks run against each fault they claim to isolate: verdict must be correct.
- MEL (O)/(M) procedures must be executable in their deferral configurations.

**A manual page whose procedure fails is a build failure.** This is Manual-Driven
Development's enforcement arm (ADR-0005): the binder ships true or nothing ships.

### 7. Perf benchmarks (`tests/perf/`)
pytest-benchmark against kernel budgets (see kernel spec). Informational at M1, gating
at M2+ with explicit budget table in-repo. Runs on a pinned CI machine class; local
results advisory.

## Fixtures

- **TB-1 "Breadboard"**: minimal viable ship (1 battery, 2 buses, 1 PDU, 1 data bus,
  4 sensors, 1 pump/loop) — small enough that hand-computed physics appear in test
  comments as the expected values' provenance. Grows *very* reluctantly.
- **UEV Kestrel**: full playable ship; used by conformance and integration tests.
- Scenario files double as fixtures (same format players share — bug reports arrive as
  scenario + seed + journal, runnable verbatim).

## CI pipeline (every PR)

```
ruff check+format → mypy --strict → unit+invariant+determinism → content validate
→ manual generators diff-check → conformance → (perf, M2+) → docs build
```

Target: < 10 min. Conformance shards by manual chapter as the binder grows.

## Local developer loop

`make check` = lint + types + fast tests (< 60 s target). `make test-all` = the CI set.
Pre-commit hooks: ruff, content validation on changed files. Full commands in AGENTS.md.

## Bug reporting protocol (dev + eventually players)

A valid sim bug report = scenario file (or save) + seed + FDR journal + expected/actual.
`ultraspace replay --to-tick N` reproduces; `tools/replay_bisect.py` (M2) finds
divergence points. "Cannot reproduce" should be structurally impossible for
sub-presentation bugs; UI bugs get Textual pilot scripts instead.

## Coverage stance

Line coverage is reported, not gated (uninformative for sim truthfulness). The gates
that matter: every failure mode has a casualty test; every procedure conforms; every
solver has conservation + tier-consistency properties; determinism suite green. A
`tools/coverage_matrix.py` (M2) report cross-tabs failure modes × tests and manual
sections × conformance runs, and fails on uncovered *new* content.
