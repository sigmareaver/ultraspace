# ATA 42 — Avionics & Data

Status: Draft v0.4 (M2 increments 1–3 implementation contract) · Last updated: 2026-09-12 · Owner: design+engineering
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
v1, checkout manual) shipped 2026-07-18; **increment 2** (fault model v1:
stuck-dominant, power-cycle repair, executable FIM 42-11, runner branching)
shipped 2026-07-19. This revision specifies **increment 3** — the harness:
topology, located medium faults, and measurement-driven isolation — and marks
the rest **(later M2)**. Fidelity tier: L1 (the bus is quasi-static within a
tick).

**Review of increments 1–2 (why increment 3 exists).** The ledger knows counts
but not places. The electrical system gets its depth from topology — a solve
over a physical graph makes truth *located* (this node, that branch) and lets
procedures exploit location. The data bus so far has no medium: RTs float in
space, every power fault looks identical, the only global fault is a jam, and
the only repair is a power cycle. Two analyzable patterns (one-dark, all-dark)
is not a diagnostic discipline. Increment 3 gives the bus a body — trunk,
couplers, stubs, terminators — with faults *at places*, and gives the player a
measurement (the DMM) that reads those places. The illusion-of-simulation
contract is kept exactly the electrical way: no waveform, no bits, no timing —
graph reachability and equivalent-resistance arithmetic per tick, negligible
cost, all of it consistent with the physical story. Reference: MIL-STD-1553's
own design culture (isolation transformers, transformer-coupled stubs, both-
end termination) — the standard is *designed* so one module cannot kill the
bus; the failures that still can are the interesting ones.

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

## 2. Composition (TB-1; increments 1–3)

| Device | Part | Behavior |
|---|---|---|
| Bus controller | `core:bc-1553` | Cyclic schedule, transaction accounting, health telemetry |
| Remote terminal | `core:rt-1553` | Answers BC polls while powered; per-instance RT address |
| Bus coupler | `core:db-coupler` | Trunk junction: feed-through + stub taps; DMM probe point |
| Harness segment | `core:db-harness` | A run of twinax (trunk or stub); fault-capable medium |

TB-1 topology (the fixture's "1 data bus", testing.md §fixtures):

```
        seg.bc-j1       seg.j1-j2
  bc.a ────────── J1 ────────── J2 ── (78 ohm end terminator)
                   │             │
                stub.j1-rt5   stub.j2-rt12
                   │             │
                  rt.5         rt.12   (bc.a end: 78 ohm terminator)
```

- `bc.a` fed from BUS E via `CB E2` (the BC is the ship's data eyesight; it
  belongs on the essential bus).
- `rt.5` fed from BUS E via `CB E3`; `rt.12` (the PDU-2 role from the U4
  story) fed from BUS A via `CB A2`.
- Two couplers `j1` (essential-bay side), `j2` (equipment-bay side) — the
  network's relays: a coupler or trunk fault partitions the bus, and the
  dark zone is *contiguous from the BC's chair*, which is what makes it
  diagnosable from the analyzer pattern.
- Both trunk ends terminated at the cable's nominal 78 ohm (MIL-STD-1553B:
  "a resistance equal to the selected cable nominal characteristic
  impedance"); stubs are **transformer-coupled** — the standard's own
  fault-containment culture, see §6.

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
  that tick fails, exactly as the BC would see it.
- **Topology (increment 3).** The bus is a graph: junctions (couplers)
  joined by trunk segments, with stub segments tapping RTs at couplers. An
  RT answers a poll iff it is energized, alive, and *reachable* — an
  unbroken path of ok segments and couplers from the BC. The poll outcome is
  computed per tick from the graph (O(members); no waveform, no timing —
  the illusion contract).
- **Medium death (increment 3).** A **trunk short** (or a shorted coupler)
  kills the whole medium electrically: every transaction fails, exactly like
  a jam — but cycling terminals does *not* help, and the DMM reads ~0 ohm.
  A **stub short is contained**: transformer coupling (the 1553B-preferred
  stubbing, §6) isolates the fault to the stub and its terminal — one RT
  dark, the bus untouched.

**Extension points (specified, not built):** retries, message payloads
(sensor transport), DB-B failover, BC self-test/fault modes, missing/
degraded termination (reflections → intermittents, needs the stress model).

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
bus loss) → BC timeouts → `DEGRADED`; unpowered BC → bus silence.
Increment 2 shipped the fault model v1 (injection console, FDR-logged
injection and clearing; nothing surfaces to the operator live). Increment 3
completes the located-fault matrix:

| Fault | Target | Bus effect | Analyzer signature | Distinguisher |
|---|---|---|---|---|
| Power loss | RT feed | none beyond it | one RT dark | breaker open / feed dead |
| `dead` (module, silent) | RT | none beyond it | one RT dark, powered | stub ohms good, board won't answer |
| `stuck_dominant` (latch-up) | RT | **protocol jam** | all RTs dark | clears on power removal of the babbler |
| `open` | stub segment | none beyond it | one RT dark, powered | stub ohms OL at the coupler |
| `short` | stub segment | **contained** (transformer coupling) | one RT dark, powered | stub ohms ~0 at the coupler |
| `open` | trunk segment | **partition** | contiguous dark suffix from the BC | trunk ohms OL toward the dark zone, from either end |
| `short` | trunk segment | **medium dead** | all RTs dark | cycling doesn't help; trunk ohms ~0 at both ends of the run |
| `open` | coupler | **partition** | contiguous dark suffix from the BC | OL *from the neighbouring coupler*; clean at its own probe point |
| `short` | coupler | **medium dead** | all RTs dark | trunk ohms ~0 in **both** directions at its own probe point |

The matrix is the CAN/1553 fault gospel made physical, with the standard's
own containment culture: isolation transformers and transformer-coupled
stubs mean *one module's electrical fault cannot kill the bus* — the
failures that still can are a babbling transmitter (protocol, clears with
power) and a trunk short (medium, located, ohmable). A shorted stub is the
contained case; had the ship been wired with direct-coupled stubs it would
kill the bus — our ships are built to the standard's preferred culture.

**Measurement (the DMM).** Isolation is measurement-driven. A junction
`read` is a DMM ohms check at that coupler, per direction: equivalent
resistance seen looking along each segment — the far terminator (78 ohm)
through an unbroken path, `OL` toward an open, ~0 ohm toward a short;
stub taps read the coupling-winding continuity (~2 ohm) / OL / ~0.
**Interlock, real shop practice:** ohms checks refuse while any data
device on that bus is energized — de-energize the bus before probing
(FIM 42-12 teaches it; refusal cites it).

**What the meter cannot say (the coupler asymmetry).** The probed
coupler's own state colors its trunk readings, and the two coupler faults
are not symmetric — this is the discipline the harness tree is built on:

- A **shorted coupler** is a short across the pair *at the probe point*:
  every trunk direction from it reads ~0. A shorted run reads ~0 in one
  direction only. "Both ways zero at one coupler" therefore convicts the
  coupler, and nothing else does.
- An **open coupler** is a broken feed-through *between* its two trunk
  faces: each face still reads its own way out at 78 ohm, so the fault is
  invisible from the coupler standing on it and shows as `OL` from the
  neighbour. A coupler break is confirmed one coupler down.
- One pair is **genuinely inseparable by ohms**: a short in a run versus a
  short in the coupler at that run's far end both put ~0 at both ends of
  the run. The meter has said all it can; the tree then works it by
  replacement in cost order (run first, verify, then the coupler), which is
  what a shop does. Isolation is allowed to bottom out in a swap — it is
  not allowed to bottom out in a guess the sim silently scores.

**Repair (field form; MAINT attaches cost later).** `repair` on a segment,
coupler, or RT (module) replaces the part — whatever its state — FDR-logged
(with `fault_found` for review), interlocked the same way: you do not
splice a live bus. It reports the same text either way, because refusing
"nothing to repair" on a sound part would hand the player a verdict no
instrument gave them (No God View). Replacing a good run is a wasted part;
the bus table after re-energizing is the only verdict. Intermittents, SEU
rates, and stress scheduling (the solar event that *causes* the latch-up):
the stress-model increment. BC fault modes: the BC/firmware increment.

## 7. Procedures (manual set, staged)

- **SOM 42-00-00** Theory of data operations (topology, termination,
  coupling culture, and DMM practice added at increment 3).
- **SOM 42-30-01** *Data Bus Checkout* (executable; conformance).
- **FIM 42-11** *Data Bus Degraded* (executable): the U4 jam tree —
  all-dark → sequential power-cycling → the bus recovers when the babbling
  terminal goes dark. Its boundaries now hand off to FIM 42-12.
- **FIM 42-12** *Data Bus Wiring and Medium Faults* (executable,
  increment 3): the harness tree — one-dark with a good feed → stub ohms
  at the coupler (stub / coupler / board / trunk upstream); all-dark after
  cycling → de-energize → trunk ohms at the couplers (short: ~0; open: OL)
  → `repair` the interval → re-energize → verify. Couplers are convicted
  inside this tree, not deferred: the asymmetry above supplies the
  discriminators (both-ways-zero at a probe point; `OL` seen from the
  neighbour), and the one inseparable pair is worked by the replace-verify
  ladder. What still exits to **FIM 42-13** is the controller itself —
  harness clean end to end, bus still dark. Conformance runs the tree
  against *every* injectable harness fault (a canary derives the expected
  set from the blueprint, so new harness hardware without a verdict path
  fails the build) and asserts each verdict path; the runner's expectation
  vocabulary gains `expect_text` (substring match on command output) so DMM
  readings are branchable like real checklist readings.
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

## 9. Content-schema notes (increments 1–3)

- Part behaviors: `bc`, `rt` (params `r_ohm` input load, `min_v` power
  gate; ports `pos`/`neg); `junction` (bus coupler; no electrical load) and
  `harness_seg` (trunk/stub run; `ends: {a, b}` naming bus members — BC,
  junction, or RT device ids). Buses declare `termination_ohm` (78).
- Blueprint `data_buses: [{id: db.a, name: DB-A}]`; data devices declare
  `data_bus: db.a`. RTs take their address from instance params
  (`rt_address`, 0–31; carried as float until the schema grows integer
  params — noted deviation, forward-compatible).
- Validation: exactly one BC per bus; RT addresses unique per bus; harness
  `ends` resolve to bus members; every bus member is reachable from the BC
  through declared segments at load time (a dangling harness is a build
  error, never a tick-time surprise). All load-time errors.
- WDM: the 24 feeder trees list the data-hardware breakers; a generated
  WDM 42 harness sheet (trunk/couplers/stubs/terminator, in BC-outward
  order) is the isolation map FIM 42-12 references. Harness and couplers
  carry no electrical ports, so the 24 tables are unchanged by them.

## 10. Test plan

- **Unit:** schedule execution; timeout → FAILED → health transitions;
  recovery clears; error counter monotonicity; unpowered BC publishes
  nothing. Stuck-dominant jams while energized and clears on power removal.
  Increment 3: reachability over the graph, partition contiguity, trunk
  short kills / stub short contained, ohms arithmetic per direction
  (terminator / OL / ~0, stub continuity), DMM interlock, `repair` clears.
- **Invariant (property, hypothesis):** causality over arbitrary power and
  harness-fault sequences — rx ≤ tx, replies only for polls issued the same
  tick, failed ⊆ registered, health ∈ [0,1]; a trunk short is always
  bus-wide, a stub short never is.
- **Casualty (all signatures experienced via telemetry/SCL/panel only):**
  power loss → one dark; dead module → one dark, powered; stuck-dominant →
  all dark, clears on the cycle; stub open/short → one dark with telling
  stub ohms; trunk open → *contiguous* dark suffix; trunk short → all dark
  that no power cycle fixes, trunk ohms ~0.
- **Conformance:** SOM 42-30-01 headless on both ships. FIM 42-11 per
  injected jam suspect; FIM 42-12 per injected harness fault — verdict
  path correct per fault (the executed step list is the tree's trace), and
  a deliberately wrong FIM edit fails CI. The fault set is *derived from
  the ship*, not hand-listed: every coupler/run (open, short) and every RT
  (dead) must have a path, so hardware can never be fitted without a
  documented way to isolate it.
- **Determinism:** no new RNG streams at increments 1–3; injection is
  journal-external, like SCL.
