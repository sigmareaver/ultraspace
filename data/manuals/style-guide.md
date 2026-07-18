# Manual Diagram & Table Style Guide

Status: v0.2 (M1: + semantic state-color mapping) · Owner: engineering+design
Scope: conventions for **generated** manual content and the diagrams the DOCS
reader and printed binder render, plus the live-station screens that share
the diagram grammar. Authored prose style lives in
[docs/design/manuals-as-gameplay.md](../../docs/design/manuals-as-gameplay.md).

## Generated blocks

- Every generated file begins with a `<!-- GENERATED FILE — DO NOT EDIT -->`
  header naming the regeneration command and the source files. Hand edits are
  build failures (`ultraspace generate --check` in CI).
- Generated output is deterministic and byte-stable: device ordering follows
  blueprint order; catalog listings sort by part number; floats use fixed
  formats. A diff in generated output always means a real content change.
- Section anchors (`{#breaker-table}` etc.) are stable IDs — manual prose and
  in-game cross-references link to anchors, never to line positions.

## Units in manual tables

Displayed units follow operator convention, converted from SI at generation:

| Quantity | Display | Example |
|---|---|---|
| Bus capacitance | mF | `8 mF` |
| Current ratings | A | `30 A` |
| Resistance | ohm (word, not Ω) | `50 ohm` |
| Voltage | V | `28 V` |
| Mass | kg | `0.9 kg` |

## Feeder tree grammar (the M1 one-line diagram)

One tree per bus, box-drawing branches, reading left → right as power flows
away from the bus:

```
BUS E  [bus.e]  8 mF
 ├── ctr.bat1  24-110-031  contactor 30 A     → bat1.term → bat1
 ├── tie.a     24-110-030  contactor 30 A     → BUS A
 └── cb.e1     24-120-005  breaker 5 A        → load.avionics.in → load.avionics
```

Rules:

1. Buses are declared in the blueprint (`bus: true` on the node); bus display
   names are the node id upper-cased with dots as spaces (`bus.e` → `BUS E`).
2. Branches list devices attached to the bus in blueprint order; `└──` marks
   the last branch. Device id and rating columns are padded for alignment.
3. The arrow chain shows at most two hops: the far node, then the device ids
   on it. Chains stop at buses, `GND`, or dead ends. Catalog names are *not*
   repeated in trees — they live in the load/parts tables (92-col budget).
4. Transducers never appear in feeder trees (they carry no power); they get
   their own instrumentation table.

## Table column orders (fixed, for muscle memory across chapters)

- **Panel table**: SCL address · device · P/N · type · rating · from · to.
- **Wire list**: node · capacitance · connections as `device.port`, comma-
  separated, blueprint order. Ground row is always last and shows `(ref)`.
- **Load list**: device · P/N · name · resistance · current @ 28 V ·
  protected-by (the upstream switching device).
- **Instrumentation**: telemetry id · P/N · measures · unit · SCL address.
- **Parts list (IPC extract)**: P/N · name · qty · unit mass, sorted by P/N.

## Print/DOCS-reader constraints

Generated tables and trees must render inside 92 columns (binder margin at
132-column terminal with the DOCS split view). The generator enforces this;
content that cannot fit is a generation error, not a wrap.

## Semantic state colors (live screens only)

Manual pages stay monochrome (print). Live station screens color state with
one vocabulary — the semantic contract of
[docs/design/ui-presentation.md](../../docs/design/ui-presentation.md)
("rendering language"); executable source:
`src/ultraspace/presentation/tui/palette.py`. The glyphs are shared with the
printed grammar, so a state reads the same on screen and on paper.

| Meaning | Glyph | Color | M1 examples |
|---|---|---|---|
| Caution — act or be aware | `▲` | amber | active annunciator lamp (backlit tile), `▲ TRIPPED` switch, `MASTER CAUTION: ACTIVE` |
| Advisory — normal transition in progress | `●` | cyan | precharge `● CHARGING` |
| Off / de-energized | `·` | dim | `· OPEN` / `· IDLE` states, idle lamps, de-energized feeder segments, `MASTER CAUTION: clear` |
| Stale / no report | `?` | dim | aged telemetry (`age` tag + `?`), unreported bus voltage (`--- ? (no report)`) |
| Warning — immediate action | `▲` | red | **reserved** — nothing ships warning-level at M1 (severity lands with the QRH, M2) |

Rules:

1. **No color-only information.** Every colored element also carries its
   glyph or the state word itself (colorblind-safe; the accessibility
   commitments in ui-presentation.md). A glyph is a prefix, never a
   replacement for the word.
2. De-energized feeder-tree segments dim (state cell + `→` tail). Topology —
   device ids, branch glyphs — stays lit: it is always true.
3. Stale telemetry is visibly stale: `age` column + `?` tag, dimmed (No God
   View — the display admits when it is guessing).
4. New states pick from this table. Adding a row is a design decision
   (ui-presentation.md delta), not an ad-hoc style choice in a widget.
