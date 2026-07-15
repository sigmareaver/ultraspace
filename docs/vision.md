# Vision

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: design
Related: [design/game-overview.md](design/game-overview.md), [design/simulation-depth.md](design/simulation-depth.md), [process/roadmap.md](process/roadmap.md)

## One-liner

**ULTRASPACE** *(working title)* — the ultra-in-depth spaceship simulation. A text-driven
study sim that models a spacecraft down to the boards in its avionics bays, where operating
and repairing the ship *actively requires* reading the manual.

## The fantasy

You are not an ace pilot. You are the **flight engineer / systems officer** of a working
spacecraft. Your world is bus voltages, coolant loop deltas, breaker panels, fault isolation
trees, part numbers, radio phraseology, and the crew you delegate to. The high you chase is
the one a nuclear plant operator or CERN tech knows: *the procedure worked, the board is
back in, the bus is green, and you understood every step.*

Reference points: Orbiter and DCS-grade study sims, real-world QRH/AOM aviation documents,
nuclear power plant simulators, VATSIM-style ATC discipline, Stationeers/Barotrauma systems
play — but deeper, and in text.

## Design pillars

Every feature must serve at least one pillar and violate none.

1. **Depth is real.** Every gauge reading has a physical cause inside the simulation. No
   flavor-text fakery, no scripted dice-roll "malfunctions" detached from state. If the
   manual explains why a symptom happens, the sim actually implements that why.

2. **Knowledge is the progression system.** There are no XP bars or skill trees for the
   player. You get better by understanding systems, keeping notes, and knowing where in the
   manual to look. Difficulty is tuned by *documentation availability*, never by making the
   simulation lie.

3. **The ship doesn't care about you (No God View).** The player never sees simulation
   state directly — only instrument readings, annunciators, and physical inspection. Sensors
   are themselves simulated components: they drift, fail, lie, and lose power. You get
   symptoms, not diagnoses.

4. **Space is crewed.** The human element is a first-class system: ATC-style traffic
   control with strict phraseology, closed-loop crew orders, readbacks, handoffs, fatigue,
   and trust. Talking on the radio correctly is a skill the game teaches and demands.

5. **Fidelity where you look.** The simulation runs at multiple resolutions and zooms in
   where the player's attention (and multimeter) is. Envelope models keep the whole ship
   coherent; forensic models light up when you open a bay and start probing test points.

6. **The manual is the contract.** In-game manuals are authored first, generated from the
   same data as the simulation where possible, and enforced by automated tests. If the
   manual says a procedure works, CI proves it. (See
   [adr/0005-manual-driven-development.md](adr/0005-manual-driven-development.md).)

## Tech level spectrum

The ship is a patchwork of eras — this is core, not flavor:

- **TL0 Contemporary** — 2020s aerospace. Fully documented, board-level repairable.
- **TL1 Near-future** — 2050–2120. Integrated, self-testing, LRU-swap culture.
- **TL2 Human scifi** — interstellar-capable, exotic but engineered and knowable.
- **TL3 Alien** — non-human design logic. No manuals; research dossiers and adapters.
- **TL4 Archeotech** — precursor artifacts. Function observed, mechanism opaque. Rituals,
  not procedures.

Integrating a TL3 artifact onto a TL0 power bus is a gameplay arc, not a menu click.
See [design/tech-levels.md](design/tech-levels.md).

## Presentation

Primary: a TUI (Textual) organized as crew stations — MFD-like panels, an annunciator row,
a command bar speaking the Ship Command Language (SCL). Secondary: a flat line-mode client
(teletype mode) over the identical core, used for accessibility, scripting, and tests. The
simulation core is strictly headless and presentation-agnostic.
See [design/ui-presentation.md](design/ui-presentation.md) and
[adr/0001-language-and-ui.md](adr/0001-language-and-ui.md).

## Non-goals

- Twitch combat, action minigames, or graphical rendering.
- SPICE/transistor-level electronics. Board depth stops at functional blocks (regulators,
  transceivers, MCUs, relays, fuses) with real netlists, test points, and connectors.
- Orbital mechanics at Principia rigor (v1 uses simplified but honest astrodynamics).
- Economy/4X layers. The ship and its people are the game.
- Multiplayer (revisit post-1.0; architecture must not preclude it).

## Success criteria (what "it works" means)

- A new player, given only the in-game Systems Operation Manual, can bring a cold-and-dark
  ship to powered flight readiness — and could not have done it without the manual.
- A player can diagnose an intermittent data-bus fault to a specific board using the Fault
  Isolation Manual and on-board tools, and the diagnosis is *causally correct*.
- Two players can swap "war stories" that are actually different because the failure model,
  not a script, generated them.
- A printed binder of the ship's manuals is a desirable physical object.
