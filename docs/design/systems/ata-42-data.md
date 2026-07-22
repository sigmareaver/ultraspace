# ATA 42 — Avionics & Data

Status: Draft v0.2 (M2 increments 1–2 implementation contract) · Last updated: 2026-07-19 · Owner: design+engineering
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

M2 ships in increments. **Increment 1** (bus, BC/RT, health accounting, analyzer
v1, checkout manual) shipped 2026-07-18. This revision specifies **increment 2** —
fault model v1 (the stuck-dominant RT, the U4 fault) with the power-cycle repair
and an executable FIM 42-11 — and marks the rest **(later M2)**. Fidelity tier:
L1 (the bus is quasi-static within a tick).

Increment 2 precedes sensor transport deliberately: it is the smallest slice
that puts a *casualty that happens to the player* on the bus, it builds the
fault-injection console every later casualty test needs (testing.md class 5),
and it lands FIM conformance machinery (verdict-path branching) before the
isolation trees get wide. Sensor transport, with its power-up procedure churn,
follows on the machinery this increment proves.

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

## 2. Composition (TB-1; increments 1–2)

| Device | Part | Behavior |
|---|---|---|
| Bus controller | `core:bc-1553` | Cyclic schedule, transaction accounting, health telemetry |
| Remote terminal | `core:rt-1553` | Answers BC polls while powered; per-instance RT address |

TB-1 placement (the fixture's "1 data bus", testing.md §fixtures): `DB-A`
with `bc.a` fed from BUS E via breaker `CB E2` (the BC is the ship's data
eyesight; it belongs on the essential bus) and **two** RTs: `rt.12`
(address 12, the PDU-2 role from the U4 story) fed from BUS A via `CB A2`,
and — added at increment 2 — `rt.5` fed from BUS E via `CB E3`. Two
terminals are the minimum for the analyzer's diagnostic split (§3): with
one, "this RT dark" and "the whole bus dark" are indistinguishable. RT 5 is
also where the essential instruments will ride when sensor transport lands.

Kestrel: same parts on the same scheme. VMC-1/2 and DB-B: later M2, with
failover.

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
- **Determinism.** No RNG at increments 1–2; schedules and outcomes are pure
  functions of power state and injected fault state. Error *rates* arrive with
  the stress model.
- **Stuck-dominant (increment 2).** An RT with a latched transceiver babbles
  whenever it is powered, and a babbling transceiver **jams the medium**:
  *every* transaction on the bus fails while it holds. The ledger does not
  model the jam as bus state — the ship layer computes it per tick from the
  physical truth (any energized stuck-dominant RT on the bus) and every poll
  that tick fails, exactly as the BC would see it. This is the analyzer's
  diagnostic split: **one RT dark** (its power, its board) vs **whole bus
  dark** (the medium or the BC).

**Extension points (specified, not built):** retries, message payloads
(sensor transport), DB-B failover, BC self-test/fault modes.

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

Increment 1 shipped **consequence physics**: unpowered RT (breaker action,
bus loss, harness) → BC timeouts → `DEGRADED`; unpowered BC → bus silence.

Increment 2 ships the **fault model v1** and its first injected mode:

- **Stuck-dominant transceiver** (`stuck_dominant`, the U4 latch-up
  signature). State, not exception (Iron Law 7): a flag on the RT, set via
  the **fault-injection console** (`ultraspace.testing.inject_fault` — dev
  and CI surface; scenario fault schedules reuse it when scenarios land).
  Physics per failure-and-repair.md: a latch-up is a parasitic conduction
  path — it **holds while powered and clears on power removal**. Clearing
  is logged (`fault-cleared`, FDR); injection is logged (`fault-injected`).
  Neither event surfaces to the operator live — the player discovers the
  fault through symptoms, and reconstructs the cause in FDR review.
- **Intermittents, SEU rates, stress-driven scheduling** (the solar event
  that *causes* the latch-up): the stress-model increment, per
  failure-and-repair.md §stress-model.
- **BC fault modes** (dead controller, firmware faults): with the BC
  self-test/firmware increment. FIM 42-11's whole-bus-dark tree honestly
  names the boundary — if cycling every terminal feed restores nothing,
  the suspect is the controller or the medium (FIM 42-12, *pending*).

## 7. Procedures (manual set, staged)

- **SOM 42-00-00** Theory of data operations (increment 1; jam signature
  added at increment 2).
- **SOM 42-30-01** *Data Bus Checkout* (executable; conformance).
- **FIM 42-11** *Data Bus Degraded* (executable, increment 2): the U4
  isolation tree — jam signature → sequential terminal power-cycling →
  the bus recovers when the babbling terminal goes dark → verdict.
  Branching is executable: the procedure runner gains `on_pass_goto` /
  `on_fail_goto` (data-model.md's declared on-fail branch, now built),
  and conformance runs the tree against each injected fault asserting
  the verdict path. The one-RT-dark branch and the BC/medium boundary
  are prose-honest pointers to FIM 42-12 (*pending*).
- **QRH** data-bus loss, **MEL 42-01** (DB-A deferral): with the DB-B /
  fault-scheduling increments.

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
  Increment 2: stuck-dominant jams every transaction while energized, stops
  jamming when the feed opens, and clears on power removal (`fault-cleared`).
- **Invariant (property, hypothesis):** causality over arbitrary power
  sequences — replies only for polls issued the same tick, rx ≤ tx, failed ⊆
  registered, health ∈ [0,1]; recovery restores 1.0.
- **Casualty:** `eps cb.a2 open` mid-ops → `DATA BUS A DEGRADED` experienced
  via telemetry/annunciator only; reclose → recovery. `eps cb.e2 open` →
  analyzer reports NO DATA and *no* annunciator. Increment 2: injected
  stuck-dominant → *every* RT NO RESPONSE (the jam signature, distinct from
  one-dark power loss) → power-cycling the babbling terminal's feed restores
  the bus. Injection via `ultraspace.testing.inject_fault` is the one
  permitted testing import in this directory (testing.md class 5 says
  "inject F, assert via telemetry only" — assertions stay player-surface).
- **Conformance:** SOM 42-30-01 headless on TB-1 and Kestrel. Increment 2:
  FIM 42-11 against each injected suspect — verdict path correct per
  injection (the executed step list is the tree's trace).
- **Determinism:** TB-1 journals replay through the suite (no new RNG
  streams at increments 1–2; injection is journal-external, like SCL).
