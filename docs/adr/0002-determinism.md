# ADR-0002: Fixed-tick, integer-time, seeded-stream determinism

Status: Accepted
Date: 2026-07-14
Deciders: project maintainer + founding agent session

## Context

The product's credibility rests on the simulation being *true*: every symptom has a
cause, every casualty is reconstructable, manuals are provably correct. Testing a sim
this deep is intractable unless runs are exactly reproducible. Additionally, the FDR
concept (save = replay = bug report = in-game feature) requires bit-stable re-execution.

## Decision

Everything below the presentation layer is deterministic as a function of
**(master seed, content hash, SCL journal)**:

1. **Fixed tick** (100 ms) with **integer-microsecond** sim time; dt never varies;
   time compression = more ticks per wall second, never bigger steps.
2. **All randomness** via `RngHub` named streams (`blake2b(seed || name)`), one stream
   per entity/purpose; no module-level RNG, no wall clock in model code.
3. **Deterministic scheduling**: fixed phase order per tick; registration order derived
   from content traversal; no ordering from unordered collections.
4. **State hash oracle**: canonical serialization hashed per tick (in test modes);
   replay must match hash-for-hash. CI enforces; divergence is P0.

## Consequences

- Golden tests, replay bisection, cross-machine bug repro, and the FDR product features
  all become straightforward; "cannot reproduce" is structurally impossible below UI.
- Float nondeterminism is contained by same-platform bit-exactness + pinned CI; the
  cross-platform hash matrix (M2) will surface libm differences early. If they bite,
  remedies escalate: fixed-point in affected solver → software transcendentals → per-
  platform golden sets (last resort, ADR required).
- Costs accepted: discipline overhead (lints, review), no free threading in models,
  RNG stream bookkeeping, and performance sacrifices (no fast-math, ordered reductions).

## Alternatives considered

- **Variable timestep**: standard in action games; rejected — physics results would
  depend on frame timing, killing replay and test oracles.
- **Global single RNG**: simpler; rejected — any new consumer reshuffles every
  subsequent draw (adding a sensor would change when a pump fails: absurd, untestable).
- **Best-effort determinism**: rejected; partial determinism is nondeterminism with
  extra steps and false confidence.

## Revisit triggers

- Cross-platform hash matrix reveals unfixable-at-reasonable-cost float divergence.
- Profiling shows integer-time/canonical-hash overhead > 5% of tick budget (optimize
  the mechanism, keep the contract).
