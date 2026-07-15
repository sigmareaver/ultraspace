# Coding Standards

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: engineering
Related: [architecture.md](architecture.md), [tech-stack.md](tech-stack.md)

Mechanical enforcement over prose: if a rule matters, it has a ruff rule, mypy setting,
custom lint (`tools/check_*.py`), or CI diff-check. This doc explains the *why*; the
tooling is the law. Deviations need an inline `# std-dev:` comment with justification.

## Baseline

- Python ≥ 3.12 features allowed (match, type parameter syntax, etc.). Dev on 3.14.
- `ruff` lint+format, line length 100. `mypy --strict` across `src/` — no untyped defs,
  no implicit Any. `tests/` may relax specific strictness (fixtures) but not `# type: ignore`
  without error codes.
- Public API of every package = `__all__` in `__init__.py`; cross-package imports go
  through package roots (import-layering checked by `tools/check_imports.py`).

## Units & quantities (ADR-0004 summary)

- SI base units everywhere in model code. **Every dimensioned identifier carries a unit
  suffix**: `bus_voltage_v`, `flow_kg_s`, `temp_k`, `pressure_pa`, `energy_j`,
  `power_w`, `duration_s` (float, local math) / `duration_us` (int, kernel time).
- No `pint`/units libraries in the sim loop (perf + determinism); the convention is
  enforced by reviewer checklist + a heuristic lint (`tools/check_units.py`, M1: flags
  dimensioned-looking names lacking suffixes).
- Temperatures in kelvin, always (`_k`). Celsius exists only in presentation formatting.
- Angles in radians (`_rad`); degrees only at presentation/content boundaries.
- Content files use explicit unit keys (`rating: {v: 32, a: 60}` — schema-defined units,
  documented in schema docs), converted to SI at load.

## Determinism hygiene (the do-not list)

Banned in `kernel/ networks/ ship/ world/ interaction/` (lint-enforced):

- `time.time()`, `datetime.now()`, `perf_counter` (except kernel perf telemetry, marked).
- Module-level `random.*`; any RNG not obtained from `RngHub.stream(name)`.
- Iterating `set`s / dict views into any ordered model structure or task list
  (sort first, or use lists; `dict` iteration is fine for lookup, not for ordering
  guarantees written into state).
- `float` equality (`==`) — use tolerances; state hashing uses canonical serialization,
  not float comparison.
- Wall-clock-dependent defaults in dataclasses/pydantic models.
- `async` anywhere below `presentation/`.

## State & mutation discipline

- Sim state lives in plain `@dataclass(slots=True)` structures owned by their layer;
  pydantic only at content/snapshot boundaries (convert at the edge).
- No global mutable state. Everything reachable from the `Sim` root object; tests build
  small roots.
- Cross-phase communication via the event queue / phase outputs, never by reaching into
  another device mid-phase (see kernel phase model).
- In-fiction failure is **state, not exceptions** (a `Fault` record on a block), and
  never `None`-punning: absence of data is an explicit `NoReport(reason, age_us)` value
  at instrument boundaries (this is what renders as `--- NO DATA`).

## Naming

- Canonical vocabulary from `docs/glossary.md` (LRU, SRU, BITE, annunciator...) — no
  synonyms in identifiers (`Device` not `Component`/`Unit` mixing; `Block` for netlist
  elements).
- Content IDs: kebab-case (`pdu-2`); Python: PEP 8; SCL addresses: dotted lowercase
  (`eps.bus.a.tie`); ATA chapter prefixes in manual/test identifiers (`test_ata24_...`).
- RNG stream names follow `domain/entity/purpose` (kernel spec) — grep-ability is the
  point.

## Errors, logging, comments

- Exceptions = programmer bugs (see architecture error philosophy). Never catch broadly
  inside model code; the tick guard owns crash capture.
- Two channels, never confused: **FDR events** (sim truth, shipped, replayable) vs
  `logging` (dev diagnostics, never load-bearing, stripped of gameplay meaning).
- Comments explain *physics and why*, not what: a solver step cites its equation or
  manual section (`# SOM 24-30-01 note 2: precharge limits tie inrush (C·dV/dt)`).
  Hand-computed expected values in tests cite their arithmetic.
- `TODO(name, issue#)` format; no issueless TODOs survive PR review.

## File & function scale

Soft ceilings, reviewer-enforced: modules ≤ ~400 lines, functions ≤ ~60, one class per
concept not per file-organizing habit. Solvers may exceed with a header comment mapping
the algorithm's structure.

## PR checklist (mirrors Definition of Done in workflow.md)

Types/lint/tests green · new physics has invariants · new failure modes have casualty
tests · new procedures conform · content validates · generated tables regenerated ·
docs/spec deltas included · determinism suite untouched-or-justified · no new deps
without justification · glossary respected.
