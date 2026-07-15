# ADR-0003: YAML content + pydantic schemas + generated manual tables

Status: Accepted
Date: 2026-07-14
Deciders: project maintainer + founding agent session

## Context

The game is content-dominated: parts, netlists, blueprints, procedures, manuals,
scenarios, phraseology. Content must be authorable by humans and agents in review-able
diffs, validated mercilessly (a dangling part number is a broken game), stable enough
for saves/notebooks to reference for years, and shared between the sim and the manual
build (single source of truth — the WDM pinout must equal the sim netlist forever).

## Decision

1. **YAML** (safe loader) for all authored structured content; **Markdown+frontmatter**
   for manual prose; **JSON Lines** for machine streams (FDR).
2. **pydantic v2 schemas** at the load boundary, with `schema: name/version` headers;
   hard fail on unknown major, migrate on minor. Schemas are code-reviewed like APIs.
3. **IDs are forever** (kebab-case, pack-namespaced); renames = new ID + alias.
4. **Mechanical manual content is generated** from part/blueprint data (breaker tables,
   pinouts, RT maps, IPC lists) at build time; generated blocks are injected by ID and
   cannot be hand-edited; CI diff-checks staleness.
5. Content tree layout and validation CLI as specified in data-model.md.

## Consequences

- Agents and humans author in the same reviewable medium; content bugs surface at
  build time with file/line context, not at tick time.
- The manuals physically cannot drift from the simulation for mechanical facts —
  the core MDD enabler alongside ADR-0005.
- Modding falls out for free (core content is pack `core:`).
- Costs: YAML's foot-guns (mitigated: safe loader, schemas, no anchors/merge keys
  allowed by lint), schema-evolution discipline, generator toolchain to maintain.

## Alternatives considered

- **JSON**: no comments, hostile to hand-authoring at our volume; rejected for authored
  content (kept for streams).
- **TOML**: poor nesting ergonomics for netlists/procedures.
- **Custom DSL**: maximum expressiveness, maximum tooling tax; rejected until proven
  necessary (procedure spec is the likeliest future candidate — revisit trigger below).
- **Content in Python**: unreviewable-by-nonprogrammers, unvalidatable, arbitrary code
  in mods; rejected outright.

## Revisit triggers

- Procedure specs in YAML grow conditional logic beyond ~3 branch types (→ design a
  proper checklist DSL with a compiler to today's structure, keeping files migratable).
- Content load time > 5 s for the full tree (→ compiled cache layer, same source
  format).
- Schema minor-migration burden exceeds one helper per release (→ invest in migration
  framework).
