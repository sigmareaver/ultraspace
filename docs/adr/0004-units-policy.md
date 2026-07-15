# ADR-0004: SI floats with unit-suffixed names; no units library in the sim loop

Status: Accepted
Date: 2026-07-14
Deciders: project maintainer + founding agent session

## Context

A physics-adjacent sim with electrical, thermal, and fluid domains multiplies unit-error
risk (the Mars Climate Orbiter failure class). Full dimensional-analysis libraries
(pint, astropy.units) eliminate that class but cost 10–100× per arithmetic op and
introduce wrapper types that complicate serialization, hashing, and determinism.
The sim loop runs at 10 Hz over thousands of devices in Python — wrapper overhead lands
directly on the perf budget.

## Decision

1. **SI base units for every quantity in model code.** Kelvin, pascals, watts, radians;
   no Celsius/PSI/degrees inside the sim, ever.
2. **Every dimensioned identifier carries its unit as a suffix**: `bus_voltage_v`,
   `heat_w`, `temp_k`, `flow_kg_s`, `duration_us` (int, kernel time) / `duration_s`
   (float, local math). Unsuffixed dimensioned names are review-blocking.
3. **No units library in `src/ultraspace/`** (allowed in offline tools/tests as
   cross-checks). A heuristic lint (`tools/check_units.py`, M1) flags suspicious names.
4. **Content files declare units in schema-defined keys** (`rating: {v: 32, a: 60}`),
   converted to SI at load — authors write natural units, the sim never sees them.
5. **SCL requires explicit units** on dimensioned arguments (design doc rule), so the
   player-facing layer carries the same discipline.
6. Presentation formats for humans (°C, %, kN) at the last moment, tagged with source
   unit in the formatter (single conversion site per unit pair).

## Consequences

- Unit errors remain *possible* (this is the accepted cost) but are pushed to review
  visibility, boundary conversions are centralized, and hot loops stay native-float
  fast, hashable, and serializable.
- Test strategy compensates: conservation invariants catch most dimensional errors
  dynamically (an erroneous unit factor of 1000 violates power balance loudly);
  hand-computed expected values in tests cite arithmetic in comments.

## Alternatives considered

- **pint everywhere**: perf-prohibitive in loop; serialization/hashing friction.
- **NewType wrappers (`Volts = NewType('Volts', float)`)**: mypy catches cross-
  assignments but arithmetic erases to float (`Volts * Amps` is just float — the
  interesting errors survive); all annotation cost, half the protection. May adopt
  *selectively* at solver API boundaries later; not required now.
- **Fixed-point integers everywhere**: strongest determinism, huge ergonomic cost;
  reserved as targeted remedy if ADR-0002's float triggers fire.

## Revisit triggers

- A shipped unit-error bug that conservation invariants + review both missed (→ adopt
  boundary NewTypes at minimum on the offending interfaces).
- Sim loop leaves pure Python (Rust port per tech-stack escape hatch) → reconsider
  typed quantities at the FFI boundary where they're nearly free.
