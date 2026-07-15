# Manuals as Gameplay

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: design
Related: [../adr/0005-manual-driven-development.md](../adr/0005-manual-driven-development.md),
[tech-levels.md](tech-levels.md), [../engineering/data-model.md](../engineering/data-model.md)

Pillar: **Knowledge is the progression system.** The manual is not documentation *about*
the game; it is a game object, a difficulty knob, a test oracle, and the merchandise.

## The corpus

Seven document types (see glossary), organized by ATA-style chapter, mirroring real
aviation/space practice:

| Doc | Player question it answers |
|---|---|
| SOM | "How does this system work and how do I operate it normally?" |
| QRH | "It's beeping — what do I do *right now*?" |
| FIM | "It's broken — how do I find out what, exactly?" |
| WDM | "What's physically connected to what? Where do I probe?" |
| IPC | "What part do I order/swap? What substitutes?" |
| MEL | "Can I fly with this broken? Under what conditions?" |
| CPM | "How do I say this on the radio without sounding like a fool?" |

TL3/TL4 items get **Research Dossiers (RD)** instead — fragmentary, occasionally wrong,
personality-rich documents (a previous engineer's notes, a survey team's report).

## Authoring & single source of truth

Manual content lives in `data/manuals/` as Markdown with YAML frontmatter. Two content
classes:

1. **Authored prose** — system descriptions, theory of operation, warnings. Written by
   humans (with agent assistance), reviewed like code.
2. **Generated sections** — breaker tables, connector pinouts, RT address maps, part
   lists, limit tables. Generated at build time from the same PartType/ship data the sim
   loads. *It is a build error for a generated table to be stale.* This guarantees the
   WDM pinout and the sim netlist can never disagree (no drift, ever).

Procedures (SOM normal, QRH abnormal, FIM tasks) are **structured data** (YAML procedure
spec: steps, expected indications, branch conditions) rendered into the manual as
checklists — and executed headlessly in CI by the procedure runner. **The manual is the
test suite.** See ADR-0005.

## In-game reader

- Full-text search, chapter tree, cross-reference links (`SOM 24-30-01` is a link
  everywhere it appears, including in radio/crew dialogue text).
- Bookmarks, sticky tabs (the worn-binder fantasy), split view next to any station screen.
- Revision system: manuals have revisions; your library might be out of date for your
  hardware's mod state ("effectivity" mismatches are a legitimate trap the IPC resolves).
- Print/export pipeline: HTML/PDF of the whole binder. Out-of-game printing is endorsed —
  the target player owns a ring binder.

## Knowledge acquisition as progression

| Source | What you get |
|---|---|
| Purchase (stations, guilds) | Official manual sets/revisions for owned hardware |
| Salvage/derelicts | Partial sets, wrong revisions, other ships' RDs |
| Faction standing | TL2 proprietary docs, service bulletins |
| Crew experience | Crew members "know" procedures (can execute without the doc) and can dictate notes into your notebook |
| **Player notebook** | First-class document: annotations on any manual page, freeform pages, attachable measurements ("TP-104 read 11.2 V on 2026-03-04"). For TL3/TL4, the notebook *becomes* the manual. |
| Service bulletins | Post-release content hook: SBs arrive by mail, amend manuals, occasionally mandate inspections (live-ops without breaking fiction) |

**Difficulty = documentation completeness** (see game-overview). The sim never changes;
what changes is whether you own FIM Ch 42 or must derive it empirically.

## The "actively requires a manual" bar (testable definition)

A system passes the bar when:

1. Its normal startup contains ≥ 1 ordering constraint or parameter value that is
   *not guessable* from the UI alone (e.g., precharge before tie, spin-up hold time).
2. Violating that constraint produces honest, undesirable physics (tripped protection,
   damaged component) — recoverable at tutorial scale, costly at campaign scale.
3. The constraint's rationale is *explained* in the SOM (we teach, we don't gotcha).
4. A first-time player with the manual open succeeds ≥ 80% in playtest; without it,
   ≤ 20%. (Playtest protocol in [../process/workflow.md](../process/workflow.md).)

Rule 3 is the soul: the manuals must be genuinely good technical writing — the game's
pleasure is *understanding*, not obedience.

## Voice & production values

- SOM/FIM/WDM in dry, precise techwriter voice; warnings in standard WARNING/CAUTION/NOTE
  hierarchy, used honestly (a WARNING always means injury/loss potential in-sim).
- IPC/MEL in bureaucratic-formal voice; RDs in individual human voices (characterization
  channel!); CPM in regulatory voice with example dialogues.
- Typeset for the TUI first (monospace ASCII schematics as first-class diagrams), print
  second. Diagram conventions specified in the WDM style guide (to be authored at M1 as
  `data/manuals/style-guide.md`).

## Open questions

- OQ-MG-1: Manual DRM in-fiction (proprietary TL2 docs with license dongles)? Fun or
  tedious? (Lean: one guild questline, not a system.)
- OQ-MG-2: Crew-dictated notes quality varies by skill — can players get *wrong* notes?
  (Lean: yes, flagged by confidence phrasing; never silently wrong measurements.)
