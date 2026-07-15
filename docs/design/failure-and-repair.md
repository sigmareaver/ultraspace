# Failure & Repair Model

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: design+engineering
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

## Consequence bookkeeping

- **Nonconformance log:** every jury-rig, exceeded limit, and skipped inspection. Feeds
  stress multipliers, insurance/audit events (campaign), and crew trust.
- **Component history:** each serialized device tracks hours, cycles, faults, repairs —
  visible via records screen; used by wear model (a rebuilt pump is not a new pump).
- **FDR:** every casualty is reconstructable post-hoc; the review screen is both a
  learning tool and where the player writes the incident report (campaign reputation).

## Tuning targets (v1, subject to playtest)

- Ambient fault tempo: ~1 minor casualty per 2 h of 1× operation on a healthy TL0/1 ship
  under normal environment (excludes scenario-injected faults).
- ≥ 60% of faults should be diagnosable to one suspect with onboard tools; the remainder
  require bench, spares-by-elimination, or living with uncertainty.
- Zero unexplainable faults: FDR review must always be able to show the causal chain.

## Anti-frustration rules (without lying)

- The QRH always offers a *stabilization* path even when diagnosis is hard.
- MEL deferral is always a legitimate out — the game never hard-requires a specific fix.
- Crew can be ordered to run entire FIM tasks autonomously (skill-dependent quality),
  converting player skill shortage into time cost, not walls.
