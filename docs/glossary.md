# Glossary

Status: Living document · Last updated: 2026-07-14 · Owner: design
Scope: Canonical terminology. All docs, code identifiers, and in-game text use these terms.

## Simulation & architecture

| Term | Definition |
|---|---|
| **Kernel** | The deterministic core: sim clock, scheduler, RNG hub, event log. No game content. |
| **Tick** | One fixed step of the base simulation clock (100 ms of sim time). All sim time is integer microseconds. |
| **Rate group** | A set of tasks executed every N ticks (e.g., thermal at 1 Hz, electrical at 10 Hz). |
| **Network** | A physical graph the solver operates on: electrical, thermal, fluid, or data. Devices attach to one or more networks. |
| **Device** | A simulated physical unit instantiated from a PartType (a pump, a PDU, a sensor). |
| **Block** | A functional element on a board netlist (regulator, MCU, transceiver, relay, fuse). The finest permanent simulation grain. |
| **Fidelity tier** | L0 *envelope* (algebraic steady-state), L1 *dynamic* (lumped ODE), L2 *forensic* (board/net-level, on demand). |
| **No God View** | Design law: player-facing data comes only from simulated instrumentation, never raw sim state. |
| **FDR** | Flight Data Recorder. Append-only event/telemetry log; doubles as save format, replay/debug artifact, and in-game post-incident review feature. |
| **SCL** | Ship Command Language. The noun-path/verb command grammar; every UI interaction emits SCL. |
| **Telemetry** | The read-only, instrument-mediated data stream that presentation layers consume. |

## Hardware & maintenance (borrowed from real aerospace practice)

| Term | Definition |
|---|---|
| **LRU** | Line-Replaceable Unit. A box swappable in the field (e.g., PDU-2). |
| **SRU** | Shop-Replaceable Unit. A board/module inside an LRU, swappable at the maintenance bench. |
| **BITE** | Built-In Test Equipment. Self-diagnostics a unit exposes; quality varies by tech level. |
| **PDU** | Power Distribution Unit. |
| **EPS** | Electrical Power System. |
| **ECLSS** | Environmental Control and Life Support System. |
| **RCS** | Reaction Control System. |
| **Bus (electrical)** | A DC distribution node (e.g., BUS A, BUS E ESSENTIAL). |
| **Bus (data)** | A shared digital network segment (e.g., DB-A/DB-B redundant pair). |
| **RT / BC** | Remote Terminal / Bus Controller on a data bus. |
| **SEU** | Single Event Upset. Radiation-induced bit flip; a first-class failure source. |
| **Test point** | A probe-able node (TP-xxx) on a board, documented in the WDM. |
| **Effectivity** | Which part numbers/serials a manual section or part applies to. |
| **Nonconformance log** | In-game record of jury-rigs and deviations; biases future risk and inspections. |
| **Cold and dark** | Ship state with all systems unpowered. The canonical starting point. |

## Documentation corpus (in-game manuals)

| Code | Manual | Contents |
|---|---|---|
| **SOM** | Systems Operation Manual | System descriptions, normal procedures, limits. |
| **QRH** | Quick Reference Handbook | Abnormal/emergency checklists. |
| **FIM** | Fault Isolation Manual | Symptom → decision tree → test → verdict. |
| **WDM** | Wiring Diagram Manual | ASCII schematics, harness routing, connector pinouts, test points. |
| **IPC** | Illustrated Parts Catalog | Part numbers, effectivity, substitutions. |
| **MEL** | Minimum Equipment List | What may be inoperative for departure, with (O)/(M) procedures. |
| **CPM** | Comms Procedures Manual | Radio phraseology, frequencies, readback rules. |
| **RD** | Research Dossier | Fragmentary notes for TL3/TL4 items; replaces manuals you don't have. |

## Human element

| Term | Definition |
|---|---|
| **Closed-loop comms** | Order → readback → execution → report. Enforced for crew and radio. |
| **Readback** | Repeating a clearance/order back verbatim in required phraseology. |
| **Handoff** | Transfer of a vessel between controllers/frequencies. |
| **Traffic information broadcast** | Station-published conditions/traffic bulletin (ATIS analog), lettered ALPHA, BRAVO, ... |
| **MAYDAY / PAN-PAN** | Distress / urgency radio prefixes; trigger priority handling. |
| **Violation** | Recorded procedure breach (missed readback, restricted zone entry); affects reputation. |

## Tech levels

| Code | Name | Shorthand |
|---|---|---|
| **TL0** | Contemporary | 2020s aerospace; fully documented; solder-and-swap repairable. |
| **TL1** | Near-future | 2050–2120; integrated; BITE-rich; LRU culture. |
| **TL2** | Human scifi | Interstellar; exotic but engineered; sealed units, deep BITE. |
| **TL3** | Alien | Non-human design logic; dossiers not manuals; adapters required. |
| **TL4** | Archeotech | Precursor artifacts; observed behavior only; operating rituals. |

## Project fixtures (canonical fictional entities)

| Name | Role |
|---|---|
| **UEV Kestrel** | Default player ship. TL0/TL1 patchwork utility vessel. |
| **TB-1 "Breadboard"** | Minimal test-fixture ship used by the automated test suite. |
| **Meridian Station** | Default station; source of traffic control in early milestones. |
