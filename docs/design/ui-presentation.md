# UI & Presentation

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: design
Related: [command-language.md](command-language.md),
[../adr/0001-language-and-ui.md](../adr/0001-language-and-ui.md)

Two clients over one headless core (see architecture): the **TUI** (primary, Textual) and
**teletype mode** (flat line client). Both speak SCL + telemetry only. If a feature can't
work in teletype mode, its core design is wrong (presentation-independence check).

## TUI concept: the ship as stations

The screen is a crew station, not a dashboard-of-everything. Station switching is
instant (function keys), state persists per station. This mirrors the fiction (you are
at a console) and enforces information discipline: you can't see everything at once —
choosing what to watch *is* gameplay.

| Station | Key | Contents (v1) |
|---|---|---|
| SYS/EPS | F1 | Bus diagram (live ASCII schematic), breaker panel, source/load tables |
| THERM | F2 | Loop diagram, node temps, radiator/heater states |
| DATA | F3 | Bus analyzer, RT status map, VMC modes, BITE reports |
| COMM | F4 | Frequency stack, live traffic log, message composer, broadcast decoder |
| NAV | F5 | State vector, burn plan/monitor, approach corridor view |
| MAINT | F6 | Bay/rack browser, tool state, spares inventory, bench, records |
| DOCS | F7 | Manual reader (split-view capable with any station) |
| LOG | F8 | Notebook, ship log, FDR review, nonconformance log |

Persistent chrome, always visible:

- **Annunciator row** (top): master caution/warning + chapter tiles (`ELEC`, `THERM`,
  `DATA`…), lamp-test-able (`sys annunciator test` — lamps are devices; they burn out).
- **Command bar** (bottom): SCL prompt with completion, last-result line.
- **Clock strip**: sim time (UTC-like), mission elapsed, time compression state.

## Rendering language (the aesthetic contract)

- Monospace, box-drawing, dense. The look is "1553 bus analyzer meets glass cockpit",
  not "hacker movie". No gratuitous animation; things move when physics moves.
- **Live schematics**: WDM diagrams rendered from the same netlist data, with live
  telemetry annotations (bus voltages inline, breaker states as glyphs, de-energized
  segments dimmed). The schematic *is* the mimic display — one diagram grammar for
  manual pages and live screens. Diagram grammar spec to be authored at M1
  (`data/manuals/style-guide.md`).
- Color is semantic and redundant with glyphs (colorblind-safe): warning red `▲`,
  caution amber `▲`, advisory cyan `●`, off/stale dim + `?`. Stale data is *visibly*
  stale (age tag), per No God View.
- Degrade gracefully: minimum 80×24 (reduced layouts), designed target 132×43 (a nod to
  real terminal history).

## Teletype mode (flat client)

Line-in/line-out client: SCL in, formatted text out, plus asynchronous event lines
(annunciators, radio calls) interleaved with a prefix discipline (`*` events, `>` echo,
plain results). Purposes: accessibility (screen readers), scripting/CI, playing over ssh
from anywhere, and the pure-fantasy teletype experience. Feature-parity is contractual,
enforced by running all procedure-runner tests through the teletype client codepath.

## Input philosophy

- Everything typeable; frequent actions also bindable (breaker toggles from panel focus,
  station function keys). Panel interactions *emit SCL* (visible in the command bar as
  they fire — the UI teaches the language passively, like watching an operator's hands).
- No mouse required anywhere; mouse supported where Textual gives it cheaply.
- A `tutor` overlay mode annotates station elements with their SCL addresses and manual
  chapter refs (difficulty-tier gated, see game-overview difficulty axes).

## Sound (v1: minimal, honest)

Terminal bell for master caution only, off by default. Post-1.0: optional sound pack
(fans, relays, radio squelch) — but the game must be *fully* playable silent (deaf
players, ssh sessions).

## Accessibility commitments

- Teletype mode is the accessibility floor: 100% of gameplay, screen-reader friendly.
- No color-only information; no timing-critical input in base difficulty; all text
  export-able; font/size owned by the player's terminal (we never fight the terminal).

## Anti-scope-creep fences

- No graphics mode, no web frontend before 1.0 (textual-web may fall out for free;
  fine, but zero engineering budget allocated).
- No in-TUI windowing system beyond station split-view (DOCS + one station). If a layout
  needs three panes, the station design is wrong.

## Open questions

- OQ-UI-1: Split-view DOCS default-on for new players? (Playtest at M1.)
- OQ-UI-2: Persistent mini bus-state strip on non-EPS stations? Risks dashboard creep vs.
  reduces station thrash. (Prototype at M2, decide by playtest.)
- OQ-UI-3: Configurable multi-function display (MFC) with side soft-keys — resolved by
  [ADR-0006](../adr/0006-diegetic-displays.md) (Proposed): MFCs are simulated parts;
  the pane fence binds designers (baseline-fit rule), not players. Prototype at M2
  alongside OQ-UI-2 (a mini bus strip is a degenerate MFC page). This section's fences
  get their wording update when the ADR is Accepted.
