# Ship Systems Catalog

Status: Draft v0.1 · Last updated: 2026-07-14 · Owner: design
Related: [simulation-depth.md](simulation-depth.md), [tech-levels.md](tech-levels.md),
[../engineering/data-model.md](../engineering/data-model.md)

Scope: the systems a vessel is composed of, their simulation scope, and their milestone
of first implementation. Chapter numbers follow an ATA-like convention used across all
manuals and code (`ata` field in content data), so the SOM, FIM, and codebase share one
addressing scheme.

## Chapter index

| Ch | System | First milestone | Sim scope summary |
|---|---|---|---|
| 24 | Electrical Power (EPS) | M1 | Generation, storage, DC buses, distribution, protection |
| 21 | Environmental Control & Life Support (ECLSS) | M4 | Atmosphere, water, thermal comfort loops |
| 28 | Propellant & Fuel | M4 | Storage, transfer, pressurization |
| 71/72 | Propulsion (main drive) | M4 | Power plant + thruster performance, startup/shutdown |
| 25/29 | Thermal Control | M2 | Coolant loops, radiators, heaters, heat exchangers |
| 42 | Avionics & Data | M2 | Data buses, computers, RTs, firmware behaviors |
| 23 | Communications | M3 | Radios, antennas, link budgets, channels |
| 34 | Navigation & Guidance | M4 | State estimation, burn planning/execution monitoring |
| 32 | Docking & Mechanisms | M3 | Docking system, hatches, actuators, umbilicals |
| 51–57 | Structure & Hull | M5 | Mounting graph, leaks, vibration environment |
| 33 | Lighting & Cabin | M4 | Loads on EPS; crew environment quality |
| 45 | Central Maintenance / BITE | M2 | Self-test infrastructure, fault reporting consolidation |

Chapters not listed (e.g., 26 Fire Protection, 35 Oxygen) are added when designed; the
numbering space is reserved now to keep manuals stable.

## Per-system specification template

Every system gets its own design doc `design/systems/ata-XX-name.md` when its milestone
approaches, using this template:

1. **Function & player-facing behavior** — what it does, what the player touches.
2. **Composition** — subsystems → LRUs → SRUs → notable blocks (with candidate part numbers).
3. **Network attachments** — electrical loads/sources, thermal nodes, fluid ports, data RTs.
4. **Model tiers** — what L0/L1/L2 each mean for this system, with equations or references.
5. **Failure modes** — per failure-and-repair taxonomy, with detectability paths.
6. **Procedures** — normal (SOM), abnormal (QRH), fault isolation (FIM) to be authored.
7. **Tech level variants** — how TL0..TL4 versions differ.
8. **Test plan** — invariants, scenario tests, manual-conformance procedures.

## System sketches (pre-spec summaries)

### EPS (Ch 24) — the first system built, the reference implementation
- TL0 baseline: fuel cells + battery banks + solar wings; BUS A, BUS B, ESSENTIAL BUS E;
  bus tie contactors; breaker panels (physical-feeling: numbered, pull/collar-able);
  PDUs with board-level netlists; shunt/ammeter instrumentation.
- The canonical player skills: load shedding math, bus tie logic, breaker discipline,
  battery depth-of-discharge management, ground/dock umbilical power.
- Design doc to be written first as `design/systems/ata-24-eps.md` (M1 entry gate).

### Thermal (Ch 25/29)
- Two pumped coolant loops (A aft / B fwd), cold plates on avionics, radiators with
  bypass valves, heaters with thermostats (which stick — a classic fault).
- Couples to everything; the system that turns small electrical faults into deadlines.

### Avionics & Data (Ch 42)
- Redundant data buses DB-A/DB-B (1553-flavored: BC/RT, message schedule), vehicle
  management computers VMC-1/2, RTs embedded in LRUs across the ship.
- Firmware simulated behaviorally: modes, watchdogs, fault flags, reload procedure.
- The bus analyzer tool lives here; this system makes sensors-as-devices real.

### Comms (Ch 23)
- Channelized radios, antenna selection/pointing, link budget (range, occlusion),
  station broadcast reception, directed messages with light-lag beyond local space.
- The human element's physical layer; see [human-element.md](human-element.md).

### ECLSS (Ch 21)
- Cabin volumes with pressure/ppO2/ppCO2/humidity; scrubbers, fans, valves;
  crew as metabolic loads. Leaks as slow casualties with FIM localization gameplay.

### Propulsion (Ch 71/72)
- v1: fission-thermal or MPD baseline (TL1), with hydrazine RCS (TL0).
- Startup is a real multi-page procedure with holds and abort criteria — the "reactor
  startup" fantasy, gated on manuals, not minigames.

### Navigation (Ch 34)
- State vector estimation with sensor fusion quality dependent on which sensors are
  actually healthy/powered; burns planned as events, executed by autopilot modes with
  monitoring (the player is the systems conscience, not the joystick).

### Docking & Mechanisms (Ch 32)
- Approach corridors, capture, hard-dock sequence, umbilical mating (power/data/fluid
  transfer — a rich fault surface), hatch interlocks.

## Cross-system design rules

1. **Everything electrical is on a breaker.** Every load traces to a named breaker on a
   named bus, documented in the WDM. No phantom loads.
2. **Everything reported is sensed.** No system may publish state to displays without a
   sensor device path. (No God View, enforced at data-model validation.)
3. **Everything has a part number.** Any LRU/SRU the player can touch exists in the IPC.
4. **Every procedure the manual documents is executable** by the procedure runner in CI.
5. **Chapter ownership**: one design doc, one manual set, one test suite per chapter —
   same ATA address everywhere.
