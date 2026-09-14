# Failure & Repair Model

Status: Draft v0.4 (MAINT v1 implementation contract) · Last updated: 2026-09-13 · Owner: design+engineering
Related: [simulation-depth.md](simulation-depth.md), [manuals-as-gameplay.md](manuals-as-gameplay.md),
[../engineering/testing.md](../engineering/testing.md)

The casualty loop is the signature experience. This doc specifies how things break, how
breakage is observed, and every way the player can respond.

## Failure taxonomy

Faults attach to blocks, connectors, harness segments, and fluid/mechanical elements.
Each fault instance has: mode, onset profile, detectability paths, and repair paths.

| Class | Examples | Onset profile |
|---|---|---|
| **Wear-out** | Pump bearing degradation, relay contact erosion, battery capacity fade | Gradual drift; rate driven by stress model |
| **Random hard** | Fuse open, regulator short, valve stuck | Instant; hazard rate from stress model |
| **Intermittent** | Connector fretting, cracked solder joint, harness chafe | Condition-triggered (vibration, thermal cycle, "wiggle") |
| **Drift/calibration** | Sensor bias, oscillator drift, thermostat offset | Slow lie; system keeps "working" |
| **Software/SEU** | Bit flip, watchdog reset, mode confusion, stale firmware bug | Event-driven (radiation, specific input sequences) |
| **Induced/cascade** | Overcurrent from downstream short, thermal runaway, brownout resets | Consequence of another fault + system state |
| **Latent** | Failed standby unit, dead redundancy — discovered on demand | Silent until a demand or a scheduled test |

**Design law — latent faults justify maintenance gameplay:** scheduled inspections and
functional tests exist because redundancy silently rots. Skipping them is a legitimate,
consequential player choice.

## The stress model (why things break here and now)

Base hazard/wear rates per block (from PartType data) are modified continuously by local
conditions the sim already computes:

```
rate = base_rate × f_thermal(T_node) × f_electrical(load fraction, quality)
                × f_vibration(structural node) × f_radiation(shielding, environment)
                × f_duty(cycles) × f_nonconformance(jury-rig penalties)
```

Consequences players can learn and exploit: derate a hot PDU by shedding load; a ship
that docks hard wears connectors faster; a jury-rigged bypass makes its whole
neighborhood statistically suspect (and the crew knows it).

Randomness is drawn from named RNG streams (deterministic under seed; see
[../engineering/simulation-kernel.md](../engineering/simulation-kernel.md)) so scenarios
replay identically — a load-bearing property for both testing and FDR review.

### Stress model v1 (M2 increment 5 — implementation contract)

v1 implements the two factors the sim can compute honestly today and leaves the
rest of the formula as named, unimplemented multipliers (each lands with the
system that produces its input — `f_thermal` with the thermal loop, `f_duty`
with component history, `f_nonconformance` with jury-rigs):

```
rate_per_s = base_rate_per_s × f_env(mode) × f_rail(device)
f_env   = (flux_m2s / reference_flux_m2s) ** sensitivity      # 1.0 at quiet background
f_rail = 1.0 energized · 0.0 unpowered
```

- **The environment is physical, and it is measured.** The ship carries an
  ambient **particle flux** (`flux_m2s`, SI; instruments read the conventional
  p/cm²·s and convert at the boundary, ADR-0004 §6). Quiet background and a
  severe solar particle event differ by five orders of magnitude — which is why
  a linear `f_env` needs no fudge factor to make an event dramatic and a quiet
  cruise safe.
- **`f_rail` is not a tuning knob, it is the physics.** A latch-up is a
  parasitic conduction path: an unpowered board cannot have one. This makes
  load-shedding a real defence, which is what crews actually do during an
  event, and gives the QRH something to say that is neither "wait" nor "fix it".
- **Sensitivity is per part, per mode**, declared in content (`hazard:`), so a
  part's susceptibility ships with the part and shows up in PR diffs.

**Randomness (ADR-0002).** One stream per (device, mode): `fault/<device>/<mode>`,
the naming the kernel doc already uses. Per tick each stream is drawn **exactly
once, unconditionally**, and the draw is compared against `rate_per_s × dt`
afterwards. Drawing only for eligible devices would let a breaker position
shift the sequence, and a recorded session would stop replaying — the same law
the sensor-transport increment established for instrument noise: *the world
rolls its dice whether or not they can matter*.

**Onset is an event with a cause.** A fault the stress model starts is written
to the FDR with the factors that produced it (flux, the factor values, the
resulting rate and the draw). "Zero unexplainable faults" is a testable claim,
not an aspiration: FDR review can always show the causal chain, and a fault
with no cause record is a bug.

**Scheduling.** Scenario content (`scenario/1`) carries the environment
timeline and any scripted faults; the world layer walks it and writes the
environment the ship then reads. Scripted faults and stress-model faults enter
through the *same* ship-layer call, so an authored casualty and an emergent one
are indistinguishable downstream — including to the FDR, which records only
which of them it was.

**Tempo (v1 numbers, subject to playtest).** Quiet background is 0.1 p/cm²·s;
a severe event peaks four to five orders above it. RT latch-up base rate is
1.67e-7/s at the quiet reference — a mean time to latch-up of roughly 70 days
per terminal when nothing is happening, and roughly a minute at the peak of a
severe event. The healthy ship is boring on purpose; the event is the story.

## Observability: symptoms, not diagnoses

A fault never announces itself. It changes physics; physics changes sensor inputs;
sensors (which have their own faults) publish onto data buses; displays render what
arrived. The annunciator system (Ch 45) is itself configured by data — a warning fires
because a monitored parameter crossed a threshold *as measured*, not because the fault
exists.

Consequences the design embraces:

- Failed sensor vs. failed system is a genuine, recurring dilemma (voting, cross-checks).
- A data bus fault can make *healthy* systems look sick (see the canonical U4 story in
  [simulation-depth.md](simulation-depth.md)).
- Some faults are only findable by physical inspection verbs (borescope, wiggle test,
  thermal camera, sniffer) executed by player or crew at a location.
- **The environment obeys the same law as the ship.** A solar particle event is not a
  message from the game; it is a number on a monitor that the crew has to notice, read,
  and act on. No instrument fitted, no warning — and the faults arrive anyway.

## The diagnosis loop (and its tools)

FIM-driven: symptom → FIM entry table → decision tree → tests → verdict → repair ref.

| Tool | TL | Capability |
|---|---|---|
| DMM | TL0 | Volts/ohms/amps at test points and connector pins |
| Oscilloscope | TL0 | Waveform-class checks, abstracted to pattern verdicts ("ripple > spec") |
| Bus analyzer | TL0/1 | Data bus traffic, error counters per RT, message inspection |
| BITE terminal | TL1/2 | Unit self-test, fault log download, mode/config management |
| Thermal camera | TL0 | Hot/cold spot inspection reports per bay |
| Borescope, sniffer, UV dye | TL0 | Physical inspection verbs for fluid/structure |
| Bench (maintenance bay) | TL0/1 | SRU-level test fixtures, solder station, calibration rig |

Tests cost time (and sometimes require system states: "bus de-energized" — safety
interlocks are real). The FIM's job is to sequence cheap-informative tests first, exactly
like the real documents.

## Repair verbs (complete list, v1)

| Verb | Notes |
|---|---|
| `reseat` | Connectors/boards. Cheap, fixes fretting *temporarily* (fault remains latent). |
| `swap lru` / `swap sru` | Requires spare (IPC part number + effectivity match), tools, access, and time. |
| `repair component` | TL0 (and brave TL1): replace block-level part at bench. Cheapest in parts, dearest in skill/time. |
| `jumper` / `bypass` | Jury-rig: defeats an interlock or routes around damage. **Always** logged to nonconformance; applies stress penalties; crew morale/trust effects. |
| `patch firmware` / `reload` | TL1+: reload known-good image; config restore from ship records. |
| `calibrate` | Zero/spans a sensor against a reference. |
| `fabricate` | M5+, TL2 shops: print/machine limited part classes. |
| `defer (MEL)` | Formally accept inoperative equipment per MEL, with (O)perational and (M)aintenance conditions. The respectable choice. |

**Spares logistics:** finite inventory with part numbers, shelf-life for some items,
substitution tables in the IPC ("42-118-002 supersedes -001; -001 usable with restriction
R-4"). Buying the right spares kit for your patchwork ship is campaign strategy.

### MAINT v1 (M2 increment 7 — implementation contract)

v1 implements one row of that table — `swap lru` — for one class of hardware
(ATA 42 remote terminals), plus the bookkeeping every other row will need. It
is the missing half of the U4 story: the FIM already names a suspect and the
QRH already stabilizes, but the only way to act on a verdict was a `repair`
verb that conjured a new module out of nothing.

**A swap is two verbs, because the interesting state is the empty position.**
SCL has no multi-word verbs, so `swap lru` is `remove` and `install`. That is
not just grammar. An atomic swap can never be interrupted, deferred, botched,
or flown in — and a ship flying with a position open is a real situation with
a real cost. Removal and installation are separately refusable, separately
logged, and separately survivable.

**An empty position is empty.** A removed unit draws no current, answers no
poll, and cannot jam anything. So pulling a babbling terminal cures the bus on
the spot — a legitimate, discoverable repair, and a trap: the bus is healthy
and the function is gone. The system display is *not* told about it. A
controller cannot see an empty rack; it sees a terminal that stopped
answering, and it says `NO RESPONSE` exactly as it would for a dead board. What
separates the two is the ship's own maintenance record — `NOT FITTED` appears
where the crew looks at the position, and on the stores sheet as an open
removal. Forgetting what you pulled is allowed to cost you, which is the whole
lesson of QRH 00-00 §3.

**Every fitted box is a serialized unit.** Identity is `<part number>/<NNNN>`
— `42-110-001/0003` — assigned per part number in blueprint order, with spares
continuing the same sequence (serials are issued at manufacture, not at
fitting). Deriving identity means no authoring burden and no content churn, at
one known cost: inserting a device earlier in a blueprint renumbers the ones
after it, which "IDs are forever" (ADR-0001) does not permit for saved
campaigns. The escape hatch is already shaped — blueprints gain an optional
authored serial and the derivation becomes the fallback — and it lands when
persistence does, not before.

**Stores are finite and belong to the ship.** A blueprint declares `spares:`
by part and quantity; `install` consumes the lowest-serial spare whose part
matches the position exactly. Effectivity in v1 *is* that exact match:
supersession and restricted substitution are IPC data the parts catalog does
not carry yet. No spare is a refusal, and refusals cite the IPC sheet — the
sheet is generated from the same blueprint, so it cannot promise a part the
ship does not have.

**Records are an artifact, not a view.** A unit's record is its nameplate plus
its logbook page: serial, part number, position, powered hours, and the
history — fitted, removed, installed, and when. Reading it is allowed under No
God View for the same reason reading a placard is: the crew is looking at
something that physically exists. What it must never show is whether the unit
is *actually* faulty. A board that came off on suspicion reads `not
bench-tested`, because in v1 nobody has tested it; the FDR keeps the truth for
review, where it belongs. When the bench arrives, that line becomes **no fault
found** — a statement about the shop, not about the part — and a second NFF on
the same serial is a story the player gets to notice on their own.

**Hours are counted only where the sim knows.** v1 accrues powered hours for
rail-gated data hardware, the one class whose power gate is already computed
every tick. Everything else reads `not tracked`, never `0.0 h`: a zero would be
a false instrument reading, which is the one thing an instrument may not do.

**FDR.** `unit-removed` and `unit-installed`, each carrying serial, part
number, position and the fault state found on removal. A swap is a maintenance
action with consequences, and the review screen owes the player the record of
who changed what.

**Not in this increment:** SRU/bench work, shelf life, substitution tables,
`reseat`, MEL deferral, tool/access/time cost, transducers and harness elements
as serialized units (wiring is *repaired*, not swapped — `repair` stays where
it belongs, on junctions and segments), and crew delegation of the task.

## Consequence bookkeeping

- **Nonconformance log:** every jury-rig, exceeded limit, and skipped inspection. Feeds
  stress multipliers, insurance/audit events (campaign), and crew trust.
- **Component history:** each serialized device tracks hours, cycles, faults, repairs —
  visible via records screen; used by wear model (a rebuilt pump is not a new pump).
  v1 of this ledger ships with MAINT above: serial, position, powered hours, and the
  fitted/removed/installed history, readable with `records` at any device address.
- **FDR:** every casualty is reconstructable post-hoc; the review screen is both a
  learning tool and where the player writes the incident report (campaign reputation).

## Tuning targets (v1, subject to playtest)

- Ambient fault tempo: ~1 minor casualty per 2 h of 1× operation on a healthy TL0/1 ship
  under normal environment (excludes scenario-injected faults). This is a *whole-ship*
  figure at M4 scale — hundreds of devices, every class of fault. A TB-1 with two
  terminals and one implemented fault mode must be far quieter than that, and is
  (stress model v1: ~70 days per terminal at quiet background). The tempo target is
  reached by breadth of modelled hardware, never by making any one part fragile.
- ≥ 60% of faults should be diagnosable to one suspect with onboard tools; the remainder
  require bench, spares-by-elimination, or living with uncertainty.
- Zero unexplainable faults: FDR review must always be able to show the causal chain.

## Anti-frustration rules (without lying)

- The QRH always offers a *stabilization* path even when diagnosis is hard.
- MEL deferral is always a legitimate out — the game never hard-requires a specific fix.
- Crew can be ordered to run entire FIM tasks autonomously (skill-dependent quality),
  converting player skill shortage into time cost, not walls.
