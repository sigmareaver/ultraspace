# ATA 42 — Avionics & Data

Status: Draft v0.1 (M2 increment-1 implementation contract) · Last updated: 2026-07-18 · Owner: design+engineering
Related: [../ship-systems.md](../ship-systems.md), [../simulation-depth.md](../simulation-depth.md),
[../failure-and-repair.md](../failure-and-repair.md), [ata-24-eps.md](ata-24-eps.md),
[../../engineering/data-model.md](../../engineering/data-model.md)

The data network is the **first M2 feature**, because the M2 acceptance vignette
(the U4 latch-up story, simulation-depth.md §worked-example) is observed entirely
through it: the `DATA BUS A DEGRADED` annunciator, the FIM 42-11 decision tree, the
bus analyzer, the DB-B failover, and the MEL DB-A deferral are all data-network
behaviors. Thermal and the stress model supply the *causes*; this chapter supplies
the *symptom surface* — and the game's law is symptoms first. It also makes
"sensors-as-devices" real (ship-systems.md): the M1 direct-wiring instrumentation
fiction is replaced, in stages, by a transport that can fail, lag, or lie.

M2 ships in increments. This revision specifies **increment 1** — bus, BC/RT,
health accounting, analyzer v1, checkout manual — and marks the rest
**(later M2)**. Fidelity tier: L1 (the bus is quasi-static within a tick).

## 1. Function & player-facing behavior

The ship's data backbone: redundant buses carrying command/response traffic
between a bus controller and remote terminals embedded in LRUs across the ship.

The player touches, at increment 1:

- **Bus health**, as reported by the BC: per-RT state and error counters — the
  bus analyzer v1 (`data.db.a read`). A dead RT reads `NO RESPONSE`, never its
  root cause (the BC cannot see *why*; that is what FIM is for).
- **The annunciator** `DATA BUS A DEGRADED`.
- **Power control**: data hardware is ordinary hardware (cross-system law 1) —
  the BC and every RT sit on named breakers, draw load, and die with their rail.
  Killing an RT's breaker degrades the bus; killing the BC's silences it.

Later M2: DB-B failover, sensor-transport migration (displays show stale values
when their RT dies — the U4 step-3 symptom), FIM 42-11, MEL DB-A deferral,
firmware behaviors (modes, watchdogs, reload).

## 2. Composition (increment 1: TB-1)

| Device | Part | Behavior |
|---|---|---|
| Bus controller | `core:bc-1553` | Cyclic schedule, transaction accounting, health telemetry |
| Remote terminal | `core:rt-1553` | Answers BC polls while powered; per-instance RT address |

TB-1 placement (the fixture's "1 data bus", testing.md §fixtures — the first
deliberate growth since M1): `DB-A` with `bc.a` fed from BUS E via new breaker
`CB E2` (the BC is the ship's data eyesight; it belongs on the essential bus)
and `rt.12` (address 12, the PDU-2 role from the U4 story) fed from BUS A via
new breaker `CB A2`. This placement makes the two distinct symptoms reachable
by hand: `eps cb.a2 open` → one RT dark → `DEGRADED`; `eps cb.e2 open` → the
analyzer itself goes silent.

Kestrel: same parts on the same scheme (BC essential-fed, RTs distributed);
lands with its blueprint update in the same increment. VMC-1/2 and DB-B: later
M2, with failover.

## 3. Data-bus model (networks/data)

**1553-flavored command/response, quasi-static within the tick.** A 1 Mbps bus
moves a status transaction in ~100 µs — four orders below the 100 ms tick — so
a poll and its reply complete inside the tick that schedules them; there is no
intra-tick bus physics at L1 (that is what L2 is for, later M2).

- **Cyclic schedule.** The BC polls every registered RT once per tick (status
  request; minor frame = 1 tick). Richer frame structures and message payloads
  arrive with sensor transport.
- **Transaction outcome.** An RT replies iff it is *powered* (rail voltage ≥
  `min_v` from part params). Otherwise the BC scores a timeout: per-RT
  consecutive-timeout counter increments; at 3 consecutive the RT is declared
  FAILED; the first good reply clears both. Per-RT total error counter is
  monotone — it is the analyzer's evidence, and it never rewinds.
- **Bus health.** HEALTHY while every RT answers; DEGRADED while ≥1 RT is
  FAILED. The BC publishes health as a telemetry fraction (responding / total,
  1.0 with zero RTs) every tick it is powered — and publishes nothing when
  unpowered (instruments are devices; a dead instrument is silent, not lying).
- **Causality (the data-network conservation law).** Replies are counted only
  for polls issued in the same tick; received ≤ transmitted, always. No message
  is delivered that was never sent (simulation-depth.md). Test-enforced.
- **Determinism.** No RNG at increment 1; schedules and outcomes are pure
  functions of power state. Error *rates* arrive with the stress model.

**Extension points (specified, not built):** a stuck-dominant transceiver (the
U4 latch-up) jams the medium — *every* transaction fails, so the analyzer
distinguishes "one RT dark" (board or its power) from "whole bus dark" (medium
or BC). Retries, payloads, failover, and BC self-test join their increments.

## 4. Instrumentation & the No God View chain

M1 transducers publish directly to the telemetry store (rig-powered fiction,
ata-24-eps.md §4). Migration is staged so every step stays honest:

1. **Increment 1 (this spec):** transport untouched. The BC is itself an
   instrument; its health telemetry and bus table are the new surfaces.
2. **Sensor transport (later M2):** transducer values ride their RT; a dark RT
   sends its sensors stale (`?` per the color contract) — the U4 step-3
   symptom, displays wrong while the cabin is fine.
3. **Consumption (later M2):** displays/annunciators read BC-collected data;
   the scan loop is unchanged, only provenance deepens.

## 5. Annunciators (increment 1)

`DATA BUS A DEGRADED` — config threshold monitor on the BC health fraction:
`low: 1.0` with `arm_above: 0.99`. Quiet while cold & dark; arms once the bus
first comes fully up; fires when any RT stops answering; clears when it
recovers. BC unpowered → no telemetry → monitor quiet (no sensor, no alarm —
the honest dark-panel lesson from the M1 playtests).

## 6. Failure modes

Increment 1 ships **consequence physics only**: unpowered RT (breaker action,
bus loss, harness) → BC timeouts → `DEGRADED`; unpowered BC → bus silence.
Fault *injection* — SEU latch-up / stuck-dominant U4, intermittents (connector
fretting), BC firmware faults — arrives with the stress/fault-scheduling
increment per failure-and-repair.md; their bus-level signatures are already
specified (§3 extension points) so the analyzer and FIM land on a model that
was designed for them, not retrofitted.

## 7. Procedures (manual set, staged)

- **SOM 42-00-00** Theory of data operations (increment 1): DB-A topology,
  BC/RT roles, what DEGRADED means and what it does *not* mean.
- **SOM 42-30-01** *Data Bus Checkout* (executable, increment 1; conformance):
  from powered EPS, energize BC and RT feeds, verify the bus table.
- **FIM 42-11** (the U4 tree), **QRH** data-bus loss, **MEL 42-01** (DB-A
  deferral, single-bus ops with documented risk): with the fault increments.

## 8. SCL address map (TB-1)

```
data                     read   (system summary: each bus with BC state)
data.db.a                read   (BC bus table — analyzer v1)
```

RTs have no operator address at increment 1: they are boxes, reached through
their power breakers (and, at L2, their test points). The BC has no verbs
beyond `read` — schedule control is firmware, not panel.

## 9. Content-schema notes (increment 1)

- New part behaviors: `bc`, `rt` (params `r_ohm` input load, `min_v` power
  gate; ports `pos`/`neg` — they are electrical loads that also attach to a
  data bus).
- Blueprint gains `data_buses: [{id: db.a, name: DB-A}]`; data devices declare
  `data_bus: db.a`. RTs take their address from instance params
  (`rt_address`, 0–31; carried as float until the schema grows integer params —
  noted deviation, forward-compatible).
- Validation: exactly one BC per bus; RT addresses unique per bus; `data_bus`
  references resolve. All load-time errors, never tick-time.
- WDM: the 24 feeder trees list the new breakers (they are EPS loads); the
  generator classifies `bc`/`rt` so `make generate-check` stays green. WDM 42
  sheets arrive with L2 netlists.

## 10. Test plan

- **Unit:** schedule execution; timeout → FAILED → health transitions;
  recovery clears; error counter monotonicity; unpowered BC publishes nothing.
- **Invariant (property, hypothesis):** causality over arbitrary power
  sequences — replies only for polls issued the same tick, rx ≤ tx, failed ⊆
  registered, health ∈ [0,1]; recovery restores 1.0.
- **Casualty:** `eps cb.a2 open` mid-ops → `DATA BUS A DEGRADED` experienced
  via telemetry/annunciator only; reclose → recovery. `eps cb.e2 open` →
  analyzer reports NO DATA and *no* annunciator (the honest dark instrument).
- **Conformance:** SOM 42-30-01 headless on TB-1.
- **Determinism:** TB-1 journals replay through the suite with the new devices
  (no new RNG streams at increment 1).
