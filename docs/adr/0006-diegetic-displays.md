# ADR-0006: Diegetic displays — MFCs as simulated parts, panes as consoles

Status: Proposed
Date: 2026-07-14
Deciders: project maintainer + agent session

## Context

Players want configurable multi-function displays (MFCs) with side soft-keys — the
glass-cockpit staple. Two fences in ui-presentation.md appear to forbid this:

1. "The screen is a crew station... you can't see everything at once — choosing what
   to watch *is* gameplay."
2. "No in-TUI windowing system beyond station split-view (DOCS + one station). If a
   layout needs three panes, the station design is wrong."

But those fences are proxies for two underlying goals: **(a)** information discipline
must remain a gameplay resource, and **(b)** zero engineering budget on a terminal
window manager. Neither goal actually requires that display capability be fixed by
the UI. Meanwhile the game's whole method is to push constraints out of the interface
and into the simulation (No God View, instruments-as-devices, failures-as-state).
A configurable display implemented as a UI feature would violate the fences; the same
capability implemented as *ship hardware* strengthens them.

Interpretive ruling recorded here: **the fences bind designers, not players.** They
guarantee that no procedure, manual, or acceptance vignette ever *requires* more
simultaneous visibility than the baseline fit provides. They do not cap what a player
may build, buy, or watch. In a deep sim, player freedom beyond the required baseline
is the product; the limit on that freedom must be the ship, not the window manager.

## Decision

**Display real estate is ship hardware. The MFC is a simulated part; the TUI renders
consoles, it does not own displays.**

1. **MFC as Block/LRU**: an MFC is a content-defined part (part spec, IPC entry,
   WDM presence) with: an EPS feed (it browns out honestly), a data-network
   subscription (it can only show what its bus carries — No God View holds by
   construction), a page set defined in content data, side soft-keys, and `Fault`
   modes like any device (stuck pixels rows, dead soft-key, frozen page — all data,
   not exceptions).
2. **Soft keys emit SCL**: every bezel press appears in the command bar as the SCL it
   emitted (`mfc.1 page eps-summary`, `mfc.1 sel 3`), consistent with the input
   philosophy — the panel teaches the language. The FDR journal remains the sole
   replay input.
3. **Pages are generated views**: MFC pages use the same diagram/table grammar as the
   WDM and station screens (one grammar for manuals, stations, and MFCs). Page
   definitions are content, validated like parts; mechanical page content is
   generated, never hand-edited.
4. **The pane fence is restated, not repealed**: the TUI layout remains **at most two
   panes** (primary station + one auxiliary: DOCS or any fitted display device). The
   third-pane prohibition stands as an engineering rule. What changes is pane
   *content*: an auxiliary pane may render any display device fitted to the ship, and
   station screens themselves are understood as fixed console instruments.
5. **Designer-side baseline rule** (the fence, relocated): every procedure and
   acceptance vignette must be completable with the ship's *SOM baseline fit* —
   one station screen + the manual. Requiring a second MFC page to be visible
   simultaneously is a design defect, same severity as a three-pane layout. Extra
   fitted MFCs are player advantage (fewer station switches), never a requirement.
6. **Fit is campaign surface**: MFC units occupy rack/panel positions, draw power,
   cost money, appear in IPC, and are legitimate acquisition/upgrade targets (TL
   variance applies: a TL3 display artifact is a research object like anything else).

## Consequences

- The "configurable display" feature costs almost no UI engineering: the TUI gains
  one widget (render a display device's active page + soft-key strip); everything
  else is parts, content, and the existing solver/telemetry machinery.
- Information discipline becomes *more* honest: the limit on simultaneous knowledge
  is now diegetic (fitted hardware, powered and fed by real buses) instead of an
  arbitrary UI rule — and it's tunable per ship, scenario, and campaign economy.
- Displays can now fail, which is pure gameplay profit (QRH: "MFC 1 FROZEN — verify
  with second source before acting on stale page").
- Teletype parity is preserved cheaply: an MFC page is text; `mfc.1 read` prints it.
  Feature-parity remains contractual.
- Costs accepted: page-definition schema to design and validate; MFC telemetry
  freshness must be modeled (a page is a report, so it carries age/staleness like
  every instrument); conformance suites must pin the baseline fit so a content edit
  adding an MFC can't silently become load-bearing for a procedure.
- The two-pane terminal limit slightly narrows "freedom is king": freedom is in what
  displays can show, not in window count. One terminal is one seat's eyes.

## Alternatives considered

- **UI-level configurable panes** (window manager): violates both fence goals;
  budget-hungry; un-diegetic; nothing stops it from becoming dashboard-of-everything.
  Rejected.
- **Do nothing (stations only)**: leaves a real player desire unmet and wastes the
  fiction's best answer to it; rejected — the hardware framing was too good.
- **Persistent mini-strips per station** (OQ-UI-2 alone): solves station-thrash but
  is designer-configured, not player-configured; subsumed — a mini-strip is a
  degenerate MFC page, and OQ-UI-2's prototype should be built *as* one.
- **Unlimited panes bounded only by fitted hardware**: purest freedom reading, but
  buys terminal-layout complexity (the exact thing fence (b) exists to prevent) for
  marginal benefit at 132×43. Rejected for now; see revisit triggers.

## Revisit triggers

- Playtests show players thrashing between MFC pages *within* the two-pane limit to
  complete common tasks → the baseline fit is wrong or a page design is bad; fix
  content before touching the pane rule.
- Multi-crew/multi-client play (M3+, several terminals attached to one sim as
  different seats) — the honest way to increase simultaneous eyes; if implemented,
  re-examine whether the aux pane still earns its place.
- Terminal sizes ≫ 132×43 become the playtested norm and the second pane routinely
  sits empty or trivially used → consider whether fitted hardware should drive a
  richer layout.
- Page-definition schema fails to express a real instrument page without ad-hoc code
  (mirrors ADR-0003's expressiveness trigger).
