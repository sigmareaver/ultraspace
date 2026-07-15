<!-- GENERATED FILE — DO NOT EDIT (ultraspace generate). -->
<!-- Source: ships/uev-kestrel/blueprint.yaml + the part catalog. -->
<!-- Style: data/manuals/style-guide.md. Hand edits fail CI. -->


# WDM 24 — Generated Data Sheets — UEV Kestrel (core:uev-kestrel)

## Panel: protection & switching {#breaker-table}

| SCL address | Device | P/N | Type | Rating | From | To |
|---|---|---|---|---|---|---|
| `eps.bat.1.contactor` | ctr.bat1 | 24-110-031 | contactor | 30 A | bat1.term | bus.e |
| `eps.bat.2.contactor` | ctr.bat2 | 24-110-031 | contactor | 30 A | bat2.term | bus.b |
| `eps.bus.a.tie` | tie.a | 24-110-030 | contactor | 30 A | bus.e | bus.a |
| `eps.bus.a.precharge` | pcu.a | 24-115-050 | precharge | 50 ohm | bus.e | bus.a |
| `eps.bus.b.tie` | tie.b | 24-110-030 | contactor | 30 A | bus.e | bus.b |
| `eps.bus.b.precharge` | pcu.b | 24-115-050 | precharge | 50 ohm | bus.e | bus.b |
| `eps.cb.e1` | cb.e1 | 24-120-005 | breaker | 5 A | bus.e | load.avionics.in |
| `eps.cb.a1` | cb.a1 | 24-120-010 | breaker | 10 A | bus.a | load.cabin.in |
| `eps.cb.b1` | cb.b1 | 24-120-010 | breaker | 10 A | bus.b | load.equipbay.in |

## Feeder trees {#feeder-trees}

```
BUS E  [bus.e]  8 mF
 ├── ctr.bat1  24-110-031  contactor 30 A      → bat1.term → bat1
 ├── tie.a     24-110-030  contactor 30 A      → BUS A
 ├── pcu.a     24-115-050  precharge 50 ohm    → BUS A
 ├── tie.b     24-110-030  contactor 30 A      → BUS B
 ├── pcu.b     24-115-050  precharge 50 ohm    → BUS B
 └── cb.e1     24-120-005  breaker 5 A         → load.avionics.in → load.avionics

BUS A  [bus.a]  12 mF
 ├── tie.a  24-110-030  contactor 30 A      → BUS E
 ├── pcu.a  24-115-050  precharge 50 ohm    → BUS E
 └── cb.a1  24-120-010  breaker 10 A        → load.cabin.in → load.cabin

BUS B  [bus.b]  10 mF
 ├── ctr.bat2  24-110-031  contactor 30 A      → bat2.term → bat2
 ├── tie.b     24-110-030  contactor 30 A      → BUS E
 ├── pcu.b     24-115-050  precharge 50 ohm    → BUS E
 └── cb.b1     24-120-010  breaker 10 A        → load.equipbay.in → load.equipbay
```

## Wire list {#wire-list}

| Node | Capacitance | Connections (device.port) |
|---|---|---|
| bat1.term | 0.2 mF | bat1.pos, ctr.bat1.a |
| bat2.term | 0.2 mF | bat2.pos, ctr.bat2.a |
| bus.e | 8 mF | ctr.bat1.b, tie.a.a, pcu.a.a, tie.b.a, pcu.b.a, cb.e1.a |
| bus.a | 12 mF | tie.a.b, pcu.a.b, cb.a1.a |
| bus.b | 10 mF | ctr.bat2.b, tie.b.b, pcu.b.b, cb.b1.a |
| load.avionics.in | 0.1 mF | cb.e1.b, load.avionics.pos |
| load.cabin.in | 0.1 mF | cb.a1.b, load.cabin.pos |
| load.equipbay.in | 0.1 mF | cb.b1.b, load.equipbay.pos |
| gnd (ref) | - | bat1.neg, bat2.neg, load.avionics.neg, load.cabin.neg, load.equipbay.neg |

## Load list {#load-list}

| Device | P/N | Name | R | I @ 28 V | Protected by |
|---|---|---|---|---|---|
| load.avionics | 24-190-060 | Equipment load, 60 W class | 13.07 ohm | 2.1 A | cb.e1 |
| load.cabin | 24-190-150 | Equipment load, 150 W class | 5.23 ohm | 5.4 A | cb.a1 |
| load.equipbay | 24-190-150 | Equipment load, 150 W class | 5.23 ohm | 5.4 A | cb.b1 |

## Instrumentation {#instrumentation}

| Telemetry ID | P/N | Measures | Unit | SCL |
|---|---|---|---|---|
| mt.bus.e.v | 24-150-001 | bus.e | V | `eps.bus.e` |
| mt.bus.a.v | 24-150-001 | bus.a | V | `eps.bus.a` |
| mt.bus.b.v | 24-150-001 | bus.b | V | `eps.bus.b` |
| mt.bat.1.i | 24-150-002 | ctr.bat1 | A | `eps.bat.1` |
| mt.bat.1.soc | 24-150-003 | bat1 | frac | `eps.bat.1` |
| mt.bat.2.i | 24-150-002 | ctr.bat2 | A | `eps.bat.2` |
| mt.bat.2.soc | 24-150-003 | bat2 | frac | `eps.bat.2` |

## Parts list (IPC extract) {#parts-list}

| P/N | Name | Qty | Unit mass |
|---|---|---|---|
| 24-101-040 | Battery, 28 V class, 40 Ah | 2 | 31 kg |
| 24-110-030 | Contactor, 30 A DC | 2 | 0.9 kg |
| 24-110-031 | Contactor, 30 A DC, battery (energization-rated) | 2 | 1.4 kg |
| 24-115-050 | Precharge Unit, 50 ohm | 2 | 0.6 kg |
| 24-120-005 | Circuit breaker, 5 A | 1 | 0.1 kg |
| 24-120-010 | Circuit breaker, 10 A | 2 | 0.1 kg |
| 24-150-001 | Voltage transducer, DC bus | 3 | 0.05 kg |
| 24-150-002 | Current transducer, hall effect | 2 | 0.08 kg |
| 24-150-003 | Battery monitor, state of charge | 2 | 0.12 kg |
| 24-190-060 | Equipment load, 60 W class | 1 | 4 kg |
| 24-190-150 | Equipment load, 150 W class | 2 | 6.5 kg |
