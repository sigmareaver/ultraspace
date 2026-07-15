# Tech Levels

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: design
Related: [manuals-as-gameplay.md](manuals-as-gameplay.md),
[failure-and-repair.md](failure-and-repair.md), [../vision.md](../vision.md)

Tech level (TL) is a property of **individual parts**, not ships. A vessel is a patchwork;
integration friction between TLs is core gameplay ("the ship of Theseus loop").

## The five levels

### TL0 — Contemporary (2020s–2030s Earth aerospace)
- **Design culture:** discrete boards, connectorized harnesses, conservative margins.
- **Docs:** complete SOM/FIM/WDM/IPC down to test points and pinouts.
- **Diagnosis:** DMM + oscilloscope + bus analyzer; generous test points; readable firmware.
- **Repair:** to component level. Solder at the bench; swap fuses, relays, boards.
- **Failure character:** honest wear-out, contamination, connector fretting. Predictable.
- **Feel:** an old truck. Slow, hungry, *knowable*. The tutorial-and-trust layer.

### TL1 — Near-future (2050–2120)
- **Design culture:** high integration, LRU-swap philosophy, rich BITE, digital everything.
- **Docs:** complete but assume you'll swap, not fix; SRU repair possible with bench tools.
- **Diagnosis:** BITE narrows to SRU quickly — *when BITE itself is healthy* (BITE lies
  are a signature TL1 fault class).
- **Repair:** LRU/SRU swap; component-level only for the brave with donor boards.
- **Failure character:** software/SEU faults, mode confusion, sensor voting disagreements.
- **Feel:** a modern airliner. Efficient, opinionated, occasionally gaslighting.

### TL2 — Human scifi (interstellar-capable)
- **Design culture:** exotic physics engineered by humans: superconducting distribution,
  fusion torch drives, mag-shielded volumes. Sealed "no user serviceable parts" units.
- **Docs:** exist but specialized/proprietary; acquiring the *right revision* is gameplay.
- **Diagnosis:** deep BITE with authoritative self-reports; external instruments see
  boundaries only (you can't probe inside a sealed cryomodule).
- **Repair:** module exchange, recertification procedures, manufacturer conditions.
- **Failure character:** rare but dramatic; failure modes are *systemic* (quench, mode
  collapse) with long recovery procedures. The nuclear-plant fantasy lives here.

### TL3 — Alien
- **Design culture:** non-human logic. No boards; e.g., grown conductive lattices,
  fluidic computation, distributed sensing skin. Interfaces don't match human standards.
- **Docs:** none. **Research Dossiers** only — fragmentary, sometimes wrong, written by
  prior owners/researchers. The player's notebook becomes the manual.
- **Diagnosis:** by experiment. Instrument the boundary, perturb, record. The game
  provides honest physics behind consistent (per-artifact-species) behavior rules.
- **Repair:** you don't repair, you *coax*: environmental conditions, power quality,
  isolation. Adapters (human-built bridge LRUs, TL0–TL2) are how alien tech joins ship
  networks — and the adapter is a fault surface you *can* fix.
- **Failure character:** behavioral, environmental, sometimes apparently moody — but
  always deterministic under the hood (the sim never rolls dice without physics).

### TL4 — Archeotech
- **Design culture:** precursor artifacts. Effects reliable; mechanism opaque *by design
  of the game*: the sim models the artifact's boundary contract, not its interior.
- **Docs:** RDs at best, often hazard-focused ("do not exceed 40 K at mounting flange").
- **Diagnosis/Repair:** neither. You have **operating rituals**: empirically discovered
  procedures that keep it happy. Violate them and boundary behavior degrades or becomes
  hazardous. Rituals can be *discovered wrong* — refining them is endgame content.
- **Failure character:** the artifact never breaks. Your ship around it does.

## Gameplay implications matrix

| Axis | TL0 | TL1 | TL2 | TL3 | TL4 |
|---|---|---|---|---|---|
| Manual coverage | Full | Full (swap-biased) | Gated/revisioned | Dossiers | Fragments |
| Diagnosable to | Block | SRU (BITE) | Module boundary | Boundary behavior | Boundary contract |
| Repair strategy | Fix | Swap | Exchange + recert | Coax + adapters | Ritual compliance |
| Spares logistics | Cheap, common | Standardized | Expensive, sourced | Irreplaceable | Unique |
| Power density / capability | 1× | 3× | 10× | 30×? | Rule-breaking |
| Failure legibility | High | Medium (BITE lies) | Low freq, high drama | Experimental | Hazard-only |
| Player literacy required | Electronics | Systems/modes | Procedures | Science method | Archaeology |

The capability multipliers are the temptation knob: the campaign repeatedly offers the
player *more power for less knowability*.

## Integration friction (the patchwork rules)

1. **Interface standards are per-TL.** Connectors, voltages, data protocols, fluid
   fittings differ. Cross-TL connection requires an adapter part (which has its own
   part number, failure modes, and manual section).
2. **Documentation debt is contagious.** An undocumented device on a documented bus makes
   the *bus* harder to diagnose (FIM trees gain "if TL3 device attached..." branches
   only if the player/crew has written notes about it).
3. **Certification & MEL.** Stations at higher regulation levels may refuse docking
   clearance to ships with uncertified TL3/TL4 integrations — human-element pressure
   against hoarding alien tech, and a reason paperwork exists.
4. **The adapter principle (design law).** Alien capability must always be mediated by a
   human-tech adapter the player can understand, monitor, and fix. This keeps every
   gameplay chain terminating in something knowable.

## Authoring rules per TL (for content writers)

- TL0/TL1 parts must ship with complete manuals at authoring time (CI validates refs).
- TL2 parts must define which manual sections exist and their acquisition paths.
- TL3/TL4 parts must define a **boundary contract** (inputs → outputs → hazards) and at
  least one RD fragment; interior detail is forbidden in data (enforce opacity).
- Every TL3/TL4 part must be integrable via at least one adapter chain reachable in play.

## Open questions

- OQ-TL-1: Do TL3 "species" share design languages the player can learn across artifacts?
  (Lean: yes — 2–3 alien design cultures with consistent grammars; huge replay value.)
- OQ-TL-2: Can players author RD pages that persist across ships/saves? (Lean: notebook
  is per-campaign; meta-progression decided at M5.)
