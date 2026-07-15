# ATA 24 — Electrical Power System (EPS)

Status: Draft v0.1 (M1 implementation contract) · Last updated: 2026-07-14 · Owner: design+engineering
Related: [../ship-systems.md](../ship-systems.md), [../simulation-depth.md](../simulation-depth.md),
[../../engineering/data-model.md](../../engineering/data-model.md)

First system built; the reference implementation for the whole depth model. This
revision specifies the **M1 scope** precisely; M2+ extensions are marked.

## 1. Function & player-facing behavior

Generate, store, and distribute DC power. The player operates: battery contactors, bus
tie contactors, precharge units, and load breakers; monitors bus voltage/current
transducers and battery state; responds to undervolt/overcurrent annunciators.

M1 baseline (TL0): battery-only sources, two distribution buses. Fuel cells, solar,
umbilical power: M4. AC: none (TL0 ships are DC-only by design culture).

## 2. Composition (M1: TB-1 subset)

| Device | Part | Behavior |
|---|---|---|
| BAT 1/2 | `core:bat-28-40` | 28 V class battery: EMF(SOC) + internal resistance |
| Battery contactor | `core:ctr-30b` | As ctr-30 but energization-rated (inrush 2 kA): may close onto a dead bus |
| Bus tie contactor | `core:ctr-30` | Commanded switch, 30 A; inrush limit 150 A — precharge required |
| Precharge unit | `core:pcu-50` | Switched 50 Ω resistor path with auto-complete monitor |
| Load breakers | `core:cb-5` etc. | Manual breaker + instant overcurrent trip (thermal curve: M2) |
| Loads | `core:load-*` | Constant-resistance equipment loads (constant-power: M2) |
| V/I transducers | `core:xducer-v`, `core:xducer-i` | Instrumentation (see §4) |

Bus structure (TB-1): `BUS E` (essential; batteries land here) and `BUS A` (equipment),
joined by tie contactor + parallel precharge path. Kestrel (M1 late): adds BUS B and
per-bus battery assignment.

## 3. Electrical model (networks/electrical)

**Quasi-static DC nodal analysis with capacitive bus dynamics, backward Euler.**
Buses and terminals are nodes (ground is reference). Per tick, each device stamps the
conductance matrix G and current vector I:

- Battery: Thevenin — `G[t,t] += 1/r_int`, `I[t] += emf_v/r_int`; EMF linear in SOC:
  `emf_v = emf_empty_v + (emf_full_v - emf_empty_v) · soc`; SOC integrates terminal
  current (coulomb counting).
- Switch (contactor/breaker, closed): `g = 1/r_contact` stamped across (a,b).
- Resistor (precharge, loads): standard two-node stamp.
- Bus capacitance `c_f` (per-node, from blueprint): backward Euler —
  `G[n,n] += c_f/dt`, `I[n] += (c_f/dt)·v_prev`. Unconditionally stable at the 100 ms
  tick; precharge through 50 Ω onto ~10 mF gives τ = 0.5 s: honest, visible dynamics.

Solve by Gaussian elimination with partial pivoting (n < 20 for M1 ships; pure Python;
deterministic pivot tie-break by lowest index). Then per-device currents, SOC update,
breaker trip checks.

**Why precharge matters (the M1 "manual bar" constraint):** closing the tie directly
onto a discharged BUS A applies ~25 V across `r_contact` ≈ 20 mΩ → >1 kA inrush → tie
contactor trips (and, M2+, accumulates weld damage). SOM 24-30-01 teaches: tie OPEN →
precharge START → wait `PRECHG COMPLETE` (|ΔV| < 2 V) → tie CLOSE. The UI never hints
at this; the manual does.

**Conservation invariant (test-enforced):** Σ source power = Σ dissipation + Σ
capacitive storage rate, residual < 1e-6 · total power per solve.

Fidelity tiers at M1: this model serves as both L0 and L1 (it is cheap enough to run
always). Tier split + L2 board netlists arrive at M2 per simulation-depth.md.

## 4. Instrumentation (No God View chain, M1 form)

Transducers are devices scheduled in the INSTRUMENTS phase: they sample network state,
apply per-device gaussian noise from stream `sensor/<device>/noise` (σ from part
params) and publish `TelemetryItem(value, unit, source, tick)`. Displays/SCL `read`
surface *telemetry only*, with provenance and age. Data-bus transport is stubbed at M1
(direct wiring fiction, honest per TB-1's simplicity); DB-A/RT chain lands at M2.

Breaker/contactor positions are readable as *physical observation* (panel inspection),
not telemetry — matching real panels.

## 5. Annunciators (M1)

Config-driven threshold monitors on telemetry (ANNUNCIATORS phase), with latching
raise/clear FDR events: `BUS E UNDERVOLT` (< 24.0 V), `BUS A UNDERVOLT` (< 24.0 V,
armed only while tie closed or precharge complete), `CB TRIP` (any breaker trip event).

## 6. Failure modes

M1 ships **consequence physics only**: breaker/contactor overcurrent trips, battery
depletion, inrush trip on procedure violation. Scheduled fault injection (wear,
welded/stuck contactors, transducer drift/failure, SEU) is M2, per
failure-and-repair.md, with FIM 24-41.

## 7. Procedures (M1 manual set)

- **SOM 24-00-00** Theory of operation (prose: architecture, precharge rationale).
- **SOM 24-30-01** *Electrical Power Up — Cold & Dark to Buses Powered* (executable).
- **SOM 24-30-02** *Electrical Power Down* (executable).
- QRH/FIM/MEL Ch 24: M2 (need fault injection to be meaningful).

## 8. SCL address map (TB-1)

```
eps                      read (system summary)
eps.bat.1.contactor      close --confirm | open | read
eps.bus.a.tie            close --confirm | open | read
eps.bus.a.precharge      start | stop | read     [interlock: tie must be OPEN to start]
eps.cb.<panel-id>        open | close | read      (breakers; close --confirm if tripped)
eps.bus.e / eps.bus.a    read                     (telemetry: V, I where instrumented)
eps.bat.1                read                     (V, SOC estimate via transducer)
```

## 9. M1 content-schema subset (deviation note vs data-model.md)

M1 `part/1` carries `behavior` + `params` and omits `interfaces`/`netlists`/`sru`
(arrive M2 with L2). Blueprint `ship/1` declares electrical `nodes` (with `c_f`) and
device `ports` mapping to nodes — the WDM generator will read connectivity from here.
data-model.md remains the target shape; this subset is forward-compatible.

## 10. Test plan

- Invariants: conservation (hypothesis over random topologies/switch states); solver
  agreement with hand-computed two-bus cases (arithmetic cited in comments).
- Conformance: SOM 24-30-01 and 24-30-02 pass the headless runner on TB-1.
- Casualty-style (M1): battery contactor opened under load → decay + `BUS E UNDERVOLT`
  via telemetry only; tie closed onto discharged bus → trip event + failed procedure.
- Determinism: TB-1 cold-start journal replay → identical FDR digest.
