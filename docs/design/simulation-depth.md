# Simulation Depth Model

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: design+engineering
Related: [../engineering/architecture.md](../engineering/architecture.md),
[failure-and-repair.md](failure-and-repair.md), [ship-systems.md](ship-systems.md)

The pillar this doc serves: **Depth is real** and **Fidelity where you look**.

## The containment hierarchy

Every physical thing on the ship lives in this hierarchy. Names are canonical.

```
Vessel
└── System            (EPS, ECLSS, Propulsion, Thermal, Avionics/Data, Comms, Structure)
    └── Subsystem     (e.g., EPS → Bus A distribution)
        └── LRU       (line-replaceable box: PDU-2, pump P-201, radio R-1)
            └── SRU   (board/module inside an LRU: "PDU-2 board A2, bus controller")
                └── Block  (netlist element: regulator U1, MCU U3, transceiver U4,
                            relay K2, fuse F4, connector J1, test point TP-104)
```

- **Block is the finest permanent grain.** Faults live at block level ("U4 failed open,
  SEU latch-up"). There is no transistor/SPICE simulation (non-goal, see vision).
- Blocks connect via **board netlists**; LRUs connect via **harnesses and connectors**
  (which are themselves fault-capable devices — connector fretting is a real failure mode).
- Everything is instantiated from data (PartType definitions), never hardcoded.
  See [../engineering/data-model.md](../engineering/data-model.md).

## Cross-cutting networks

Depth emerges from coupling, not from any single deep model. Devices attach to one or
more networks; the networks exchange derived quantities every tick.

| Network | Solves | Example coupling |
|---|---|---|
| **Electrical** | DC nodal analysis per bus, quasi-static, piecewise-linear sources/loads | Electrical dissipation → heat into thermal nodes |
| **Thermal** | Lumped node graph: conduction, radiation, heat capacity | Node temp → component stress, breaker derating, sensor drift |
| **Fluid** | Loop flow/pressure (coolant, propellant, atmosphere) | Pump power ← electrical; heat transport → thermal |
| **Data** | Bus topology, message schedules, RT/BC roles, error rates | Sensor readings ride the data network; bus faults corrupt *displays* |
| **Structure** | Mounting graph: vibration, mass, hull integrity (coarse) | Vibration → connector/bearing wear rates |

**Rule: instruments are devices.** A temperature display shows the last value that made it
through: sensor → ADC block → RT → data bus → display processor. Any hop can fail, lag,
or lie. This implements No God View mechanically, not as UI policy.

## Fidelity tiers

Simulating every block on the ship every tick is neither feasible nor useful. Each model
declares up to three tiers; the scheduler promotes/demotes per unit.

| Tier | Name | What it is | Runs |
|---|---|---|---|
| **L0** | Envelope | Algebraic steady-state: flows, sums, efficiencies | Always, whole ship |
| **L1** | Dynamic | Lumped-parameter ODEs: time constants, transients | While a subsystem is active/perturbed |
| **L2** | Forensic | Board netlist solve: node voltages at test points, block states | On demand |

**Promotion triggers (L2):** player probes a test point / opens a bay; an active fault
resides in the unit; a transient involves the unit (breaker trip, relay chatter); a
scenario script requests it. **Demotion:** quiescence for a configured interval.

**Tier consistency law:** where tiers overlap, L2 steady-state must agree with L1, and L1
equilibrium with L0, within documented tolerance. This is enforced by automated
tier-consistency tests (see [../engineering/testing.md](../engineering/testing.md)).
Without this law, "zooming in" would change the truth, which players would rightly read
as the sim lying.

## Conservation laws

Per network, per solve step, the following are test-enforced invariants:

- Electrical: Σ power in = Σ power out + Σ dissipation (per bus).
- Thermal: energy conservation across the node graph (within integrator tolerance).
- Fluid: mass conservation per loop; no fluid created by valves.
- Data: no message delivered that was never sent (causality).

A conservation violation is a P0 bug. These invariants are what make "depth is real"
falsifiable instead of a slogan.

## Environment inputs

The ship sits in a simulated environment that stresses it:

- **Radiation**: background + solar events → SEU rate per shielded volume → bit flips in
  MCU blocks (watchdog resets, corrupted readings), latch-ups (the U4 story).
- **Thermal environment**: sun aspect, eclipse, station shadow.
- **Vibration/acceleration**: burns and docking → wear modifiers.
- **Vacuum/atmosphere**: leak physics for pressurized volumes.

## Worked example (canonical depth story)

This chain must be fully simulable by M2 — it is the acceptance story for the depth model:

1. Solar event raises SEU rate. A bit flips in PDU-2 board A2's MCU (U3): latch-up drives
   transceiver U4 into a stuck-dominant state.
2. Data bus DB-A degrades: RTs report intermittent; bus controller fails over to DB-B per
   its firmware. Annunciator: `DATA BUS A DEGRADED`.
3. Displays fed by DB-A-only sensors show stale values (No God View: the *display* is
   what's wrong, cabin temp is actually fine).
4. Player works FIM 42-11: bus analyzer shows error bursts localized to RT address 12
   (PDU-2). Cycling PDU-2 A2 board power clears latch-up — until the next event.
5. Permanent fix: swap A2 (IPC part 42-118-002), or accept MEL dispatch relief with DB-B
   as sole bus (with its documented risk).

Every step above exists in data + physics, none of it is scripted narrative.

## Performance envelope (design contract with engineering)

- Whole-ship L0/L1 at base rate: ~5,000 devices, 10 Hz, mid-range laptop, single core.
- L2 concurrent forensic units: ≤ 8 boards without missing the tick budget.
- Time compression 1000× achieved by batching L0 steps and event-driven wake-ups, never
  by skipping conservation checks.
  Details: [../engineering/simulation-kernel.md](../engineering/simulation-kernel.md).

## Non-goals (explicit)

- SPICE/analog waveform simulation; RF propagation physics beyond link budgets.
- PCB layout/geometry (we model netlist + connectors + test points, not copper routing).
- CFD; fluid loops are lumped, not field-solved.
