# Data Model & Content Pipeline

Status: Draft v0.2 · Last updated: 2026-07-14 · Owner: engineering
Related: [architecture.md](architecture.md),
[../design/manuals-as-gameplay.md](../design/manuals-as-gameplay.md),
[../adr/0003-content-format.md](../adr/0003-content-format.md)

Everything the player can touch is data. Code implements physics and behaviors; content
files declare what exists. A new pump, manual chapter, or scenario must be addable
without touching `src/` (modding is a side effect of our own workflow).

## Content tree

```
data/
  parts/            # PartType definitions (YAML), by chapter: parts/24/pdu-2.yaml
  ships/            # blueprints: ships/uev-kestrel/blueprint.yaml, harness.yaml
  manuals/          # Markdown+frontmatter by manual/chapter: manuals/som/24/24-30-01.md
  procedures/       # executable procedure specs: procedures/som/24-30-01-cold-start.yaml
  comms/            # phraseology grammar, station pages, controller personalities
  scenarios/        # scenario specs
  packs/            # third-party/expansion packs (same layout, namespaced IDs)
```

## Core schemas (pydantic v2, versioned)

Every file has `schema: <name>/<version>` in its header. Loaders hard-fail on unknown
majors, warn-and-migrate on minors. Schemas live in `src/ultraspace/content/schemas/`.

### PartType (`part/1`)

```yaml
schema: part/1
id: pdu-2                      # stable, namespaced when in packs ("corepack:pdu-2")
part_number: "24-118-100"      # IPC identity; effectivity/supersedure links
name: "Power Distribution Unit, Type 2"
ata: 24
tech_level: 0
mass_kg: 8.4
interfaces:                    # typed ports; the ONLY way devices touch networks
  - {port: PWR_IN,  kind: electrical, connector: J1, rating: {v: 32, a: 60}}
  - {port: DB_A,    kind: data,       connector: J3, protocol: db1553}
  - {port: COLD_PLATE, kind: thermal, node: mount}
sru: [{id: a1, name: "input filter board"}, {id: a2, name: "bus controller board"}]
netlists:                      # per-SRU block netlists (L2 forensic model source)
  a2:
    blocks:
      - {id: U1, kind: reg_ldo, out_v: 12.0, ...}
      - {id: U3, kind: mcu, fw: "pdu2-fw", watchdog_ms: 250}
      - {id: U4, kind: bus_xcvr, bus: DB_A}
      - {id: F4, kind: fuse, rating_a: 2.0}
    nets: [{id: N12V, nodes: [U1.out, U3.vcc, U4.vcc, TP104]}, ...]
    test_points: [{id: TP104, net: N12V, doc: "wdm/24/fig-24-41-3"}]
failure_modes:                 # per block/port; rates feed the stress model
  - {target: U4, mode: seu_latchup, base_rate: ..., detect: [bite, bus_analyzer]}
behaviors: {l0: pdu_envelope, l1: pdu_dynamic, l2: netlist}   # model bindings by name
docs: {som: [24-30-01], fim: [24-41], wdm: [fig-24-41-3], ipc: 24-118}
```

**Validation (CI + pre-commit):** dangling refs (docs, part numbers, net nodes,
behavior names) are build errors. TL3/TL4 parts must *omit* netlists (opacity is
schema-enforced) and define `boundary_contract` instead.

### Ship blueprint (`ship/1`)
Bays/racks (physical location — access time and inspection verbs are location-based),
LRU placements (PartType + serial + initial wear/config), harness segments and connector
mates (fault-capable devices), breaker panel layout, sensor→data-bus wiring. Blueprint
traversal order defines scheduler registration order (determinism, see kernel spec).

### Procedure (`procedure/1`)
Steps with: SCL command or manual action (`inspect`, `probe TP-104`), expected
indication (telemetry predicate with tolerance + timeout), on-fail branch (goto step /
abort ref / QRH ref), warnings/notes (rendered into manual). Executable by the runner
(player-interactive, crew-autonomous, CI-headless — same engine, see command-language).

### Scenario (`scenario/1`)
Ship + wear/config deltas, environment timeline, fault schedule (device, mode, tick or
condition), crew roster/state, world state (traffic density, station config, broadcast
letter), goals (telemetry predicates), debrief criteria, master seed.

### Manual page (frontmatter)
`manual: som`, `ata: 24`, `section: 24-30-01`, `title`, `effectivity: [part_numbers]`,
`requires: [generated:breaker-table-bus-a]` — generated blocks are referenced by ID and
injected at build; hand-editing generated output is impossible by construction (they
live only in build artifacts).

## Identity & versioning rules

1. **IDs are forever.** Content IDs (`pdu-2`, `som/24-30-01`) never change meaning;
   renames are new IDs + deprecation aliases (saves and notebooks reference IDs).
2. **Content hash** (per-file blake2b, tree-level manifest) participates in the
   determinism triple (seed, content hash, journal) and is recorded in every save/FDR.
3. **Packs namespace everything**; the core game is itself a pack (`core:`), proving
   the mechanism.
4. Save migration policy: N-1 minor compatibility guaranteed; majors get migration
   tools or an honest "museum mode" (load-only).

## Generators (single source of truth machinery)

`ultraspace generate` (implemented M1 as `ultraspace.content.generators` — in the
package, not `tools/`, because the in-game DOCS reader renders the same artifacts at
runtime): emits panel tables, feeder trees, wire lists, load lists, instrumentation
maps, and IPC extracts from parts+blueprint. Output is **committed** under
`data/manuals/*/generated/` (v0.2 decision: committed-generated makes hardware changes
show their manual impact in PR diffs) and byte-stability is enforced —
`ultraspace generate --check` plus the staleness test fail CI on any drift or hand
edit. Board-netlist pinout sheets and diagram layout hints join at M2 with L2;
*connectivity* is always generated truth. Formatting contract:
`data/manuals/style-guide.md` (incl. the 92-column print constraint, enforced at
generation time).

## Authoring ergonomics

- `ultraspace validate` — whole-tree validation with file/line errors (also pre-commit).
- `ultraspace dev --hot` — content hot-reload against a running sim where safe (parts:
  no; manuals/scenarios: yes).
- Schema docs auto-published to `docs/engineering/schemas/` (generated, do not edit) so
  content authors never read pydantic source.
