<!-- GENERATED FILE — DO NOT EDIT (ultraspace generate). -->
<!-- Source: ships/tb-1/blueprint.yaml + the part catalog. -->
<!-- Style: data/manuals/style-guide.md. Hand edits fail CI. -->


# WDM 24 — Generated Data Sheets — TB-1 Breadboard (core:tb-1)

## Panel: protection & switching {#breaker-table}

| SCL address | Device | P/N | Type | Rating | From | To |
|---|---|---|---|---|---|---|
| `eps.bat.1.contactor` | ctr.bat1 | 24-110-031 | contactor | 30 A | bat1.term | bus.e |
| `eps.bus.a.tie` | tie.a | 24-110-030 | contactor | 30 A | bus.e | bus.a |
| `eps.bus.a.precharge` | pcu.a | 24-115-050 | precharge | 50 ohm | bus.e | bus.a |
| `eps.cb.e1` | cb.e1 | 24-120-005 | breaker | 5 A | bus.e | load.avionics.in |
| `eps.cb.a1` | cb.a1 | 24-120-010 | breaker | 10 A | bus.a | load.cabin.in |

## Feeder trees {#feeder-trees}

```
BUS E  [bus.e]  8 mF
 ├── ctr.bat1  24-110-031  contactor 30 A      → bat1.term → bat1
 ├── tie.a     24-110-030  contactor 30 A      → BUS A
 ├── pcu.a     24-115-050  precharge 50 ohm    → BUS A
 └── cb.e1     24-120-005  breaker 5 A         → load.avionics.in → load.avionics

BUS A  [bus.a]  12 mF
 ├── tie.a  24-110-030  contactor 30 A      → BUS E
 ├── pcu.a  24-115-050  precharge 50 ohm    → BUS E
 └── cb.a1  24-120-010  breaker 10 A        → load.cabin.in → load.cabin
```

## Wire list {#wire-list}

| Node | Capacitance | Connections (device.port) |
|---|---|---|
| bat1.term | 0.2 mF | bat1.pos, ctr.bat1.a |
| bus.e | 8 mF | ctr.bat1.b, tie.a.a, pcu.a.a, cb.e1.a |
| bus.a | 12 mF | tie.a.b, pcu.a.b, cb.a1.a |
| load.avionics.in | 0.1 mF | cb.e1.b, load.avionics.pos |
| load.cabin.in | 0.1 mF | cb.a1.b, load.cabin.pos |
| gnd (ref) | - | bat1.neg, load.avionics.neg, load.cabin.neg |

## Load list {#load-list}

| Device | P/N | Name | R | I @ 28 V | Protected by |
|---|---|---|---|---|---|
| load.avionics | 24-190-060 | Equipment load, 60 W class | 13.07 ohm | 2.1 A | cb.e1 |
| load.cabin | 24-190-150 | Equipment load, 150 W class | 5.23 ohm | 5.4 A | cb.a1 |

## Instrumentation {#instrumentation}

| Telemetry ID | P/N | Measures | Unit | SCL |
|---|---|---|---|---|
| mt.bus.e.v | 24-150-001 | bus.e | V | `eps.bus.e` |
| mt.bus.a.v | 24-150-001 | bus.a | V | `eps.bus.a` |
| mt.bat.1.i | 24-150-002 | ctr.bat1 | A | `eps.bat.1` |
| mt.bat.1.soc | 24-150-003 | bat1 | frac | `eps.bat.1` |

## Parts list (IPC extract) {#parts-list}

| P/N | Name | Qty | Unit mass |
|---|---|---|---|
| 24-101-040 | Battery, 28 V class, 40 Ah | 1 | 31 kg |
| 24-110-030 | Contactor, 30 A DC | 1 | 0.9 kg |
| 24-110-031 | Contactor, 30 A DC, battery (energization-rated) | 1 | 1.4 kg |
| 24-115-050 | Precharge Unit, 50 ohm | 1 | 0.6 kg |
| 24-120-005 | Circuit breaker, 5 A | 1 | 0.1 kg |
| 24-120-010 | Circuit breaker, 10 A | 1 | 0.1 kg |
| 24-150-001 | Voltage transducer, DC bus | 2 | 0.05 kg |
| 24-150-002 | Current transducer, hall effect | 1 | 0.08 kg |
| 24-150-003 | Battery monitor, state of charge | 1 | 0.12 kg |
| 24-190-060 | Equipment load, 60 W class | 1 | 4 kg |
| 24-190-150 | Equipment load, 150 W class | 1 | 6.5 kg |
